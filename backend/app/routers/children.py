"""
Children router — Phase 5.

Endpoints (all require Bearer auth — see AuthMiddleware):

  POST /api/children
      Body: {name, age_group, gender?, avatar_emoji?}
      Returns: {id, name, age_group, gender, avatar_emoji, created_at, updated_at}
      Side-effect: row linked to the device_id from the Bearer token.

  GET  /api/children/{id}/progress
      Returns: {child_id, lessons: [{lesson_id, path_id, status,
                                     started_at, completed_at, updated_at}]}
      Authorization: the child must belong to the requester's device.

The progress PATCH lives in `routers/program.py` to keep all
`/api/program/...` mutating endpoints in one place.

Cross-cutting:
  * All age_group values are validated against `CANONICAL_AGE_GROUPS`
    (the same enum used by the curriculum content layer).
  * 404 on cross-device access (we do NOT leak the existence of a
    child that belongs to another device).
  * 422 on validation errors (FastAPI's Pydantic v2 / manual checks).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.core.taxonomy import CANONICAL_AGE_GROUPS
from app.db.init_db import get_conn

router = APIRouter()

# ── Pydantic models ──────────────────────────────────────────────────────


class ChildCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    age_group: str
    gender: Optional[str] = Field(default=None, max_length=20)
    avatar_emoji: Optional[str] = Field(default=None, max_length=8)

    @field_validator("age_group")
    @classmethod
    def _validate_age_group(cls, v: str) -> str:
        if v not in CANONICAL_AGE_GROUPS:
            raise ValueError(
                f"age_group غير صالح. القيم المسموحة: {sorted(CANONICAL_AGE_GROUPS)}"
            )
        return v

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name لا يمكن أن يكون فارغاً")
        return v

    @field_validator("avatar_emoji")
    @classmethod
    def _validate_emoji(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # A simple sanity check: 1-6 grapheme-ish chars; not perfect but
        # rejects multi-line / control-character input. Surrogate-pair
        # emojis (4-byte) take 2 chars in UTF-16 / 1 codepoint.
        if not re.match(r"^[\U0001F000-\U0010FFFF\U00002600-\U000027BF\U0001F300-\U0001FAFF\u2600-\u27BF]+$", v):
            raise ValueError("avatar_emoji يجب أن يكون إيموجي واحد أو أكثر")
        return v


class ChildResponse(BaseModel):
    id: int
    name: str
    age_group: str
    gender: Optional[str]
    avatar_emoji: Optional[str]
    created_at: str
    updated_at: str


# ── Helpers ──────────────────────────────────────────────────────────────


def _row_to_child(row: sqlite3.Row) -> ChildResponse:
    return ChildResponse(
        id=row["id"],
        name=row["name"],
        age_group=row["age_group"],
        gender=row["gender"],
        avatar_emoji=row["avatar_emoji"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _require_device_id(request: Request) -> str:
    """Pull the device_id that the auth middleware attached to request.state."""
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        # Should be unreachable on protected routes, but defensive.
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id


# ── Routes ───────────────────────────────────────────────────────────────


@router.post(
    "/children",
    status_code=201,
    response_model=ChildResponse,
    summary="Create a child profile for the current device",
)
def create_child(payload: ChildCreateRequest, request: Request) -> ChildResponse:
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO child_profiles
                (device_id, name, age_group, gender, avatar_emoji)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                device_id,
                payload.name,
                payload.age_group,
                payload.gender,
                payload.avatar_emoji,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM child_profiles WHERE id = ?", (new_id,)
        ).fetchone()
        return _row_to_child(row)
    finally:
        conn.close()


@router.get(
    "/children/{child_id}/progress",
    summary="Fetch lesson_progress for a child (must belong to this device)",
)
def get_child_progress(
    child_id: int,
    request: Request,
    path_id: Optional[str] = None,
):
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        child_row = conn.execute(
            "SELECT * FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()
        # Cross-device access: 404 (do not leak existence).
        if child_row is None or child_row["device_id"] != device_id:
            raise HTTPException(status_code=404, detail="طفل غير موجود.")

        sql = (
            "SELECT lesson_id, path_id, status, started_at, completed_at, updated_at "
            "FROM lesson_progress WHERE device_id = ?"
        )
        params: list = [device_id]
        if path_id is not None:
            sql += " AND path_id = ?"
            params.append(path_id)
        sql += " ORDER BY updated_at DESC"
        rows = conn.execute(sql, params).fetchall()
        lessons = [
            {
                "lesson_id": r["lesson_id"],
                "path_id": r["path_id"],
                "status": r["status"],
                "started_at": r["started_at"],
                "completed_at": r["completed_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
        return {
            "child_id": child_id,
            "device_id": device_id,
            "lessons": lessons,
            "fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    finally:
        conn.close()
