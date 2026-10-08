"""Durable per-wire-attempt admission; diagnostics never authorize paid traffic."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import logging
import os
import sqlite3
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)
_MAX_INTEGER = (1 << 63) - 1
PAID_ALIASES = ('azure_deepseek', 'deepseek', 'deepseek_aux', 'deepseek_fallback')
# llm_calls.provider values that are never a request to any wallet: the
# gateway's all-failed marker row (telemetry from codex/batch-oct8).
NON_WALLET_PROVIDERS = ('gateway',)
_LEDGER_TABLES = ('cloud_budget_months', 'cloud_budget_attempts', 'cloud_budget_carry',
                  'cloud_budget_activation', 'cloud_budget_identity')


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
# DEEPSEEK_BILLING_PROFILE_ALIASES, never a built-in default.
_BILLING_PROFILES = {
    ("https://api.deepseek.com:443", model): BillingProfile(1048576, 393216)
    for model in ("deepseek-flash", "deepseek-v4-pro")
}


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


@dataclass(frozen=True)
class Reservation:
    id: str
    wallet: str
    month: str
    bound: int


class CloudBudget:
    def __init__(self, path: Path, *, clock: Callable | None = None):
        try:
            self.path = Path(path).resolve()
        except (OSError, ValueError) as exc:
            raise BudgetDenied('cloud budget DB identity/path unknown') from exc
        self.anchor_path = Path(str(self.path) + '.cloud-budget-anchor')
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _digest(conn) -> str:
        """Witness ledger contents, including deletions and restored snapshots.

        Diagnostic telemetry rows are intentionally excluded: they are written
        after admission and cannot change the activated opening balance.
        """
        digest = hashlib.sha256()
        for table in _LEDGER_TABLES:
            schema = conn.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?',
                                  (table,)).fetchone()
            if not schema:
                raise BudgetDenied('cloud budget lost schema; reconciliation required')
            digest.update(json.dumps(schema).encode())
            for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid'):
                digest.update(json.dumps(row, separators=(',', ':')).encode())
                digest.update(b'\n')
        return digest.hexdigest()

    def _write_anchor(self, conn):
        identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone()
        if not identity:
            raise BudgetDenied('cloud budget uninitialized DB identity')
        data = json.dumps({'db_identity': identity[0], 'digest': self._digest(conn)})
        fd, name = tempfile.mkstemp(prefix=self.anchor_path.name + '.', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.anchor_path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @contextlib.contextmanager
    def _transaction(self, *, bootstrap=False):
        conn = None
        lock = None
        try:
            if not self.path.is_file():
                raise BudgetDenied('cloud budget cutover unknown: existing history DB required')
            if not bootstrap and not self.anchor_path.is_file():
                raise BudgetDenied('cloud budget cutover uninitialized or continuity anchor lost')
            # Serialize DB commit + separate durable witness across processes.
            # A crash between them denies further traffic rather than resetting.
            lock = open(str(self.anchor_path) + '.lock', 'a')
            deadline = time.monotonic() + 0.2
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise BudgetDenied('cloud budget continuity witness busy')
                    time.sleep(0.002)
            identity_stat = self.path.stat()
            conn = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=0.2)
            conn.execute("PRAGMA busy_timeout = 200")
            conn.execute('PRAGMA synchronous = FULL')
            conn.execute("BEGIN IMMEDIATE")
            # Missing telemetry is unknown history, even on explicit bootstrap.
            conn.execute('SELECT ts,provider,prompt_tokens,completion_tokens FROM llm_calls LIMIT 0')
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if self.anchor_path.exists():
                anchor = json.loads(self.anchor_path.read_text())
                identity = conn.execute('SELECT db_identity FROM cloud_budget_identity WHERE id=1').fetchone()
                if (not identity or anchor.get('db_identity') != identity[0]
                        or anchor.get('digest') != self._digest(conn)):
                    raise BudgetDenied('cloud budget continuity/restore identity mismatch; reconcile offline')
            elif not bootstrap or 'cloud_budget_activation' in tables or 'cloud_budget_identity' in tables:
                raise BudgetDenied('cloud budget continuity anchor lost; reconciliation required')
            else:
                # Adopt an intact pre-activation ledger; never repair partial loss.
                legacy = set(_LEDGER_TABLES[:3]) & tables
                if legacy and legacy != set(_LEDGER_TABLES[:3]):
                    raise BudgetDenied('cloud budget lost legacy schema; reconciliation required')
                self._create_schema(conn)
            yield conn
            current_stat = self.path.stat()
            if (identity_stat.st_dev, identity_stat.st_ino) != (current_stat.st_dev, current_stat.st_ino):
                raise BudgetDenied('cloud budget DB identity replaced during accounting')
            conn.commit()
            self._write_anchor(conn)
        except (sqlite3.Error, OSError, ValueError, TypeError, AttributeError) as exc:
            raise BudgetDenied("cloud budget accounting unknown or unavailable") from exc
        finally:
            if conn is not None:
                conn.close()  # rolls back on exceptions; never leaves a writer open
            if lock is not None:
                lock.close()

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
        conn.execute("""CREATE TABLE IF NOT EXISTS cloud_budget_carry (
            wallet TEXT NOT NULL, month TEXT NOT NULL, attempt_id TEXT NOT NULL,
            charged_tokens INTEGER NOT NULL,
            PRIMARY KEY(wallet,month,attempt_id))""")
        conn.execute('CREATE TABLE cloud_budget_activation ('
                     'wallet TEXT NOT NULL, month TEXT NOT NULL, receipt TEXT NOT NULL, '
                     'PRIMARY KEY(wallet,month))')
        conn.execute('CREATE TABLE cloud_budget_identity ('
                     'id INTEGER PRIMARY KEY CHECK(id=1), db_identity TEXT NOT NULL)')

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
        with self._transaction(bootstrap=True) as conn:
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
                legacy_aliases: tuple[str, ...]) -> Reservation:
        if not _count(cap) or cap == 0 or not _count(bound) or bound == 0 or not wallet:
            raise BudgetDenied("cloud budget invalid cap or reservation")
        with self._transaction() as conn:
            now = self.clock()
            if now.tzinfo is None:
                raise BudgetDenied("cloud budget requires a UTC accounting clock")
            month = now.astimezone(timezone.utc).strftime("%Y-%m")
            activation = conn.execute('SELECT receipt FROM cloud_budget_activation WHERE wallet=? AND month=?',
                                      (wallet, month)).fetchone()
            if not activation:
                raise BudgetDenied('cloud budget cutover uninitialized wallet/month; explicit bootstrap required')
            if not set(legacy_aliases).issubset(json.loads(activation[0])['legacy_aliases']):
                raise BudgetDenied('cloud budget cutover missing paid alias reconciliation')
            ticket = Reservation(uuid.uuid4().hex, wallet, month, bound)
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
        return ticket

    def settle(self, ticket: Reservation, prompt_tokens, completion_tokens) -> None:
        """No valid final usage => retain the full reservation. Never free on error.

        An accounting-write failure retains the committed original charge. A
        duplicate settlement cannot alter a previously settled charge.
        """
        complete_counts = _count(prompt_tokens) and _count(completion_tokens)
        actual = prompt_tokens + completion_tokens if complete_counts else ticket.bound
        try:
            with self._transaction() as conn:
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
                    if complete_counts:
                        conn.execute("UPDATE cloud_budget_carry SET charged_tokens=MIN(charged_tokens,?) "
                                     "WHERE wallet=? AND attempt_id=?", (actual, ticket.wallet, ticket.id))
        except BudgetDenied as exc:
            logger.warning("cloud budget settlement retained original charge: %s", exc)
