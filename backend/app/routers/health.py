import os
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/api/health")
async def api_health_check():
    return {"status": "ok"}


@router.get("/api/app-config")
async def get_app_config():
    return {
        "minimum_build_number": int(os.environ.get("MINIMUM_BUILD_NUMBER", "0")),
        "store_url": os.environ.get("STORE_URL", "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi")
    }
