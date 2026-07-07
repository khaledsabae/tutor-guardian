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
import time
from datetime import datetime, timedelta, timezone
from typing import Any

_CHILD_SCOPE = "habit_child"


def _secret() -> bytes:
    """Return the HMAC secret from env or a deterministic fallback for tests."""
    raw = os.environ.get("CHILD_MODE_SECRET", "tg-dev-child-mode-secret-v1")
    return raw.encode("utf-8")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    pad = -len(data) % 4
    return base64.urlsafe_b64decode(data + ("=" * pad))


def issue_child_token(device_id: str, child_id: int, ttl_seconds: int = 1800) -> str:
    """Issue a short-lived signed token for a child reporting session."""
    now = int(time.time())
    payload = {
        "scope": _CHILD_SCOPE,
        "device_id": device_id,
        "child_id": child_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_secret(), payload_bytes, hashlib.sha256).digest()
    return f"{_b64encode(payload_bytes)}.{_b64encode(sig)}"


def verify_child_token(token: str) -> dict[str, Any] | None:
    """Verify a child token signature, scope, and expiry.

    Returns the payload dict on success or None on any failure.
    """
    try:
        payload_b64, sig_b64 = token.split(".")
        payload_bytes = _b64decode(payload_b64)
        expected_sig = hmac.new(_secret(), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64decode(sig_b64)):
            return None
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("scope") != _CHILD_SCOPE:
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
