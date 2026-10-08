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
    return {(table, col) for table, col, _extra in ACTION_SOURCES}


def test_registry_covers_lessons_missions_and_followups():
    assert ("followups", "answered_at") in _sources()
    for col in ("started_at", "updated_at", "completed_at"):
        assert ("lesson_progress", col) in _sources()
    for col in ("assigned_at", "claimed_at", "confirmed_at"):
        assert ("child_missions", col) in _sources()
    # Family programs (v34) stay counted too.
    assert ("ramadan_marks", "created_at") in _sources()
    assert ("prayer_journeys", "created_at") in _sources()


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
