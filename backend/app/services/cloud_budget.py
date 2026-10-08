"""Durable per-wire-attempt admission; diagnostics never authorize paid traffic."""
from __future__ import annotations

import atexit
import contextlib
import fcntl
import hashlib
import json
import logging
import os
import queue
import sqlite3
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)
_MAX_INTEGER = (1 << 63) - 1
PAID_ALIASES = ('azure_deepseek', 'deepseek', 'deepseek_aux', 'deepseek_fallback')
# llm_calls.provider values that are never a request to any wallet: the
# gateway's all-failed marker row (telemetry from codex/batch-oct8).
NON_WALLET_PROVIDERS = ('gateway',)


class BudgetDenied(RuntimeError):
    """The paid budget is full, unknown, or its billing bound was violated."""

    def __init__(self, message: str):
        super().__init__(message)
        self.usage = (0, 0)  # denial itself never crossed the transport boundary


def _count(value) -> bool:
    return type(value) is int and 0 <= value <= _MAX_INTEGER


@dataclass(frozen=True)
class BillingProfile:
    """Documented input+generated context ceiling, not a billing prediction."""

    context_tokens: int
    max_output_tokens: int


# Verified 2026-10-07 and re-verified 2026-10-08 (URLs + SHA-256 of the
# fetched pages in docs/cloud-budget-reservations.md, "deepseek-chat"):
# api-docs.deepseek.com/quick_start/pricing and /api/create-chat-completion.
# 1M rounded up to 2**20; max_tokens 1..393216.
# Legacy aliases, Azure deployment names and compatible hosts are not verified.
# deepseek-chat in particular is NOT documented any more (its announced
# discontinuation date, 2026-07-24, has passed and the current pages do not
# name it); billing it under a profile is an explicit operator attestation via
# DEEPSEEK_BILLING_PROFILE_ALIASES, never a built-in default. Since 2026-10-08
# the app no longer SENDS it to DeepSeek: llm_config.resolve_deepseek_model
# rewrites it to deepseek-flash before the request (and before this profile
# lookup), so the alias setting is only needed for other hand-written names.
_BILLING_PROFILES = {
    ("https://api.deepseek.com:443", model): BillingProfile(1048576, 393216)
    for model in ("deepseek-flash", "deepseek-v4-pro")
}


@dataclass(frozen=True)
class TokenPrice:
    """US$ per 1M tokens at the documented PEAK rate (off-peak is half)."""

    input_cache_hit: Decimal
    input_cache_miss: Decimal
    output: Decimal


# api-docs.deepseek.com/quick_start/pricing/, fetched 2026-10-08 19:41 UTC
# (SHA-256 210f1022…63b2, docs/cloud-budget-reservations.md). Peak rates —
# the pessimistic ones. ops/tools/deploy_gate.py carries a stdlib copy; a test
# keeps them equal. A price change on that page means editing both.
DEEPSEEK_PRICES_USD_PER_M = {
    ("https://api.deepseek.com:443", "deepseek-flash"):
        TokenPrice(Decimal("0.006"), Decimal("0.30"), Decimal("1.20")),
    ("https://api.deepseek.com:443", "deepseek-v4-pro"):
        TokenPrice(Decimal("0.044"), Decimal("1.32"), Decimal("3.96")),
}


def _origin(endpoint: str) -> str:
    from urllib.parse import urlsplit

    parsed = urlsplit(endpoint)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.scheme}://{(parsed.hostname or '').lower()}:{port}"


def monthly_token_cap_for_usd(usd: Decimal, models, *, endpoint: str) -> int:
    """The largest monthly token cap that cannot bill more than `usd`.

    The ledger charges prompt + completion as ONE sum, so the cap must hold
    for every input/output split: input priced at the cache-miss rate, output
    at the output rate, both at peak. A sum is only bounded by its dearest
    per-token rate — max(cache miss, output) of the dearest model the wallet
    may be sent — so that rate prices every token. Raises ValueError when a
    model has no documented price (no cap can be derived for it).
    """
    if not isinstance(usd, Decimal) or not usd.is_finite() or usd <= 0:
        raise ValueError(f"monthly USD cap must be a positive amount, not {usd!r}")
    origin = _origin(endpoint)
    rates = []
    for model in models:
        price = DEEPSEEK_PRICES_USD_PER_M.get((origin, model))
        if price is None:
            raise ValueError(f"no documented price for {model!r} at {origin}")
        rates.append(max(price.input_cache_miss, price.output))
    if not rates:
        raise ValueError("no model to price")
    return int(usd * 1_000_000 // max(rates))


def _profile_for(origin: str, model: str, profile_aliases) -> BillingProfile | None:
    profile = _BILLING_PROFILES.get((origin, model))
    if profile is not None:
        if model in (profile_aliases or {}):
            # A documented model is never re-pointed by configuration.
            raise BudgetDenied("cloud budget alias cannot remap a documented model")
        return profile
    target = (profile_aliases or {}).get(model)
    if not isinstance(target, str) or target == model:
        return None
    # One hop, same origin, onto a verified profile only.
    return _BILLING_PROFILES.get((origin, target))


def upper_token_bound(messages: list[dict], max_output_tokens: int, *,
                      endpoint: str, model: str, profile_aliases=None) -> int:
    """Reserve the entire verified context, independent of input tokenization.

    The profile requires the actual max_tokens parameter on every wire attempt.
    Provider violations of its documented contract are outside this guarantee.
    `profile_aliases` ({undocumented name: documented name}) is the operator's
    explicit attestation that a name the provider still accepts is served and
    billed as the documented model; a settled usage above the bound still
    quarantines the wallet, so a wrong attestation stops spend rather than
    hiding it.
    """
    from urllib.parse import urlsplit

    if not _count(max_output_tokens) or max_output_tokens == 0:
        raise BudgetDenied("cloud budget requires a bounded positive max_tokens")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        origin = f"{parsed.scheme}://{(parsed.hostname or '').lower()}:{port}"
    except ValueError as exc:
        raise BudgetDenied("cloud budget invalid billing profile endpoint") from exc
    profile = _profile_for(origin, model, profile_aliases)
    if (profile is None or parsed.path.rstrip('/') not in ("", "/v1")
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise BudgetDenied("cloud budget unverified provider/model billing profile")
    if max_output_tokens > profile.max_output_tokens:
        raise BudgetDenied("cloud budget output limit exceeds verified profile")
    return profile.context_tokens


# Chat-template/special tokens a provider adds around the messages. DeepSeek's
# template adds a handful per message; 4096 is deliberately generous.
UNKNOWN_USAGE_FRAMING_TOKENS = 4096


def unknown_usage_bounds(messages: list[dict], max_output_tokens: int) -> tuple[int, int]:
    """(input, output) charged for an attempt whose usage never arrived.

    Input: every UTF-8 byte of the serialized messages (keys, roles and JSON
    escapes included) plus UNKNOWN_USAGE_FRAMING_TOKENS. A byte-level
    tokenizer never emits more text tokens than bytes, so this is >= the
    telemetry's bytes/3 estimate by construction. Output: the max_tokens the
    request carried (the provider's documented ceiling on generated tokens).
    Not a proof against hidden provider-side input — see the cap doc.
    """
    payload = json.dumps(messages, ensure_ascii=False).encode("utf-8", "replace")
    return len(payload) + UNKNOWN_USAGE_FRAMING_TOKENS, max_output_tokens


@dataclass(frozen=True)
class Reservation:
    id: str
    wallet: str
    month: str
    bound: int
    # Charged instead of `bound` when the provider reports no usage; None =
    # retain the full reservation (process death, legacy callers).
    input_bound: int | None = None
    output_bound: int | None = None


# How long a ledger transaction waits for the cross-process lock / SQLite
# write lock. A reservation sits on the answer's critical path; a settlement
# is never a denial (losing one leaves an orphan holding its full bound), so
# it waits far longer and retries until this deadline.
RESERVE_TIMEOUT_S = 5.0
SETTLE_TIMEOUT_S = 120.0
ADMIN_TIMEOUT_S = 30.0

# Tables whose rows the continuity witness covers, and the running totals a
# trigger keeps for each (column in cloud_budget_witness -> SQL of the row).
_WITNESSED = {
    'cloud_budget_attempts': (('attempts_n', '1'), ('attempts_charged', 'charged_tokens'),
                              ('attempts_settled', 'settled')),
    'cloud_budget_carry': (('carry_n', '1'), ('carry_charged', 'charged_tokens')),
    'cloud_budget_months': (('months_n', '1'), ('months_opening', 'opening_tokens'),
                            ('months_blocked', 'blocked')),
    'cloud_budget_activation': (('activation_n', '1'),),
    'cloud_budget_identity': (('identity_n', '1'),),
    'cloud_budget_attempts_archive': (('archive_n', '1'), ('archive_charged', 'charged_tokens')),
    'cloud_budget_attempt_meta': (('meta_n', '1'),),
    'cloud_budget_audit': (('audit_n', '1'),),
}
_WITNESS_COLUMNS = tuple(col for spec in _WITNESSED.values() for col, _ in spec)
_LEDGER_OBJECTS = (*_WITNESSED, 'cloud_budget_witness')


def record_call_reservations(conn, call_id: int, reservation_ids) -> None:
    """Map one llm_calls row to the ledger attempts behind it (same txn).

    Outside the witnessed ledger on purpose: telemetry writes must not take
    the ledger lock. A lost or missing mapping can only refuse a rollover.
    """
    ids = [r for r in dict.fromkeys(reservation_ids or ()) if isinstance(r, str) and r]
    if not ids:
        return
    conn.execute('CREATE TABLE IF NOT EXISTS llm_call_reservations (call_id INTEGER NOT NULL, '
                 'reservation_id TEXT NOT NULL, PRIMARY KEY(call_id, reservation_id))')
    conn.executemany('INSERT OR IGNORE INTO llm_call_reservations VALUES(?,?)',
                     [(call_id, r) for r in ids])


class LedgerBusy(BudgetDenied):
    """The ledger stayed locked past this transaction's timeout."""


# Threads of one process queue on a lock that wakes the next waiter at
# release; only cross-process contention falls back to polling the flock.
_PROCESS_LOCKS: dict[str, threading.Lock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()
# flock locks belong to an open-file description shared by forked processes.
# Keep raw descriptors so the child can close its copies without taking a
# potentially inherited Python file-object lock.
_TRANSACTION_FDS: set[int] = set()
_TRANSACTION_FDS_GUARD = threading.Lock()


def _open_transaction_lock(path: Path) -> int:
    with _TRANSACTION_FDS_GUARD:
        fd = os.open(str(path) + '.lock', os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o666)
        _TRANSACTION_FDS.add(fd)
        return fd


def _close_transaction_lock(fd: int) -> None:
    with _TRANSACTION_FDS_GUARD:
        _TRANSACTION_FDS.remove(fd)
        os.close(fd)


def _process_lock(path: Path) -> threading.Lock:
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(str(path), threading.Lock())


class CloudBudget:
    def __init__(self, path: Path, *, clock: Callable | None = None, anchor_path=None):
        try:
            self.path = Path(path).resolve()
            # Default: next to the DB. Elsewhere (another volume) a restore
            # of one volume alone no longer matches the other.
            self.anchor_path = (Path(anchor_path).resolve() if anchor_path
                                else Path(str(self.path) + '.cloud-budget-anchor'))
        except (OSError, ValueError, TypeError) as exc:
            raise BudgetDenied('cloud budget DB identity/path unknown') from exc
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # ── continuity witness: O(1) per transaction ──────────────────────────
    # Triggers bump a sequence number and keep running totals on every
    # INSERT/UPDATE/DELETE of a ledger row — including edits made outside
    # this code. The anchor file mirrors (sequence, totals, schema hash) at
    # each commit, so a restored snapshot, a deleted or edited row, or a
    # dropped trigger/table no longer matches. A forged witness row is caught
    # by the full recount (_recount) at every monthly rollover.
    @staticmethod
    def _schema_hash(conn) -> str:
        marks = ','.join('?' for _ in _LEDGER_OBJECTS)
        rows = conn.execute(
            f"SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name IN ({marks}) "
            f"OR tbl_name IN ({marks}) ORDER BY type,name", (*_LEDGER_OBJECTS, *_LEDGER_OBJECTS)).fetchall()
        return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

    @staticmethod
    def _witness(conn) -> list:
        try:
            row = conn.execute(f"SELECT seq,{','.join(_WITNESS_COLUMNS)} FROM cloud_budget_witness "
                               "WHERE id=1").fetchone()
        except sqlite3.OperationalError as exc:
            raise BudgetDenied('cloud budget lost schema; reconciliation required') from exc
        if row is None:
            raise BudgetDenied('cloud budget lost witness; reconciliation required')
        return list(row)

    @staticmethod
    def _recount(conn) -> list:
        """The witness totals recomputed from every row — O(history)."""
        totals = []
        for table, spec in _WITNESSED.items():
            exprs = ','.join(f'COALESCE(SUM({expr}),0)' for _, expr in spec)
            totals.extend(conn.execute(f'SELECT {exprs} FROM {table}').fetchone())
        return totals

    def _write_anchor(self, conn):
        identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone()
        if not identity:
            raise BudgetDenied('cloud budget uninitialized DB identity')
        data = json.dumps({'db_identity': identity[0], 'witness': self._witness(conn),
                           'schema': self._schema_hash(conn)})
        fd, name = tempfile.mkstemp(prefix=self.anchor_path.name + '.', dir=self.anchor_path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.anchor_path)
            directory = os.open(self.anchor_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @contextlib.contextmanager
    def _transaction(self, *, bootstrap=False, timeout: float | None = None):
        conn = None
        lock = None
        deadline = time.monotonic() + (RESERVE_TIMEOUT_S if timeout is None else timeout)
        local = _process_lock(self.anchor_path)
        wait = deadline - time.monotonic()
        if not (local.acquire(timeout=wait) if wait > 0 else local.acquire(blocking=False)):
            raise LedgerBusy('cloud budget continuity witness busy')
        try:
            if not self.path.is_file():
                raise BudgetDenied('cloud budget cutover unknown: existing history DB required')
            if not bootstrap and not self.anchor_path.is_file():
                raise BudgetDenied('cloud budget cutover uninitialized or continuity anchor lost')
            # Serialize DB commit + separate durable witness across processes.
            # A crash between them denies further traffic rather than resetting.
            lock = _open_transaction_lock(self.anchor_path)
            pause = 0.001
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise LedgerBusy('cloud budget continuity witness busy')
                    time.sleep(min(pause, max(0.0, deadline - time.monotonic())))
                    pause = min(pause * 2, 0.02)
            remaining = max(0.05, deadline - time.monotonic())
            identity_stat = self.path.stat()
            conn = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=remaining)
            conn.execute(f"PRAGMA busy_timeout = {int(remaining * 1000)}")
            conn.execute('PRAGMA synchronous = FULL')
            conn.execute("BEGIN IMMEDIATE")
            # Missing telemetry is unknown history, even on explicit bootstrap.
            conn.execute('SELECT ts,provider,prompt_tokens,completion_tokens FROM llm_calls LIMIT 0')
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if self.anchor_path.exists():
                anchor = json.loads(self.anchor_path.read_text())
                identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone() \
                    if 'cloud_budget_identity' in tables else None
                if (not identity or anchor.get('db_identity') != identity[0]
                        or 'cloud_budget_witness' not in tables
                        or anchor.get('witness') != self._witness(conn)
                        or anchor.get('schema') != self._schema_hash(conn)):
                    raise BudgetDenied('cloud budget continuity/restore identity mismatch; reconcile offline')
            elif not bootstrap or 'cloud_budget_activation' in tables or 'cloud_budget_identity' in tables:
                raise BudgetDenied('cloud budget continuity anchor lost; reconciliation required')
            else:
                # Adopt an intact pre-activation ledger; never repair partial loss.
                legacy = {'cloud_budget_months', 'cloud_budget_attempts', 'cloud_budget_carry'} & tables
                if legacy and legacy != {'cloud_budget_months', 'cloud_budget_attempts', 'cloud_budget_carry'}:
                    raise BudgetDenied('cloud budget lost legacy schema; reconciliation required')
                self._create_schema(conn)
            yield conn
            current_stat = self.path.stat()
            if (identity_stat.st_dev, identity_stat.st_ino) != (current_stat.st_dev, current_stat.st_ino):
                raise BudgetDenied('cloud budget DB identity replaced during accounting')
            conn.commit()
            self._write_anchor(conn)
        except sqlite3.OperationalError as exc:
            if 'locked' in str(exc) or 'busy' in str(exc):
                raise LedgerBusy('cloud budget ledger busy') from exc
            raise BudgetDenied("cloud budget accounting unknown or unavailable") from exc
        except (sqlite3.Error, OSError, ValueError, TypeError, AttributeError) as exc:
            raise BudgetDenied("cloud budget accounting unknown or unavailable") from exc
        finally:
            if conn is not None:
                conn.close()  # rolls back on exceptions; never leaves a writer open
            if lock is not None:
                _close_transaction_lock(lock)
            local.release()

    @staticmethod
    def _create_schema(conn):
        conn.execute("""CREATE TABLE IF NOT EXISTS cloud_budget_months (
            wallet TEXT NOT NULL, month TEXT NOT NULL,
            opening_tokens INTEGER NOT NULL, blocked INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(wallet, month))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS cloud_budget_attempts (
            id TEXT PRIMARY KEY, wallet TEXT NOT NULL, month TEXT NOT NULL,
            bound INTEGER NOT NULL, charged_tokens INTEGER NOT NULL,
            settled INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("CREATE INDEX IF NOT EXISTS cloud_budget_wallet_month "
                     "ON cloud_budget_attempts(wallet,month)")
        conn.execute("CREATE INDEX IF NOT EXISTS cloud_budget_unsettled "
                     "ON cloud_budget_attempts(wallet,month) WHERE settled=0")
        conn.execute("""CREATE TABLE IF NOT EXISTS cloud_budget_carry (
            wallet TEXT NOT NULL, month TEXT NOT NULL, attempt_id TEXT NOT NULL,
            charged_tokens INTEGER NOT NULL,
            PRIMARY KEY(wallet,month,attempt_id))""")
        conn.execute('CREATE TABLE cloud_budget_activation ('
                     'wallet TEXT NOT NULL, month TEXT NOT NULL, receipt TEXT NOT NULL, '
                     'PRIMARY KEY(wallet,month))')
        conn.execute('CREATE TABLE cloud_budget_identity ('
                     'id INTEGER PRIMARY KEY CHECK(id=1), db_identity TEXT NOT NULL)')
        conn.execute('CREATE TABLE cloud_budget_attempts_archive ('
                     'id TEXT PRIMARY KEY, wallet TEXT NOT NULL, month TEXT NOT NULL, '
                     'bound INTEGER NOT NULL, charged_tokens INTEGER NOT NULL, '
                     'settled INTEGER NOT NULL, archived_in TEXT NOT NULL)')
        conn.execute('CREATE TABLE cloud_budget_attempt_meta ('
                     'attempt_id TEXT PRIMARY KEY, reserved_at TEXT NOT NULL, unknown_charge INTEGER)')
        conn.execute('CREATE TABLE cloud_budget_audit ('
                     'id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, action TEXT NOT NULL, '
                     'attempt_id TEXT, wallet TEXT, month TEXT, old_charge INTEGER, new_charge INTEGER, '
                     'policy TEXT, evidence TEXT NOT NULL)')
        columns = ','.join(f'{col} INTEGER NOT NULL DEFAULT 0' for col in _WITNESS_COLUMNS)
        conn.execute(f'CREATE TABLE cloud_budget_witness (id INTEGER PRIMARY KEY CHECK(id=1), '
                     f'seq INTEGER NOT NULL DEFAULT 0, {columns})')
        # Adopted pre-activation rows are counted once, here.
        totals = CloudBudget._recount(conn)
        conn.execute(f"INSERT INTO cloud_budget_witness(id,seq,{','.join(_WITNESS_COLUMNS)}) "
                     f"VALUES(1,0,{','.join('?' for _ in totals)})", totals)
        for table, spec in _WITNESSED.items():
            for event, sign_old, sign_new in (('INSERT', None, '+'), ('DELETE', '-', None),
                                              ('UPDATE', '-', '+')):
                sets = ['seq=seq+1']
                for col, expr in spec:
                    term = col
                    if sign_old:
                        term += f"-({expr.replace('charged_tokens', 'OLD.charged_tokens').replace('opening_tokens', 'OLD.opening_tokens').replace('settled', 'OLD.settled').replace('blocked', 'OLD.blocked')})"
                    if sign_new:
                        term += f"+({expr.replace('charged_tokens', 'NEW.charged_tokens').replace('opening_tokens', 'NEW.opening_tokens').replace('settled', 'NEW.settled').replace('blocked', 'NEW.blocked')})"
                    sets.append(f'{col}={term}')
                conn.execute(f'CREATE TRIGGER {table}_witness_{event.lower()} AFTER {event} ON {table} '
                             f'BEGIN UPDATE cloud_budget_witness SET {", ".join(sets)} WHERE id=1; END')

    def bootstrap(self, receipt: dict) -> None:
        """Explicit operator-attested cutover, never evidence inferred from emptiness.

        opening_tokens covers all actual monthly charges through the cutoff,
        including external/aliased consumption. Replaying the identical receipt
        is a no-op; changed evidence requires offline reconciliation, not reseed.
        """
        try:
            now = self.clock()
            cutoff = datetime.fromisoformat(receipt['reconciled_through'])
            aliases = receipt['legacy_aliases']
            if (now.tzinfo is None or cutoff.tzinfo is None or cutoff > now
                    or cutoff.astimezone(timezone.utc).strftime('%Y-%m') != receipt['month']
                    or receipt['month'] != now.astimezone(timezone.utc).strftime('%Y-%m')
                    or not _count(receipt['opening_tokens'])
                    or receipt['unreserved_writers_drained'] is not True
                    or not isinstance(aliases, list) or not all(isinstance(a, str) and a for a in aliases)
                    or not set(PAID_ALIASES).issubset(aliases)
                    or any(not isinstance(receipt[key], str) or not receipt[key].strip()
                           for key in ('db_identity', 'wallet', 'evidence_reference'))):
                raise BudgetDenied('cloud budget cutover evidence incomplete or unknown')
            covered = receipt.get('unknown_usage_rows_covered')
            if covered is not None and (
                    not isinstance(covered, list) or not all(type(r) is int and r > 0 for r in covered)
                    or len(set(covered)) != len(covered)):
                raise BudgetDenied('cloud budget unknown-usage coverage malformed')
            receipt = {key: receipt[key] for key in ('db_identity', 'wallet', 'month', 'opening_tokens',
                       'reconciled_through', 'legacy_aliases', 'evidence_reference', 'unreserved_writers_drained')}
            receipt['legacy_aliases'] = sorted(set(aliases))
            if covered is not None:
                # Part of the attested receipt: a changed list is a reseed.
                receipt['unknown_usage_rows_covered'] = sorted(covered)
            encoded = json.dumps(receipt, sort_keys=True, separators=(',', ':'))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise BudgetDenied('cloud budget cutover evidence unknown') from exc
        with self._transaction(bootstrap=True, timeout=ADMIN_TIMEOUT_S) as conn:
            identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone()
            if identity and identity[0] != receipt['db_identity']:
                raise BudgetDenied('cloud budget cutover DB identity mismatch')
            wallet, month = receipt['wallet'], receipt['month']
            existing = conn.execute('SELECT receipt FROM cloud_budget_activation WHERE wallet=? AND month=?',
                                    (wallet, month)).fetchone()
            if existing:
                if existing[0] != encoded:
                    raise BudgetDenied('cloud budget cutover reseed forbidden; reconcile offline')
                return
            historical = self._opening(conn, month, tuple(receipt['legacy_aliases']), cutoff=cutoff,
                                       covered=frozenset(receipt.get('unknown_usage_rows_covered', ())))
            if receipt['opening_tokens'] < historical:
                raise BudgetDenied('cloud budget opening below known historical spend')
            conn.execute('INSERT OR IGNORE INTO cloud_budget_identity VALUES(1,?)', (receipt['db_identity'],))
            conn.execute('INSERT INTO cloud_budget_activation VALUES(?,?,?)', (wallet, month, encoded))
            conn.execute('INSERT INTO cloud_budget_months VALUES(?,?,?,0) '
                         'ON CONFLICT(wallet,month) DO UPDATE SET '
                         'opening_tokens=MAX(opening_tokens,excluded.opening_tokens)',
                         (wallet, month, receipt['opening_tokens']))

    def _opening(self, conn, month: str, aliases: tuple[str, ...], *, cutoff=None,
                 covered: frozenset = frozenset()) -> int:
        """Known historical spend: the floor an attested opening must reach.

        Rows flagged usage_estimated=1 carry numbers and count at face value
        (bytes/3 over-reads Arabic, so for the floor that is the safe side).
        A row with NULL counts is unknown spend: it blocks activation unless
        the receipt lists exactly those rows as covered by the provider's
        billing export behind opening_tokens. Gateway marker rows are never
        requests and never spend.
        """
        aliases = tuple(a for a in aliases if a not in NON_WALLET_PROVIDERS)
        if not aliases or not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='llm_calls'"
        ).fetchone():
            raise BudgetDenied('cloud budget opening billing unknown: missing history')
        rows = self.unknown_and_known_rows(conn, month, aliases)
        total = 0
        unknown = set()
        for rowid, ts, prompt, completion in rows:
            known = _count(prompt) and _count(completion)
            if not ts or (not known and rowid not in covered):
                raise BudgetDenied("cloud budget opening billing unknown")
            if not known:
                unknown.add(rowid)
            try:
                stamp = datetime.fromisoformat(ts)
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)  # SQLite datetime('now') is UTC
                if cutoff is not None and stamp > cutoff:
                    raise BudgetDenied('cloud budget reconciliation cutoff precedes historical spend')
            except (ValueError, TypeError) as exc:
                raise BudgetDenied('cloud budget historical timestamp unknown') from exc
            if known:
                total += prompt + completion
            if total > _MAX_INTEGER:
                raise BudgetDenied("cloud budget opening balance overflow")
        if unknown != set(covered):
            raise BudgetDenied('cloud budget unknown-usage coverage does not match history')
        return total

    def _auto_rollover(self, conn, wallet: str, month: str) -> str | None:
        """Open `month` from the previous month's ledger, or say why not.

        Runs inside a continuity-verified transaction (same anchor identity
        and ledger digest), so a restored, replaced or edited ledger never
        gets here. Rolls over only if the previous month was activated for
        this wallet on this DB identity, the wallet is not quarantined, every
        reservation up to the previous month is settled, and telemetry shows
        no spend the ledger did not reserve: no unknown-usage paid row and no
        more paid tokens than the ledger charged — for the previous month
        after its attested cutoff, and for this month so far. The new month
        then opens at what the ledger measured: opening 0, plus the late
        settlements already carried into it. Returns None when rolled over.
        """
        if self._recount(conn) != self._witness(conn)[1:]:
            return 'ledger rows disagree with the continuity witness (edited or forged)'
        year, mon = (int(part) for part in month.split('-'))
        prev = f'{year - 1}-12' if mon == 1 else f'{year}-{mon - 1:02d}'
        month_start = datetime(year, mon, 1, tzinfo=timezone.utc)
        row = conn.execute('SELECT receipt FROM cloud_budget_activation WHERE wallet=? AND month=?',
                           (wallet, prev)).fetchone()
        if not row:
            return f'no activation for the previous month {prev}'
        previous = json.loads(row[0])
        identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone()
        if not identity or identity[0] != previous.get('db_identity'):
            return 'DB identity differs from the previous receipt'
        if previous.get('unreserved_writers_drained') is not True:
            return 'previous receipt does not attest drained writers'
        if conn.execute('SELECT 1 FROM cloud_budget_months WHERE wallet=? AND blocked=1', (wallet,)).fetchone():
            return 'wallet quarantined'
        if not conn.execute('SELECT 1 FROM cloud_budget_months WHERE wallet=? AND month=?',
                            (wallet, prev)).fetchone():
            return f'opening of {prev} lost'
        if conn.execute('SELECT 1 FROM cloud_budget_attempts WHERE wallet=? AND month<=? AND settled=0',
                        (wallet, prev)).fetchone():
            return f'unsettled reservations up to {prev}'
        aliases = tuple(previous['legacy_aliases'])
        cutoff = datetime.fromisoformat(previous['reconciled_through'])
        # Every paid row after the attested cutoff must name the settled
        # ledger attempts behind it (llm_call_reservations), each attempt
        # claimed once, and report no more tokens than they charged. A row
        # without a reservation is spend the cap never admitted. Matching by
        # id, not by month, also places a row logged just after midnight.
        has_map = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                               "AND name='llm_call_reservations'").fetchone()
        claimed: dict[str, int] = {}
        for period, after in ((prev, cutoff), (month, month_start)):
            for rowid, ts, prompt, completion in self.unknown_and_known_rows(conn, period, aliases):
                try:
                    stamp = datetime.fromisoformat(ts)
                except (TypeError, ValueError):
                    return 'paid telemetry row without a timestamp'
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                if stamp <= after:
                    continue  # covered by the attested opening
                if not (_count(prompt) and _count(completion)):
                    return f'paid telemetry row {rowid} with unknown usage in {period}'
                tokens = prompt + completion
                if tokens == 0:
                    continue  # refused / denied before any request
                ids = [r[0] for r in conn.execute('SELECT reservation_id FROM llm_call_reservations '
                                                  'WHERE call_id=?', (rowid,))] if has_map else []
                if not ids:
                    return (f'paid telemetry row {rowid} ({tokens} tokens at {ts}) maps to no reservation: '
                            'an unreserved writer spent from this wallet')
                charged = 0
                for rid in ids:
                    if rid in claimed:
                        return f'reservation {rid} is claimed by telemetry rows {claimed[rid]} and {rowid}'
                    claimed[rid] = rowid
                    hit = conn.execute(
                        'SELECT charged_tokens,settled FROM cloud_budget_attempts WHERE id=? AND wallet=? '
                        'UNION ALL SELECT charged_tokens,settled FROM cloud_budget_attempts_archive '
                        'WHERE id=? AND wallet=?', (rid, wallet, rid, wallet)).fetchone()
                    if hit is None:
                        return f'telemetry row {rowid} names reservation {rid}, unknown to this wallet'
                    if not hit[1]:
                        return f'telemetry row {rowid} names unsettled reservation {rid}'
                    charged += hit[0]
                if tokens > charged:
                    return (f'telemetry row {rowid} reports {tokens} tokens, above the {charged} '
                            'its reservations charged')
        receipt = {'db_identity': identity[0], 'wallet': wallet, 'month': month, 'opening_tokens': 0,
                   'reconciled_through': month_start.isoformat(), 'legacy_aliases': sorted(set(aliases)),
                   'evidence_reference': f'auto-rollover from {prev}: continuous ledger, '
                                         'telemetry within reserved charges',
                   'unreserved_writers_drained': True, 'rollover_from': prev}
        conn.execute('INSERT INTO cloud_budget_activation VALUES(?,?,?)',
                     (wallet, month, json.dumps(receipt, sort_keys=True, separators=(',', ':'))))
        conn.execute('INSERT INTO cloud_budget_months VALUES(?,?,0,0)', (wallet, month))
        # Keep the hot tables to two months: settled attempts and carries of
        # earlier months move to the archive (still witnessed, never re-read
        # on the reservation path).
        conn.execute('INSERT INTO cloud_budget_attempts_archive '
                     'SELECT id,wallet,month,bound,charged_tokens,settled,? FROM cloud_budget_attempts '
                     'WHERE wallet=? AND month<? AND settled=1', (month, wallet, prev))
        conn.execute('DELETE FROM cloud_budget_attempts WHERE wallet=? AND month<? AND settled=1',
                     (wallet, prev))
        conn.execute('DELETE FROM cloud_budget_carry WHERE wallet=? AND month<?', (wallet, prev))
        conn.execute('DELETE FROM cloud_budget_attempt_meta WHERE attempt_id NOT IN '
                     '(SELECT id FROM cloud_budget_attempts)')
        logger.info('cloud budget rolled %s over from %s to %s', wallet, prev, month)
        return None

    @staticmethod
    def unknown_and_known_rows(conn, month: str, aliases: tuple[str, ...]):
        aliases = tuple(a for a in aliases if a not in NON_WALLET_PROVIDERS)
        marks = ",".join("?" for _ in aliases)
        return conn.execute(
            f"SELECT rowid,ts,prompt_tokens,completion_tokens FROM llm_calls WHERE provider IN ({marks}) "
            "AND (strftime('%Y-%m',ts)=? OR strftime('%Y-%m',ts) IS NULL) ORDER BY rowid",
            (*aliases, month),
        ).fetchall()

    def list_unknown_usage_rows(self, month: str, aliases: tuple[str, ...] = PAID_ALIASES) -> list[dict]:
        """Read-only: the paid rows of `month` whose usage is unknown (NULL)."""
        conn = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        try:
            return [{'id': rowid, 'ts': ts, 'prompt_tokens': p, 'completion_tokens': c}
                    for rowid, ts, p, c in self.unknown_and_known_rows(conn, month, aliases)
                    if not (_count(p) and _count(c))]
        finally:
            conn.close()

    def reserve(self, wallet: str, cap: int, bound: int, *,
                legacy_aliases: tuple[str, ...], unknown_usage_bounds=None) -> Reservation:
        if not _count(cap) or cap == 0 or not _count(bound) or bound == 0 or not wallet:
            raise BudgetDenied("cloud budget invalid cap or reservation")
        if unknown_usage_bounds is not None and (
                not isinstance(unknown_usage_bounds, (tuple, list)) or len(unknown_usage_bounds) != 2
                or not all(_count(v) and v > 0 for v in unknown_usage_bounds)):
            raise BudgetDenied("cloud budget invalid unknown-usage bounds")
        with self._transaction(timeout=RESERVE_TIMEOUT_S) as conn:
            now = self.clock()
            if now.tzinfo is None:
                raise BudgetDenied("cloud budget requires a UTC accounting clock")
            month = now.astimezone(timezone.utc).strftime("%Y-%m")
            activation = conn.execute('SELECT receipt FROM cloud_budget_activation WHERE wallet=? AND month=?',
                                      (wallet, month)).fetchone()
            if not activation:
                refusal = self._auto_rollover(conn, wallet, month)
                if refusal is not None:
                    logger.warning("cloud budget auto-rollover refused for %s %s: %s; "
                                   "explicit bootstrap required", wallet, month, refusal)
                    raise BudgetDenied('cloud budget cutover uninitialized wallet/month; explicit bootstrap required')
                activation = conn.execute('SELECT receipt FROM cloud_budget_activation WHERE wallet=? AND month=?',
                                          (wallet, month)).fetchone()
            if not set(legacy_aliases).issubset(json.loads(activation[0])['legacy_aliases']):
                raise BudgetDenied('cloud budget cutover missing paid alias reconciliation')
            ticket = Reservation(uuid.uuid4().hex, wallet, month, bound,
                                 *(unknown_usage_bounds or (None, None)))
            if conn.execute("SELECT 1 FROM cloud_budget_months WHERE wallet=? AND blocked=1",
                            (wallet,)).fetchone():
                raise BudgetDenied("cloud budget wallet quarantined; billing bounds require review")
            row = conn.execute("SELECT opening_tokens,blocked FROM cloud_budget_months "
                               "WHERE wallet=? AND month=?", (wallet, month)).fetchone()
            if row is None:
                raise BudgetDenied('cloud budget cutover opening lost; reconciliation required')
            else:
                opening, blocked = row
                if blocked or not _count(opening):
                    raise BudgetDenied("cloud budget wallet quarantined or unknown")
            used = conn.execute("SELECT COALESCE(SUM(charged_tokens),0) FROM cloud_budget_attempts "
                                "WHERE wallet=? AND month=?", (wallet, month)).fetchone()[0]
            # Old unresolved attempts may still bill this month. Neither process
            # death nor calendar rollover proves they were free or finished.
            conn.execute("INSERT OR IGNORE INTO cloud_budget_carry "
                         "SELECT wallet,?,id,charged_tokens FROM cloud_budget_attempts "
                         "WHERE wallet=? AND month<? AND settled=0", (month, wallet, month))
            carried = conn.execute("SELECT COALESCE(SUM(charged_tokens),0) FROM cloud_budget_carry "
                                   "WHERE wallet=? AND month=?", (wallet, month)).fetchone()[0]
            if not _count(used) or not _count(carried) or opening + used + carried + bound > cap:
                raise BudgetDenied("cloud budget monthly reservation would exceed cap")
            conn.execute("INSERT INTO cloud_budget_attempts VALUES(?,?,?,?,?,0)",
                         (ticket.id, wallet, month, bound, bound))
            conn.execute("INSERT INTO cloud_budget_attempt_meta VALUES(?,?,?)",
                         (ticket.id, now.astimezone(timezone.utc).isoformat(),
                          sum(unknown_usage_bounds) if unknown_usage_bounds else None))
        return ticket

    def settle(self, ticket: Reservation, prompt_tokens, completion_tokens) -> None:
        """Charge reported usage; otherwise the request's own upper bound.

        A missing count is replaced by the ticket's input/output bound (see
        unknown_usage_bounds), never above the reservation and never a
        quarantine trigger. A ticket without bounds retains the full
        reservation. Never free on error: an accounting-write failure retains
        the committed original charge; a duplicate settlement cannot alter a
        previously settled charge.
        """
        actual = self._actual(ticket, prompt_tokens, completion_tokens)
        deadline = time.monotonic() + SETTLE_TIMEOUT_S
        while True:
            try:
                self._settle_once(ticket, actual, max(0.05, deadline - time.monotonic()))
                return
            except LedgerBusy as exc:
                if time.monotonic() < deadline:
                    continue  # a settlement waits; it is never a denial
                logger.error("cloud budget settlement still busy after %.0fs; attempt %s stays an "
                             "orphan holding its bound (settle it with --settle-orphans): %s",
                             SETTLE_TIMEOUT_S, ticket.id, exc)
                return
            except BudgetDenied as exc:
                logger.warning("cloud budget settlement retained original charge: %s", exc)
                return

    @staticmethod
    def _actual(ticket: Reservation, prompt_tokens, completion_tokens) -> int:
        if _count(prompt_tokens) and _count(completion_tokens):
            return prompt_tokens + completion_tokens
        if ticket.input_bound is not None and ticket.output_bound is not None:
            return min(ticket.bound,
                       (prompt_tokens if _count(prompt_tokens) else ticket.input_bound)
                       + (completion_tokens if _count(completion_tokens) else ticket.output_bound))
        return ticket.bound

    def try_settle_now(self, ticket: Reservation, prompt_tokens, completion_tokens) -> bool:
        """Settle only if the ledger is free right now; never wait for it.

        False = busy (hand it to the background settler). True = settled, or
        refused for a non-transient reason (logged; the charge is retained).
        """
        try:
            self._settle_once(ticket, self._actual(ticket, prompt_tokens, completion_tokens), 0.0)
        except LedgerBusy:
            return False
        except BudgetDenied as exc:
            logger.warning("cloud budget settlement retained original charge: %s", exc)
        return True

    def status(self) -> dict:
        """Read-only activation state (mode=ro, no lock, nothing created)."""
        result = {'db_present': self.path.is_file(), 'anchor_present': self.anchor_path.is_file(),
                  'activated': False, 'continuity': None, 'wallets': {}, 'unsettled_attempts': None}
        if not result['db_present']:
            return result
        conn = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=0.2)
        try:
            conn.execute('PRAGMA query_only=ON')
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'cloud_budget_activation' not in tables:
                return result
            month = self.clock().astimezone(timezone.utc).strftime('%Y-%m')
            wallets: dict = {}
            for wallet, activated in conn.execute('SELECT wallet, month FROM cloud_budget_activation '
                                                  'ORDER BY wallet, month'):
                entry = wallets.setdefault(wallet, {'activated_months': [], 'current_month_activated': False,
                                                    'quarantined': False})
                entry['activated_months'].append(activated)
                entry['current_month_activated'] |= activated == month
            for (wallet,) in conn.execute('SELECT DISTINCT wallet FROM cloud_budget_months WHERE blocked=1'):
                if wallet in wallets:
                    wallets[wallet]['quarantined'] = True
            result['wallets'] = wallets
            result['activated'] = bool(wallets)
            result['unsettled_attempts'] = conn.execute(
                'SELECT COUNT(*) FROM cloud_budget_attempts WHERE settled=0').fetchone()[0]
            result['continuity'] = False
            if result['anchor_present'] and 'cloud_budget_witness' in tables:
                anchor = json.loads(self.anchor_path.read_text())
                identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone()
                result['continuity'] = bool(identity and anchor.get('db_identity') == identity[0]
                                            and anchor.get('witness') == self._witness(conn)
                                            and anchor.get('schema') == self._schema_hash(conn))
        except (sqlite3.Error, OSError, ValueError, BudgetDenied):
            result['continuity'] = False if result['activated'] else result['continuity']
        finally:
            conn.close()
        return result

    def _settle_once(self, ticket: Reservation, actual: int, timeout: float) -> None:
        with self._transaction(timeout=timeout) as conn:
            row = conn.execute("SELECT bound,settled FROM cloud_budget_attempts "
                               "WHERE id=? AND wallet=? AND month=?",
                               (ticket.id, ticket.wallet, ticket.month)).fetchone()
            if row is None:
                raise BudgetDenied("cloud budget settlement has no reservation")
            bound, settled = row
            if actual > bound:
                conn.execute("UPDATE cloud_budget_months SET blocked=1 WHERE wallet=? AND month=?",
                             (ticket.wallet, ticket.month))
                return
            if not settled:
                conn.execute("UPDATE cloud_budget_attempts SET charged_tokens=?,settled=1 WHERE id=?",
                             (actual, ticket.id))
                month = self.clock().astimezone(timezone.utc).strftime("%Y-%m")
                if month > ticket.month:
                    # The invoice may use completion month. Count it in both
                    # possible months rather than silently freeing this one.
                    conn.execute("INSERT OR IGNORE INTO cloud_budget_carry VALUES(?,?,?,?)",
                                 (ticket.wallet, month, ticket.id, actual))
                if actual < bound:
                    conn.execute("UPDATE cloud_budget_carry SET charged_tokens=MIN(charged_tokens,?) "
                                 "WHERE wallet=? AND attempt_id=?", (actual, ticket.wallet, ticket.id))

    def settle_orphans(self, *, older_than: timedelta, evidence: str, now: datetime,
                       policy: str = 'request-bound', dry_run: bool = False) -> list[str]:
        """Offline: settle reservations whose process died, with an audit row each.

        Only attempts reserved before `now - older_than` (an in-flight call is
        never touched). 'request-bound' charges the attempt's own unknown-usage
        bound (as a settle without usage would have); 'full' keeps the whole
        reservation. Either way the attempt becomes settled, so it no longer
        blocks the monthly rollover; a later real settle cannot rewrite it.
        """
        if not isinstance(evidence, str) or not evidence.strip() or policy not in ('request-bound', 'full'):
            raise BudgetDenied('cloud budget orphan settlement needs evidence and a known policy')
        if now.tzinfo is None or older_than <= timedelta(0):
            raise BudgetDenied('cloud budget orphan settlement needs a UTC time and a positive age')
        cutoff = (now - older_than).astimezone(timezone.utc).isoformat()
        query = ("SELECT a.id,a.wallet,a.month,a.charged_tokens,a.bound,m.unknown_charge "
                 "FROM cloud_budget_attempts a JOIN cloud_budget_attempt_meta m ON m.attempt_id=a.id "
                 "WHERE a.settled=0 AND m.reserved_at < ? ORDER BY m.reserved_at")
        if dry_run:
            conn = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
            try:
                return [r[0] for r in conn.execute(query, (cutoff,))]
            finally:
                conn.close()
        settled = []
        with self._transaction(timeout=ADMIN_TIMEOUT_S) as conn:
            for attempt_id, wallet, month, old, bound, unknown in conn.execute(query, (cutoff,)).fetchall():
                new = min(bound, unknown) if policy == 'request-bound' and _count(unknown) else bound
                conn.execute('UPDATE cloud_budget_attempts SET charged_tokens=?,settled=1 WHERE id=?',
                             (new, attempt_id))
                conn.execute('UPDATE cloud_budget_carry SET charged_tokens=MIN(charged_tokens,?) '
                             'WHERE wallet=? AND attempt_id=?', (new, wallet, attempt_id))
                conn.execute('INSERT INTO cloud_budget_audit(ts,action,attempt_id,wallet,month,old_charge,'
                             'new_charge,policy,evidence) VALUES(?,?,?,?,?,?,?,?,?)',
                             (now.astimezone(timezone.utc).isoformat(), 'settle_orphan', attempt_id,
                              wallet, month, old, new, policy, evidence.strip()))
                settled.append(attempt_id)
        return settled


SHUTDOWN_DRAIN_S = 10.0


class BackgroundSettler:
    """Settlements off the request path: one worker, a bounded queue.

    submit() settles inline only if the ledger is free right now (the same
    kind of work reserve already does); otherwise the attempt is queued and
    the worker settles it with the long retry (SETTLE_TIMEOUT_S). A full
    queue or a shutdown leaves the attempt an orphan holding its bound —
    logged with the remedy, --settle-orphans — never a blocked request.
    """

    def __init__(self, maxsize: int = 10000):
        self._queue: queue.Queue = queue.Queue(maxsize)
        self._pending: dict[str, Reservation] = {}
        self._guard = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stopping = False

    def submit(self, ledger: CloudBudget, ticket: Reservation, prompt_tokens, completion_tokens) -> bool:
        if ledger.try_settle_now(ticket, prompt_tokens, completion_tokens):
            return True
        with self._guard:
            if self._stopping:
                accepted = False
            else:
                try:
                    self._queue.put_nowait((ledger, ticket, prompt_tokens, completion_tokens))
                    self._pending[ticket.id] = ticket
                    accepted = True
                except queue.Full:
                    accepted = False
            if accepted and (self._thread is None or not self._thread.is_alive()):
                self._thread = threading.Thread(target=self._work, name='cloud-budget-settler', daemon=True)
                self._thread.start()
        if not accepted:
            logger.error("cloud budget settler %s: attempt %s left as an orphan holding its bound; "
                         "settle it with cloud_budget_bootstrap --settle-orphans",
                         'stopping' if self._stopping else 'queue full', ticket.id)
        return accepted

    def _work(self) -> None:
        while True:
            try:
                ledger, ticket, prompt_tokens, completion_tokens = self._queue.get(timeout=0.05)
            except queue.Empty:
                with self._guard:
                    if self._stopping:
                        return
                continue
            try:
                ledger.settle(ticket, prompt_tokens, completion_tokens)
            except Exception:  # noqa: BLE001 — the worker must survive any one settlement
                logger.exception("cloud budget background settlement failed for %s", ticket.id)
            finally:
                with self._guard:
                    self._pending.pop(ticket.id, None)
                self._queue.task_done()

    def flush(self, timeout: float) -> bool:
        """Wait (bounded) until every queued settlement has been attempted."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._guard:
                if not self._pending:
                    return True
            time.sleep(0.01)
        with self._guard:
            return not self._pending

    def drain(self, timeout: float = SHUTDOWN_DRAIN_S) -> list[str]:
        """Shutdown: stop accepting, wait up to `timeout`, name what is left."""
        with self._guard:
            self._stopping = True
        deadline = time.monotonic() + timeout
        self.flush(timeout)
        with self._guard:
            left = list(self._pending)
            worker = self._thread
        if worker is not None:
            worker.join(max(0.0, deadline - time.monotonic()))
        if left:
            logger.error("cloud budget shutdown: %d settlement(s) not written (%s); they stay orphans "
                         "holding their bound — settle them with cloud_budget_bootstrap --settle-orphans",
                         len(left), ', '.join(left))
        return left


SETTLER = BackgroundSettler()


def _reset_after_fork() -> None:
    # Only the forking thread survives. Never acquire an inherited lock or
    # drain copied reservations: their owner is still the parent process.
    global SETTLER, _PROCESS_LOCKS, _PROCESS_LOCKS_GUARD
    global _TRANSACTION_FDS, _TRANSACTION_FDS_GUARD
    for fd in _TRANSACTION_FDS:
        os.close(fd)  # parent retains its own descriptor and lock
    _TRANSACTION_FDS = set()
    _TRANSACTION_FDS_GUARD = threading.Lock()
    _PROCESS_LOCKS = {}
    _PROCESS_LOCKS_GUARD = threading.Lock()
    SETTLER = BackgroundSettler(maxsize=SETTLER._queue.maxsize)
    # SQLite connections are transaction-local and never cached here.


os.register_at_fork(
    # Serialize fork with descriptor creation/close, never with a transaction.
    before=lambda: _TRANSACTION_FDS_GUARD.acquire(),
    after_in_parent=lambda: _TRANSACTION_FDS_GUARD.release(),
    after_in_child=_reset_after_fork,
)
# Resolve the current singleton at exit, including in a forked child.
atexit.register(lambda: SETTLER.drain())
