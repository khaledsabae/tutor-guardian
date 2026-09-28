"""Habit streak with the weekly shield, and the 7-day strip (UX-3, §3.2–3.3)."""
import sqlite3
from datetime import date, timedelta

from app.services.habit_streak import compute_streak, week_strip

# 2026-09-24 is a Thursday; its ISO week runs Mon 21 → Sun 27.
THU = date(2026, 9, 24)


def _days(*offsets):
    return {THU - timedelta(days=o) for o in offsets}


def test_no_effort_no_streak():
    assert compute_streak(set(), THU) == {
        "days": 0, "today_active": False, "shield_used_this_week": False,
    }


def test_consecutive_days_count_including_today():
    s = compute_streak(_days(0, 1, 2), THU)
    assert s["days"] == 3 and s["today_active"] is True
    assert s["shield_used_this_week"] is False


def test_empty_today_does_not_break_or_spend_the_shield():
    s = compute_streak(_days(1, 2, 3), THU)
    assert s["days"] == 3 and s["today_active"] is False
    assert s["shield_used_this_week"] is False


def test_one_gap_a_week_is_forgiven_and_not_counted():
    # Thu, Wed active; Tue empty (shielded); Mon active.
    s = compute_streak(_days(0, 1, 3), THU)
    assert s["days"] == 3
    assert s["shield_used_this_week"] is True


def test_two_gaps_in_one_week_end_the_run():
    # Thu active; Wed + Tue empty → run is just today.
    assert compute_streak(_days(0, 3, 4), THU)["days"] == 1


def test_one_gap_in_each_week_keeps_a_long_run():
    # 20 days back with one empty day in each of three different weeks.
    active = _days(*[o for o in range(20) if o not in (2, 9, 16)])
    assert compute_streak(active, THU)["days"] == 17


def test_trailing_forgiven_day_is_not_reported_as_used():
    # Only today active; yesterday (same week) empty → forgiven, then a
    # second empty day ends the run. Nothing was bridged, so not "used".
    s = compute_streak(_days(0), THU)
    assert s["days"] == 1
    assert s["shield_used_this_week"] is False


def _conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE habits_value_events (id INTEGER PRIMARY KEY, device_id TEXT,"
        " child_id INTEGER, habit_name TEXT, status TEXT, created_at TEXT)"
    )
    return c


def test_week_strip_aligns_days_and_latest_record_wins():
    c = _conn()
    rows = [
        ("صلاة الفجر", "missed", "2026-09-24 06:00:00"),
        ("صلاة الفجر", "completed", "2026-09-24 07:00:00"),  # later wins
        ("صلاة الفجر", "partially", "2026-09-18 07:00:00"),  # oldest strip day
        ("الصدق", "completed", "2026-09-17 07:00:00"),       # outside the window
        ("الصدق", "completed", "2026-09-22 07:00:00"),
    ]
    for name, st, ts in rows:
        c.execute(
            "INSERT INTO habits_value_events (device_id, child_id, habit_name, status, created_at)"
            " VALUES ('d', 1, ?, ?, ?)", (name, st, ts),
        )
    dates, strip = week_strip(c, "d", 1, THU)
    assert dates == [f"2026-09-{d}" for d in range(18, 25)]
    assert strip["صلاة الفجر"] == ["partially", None, None, None, None, None, "completed"]
    assert strip["الصدق"] == [None, None, None, None, "completed", None, None]


def test_four_week_rates_split_current_and_previous_windows():
    from app.services.habit_streak import four_week_rates

    c = _conn()
    rows = [
        ("الصدق", "completed", "2026-09-24 07:00:00"),   # current window
        ("الصدق", "partially", "2026-09-20 07:00:00"),   # current window
        ("الصدق", "missed", "2026-09-20 09:00:00"),      # same day, later → wins
        ("الصدق", "completed", "2026-08-20 07:00:00"),   # previous window
        ("الصدق", "completed", "2026-07-01 07:00:00"),   # outside both
    ]
    for name, st, ts in rows:
        c.execute(
            "INSERT INTO habits_value_events (device_id, child_id, habit_name, status, created_at)"
            " VALUES ('d', 1, ?, ?, ?)", (name, st, ts),
        )
    rates = four_week_rates(c, "d", 1, THU)
    assert rates == {"الصدق": {"rate": round(1 / 28, 3), "prev_rate": round(1 / 28, 3)}}
