"""Immutable query_rewrites migration 1: adopt the production rewrite cache.

Baseline for app.services.query_rewriter, the table's creator, in
ops/sessions.db. A fresh database gets production's shape (copied 2026-10-08,
tests/fixtures/prod_sessions_db_2026-10-08.sql). An existing table is adopted if
the cache can use it as-is: the PRIMARY KEY(question_hash) that INSERT OR
REPLACE depends on, `rewritten`, and the `ts` default that retention ages rows
by. Extra columns are kept if a named INSERT that omits them still works. A
table from before the retention marker gains `redacted INTEGER`, the same
additive step retention.ensure_marker takes; its rows stay as they are.
Anything else is refused, never rebuilt, and no row is touched.
Self-contained on purpose: the checksum covers this file only.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .runner import Migration, MigrationContext, MigrationError

_TABLE = "query_rewrites"
# name -> (affinity, notnull, default, pk) exactly as production declares them.
_COLUMNS = {
    "question_hash": ("TEXT", 0, None, 1),
    "rewritten": ("TEXT", 0, None, 0),
    "ts": ("TEXT", 0, "datetime('now')", 0),
    "redacted": ("INTEGER", 0, None, 0),
}
_MARKER = "redacted"
_CREATE_TABLE = """CREATE TABLE main.query_rewrites (
                question_hash TEXT PRIMARY KEY, rewritten TEXT,
                ts TEXT DEFAULT (datetime('now')), redacted INTEGER)"""


def _affinity(declaration: str) -> str:
    declaration = declaration.upper()
    if "INT" in declaration:
        return "INTEGER"
    if any(part in declaration for part in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    return "OTHER"


def _default(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    while value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    return value


def _check(context: MigrationContext, *, complete: bool) -> dict:
    """Return the existing columns ({} if no table); raise if unusable."""
    obj = context.execute(
        "SELECT type FROM main.sqlite_master WHERE name = ?", (_TABLE,)
    ).fetchone()
    if obj is None:
        if complete:
            raise MigrationError(f"{_TABLE} is missing after migration")
        return {}
    if obj[0] != "table":
        raise MigrationError(f"{_TABLE} exists but is not a table")
    # (cid, name, type, notnull, dflt_value, pk, hidden)
    columns = {row[1]: row for row in context.execute(f"PRAGMA main.table_xinfo({_TABLE})")}
    for name, (kind, notnull, default, pk) in _COLUMNS.items():
        row = columns.get(name)
        if row is None and name == _MARKER and not complete:
            continue  # pre-marker table: _apply adds it
        if (row is None or _affinity(row[2]) != kind or row[3] != notnull
                or _default(row[4]) != default or row[5] != pk or row[6] != 0):
            raise MigrationError(f"{_TABLE}.{name} has an incompatible shape")
    for name, row in columns.items():
        if name not in _COLUMNS and (row[5] or row[6] != 0 or (row[3] and row[4] is None)):
            raise MigrationError(f"{_TABLE}.{name} would break the cache's inserts")
    keys = [
        tuple(r[0] for r in context.execute(
            "SELECT name FROM pragma_index_info(?) ORDER BY seqno", (row[1],)))
        for row in context.execute(f"PRAGMA main.index_list({_TABLE})")
        if row[3] == "pk" and row[2] and not row[4]
    ]
    if keys != [("question_hash",)]:
        raise MigrationError(f"{_TABLE} requires PRIMARY KEY(question_hash) for INSERT OR REPLACE")
    return columns


def _apply(context: MigrationContext) -> None:
    columns = _check(context, complete=False)
    if not columns:
        context.execute(_CREATE_TABLE)
    elif _MARKER not in columns:
        context.execute(f"ALTER TABLE main.{_TABLE} ADD COLUMN {_MARKER} INTEGER")


def _validate(context: MigrationContext) -> None:
    _check(context, complete=True)


MIGRATION = Migration(
    number=1,
    name="query_rewrites_baseline",
    checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    apply=_apply,
    validate=_validate,
)
