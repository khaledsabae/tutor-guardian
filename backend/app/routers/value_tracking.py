"""Value tracking router for «ميزان العادات».

Tracks daily habit completion (worship / self_building / study) for
children aged 10–18. All endpoints require Bearer auth and operate only
on children owned by the caller's device.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.init_db import get_conn
from app.models.value_tracking import (
    HabitDayOut,
    HabitDeleteOut,
    HabitEventCreate,
    HabitEventOut,
    HabitSummaryOut,
)

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────


def _require_device_id(request: Request) -> str:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id


def _load_owned_child(conn: sqlite3.Connection, child_id: int, device_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM child_profiles WHERE id = ?", (child_id,)
    ).fetchone()
    if row is None or row["device_id"] != device_id:
        raise HTTPException(status_code=404, detail="طفل غير موجود.")
    return row


def _today() -> str:
    """Return the local calendar date used for the habit bucket."""
    return date.today().isoformat()


def _event_row_to_model(row: sqlite3.Row) -> HabitEventOut:
    return HabitEventOut(
        id=row["id"],
        child_id=row["child_id"],
        category=row["category"],
        habit_name=row["habit_name"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ── Age-gate helper ───────────────────────────────────────────────────────

_HABIT_AGE_GROUPS = {"7-9", "10-12", "13-15", "16-18"}


def _is_habit_age(age_group: str) -> bool:
    return age_group in _HABIT_AGE_GROUPS


@router.get("/value-tracking/today", response_model=HabitDayOut)
def get_today(request: Request, child_id: int = Query(..., ge=1)):
    """Fetch today's habit events for a child."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        child = _load_owned_child(conn, child_id, device_id)
        if not _is_habit_age(child["age_group"]):
            raise HTTPException(
                status_code=400,
                detail="ميزان العادات متاح للأطفال من 7 إلى 18 سنة فقط.",
            )
        today = _today()
        rows = conn.execute(
            "SELECT * FROM habits_value_events "
            "WHERE device_id = ? AND child_id = ? AND date(created_at) = ? "
            "ORDER BY created_at",
            (device_id, child_id, today),
        ).fetchall()

        # Compute today's local points from events.
        points = _sum_points(rows)
        return HabitDayOut(
            child_id=child_id,
            date=today,
            events=[_event_row_to_model(r) for r in rows],
            points=points,
        )
    finally:
        conn.close()


@router.post("/value-tracking/events", response_model=HabitEventOut)
def create_event(
    request: Request,
    payload: HabitEventCreate,
    child_id: int = Query(..., ge=1),
):
    """Record a new habit evaluation for a child today."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        child = _load_owned_child(conn, child_id, device_id)
        if not _is_habit_age(child["age_group"]):
            raise HTTPException(
                status_code=400,
                detail="ميزان العادات متاح للأطفال من 7 إلى 18 سنة فقط.",
            )
        cur = conn.execute(
            """
            INSERT INTO habits_value_events (
                device_id, child_id, category, habit_name, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                device_id,
                child_id,
                payload.category,
                payload.habit_name,
                payload.status,
            ),
        )
        event_id = cur.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT * FROM habits_value_events WHERE id = ?", (event_id,)
        ).fetchone()
        return _event_row_to_model(row)
    finally:
        conn.close()


@router.delete("/value-tracking/events/{event_id}", response_model=HabitDeleteOut)
def delete_event(event_id: int, request: Request):
    """Delete a habit event."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, device_id FROM habits_value_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if row is None or row["device_id"] != device_id:
            raise HTTPException(status_code=404, detail="حدث غير موجود.")
        conn.execute("DELETE FROM habits_value_events WHERE id = ?", (event_id,))
        conn.commit()
        return HabitDeleteOut(deleted=1)
    finally:
        conn.close()


@router.get("/value-tracking/summary", response_model=HabitSummaryOut)
def get_summary(
    request: Request,
    child_id: int = Query(..., ge=1),
    days: int = Query(default=7, ge=1, le=30),
):
    """Aggregated habit summary for the last N days."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        child = _load_owned_child(conn, child_id, device_id)
        if not _is_habit_age(child["age_group"]):
            raise HTTPException(
                status_code=400,
                detail="ميزان العادات متاح للأطفال من 7 إلى 18 سنة فقط.",
            )
        since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT * FROM habits_value_events "
            "WHERE device_id = ? AND child_id = ? AND date(created_at) >= ? "
            "ORDER BY created_at",
            (device_id, child_id, since),
        ).fetchall()
        total_completed = 0
        total_partially = 0
        total_missed = 0
        by_category: dict[str, dict[str, int]] = defaultdict(
            lambda: {"completed": 0, "partially": 0, "missed": 0}
        )
        points_per_day: dict[str, float] = defaultdict(float)
        for row in rows:
            status = row["status"]
            category = row["category"]
            d = row["created_at"][:10]
            if status == "completed":
                total_completed += 1
                points_per_day[d] += 1
            elif status == "partially":
                total_partially += 1
                points_per_day[d] += 0.5
            elif status == "missed":
                total_missed += 1
            by_category[category][status] += 1
        # Total points over the window.
        total_points = round(sum(points_per_day.values()), 2)
        return HabitSummaryOut(
            days=days,
            total_completed=total_completed,
            total_partially=total_partially,
            total_missed=total_missed,
            by_category=dict(by_category),
            total_points=total_points,
        )
    finally:
        conn.close()


def _sum_points(rows) -> float:
    total = 0.0
    for row in rows:
        status = row["status"]
        if status == "completed":
            total += 1.0
        elif status == "partially":
            total += 0.5
    return round(total, 2)