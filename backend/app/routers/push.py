"""
Push-token router — Phase 1.1 re-engagement loop.

Stores FCM tokens per device_id on the backend so the server can send
re-engagement pushes later (streak-at-risk, new content, win-back).
AuthMiddleware guarantees the device_id in request.state.device_id.
"""
from fastapi import APIRouter, Request

from app.db.init_db import get_conn
from app.services import device_alerts, device_proof, device_twins

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
        _upsert_push_token(conn, device_id, token, platform, app_version, build_number,
                           session_token=getattr(request.state, "token", None))
    finally:
        conn.close()

    # The one request every launch makes, so it is where an install that
    # 1.0.58-1.0.67 split into two device ids gets put back together: if this
    # device is a childless twin of the family's device (same FCM token, born
    # in the same seconds — services/device_twins.py), it is folded into it
    # and the token the app holds now opens the family's data. Old builds
    # ignore the extra fields; new ones adopt the device id.
    canonical = device_twins.recover(device_id, credential=getattr(request.state, "token", None))
    if canonical:
        # This request's census belongs to the family device now — the token
        # that sent it opens it. (The twin's own row was removed by the fold,
        # logged; the family's row is only touched here, by the live request.)
        conn = get_conn()
        try:
            _upsert_push_token(conn, canonical, token, platform, app_version, build_number)
        finally:
            conn.close()
        return {"ok": True, "device_id": canonical, "identity_recovered": True}
    return {"ok": True}


def _upsert_push_token(conn, device_id, token, platform, app_version, build_number,
                       session_token=None) -> None:
    """Store the token. A *change* of token is the one event the device proof
    cannot see by itself (PR #26 review, round 3): a session can register any
    token for its device, so before SESSION_MINT_ENFORCE someone who knows a
    device id could point it at a phone they hold and pass the challenge there.

    So a change records when the new token became current (`token_since`) and
    whether a session with a clean proof vouched for it (`token_vouched`,
    services/device_proof.vouches_for). An unvouched change pauses the
    protected routes for 72 hours and owes the previous token a notice
    (services/device_alerts.py). Re-registering the same token — every launch
    does — changes neither. A first token is not a change and warns no one; on
    an established device it pauses account and child deletion for 72 hours
    (`token_first`, round 4).
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT token FROM push_tokens WHERE device_id = ?",
                           (device_id,)).fetchone()
        old = row["token"] if row is not None and row["token"] else None
        changed = old is not None and old != token
        vouched = (not changed) or device_proof.vouches_for(
            conn, device_id, session_token, old, token)
        first = old is None and device_proof.established(conn, device_id)
        conn.execute(
            """
            INSERT INTO push_tokens (device_id, token, platform, updated_at, app_version,
                                     build_number, token_since, token_vouched, token_first)
            VALUES (?, ?, ?, datetime('now'), ?, ?, datetime('now'), ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                token = excluded.token,
                platform = excluded.platform,
                updated_at = excluded.updated_at,
                app_version = COALESCE(excluded.app_version, push_tokens.app_version),
                build_number = COALESCE(excluded.build_number, push_tokens.build_number),
                token_since = CASE WHEN push_tokens.token = excluded.token
                                   THEN push_tokens.token_since ELSE excluded.token_since END,
                token_vouched = CASE WHEN push_tokens.token = excluded.token
                                     THEN push_tokens.token_vouched ELSE excluded.token_vouched END,
                token_first = CASE WHEN push_tokens.token = excluded.token
                                   THEN push_tokens.token_first ELSE excluded.token_first END
            """,
            (device_id, token, platform, app_version, build_number,
             1 if vouched else 0, 1 if first else 0),
        )
        if changed and not vouched:
            device_alerts.queue(conn, device_id, old)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
