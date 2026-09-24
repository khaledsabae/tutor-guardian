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
    # The body is an untyped dict: a null or numeric field used to raise
    # AttributeError on .strip() and answer 500.
    token = str(payload.get("token") or "").strip()[:4096]
    platform = str(payload.get("platform") or "android").strip().lower()[:16] or "android"
    if not token:
        return {"ok": False, "error": "token_required"}

    # The build census rides along with the token, because this is the one
    # request the app makes on every launch. Both fields are optional: builds
    # already on Play do not send them, and their rows keep whatever they had
    # (COALESCE, not overwrite-with-null) so a silent client cannot erase a
    # version we already knew.
    app_version = str(payload.get("app_version") or "").strip()[:32] or None
    try:
        build_number = int(payload.get("build_number"))
    except (TypeError, ValueError):
        build_number = None

    conn = get_conn()
    try:
        _upsert_push_token(conn, device_id, token, platform, app_version, build_number)
    finally:
        conn.close()
    return {"ok": True}


def _upsert_push_token(conn, device_id, token, platform, app_version, build_number) -> None:
    conn.execute(
        """
        INSERT INTO push_tokens (device_id, token, platform, updated_at,
                                 app_version, build_number)
        VALUES (?, ?, ?, datetime('now'), ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            token = excluded.token,
            platform = excluded.platform,
            updated_at = excluded.updated_at,
            app_version = COALESCE(excluded.app_version, push_tokens.app_version),
            build_number = COALESCE(excluded.build_number, push_tokens.build_number)
        """,
        (device_id, token, platform, app_version, build_number),
    )
    conn.commit()


@router.get("/push/token")
def get_push_token(request: Request) -> dict:
    """For health/checks — returns whether we have a stored token."""
    device_id = getattr(request.state, "device_id", "")
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT token, platform, updated_at FROM push_tokens WHERE device_id = ?",
            (device_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"ok": False, "registered": False}
    return {"ok": True, "registered": True, "updated_at": row["updated_at"]}
