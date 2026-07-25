"""
Feedback router — تقييم المحادثة
=================================
POST /api/feedback   → تسجيل 👍 / 👎 مع تعليق اختياري

يتطلب Bearer token (نفس auth middleware).
"""
import base64
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Header,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field, field_validator

from app.db.init_db import get_conn

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Simple shared secret so only Khaled can read submitted feedback.
# Fail closed: if FEEDBACK_ADMIN_KEY is unset the admin endpoints are disabled
# (no guessable default). Must be configured in the production .env.
_ADMIN_KEY = os.environ.get("FEEDBACK_ADMIN_KEY", "")


def _require_admin(x_admin_key: str) -> None:
    """Guard admin-only feedback endpoints with a constant-time secret compare."""
    import secrets as _secrets

    if not _ADMIN_KEY or not _secrets.compare_digest(x_admin_key, _ADMIN_KEY):
        raise HTTPException(status_code=403, detail="forbidden")


# Optional Telegram notifications for new app feedback. Both must be set in the
# production .env or notification is silently skipped (the feedback is still
# stored — the alert is a convenience, never a dependency).
_TG_BOT_TOKEN = os.environ.get("FEEDBACK_TELEGRAM_BOT_TOKEN", "")
_TG_CHAT_ID = os.environ.get("FEEDBACK_TELEGRAM_CHAT_ID", "")

logger = logging.getLogger(__name__)


def _tg_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_TG_BOT_TOKEN}/{method}"


def telegram_configured() -> bool:
    return bool(_TG_BOT_TOKEN and _TG_CHAT_ID)


def _remember_tg_message(fid: str, message_id: int) -> None:
    """Store the alert's Telegram message id so a reply to it can be traced
    back to this feedback row. This is the primary correlation key for the
    reply loop; the #fb_ tag in the text is the fallback."""
    try:
        con = get_conn()
        _ensure_app_feedback_table(con)
        con.execute(
            "UPDATE app_feedback SET tg_message_id = ? WHERE id = ?",
            (message_id, fid),
        )
        con.commit()
        con.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not store tg_message_id for %s: %s", fid, exc)


def notify_new_feedback(
    fid: str,
    message: str,
    audio_b64: str | None,
    app_version: str | None,
    contact: str | None,
    device_id: str | None,
) -> None:
    """Telegram ping for a new feedback row. Runs as a BackgroundTask, i.e.
    after the user's response has already been sent — a slow or unreachable
    Telegram must never be felt by someone trying to report a problem.

    Deliberately sends plain text, no parse_mode: user-written feedback
    routinely contains `_`, `*` and backticks, and Telegram rejects the whole
    message (400) when those don't form valid Markdown. The previous version
    used parse_mode=Markdown, so exactly the messages most worth reading were
    the ones that silently failed to arrive.
    """
    if not telegram_configured():
        return
    try:
        body = message.strip() or "(صوتي فقط)"
        if len(body) > 3000:
            body = body[:3000] + "…"
        text = "\n".join(
            [
                "📝 فيدباك جديد في المربّي",
                f"الإصدار: {app_version or 'غير معروف'}",
                f"للتواصل: {contact}" if contact else "للتواصل: —",
                f"الجهاز: {device_id[:8] if device_id else '—'}",
                "",
                body,
                "",
                # Both the reply anchor and the fallback correlation key.
                f"#fb_{fid[:8]}  ← ردّ على هذه الرسالة ليصل ردّك للمستخدم",
            ]
        )
        resp = httpx.post(
            _tg_url("sendMessage"),
            json={"chat_id": _TG_CHAT_ID, "text": text},
            timeout=10,
        )
        message_id = None
        if resp.status_code == 200:
            message_id = (resp.json().get("result") or {}).get("message_id")
            if message_id:
                _remember_tg_message(fid, message_id)
        else:
            logger.warning("telegram sendMessage %s: %s", resp.status_code, resp.text[:200])

        # Upload the voice note itself rather than linking to it: the download
        # endpoint is admin-key protected, so a bare URL would just 403 in the
        # Telegram client. This way the note is playable in the chat.
        if audio_b64:
            _send_voice(fid, audio_b64, reply_to=message_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram notify failed for %s: %s", fid, exc)


def _send_voice(fid: str, audio_b64: str, reply_to: int | None) -> None:
    try:
        raw = base64.b64decode(audio_b64)
        payload = {"chat_id": _TG_CHAT_ID, "caption": f"🎤 #fb_{fid[:8]}"}
        if reply_to:
            payload["reply_to_message_id"] = str(reply_to)
        resp = httpx.post(
            _tg_url("sendAudio"),
            data=payload,
            files={"audio": (f"feedback_{fid[:8]}.m4a", raw, "audio/mp4")},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("telegram sendAudio %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram voice upload failed for %s: %s", fid, exc)


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
    # Columns added after the table shipped. `audio_b64` holds voice notes
    # inline because the docs/ volume is mounted read-only in production;
    # `tg_message_id` links a row to its Telegram alert so replies can be
    # routed back to the sender.
    cols = {r[1] for r in con.execute("PRAGMA table_info(app_feedback)")}
    for name, ddl in (("audio_b64", "TEXT"), ("tg_message_id", "INTEGER")):
        if name not in cols:
            con.execute(f"ALTER TABLE app_feedback ADD COLUMN {name} {ddl}")


class AppFeedbackIn(BaseModel):
    message: str = Field("", max_length=4000)
    contact: str | None = Field(None, max_length=200)
    device_id: str | None = Field(None, max_length=120)
    app_version: str | None = Field(None, max_length=40)
    # Optional voice note as a base64 string (no data-url prefix needed).
    audio_base64: str | None = None


@router.post("/app", status_code=status.HTTP_201_CREATED)
def submit_app_feedback(body: AppFeedbackIn, background: BackgroundTasks) -> dict:
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

    background.add_task(
        notify_new_feedback,
        fid,
        body.message.strip(),
        audio_b64,
        body.app_version,
        body.contact,
        body.device_id,
    )
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
