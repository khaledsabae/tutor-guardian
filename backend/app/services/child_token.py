"""Stateless child-mode session tokens for «ميزان العادات».

Uses HMAC-SHA256 signed tokens so the server can verify child sessions
without any database table, lock, or query. (The one-time QR claim codes that
lead to a web token are the exception: they are in `child_web_claims`.) Tokens are short-lived (30
minutes by default) and carry only: child_id, a keyed device binding (never the
device id itself — format v2), scope, iat, exp.
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

from app.db.init_db import get_conn

_CHILD_SCOPE = "habit_child"
_WEB_SCOPE = "habit_child_web"


# One-time claim codes live in `child_web_claims` (schema v29). They used to
# be a module-level dict, which had three faults: a restart (every deploy)
# lost every code in flight, a second worker would not see the first one's
# codes, and redemption was check-then-set across threadpool threads, so two
# simultaneous redeems of one code could both succeed. The table stores the
# sha256 of the code, never the code, and never a token: the web token is
# minted at redemption, so a copy of the table holds nothing usable.
_CLAIM_TTL_SECONDS = 120


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _secret() -> bytes:
    """Return the HMAC secret from env. Fails closed: no fallback value."""
    raw = os.environ.get("CHILD_MODE_SECRET")
    if not raw:
        raise RuntimeError(
            "CHILD_MODE_SECRET is not set — refusing to sign/verify child tokens. "
            "Set a strong random value (e.g. `openssl rand -hex 32`) in the environment."
        )
    return raw.encode("utf-8")


def assert_configured() -> None:
    """Startup guard: raise early if the child-token secret is missing."""
    _secret()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    pad = -len(data) % 4
    return base64.urlsafe_b64decode(data + ("=" * pad))


def _device_binding(device_id: str) -> str:
    """An opaque, keyed stand-in for the parent's device id.

    Child tokens used to carry the device id itself, readable by anyone who
    base64-decodes the payload — a teen holding a 20-hour web token could read
    their parent's device id and mint a parent session with it (PR #26 review,
    P1). The token now carries only this HMAC: the server resolves the device
    from the child and checks it still matches; the bearer learns nothing.
    """
    return _b64encode(hmac.new(_secret(), b"device:" + device_id.encode("utf-8"),
                               hashlib.sha256).digest()[:18])


def issue_child_token(device_id: str, child_id: int, ttl_seconds: int = 1800, is_web: bool = False) -> str:
    """Issue a short-lived signed token for a child reporting session.

    When is_web=True the token is scoped for web use and is valid for a longer
    duration (20 hours) so the teen does not need to re-scan a QR code during
    the day. The default 30-minute token remains for mobile child-mode.
    Format v2: no device id in the payload (see _device_binding).
    """
    now = int(time.time())
    scope = _WEB_SCOPE if is_web else _CHILD_SCOPE
    payload = {
        "v": 2,
        "scope": scope,
        "dh": _device_binding(device_id),
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
    secret = _secret()  # outside the try: misconfiguration must not read as "invalid token"
    try:
        payload_b64, sig_b64 = token.split(".")
        payload_bytes = _b64decode(payload_b64)
        expected_sig = hmac.new(secret, payload_bytes, hashlib.sha256).digest()
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
    except Exception:
        return None
    if "device_id" in payload:
        # Format v1 (device id in clear). Still accepted until it expires —
        # at most 20 hours after this deploy — and never issued again.
        return payload
    return _resolve_device(payload)


def _resolve_device(payload: dict[str, Any]) -> dict[str, Any] | None:
    """v2: the device comes from the child's profile, checked against the
    token's keyed binding. A deleted child, or one no longer on that device,
    invalidates the token."""
    try:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT device_id FROM child_profiles WHERE id = ?",
                (int(payload.get("child_id", 0)),),
            ).fetchone()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — unreadable store: not a valid token
        return None
    if row is None or not hmac.compare_digest(
            _device_binding(row["device_id"]), str(payload.get("dh", ""))):
        return None
    return {**payload, "device_id": row["device_id"]}


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

    `ttl_seconds` is the lifetime of the web token the code redeems for; the
    code itself is good for two minutes.
    """
    code = secrets.token_urlsafe(24)
    now = time.time()
    conn = get_conn()
    try:
        conn.execute("DELETE FROM child_web_claims WHERE expires_at < ?", (now,))
        conn.execute(
            "INSERT INTO child_web_claims (code_hash, device_id, child_id, ttl_seconds, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_code_hash(code), device_id, child_id, ttl_seconds, now + _CLAIM_TTL_SECONDS),
        )
        conn.commit()
    finally:
        conn.close()
    return code


def redeem_claim_code(code: str) -> dict[str, Any] | None:
    """Redeem a one-time claim code.

    Returns {"token": <web-token>, "child_id": int, "expires_at": iso}
    on success, or None if the code is missing, expired, or already used.

    The spend is a single conditional UPDATE, so of two concurrent redeems
    exactly one sees rowcount 1; SQLite serialises the writes.
    """
    h = _code_hash(code)
    conn = get_conn()
    try:
        spent = conn.execute(
            "UPDATE child_web_claims SET used_at = ? "
            "WHERE code_hash = ? AND used_at IS NULL AND expires_at >= ?",
            (time.time(), h, time.time()),
        ).rowcount
        conn.commit()
        if spent != 1:
            return None
        row = conn.execute(
            "SELECT device_id, child_id, ttl_seconds FROM child_web_claims WHERE code_hash = ?",
            (h,),
        ).fetchone()
    finally:
        conn.close()
    token = issue_child_token(row["device_id"], row["child_id"],
                              ttl_seconds=row["ttl_seconds"], is_web=True)
    return {
        "token": token,
        "child_id": row["child_id"],
        "expires_at": child_token_expiry_iso(token),
    }


def web_ttl_seconds() -> int:
    """Return the configured web token lifetime (default 20h)."""
    try:
        return int(os.environ.get("CHILD_WEB_TOKEN_TTL_SECONDS", "72000"))
    except ValueError:
        return 72000