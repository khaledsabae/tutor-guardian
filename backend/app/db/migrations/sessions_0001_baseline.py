"""Immutable sessions migration 1: adopt the production `sessions` table.

Baseline for app.services.session_logger, the table's only DDL owner, in
ops/sessions.db. A fresh database gets production's shape (copied 2026-10-08,
tests/fixtures/prod_sessions_db_2026-10-08.sql). session_logger inserts
positionally (INSERT INTO sessions VALUES with 11 values), so an existing table
is adopted only with exactly production's eleven columns in production's
order and types, plus the primary key on id. Anything else, including an
extra nullable column, would break that insert. It is refused, never rebuilt,
and no row is touched. Self-contained on purpose: the checksum covers this
file only.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .runner import Migration, MigrationContext, MigrationError

_TABLE = "sessions"
# (name, affinity, pk) in production's column order; none NOT NULL, no defaults.
_COLUMNS = (
    ("id", "TEXT", 1),
    ("ts", "TEXT", 0),
    ("domain", "TEXT", 0),
    ("behavior_type", "TEXT", 0),
    ("age_group", "TEXT", 0),
    ("severity", "TEXT", 0),
    ("mode", "TEXT", 0),
    ("needs_human_review", "INTEGER", 0),
    ("reply_length", "INTEGER", 0),
    ("retrieved_count", "INTEGER", 0),
    ("flag", "TEXT", 0),
)
_CREATE_TABLE = """CREATE TABLE main.sessions (
            id TEXT PRIMARY KEY,
            ts TEXT,
            domain TEXT,
            behavior_type TEXT,
            age_group TEXT,
            severity TEXT,
            mode TEXT,
            needs_human_review INTEGER,
            reply_length INTEGER,
            retrieved_count INTEGER,
            flag TEXT
        )"""


def _affinity(declaration: str) -> str:
    declaration = declaration.upper()
    if "INT" in declaration:
        return "INTEGER"
    if any(part in declaration for part in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    return "OTHER"


def _check(context: MigrationContext, *, complete: bool) -> bool:
    """Return whether the table exists; raise if it cannot be used as-is."""
    obj = context.execute(
        "SELECT type FROM main.sqlite_master WHERE name = ?", (_TABLE,)
    ).fetchone()
    if obj is None:
        if complete:
            raise MigrationError(f"{_TABLE} is missing after migration")
        return False
    if obj[0] != "table":
        raise MigrationError(f"{_TABLE} exists but is not a table")
    # (cid, name, type, notnull, dflt_value, pk, hidden)
    columns = list(context.execute(f"PRAGMA main.table_xinfo({_TABLE})"))
    found = [(row[1], _affinity(row[2]), row[5]) for row in columns]
    if found != list(_COLUMNS):
        raise MigrationError(
            f"{_TABLE} must have exactly production's columns in order (positional INSERT)")
    if any(row[3] or row[4] is not None or row[6] for row in columns):
        raise MigrationError(f"{_TABLE} has a NOT NULL, default or hidden column production lacks")
    keys = [
        tuple(r[0] for r in context.execute(
            "SELECT name FROM pragma_index_info(?) ORDER BY seqno", (row[1],)))
        for row in context.execute(f"PRAGMA main.index_list({_TABLE})")
        if row[3] == "pk" and row[2] and not row[4]
    ]
    if keys != [("id",)]:
        raise MigrationError(f"{_TABLE} requires PRIMARY KEY(id)")
    return True


def _apply(context: MigrationContext) -> None:
    if not _check(context, complete=False):
        context.execute(_CREATE_TABLE)


def _validate(context: MigrationContext) -> None:
    _check(context, complete=True)


MIGRATION = Migration(
    number=1,
    name="sessions_baseline",
    checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    apply=_apply,
    validate=_validate,
)
