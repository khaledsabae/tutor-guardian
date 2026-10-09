"""The canonical registry of meaningful family actions («عدّاد صادق»).

One list decides what counts as a parenting action in a family's week — the
weekly funnel report (ops/scripts/weekly_funnel_report.py) and the upcoming
/api/family/week lantern counter both import it, so the report and the
lanterns can never disagree.

Standing rules (نور والقناديل plan, Phase 0):
* Worship acts (adhkar, quran) NEVER light lantern counters. The lanterns are
  for parenting acts only: a lesson, a question (at most one a day), a
  follow-up answered, a mission confirmed, a weekly-plan step taken.
* Du'as are answered only by their id from the guarded `family_adhkar` bank,
  never free text — no ayah is ever used as an app metaphor.

Semantics are lifted verbatim from the funnel report: (table, timestamp
column, extra WHERE). Timestamps go through SQLite's datetime() because the
tables disagree on format. Tables or columns missing from a database are
skipped by the reader, not fatal.
"""
from __future__ import annotations

ACTION_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("lesson_progress", "started_at", ""),
    ("lesson_progress", "updated_at", ""),
    ("lesson_progress", "completed_at", ""),
    ("habits_value_events", "created_at", ""),
    ("child_missions", "assigned_at", ""),
    ("child_missions", "claimed_at", ""),
    ("child_missions", "confirmed_at", ""),
    ("child_challenges", "started_at", ""),
    # Family programs (backend schema v34): a Ramadan «تمّ» and a Prayer
    # Journey started are parenting acts. The journey's tasks are already
    # child_missions rows above. Absent tables are skipped.
    ("ramadan_marks", "created_at", ""),
    ("prayer_journeys", "created_at", ""),
    # A follow-up answered (نور والقناديل, Phase 0): the parent came back and
    # reported whether the advice worked — the truest parenting act there is.
    ("followups", "answered_at", ""),
)
