"""The per-test conversations DB (conftest's autouse `_temp_conversations_db`).

Every test gets a fresh SQLite file, and `db_path()` reads CONVERSATIONS_DB at
call time. Kept here, outside the fixture, so its behaviour across two
consecutive tests can itself be tested (test_background_work_isolation.py).

Work a test hands to a thread pool and does not wait for — child-memory
extraction after an answer, the LLM stream worker, `asyncio.to_thread` calls
still queued when the TestClient closed — resolves db_path() whenever it gets
to run. Left alone it can run after the test: against ops/conversations.db
once the env is restored, or against the NEXT test's fresh file, where a
write in progress fails that test's init_db() with "database is locked" (the
busy timeout does not apply to the WAL switch of a new file; CI, 2026-10-08).
So the DB is not let go until the work the test started has finished.
"""
from __future__ import annotations

import os
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager

import pytest

DRAIN_TIMEOUT_S = 20.0


def _describe(fn, args) -> str:
    # ai_gateway lanes submit `ctx.run, fn, ...`: name the function, not run.
    if getattr(fn, "__name__", "") == "run" and args and callable(args[0]):
        fn = args[0]
    return getattr(fn, "__qualname__", None) or repr(fn)


@contextmanager
def _track_pool_work(monkeypatch):
    """Record every future submitted to any ThreadPoolExecutor meanwhile
    (loop.run_in_executor and asyncio.to_thread go through submit too)."""
    started: list[tuple[Future, str]] = []
    real_submit = ThreadPoolExecutor.submit

    def submit(self, fn, /, *args, **kwargs):
        fut = real_submit(self, fn, *args, **kwargs)
        started.append((fut, _describe(fn, args)))
        return fut

    monkeypatch.setattr(ThreadPoolExecutor, "submit", submit)  # undone with the test
    yield started


def _drain(started: list[tuple[Future, str]], timeout: float, *, fail: bool = True) -> None:
    deadline = time.monotonic() + timeout
    while True:
        # A finishing job may submit more (to_thread from a draining task).
        pending = [(f, name) for f, name in list(started) if not f.done()]
        if not pending:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            pending[0][0].result(timeout=remaining)
        except Exception:  # noqa: BLE001 — its own failure is not ours to judge
            pass
    if not fail:
        return
    names = sorted({name for _, name in pending})
    pytest.fail(
        f"background work this test started is still running after {timeout:g}s: "
        f"{names} — it would run against the next test's DB. Wait for it in the "
        "test, or stop it (a blocked fake provider, an unset event).",
        pytrace=False,
    )


@contextmanager
def isolated_conversations_db(monkeypatch, drain_timeout: float = DRAIN_TIMEOUT_S):
    """One test's DB: created and initialised on entry; on exit, the work the
    test started is waited for, then the file is removed.

    `monkeypatch` is the test's own: pytest undoes it (restoring
    CONVERSATIONS_DB) only after this has exited.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("CONVERSATIONS_DB", path)  # resolved at call time by db_path()
    from app.db.init_db import init_db
    init_db()
    try:
        with _track_pool_work(monkeypatch) as started:
            try:
                yield path
            except BaseException:
                _drain(started, drain_timeout, fail=False)  # don't mask the real error
                raise
            _drain(started, drain_timeout)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
