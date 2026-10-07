#!/usr/bin/env python3
"""Manual trusted-main diagnostic. Only ciphertext leaves the existing container.

No application startup, schema migration, bootstrap, provider call or device row
export. DB reads are bounded, mode=ro/query_only transactions. Missing evidence is
unavailable, never proof of zero spend, recoverability or volume continuity.

Parent retains the ephemeral private RSA key offline. Envelope fields are Base64;
unwrap with RSA-OAEP/MGF1 SHA256 (label=None), then AESGCM.decrypt with AAD below.
Decrypted UTF-8 JSON has harmless trailing spaces for constant artifact size.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

AAD = b'tutor-guardian/runtime-readiness/v1'
PAID = ('azure_deepseek', 'deepseek', 'deepseek_aux', 'deepseek_fallback')
TABLES = ('cloud_budget_months', 'cloud_budget_attempts', 'cloud_budget_carry',
          'cloud_budget_activation', 'cloud_budget_identity')
UNKNOWN = {'status': 'unavailable'}


def redacted_endpoint(value):
    try:
        p = urlsplit(value)
        if p.scheme not in ('http', 'https') or not p.hostname:
            return 'unavailable'
        host = p.hostname
        if not re.fullmatch(r'[a-zA-Z0-9.:-]+', host):
            return 'unavailable'
        host = f'[{host}]' if ':' in host else host
        port = f':{p.port}' if p.port else ''
        return f'{p.scheme}://{host}{port}'
    except (TypeError, ValueError):
        return 'unavailable'


def safe_model(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._/-]{1,128}', value) else 'unavailable'


def project_mounts(mounts):
    return [{'type': m.get('Type'), 'name': m.get('Name'), 'source': m.get('Source'),
             'destination': m['Destination'], 'read_write': m.get('RW') is True}
            for m in mounts if m.get('Destination') == '/app/ops']


def _aggregate(conn, sql, args=()):
    try:
        row = conn.execute(sql, args).fetchone()
        return row
    except sqlite3.Error:
        return None


def _continuity(conn, path, deadline):
    result = {'anchor_present': Path(str(path) + '.cloud-budget-anchor').is_file(),
              'witness_matches': None, 'external_continuity_proof_required': True,
              'observation_atomic_with_writers': False}
    try:
        identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone()
        if not identity or not result['anchor_present']:
            return result
        anchor_path = Path(str(path) + '.cloud-budget-anchor')
        if anchor_path.stat().st_size > 8192:
            return result
        anchor = json.loads(anchor_path.read_text())
        digest = hashlib.sha256()
        for table in TABLES:
            schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not schema:
                return result
            digest.update(json.dumps(schema).encode())
            for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid'):
                if time.monotonic() > deadline:
                    return result
                digest.update(json.dumps(row, separators=(',', ':')).encode())
                digest.update(b'\n')
        result['witness_matches'] = anchor.get('db_identity') == identity[0] and anchor.get('digest') == digest.hexdigest()
    except (sqlite3.Error, OSError, ValueError, TypeError, AttributeError):
        pass
    return result


def database_report(path, month, now):
    """All SELECTs share a bounded read transaction; no absent DB is created."""
    path = Path(path)
    result = {'status': 'unavailable', 'path': str(path),
              'monthly_paid_usage': dict(UNKNOWN), 'build_census': dict(UNKNOWN),
              'session_mints': dict(UNKNOWN), 'recovery': dict(UNKNOWN)}
    conn = None
    try:
        if not path.is_file():
            return result
        stat = path.stat()
        result['file_identity'] = {'device': stat.st_dev, 'inode': stat.st_ino}
        deadline = time.monotonic() + 15
        conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=0.2)
        conn.execute('PRAGMA query_only=ON')
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        conn.execute('BEGIN')
        valid = "typeof(prompt_tokens)='integer' AND prompt_tokens>=0 AND typeof(completion_tokens)='integer' AND completion_tokens>=0"
        marks = ','.join('?' for _ in PAID)
        row = _aggregate(conn, f"SELECT COUNT(*), COALESCE(SUM(CASE WHEN {valid} THEN 0 ELSE 1 END),0), "
                         "COALESCE(SUM(CASE WHEN strftime('%Y-%m',ts) IS NULL THEN 1 ELSE 0 END),0), "
                         f"COALESCE(SUM(CASE WHEN {valid} THEN prompt_tokens+completion_tokens ELSE 0 END),0) "
                         f"FROM llm_calls WHERE provider IN ({marks}) AND (strftime('%Y-%m',ts)=? OR strftime('%Y-%m',ts) IS NULL)", (*PAID, month))
        if row and all(type(n) is int and n >= 0 for n in row):
            result['monthly_paid_usage'] = dict(zip(('rows', 'invalid_usage_rows', 'unknown_timestamp_rows', 'known_tokens'), row), status='available', month=month)
        row = _aggregate(conn, "SELECT COUNT(*), COALESCE(SUM(typeof(build_number)='integer' AND build_number>=106),0), "
                         "COALESCE(SUM(typeof(build_number)='integer' AND build_number>=0 AND build_number<106),0), "
                         "COALESCE(SUM(build_number IS NULL OR typeof(build_number)!='integer' OR build_number<0),0), "
                         "COALESCE(SUM(typeof(build_number)='integer' AND build_number>=106 AND datetime(updated_at)>=datetime(?,'-30 days') AND datetime(updated_at)<=datetime(?)),0) FROM push_tokens", (now, now))
        if row:
            result['build_census'] = dict(zip(('rows', 'at_least_106', 'below_106', 'unknown_build', 'active_30d_at_least_106'), row), status='available')
        row = _aggregate(conn, "SELECT COUNT(*), COUNT(DISTINCT device_id), COUNT(DISTINCT CASE WHEN device_id IN "
                         "(SELECT device_id FROM push_tokens WHERE typeof(build_number)='integer' AND build_number>=106) THEN device_id END) "
                         "FROM api_tokens WHERE strftime('%Y-%m',created_at)=?", (month,))
        if row:
            result['session_mints'] = dict(zip(('month_rows', 'month_devices', 'devices_at_least_106'), row), status='available')
        row = _aggregate(conn, "SELECT COUNT(*), COUNT(DISTINCT canonical_device), (SELECT COUNT(*) FROM device_fold_log), "
                         "COUNT(DISTINCT CASE WHEN canonical_device IN (SELECT device_id FROM push_tokens "
                         "WHERE typeof(build_number)='integer' AND build_number>=106) THEN canonical_device END) FROM device_aliases")
        if row:
            result['recovery'] = dict(zip(('folded_aliases', 'families_with_folded_aliases', 'fold_log_rows', 'families_at_least_106'), row), status='available', pending_recoverable_devices='unavailable')
        result['continuity'] = _continuity(conn, path, deadline)
        result['status'] = 'available'
    except (OSError, sqlite3.Error, ValueError):
        pass
    finally:
        if conn is not None:
            conn.close()
    return result


def collect_report(mounts):
    # This module only defines an environment-backed dataclass; never import main,
    # init_db, gateway or a recovery service (they can initialize/migrate state).
    from app.config import llm_config
    from importlib.metadata import version
    cfg = llm_config.LLM
    root = Path(llm_config.__file__).resolve().parents[3]
    now = datetime.now(timezone.utc).isoformat()
    month = now[:7]
    primary_cap = cfg.deepseek_primary_monthly_token_cap
    result = {'version': 1, 'collected_at_utc': now,
              'crypto_version': version('cryptography'),
              'cloud': {
                  'primary': {'provider': safe_model(cfg.primary_provider), 'endpoint_origin': redacted_endpoint(cfg.deepseek_base_url), 'model': safe_model(cfg.deepseek_model), 'cap': primary_cap},
                  'fallback': {'enabled': cfg.deepseek_fallback_enabled, 'endpoint_origin': redacted_endpoint(cfg.deepseek_base_url), 'model': safe_model(cfg.deepseek_model), 'cap': cfg.deepseek_fallback_monthly_token_cap},
                  'azure': {'enabled': cfg.cloud_tier_enabled, 'endpoint_origin': redacted_endpoint(cfg.azure_endpoint), 'model': safe_model(cfg.azure_model), 'cap': primary_cap},
                  'refusal_model': safe_model(cfg.deepseek_model_fallback),
                  'in_process_model_switches': 'unavailable', 'invoice_guarantee': False},
              'session_mint_enforced': os.environ.get('SESSION_MINT_ENFORCE', '').strip().lower() in ('1', 'true', 'yes'),
              'mounts': mounts,
              'telemetry': database_report(root / 'ops/sessions.db', month, now),
              'conversations': database_report(Path(os.environ.get('CONVERSATIONS_DB', str(root / 'ops/conversations.db'))), month, now)}
    for name in ('telemetry', 'conversations'):
        path = Path(result[name]['path']).resolve()
        result[name]['path'] = str(path)
        mount = next((m for m in mounts if path.is_relative_to(m['destination'])), None)
        result[name]['persistent_mount_observed'] = mount is not None
        result[name]['file_and_mount_device_match'] = None
        if mount and path.is_file():
            result[name]['file_and_mount_device_match'] = path.stat().st_dev == Path(mount['destination']).stat().st_dev
    return result


def _recipient(pem):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    if not isinstance(pem, bytes) or len(pem) > 16384:
        raise ValueError('invalid recipient')
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, rsa.RSAPublicKey) or not 2048 <= key.key_size <= 8192:
        raise ValueError('invalid recipient')
    return key


def encrypt_report(report, pem):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = _recipient(pem)
    aes = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    raw = json.dumps(report, separators=(',', ':'), sort_keys=True).encode()
    if len(raw) > 65536:
        raise ValueError('report exceeds fixed envelope')
    # Actions exposes artifact sizes. Pad JSON with valid trailing whitespace so
    # changes in private aggregate count lengths cannot change that public size.
    raw = raw.ljust(65536, b' ')
    wrap = key.encrypt(aes, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    b64 = lambda value: base64.b64encode(value).decode('ascii')
    return json.dumps({'version': 1, 'algorithm': 'AES-256-GCM+RSA-OAEP-SHA256',
                       'wrapped_key': b64(wrap), 'nonce': b64(nonce),
                       'ciphertext': b64(AESGCM(aes).encrypt(nonce, raw, AAD))})


def container_report(payload):
    # Verify existing crypto APIs and the recipient before any DB/config read.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
    pem = payload['public_key'].encode()
    _recipient(pem)
    # Libraries/config must never leak incidental output to Actions logs.
    with contextlib.redirect_stdout(sys.stderr):
        report = collect_report(payload['mounts'])
    return encrypt_report(report, pem)


def main(argv=None):
    try:
        expected = os.environ.get('READINESS_EXPECTED_SHA', '')
        if (os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
                or os.environ.get('GITHUB_REF') != 'refs/heads/main'
                or not re.fullmatch(r'[0-9a-f]{40}', expected)
                or os.environ.get('GITHUB_SHA') != expected
                or os.environ.get('READINESS_WORKFLOW_SHA') != expected):
            raise ValueError('trusted workflow context required')
        pem = os.environ['REPORT_PUBLIC_KEY_PEM']
        if len(pem) > 16384 or not pem.startswith('-----BEGIN PUBLIC KEY-----'):
            raise ValueError('invalid recipient')
        inspected = subprocess.run(['docker', 'inspect', '--format', '{{json .Mounts}}', 'tg_backend'], capture_output=True, timeout=10, check=True)
        mounts = project_mounts(json.loads(inspected.stdout))
        payload = json.dumps({'source': Path(__file__).read_text(), 'public_key': pem, 'mounts': mounts}).encode()
        launcher = "import json,sys; p=json.load(sys.stdin); ns={'__name__':'readiness'}; exec(compile(p['source'],'<trusted-readiness>','exec'),ns); print(ns['container_report'](p))"
        child = subprocess.run(['docker', 'exec', '-i', 'tg_backend', 'python', '-c', launcher], input=payload, capture_output=True, timeout=75, check=True)
        if len(child.stdout) > 4_000_000:
            raise ValueError('invalid envelope')
        envelope = json.loads(child.stdout)
        if set(envelope) != {'version', 'algorithm', 'wrapped_key', 'nonce', 'ciphertext'} or envelope['algorithm'] != 'AES-256-GCM+RSA-OAEP-SHA256':
            raise ValueError('invalid envelope')
        wrapped = base64.b64decode(envelope['wrapped_key'], validate=True)
        nonce = base64.b64decode(envelope['nonce'], validate=True)
        ciphertext = base64.b64decode(envelope['ciphertext'], validate=True)
        if (envelope['version'] != 1 or not 256 <= len(wrapped) <= 1024
                or len(nonce) != 12 or len(ciphertext) != 65552):
            raise ValueError('invalid envelope')
        print(json.dumps(envelope, separators=(',', ':')))
        return 0
    except Exception:
        # Never print exception values, docker stderr, runtime environment or rows.
        print('Runtime readiness collection failed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
