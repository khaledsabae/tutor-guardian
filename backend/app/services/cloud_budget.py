"""Durable per-wire-attempt admission; diagnostics never authorize paid traffic."""
from __future__ import annotations

import contextlib
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)
_MAX_INTEGER = (1 << 63) - 1


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


# Verified 2026-10-07: api-docs.deepseek.com/quick_start/pricing and
# api-docs.deepseek.com/api/create-chat-completion. 1M rounded up to 2**20.
# Legacy aliases, Azure deployment names and compatible hosts are not verified.
_BILLING_PROFILES = {
    ("https://api.deepseek.com:443", model): BillingProfile(1048576, 393216)
    for model in ("deepseek-flash", "deepseek-v4-pro")
}


def upper_token_bound(messages: list[dict], max_output_tokens: int, *,
                      endpoint: str, model: str) -> int:
    """Reserve the entire verified context, independent of input tokenization.

    The profile requires the actual max_tokens parameter on every wire attempt.
    Provider violations of its documented contract are outside this guarantee.
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
    profile = _BILLING_PROFILES.get((origin, model))
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
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @contextlib.contextmanager
    def _transaction(self):
        conn = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=0.2)
            conn.execute("PRAGMA busy_timeout = 200")
            conn.execute("BEGIN IMMEDIATE")
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
            yield conn
            conn.commit()
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise BudgetDenied("cloud budget accounting unknown or unavailable") from exc
        finally:
            if conn is not None:
                conn.close()  # rolls back on exceptions; never leaves a writer open

    def _opening(self, conn, month: str, aliases: tuple[str, ...]) -> int:
        if not aliases or not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='llm_calls'"
        ).fetchone():
            return 0
        marks = ",".join("?" for _ in aliases)
        rows = conn.execute(
            f"SELECT ts,prompt_tokens,completion_tokens FROM llm_calls WHERE provider IN ({marks}) "
            "AND (strftime('%Y-%m',ts)=? OR strftime('%Y-%m',ts) IS NULL)",
            (*aliases, month),
        )
        total = 0
        for ts, prompt, completion in rows:
            if not ts or not _count(prompt) or not _count(completion):
                raise BudgetDenied("cloud budget opening billing unknown")
            total += prompt + completion
            if total > _MAX_INTEGER:
                raise BudgetDenied("cloud budget opening balance overflow")
        return total

    def reserve(self, wallet: str, cap: int, bound: int, *,
                legacy_aliases: tuple[str, ...]) -> Reservation:
        if not _count(cap) or cap == 0 or not _count(bound) or bound == 0 or not wallet:
            raise BudgetDenied("cloud budget invalid cap or reservation")
        with self._transaction() as conn:
            now = self.clock()
            if now.tzinfo is None:
                raise BudgetDenied("cloud budget requires a UTC accounting clock")
            month = now.astimezone(timezone.utc).strftime("%Y-%m")
            ticket = Reservation(uuid.uuid4().hex, wallet, month, bound)
            if conn.execute("SELECT 1 FROM cloud_budget_months WHERE wallet=? AND blocked=1",
                            (wallet,)).fetchone():
                raise BudgetDenied("cloud budget wallet quarantined; billing bounds require review")
            row = conn.execute("SELECT opening_tokens,blocked FROM cloud_budget_months "
                               "WHERE wallet=? AND month=?", (wallet, month)).fetchone()
            if row is None:
                opening = self._opening(conn, month, legacy_aliases)
                conn.execute("INSERT INTO cloud_budget_months VALUES(?,?,?,0)", (wallet, month, opening))
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
