"""Value tracking router for «ميزان العادات».

Tracks daily habit completion (worship / self_building / study) for
children aged 7–18. All endpoints require Bearer auth and operate only
on children owned by the caller's device.

Merge logic in get_today(): age-banded defaults are merged with active
parent-defined custom templates from habit_templates. A recorded event
can belong to either source; the habit_name must match an allowed default
or an active custom template for the child.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.init_db import get_conn
from app.models.value_tracking import (
    ChildHabitDayOut,
    ChildHabitEventCreate,
    HabitDayOut,
    HabitDeleteOut,
    HabitEventCreate,
    HabitEventOut,
    HabitSummaryOut,
    TodayHabitItem,
)

__all__ = [
    "router",
    "_DEFAULT_HABITS",
    "_load_active_templates",
    "_load_today_events",
    "_build_today_habits",
    "_persist_event",
    "_verify_child_ownership",
    "_is_habit_age",
    "_event_row_to_model",
]

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────


def _require_device_id(request: Request) -> str:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id


def _verify_child_ownership(device_id: str, child_id: int) -> sqlite3.Row:
    """Verify that child_id belongs to device_id."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()
        if row is None or row["device_id"] != device_id:
            raise HTTPException(status_code=404, detail="طفل غير موجود.")
        return row
    finally:
        conn.close()


def _load_owned_child(conn: sqlite3.Connection, child_id: int, device_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM child_profiles WHERE id = ?", (child_id,)
    ).fetchone()
    if row is None or row["device_id"] != device_id:
        raise HTTPException(status_code=404, detail="طفل غير موجود.")
    return row


def _today() -> str:
    """Return the local calendar date used for the habit bucket."""
    return datetime.now(timezone.utc).date().isoformat()


def _event_row_to_model(row: sqlite3.Row) -> HabitEventOut:
    return HabitEventOut(
        id=row["id"],
        child_id=row["child_id"],
        category=row["category"],
        habit_name=row["habit_name"],
        status=row["status"],
        submitted_by=row["submitted_by"],
        device_timestamp=row["device_timestamp"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _load_today_events(
    conn: sqlite3.Connection, device_id: str, child_id: int, today: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM habits_value_events "
        "WHERE device_id = ? AND child_id = ? AND date(created_at) = ? "
        "ORDER BY created_at",
        (device_id, child_id, today),
    ).fetchall()


def _persist_event(
    conn: sqlite3.Connection,
    device_id: str,
    child_id: int,
    today: str,
    payload: HabitEventCreate,
    submitted_by: str = "parent",
    device_timestamp: str | None = None,
) -> HabitEventOut:
    ts = device_timestamp or datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO habits_value_events (
            device_id, child_id, category, habit_name, status,
            submitted_by, device_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            device_id,
            child_id,
            payload.category,
            payload.habit_name,
            payload.status,
            submitted_by,
            ts,
        ),
    )
    event_id = cur.lastrowid
    conn.commit()
    row = conn.execute(
        "SELECT * FROM habits_value_events WHERE id = ?", (event_id,)
    ).fetchone()
    return _event_row_to_model(row)


# ── Age-gate helper ───────────────────────────────────────────────────────

_HABIT_AGE_GROUPS = {"7-9", "10-12", "13-15", "16-18"}

# Mirrors kAgeBandedHabits in mobile/lib/features/routine/models/habit_models.dart.
_DEFAULT_HABITS: dict[str, dict[str, list[str]]] = {
    "7-9": {
        "worship": ["صلاة الفجر", "ورد القرآن"],
        "self_building": ["بر الوالدين", "النظام", "النوم المبكر"],
        "study": ["أداء الواجب", "مراجعة اليوم"],
    },
    "10-12": {
        "worship": ["صلاة الفجر", "ورد القرآن", "صلاة النافلة"],
        "self_building": ["بر الوالدين", "النظام", "التحكم بالغضب", "الصدق"],
        "study": ["أداء الواجب", "القراءة", "المراجعة"],
    },
    "13-15": {
        "worship": ["صلاة الفجر", "ورد القرآن", "قيام الليل"],
        "self_building": ["بر الوالدين", "النظام", "التحكم بالغضب", "الأمانة", "الصبر"],
        "study": ["أداء الواجب", "القراءة", "المراجعة", "التخطيط الدراسي"],
    },
    "16-18": {
        "worship": ["صلاة الفجر", "ورد القرآن", "قيام الليل", "ذكر الله"],
        "self_building": ["بر الوالدين", "النظام", "التحكم بالغضب", "الأمانة", "الصبر", "المواظبة"],
        "study": ["أداء الواجب", "القراءة", "المراجعة", "التخطيط الدراسي", "البحث"],
    },
}


def _default_habits_for_age(age_group: str) -> dict[str, list[str]]:
    return _DEFAULT_HABITS.get(age_group, _DEFAULT_HABITS["10-12"])


def _is_habit_age(age_group: str) -> bool:
    return age_group in _HABIT_AGE_GROUPS


def _load_active_templates(conn: sqlite3.Connection, device_id: str, child_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, category, custom_name, is_active FROM habit_templates "
        "WHERE device_id = ? AND child_id = ? AND is_active = 1 "
        "ORDER BY created_at",
        (device_id, child_id),
    ).fetchall()


def _build_today_habits(
    age_group: str,
    templates: list[sqlite3.Row],
    today_events: list[sqlite3.Row],
) -> list[TodayHabitItem]:
    """Merge defaults + active custom templates and attach today's status."""
    event_by_name: dict[str, sqlite3.Row] = {
        r["habit_name"]: r for r in today_events
    }
    seen: set[str] = set()
    items: list[TodayHabitItem] = []

    for category, names in _default_habits_for_age(age_group).items():
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            ev = event_by_name.get(name)
            items.append(
                TodayHabitItem(
                    category=category,
                    habit_name=name,
                    source="default",
                    status=ev["status"] if ev else None,
                    event_id=ev["id"] if ev else None,
                    template_id=None,
                )
            )

    for t in templates:
        name = t["custom_name"]
        if name in seen:
            continue
        seen.add(name)
        ev = event_by_name.get(name)
        items.append(
            TodayHabitItem(
                category=t["category"],
                habit_name=name,
                source="custom",
                status=ev["status"] if ev else None,
                event_id=ev["id"] if ev else None,
                template_id=t["id"],
            )
        )
    return items


def _allowed_habit_names(
    age_group: str,
    templates: list[sqlite3.Row],
) -> tuple[set[str], set[str]]:
    defaults = set()
    for names in _default_habits_for_age(age_group).values():
        defaults.update(names)
    customs = {t["custom_name"] for t in templates if t["is_active"]}
    return defaults, customs


@router.get("/value-tracking/today", response_model=HabitDayOut)
def get_today(request: Request, child_id: int = Query(..., ge=1)):
    """Fetch today's habit events for a child, merged with default + custom templates."""
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
        rows = _load_today_events(conn, device_id, child_id, today)
        templates = _load_active_templates(conn, device_id, child_id)

        # Compute today's local points from events.
        points = _sum_points(rows)
        habits = _build_today_habits(child["age_group"], templates, rows)
        return HabitDayOut(
            child_id=child_id,
            date=today,
            events=[_event_row_to_model(r) for r in rows],
            points=points,
            habits=habits,
        )
    finally:
        conn.close()


@router.post("/value-tracking/events", response_model=HabitEventOut)
def create_event(
    request: Request,
    payload: HabitEventCreate,
    child_id: int = Query(..., ge=1),
):
    """Record a new habit evaluation for a child today.

    The habit_name must match either a default habit for the child's age
    band or an active custom template owned by this device.
    """
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        child = _load_owned_child(conn, child_id, device_id)
        if not _is_habit_age(child["age_group"]):
            raise HTTPException(
                status_code=400,
                detail="ميزان العادات متاح للأطفال من 7 إلى 18 سنة فقط.",
            )
        templates = _load_active_templates(conn, device_id, child_id)
        defaults, customs = _allowed_habit_names(child["age_group"], templates)
        if payload.habit_name not in defaults and payload.habit_name not in customs:
            raise HTTPException(
                status_code=400,
                detail="اسم العادة غير مسموح به. اختر عادة من القائمة أو أنشئ قالباً مخصصاً.",
            )
        return _persist_event(conn, device_id, child_id, _today(), payload)
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