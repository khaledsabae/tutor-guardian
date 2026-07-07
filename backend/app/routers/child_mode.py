"""Child-mode endpoints for self-reported habit tracking.

These routes accept `Authorization: Child-Bearer <token>` issued by the
parent-facing session creation endpoint. They are intentionally narrow:
* view today's merged habit list for the linked child
* submit a single status for one habit today (no edit/delete)
"""
import sqlite3
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.init_db import get_conn
from app.models.value_tracking import (
    ChildHabitDayOut,
    HabitEventCreate,
    HabitEventOut,
    TodayHabitItem,
)
from app.routers.value_tracking import (
    _build_today_habits,
    _event_row_to_model,
    _load_active_templates,
    _load_today_events,
    _persist_event,
    _verify_child_ownership,
    router as value_router,
)
from app.services import child_token as child_token_service

router = APIRouter(tags=["child-mode"])


def _get_child_id(request: Request) -> int:
    child_id = getattr(request.state, "child_id", None)
    if not isinstance(child_id, int):
        raise HTTPException(status_code=401, detail="وضع الطفل غير مفعل.")
    return child_id


def _require_device_id(request: Request) -> str:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id


@router.post("/value-tracking/child-sessions", response_model=dict)
def create_child_session(request: Request, child_id: int = Query(..., ge=1)):
    """Parent endpoint: issue a short-lived child-mode token for a child.

    Requires normal parent Bearer auth. The returned token is meant to be
    handed to the child's device (or the same device in child mode) and is
    valid for 30 minutes.
    """
    device_id = _require_device_id(request)
    _verify_child_ownership(device_id, child_id)
    token = child_token_service.issue_child_token(device_id, child_id, ttl_seconds=1800)
    expires_at = child_token_service.child_token_expiry_iso(token)
    return {"token": token, "expires_at": expires_at, "child_id": child_id}


@router.get("/value-tracking/child-mode/today", response_model=ChildHabitDayOut)
def child_get_today(request: Request):
    """Child endpoint: fetch today's merged habit list (read-only)."""
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)

    conn = get_conn()
    today = date.today().isoformat()
    try:
        events = _load_today_events(conn, device_id, child_id, today)
        templates = _load_active_templates(conn, device_id, child_id)
        age_group = conn.execute(
            "SELECT age_group FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()["age_group"]
        habits = _build_today_habits(age_group, templates, events)
        return {
            "child_id": child_id,
            "date": today,
            "habits": habits,
            "events": [_event_row_to_model(r) for r in events],
        }
    finally:
        conn.close()


@router.post("/value-tracking/child-mode/events", response_model=HabitEventOut)
def child_record_event(request: Request, body: HabitEventCreate):
    """Child endpoint: submit today's status for one habit (submit-only)."""
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)

    # Validate that this is one of the habits available to the child today.
    today_data = child_get_today(request)
    available_names = {h.habit_name for h in today_data["habits"]}
    if body.habit_name not in available_names:
        raise HTTPException(
            status_code=400,
            detail="العادة غير متاحة لهذا الطفل اليوم.",
        )

    # Submit-only: if an event already exists today, reject the second attempt.
    today = date.today().isoformat()
    conn = get_conn()
    try:
        existing = _load_today_events(conn, device_id, child_id, today)
        already = [e for e in existing if e["habit_name"] == body.habit_name]
        if already:
            raise HTTPException(
                status_code=409,
                detail="تم تسجيل هذه العادة اليوم بالفعل. لا يمكن تعديلها من وضع الطفل.",
            )
        return _persist_event(conn, device_id, child_id, today, body)
    finally:
        conn.close()
