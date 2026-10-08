"""Additive telemetry migrations on synthetic, isolated SQLite fixtures only."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import importlib
import importlib.util
import multiprocessing
import sqlite3

import pytest

from app.services import ai_gateway


LEGACY_SQL = """CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')),
    provider TEXT, model TEXT, latency_ms INTEGER,
    prompt_tokens INTEGER, completion_tokens INTEGER,
    streamed INTEGER, ok INTEGER
)"""
NAMESPACE = "llm_telemetry"


def modules():
    name = "app.db.migrations.runner"
    assert importlib.util.find_spec(name) is not None, "numbered migration runner is missing"
    return importlib.import_module(name), importlib.import_module(
        "app.db.migrations.telemetry_0001_llm_calls"
    )


def migrate(conn):
    runner, migration = modules()
    return runner.apply_migrations(conn, NAMESPACE, (migration.MIGRATION,))


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "synthetic.db")
    yield c
    c.close()


def legacy(conn, *, extensions=False):
    conn.execute(LEGACY_SQL)
    if extensions:
        conn.execute("ALTER TABLE llm_calls ADD COLUMN budget_extension TEXT")
        conn.execute("CREATE INDEX fixture_provider_index ON llm_calls(provider, budget_extension)")
    conn.execute(
        "INSERT INTO llm_calls(ts,provider,model,latency_ms,prompt_tokens,completion_tokens,streamed,ok) "
        "VALUES ('2026-01-02 03:04:05','fixture','synthetic',17,NULL,9,1,0)"
    )
    if extensions:
        conn.execute("UPDATE llm_calls SET budget_extension = 'keep-exact-value'")
    conn.commit()


def snapshot(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_xinfo(llm_calls)")]
    return (
        cols,
        conn.execute("SELECT * FROM llm_calls ORDER BY id").fetchall(),
        conn.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='llm_calls'").fetchall(),
        conn.execute("SELECT seq FROM sqlite_sequence WHERE name='llm_calls'").fetchall(),
    )


def test_empty_store_has_numbered_checksummed_ledger(conn):
    runner, migration = modules()
    assert migrate(conn) == (1,)
    assert not conn.in_transaction
    assert conn.execute(
        "SELECT version,name,checksum FROM schema_migrations WHERE namespace=?", (NAMESPACE,)
    ).fetchall() == [(1, "llm_calls", migration.MIGRATION.checksum)]
    assert len(migration.MIGRATION.checksum) == 64
    assert runner.apply_migrations(conn, NAMESPACE, (migration.MIGRATION,)) == ()


@pytest.mark.parametrize("extensions", [False, True])
def test_real_legacy_base_shape_keeps_columns_indexes_values_and_ids(conn, extensions):
    legacy(conn, extensions=extensions)
    cols, rows, indexes, sequence = snapshot(conn)
    migrate(conn)
    quoted = ",".join('"' + c + '"' for c in cols)
    assert conn.execute(f"SELECT {quoted} FROM llm_calls ORDER BY id").fetchall() == rows
    assert snapshot(conn)[2:] == (indexes, sequence)
    assert conn.execute("SELECT tier,route_reason FROM llm_calls").fetchall() == [(None, None)]


def test_current_shape_adoption_preserves_extensions_and_is_a_true_noop_on_repeat(conn):
    legacy(conn, extensions=True)
    conn.execute("ALTER TABLE llm_calls ADD COLUMN tier TEXT")
    conn.execute("ALTER TABLE llm_calls ADD COLUMN route_reason TEXT")
    conn.execute("UPDATE llm_calls SET tier='fixture-tier',route_reason='fixture-reason'")
    conn.commit()
    before = snapshot(conn)
    migrate(conn)
    assert snapshot(conn) == before
    schema = conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall()
    ledger = conn.execute("SELECT * FROM schema_migrations").fetchall()
    total = conn.total_changes
    assert migrate(conn) == ()
    assert conn.total_changes == total
    assert conn.execute("SELECT * FROM schema_migrations").fetchall() == ledger
    assert conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall() == schema


def test_preserves_user_version_core_stamp_and_connection_policy(conn):
    conn.execute("PRAGMA user_version=35")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=4321")
    conn.execute("CREATE TABLE schema_version(version INTEGER)")
    conn.execute("INSERT INTO schema_version VALUES(35)")
    conn.commit()
    policy = [conn.execute(f"PRAGMA {p}").fetchone() for p in ("user_version", "foreign_keys", "busy_timeout", "journal_mode")]
    migrate(conn)
    assert [conn.execute(f"PRAGMA {p}").fetchone() for p in ("user_version", "foreign_keys", "busy_timeout", "journal_mode")] == policy
    assert conn.execute("SELECT version FROM schema_version").fetchall() == [(35,)]


def test_failure_after_first_alter_rolls_back_column_and_ledger_then_retries(conn):
    legacy(conn)
    before = snapshot(conn)
    def deny_second_column(action, first, second, *_):
        if action == sqlite3.SQLITE_ALTER_TABLE and first == "main" and second == "llm_calls":
            deny_second_column.calls += 1
            if deny_second_column.calls == 2:
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    deny_second_column.calls = 0
    conn.set_authorizer(deny_second_column)
    with pytest.raises(sqlite3.DatabaseError):
        migrate(conn)
    conn.set_authorizer(None)
    assert snapshot(conn) == before
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='schema_migrations'").fetchall() == []
    assert migrate(conn) == (1,)


def test_sqlite_interrupt_after_first_alter_rolls_back_adapter_work(conn, monkeypatch):
    legacy(conn)
    before = snapshot(conn)
    database = conn.execute("PRAGMA database_list").fetchone()[2]
    monkeypatch.setattr(ai_gateway, "_telemetry_schema_ready", False)
    def interrupt_second_alter(action, first, second, *_):
        if action == sqlite3.SQLITE_ALTER_TABLE and second == "llm_calls":
            interrupt_second_alter.calls += 1
            if interrupt_second_alter.calls == 2:
                conn.set_progress_handler(lambda: 1, 1)
        return sqlite3.SQLITE_OK
    interrupt_second_alter.calls = 0
    conn.set_authorizer(interrupt_second_alter)
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        ai_gateway._ensure_telemetry_schema(conn)
    # A permanently cancelling callback cannot be cleared behind the caller's
    # back. Discard the unusable connection and verify the persisted state.
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with sqlite3.connect(database) as fresh:
        assert snapshot(fresh) == before
        assert fresh.execute("SELECT name FROM sqlite_master WHERE name='schema_migrations'").fetchall() == []
        fresh.execute("BEGIN IMMEDIATE")  # no leaked writer lock
        fresh.rollback()


@pytest.mark.parametrize("progress_interval", [1, 2, 3, 4, 5])
def test_interrupted_begin_releases_owned_writer_lock_without_schema_changes(tmp_path, progress_interval):
    path = tmp_path / "interrupted-acquisition.db"
    c = sqlite3.connect(path)
    c.set_progress_handler(lambda: int(c.in_transaction), progress_interval)
    try:
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            migrate(c)
        # A separate real connection must obtain the writer lock immediately;
        # checking only schema contents misses an interrupted open transaction.
        with sqlite3.connect(path, timeout=0) as next_startup:
            next_startup.execute("BEGIN IMMEDIATE")
            assert next_startup.execute("SELECT name FROM sqlite_master").fetchall() == []
            next_startup.rollback()
        # Cleanup may close a connection when its persistent callback prevents
        # ROLLBACK, but must never leave a usable connection owning work.
        try:
            assert not c.in_transaction
        except sqlite3.ProgrammingError:
            pass
    finally:
        c.close()


@pytest.mark.parametrize("cancellation", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt])
def test_error_or_cancellation_rolls_back_all_owned_work(conn, cancellation):
    runner, mod = modules()
    def fail(context):
        context.execute("CREATE TABLE failure_fixture(value TEXT)")
        raise cancellation("fixture cancellation")
    bad = replace(mod.MIGRATION, apply=fail)
    with pytest.raises(cancellation):
        runner.apply_migrations(conn, NAMESPACE, (bad,))
    assert not conn.in_transaction
    assert conn.execute("SELECT name FROM sqlite_master WHERE name IN ('schema_migrations','failure_fixture')").fetchall() == []


def test_executescript_cannot_implicitly_commit_a_migration(conn):
    runner, mod = modules()
    def accidental_script(context):
        context.execute("CREATE TABLE failure_fixture(value TEXT)")
        context.executescript("CREATE TABLE incorrectly_committed(value TEXT);")
    bad = replace(mod.MIGRATION, apply=accidental_script)
    with pytest.raises((AttributeError, runner.MigrationError)):
        runner.apply_migrations(conn, NAMESPACE, (bad,))
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


@pytest.mark.parametrize("sql", ["COMMIT", "ROLLBACK", "DROP TABLE failure_fixture", "ALTER TABLE failure_fixture RENAME TO renamed", "PRAGMA user_version=99"])
def test_additive_context_refuses_transaction_control_destructive_ddl_and_pragma_writes(conn, sql):
    runner, mod = modules()
    def unsafe(context):
        context.execute("CREATE TABLE failure_fixture(value TEXT)")
        context.execute(sql)
    with pytest.raises(runner.MigrationError):
        runner.apply_migrations(conn, NAMESPACE, (replace(mod.MIGRATION, apply=unsafe),))
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_rejects_caller_transaction_without_committing_or_rolling_it_back(conn):
    runner, _ = modules()
    conn.execute("CREATE TABLE caller_work(value TEXT)")
    conn.execute("INSERT INTO caller_work VALUES('caller-owned')")
    with pytest.raises(runner.MigrationError):
        migrate(conn)
    assert conn.in_transaction
    conn.rollback()
    assert conn.execute("SELECT * FROM caller_work").fetchall() == []


@pytest.mark.parametrize("drift", ["checksum", "future", "name"])
def test_ledger_drift_or_unknown_version_refuses_without_writes(conn, drift):
    runner, _ = modules()
    migrate(conn)
    if drift == "future":
        conn.execute("INSERT INTO schema_migrations(namespace,version,name,checksum) VALUES(?,99,'future',?)", (NAMESPACE, "f" * 64))
    else:
        conn.execute(f"UPDATE schema_migrations SET {drift}=? WHERE namespace=?", ("0" * 64 if drift == "checksum" else "other", NAMESPACE))
    conn.commit()
    before = conn.iterdump()
    before = list(before)
    with pytest.raises(runner.MigrationError):
        migrate(conn)
    assert list(conn.iterdump()) == before


@pytest.mark.parametrize("shape", ["missing_core", "bad_core_type", "bad_extension_type", "view"])
def test_incompatible_live_shape_is_refused_without_ledger_or_repair(conn, shape):
    runner, _ = modules()
    if shape == "view":
        conn.execute("CREATE VIEW llm_calls AS SELECT 1 AS id")
    else:
        sql = LEGACY_SQL.replace("provider TEXT", "other TEXT") if shape == "missing_core" else LEGACY_SQL.replace("prompt_tokens INTEGER", "prompt_tokens TEXT") if shape == "bad_core_type" else LEGACY_SQL
        conn.execute(sql)
        if shape == "bad_extension_type":
            conn.execute("ALTER TABLE llm_calls ADD COLUMN tier INTEGER")
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(runner.MigrationError):
        migrate(conn)
    assert list(conn.iterdump()) == before


def test_post_adoption_schema_drift_is_checked_even_with_valid_checksum(conn):
    runner, _ = modules()
    migrate(conn)
    conn.execute("ALTER TABLE llm_calls RENAME COLUMN route_reason TO unrelated_extension")
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(runner.MigrationError):
        migrate(conn)
    assert list(conn.iterdump()) == before


@pytest.mark.parametrize("bad", ["checksum", "zero", "gap", "duplicate"])
def test_invalid_registry_refuses_before_any_schema_work(conn, bad):
    runner, mod = modules()
    migrations = (replace(mod.MIGRATION, checksum="not-a-sha"),) if bad == "checksum" else (replace(mod.MIGRATION, number=0),) if bad == "zero" else (replace(mod.MIGRATION, number=2),) if bad == "gap" else (mod.MIGRATION, mod.MIGRATION)
    with pytest.raises(runner.MigrationError):
        runner.apply_migrations(conn, NAMESPACE, migrations)
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_other_ledger_namespace_is_preserved(conn):
    migrate(conn)
    conn.execute("INSERT INTO schema_migrations(namespace,version,name,checksum) VALUES('future_budget',9,'unrelated',?)", ("e" * 64,))
    conn.commit()
    before = conn.execute("SELECT * FROM schema_migrations WHERE namespace='future_budget'").fetchall()
    assert migrate(conn) == ()
    assert conn.execute("SELECT * FROM schema_migrations WHERE namespace='future_budget'").fetchall() == before


def test_incompatible_existing_ledger_is_preserved_and_refused(conn):
    runner, _ = modules()
    conn.execute("CREATE TABLE schema_migrations(namespace TEXT,version INTEGER,name TEXT,checksum TEXT)")
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(runner.MigrationError):
        migrate(conn)
    assert list(conn.iterdump()) == before


def test_ledger_with_a_different_composite_key_is_not_adopted(conn):
    runner, _ = modules()
    conn.execute("CREATE TABLE schema_migrations(namespace TEXT NOT NULL,version INTEGER NOT NULL,name TEXT NOT NULL,checksum TEXT NOT NULL,applied_at TEXT NOT NULL DEFAULT 'fixture',extra TEXT NOT NULL DEFAULT 'fixture',PRIMARY KEY(namespace,version,extra))")
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(runner.MigrationError):
        migrate(conn)
    assert list(conn.iterdump()) == before


@pytest.mark.parametrize("shape", ["descending_key", "without_rowid"])
def test_non_rowid_primary_key_is_refused_instead_of_breaking_unchanged_logger(conn, shape):
    runner, _ = modules()
    sql = LEGACY_SQL.replace("PRIMARY KEY AUTOINCREMENT", "PRIMARY KEY DESC") if shape == "descending_key" else LEGACY_SQL.replace(" AUTOINCREMENT", "") + " WITHOUT ROWID"
    conn.execute(sql)
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(runner.MigrationError):
        migrate(conn)
    assert list(conn.iterdump()) == before


def test_adapter_initializes_two_databases_and_replaced_file_despite_old_ready_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_gateway, "_telemetry_schema_ready", True)
    for path in [tmp_path / "first.db", tmp_path / "second.db", tmp_path / "first.db"]:
        if path.exists():
            path.unlink()
        with sqlite3.connect(path) as c:
            ai_gateway._ensure_telemetry_schema(c)
            assert c.execute("SELECT version FROM schema_migrations WHERE namespace=?", (NAMESPACE,)).fetchall() == [(1,)]


def test_adapter_logging_and_monthly_budget_keep_existing_contract_and_paths(tmp_path, monkeypatch):
    path = tmp_path / "telemetry.db"
    monkeypatch.setattr(ai_gateway, "_TELEMETRY_DB", path)
    monkeypatch.setattr(ai_gateway, "_telemetry_schema_ready", True)
    from app.db.init_db import db_path
    conversation_path = db_path()
    ai_gateway._log_call("fixture-provider", "fixture-model", 12, 7, 3, True, False, "fixture-tier", "fixture-reason")
    assert ai_gateway._monthly_tokens_used("fixture-provider") == 10
    assert ai_gateway._TELEMETRY_DB == path and db_path() == conversation_path
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT provider,model,latency_ms,prompt_tokens,completion_tokens,streamed,ok,tier,route_reason FROM llm_calls").fetchall() == [("fixture-provider", "fixture-model", 12, 7, 3, 1, 0, "fixture-tier", "fixture-reason")]
        assert c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone() == (1,)


def _startup_worker(path, barrier, queue, worker_id):
    try:
        with sqlite3.connect(path, timeout=10) as c:
            barrier.wait(timeout=8)
            ai_gateway._ensure_telemetry_schema(c)
            c.execute("INSERT INTO llm_calls(provider,model) VALUES('fixture-worker',?)", (str(worker_id),))
        queue.put("ok")
    except BaseException as error:
        queue.put(type(error).__name__ + ": " + str(error))


def test_two_real_processes_start_concurrently_and_apply_exactly_once(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    path = str(tmp_path / "concurrent.db")
    barrier, queue = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_startup_worker, args=(path, barrier, queue, i)) for i in range(2)]
    try:
        for worker in workers:
            worker.start()
        results = [queue.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=5)
        assert results == ["ok", "ok"]
        assert [w.exitcode for w in workers] == [0, 0]
        with sqlite3.connect(path) as c:
            assert c.execute("SELECT COUNT(*) FROM schema_migrations WHERE namespace=?", (NAMESPACE,)).fetchone() == (1,)
            assert c.execute("SELECT model FROM llm_calls ORDER BY model").fetchall() == [("0",), ("1",)]
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        queue.close()
