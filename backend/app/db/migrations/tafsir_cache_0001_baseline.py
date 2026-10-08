"""Immutable tafsir_cache migration 1: adopt the production cache table.

Baseline for app.services.tafsir_service, the table's only DDL owner, in
ops/sessions.db. A fresh database gets production's shape (copied 2026-10-08,
tests/fixtures/prod_sessions_db_2026-10-08.sql). An existing table is adopted
only if the service can use it as-is: columns, row-ID key, the UNIQUE(cache_key)
that INSERT OR REPLACE depends on, and the defaults the TTL lookup reads. Extra
columns are kept if an INSERT that omits them still works. A missing lookup
index is recreated; anything else is refused, never rebuilt, and no row is
touched either way. Self-contained on purpose: the checksum covers this file only.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .runner import Migration, MigrationContext, MigrationError

_TABLE = "tafsir_cache"
_INDEX = "idx_tafsir_cache_lookup"
_INDEX_COLUMNS = ("surah", "ayah", "source")
# name -> (affinity, notnull, default) exactly as production declares them.
_COLUMNS = {
    "id": ("INTEGER", 0, None),
    "cache_key": ("TEXT", 0, None),
    "surah": ("INTEGER", 1, None),
    "ayah": ("INTEGER", 1, None),
    "source": ("TEXT", 1, None),
    "attribution": ("TEXT", 0, None),
    "text": ("TEXT", 1, None),
    "footnotes_json": ("TEXT", 0, None),
    "created_at": ("TEXT", 0, "datetime('now')"),
    "hit_count": ("INTEGER", 0, "0"),
}
_CREATE_TABLE = """CREATE TABLE main.tafsir_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            surah INTEGER NOT NULL,
            ayah INTEGER NOT NULL,
            source TEXT NOT NULL,
            attribution TEXT,
            text TEXT NOT NULL,
            footnotes_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            hit_count INTEGER DEFAULT 0
        )"""
_CREATE_INDEX = "CREATE INDEX main.idx_tafsir_cache_lookup ON tafsir_cache (surah, ayah, source)"


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


def _indexes(context: MigrationContext) -> dict:
    """name -> (unique, origin, partial, ((column, collation, desc), ...))."""
    found = {}
    for _, name, unique, origin, partial in context.execute(f"PRAGMA main.index_list({_TABLE})"):
        keys = tuple(
            (row[2], (row[4] or "").upper(), row[3])
            for row in context.execute(
                "SELECT seqno, cid, name, desc, coll, key FROM pragma_index_xinfo(?) "
                "WHERE key = 1 ORDER BY seqno", (name,),
            )
        )
        found[name] = (unique, origin, partial, keys)
    return found


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
    columns = {row[1]: row for row in context.execute(f"PRAGMA main.table_xinfo({_TABLE})")}
    # (cid, name, type, notnull, dflt_value, pk, hidden)
    for name, (kind, notnull, default) in _COLUMNS.items():
        row = columns.get(name)
        if (row is None or _affinity(row[2]) != kind or row[3] != notnull
                or _default(row[4]) != default or row[6] != 0):
            raise MigrationError(f"{_TABLE}.{name} has an incompatible shape")
    for name, row in columns.items():
        if name not in _COLUMNS and (row[6] != 0 or (row[3] and row[4] is None)):
            raise MigrationError(f"{_TABLE}.{name} would break the cache's inserts")
    if (columns["id"][2].upper() != "INTEGER" or columns["id"][5] != 1
            or sum(bool(row[5]) for row in columns.values()) != 1):
        raise MigrationError(f"{_TABLE} requires its INTEGER PRIMARY KEY row ID")
    indexes = _indexes(context)
    # INTEGER PRIMARY KEY DESC and WITHOUT ROWID get a separate pk index.
    if any(origin == "pk" for _, origin, _, _ in indexes.values()):
        raise MigrationError(f"{_TABLE} primary key must be the row ID")
    if not any(unique and not partial and keys == (("cache_key", "BINARY", 0),)
               for unique, _, partial, keys in indexes.values()):
        raise MigrationError(f"{_TABLE} requires UNIQUE(cache_key) for INSERT OR REPLACE")
    lookup = indexes.get(_INDEX)
    if lookup is None:
        if complete:
            raise MigrationError(f"{_INDEX} is missing after migration")
    elif lookup != (0, "c", 0, tuple((c, "BINARY", 0) for c in _INDEX_COLUMNS)):
        raise MigrationError(f"{_INDEX} exists with an incompatible definition")
    return True


def _apply(context: MigrationContext) -> None:
    if not _check(context, complete=False):
        context.execute(_CREATE_TABLE)
    if _INDEX not in _indexes(context):
        context.execute(_CREATE_INDEX)


def _validate(context: MigrationContext) -> None:
    _check(context, complete=True)


MIGRATION = Migration(
    number=1,
    name="tafsir_cache_baseline",
    checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    apply=_apply,
    validate=_validate,
)
