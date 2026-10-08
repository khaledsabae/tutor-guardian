"""The runner's lock-free fast path for an already-migrated database.

An open that finds the namespace's ledger complete and every live shape valid
answers from a deferred read transaction (a WAL snapshot). It never queues
behind the writer lock. Anything else (a pending migration, a changed
checksum, a shape that no longer validates) still goes through BEGIN
IMMEDIATE, which decides and raises. Every database here is production's
copied sessions.db DDL.
"""
from __future__ import annotations

import importlib
import multiprocessing
import sqlite3
import threading
import time

import pytest

from app.db.migrations.runner import MigrationError, apply_migrations
from tests.prod_schema_support import build_prod, ledger, objects, rows

OWNERS = {
    "sessions": "app.db.migrations.sessions_0001_baseline",
    "tafsir_cache": "app.db.migrations.tafsir_cache_0001_baseline",
    "bahouth_cache": "app.db.migrations.bahouth_cache_0001_baseline",
    "query_rewrites": "app.db.migrations.query_rewrites_0001_baseline",
}
TELEMETRY = ("app.db.migrations.telemetry_0001_llm_calls",
             "app.db.migrations.telemetry_0002_usage_estimated")


def registry(namespace: str) -> tuple:
    if namespace == "llm_telemetry":
        return tuple(importlib.import_module(m).MIGRATION for m in TELEMETRY)
    return (importlib.import_module(OWNERS[namespace]).MIGRATION,)


NAMESPACES = [*OWNERS, "llm_telemetry"]


def no_wait(path) -> sqlite3.Connection:
    """A connection that fails at once, instead of waiting, if it needs the writer lock."""
    conn = sqlite3.connect(path, timeout=0)
    conn.execute("PRAGMA busy_timeout = 0")
    return conn


class Writer:
    """Another connection holding the writer lock of a WAL database."""

    def __init__(self, path):
        self.conn = sqlite3.connect(path, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode = WAL")

    def __enter__(self):
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.execute("INSERT INTO llm_calls(provider) VALUES('held-writer')")
        return self

    def __exit__(self, *exc):
        self.conn.execute("ROLLBACK")
        self.conn.close()


@pytest.fixture
def migrated(tmp_path):
    path = tmp_path / "prod_sessions.db"
    conn = build_prod(path)
    conn.execute("PRAGMA journal_mode = WAL")
    for namespace in OWNERS:
        apply_migrations(conn, namespace, registry(namespace))
    conn.close()
    return path


@pytest.mark.parametrize("namespace", NAMESPACES)
def test_validated_open_does_not_wait_for_a_held_writer(migrated, namespace):
    conn = no_wait(migrated)
    try:
        with Writer(migrated):
            assert apply_migrations(conn, namespace, registry(namespace)) == ()
        assert not conn.in_transaction
        assert conn.total_changes == 0
    finally:
        conn.close()


@pytest.mark.parametrize("namespace", list(OWNERS))
def test_pending_migration_still_takes_the_writer_lock(tmp_path, namespace):
    path = tmp_path / "prod_sessions.db"
    build_prod(path).close()
    conn = no_wait(path)
    try:
        with Writer(path):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                apply_migrations(conn, namespace, registry(namespace))
        assert not conn.in_transaction
        assert ledger(conn, namespace) == []
        assert apply_migrations(conn, namespace, registry(namespace)) == (1,)
    finally:
        conn.close()


def test_a_shape_broken_after_adoption_is_never_answered_from_the_snapshot(migrated):
    conn = sqlite3.connect(migrated)
    conn.execute("DROP INDEX idx_tafsir_cache_lookup")
    conn.commit()
    conn.close()
    conn = no_wait(migrated)
    try:
        # The fast path declines, so the authoritative path needs the lock...
        with Writer(migrated):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                apply_migrations(conn, "tafsir_cache", registry("tafsir_cache"))
        # ...and, given it, refuses rather than guessing.
        with pytest.raises(MigrationError):
            apply_migrations(conn, "tafsir_cache", registry("tafsir_cache"))
        assert not conn.in_transaction
    finally:
        conn.close()


def test_a_changed_checksum_is_refused_by_the_authoritative_path(migrated):
    conn = sqlite3.connect(migrated)
    conn.execute("UPDATE schema_migrations SET checksum=? WHERE namespace='sessions'", ("0" * 64,))
    conn.commit()
    try:
        with pytest.raises(MigrationError, match="checksum"):
            apply_migrations(conn, "sessions", registry("sessions"))
        assert not conn.in_transaction
    finally:
        conn.close()


def test_fast_path_still_refuses_a_caller_owned_transaction(migrated):
    conn = sqlite3.connect(migrated)
    try:
        conn.execute("BEGIN")
        with pytest.raises(MigrationError, match="caller-owned"):
            apply_migrations(conn, "sessions", registry("sessions"))
        assert conn.in_transaction  # the caller's transaction is left alone
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def test_query_rewrite_hit_is_served_while_another_writer_holds_the_lock(migrated, monkeypatch):
    """A pure read used to queue for busy_timeout (5 s) and then return None."""
    from app.services import query_rewriter
    monkeypatch.setattr(query_rewriter, "_CACHE_DB", migrated)
    seed = sqlite3.connect(migrated)
    seed.execute("INSERT INTO query_rewrites(question_hash,rewritten,redacted) VALUES('seed','كلمات',1)")
    seed.commit()
    seed.close()
    with Writer(migrated):
        started = time.perf_counter()
        assert query_rewriter._cache_get("seed") == "كلمات"
        assert time.perf_counter() - started < 2.0


def test_tafsir_miss_does_not_wait_for_a_held_writer(migrated, monkeypatch):
    from app.services import tafsir_service
    monkeypatch.setattr(tafsir_service, "_TELEMETRY_DB", migrated)
    monkeypatch.setattr(tafsir_service, "TAFSIR_CACHE_ENABLED", True)
    with Writer(migrated):
        started = time.perf_counter()
        assert tafsir_service._cache_get(999, 1, "absent") is None
        assert time.perf_counter() - started < 2.0


def _first_open_worker(path, barrier, queue):
    try:
        barrier.wait(timeout=20)
        for namespace in NAMESPACES:
            conn = sqlite3.connect(path, timeout=30)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 30000")
            try:
                apply_migrations(conn, namespace, registry(namespace))
            finally:
                conn.close()
        queue.put("ok")
    except BaseException as error:  # noqa: BLE001 — reported to the parent
        queue.put(f"{type(error).__name__}: {error}")


def test_six_processes_first_open_concurrently_and_apply_each_once(tmp_path):
    path = tmp_path / "prod_sessions.db"
    conn = build_prod(path)
    conn.execute("PRAGMA journal_mode = WAL")
    before = objects(conn), {t: rows(conn, t) for t in OWNERS}
    conn.close()

    ctx = multiprocessing.get_context("spawn")
    barrier, queue = ctx.Barrier(6), ctx.Queue()
    workers = [ctx.Process(target=_first_open_worker, args=(str(path), barrier, queue))
               for _ in range(6)]
    try:
        for worker in workers:
            worker.start()
        results = [queue.get(timeout=120) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
        assert results == ["ok"] * 6
        assert [w.exitcode for w in workers] == [0] * 6
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        queue.close()

    conn = sqlite3.connect(path)
    try:
        assert (objects(conn), {t: rows(conn, t) for t in OWNERS}) == before
        for namespace in NAMESPACES:
            assert [r[0] for r in ledger(conn, namespace)] == list(
                range(1, len(registry(namespace)) + 1))
    finally:
        conn.close()
