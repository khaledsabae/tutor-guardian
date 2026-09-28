"""Habit streaks and the 7-day strip (UX_UI_ROADMAP §3.2–3.3).

A streak day is a UTC calendar day on which the child logged at least one habit
as completed or partially done. Effort counts; a "missed" record does not break
anything by being recorded, it simply does not extend the run.

The streak shield: one day without effort per calendar week (Mon–Sun) is
forgiven, so a single bad day does not erase a month. A forgiven day does not
add to the count. Two empty days in the same week end the run.

Today never breaks a streak: the day is not over, so an empty today is skipped
rather than spent as the shield.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

# Effort statuses. Mirrors the points rule in value_tracking (completed = 1,
# partially = 0.5): anything that earns a point keeps the streak alive.
_EFFORT = ("completed", "partially")

# How far back to look. A streak longer than this reports as this.
MAX_STREAK_DAYS = 400

STRIP_DAYS = 7


def _week(d: date) -> date:
    """Monday of the ISO week containing `d`."""
    return d - timedelta(days=d.weekday())


def effort_days(
    conn: sqlite3.Connection, device_id: str, child_id: int, since: date
) -> set[date]:
    rows = conn.execute(
        "SELECT DISTINCT date(created_at) AS d FROM habits_value_events "
        "WHERE device_id = ? AND child_id = ? AND date(created_at) >= ? "
        f"AND status IN ({','.join('?' * len(_EFFORT))})",
        (device_id, child_id, since.isoformat(), *_EFFORT),
    ).fetchall()
    return {date.fromisoformat(r["d"]) for r in rows}


def compute_streak(active: set[date], today: date) -> dict:
    """{days, today_active, shield_used_this_week} for a set of effort days."""
    today_active = today in active
    shielded_weeks: set[date] = set()
    forgiven: list[date] = []
    oldest_active: date | None = None
    days = 0
    d = today if today_active else today - timedelta(days=1)
    earliest = today - timedelta(days=MAX_STREAK_DAYS)
    while d >= earliest:
        if d in active:
            days += 1
            oldest_active = d
        elif _week(d) not in shielded_weeks:
            shielded_weeks.add(_week(d))
            forgiven.append(d)
        else:
            break
        d -= timedelta(days=1)
    # A shield counts as "used" only when it bridges two parts of the run:
    # a forgiven day older than every active day protected nothing.
    used_this_week = oldest_active is not None and any(
        _week(f) == _week(today) and f > oldest_active for f in forgiven
    )
    return {
        "days": days,
        "today_active": today_active,
        "shield_used_this_week": used_this_week,
    }


def habit_streak(
    conn: sqlite3.Connection, device_id: str, child_id: int, today: date
) -> dict:
    since = today - timedelta(days=MAX_STREAK_DAYS)
    return compute_streak(effort_days(conn, device_id, child_id, since), today)


def week_strip(
    conn: sqlite3.Connection, device_id: str, child_id: int, today: date
) -> tuple[list[str], dict[str, list[str | None]]]:
    """(dates oldest→today, {habit_name: [status | None per date]}).

    The latest record of a day wins, the same rule the today view uses.
    """
    dates = [today - timedelta(days=i) for i in range(STRIP_DAYS - 1, -1, -1)]
    index = {d.isoformat(): i for i, d in enumerate(dates)}
    rows = conn.execute(
        "SELECT habit_name, status, date(created_at) AS d FROM habits_value_events "
        "WHERE device_id = ? AND child_id = ? AND date(created_at) >= ? "
        "ORDER BY created_at, id",
        (device_id, child_id, dates[0].isoformat()),
    ).fetchall()
    strip: dict[str, list[str | None]] = {}
    for r in rows:
        i = index.get(r["d"])
        if i is None:
            continue
        strip.setdefault(r["habit_name"], [None] * STRIP_DAYS)[i] = r["status"]
    return [d.isoformat() for d in dates], strip


RATE_DAYS = 28
_VALUE = {"completed": 1.0, "partially": 0.5}


def four_week_rates(
    conn: sqlite3.Connection, device_id: str, child_id: int, today: date
) -> dict[str, dict[str, float]]:
    """{habit: {rate, prev_rate}}: share of the last 28 days the habit was done
    (partly = half), and the same for the 28 days before, for "which habits are
    sticking". The latest record of a day wins; a day with no record is 0.
    Only habits with a record in the 56-day window are listed.
    """
    start_cur = today - timedelta(days=RATE_DAYS - 1)
    start_prev = start_cur - timedelta(days=RATE_DAYS)
    rows = conn.execute(
        "SELECT habit_name, status, date(created_at) AS d FROM habits_value_events "
        "WHERE device_id = ? AND child_id = ? AND date(created_at) >= ? "
        "ORDER BY created_at, id",
        (device_id, child_id, start_prev.isoformat()),
    ).fetchall()
    latest: dict[tuple[str, str], str] = {}
    for r in rows:
        latest[(r["habit_name"], r["d"])] = r["status"]
    cur: dict[str, float] = {}
    prev: dict[str, float] = {}
    for (name, d), status in latest.items():
        bucket = cur if date.fromisoformat(d) >= start_cur else prev
        bucket[name] = bucket.get(name, 0.0) + _VALUE.get(status, 0.0)
    return {
        name: {
            "rate": round(cur.get(name, 0.0) / RATE_DAYS, 3),
            "prev_rate": round(prev.get(name, 0.0) / RATE_DAYS, 3),
        }
        for name in {n for n, _ in latest}
    }
