"""
Referral router — Phase 0.2 growth loop.

Anonymous, device-based referral (no accounts). Every device gets a short
referral code; a freshly-installed device claims the code it arrived with
(captured via the Google Play Install Referrer, `&referrer=ref_<code>`), and
the backend records the attribution. Coins are credited client-side (there is
no server coins ledger), so these endpoints return the reward amount and the
referrer's running invited-count for the client to reconcile locally.

Endpoints (Bearer auth — see AuthMiddleware; the prefix is exempted from the
public list there only for nothing — it requires a token like /api/children):

  GET  /api/referral/me      → {code, invited_count, reward_coins, share_url}
  POST /api/referral/claim   → body {code}; records this device as referred.

Campaign codes (`DA01`, `WAAR`, `KT001` — see app.services.attribution) have no
device behind them. A claim of one that is well-formed is recorded under the
owner `campaign#<CODE>` even if the code was never seen before: the app makes
exactly one claim attempt per install, so a 404 there loses the install's
attribution for good — which is what happened to every campaign code until
now, since none existed in referral_codes.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db.init_db import get_conn
from app.services.attribution import (
    DEVICE_CODE_ALPHABET,
    DEVICE_CODE_LEN,
    campaign_owner,
    is_campaign_code,
    normalize_code,
    play_install_url,
)

router = APIRouter(prefix="/referral", tags=["referral"])

# Coins each side earns; credited client-side (no server ledger).
# Doubled 2026-07-16 (growth plan §6.4 — temporary referral campaign);
# revert to 50 when the campaign ends.
REWARD_COINS = 100
# Unambiguous alphabet (no 0/O/1/I) for codes that get typed/read aloud. The
# shape is also what tells a person's code from a campaign's (attribution.py).
_ALPHABET = DEVICE_CODE_ALPHABET
_CODE_LEN = DEVICE_CODE_LEN


class ClaimRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=16)


def _require_device_id(request: Request) -> str:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق")
    return device_id


def _gen_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))


def _code_for_device(conn, device_id: str) -> str:
    """Return this device's referral code, creating a unique one on first ask."""
    row = conn.execute(
        "SELECT code FROM referral_codes WHERE device_id = ?", (device_id,)
    ).fetchone()
    if row:
        return row["code"]
    for _ in range(8):  # vanishingly unlikely to collide, but be safe
        code = _gen_code()
        try:
            conn.execute(
                "INSERT INTO referral_codes (device_id, code) VALUES (?, ?)",
                (device_id, code),
            )
            conn.commit()
            return code
        except Exception:  # noqa: BLE001 — UNIQUE clash, retry
            continue
    raise HTTPException(status_code=500, detail="تعذّر توليد كود الإحالة")


@router.get("/me")
def my_referral(request: Request) -> dict:
    """This device's code + how many installs it has driven."""
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        code = _code_for_device(conn, device_id)
        invited = conn.execute(
            "SELECT COUNT(*) AS n FROM referrals WHERE referrer_device = ?",
            (device_id,),
        ).fetchone()["n"]
    finally:
        conn.close()
    return {
        "code": code,
        "invited_count": invited,
        "reward_coins": REWARD_COINS,
        "share_url": play_install_url(code),  # …&referrer=ref_<code>, as ever
    }


def _get_client_ip(request: Request) -> str:
    # Resolved once, from trusted proxies only, by ClientIPMiddleware. Reading
    # CF-Connecting-IP / X-Forwarded-For here trusted whatever the caller sent.
    return request.client.host if request.client else "unknown"


@router.post("/claim")
def claim_referral(body: ClaimRequest, request: Request) -> dict:
    """Record that this (new) device was referred by `body.code`.

    Idempotent + abuse-guarded: a device can be referred only once, can't
    refer itself, and the code must exist — or be a well-formed campaign code,
    which needs no row of its own. Returns the reward for the client to credit
    locally."""
    device_id = _require_device_id(request)
    raw = body.code.strip().upper()
    # `da-01` typed or linked by hand is DA01; anything that cannot be a code
    # is looked up as sent and 404s as before.
    code = raw if raw == "AUTO" else (normalize_code(raw) or raw)
    conn = get_conn()
    try:
        # Check if already claimed first to avoid fingerprinting for already claimed devices
        already = conn.execute(
            "SELECT 1 FROM referrals WHERE referred_device = ?", (device_id,)
        ).fetchone()
        if already:
            return {"ok": False, "already_claimed": True, "reward_coins": 0}

        if code == "AUTO":
            ip = _get_client_ip(request)
            click = conn.execute(
                "SELECT code FROM referral_clicks "
                "WHERE ip = ? AND clicked_at > datetime('now', '-24 hours') "
                "ORDER BY clicked_at DESC LIMIT 1",
                (ip,)
            ).fetchone()
            if click:
                code = click["code"]
            else:
                return {"ok": False, "already_claimed": False, "reward_coins": 0, "detail": "no_fingerprint_match"}

        owner = conn.execute(
            "SELECT device_id FROM referral_codes WHERE code = ?", (code,)
        ).fetchone()
        if owner is not None:
            referrer = owner["device_id"]
        elif is_campaign_code(code):
            referrer = campaign_owner(code)
        else:
            raise HTTPException(status_code=404, detail="كود إحالة غير صالح")
        if referrer == device_id:
            raise HTTPException(status_code=400, detail="لا يمكن إحالة نفسك")

        conn.execute(
            "INSERT INTO referrals (referrer_device, referred_device, code) "
            "VALUES (?, ?, ?)",
            (referrer, device_id, code),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "already_claimed": False, "reward_coins": REWARD_COINS}
