"""
Privacy policy router.

Serves the static privacy-policy.md at GET /privacy-policy.
Required by Google Play for the data-safety form.

The file path is resolved relative to PROJECT_ROOT (the repo root) so the
content is served from the deployed repo, not bundled into the Docker image.
"""
import logging
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter()

# Project root (…/tutor-guardian), overridable for containers.
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[3]))
_PRIVACY_CANDIDATES = [
    PROJECT_ROOT / "docs" / "privacy-policy.md",
    Path(__file__).resolve().parents[2] / "docs" / "privacy-policy.md",  # /app/docs/ inside container
    Path(__file__).resolve().parents[3] / "docs" / "privacy-policy.md",
]


def _resolve_privacy_policy_path() -> Path:
    """Find privacy-policy.md across the candidate locations.

    The container image has docs/ at /app/docs/, while dev mode puts it at
    PROJECT_ROOT/docs/. We try the env-driven path first, then fall back.
    """
    for candidate in _PRIVACY_CANDIDATES:
        if candidate.is_file():
            return candidate
    return _PRIVACY_CANDIDATES[0]  # default; endpoint will return 503


PRIVACY_POLICY_PATH = _resolve_privacy_policy_path()


@router.get("/privacy-policy", include_in_schema=False)
async def get_privacy_policy():
    """Serve the privacy policy as plain text/markdown."""
    if not PRIVACY_POLICY_PATH.is_file():
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
