"""Web-facing child-mode endpoints for the QR Web App (Phase 4).

Teens (13-18) scan a QR code shown by the parent app. The QR encodes a
short one-time claim code, NOT the real token, so the token never appears in
browser history. The browser opens a static landing page served by FastAPI and
redeems the code via POST /api/child-web/claim-session/{code}. The returned
long-lived web token (20h) is then stored in localStorage and used as a
Child-Bearer header for subsequent habit-reporting requests.

The actual habit endpoints are the existing /api/value-tracking/child-mode/*
routes; they already accept Child-Bearer tokens. This router only adds the
claim/redeem flow plus a metadata endpoint the UI can use to display the teen's
name after claiming.
"""
from fastapi import APIRouter, HTTPException, Query, Request

from app.db.init_db import get_conn
from app.services import child_token as child_token_service

router = APIRouter(prefix="/child-web", tags=["child-web"])


@router.post("/claim-session", response_model=dict)
def claim_session(request: Request, claim: str | None = Query(None, min_length=8)):
    """Redeem a one-time QR claim code for a long-lived web child token."""
    if not claim:
        raise HTTPException(status_code=422, detail="مطلوب رمز المطالبة (claim).")
    result = child_token_service.redeem_claim_code(claim)
    if result is None:
        raise HTTPException(status_code=410, detail="الرمز غير صالح أو تم استخدامه.")

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT name, age_group FROM child_profiles WHERE id = ?",
            (result["child_id"],),
        ).fetchone()
    finally:
        conn.close()

    return {
        "token": result["token"],
        "child_id": result["child_id"],
        "child_name": row["name"] if row else "الطفل",
        "age_group": row["age_group"] if row else None,
        "expires_at": result["expires_at"],
    }


@router.get("/me", response_model=dict)
def web_child_profile(request: Request):
    """Return minimal profile info for the currently authenticated web child."""
    child_id = getattr(request.state, "child_id", None)
    device_id = getattr(request.state, "device_id", None)
    if not isinstance(child_id, int) or not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق وضع الطفل.")

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT name, age_group FROM child_profiles WHERE id = ? AND device_id = ?",
            (child_id, device_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="لم يُعثر على ملف الطفل.")

    return {
        "child_id": child_id,
        "child_name": row["name"],
        "age_group": row["age_group"],
    }


@router.post("/refresh", response_model=dict)
def refresh_web_session(request: Request):
    """Refresh an existing web child token using its stored child_id/device_id.

    This lets a teen who still has a valid (or just-expired) localStorage token
    request a fresh 20h token without scanning a new QR, as long as the parent
    has not revoked the underlying relationship. The new token is issued only
    from the existing identity carried by the request, so no parent credentials
    are required.
    """
    child_id = getattr(request.state, "child_id", None)
    device_id = getattr(request.state, "device_id", None)
    if not isinstance(child_id, int) or not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق وضع الطفل.")

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM child_profiles WHERE id = ? AND device_id = ?",
            (child_id, device_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="لم يُعثر على ملف الطفل.")

    ttl = child_token_service.web_ttl_seconds()
    token = child_token_service.issue_child_token(
        device_id, child_id, ttl_seconds=ttl, is_web=True
    )
    return {
        "token": token,
        "child_id": child_id,
        "expires_at": child_token_service.child_token_expiry_iso(token),
    }
