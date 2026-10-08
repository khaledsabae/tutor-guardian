"""Production's sessions.db schema, for baseline-migration tests.

The fixture is production's own DDL (copied read-only from tg_backend, schema
only, see its header). Helpers here never invent a table shape: variants are
derived from the copied text.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import sqlite3

FIXTURE = Path(__file__).parent / "fixtures" / "prod_sessions_db_2026-10-08.sql"


def prod_statements() -> list[str]:
    text = "\n".join(
        line for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("--")
    )
    return [s.strip() for s in text.split(";\n") if s.strip()]


def prod_table_sql(table: str) -> str:
    (sql,) = [s for s in prod_statements() if s.startswith(f"CREATE TABLE {table} ")]
    return sql


def prod_index_sql(index: str) -> str:
    (sql,) = [s for s in prod_statements() if s.startswith(f"CREATE INDEX {index} ")]
    return sql


def variant(sql: str, old: str, new: str) -> str:
    assert old in sql, f"fixture no longer contains {old!r}"
    return sql.replace(old, new, 1)


def telemetry_ledger() -> list[tuple]:
    rows = []
    for name in ("telemetry_0001_llm_calls", "telemetry_0002_usage_estimated"):
        m = importlib.import_module(f"app.db.migrations.{name}").MIGRATION
        rows.append(("llm_telemetry", m.number, m.name, m.checksum))
    return rows


def build_prod(path: Path, inserts=()) -> sqlite3.Connection:
    """The whole production sessions.db schema, with its llm_telemetry ledger."""
    conn = sqlite3.connect(path)
    conn.executescript(FIXTURE.read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO schema_migrations(namespace,version,name,checksum,applied_at) "
        "VALUES(?,?,?,?,'2026-10-08 06:38:24')", telemetry_ledger(),
    )
    for sql in inserts:
        conn.execute(sql)
    conn.commit()
    return conn


def objects(conn) -> list[tuple]:
    return sorted(tuple(r) for r in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master"))


def rows(conn, table: str) -> list[tuple]:
    return sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {table}"))


def ledger(conn, namespace: str) -> list[tuple]:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone() is None:
        return []
    return [tuple(r) for r in conn.execute(
        "SELECT version,name,checksum FROM schema_migrations WHERE namespace=? ORDER BY version",
        (namespace,))]


def shape(conn, table: str):
    columns = [tuple(r) for r in conn.execute(f"PRAGMA table_xinfo({table})")]
    indexes = []
    for _, name, unique, origin, partial in conn.execute(f"PRAGMA index_list({table})"):
        cols = tuple(r[2] for r in conn.execute(f"PRAGMA index_info({name})"))
        indexes.append((name if origin == "c" else origin, unique, partial, cols))
    return columns, sorted(indexes)
