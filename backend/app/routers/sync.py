"""
Sync router — Zero-Knowledge Sync.
Allows devices to upload and download end-to-end encrypted database backups.
Supports both anonymous device backups and multi-device sync via linked Google accounts.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sync"])

class BackupUploadRequest(BaseModel):
    salt: str = Field(..., min_length=1, max_length=256, description="Base64 encoded key derivation salt")
    nonce: str = Field(..., min_length=1, max_length=256, description="Base64 encoded AES-GCM nonce")
    # ~37MB of encrypted DB after base64 — far above any real client DB, but
    # bounded so a hostile client can't park unbounded blobs in server memory.
    payload: str = Field(..., min_length=1, max_length=50_000_000, description="Base64 encoded encrypted database bytes")

@router.post("/api/sync/upload")
def upload_backup(request: Request, payload: BackupUploadRequest):  # sync on purpose: sqlite work runs in the threadpool
    """
    Upload an encrypted database payload.
    Automatically links to the active Google identity if the device is linked.
    """
    device_id = getattr(request.state, "device_id", "")
    if not device_id:
        raise HTTPException(status_code=401, detail="Unauthorized: device_id missing")

    conn = get_conn()
    try:
        # Check if the device is linked to a Google account
        link = conn.execute(
            "SELECT google_id FROM identity_links WHERE device_id = ?",
            (device_id,)
        ).fetchone()
        google_id = link["google_id"] if link else None

        # Store or update the backup
        conn.execute(
            """
            INSERT INTO user_backups (device_id, google_id, salt, nonce, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(device_id) DO UPDATE SET
                google_id = excluded.google_id,
                salt = excluded.salt,
                nonce = excluded.nonce,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (device_id, google_id, payload.salt, payload.nonce, payload.payload)
        )
        conn.commit()
        return {"ok": True}
    except Exception as exc:
        logger.error("Failed to upload backup for device %s: %s", device_id, exc)
        raise HTTPException(status_code=500, detail="Database write error")
    finally:
        conn.close()

@router.get("/api/sync/download")
def download_backup(request: Request):  # sync on purpose: sqlite work runs in the threadpool
    """
    Download the latest encrypted database payload.
    Checks the device backup first. If none exists and the device is linked to Google,
    retrieves the newest backup from any device linked to the same Google account.
    """
    device_id = getattr(request.state, "device_id", "")
    if not device_id:
        raise HTTPException(status_code=401, detail="Unauthorized: device_id missing")

    conn = get_conn()
    try:
        # Newest backup wins across BOTH the device's own row and any row on
        # the linked Google account. (Previously the device's own backup was
        # returned even when a sibling device had uploaded a newer one, so a
        # re-linking device could restore a stale copy forever.)
        row = conn.execute(
            """
            SELECT salt, nonce, payload, updated_at FROM user_backups
            WHERE device_id = ?
               OR (google_id IS NOT NULL AND google_id =
                     (SELECT google_id FROM identity_links WHERE device_id = ?))
            ORDER BY updated_at DESC LIMIT 1
            """,
            (device_id, device_id),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No backup found")

        return {
            "ok": True,
            "salt": row["salt"],
            "nonce": row["nonce"],
            "payload": row["payload"],
            "updated_at": row["updated_at"]
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to download backup for device %s: %s", device_id, exc)
        raise HTTPException(status_code=500, detail="Database read error")
    finally:
        conn.close()
