"""Baseline migrations for sessions.db's `sessions` and `query_rewrites`.

Built only from production's copied DDL (tests/prod_schema_support.py). The
two owners differ in what "compatible" means. session_logger inserts
positionally, so `sessions` must keep exactly production's eleven columns in
order. query_rewriter inserts by name and retention reads `redacted`, so
`query_rewrites` keeps extra columns and gains the marker if it lacks it.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import logging
import re
import sqlite3

import pytest

from app.db.migrations.runner import MigrationError, apply_migrations
from tests.prod_schema_support import (
    build_prod, ledger, objects, prod_table_sql, rows, shape, telemetry_ledger, variant,
)


@dataclass(frozen=True)
class Owner:
    module: str
    namespace: str
    table: str
    service: str
    path_attr: str
    insert: str


SESSIONS = Owner(
    module="app.db.migrations.sessions_0001_baseline",
    namespace="sessions",
    table="sessions",
    service="app.services.session_logger",
    path_attr="DB_PATH",
    insert=("INSERT INTO sessions VALUES ('s-synthetic','2026-01-02T03:04:05+00:00',"
            "'tarbiyah','b','7-9','خفيف','normal',0,120,3,'')"),
)
REWRITES = Owner(
    module="app.db.migrations.query_rewrites_0001_baseline",
    namespace="query_rewrites",
    table="query_rewrites",
    service="app.services.query_rewriter",
    path_attr="_CACHE_DB",
    insert=("INSERT INTO query_rewrites(question_hash,rewritten,ts,redacted) "
            "VALUES ('h-synthetic','كلمات بحث','2026-01-02 03:04:05',1)"),
)
OWNERS = [pytest.param(SESSIONS, id="sessions"), pytest.param(REWRITES, id="query_rewrites")]
INSERTS = (SESSIONS.insert, REWRITES.insert)


def migration(owner: Owner):
    return importlib.import_module(owner.module).MIGRATION


def migrate(conn, owner: Owner):
    return apply_migrations(conn, owner.namespace, (migration(owner),))


@pytest.fixture
def prod(tmp_path):
    conn = build_prod(tmp_path / "prod_sessions.db", INSERTS)
    yield conn
    conn.close()


def _service(owner: Owner, monkeypatch, path):
    svc = importlib.import_module(owner.service)
    monkeypatch.setattr(svc, owner.path_attr, path)
    return svc


# ── adopt ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("owner", OWNERS)
def test_production_shape_is_adopted_without_ddl_or_data_change(prod, owner):
    before_objects = objects(prod)
    before = {t: rows(prod, t) for t in ("sessions", "query_rewrites", "llm_calls")}
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


def test_query_rewrites_without_the_marker_gains_it_and_keeps_every_row(tmp_path):
    conn = sqlite3.connect(tmp_path / "legacy.db")
    conn.execute(variant(prod_table_sql("query_rewrites"), ", redacted INTEGER)", ")"))
    conn.execute("INSERT INTO query_rewrites(question_hash,rewritten,ts) "
                 "VALUES ('h-old','قديم','2026-01-01 00:00:00')")
    conn.commit()

    assert migrate(conn, REWRITES) == (1,)

    assert rows(conn, "query_rewrites") == [("h-old", "قديم", "2026-01-01 00:00:00", None)]
    prod = build_prod(tmp_path / "prod.db")
    assert shape(conn, "query_rewrites") == shape(prod, "query_rewrites")
    prod.close()
    conn.close()


def test_query_rewrites_extra_nullable_column_is_kept(prod):
    prod.execute("ALTER TABLE query_rewrites ADD COLUMN model TEXT")
    prod.commit()
    before = rows(prod, "query_rewrites")
    assert migrate(prod, REWRITES) == (1,)
    assert rows(prod, "query_rewrites") == before


# ── refuse ─────────────────────────────────────────────────────────────────
INCOMPATIBLE = {
    SESSIONS: {
        # INSERT INTO sessions VALUES (11 values) cannot fill a twelfth column.
        "extra_column": lambda c: (c.execute(prod_table_sql("sessions")),
                                   c.execute("ALTER TABLE sessions ADD COLUMN extra TEXT")),
        "column_order_swapped": lambda c: c.execute(variant(
            prod_table_sql("sessions"), "domain TEXT,\n            behavior_type TEXT,",
            "behavior_type TEXT,\n            domain TEXT,")),
        "flag_missing": lambda c: c.execute(variant(
            prod_table_sql("sessions"), ",\n            flag TEXT", "")),
        "id_not_primary_key": lambda c: c.execute(variant(
            prod_table_sql("sessions"), "id TEXT PRIMARY KEY", "id TEXT")),
        "ts_wrong_affinity": lambda c: c.execute(variant(
            prod_table_sql("sessions"), "ts TEXT,", "ts BLOB,")),
        "domain_made_not_null": lambda c: c.execute(variant(
            prod_table_sql("sessions"), "domain TEXT,", "domain TEXT NOT NULL,")),
        "table_name_is_a_view": lambda c: c.execute("CREATE VIEW sessions AS SELECT 1 AS id"),
    },
    REWRITES: {
        "question_hash_not_primary_key": lambda c: c.execute(variant(
            prod_table_sql("query_rewrites"), "question_hash TEXT PRIMARY KEY", "question_hash TEXT")),
        "ts_lost_default": lambda c: c.execute(variant(
            prod_table_sql("query_rewrites"), "ts TEXT DEFAULT (datetime('now'))", "ts TEXT")),
        "redacted_wrong_affinity": lambda c: c.execute(variant(
            prod_table_sql("query_rewrites"), "redacted INTEGER", "redacted TEXT")),
        "rewritten_missing": lambda c: c.execute(variant(
            prod_table_sql("query_rewrites"), " rewritten TEXT,", "")),
        "extra_not_null_column_without_default": lambda c: c.execute(
            re.sub(r"\)\s*$", ", required_extra TEXT NOT NULL)", prod_table_sql("query_rewrites"))),
        "table_name_is_a_view": lambda c: c.execute(
            "CREATE VIEW query_rewrites AS SELECT 1 AS question_hash"),
    },
}
CASES = [pytest.param(owner, case, id=f"{owner.table}-{case}")
         for owner in (SESSIONS, REWRITES) for case in sorted(INCOMPATIBLE[owner])]


@pytest.mark.parametrize("owner,case", CASES)
def test_incompatible_shape_is_refused_and_left_untouched(tmp_path, owner, case):
    conn = sqlite3.connect(tmp_path / "variant.db")
    INCOMPATIBLE[owner][case](conn)
    conn.commit()
    before = objects(conn)

    with pytest.raises(MigrationError):
        migrate(conn, owner)

    assert objects(conn) == before
    assert ledger(conn, owner.namespace) == []
    assert not conn.in_transaction
    conn.close()


# ── the owners themselves go through the runner ────────────────────────────
@pytest.mark.parametrize("owner", OWNERS)
def test_service_connection_adopts_every_database_it_opens(tmp_path, monkeypatch, owner):
    """No process flag: a second DB in the same process is adopted too."""
    m = migration(owner)
    for name in ("first.db", "second.db"):
        path = tmp_path / name
        build_prod(path).close()
        svc = _service(owner, monkeypatch, path)
        conn = svc._get_conn()
        try:
            assert not conn.in_transaction
            assert ledger(conn, owner.namespace) == [(1, m.name, m.checksum)]
            assert ledger(conn, "llm_telemetry") == [r[1:] for r in telemetry_ledger()]
        finally:
            conn.close()


def test_session_logger_writes_to_the_production_db(tmp_path, monkeypatch):
    path = tmp_path / "prod.db"
    build_prod(path).close()
    svc = _service(SESSIONS, monkeypatch, path)
    svc.log_session("tarbiyah", "b", "7-9", "خفيف", "normal", False, 10, 2, "")
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT domain, reply_length FROM sessions").fetchall() == [("tarbiyah", 10)]
    conn.close()


def test_query_rewrite_cache_roundtrip_on_production_db(tmp_path, monkeypatch):
    path = tmp_path / "prod.db"
    build_prod(path).close()
    svc = _service(REWRITES, monkeypatch, path)
    svc._cache_put("h1", "نوم الطفل")
    assert svc._cache_get("h1") == "نوم الطفل"
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT redacted FROM query_rewrites WHERE question_hash='h1'").fetchone() == (1,)
    conn.close()


@pytest.mark.parametrize("owner,case", [
    pytest.param(SESSIONS, "extra_column", id="sessions"),
    pytest.param(REWRITES, "question_hash_not_primary_key", id="query_rewrites"),
])
def test_incompatible_db_is_non_fatal_and_untouched(tmp_path, monkeypatch, owner, case):
    path = tmp_path / "variant.db"
    conn = sqlite3.connect(path)
    INCOMPATIBLE[owner][case](conn)
    conn.commit()
    before = objects(conn), rows(conn, owner.table)
    conn.close()

    svc = _service(owner, monkeypatch, path)
    with pytest.raises(MigrationError):
        svc._get_conn()
    if owner is SESSIONS:
        svc.log_session("tarbiyah", "b", "7-9", "خفيف", "normal", False, 10, 2, "")  # swallowed
    else:
        assert svc._cache_get("h1") is None
        svc._cache_put("h1", "x")  # swallowed

    conn = sqlite3.connect(path)
    assert (objects(conn), rows(conn, owner.table)) == before
    conn.close()


def test_a_refused_rewrite_cache_warns_once_per_process(tmp_path, monkeypatch, caplog):
    path = tmp_path / "variant.db"
    conn = sqlite3.connect(path)
    INCOMPATIBLE[REWRITES]["question_hash_not_primary_key"](conn)
    conn.commit()
    conn.close()
    svc = _service(REWRITES, monkeypatch, path)
    monkeypatch.setattr(svc, "_refusal_warned", False)
    caplog.set_level(logging.DEBUG, logger=REWRITES.service)
    for _ in range(3):
        assert svc._cache_get("h1") is None
        svc._cache_put("h1", "x")
    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING and r.name == REWRITES.service]
    assert len(warnings) == 1
    assert "query_rewrites" in warnings[0].getMessage() and "refused" in warnings[0].getMessage()
