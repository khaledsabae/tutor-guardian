"""Stateless child-mode session tokens for «ميزان العادات».

Uses HMAC-SHA256 signed tokens so the server can verify child sessions
without any database table, lock, or query. Tokens are short-lived (30
minutes by default) and carry only: child_id, device_id, scope, iat, exp.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

_CHILD_SCOPE = "habit_child"
_WEB_SCOPE = "habit_child_web"


# In-memory store for one-time claim codes. Keyed by a short random code.
# Each code stores the token to deliver to the browser. Codes are single-use
# and expire quickly (2 minutes) to prevent URL-history leakage and replay.
_claim_store: dict[str, dict[str, Any]] = {}


def _secret() -> bytes:
    """Return the HMAC secret from env or a deterministic fallback for tests."""
    raw = os.environ.get("CHILD_MODE_SECRET", "tg-dev-child-mode-secret-v1")
    return raw.encode("utf-8")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    pad = -len(data) % 4
    return base64.urlsafe_b64decode(data + ("=" * pad))


def issue_child_token(device_id: str, child_id: int, ttl_seconds: int = 1800, is_web: bool = False) -> str:
    """Issue a short-lived signed token for a child reporting session.

    When is_web=True the token is scoped for web use and is valid for a longer
    duration (20 hours) so the teen does not need to re-scan a QR code during
    the day. The default 30-minute token remains for mobile child-mode.
    """
    now = int(time.time())
    scope = _WEB_SCOPE if is_web else _CHILD_SCOPE
    payload = {
        "scope": scope,
        "device_id": device_id,
        "child_id": child_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_secret(), payload_bytes, hashlib.sha256).digest()
    return f"{_b64encode(payload_bytes)}.{_b64encode(sig)}"


def verify_child_token(token: str, *, allow_web: bool = True) -> dict[str, Any] | None:
    """Verify a child token signature, scope, and expiry.

    allow_web=True accepts both child-scope and web-scope tokens. Set to False
    to restrict to mobile child-mode only.

    Returns the payload dict on success or None on any failure.
    """
    try:
        payload_b64, sig_b64 = token.split(".")
        payload_bytes = _b64decode(payload_b64)
        expected_sig = hmac.new(_secret(), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64decode(sig_b64)):
            return None
        payload = json.loads(payload_bytes.decode("utf-8"))
        scope = payload.get("scope")
        if scope not in {_CHILD_SCOPE, _WEB_SCOPE}:
            return None
        if not allow_web and scope == _WEB_SCOPE:
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def child_token_expiry_iso(token: str) -> str | None:
    """Return the token expiry as an ISO string (for UI display)."""
    payload = verify_child_token(token)
    if payload is None:
        return None
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    return exp.isoformat()


def create_claim_code(device_id: str, child_id: int, ttl_seconds: int = 72000) -> str:
    """Create a short one-time claim code that redeems a long-lived web token.

    The parent app displays this code as a QR; when the teen's browser opens
    the corresponding /claim-session/{code} URL, the backend redeems it via
    POST and returns the real token. This prevents the actual token from ever
    appearing in browser history or being reshared as a link.
    """
    token = issue_child_token(device_id, child_id, ttl_seconds=ttl_seconds, is_web=True)
    code = secrets.token_urlsafe(24)
    now = time.time()
    _claim_store[code] = {
        "token": token,
        "device_id": device_id,
        "child_id": child_id,
        "exp": now + 120,
        "used": False,
    }
    _prune_claim_store()
    return code


def redeem_claim_code(code: str) -> dict[str, Any] | None:
    """Redeem a one-time claim code.

    Returns {"token": <web-token>, "child_id": int, "expires_at": iso}
    on success, or None if the code is missing, expired, or already used.
    """
    _prune_claim_store()
    entry = _claim_store.get(code)
    if entry is None:
        return None
    if entry["used"] or entry["exp"] < time.time():
        del _claim_store[code]
        return None
    entry["used"] = True
    token = entry["token"]
    expires_at = child_token_expiry_iso(token)
    return {
        "token": token,
        "child_id": entry["child_id"],
        "expires_at": expires_at,
    }


def _prune_claim_store() -> None:
    """Remove expired claim entries periodically."""
    now = time.time()
    expired = [code for code, entry in _claim_store.items() if entry["exp"] < now]
    for code in expired:
        del _claim_store[code]


def web_ttl_seconds() -> int:
    """Return the configured web token lifetime (default 20h)."""
    try:
        return int(os.environ.get("CHILD_WEB_TOKEN_TTL_SECONDS", "72000"))
    except ValueError:
        return 72000