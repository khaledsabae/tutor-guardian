"""Work a test leaves running must finish on that test's own DB.

CI, 2026-10-08 (PR #93, run 37840203783): 4116 passed, 1 error —
test_sensitive_and_medication_facts_are_never_stored failed in SETUP with
`database is locked` at `PRAGMA journal_mode = WAL` in init_db().

The test before it asks a question with a child (test_remembered_facts_…),
and the answer hands the turn to child_memory.schedule_extraction:
fire-and-forget, on the module's own thread pool. The test returned with that
work still queued; db_path() resolves CONVERSATIONS_DB when the work runs, so
on a loaded machine it ran against the NEXT test's fresh file (seen locally
under CPU contention: an extraction submitted by one test opening the next
test's DB during its setup). A fresh file is still in rollback mode, and
switching it to WAL upgrades a read lock to a write lock — SQLite returns
SQLITE_BUSY at once there instead of calling the busy handler (an upgrade
could deadlock), so the 5 s timeout never applies: a write the leftover work
had in progress on that file failed the next test's init_db() immediately.

The fixture now waits for the work a test started before letting go of its DB.
"""
from __future__ import annotations

import threading
import time

import pytest

from app.db.init_db import db_path, get_conn
from app.services import child_memory
from tests.conversations_db_support import isolated_conversations_db


def test_work_a_test_leaves_running_finishes_on_that_tests_own_db():
    seen: list[str] = []

    def leftover():
        """An extraction in miniature: starts late, then writes."""
        time.sleep(0.3)
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            seen.append(str(db_path()))
            time.sleep(0.2)
        finally:
            conn.rollback()
            conn.close()

    first_mp = pytest.MonkeyPatch()
    try:
        with isolated_conversations_db(first_mp) as first:
            child_memory._EXECUTOR.submit(leftover)  # the test returns here
    finally:
        first_mp.undo()  # what pytest does next

    second_mp = pytest.MonkeyPatch()
    try:
        with isolated_conversations_db(second_mp) as second:  # the next test
            time.sleep(0.8)
    finally:
        second_mp.undo()

    assert second not in seen, "the leftover work wrote into the next test's DB"
    assert seen == [first]


def test_work_that_never_finishes_fails_its_own_test():
    release = threading.Event()
    mp = pytest.MonkeyPatch()
    try:
        with pytest.raises(pytest.fail.Exception, match=r"still running.*Event\.wait"):
            with isolated_conversations_db(mp, drain_timeout=0.2):
                child_memory._EXECUTOR.submit(release.wait, 10)
    finally:
        release.set()
        mp.undo()
