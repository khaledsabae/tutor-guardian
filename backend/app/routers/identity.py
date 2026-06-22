"""
Identity router — Phase 1.2 optional Google Sign-In.

Allows an anonymous device-bound parent to optionally link a Google
identity. The link survives app reinstall because child_profiles + progress
are keyed off device_id, and the server can migrate data from a previous
device_id to the linked google_id. This is the seed of multi-device sync.
"""
from fastapi import APIRouter, Request

from app.db.init_db import get_conn

router = APIRouter(tags=["identity"])


@router.post("/identity/link-google")
def link_google_identity(request: Request, payload: dict) -> dict:
    device_id = getattr(request.state, "device_id", "")
    google_id = payload.get("google_id", "").strip()
    email = payload.get("email", "").strip()
    display_name = payload.get("display_name", "").strip()

    if not google_id or not device_id:
        return {"ok": False, "error": "google_id_and_device_required"}

    conn = get_conn()
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
    _merge_legacy_device_data(conn, device_id, google_id)

    conn.close()
    return {"ok": True}


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
            INSERT INTO child_profiles (device_id, name, dob, gender, avatar_emoji, created_at, updated_at)
            SELECT ?, name, dob, gender, avatar_emoji, created_at, updated_at
            FROM child_profiles WHERE device_id = ?
            """,
            (current_device_id, old_device),
        )
    conn.commit()
