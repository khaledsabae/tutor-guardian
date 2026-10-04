"""Retention the privacy policy promises — enforced on a schedule, not on traffic.

Run once a day from the existing evening cron (ops/scripts/cron_push_triggers.py
→ evening_run → privacy_housekeeping); no new cron line. It used to happen only
as a side effect of new writes, so a quiet table kept everything (PR #26
review, P7: 639 of 641 referral clicks were already older than their 7 days).

| store (ops/sessions.db unless noted) | kept | historical rows logged with names |
|---|---|---|
| retrieval_log (search log)          | 90 days | deleted |
| query_rewrites (rewrite cache)      | 90 days | deleted |
| answer_cache (general answers)      | 45 days | deleted (and never served) |
| blocked_fiqh_log                    | 90 days | names re-redacted in place |
| llm_calls (AI call log, no text)    | 90 days | — |
| sessions (usage log, no text)       | 90 days | — |
| referral_clicks (main DB: IP + UA)  | 7 days  | — (folded by PR #25 once it lands) |
| child_web_claims (main DB)          | until expiry | — |

"Historical" = written before the redacting code: those rows carry no
`redacted = 1` marker. Every writer now sets it.

Failures are not swallowed: each step reports `error: …` in the result and
logs at ERROR; the cron prints the summary and exits non-zero after the pushes.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

DAYS = {
    "retrieval_log": 90,
    "query_rewrites": 90,
    "answer_cache": 45,
    "blocked_fiqh_log": 90,
    "llm_calls": 90,
    "sessions": 90,
}
REFERRAL_CLICK_DAYS = 7


def ensure_marker(conn: sqlite3.Connection, table: str) -> None:
    """Add the `redacted` marker column to a log table that predates it."""
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if cols and "redacted" not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN redacted INTEGER")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _purge(path: Path, table: str, ts_col: str, days: int,
           drop_unmarked: bool = False) -> int:
    conn = sqlite3.connect(path, timeout=10.0)
    try:
        cols = _columns(conn, table)
        if not cols:
            return 0                                   # never created: nothing kept
        # datetime(): rows are written both as SQLite's «YYYY-MM-DD HH:MM:SS»
        # and as Python ISO strings with a «T» and an offset.
        n = conn.execute(
            f"DELETE FROM {table} WHERE datetime({ts_col}) < datetime('now', ?)",
            (f"-{days} days",),
        ).rowcount
        if drop_unmarked:
            if "redacted" in cols:
                n += conn.execute(f"DELETE FROM {table} WHERE redacted IS NULL").rowcount
            else:
                n += conn.execute(f"DELETE FROM {table}").rowcount   # all historical
                ensure_marker(conn, table)
        conn.commit()
        return n
    finally:
        conn.close()


def _reredact_fiqh(path: Path) -> int:
    """Old blocked-question rows were scrubbed with the exact-spelling matcher;
    run them through today's (variants, tokens) and mark them."""
    from app.services.privacy import known_child_names, redact_with_names
    conn = sqlite3.connect(path, timeout=10.0)
    try:
        if not _columns(conn, "blocked_fiqh_log"):
            return 0
        ensure_marker(conn, "blocked_fiqh_log")
        names = known_child_names()
        rows = conn.execute(
            "SELECT id, question FROM blocked_fiqh_log WHERE redacted IS NULL").fetchall()
        for rid, question in rows:
            conn.execute("UPDATE blocked_fiqh_log SET question = ?, redacted = 1 WHERE id = ?",
                         (redact_with_names(question or "", names), rid))
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def _purge_main_db() -> dict[str, int]:
    from app.db.init_db import get_conn
    conn = get_conn()
    out: dict[str, int] = {}
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "referral_clicks" in tables and "referral_click_days" not in tables:
            # PR #25 folds raw clicks into daily counts on its own schedule;
            # without it, raw rows simply go after their seven days.
            out["referral_clicks"] = conn.execute(
                "DELETE FROM referral_clicks WHERE clicked_at < datetime('now', ?)",
                (f"-{REFERRAL_CLICK_DAYS} days",)).rowcount
        if "child_web_claims" in tables:
            out["child_web_claims"] = conn.execute(
                "DELETE FROM child_web_claims WHERE expires_at < ?", (time.time(),)).rowcount
        conn.commit()
        return out
    finally:
        conn.close()


def _steps() -> list[tuple[str, Callable[[], object]]]:
    from app.services import (
        ai_gateway, answer_cache, fiqh_guard, query_rewriter, retrieval, session_logger,
    )
    return [
        ("retrieval_log", lambda: _purge(Path(retrieval._TELEMETRY_DB), "retrieval_log", "ts",
                                         DAYS["retrieval_log"], drop_unmarked=True)),
        ("query_rewrites", lambda: _purge(Path(query_rewriter._CACHE_DB), "query_rewrites", "ts",
                                          DAYS["query_rewrites"], drop_unmarked=True)),
        ("answer_cache", lambda: _purge(Path(answer_cache._DB), "answer_cache", "created_at",
                                        DAYS["answer_cache"], drop_unmarked=True)),
        ("blocked_fiqh_log", lambda: _reredact_fiqh(Path(fiqh_guard._LOG_DB))
            + _purge(Path(fiqh_guard._LOG_DB), "blocked_fiqh_log", "created_at",
                     DAYS["blocked_fiqh_log"])),
        ("llm_calls", lambda: _purge(Path(ai_gateway._TELEMETRY_DB), "llm_calls", "ts",
                                     DAYS["llm_calls"])),
        ("sessions", lambda: _purge(Path(session_logger.DB_PATH), "sessions", "ts",
                                    DAYS["sessions"])),
        ("main", _purge_main_db),
    ]


def run_housekeeping() -> dict[str, object]:
    """Every purge, each on its own: one failure neither hides nor stops the rest."""
    results: dict[str, object] = {}
    for name, step in _steps():
        try:
            out = step()
            if isinstance(out, dict):
                results.update(out)
            else:
                results[name] = out
        except Exception as exc:  # noqa: BLE001 — reported, not swallowed
            logger.error("retention: %s failed: %s", name, exc)
            results[name] = f"error: {type(exc).__name__}: {exc}"
    return results


def has_errors(results: dict[str, object]) -> bool:
    return any(isinstance(v, str) and v.startswith("error") for v in results.values())
