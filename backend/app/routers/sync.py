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
    salt: str = Field(..., min_length=1, description="Base64 encoded key derivation salt")
    nonce: str = Field(..., min_length=1, description="Base64 encoded AES-GCM nonce")
    payload: str = Field(..., min_length=1, description="Base64 encoded encrypted database bytes")

@router.post("/api/sync/upload")
async def upload_backup(request: Request, payload: BackupUploadRequest):
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
async def download_backup(request: Request):
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
        # 1. Try to fetch direct device backup
        row = conn.execute(
            "SELECT salt, nonce, payload, updated_at FROM user_backups WHERE device_id = ?",
            (device_id,)
        ).fetchone()

        # 2. If not found, check Google link and find newest backup for the linked Google ID
        if not row:
            link = conn.execute(
                "SELECT google_id FROM identity_links WHERE device_id = ?",
                (device_id,)
            ).fetchone()
            if link:
                google_id = link["google_id"]
                row = conn.execute(
                    """
                    SELECT salt, nonce, payload, updated_at FROM user_backups
                    WHERE google_id = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (google_id,)
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
