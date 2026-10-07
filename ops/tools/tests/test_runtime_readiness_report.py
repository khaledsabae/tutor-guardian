"""Offline privacy, read-only and encryption contracts; no production access."""
import base64
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'ops/tools/runtime_readiness_report.py'


def utility():
    assert SOURCE.is_file(), 'read-only runtime readiness utility missing'
    spec = importlib.util.spec_from_file_location('readiness', SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path):
    p = tmp_path / 'runtime.db'
    with sqlite3.connect(p) as c:
        c.executescript('''CREATE TABLE llm_calls(ts TEXT,provider TEXT,prompt_tokens INTEGER,completion_tokens INTEGER);
            CREATE TABLE push_tokens(device_id TEXT,token TEXT,build_number INTEGER,updated_at TEXT);
            CREATE TABLE api_tokens(device_id TEXT,token TEXT,created_at TEXT);
            CREATE TABLE device_aliases(device_id TEXT,canonical_device TEXT);
            CREATE TABLE device_fold_log(id INTEGER);''')
        c.executemany('INSERT INTO llm_calls VALUES(?,?,?,?)', [
            ('2026-10-07', 'deepseek', 5, 2), ('2026-10-07', 'deepseek_aux', None, 2),
            ('bad-stamp', 'azure_deepseek', 2, 1), ('2026-09-01', 'deepseek', 500, 20),
            ('2026-10-07', 'local', 900, 200)])
        c.executemany('INSERT INTO push_tokens VALUES(?,?,?,?)', [
            ('private-device-1', 'secret-token-1', 106, '2026-10-06'),
            ('private-device-2', 'secret-token-2', 105, '2026-10-06'),
            ('private-device-3', 'secret-token-3', None, '2026-10-06')])
        c.execute("INSERT INTO api_tokens VALUES('private-device-1','private-auth-token','2026-10-06')")
        c.execute("INSERT INTO device_aliases VALUES('private-twin','private-device-1')")
        c.execute('INSERT INTO device_fold_log VALUES(1)')
    return p


def test_missing_db_never_created(tmp_path):
    m = utility(); p = tmp_path / 'missing.db'
    assert m.database_report(p, '2026-10', '2026-10-07T00:00:00+00:00')['status'] == 'unavailable'
    assert not p.exists()


def test_readonly_aggregate_census_and_month_integrity(db):
    m = utility(); before = db.read_bytes()
    r = m.database_report(db, '2026-10', '2026-10-07T00:00:00+00:00')
    assert r['monthly_paid_usage']['rows'] == 3
    assert r['monthly_paid_usage']['invalid_usage_rows'] == 1
    assert r['monthly_paid_usage']['unknown_timestamp_rows'] == 1
    assert r['monthly_paid_usage']['known_tokens'] == 10
    assert r['build_census']['at_least_106'] == 1
    assert r['build_census']['below_106'] == 1
    assert r['build_census']['unknown_build'] == 1
    assert r['session_mints']['month_rows'] == 1
    assert r['session_mints']['devices_at_least_106'] == 1
    assert r['recovery']['folded_aliases'] == 1
    text = json.dumps(r)
    assert 'private-' not in text and 'secret-token' not in text
    assert db.read_bytes() == before
    assert not Path(str(db) + '.cloud-budget-anchor').exists()
    assert not Path(str(db) + '-journal').exists()


def test_absent_schema_is_unknown_not_zero(tmp_path):
    m = utility(); p = tmp_path / 'empty.db'
    with sqlite3.connect(p): pass
    r = m.database_report(p, '2026-10', '2026-10-07T00:00:00+00:00')
    for key in ('monthly_paid_usage', 'build_census', 'session_mints', 'recovery'):
        assert r[key] == {'status': 'unavailable'}


@pytest.mark.parametrize('url', ['https://user:password@host.example/v1?key=SECRET#secret',
                                 'https://host.example/a/SECRET?token=SECRET'])
def test_endpoint_never_retains_userinfo_query_fragment_or_arbitrary_path(url):
    out = utility().redacted_endpoint(url)
    assert 'SECRET' not in out and 'password' not in out and 'user' not in out
    assert out == 'https://host.example'


@pytest.mark.parametrize('url', ['bad-url', 'https://host:bad', 'file:///secret'])
def test_invalid_endpoint_is_unknown(url):
    assert utility().redacted_endpoint(url) == 'unavailable'


@pytest.fixture(scope='module')
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def test_hybrid_encryption_roundtrip_and_tamper(key):
    m = utility(); pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    envelope = json.loads(m.encrypt_report({'aggregate': 106}, pem))
    assert set(envelope) == {'version', 'algorithm', 'wrapped_key', 'nonce', 'ciphertext'}
    dec = lambda name: base64.b64decode(envelope[name])
    aes = key.decrypt(dec('wrapped_key'), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    assert json.loads(AESGCM(aes).decrypt(dec('nonce'), dec('ciphertext'), m.AAD)) == {'aggregate': 106}
    bad = bytearray(dec('ciphertext')); bad[0] ^= 1
    with pytest.raises(InvalidTag): AESGCM(aes).decrypt(dec('nonce'), bytes(bad), m.AAD)
    assert m.encrypt_report({'aggregate': 106}, pem) != m.encrypt_report({'aggregate': 106}, pem)


def test_invalid_recipient_before_collection(monkeypatch):
    m = utility(); calls = []
    monkeypatch.setattr(m, 'collect_report', lambda *a: calls.append(a))
    with pytest.raises(ValueError): m.container_report({'public_key': 'not-a-key', 'mounts': []})
    assert calls == []


def test_mounts_projection_drops_extra_fields():
    m = utility()
    r = m.project_mounts([{'Type':'volume','Name':'tg_sessions','Source':'/volume/data',
                          'Destination':'/app/ops','RW':True,'secret':'DO-NOT-INCLUDE'},
                         {'Type':'bind','Source':'/secret','Destination':'/app/backend/secrets','RW':False}])
    assert r == [{'type':'volume','name':'tg_sessions','source':'/volume/data','destination':'/app/ops','read_write':True}]


def test_host_failure_never_prints_runtime_stderr(monkeypatch, capsys):
    m = utility()
    monkeypatch.setenv('REPORT_PUBLIC_KEY_PEM', 'bad-key')
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1, stdout=b'private-device', stderr=b'API_KEY=SECRET'))
    assert m.main([]) == 2
    captured = capsys.readouterr()
    assert 'SECRET' not in captured.err + captured.out and 'private-device' not in captured.err + captured.out


def test_workflow_only_manual_trusted_main_and_encrypted_artifact():
    utility()
    p = ROOT / '.github/workflows/runtime-readiness.yml'
    assert p.exists()
    import yaml
    w = yaml.safe_load(p.read_text())
    trigger = w.get('on', w.get(True))
    assert set(trigger) == {'workflow_dispatch'}
    assert w['jobs']['diagnostic']['runs-on'] == ['self-hosted', 'production']
    assert "github.ref == 'refs/heads/main'" in w['jobs']['diagnostic']['if']
    assert "github.event_name == 'workflow_dispatch'" in w['jobs']['diagnostic']['if']
    assert w['jobs']['diagnostic']['needs'] == 'guard'
    assert 'expected_sha' in trigger['workflow_dispatch']['inputs']
    assert 'REPORT_PUBLIC_KEY_PEM' in p.read_text()
    assert 'refs/heads/main' in p.read_text() and 'workflow_sha' in p.read_text()
    assert not any('docker logs' in str(s) or 'docker restart' in str(s) for s in w['jobs']['diagnostic']['steps'])


def test_fixed_ciphertext_size_does_not_publish_count_length(key):
    m = utility(); pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    a = json.loads(m.encrypt_report({'count': 1}, pem))
    b = json.loads(m.encrypt_report({'count': 1000000}, pem))
    assert len(base64.b64decode(a['ciphertext'])) == len(base64.b64decode(b['ciphertext'])) == 65552


def test_weak_rsa_key_refused():
    m = utility(); k = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    pem = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    with pytest.raises(ValueError): m.encrypt_report({'count': 1}, pem)


def test_current_runtime_config_projection_and_fallback_model(db, monkeypatch):
    m = utility()
    from app.config import llm_config
    cfg = SimpleNamespace(primary_provider='deepseek', deepseek_base_url='https://user:secret@host.example/v1?key=secret',
        deepseek_model='configured-model', deepseek_model_fallback='refusal-model',
        deepseek_primary_monthly_token_cap=100, deepseek_fallback_monthly_token_cap=50,
        deepseek_fallback_enabled=True, cloud_tier_enabled=False,
        azure_endpoint='https://azure.example?secret=value', azure_model='azure-model', deepseek_api_key='MUST-NOT-APPEAR')
    monkeypatch.setattr(llm_config, 'LLM', cfg)
    monkeypatch.setenv('CONVERSATIONS_DB', str(db))
    monkeypatch.setenv('SESSION_MINT_ENFORCE', 'true')
    monkeypatch.setenv('UNRELATED_BUSINESS_SECRET', 'MUST-NOT-APPEAR')
    monkeypatch.setattr(m, 'database_report', lambda path,*args: {'path': str(path), 'status': 'unavailable'})
    r = m.collect_report([])
    assert r['cloud']['fallback']['model'] == 'configured-model'
    assert r['cloud']['refusal_model'] == 'refusal-model'
    assert r['session_mint_enforced'] is True
    assert 'secret' not in json.dumps(r) and 'MUST-NOT-APPEAR' not in json.dumps(r)
    assert set(r) == {'version','collected_at_utc','crypto_version','cloud','session_mint_enforced','mounts','telemetry','conversations'}


def test_live_wal_reads_latest_committed_counts_without_initializing_files(tmp_path):
    m = utility(); p = tmp_path / 'wal.db'
    with sqlite3.connect(p) as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('CREATE TABLE llm_calls(ts,provider,prompt_tokens,completion_tokens)')
        c.commit()
        c.execute("INSERT INTO llm_calls VALUES('2026-10-07','deepseek',5,2)")
        c.commit()
        before = p.read_bytes(); files = set(tmp_path.iterdir())
        r = m.database_report(p, '2026-10', '2026-10-07T00:00:00+00:00')
        assert r['monthly_paid_usage']['known_tokens'] == 7
        assert p.read_bytes() == before and set(tmp_path.iterdir()) == files


def test_host_rejects_plaintext_shaped_envelope(key, monkeypatch, capsys):
    m = utility()
    for name, value in {'GITHUB_EVENT_NAME':'workflow_dispatch', 'GITHUB_REF':'refs/heads/main',
                        'GITHUB_SHA':'a'*40, 'READINESS_WORKFLOW_SHA':'a'*40, 'READINESS_EXPECTED_SHA':'a'*40}.items():
        monkeypatch.setenv(name, value)
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    monkeypatch.setenv('REPORT_PUBLIC_KEY_PEM', pem)
    responses = iter([SimpleNamespace(stdout=b'[]'), SimpleNamespace(stdout=json.dumps({
        'version':1,'algorithm':'AES-256-GCM+RSA-OAEP-SHA256',
        'wrapped_key':'PRIVATE-BUSINESS','nonce':'PRIVATE-DEVICE','ciphertext':'SECRET-KEY'}).encode())])
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: next(responses))
    assert m.main([]) == 2
    assert 'PRIVATE' not in capsys.readouterr().out


def test_recovery_build_106_count_is_aggregate_only(db):
    r = utility().database_report(db, '2026-10', '2026-10-07T00:00:00+00:00')
    assert r['recovery']['families_at_least_106'] == 1


@pytest.mark.parametrize('change,accepted', [({},True),({'expected':'f'*40},False),
    ({'head':'f'*40},False),({'workflow':'f'*40},False),({'expected':'main'},False)])
def test_sha_guard_executes_before_admission(change, accepted):
    import subprocess
    import yaml
    w = yaml.safe_load((ROOT / '.github/workflows/runtime-readiness.yml').read_text())
    script = w['jobs']['guard']['steps'][0]['with']['script']
    sha = 'a'*40
    v = {'expected':sha,'head':sha,'workflow':sha}
    v.update(change)
    js = '''const input=JSON.parse(process.argv[1]);
    process.env.EXPECTED_SHA=input.expected; process.env.WORKFLOW_SHA=input.workflow;
    const context={repo:{owner:'test',repo:'test'},sha:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'};
    const github={rest:{git:{getRef:async()=>({data:{object:{sha:input.head}}})}}};
    let refused=false, admitted=false;
    const core={setFailed:()=>{refused=true},setOutput:()=>{admitted=true}};
    const run=new (Object.getPrototypeOf(async function(){}).constructor)('github','context','core',input.script);
    run(github,context,core).then(()=>process.stdout.write(JSON.stringify({refused,admitted}))).catch(()=>process.exit(2));'''
    v['script'] = script
    proc = subprocess.run(['node','-e',js,json.dumps(v)],capture_output=True,timeout=5,check=True)
    assert json.loads(proc.stdout) == {'refused':not accepted,'admitted':accepted}


def test_symlink_outside_mount_cannot_claim_persistence(tmp_path, monkeypatch):
    m = utility(); mounted = tmp_path / 'mount'; mounted.mkdir()
    target = tmp_path / 'outside.db'; target.touch()
    link = mounted / 'link.db'; link.symlink_to(target)
    monkeypatch.setenv('CONVERSATIONS_DB', str(link))
    monkeypatch.setattr(m, 'database_report', lambda path,*args: {'path': str(path), 'status':'unavailable'})
    r = m.collect_report([{'destination':str(mounted),'type':'volume','name':'fake','source':'fake','read_write':True}])
    assert r['conversations']['persistent_mount_observed'] is False


def test_host_requires_manual_main_context_before_docker(key, monkeypatch):
    m = utility(); calls = []
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    monkeypatch.setenv('REPORT_PUBLIC_KEY_PEM', pem)
    for name in ('GITHUB_EVENT_NAME','GITHUB_REF','GITHUB_SHA','GITHUB_WORKFLOW_SHA','READINESS_EXPECTED_SHA'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: calls.append(a) or SimpleNamespace(stdout=b'[]'))
    assert m.main([]) == 2
    assert calls == []


def test_host_valid_context_emits_only_valid_encrypted_envelope(key, monkeypatch, capsys):
    m = utility()
    for name, value in {'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/main',
                        'GITHUB_SHA':'a'*40,'READINESS_WORKFLOW_SHA':'a'*40,'READINESS_EXPECTED_SHA':'a'*40}.items():
        monkeypatch.setenv(name, value)
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setenv('REPORT_PUBLIC_KEY_PEM', pem.decode())
    envelope = m.encrypt_report({'count':106}, pem)
    responses = iter([SimpleNamespace(stdout=b'[]'),SimpleNamespace(stdout=envelope.encode())])
    monkeypatch.setattr(m.subprocess,'run',lambda *a, **k: next(responses))
    assert m.main([]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == json.loads(envelope) and captured.err == ''


def test_estimated_usage_is_counted_apart_from_measured_usage(tmp_path):
    """The gateway now flags counts the provider did not report
    (llm_calls.usage_estimated). A budget bootstrap must see them as such:
    estimated tokens are never folded into known_tokens."""
    m = utility(); p = tmp_path / 'estimated.db'
    with sqlite3.connect(p) as c:
        c.execute('CREATE TABLE llm_calls(ts TEXT,provider TEXT,prompt_tokens INTEGER,'
                  'completion_tokens INTEGER,usage_estimated INTEGER NOT NULL DEFAULT 0)')
        c.executemany('INSERT INTO llm_calls VALUES(?,?,?,?,?)', [
            ('2026-10-07', 'deepseek', 5, 2, 0), ('2026-10-07', 'deepseek', 300, 40, 1),
            ('2026-10-07', 'deepseek', None, None, 0), ('2026-10-07', 'gateway', 0, 0, 0)])
    r = m.database_report(p, '2026-10', '2026-10-07T00:00:00+00:00')['monthly_paid_usage']
    assert (r['rows'], r['invalid_usage_rows'], r['known_tokens']) == (3, 1, 7)
    assert (r['estimated_usage_rows'], r['estimated_tokens']) == (1, 340)


def test_a_store_without_the_flag_reports_zero_estimated(db):
    r = utility().database_report(db, '2026-10', '2026-10-07T00:00:00+00:00')['monthly_paid_usage']
    assert (r['estimated_usage_rows'], r['estimated_tokens'], r['known_tokens']) == (0, 0, 10)
