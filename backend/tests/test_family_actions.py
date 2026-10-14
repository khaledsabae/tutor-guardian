"""The canonical family-action registry (نور والقناديل, Phase 0 «عدّاد صادق»).

The weekly funnel report and the upcoming /api/family/week must never
disagree about what lights a lantern: both import ACTION_SOURCES from
backend/app/services/family_actions.py. These tests pin the registry's
contents and prove the report's get_action_events counts a follow-up
answered in-window through the shared list.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.services.family_actions import ACTION_SOURCES

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _report_module():
    spec = importlib.util.spec_from_file_location(
        "weekly_funnel_report", _REPO_ROOT / "ops" / "scripts" / "weekly_funnel_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sources() -> set[tuple[str, str]]:
    return {(src.table, src.column) for src in ACTION_SOURCES}


def test_registry_covers_lessons_missions_and_followups():
    assert ("followups", "answered_at") in _sources()
    for col in ("started_at", "updated_at", "completed_at"):
        assert ("lesson_progress", col) in _sources()
    for col in ("assigned_at", "claimed_at", "confirmed_at"):
        assert ("child_missions", col) in _sources()
    # Family programs (v34) stay counted too.
    assert ("ramadan_marks", "created_at") in _sources()
    assert ("prayer_journeys", "created_at") in _sources()
    # A step of the weekly plan ticked (Phase 3).
    assert ("weekly_plan_marks", "created_at") in _sources()


def test_every_source_names_its_lantern_kind():
    """/api/family/week labels each act by kind; the app draws the lantern by it."""
    kinds = {src.kind for src in ACTION_SOURCES}
    assert kinds == {"lesson", "habit", "mission", "challenge", "ramadan_mark",
                     "prayer_journey", "followup", "plan_tick"}
    by_source = {(src.table, src.column): src.kind for src in ACTION_SOURCES}
    assert by_source[("weekly_plan_marks", "created_at")] == "plan_tick"
    assert by_source[("followups", "answered_at")] == "followup"


def test_worship_acts_are_declared_on_the_registry_not_hidden_in_a_query():
    """The plan's rule — worship never lights the weekly lanterns — is a
    property of each source, so the counter and any later reader see it."""
    worship = {src.table: src.worship for src in ACTION_SOURCES if src.worship}
    assert worship["ramadan_marks"] == worship["prayer_journeys"] == "ALL"
    assert "prayer_journey" in worship["child_missions"]
    assert "worship" in worship["habits_value_events"]
    assert "worship_" in worship["weekly_plan_marks"]
    assert "lesson_progress" not in worship and "followups" not in worship


def test_registry_never_lights_lanterns_for_worship_acts():
    """Standing rule: adhkar and quran tables never light lantern counters —
    worship is between a family and Allah, not a number in a week."""
    worship = {"family_adhkar", "adhkar_events", "quran_sessions", "quran_progress"}
    assert not {table for table, _col in _sources()} & worship


def test_report_counts_a_followup_answered_in_window(tmp_path):
    report = _report_module()
    db = tmp_path / "minimal.db"
    now = datetime.utcnow()
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE followups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            child_id    INTEGER NOT NULL,
            answered_at TEXT
        );
        CREATE TABLE lesson_progress (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            started_at  TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO followups (device_id, child_id, answered_at) VALUES (?, ?, ?)",
        [
            # In-window, ISO-8601 with a "T": the format followups actually writes.
            ("dev-answer", 1, (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")),
            # Long out of window.
            ("dev-old", 1, "2026-01-01T08:00:00+00:00"),
            # Never answered: must be skipped, not crash.
            ("dev-pending", 1, None),
        ],
    )
    conn.execute(
        "INSERT INTO lesson_progress (device_id, started_at) VALUES (?, ?)",
        ("dev-lesson", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

    events = report.get_action_events(db, since=now - timedelta(days=7))
    devices = {device for device, _ts in events}
    assert "dev-answer" in devices        # the new source, counted
    assert "dev-lesson" in devices        # the lift kept the old sources
    assert "dev-old" not in devices
    assert "dev-pending" not in devices


def test_report_counts_a_plan_tick(tmp_path):
    """A family whose only act this week was ticking a plan step is active —
    the report and the lanterns read the same registry."""
    report = _report_module()
    db = tmp_path / "plan_tick.db"
    now = datetime.utcnow()
    conn = sqlite3.connect(db)
    # Copied from backend/app/db/init_db.py v36 (_CREATE_WEEKLY_PLAN_MARKS),
    # the schema production runs since Phase 0 deployed.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS weekly_plan_marks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            child_id    INTEGER NOT NULL,
            item_id     TEXT NOT NULL,
            marked_on   TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (device_id, child_id, item_id, marked_on),
            FOREIGN KEY (child_id) REFERENCES child_profiles(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        "INSERT INTO weekly_plan_marks (device_id, child_id, item_id, marked_on, created_at) "
        "VALUES ('dev-tick', 1, 'sleep_school_1', ?, ?)",
        ((now - timedelta(days=1)).date().isoformat(),
         (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    events = report.get_action_events(db, since=now - timedelta(days=7))
    assert {device for device, _ts in events} == {"dev-tick"}


def test_report_skips_missing_tables_and_columns(tmp_path):
    """A store without the followups table must still report lesson actions —
    the registry degrades per source, never fatally."""
    report = _report_module()
    db = tmp_path / "no_followups.db"
    now = datetime.utcnow()
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE lesson_progress (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "device_id TEXT NOT NULL, started_at TEXT)")
    conn.execute(
        "INSERT INTO lesson_progress (device_id, started_at) VALUES (?, ?)",
        ("dev-only", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    events = report.get_action_events(db, since=now - timedelta(days=7))
    assert {device for device, _ts in events} == {"dev-only"}
