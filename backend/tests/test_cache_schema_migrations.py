"""Baseline migrations for the tafsir/bahouth cache tables in ops/sessions.db.

Every "production" database here is built from production's own DDL
(tests/fixtures/prod_sessions_db_2026-10-08.sql, copied read-only from
tg_backend), never from a hand-written approximation of it. Variants are
derived from that text, so a test can only be as wrong as production itself.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import sqlite3

import pytest

from app.db.migrations.runner import MigrationError, apply_migrations

FIXTURE = Path(__file__).parent / "fixtures" / "prod_sessions_db_2026-10-08.sql"


@dataclass(frozen=True)
class Owner:
    module: str
    namespace: str
    table: str
    index: str
    index_columns: tuple[str, ...]
    service: str
    insert: str


TAFSIR = Owner(
    module="app.db.migrations.tafsir_cache_0001_baseline",
    namespace="tafsir_cache",
    table="tafsir_cache",
    index="idx_tafsir_cache_lookup",
    index_columns=("surah", "ayah", "source"),
    service="app.services.tafsir_service",
    insert=("INSERT INTO tafsir_cache(cache_key,surah,ayah,source,attribution,text,"
            "footnotes_json,created_at,hit_count) VALUES "
            "('k-synthetic',1,2,'saadi','fixture','synthetic text',NULL,"
            "'2026-01-02 03:04:05',7)"),
)
BAHOUTH = Owner(
    module="app.db.migrations.bahouth_cache_0001_baseline",
    namespace="bahouth_cache",
    table="bahouth_cache",
    index="idx_bahouth_cache_lookup",
    index_columns=("tool", "cache_key"),
    service="app.services.quranic_linguistics_service",
    insert=("INSERT INTO bahouth_cache(cache_key,tool,arguments_json,result_json,"
            "created_at,hit_count) VALUES "
            "('k-synthetic','find_root','{}','{\"ok\":1}','2026-01-02 03:04:05',7)"),
)
OWNERS = [pytest.param(TAFSIR, id="tafsir_cache"), pytest.param(BAHOUTH, id="bahouth_cache")]


def migration(owner: Owner):
    return importlib.import_module(owner.module).MIGRATION


def migrate(conn, owner: Owner):
    return apply_migrations(conn, owner.namespace, (migration(owner),))


def prod_statements() -> list[str]:
    text = "\n".join(
        line for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("--")
    )
    return [s.strip() for s in text.split(";\n") if s.strip()]


def prod_table_sql(owner: Owner) -> str:
    (sql,) = [s for s in prod_statements() if s.startswith(f"CREATE TABLE {owner.table} ")]
    return sql


def prod_index_sql(owner: Owner) -> str:
    (sql,) = [s for s in prod_statements() if s.startswith(f"CREATE INDEX {owner.index} ")]
    return sql


def telemetry_ledger():
    rows = []
    for name in ("telemetry_0001_llm_calls", "telemetry_0002_usage_estimated"):
        m = importlib.import_module(f"app.db.migrations.{name}").MIGRATION
        rows.append(("llm_telemetry", m.number, m.name, m.checksum))
    return rows


def build_prod(path: Path) -> sqlite3.Connection:
    """The whole production sessions.db schema, with its llm_telemetry ledger."""
    conn = sqlite3.connect(path)
    conn.executescript(FIXTURE.read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO schema_migrations(namespace,version,name,checksum,applied_at) "
        "VALUES(?,?,?,?,'2026-10-08 06:38:24')", telemetry_ledger(),
    )
    for o in (TAFSIR, BAHOUTH):
        conn.execute(o.insert)
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


@pytest.fixture
def prod(tmp_path):
    conn = build_prod(tmp_path / "prod_sessions.db")
    yield conn
    conn.close()


def test_fixture_is_production_with_the_telemetry_ledger(prod):
    tables = {r[0] for r in prod.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert tables == {"answer_cache", "bahouth_cache", "blocked_fiqh_log", "llm_calls",
                      "query_rewrites", "retrieval_log", "schema_migrations", "sessions",
                      "tafsir_cache"}
    # The checked-in telemetry migrations are exactly what production recorded.
    assert [r[1:] for r in telemetry_ledger()] == [
        (1, "llm_calls", "83c9b23721f7cdaf2a23aa5dca3e62645c0128bbb1e15defa321754e4ecf212e"),
        (2, "usage_estimated", "772d8c7769aa5c71b8a59dff1d25976fe9c217ae283d4bc09cbfdcbea4f1ca8f"),
    ]


# ── adopt: production's own shape is accepted untouched ────────────────────
@pytest.mark.parametrize("owner", OWNERS)
def test_production_shape_is_adopted_without_ddl_or_data_change(prod, owner):
    before_objects = objects(prod)
    before = {t: rows(prod, t) for t in ("tafsir_cache", "bahouth_cache", "llm_calls")}
    telemetry_before = ledger(prod, "llm_telemetry")

    assert migrate(prod, owner) == (1,)

    assert objects(prod) == before_objects
    assert {t: rows(prod, t) for t in before} == before
    assert ledger(prod, "llm_telemetry") == telemetry_before
    m = migration(owner)
    assert ledger(prod, owner.namespace) == [(1, m.name, m.checksum)]
    assert not prod.in_transaction


@pytest.mark.parametrize("owner", OWNERS)
def test_rerun_is_a_noop(prod, owner):
    migrate(prod, owner)
    snapshot = objects(prod), rows(prod, owner.table), ledger(prod, owner.namespace)
    assert migrate(prod, owner) == ()
    assert (objects(prod), rows(prod, owner.table), ledger(prod, owner.namespace)) == snapshot


@pytest.mark.parametrize("owner", OWNERS)
def test_fresh_database_gets_exactly_the_production_shape(tmp_path, prod, owner):
    fresh = sqlite3.connect(tmp_path / "fresh.db")
    assert migrate(fresh, owner) == (1,)
    assert shape(fresh, owner.table) == shape(prod, owner.table)
    fresh.close()


@pytest.mark.parametrize("owner", OWNERS)
def test_missing_lookup_index_is_recreated_and_rows_kept(prod, owner):
    prod.execute(f"DROP INDEX {owner.index}")
    prod.commit()
    before = rows(prod, owner.table)
    assert migrate(prod, owner) == (1,)
    assert rows(prod, owner.table) == before
    (index,) = [i for i in shape(prod, owner.table)[1] if i[0] == owner.index]
    assert index == (owner.index, 0, 0, owner.index_columns)


@pytest.mark.parametrize("owner", OWNERS)
def test_extra_nullable_extension_column_is_kept(prod, owner):
    # retention.ensure_marker adds exactly this to sibling sessions.db tables.
    prod.execute(f"ALTER TABLE {owner.table} ADD COLUMN redacted INTEGER")
    prod.execute(f"UPDATE {owner.table} SET redacted = 1")
    prod.commit()
    before = rows(prod, owner.table)
    assert migrate(prod, owner) == (1,)
    assert rows(prod, owner.table) == before


# ── refuse: anything the service could not safely use ──────────────────────
def _variant(sql: str, old: str, new: str) -> str:
    assert old in sql, f"fixture no longer contains {old!r}"
    return sql.replace(old, new, 1)


INCOMPATIBLE = {
    "cache_key_not_unique": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "cache_key TEXT UNIQUE", "cache_key TEXT")),
    "created_at_missing": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "created_at TEXT DEFAULT (datetime('now')),", "")),
    "created_at_wrong_affinity": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "created_at TEXT", "created_at BLOB")),
    "created_at_lost_default": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "created_at TEXT DEFAULT (datetime('now'))", "created_at TEXT")),
    "hit_count_lost_default": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "hit_count INTEGER DEFAULT 0", "hit_count INTEGER")),
    "nullable_column_made_not_null": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "cache_key TEXT UNIQUE", "cache_key TEXT NOT NULL UNIQUE")),
    "extra_not_null_column_without_default": lambda o, c: c.execute(
        re.sub(r"\)\s*$", ", required_extra TEXT NOT NULL)", prod_table_sql(o))),
    "id_not_rowid_alias": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "id INTEGER PRIMARY KEY AUTOINCREMENT", "id TEXT PRIMARY KEY")),
    "without_rowid": lambda o, c: c.execute(
        _variant(prod_table_sql(o), "id INTEGER PRIMARY KEY AUTOINCREMENT",
                 "id INTEGER PRIMARY KEY") + " WITHOUT ROWID"),
    "lookup_index_name_on_wrong_columns": lambda o, c: (
        c.execute(prod_table_sql(o)),
        c.execute(f"CREATE INDEX {o.index} ON {o.table} (created_at)")),
    "lookup_index_name_is_unique": lambda o, c: (
        c.execute(prod_table_sql(o)),
        c.execute(_variant(prod_index_sql(o), "CREATE INDEX", "CREATE UNIQUE INDEX"))),
    "table_name_is_a_view": lambda o, c: c.execute(
        f"CREATE VIEW {o.table} AS SELECT 1 AS cache_key"),
}


@pytest.mark.parametrize("case", sorted(INCOMPATIBLE))
@pytest.mark.parametrize("owner", OWNERS)
def test_incompatible_shape_is_refused_and_left_untouched(tmp_path, owner, case):
    conn = sqlite3.connect(tmp_path / "variant.db")
    INCOMPATIBLE[case](owner, conn)
    conn.commit()
    before = objects(conn)

    with pytest.raises(MigrationError):
        migrate(conn, owner)

    assert objects(conn) == before  # no ledger, no index, no rebuild
    assert ledger(conn, owner.namespace) == []
    assert not conn.in_transaction
    conn.close()


@pytest.mark.parametrize("owner", OWNERS)
def test_index_dropped_after_adoption_is_refused_not_guessed(prod, owner):
    """A valid ledger never bypasses live validation."""
    migrate(prod, owner)
    prod.execute(f"DROP INDEX {owner.index}")
    prod.commit()
    with pytest.raises(MigrationError):
        migrate(prod, owner)


# ── the owners themselves go through the runner ────────────────────────────
@pytest.mark.parametrize("owner", OWNERS)
def test_service_connection_adopts_production_db(tmp_path, monkeypatch, owner):
    path = tmp_path / "prod_sessions.db"
    build_prod(path).close()
    svc = importlib.import_module(owner.service)
    monkeypatch.setattr(svc, "_TELEMETRY_DB", path)

    conn = svc._cache_conn()
    try:
        assert not conn.in_transaction
        m = migration(owner)
        assert ledger(conn, owner.namespace) == [(1, m.name, m.checksum)]
        assert ledger(conn, "llm_telemetry") == [r[1:] for r in telemetry_ledger()]
    finally:
        conn.close()


def test_tafsir_cache_roundtrip_on_production_db(tmp_path, monkeypatch):
    svc = importlib.import_module(TAFSIR.service)
    path = tmp_path / "prod_sessions.db"
    build_prod(path).close()
    monkeypatch.setattr(svc, "_TELEMETRY_DB", path)
    monkeypatch.setattr(svc, "TAFSIR_CACHE_ENABLED", True)
    svc._cache_put(svc.TafsirResult(surah=2, ayah=255, source="saadi",
                                    attribution="fixture", text="synthetic"))
    got = svc._cache_get(2, 255, "saadi")
    assert got is not None and got.text == "synthetic"


def test_bahouth_cache_roundtrip_on_production_db(tmp_path, monkeypatch):
    svc = importlib.import_module(BAHOUTH.service)
    path = tmp_path / "prod_sessions.db"
    build_prod(path).close()
    monkeypatch.setattr(svc, "_TELEMETRY_DB", path)
    monkeypatch.setattr(svc, "BAHOUTH_CACHE_ENABLED", True)
    svc._cache_put("find_root", {"root": "علم"}, {"ok": 1})
    assert svc._cache_get("find_root", {"root": "علم"}) == {"ok": 1}


@pytest.mark.parametrize("owner", OWNERS)
def test_incompatible_db_disables_the_cache_without_touching_it(tmp_path, monkeypatch, owner):
    path = tmp_path / "variant.db"
    conn = sqlite3.connect(path)
    INCOMPATIBLE["cache_key_not_unique"](owner, conn)
    conn.commit()
    before = objects(conn)
    conn.close()

    svc = importlib.import_module(owner.service)
    monkeypatch.setattr(svc, "_TELEMETRY_DB", path)
    with pytest.raises(MigrationError):
        svc._cache_conn()
    if owner is TAFSIR:
        monkeypatch.setattr(svc, "TAFSIR_CACHE_ENABLED", True)
        assert svc._cache_get(1, 1, "saadi") is None  # non-fatal: falls back to the network
    else:
        monkeypatch.setattr(svc, "BAHOUTH_CACHE_ENABLED", True)
        assert svc._cache_get("find_root", {"root": "x"}) is None

    conn = sqlite3.connect(path)
    assert objects(conn) == before
    conn.close()
