"""Schema v36 — the honest weekly counter's shared migration (نور والقناديل).

One migration adds both objects Phase 0 needs:
* `followups.source` — nullable TEXT, no backfill (old rows keep NULL).
* `weekly_plan_marks` — one «تمّ» per child per plan item per day.

Style follows test_programs_birth_month.py: build the previous shape, run
init_db() (twice, for idempotence), assert by effect.
"""
from __future__ import annotations

import sqlite3

from app.db.init_db import SCHEMA_VERSION, init_db

_V35_FOLLOWUPS = """
CREATE TABLE followups (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id         TEXT NOT NULL,
    child_id          INTEGER NOT NULL,
    strategy          TEXT NOT NULL,
    topic             TEXT,
    due_at            TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    answered_at       TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _columns(db, table: str) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_schema_version_is_36():
    assert SCHEMA_VERSION == 36


def test_fresh_db_gets_the_column_and_the_table():
    init_db()
    from app.db.init_db import db_path
    db = db_path()
    assert "source" in _columns(db, "followups")
    marks = _columns(db, "weekly_plan_marks")
    assert {"id", "device_id", "child_id", "item_id", "marked_on"} <= marks


def test_v35_db_is_upgraded_in_place():
    """A database at the previous version (no source column, no marks table)
    is migrated up without losing its rows; existing followups keep source
    = NULL. The autouse fixture hands every test a fully-migrated db, so this
    rewinds it to the v35 shape first."""
    from app.db.init_db import db_path
    db = db_path()
    conn = sqlite3.connect(db)
    conn.executescript(
        "DROP TABLE weekly_plan_marks;"
        "DROP TABLE followups;"
        + _V35_FOLLOWUPS
        + "UPDATE schema_version SET version = 35;"
    )
    conn.execute(
        "INSERT INTO followups (device_id, child_id, strategy, due_at) "
        "VALUES ('d', 1, 'prayer_calm', '2026-10-01')")
    conn.commit()
    conn.close()

    init_db()
    conn = sqlite3.connect(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(followups)")}
        row = conn.execute("SELECT device_id, source FROM followups").fetchone()
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        has_marks = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='weekly_plan_marks'"
        ).fetchone()
    finally:
        conn.close()
    assert "source" in cols
    assert tuple(row) == ("d", None)      # no backfill: the old row stays NULL
    assert version == 36
    assert has_marks


def test_migration_is_idempotent_and_marks_are_unique_per_day():
    init_db()
    init_db()  # re-run: additive steps must be safe twice
    from app.db.init_db import db_path
    db = db_path()
    assert "source" in _columns(db, "followups")

    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO weekly_plan_marks (device_id, child_id, item_id, marked_on) "
            "VALUES ('d', 1, 'action_calm_voice', '2026-10-09')")
        # Same child, same item, same day: the second «تمّ» is the same mark.
        try:
            conn.execute(
                "INSERT INTO weekly_plan_marks (device_id, child_id, item_id, marked_on) "
                "VALUES ('d', 1, 'action_calm_voice', '2026-10-09')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("unique(device,child,item,day) was not enforced")
        # A different day is a different mark.
        conn.execute(
            "INSERT INTO weekly_plan_marks (device_id, child_id, item_id, marked_on) "
            "VALUES ('d', 1, 'action_calm_voice', '2026-10-10')")
        n = conn.execute("SELECT COUNT(*) FROM weekly_plan_marks").fetchone()[0]
    finally:
        conn.close()
    assert n == 2
