"""
Feedback router — تقييم المحادثة
=================================
POST /api/feedback   → تسجيل 👍 / 👎 مع تعليق اختياري

يتطلب Bearer token (نفس auth middleware).
"""
import base64
import json
import logging
import os
import re
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


# ── Reply loop ────────────────────────────────────────────────────────────────
# Khaled replies to a feedback alert in Telegram; the reply is delivered back to
# the device that sent the feedback. Without this, a user who reports a problem
# never hears anything — which teaches people that reporting is pointless.

_TG_WEBHOOK_SECRET = os.environ.get("FEEDBACK_TELEGRAM_WEBHOOK_SECRET", "")

# Telegram will resend an update it thinks failed, so the handler must be cheap
# and always answer 200. Anything slow happens in a background task.
_MAX_REPLY_LEN = 2000


def _require_webhook_secret(token: str) -> None:
    """Fail closed. While the secret is unset the webhook accepts nothing —
    an unauthenticated public endpoint that writes to the DB and sends pushes
    is not something to leave open by default."""
    import secrets as _secrets

    if not _TG_WEBHOOK_SECRET or not _secrets.compare_digest(
        token, _TG_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=403, detail="forbidden")


def _find_feedback_for_reply(con, replied_to: dict) -> tuple[str, str | None] | None:
    """Resolve which feedback a Telegram reply belongs to.

    Primary key is the alert's message id, stored when the alert was sent.
    Falls back to the `#fb_<id8>` tag in the replied-to text or caption, which
    covers replies to the voice-note message and any alert sent before the
    message id was being recorded.
    """
    message_id = replied_to.get("message_id")
    if message_id:
        row = con.execute(
            "SELECT id, device_id FROM app_feedback WHERE tg_message_id = ?",
            (message_id,),
        ).fetchone()
        if row:
            return row[0], row[1]

    text = replied_to.get("text") or replied_to.get("caption") or ""
    match = re.search(r"#fb_([0-9a-f]{8})", text)
    if not match:
        return None
    row = con.execute(
        "SELECT id, device_id FROM app_feedback WHERE id LIKE ?",
        (match.group(1) + "%",),
    ).fetchone()
    return (row[0], row[1]) if row else None


def _deliver_reply(feedback_id: str, device_id: str | None, text: str) -> None:
    """Store the reply, then nudge the device. Runs in a background task.

    Push is only a nudge: it can fail silently (token expired, notifications
    off, app uninstalled). The reply is stored first and the app also polls
    GET /api/feedback/replies on launch, so delivery does not depend on FCM.
    """
    rid = uuid.uuid4().hex
    try:
        con = get_conn()
        con.execute(
            "INSERT INTO feedback_replies (id, feedback_id, device_id, "
            "reply_text, created_at) VALUES (?,?,?,?,?)",
            (rid, feedback_id, device_id, text,
             datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
        con.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not store reply for %s: %s", feedback_id, exc)
        return

    if not device_id:
        # Pre-fix feedback rows have no device id; the reply is stored and
        # visible to admin tooling, but there is nobody to deliver it to.
        logger.info("reply %s stored with no device_id — cannot deliver", rid)
        return

    try:
        from app.services.push_sender import send_to_device

        send_to_device(
            device_id,
            "ردّ من فريق المربّي 💬",
            text[:200],
            data={"link": "/inbox", "type": "feedback_reply"},
        )
        con = get_conn()
        con.execute(
            "UPDATE feedback_replies SET delivered_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), rid),
        )
        con.commit()
        con.close()
    except Exception as exc:  # noqa: BLE001
        # The reply is stored; the app will pick it up on next launch.
        logger.warning("push for reply %s failed: %s", rid, exc)


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(default=""),
) -> dict:
    """Receive a Telegram reply and route it back to the user who wrote in.

    This route is public in the auth middleware (Telegram has no device token),
    so it carries its own three guards: a shared secret compared in constant
    time, an allowlist on the chat id, and a body size cap.
    """
    _require_webhook_secret(x_telegram_bot_api_secret_token)

    raw = await request.body()
    if len(raw) > 64 * 1024:
        raise HTTPException(status_code=413, detail="payload too large")
    try:
        update = json.loads(raw or b"{}")
    except Exception:  # noqa: BLE001
        return {"ok": True}  # malformed: swallow, don't make Telegram retry

    message = update.get("message") or update.get("channel_post") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    # Only the configured chat can drive this. A valid secret from the wrong
    # chat is still rejected.
    if not _TG_CHAT_ID or chat_id != str(_TG_CHAT_ID):
        logger.warning("webhook update from unexpected chat %s", chat_id[:20])
        return {"ok": True}

    replied_to = message.get("reply_to_message") or {}
    text = (message.get("text") or "").strip()
    if not replied_to or not text:
        return {"ok": True}  # a plain message, not a reply — nothing to route

    try:
        con = get_conn()
        _ensure_app_feedback_table(con)
        found = _find_feedback_for_reply(con, replied_to)
        con.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("webhook lookup failed: %s", exc)
        return {"ok": True}

    if not found:
        logger.info("reply did not match any feedback row")
        return {"ok": True}

    feedback_id, device_id = found
    background.add_task(
        _deliver_reply, feedback_id, device_id, text[:_MAX_REPLY_LEN]
    )
    return {"ok": True}


@router.get("/replies")
def list_my_replies(request: Request) -> dict:
    """Replies waiting for this device.

    Protected by the auth middleware, so the device id comes from the caller's
    token and cannot be supplied (or guessed) as a parameter.
    """
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="no device")
    con = get_conn()
    rows = con.execute(
        "SELECT id, feedback_id, reply_text, created_at, read_at "
        "FROM feedback_replies WHERE device_id = ? "
        "ORDER BY created_at DESC LIMIT 50",
        (device_id,),
    ).fetchall()
    con.close()
    cols = ["id", "feedback_id", "reply_text", "created_at", "read_at"]
    items = [dict(zip(cols, r)) for r in rows]
    return {
        "count": len(items),
        "unread": sum(1 for i in items if not i["read_at"]),
        "items": items,
    }


@router.post("/replies/{reply_id}/read")
def mark_reply_read(reply_id: str, request: Request) -> dict:
    """Mark a reply as seen. Scoped to the caller's own device."""
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="no device")
    con = get_conn()
    cur = con.execute(
        "UPDATE feedback_replies SET read_at = ? WHERE id = ? AND device_id = ?",
        (datetime.now(timezone.utc).isoformat(), reply_id, device_id),
    )
    con.commit()
    changed = cur.rowcount
    con.close()
    if not changed:
        raise HTTPException(status_code=404, detail="not found")
    return {"status": "ok"}


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
