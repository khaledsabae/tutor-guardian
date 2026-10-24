import os
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    """Deep health check — verifies SQLite and ChromaDB readiness."""
    checks: dict = {}

    # 1. SQLite connectivity
    try:
        from app.db.init_db import get_conn
        conn = get_conn()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["sqlite"] = "ok"
    except Exception as e:
        logger.error("Health check: SQLite failure — %s", e)
        checks["sqlite"] = f"error: {e}"

    # 2. ChromaDB readiness (non-blocking — only if index is already loaded)
    try:
        from app.services.retrieval import _get_collection
        col = _get_collection()
        if col is not None:
            col.count()
            checks["chromadb"] = "ok"
        else:
            checks["chromadb"] = "not_loaded"
    except Exception as e:
        logger.warning("Health check: ChromaDB not ready — %s", e)
        checks["chromadb"] = f"not_ready: {e}"

    # 3. The reranker's own kill switch. It turns itself off for the life of the
    # process after repeated slow calls, and it takes the off-topic filter with
    # it — so the app answers from raw retrieval order with no topic check while
    # nothing anywhere says so. Degraded, not down: answers still come out.
    try:
        from app.services.reranker import is_disabled
        checks["reranker"] = "disabled_after_strikes" if is_disabled() else "ok"
    except Exception as e:  # noqa: BLE001
        checks["reranker"] = f"unknown: {e}"

    # Return 500 only if SQLite is broken — ChromaDB degraded is acceptable.
    if "error" in checks.get("sqlite", ""):
        return JSONResponse(status_code=500, content={"status": "down", "checks": checks})

    return {"status": "ok", "checks": checks}


@router.get("/api/health")
async def api_health_check():
    return {"status": "ok"}


def _support_config() -> dict:
    """The «ادعم المربّي» fields, which must never cost the force-update gate.

    This endpoint is how every build learns whether it must update, so nothing
    optional may make it fail. donations.is_enabled() is computed once per
    process and already degrades to False; the guard here covers the import
    and anything future. Additive (v31): older builds ignore both fields.
    """
    try:
        from app.services import donations

        return {
            "donations_enabled": donations.is_enabled(),
            "donation_product_ids": list(donations.product_ids()),
        }
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "support config unavailable (%s) — reported as off", type(exc).__name__)
        return {"donations_enabled": False, "donation_product_ids": []}


@router.get("/api/app-config")
async def get_app_config():
    from app.services import erased_devices

    return {
        "minimum_build_number": int(os.environ.get("MINIMUM_BUILD_NUMBER", "0")),
        "store_url": os.environ.get("STORE_URL", "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"),
        # The first build the session mint answers `410 device_erased` (null =
        # none yet): only for such a build is a 201 proof that a device id was
        # NOT erased — what settling a lost account deletion relies on.
        "erased_device_410_min_build": erased_devices.min_build(),
        **_support_config(),
        # «نور يتذكّر» kill switch (phase 2): the companion header on Today.
        # Default on; NOOR_HEADER_ENABLED=0 in .env turns every installed
        # build back to the plain greeting row — no release needed.
        "noor_header_enabled": os.environ.get(
            "NOOR_HEADER_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off"),
        # «على الأفق» kill switch («عالم الأسرة»): the one-line strip on Today
        # that points at the family road's nearest gate. Default on;
        # HORIZON_STRIP_ENABLED=0 hides it on every installed build.
        "horizon_strip_enabled": os.environ.get(
            "HORIZON_STRIP_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off"),
        # «صورة حيّة» experiment (2026-10-24): "ab" = every device keeps the
        # arm its id hashes to (living pictures vs the same paintings still);
        # "motion" / "static" = everyone gets that one. After the month the
        # winner is set with STORY_MOTION_MODE in .env — no release needed.
        "story_motion_mode": story_motion_mode(),
    }


def story_motion_mode() -> str:
    """STORY_MOTION_MODE, or "ab" for anything unset or unknown."""
    mode = os.environ.get("STORY_MOTION_MODE", "ab").strip().lower()
    return mode if mode in ("ab", "motion", "static") else "ab"
