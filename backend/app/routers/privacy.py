"""
Privacy router.

Serves the static privacy-policy.md at GET /privacy-policy.
Required by Google Play for the data-safety form.

The file path is resolved relative to PROJECT_ROOT (the repo root) so the
content is served from the deployed repo, not bundled into the Docker image.

And `api_router` (mounted under /api, Bearer auth) holds the delete-all path:
DELETE /api/privacy/memory erases everything the assistant has learned about
the caller's children — every table in MEMORY_TABLES. A table that stores
per-device memory and is missing from that tuple survives a parent's "forget
everything"; tests/test_child_memory.py fails if a v30 table is left out.
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter()
api_router = APIRouter()

# Every table holding what the assistant learned about a device's children,
# with the column that scopes a row to the device. Schema v30.
MEMORY_TABLES: tuple[tuple[str, str], ...] = (
    ("child_facts", "device_id"),
    ("followups", "device_id"),
    ("weekly_plans", "device_id"),
    ("child_memory_settings", "device_id"),
)


def erase_device_memory(device_id: str) -> dict[str, int]:
    """Delete every MEMORY_TABLES row of one device, in one transaction."""
    conn = get_conn()
    try:
        counts: dict[str, int] = {}
        conn.execute("BEGIN")
        for table, column in MEMORY_TABLES:
            cur = conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (device_id,))
            counts[table] = cur.rowcount
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@api_router.delete("/privacy/memory", summary="Forget everything about my children")
def delete_my_memory(request: Request):
    """The privacy delete-all for child memory: facts, follow-ups, weekly plans
    and the memory switch itself, for every child of the calling device."""
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    counts = erase_device_memory(device_id)
    logger.info("privacy: device memory erased (%d rows)", sum(counts.values()))
    return {
        "deleted": counts,
        "deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

# Project root (…/tutor-guardian), overridable for containers.
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[3]))
_PRIVACY_CANDIDATES = [
    PROJECT_ROOT / "docs" / "privacy-policy.md",
    Path(__file__).resolve().parents[2] / "docs" / "privacy-policy.md",  # /app/docs/ inside container
    Path(__file__).resolve().parents[3] / "docs" / "privacy-policy.md",
]


def _is_servable(path: Path) -> bool:
    """Existing is not enough — the file has to be *readable* by this process.

    docs/ is bind-mounted into the container from the host, and the container
    runs as appuser (uid 10001) while the host files arrive by rsync owning
    uid 1000 mode 0600. `is_file()` still passes on those (the directory is
    traversable), so a bare existence check let FileResponse start a 200,
    fail to open the file, and emit a truncated body — which Cloudflare turned
    into an opaque 520. Checking readability makes that an honest 503 instead.
    """
    return path.is_file() and os.access(path, os.R_OK)


def _resolve_privacy_policy_path() -> Path:
    """Find privacy-policy.md across the candidate locations.

    The container image has docs/ at /app/docs/, while dev mode puts it at
    PROJECT_ROOT/docs/. We try the env-driven path first, then fall back.
    """
    for candidate in _PRIVACY_CANDIDATES:
        if _is_servable(candidate):
            return candidate
    return _PRIVACY_CANDIDATES[0]  # default; endpoint will return 503


PRIVACY_POLICY_PATH = _resolve_privacy_policy_path()


@router.get("/privacy-policy", include_in_schema=False)
async def get_privacy_policy():
    """Serve the privacy policy as plain text/markdown."""
    # Re-checked per request, not just at import: docs/ is a bind mount whose
    # permissions can change under a running container.
    if not _is_servable(PRIVACY_POLICY_PATH):
        if PRIVACY_POLICY_PATH.is_file():
            logger.error(
                "Privacy policy file at %s exists but is not readable by uid %s",
                PRIVACY_POLICY_PATH,
                os.getuid(),
            )
        else:
            logger.error("Privacy policy file not found at %s", PRIVACY_POLICY_PATH)
        return Response(
            content="Privacy policy is temporarily unavailable. Please contact support@alsaba.cloud.",
            status_code=503,
            media_type="text/plain; charset=utf-8",
        )
    return FileResponse(
        path=str(PRIVACY_POLICY_PATH),
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )
