"""
Push-token router — Phase 1.1 re-engagement loop.

Stores FCM tokens per device_id on the backend so the server can send
re-engagement pushes later (streak-at-risk, new content, win-back).
AuthMiddleware guarantees the device_id in request.state.device_id.
"""
from fastapi import APIRouter, Request

from app.db.init_db import get_conn

router = APIRouter(tags=["push"])


@router.post("/push/register")
def register_push_token(request: Request, payload: dict) -> dict:
    device_id = getattr(request.state, "device_id", "")
    token = payload.get("token", "").strip()
    if not token:
        return {"ok": False, "error": "token_required"}

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO push_tokens (device_id, token, platform, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(device_id) DO UPDATE SET
            token = excluded.token,
            platform = excluded.platform,
            updated_at = excluded.updated_at
        """,
        (device_id, token, payload.get("platform", "android").strip().lower() or "android"),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/push/token")
def get_push_token(request: Request) -> dict:
    """For health/checks — returns whether we have a stored token."""
    device_id = getattr(request.state, "device_id", "")
    conn = get_conn()
    row = conn.execute(
        "SELECT token, platform, updated_at FROM push_tokens WHERE device_id = ?",
        (device_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {"ok": False, "registered": False}
    return {"ok": True, "registered": True, "updated_at": row["updated_at"]}
