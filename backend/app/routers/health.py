import os
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
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

    # Return 500 only if SQLite is broken — ChromaDB degraded is acceptable.
    if "error" in checks.get("sqlite", ""):
        return JSONResponse(status_code=500, content={"status": "down", "checks": checks})

    return {"status": "ok", "checks": checks}


@router.get("/api/health")
async def api_health_check():
    return {"status": "ok"}


@router.get("/api/app-config")
async def get_app_config():
    return {
        "minimum_build_number": int(os.environ.get("MINIMUM_BUILD_NUMBER", "0")),
        "store_url": os.environ.get("STORE_URL", "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi")
    }
