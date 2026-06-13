"""
Feedback router — تقييم المحادثة
=================================
POST /api/feedback   → تسجيل 👍 / 👎 مع تعليق اختياري

يتطلب Bearer token (نفس auth middleware).
"""
import base64
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.db.init_db import get_conn

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Where uploaded voice notes land (served read-only at /docs by main.py).
_FEEDBACK_AUDIO_DIR = Path(__file__).resolve().parents[3] / "docs" / "feedback"
# Simple shared secret so only Khaled can read submitted feedback.
_ADMIN_KEY = os.environ.get("FEEDBACK_ADMIN_KEY", "almorabbi-admin")


def _ensure_app_feedback_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS app_feedback (
            id TEXT PRIMARY KEY,
            message TEXT,
            contact TEXT,
            audio_file TEXT,
            device_id TEXT,
            app_version TEXT,
            created_at TEXT
        )
        """
    )


class AppFeedbackIn(BaseModel):
    message: str = Field("", max_length=4000)
    contact: str | None = Field(None, max_length=200)
    device_id: str | None = Field(None, max_length=120)
    app_version: str | None = Field(None, max_length=40)
    # Optional voice note as a base64 string (no data-url prefix needed).
    audio_base64: str | None = None


@router.post("/app", status_code=status.HTTP_201_CREATED)
def submit_app_feedback(body: AppFeedbackIn) -> dict:
    """General in-app feedback (text and/or a voice note) — reaches Khaled."""
    if not (body.message.strip() or body.audio_base64):
        raise HTTPException(status_code=400, detail="empty feedback")

    fid = uuid.uuid4().hex
    audio_file = None
    if body.audio_base64:
        try:
            raw = base64.b64decode(body.audio_base64)
            if len(raw) > 8 * 1024 * 1024:  # 8 MB cap
                raise HTTPException(status_code=413, detail="audio too large")
            _FEEDBACK_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            audio_file = f"docs/feedback/{fid}.m4a"
            (_FEEDBACK_AUDIO_DIR / f"{fid}.m4a").write_bytes(raw)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"bad audio: {exc}") from exc

    try:
        con = get_conn()
        _ensure_app_feedback_table(con)
        con.execute(
            "INSERT INTO app_feedback (id, message, contact, audio_file, "
            "device_id, app_version, created_at) VALUES (?,?,?,?,?,?,?)",
            (fid, body.message.strip(), body.contact, audio_file,
             body.device_id, body.app_version,
             datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
        con.close()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc

    return {"status": "ok", "id": fid}


@router.get("/app")
def list_app_feedback(x_admin_key: str = Header(default="")) -> dict:
    """Khaled-only: list submitted feedback (audio at /<audio_file>)."""
    if x_admin_key != _ADMIN_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    con = get_conn()
    _ensure_app_feedback_table(con)
    rows = con.execute(
        "SELECT id, message, contact, audio_file, device_id, app_version, "
        "created_at FROM app_feedback ORDER BY created_at DESC LIMIT 500"
    ).fetchall()
    con.close()
    cols = ["id", "message", "contact", "audio_file", "device_id",
            "app_version", "created_at"]
    return {"count": len(rows), "items": [dict(zip(cols, r)) for r in rows]}


class FeedbackIn(BaseModel):
    session_id: str | None = None
    rating: str = Field(..., description="'up' or 'down'")
    comment: str | None = Field(None, max_length=500)

    @field_validator("rating")
    @classmethod
    def _validate_rating(cls, v: str) -> str:
        if v not in ("up", "down"):
            raise ValueError("rating must be 'up' or 'down'")
        return v


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_feedback(body: FeedbackIn, request: Request) -> dict:
    """Record 👍/👎 feedback.

    The authenticated session_id is used when body.session_id is omitted.
    """
    session_id = body.session_id or getattr(request.state, "session_id", None)
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        con = get_conn()
        con.execute(
            """
            INSERT INTO user_feedback (session_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, body.rating, body.comment, created_at),
        )
        con.commit()
        con.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc

    return {"status": "ok"}
