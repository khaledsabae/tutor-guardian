"""Daily routine router for «حِساب اليوم».

Tracks child routines (sleep, feed, diaper) as behavioural data tied to the
parent's authenticated device and child profile. All endpoints require Bearer
auth and operate only on children owned by the caller's device.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.init_db import get_conn
from app.models.daily_routine import (
    RoutineDayOut,
    RoutineDeleteOut,
    RoutineEventCreate,
    RoutineEventOut,
    RoutineSummaryOut,
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
    """Return the local calendar date used for the daily routine bucket."""
    return date.today().isoformat()


def _ensure_routine_row(conn: sqlite3.Connection, device_id: str, child_id: int, routine_date: str) -> int:
    """Get or create the daily routine row for a child/date; return its id."""
    row = conn.execute(
        "SELECT id FROM child_daily_routines "
        "WHERE device_id = ? AND child_id = ? AND routine_date = ?",
        (device_id, child_id, routine_date),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO child_daily_routines (device_id, child_id, routine_date) "
        "VALUES (?, ?, ?)",
        (device_id, child_id, routine_date),
    )
    lastrowid = cur.lastrowid
    if lastrowid is None:
        raise RuntimeError("Failed to create routine row")
    return lastrowid


def _event_row_to_model(row: sqlite3.Row) -> RoutineEventOut:
    return RoutineEventOut(
        id=row["id"],
        routine_id=row["routine_id"],
        event_type=row["event_type"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        feed_type=row["feed_type"],
        amount_ml=row["amount_ml"],
        side=row["side"],
        diaper_type=row["diaper_type"],
        notes=row["notes"],
        source=row["source"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _duration_minutes(started_at: str, ended_at: str | None) -> int:
    if not ended_at:
        return 0
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        return max(0, int((end - start).total_seconds() // 60))
    except Exception:
        return 0


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/daily-routine/today", response_model=RoutineDayOut)
def get_today(request: Request, child_id: int = Query(..., ge=1)):
    """Fetch today's routine events for a child."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        routine_id = _ensure_routine_row(conn, device_id, child_id, _today())
        rows = conn.execute(
            "SELECT * FROM routine_events WHERE routine_id = ? ORDER BY started_at",
            (routine_id,),
        ).fetchall()
        return RoutineDayOut(
            routine_id=routine_id,
            child_id=child_id,
            routine_date=_today(),
            events=[_event_row_to_model(r) for r in rows],
        )
    finally:
        conn.close()


@router.post("/daily-routine/events", response_model=RoutineEventOut)
def create_event(
    request: Request,
    payload: RoutineEventCreate,
    child_id: int = Query(..., ge=1),
):
    """Record a new routine event for a child today."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        routine_id = _ensure_routine_row(conn, device_id, child_id, _today())
        cur = conn.execute(
            """
            INSERT INTO routine_events (
                routine_id, event_type, started_at, ended_at, feed_type,
                amount_ml, side, diaper_type, notes, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                routine_id,
                payload.event_type,
                payload.started_at,
                payload.ended_at,
                payload.feed_type,
                payload.amount_ml,
                payload.side,
                payload.diaper_type,
                payload.notes,
                payload.source,
            ),
        )
        event_id = cur.lastrowid
        conn.execute(
            "UPDATE child_daily_routines SET updated_at = datetime('now') WHERE id = ?",
            (routine_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM routine_events WHERE id = ?", (event_id,)
        ).fetchone()
        return _event_row_to_model(row)
    finally:
        conn.close()


@router.patch("/daily-routine/events/{event_id}", response_model=RoutineEventOut)
def update_event(event_id: int, request: Request, payload: RoutineEventCreate):
    """Update an existing event (must belong to the caller's device/child)."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT e.*, r.device_id, r.child_id
            FROM routine_events e
            JOIN child_daily_routines r ON e.routine_id = r.id
            WHERE e.id = ?
            """,
            (event_id,),
        ).fetchone()
        if row is None or row["device_id"] != device_id:
            raise HTTPException(status_code=404, detail="حدث غير موجود.")
        conn.execute(
            """
            UPDATE routine_events SET
                event_type = ?, started_at = ?, ended_at = ?, feed_type = ?,
                amount_ml = ?, side = ?, diaper_type = ?, notes = ?, source = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                payload.event_type,
                payload.started_at,
                payload.ended_at,
                payload.feed_type,
                payload.amount_ml,
                payload.side,
                payload.diaper_type,
                payload.notes,
                payload.source,
                event_id,
            ),
        )
        conn.execute(
            "UPDATE child_daily_routines SET updated_at = datetime('now') WHERE id = ?",
            (row["routine_id"],),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM routine_events WHERE id = ?", (event_id,)
        ).fetchone()
        return _event_row_to_model(row)
    finally:
        conn.close()


@router.delete("/daily-routine/events/{event_id}", response_model=RoutineDeleteOut)
def delete_event(event_id: int, request: Request):
    """Delete an event."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT e.id, e.routine_id, r.device_id
            FROM routine_events e
            JOIN child_daily_routines r ON e.routine_id = r.id
            WHERE e.id = ?
            """,
            (event_id,),
        ).fetchone()
        if row is None or row["device_id"] != device_id:
            raise HTTPException(status_code=404, detail="حدث غير موجود.")
        conn.execute("DELETE FROM routine_events WHERE id = ?", (event_id,))
        conn.execute(
            "UPDATE child_daily_routines SET updated_at = datetime('now') WHERE id = ?",
            (row["routine_id"],),
        )
        conn.commit()
        return RoutineDeleteOut(deleted=1)
    finally:
        conn.close()


@router.get("/daily-routine/summary", response_model=RoutineSummaryOut)
def get_summary(
    request: Request,
    child_id: int = Query(..., ge=1),
    days: int = Query(default=7, ge=1, le=30),
):
    """Aggregated routine summary for the last N days."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """
            SELECT e.*
            FROM routine_events e
            JOIN child_daily_routines r ON e.routine_id = r.id
            WHERE r.device_id = ? AND r.child_id = ? AND r.routine_date >= ?
            ORDER BY r.routine_date, e.started_at
            """,
            (device_id, child_id, since),
        ).fetchall()
        total_sleep = 0
        feed_count = 0
        feed_amount = 0
        diaper_count = 0
        for row in rows:
            et = row["event_type"]
            if et == "sleep":
                total_sleep += _duration_minutes(row["started_at"], row["ended_at"])
            elif et == "feed":
                feed_count += 1
                if row["amount_ml"]:
                    feed_amount += row["amount_ml"]
            elif et == "diaper":
                diaper_count += 1
        return RoutineSummaryOut(
            days=days,
            total_sleep_minutes=total_sleep,
            total_feed_count=feed_count,
            total_feed_amount_ml=feed_amount,
            diaper_count=diaper_count,
        )
    finally:
        conn.close()
