"""
Push sender — Phase 1.1 re-engagement loop.

Uses Firebase Admin SDK (FCM HTTP v1). Credentials are loaded from:
  1. env FIREBASE_CREDENTIALS (raw JSON string), or
  2. backend/secrets/firebase-adminsdk.json (gitignored file).

Provides thin helpers to send notifications to a device by device_id.
Cron scripts live outside this module (ops/scripts/) and call these helpers.
"""
import json
import os
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from app.db.init_db import get_conn

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CREDENTIALS_PATH = _PROJECT_ROOT / "secrets" / "firebase-adminsdk.json"

_app: firebase_admin.App | None = None


def _load_credentials() -> Optional[dict]:
    """Read service account JSON from env, env-path, or file. Returns None if missing."""
    raw = os.environ.get("FIREBASE_CREDENTIALS", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    path_env = os.environ.get("FIREBASE_CREDENTIALS_PATH", "").strip()
    if path_env:
        p = Path(path_env)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    if _CREDENTIALS_PATH.exists():
        return json.loads(_CREDENTIALS_PATH.read_text(encoding="utf-8"))
    return None


def _ensure_app() -> bool:
    """Initialize Firebase Admin once. Returns True if initialized."""
    global _app
    if _app is not None:
        return True
    creds = _load_credentials()
    if creds is None:
        return False
    cred_obj = credentials.Certificate(creds)
    _app = firebase_admin.initialize_app(cred_obj)
    return True


def get_fcm_token(device_id: str) -> Optional[str]:
    """Return the latest FCM token for a device, or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT token FROM push_tokens WHERE device_id = ? ORDER BY updated_at DESC LIMIT 1",
        (device_id,),
    ).fetchone()
    conn.close()
    return row["token"] if row else None


def send_to_device(
    device_id: str,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> dict:
    """Send an FCM notification to a single device.

    Returns {"ok": True, "sent": True, "message_id": ...} on success,
    {"ok": True, "sent": False, "reason": "no_token"} if no token stored,
    {"ok": False, "error": ...} on other failures.
    """
    if not _ensure_app():
        return {"ok": False, "error": "firebase_credentials_not_configured"}

    token = get_fcm_token(device_id)
    if not token:
        return {"ok": True, "sent": False, "reason": "no_token"}

    notification = messaging.Notification(title=title, body=body)
    message = messaging.Message(
        notification=notification,
        data=data or {},
        token=token,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="almorabbi_reengagement",
                sound="default",
            ),
        ),
    )
    try:
        message_id = messaging.send(message, app=_app)
        return {"ok": True, "sent": True, "message_id": message_id}
    except messaging.UnregisteredError:
        # Token is stale; remove it so we don't retry.
        _remove_token(device_id)
        return {"ok": True, "sent": False, "reason": "unregistered"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _remove_token(device_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM push_tokens WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()


def send_to_topic(
    topic: str,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> dict:
    """Broadcast to an FCM topic (e.g. 'all_parents')."""
    if not _ensure_app():
        return {"ok": False, "error": "firebase_credentials_not_configured"}

    notification = messaging.Notification(title=title, body=body)
    message = messaging.Message(
        notification=notification,
        data=data or {},
        topic=topic,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="almorabbi_reengagement",
                sound="default",
            ),
        ),
    )
    try:
        message_id = messaging.send(message, app=_app)
        return {"ok": True, "sent": True, "message_id": message_id}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
