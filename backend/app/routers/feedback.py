"""
Feedback router — تقييم المحادثة
=================================
POST /api/feedback   → تسجيل 👍 / 👎 مع تعليق اختياري

يتطلب Bearer token (نفس auth middleware).
"""
import base64
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.db.init_db import get_conn

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Where uploaded voice notes land (served read-only at /docs by main.py).
_FEEDBACK_AUDIO_DIR = Path(__file__).resolve().parents[3] / "docs" / "feedback"
# Simple shared secret so only Khaled can read submitted feedback.
# Fail closed: if FEEDBACK_ADMIN_KEY is unset the admin endpoints are disabled
# (no guessable default). Must be configured in the production .env.
_ADMIN_KEY = os.environ.get("FEEDBACK_ADMIN_KEY", "")


def _require_admin(x_admin_key: str) -> None:
    """Guard admin-only feedback endpoints with a constant-time secret compare."""
    import secrets as _secrets

    if not _ADMIN_KEY or not _secrets.compare_digest(x_admin_key, _ADMIN_KEY):
        raise HTTPException(status_code=403, detail="forbidden")


# Optional Telegram notifications for new app feedback.
_TG_BOT_TOKEN = os.environ.get("FEEDBACK_TELEGRAM_BOT_TOKEN")
_TG_CHAT_ID = os.environ.get("FEEDBACK_TELEGRAM_CHAT_ID")


def _notify_new_feedback(fid: str, message: str, has_audio: bool, app_version: str | None) -> None:
    """Best-effort Telegram ping when a new feedback row is created."""
    if not _TG_BOT_TOKEN or not _TG_CHAT_ID:
        return
    try:
        text = (
            "📝 فيدباك جديد في المربّي\n"
            f"ID: `{fid[:8]}`\n"
            f"الإصدار: {app_version or 'unknown'}\n"
            f"صوتي: {'نعم' if has_audio else 'لا'}\n"
            f"المحتوى: {message[:300]}{'...' if len(message) > 300 else ''}"
        )
        httpx.post(
            f"https://api.telegram.org/bot{_TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": _TG_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass  # never block feedback submission on notification failure


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
    # Voice notes are stored in the DB (the docs/ volume is mounted read-only
    # in production, so we can't write audio files there). Add the column on
    # the fly for older DBs.
    cols = {r[1] for r in con.execute("PRAGMA table_info(app_feedback)")}
    if "audio_b64" not in cols:
        con.execute("ALTER TABLE app_feedback ADD COLUMN audio_b64 TEXT")


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
    audio_b64 = None
    if body.audio_base64:
        # Validate it decodes and isn't oversized; store the base64 in the DB
        # (docs/ is read-only in prod, so no file write).
        try:
            raw = base64.b64decode(body.audio_base64)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"bad audio: {exc}") from exc
        if len(raw) > 8 * 1024 * 1024:  # 8 MB cap
            raise HTTPException(status_code=413, detail="audio too large")
        audio_b64 = body.audio_base64

    try:
        con = get_conn()
        _ensure_app_feedback_table(con)
        con.execute(
            "INSERT INTO app_feedback (id, message, contact, audio_file, "
            "device_id, app_version, created_at, audio_b64) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (fid, body.message.strip(), body.contact, None,
             body.device_id, body.app_version,
             datetime.now(timezone.utc).isoformat(), audio_b64),
        )
        con.commit()
        con.close()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc

    _notify_new_feedback(fid, body.message.strip(), body.audio_base64 is not None, body.app_version)
    return {"status": "ok", "id": fid}


@router.get("/app")
def list_app_feedback(x_admin_key: str = Header(default="")) -> dict:
    """Khaled-only: list submitted feedback. Voice notes (has_audio=true) are
    fetched separately at GET /api/feedback/app/{id}/audio."""
    _require_admin(x_admin_key)
    con = get_conn()
    _ensure_app_feedback_table(con)
    rows = con.execute(
        "SELECT id, message, contact, device_id, app_version, created_at, "
        "(audio_b64 IS NOT NULL) FROM app_feedback "
        "ORDER BY created_at DESC LIMIT 500"
    ).fetchall()
    con.close()
    cols = ["id", "message", "contact", "device_id", "app_version",
            "created_at", "has_audio"]
    items = [dict(zip(cols, r)) for r in rows]
    for it in items:
        it["has_audio"] = bool(it["has_audio"])
    return {"count": len(rows), "items": items}


@router.get("/digest")
async def feedback_digest(limit: int = 200, x_admin_key: str = Header(default="")) -> dict:
    """Khaled-only: ملخّص قرارات ذكي ومرتّب بالأولوية لكل الفيدباك.

    يحلّل تقييمات 👍/👎 (مربوطة بالـQ&A الحقيقية) + فيدباك التطبيق عبر DeepSeek،
    ويرجّع العناصر الحقيقية القابلة للتنفيذ مصنّفة ومرتّبة حسب الخطورة."""
    _require_admin(x_admin_key)
    from app.services.feedback_analyzer import analyze

    return await analyze(limit)


@router.get("/app/{feedback_id}/audio")
def get_app_feedback_audio(feedback_id: str, x_admin_key: str = Header(default="")):
    """Khaled-only: download a feedback voice note as audio/mp4."""
    from fastapi.responses import Response

    _require_admin(x_admin_key)
    con = get_conn()
    _ensure_app_feedback_table(con)
    row = con.execute(
        "SELECT audio_b64 FROM app_feedback WHERE id = ?", (feedback_id,)
    ).fetchone()
    con.close()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="no audio")
    return Response(content=base64.b64decode(row[0]), media_type="audio/mp4")


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
