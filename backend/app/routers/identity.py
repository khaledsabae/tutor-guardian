"""
Identity router — Phase 1.2 optional Google Sign-In.

Allows an anonymous device-bound parent to optionally link a Google
identity. The link survives app reinstall because child_profiles + progress
are keyed off device_id, and the server can migrate data from a previous
device_id to the linked google_id. This is the seed of multi-device sync.

Security:
  - The mobile app sends a Google ID token (JWT), not a raw google_id.
  - The server verifies the token signature/claims with Google's public
    tokeninfo endpoint before linking.
"""
import asyncio
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Request

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(tags=["identity"])


# Accepted issuers per Google OAuth 2.0 docs.
_GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})

# Hard-coded, non-secret client ID used to validate the Google ID token audience.
# The web client ID is the one the mobile plugin uses as serverClientId.
_GOOGLE_WEB_CLIENT_ID = "620240456244-d7a3fd35ianuu34i1sobb0pj4ncttmdu.apps.googleusercontent.com"


async def _verify_google_id_token(id_token: str) -> Optional[dict]:
    """Verify a Google ID token via Google's tokeninfo endpoint.

    Returns the token payload on success, None on failure.
    Validates issuer, expiry, and audience/authorized party.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
            )
    except httpx.HTTPError as e:
        logger.warning("Google tokeninfo network error: %s", e)
        return None

    if r.status_code != 200:
        logger.warning("Google tokeninfo returned %s: %s", r.status_code, r.text)
        return None

    try:
        payload = r.json()
    except Exception:
        return None

    iss = payload.get("iss", "")
    if iss not in _GOOGLE_ISSUERS:
        logger.warning("Google token invalid issuer: %s", iss)
        return None

    try:
        exp = int(payload.get("exp", "0"))
    except (ValueError, TypeError):
        return None
    if exp == 0:
        return None

    # Accept tokens issued for the Web client ID (serverClientId).
    aud = payload.get("aud", "")
    azp = payload.get("azp", "")
    if aud != _GOOGLE_WEB_CLIENT_ID and azp != _GOOGLE_WEB_CLIENT_ID:
        logger.warning("Google token audience not recognised: aud=%s azp=%s", aud, azp)
        return None

    return payload


@router.post("/identity/link-google")
async def link_google_identity(request: Request, payload: dict) -> dict:
    device_id = getattr(request.state, "device_id", "")
    id_token = (payload.get("id_token") or "").strip()

    if not id_token or not device_id:
        return {"ok": False, "error": "id_token_and_device_required"}

    token_payload = await _verify_google_id_token(id_token)
    if token_payload is None:
        return {"ok": False, "error": "invalid_google_id_token"}

    google_id = token_payload.get("sub", "").strip()
    email = (token_payload.get("email") or "").strip()
    display_name = (token_payload.get("name") or "").strip()

    if not google_id:
        return {"ok": False, "error": "invalid_google_id_token"}

    # sqlite is blocking — keep it off the event loop.
    await asyncio.to_thread(_link_identity, device_id, google_id, email, display_name)
    return {"ok": True, "google_id": google_id, "email": email}


def _link_identity(device_id: str, google_id: str, email: str, display_name: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO parent_identities (google_id, email, display_name)
            VALUES (?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                email = COALESCE(excluded.email, parent_identities.email),
                display_name = COALESCE(excluded.display_name, parent_identities.display_name)
            """,
            (google_id, email or None, display_name or None),
        )
        conn.execute(
            """
            INSERT INTO identity_links (device_id, google_id, linked_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(device_id) DO UPDATE SET
                google_id = excluded.google_id,
                linked_at = excluded.linked_at
            """,
            (device_id, google_id),
        )
        conn.commit()

        # Optional: merge data from any previously linked device_id.
        # Best-effort by design — the link above is already committed.
        try:
            _merge_legacy_device_data(conn, device_id, google_id)
        except Exception as e:
            logger.warning("Legacy device merge failed (link kept): %s", e)
    finally:
        conn.close()


@router.get("/identity/me")
def get_identity(request: Request) -> dict:
    device_id = getattr(request.state, "device_id", "")
    conn = get_conn()
    row = conn.execute(
        """
        SELECT p.google_id, p.email, p.display_name, l.linked_at
        FROM identity_links l
        JOIN parent_identities p ON p.google_id = l.google_id
        WHERE l.device_id = ?
        """,
        (device_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {"ok": True, "linked": False}
    return {
        "ok": True,
        "linked": True,
        "google_id": row["google_id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "linked_at": row["linked_at"],
    }


def _merge_legacy_device_data(conn, current_device_id: str, google_id: str) -> None:
    """Best-effort migration from any older device linked to the same Google id."""
    old = conn.execute(
        "SELECT device_id FROM identity_links WHERE google_id = ? AND device_id != ?",
        (google_id, current_device_id),
    ).fetchone()
    if not old:
        return

    old_device = old["device_id"]
    # Copy child profiles if the current device has none.
    has_children = conn.execute(
        "SELECT 1 FROM child_profiles WHERE device_id = ? LIMIT 1",
        (current_device_id,),
    ).fetchone()
    if not has_children:
        conn.execute(
            """
            INSERT INTO child_profiles (device_id, name, age_group, gender, avatar_emoji, created_at, updated_at)
            SELECT ?, name, age_group, gender, avatar_emoji, created_at, updated_at
            FROM child_profiles WHERE device_id = ?
            """,
            (current_device_id, old_device),
        )
    conn.commit()
