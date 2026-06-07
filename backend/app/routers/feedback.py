"""
Feedback router — تقييم المحادثة
=================================
POST /api/feedback   → تسجيل 👍 / 👎 مع تعليق اختياري

يتطلب Bearer token (نفس auth middleware).
"""
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.db.init_db import get_conn

router = APIRouter(prefix="/feedback", tags=["feedback"])


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
