"""Custom habit templates router for «ميزان العادات».

Parent-defined habits that supplement the age-banded defaults for each child.
Templates are soft-archived via is_active and protected by a unique
(child_id, custom_name) constraint at the database layer.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.init_db import get_conn
from app.models.value_tracking import HabitTemplateCreate, HabitTemplateOut, HabitTemplateUpdate

router = APIRouter()


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


def _template_row_to_model(row: sqlite3.Row) -> HabitTemplateOut:
    return HabitTemplateOut(
        id=row["id"],
        child_id=row["child_id"],
        category=row["category"],
        custom_name=row["custom_name"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("/habit-templates", response_model=HabitTemplateOut, status_code=201)
def create_template(
    request: Request,
    payload: HabitTemplateCreate,
    child_id: int = Query(..., ge=1),
):
    """Add a parent-defined habit template for a child."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        now = datetime.now().isoformat()
        try:
            cur = conn.execute(
                """
                INSERT INTO habit_templates (device_id, child_id, category, custom_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (device_id, child_id, payload.category, payload.custom_name, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail=f"عادة مخصصة بنفس الاسم موجودة بالفعل لهذا الطفل: {payload.custom_name}",
            ) from exc
        template_id = cur.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT * FROM habit_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return _template_row_to_model(row)
    finally:
        conn.close()


@router.get("/habit-templates", response_model=list[HabitTemplateOut])
def list_templates(
    request: Request,
    child_id: int = Query(..., ge=1),
    active_only: bool = Query(default=False),
):
    """List custom habit templates for a child."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
        sql = (
            "SELECT * FROM habit_templates WHERE device_id = ? AND child_id = ?"
        )
        params: list = [device_id, child_id]
        if active_only:
            sql += " AND is_active = 1"
        sql += " ORDER BY created_at"
        rows = conn.execute(sql, params).fetchall()
        return [_template_row_to_model(r) for r in rows]
    finally:
        conn.close()


@router.patch("/habit-templates/{template_id}", response_model=HabitTemplateOut)
def update_template(
    template_id: int,
    request: Request,
    payload: HabitTemplateUpdate,
):
    """Activate or archive (soft-delete) a custom habit template."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM habit_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if row is None or row["device_id"] != device_id:
            raise HTTPException(status_code=404, detail="قالب عادة غير موجود.")
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE habit_templates SET is_active = ?, updated_at = ? WHERE id = ?",
            (int(payload.is_active), now, template_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM habit_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return _template_row_to_model(row)
    finally:
        conn.close()
