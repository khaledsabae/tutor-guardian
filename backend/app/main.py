"""
Tutor Guardian – FastAPI Application
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.guardrails_loader import load_guardrails_config
from app.db.init_db import init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.auth import AuthMiddleware
from app.routers import (
    health, assistant, chat, feedback, privacy, program, children, referral, push, identity,
    web, stats,
)
from app.services.push_sender import send_to_device
from app import curriculum_loader as curriculum

logger = logging.getLogger(__name__)

# Project root (…/tutor-guardian), overridable for containers.
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[2]))
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# CORS origins from env (comma-separated); defaults to local dev.
_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""

    # ── Base startup ─────────────────────────────────────────────────────
    app.state.guardrails_config = load_guardrails_config()
    init_db()
    curriculum.load_curriculum()

    # ── Warm-up: eager-load embeddings + ChromaDB index ──────────────────
    # Eliminates the 30-60s cold load on the first user request.
    try:
        from app.services.retrieval import _ensure_index
        from app.services.retrieval import _embedder as _warmup_embedder

        logger.info("🔥 Warm-up: loading ONNX embedder...")
        _warmup_embedder()  # trigger eager-load before _ensure_index uses it
        logger.info("🔥 Warm-up: ensuring ChromaDB index...")
        _ensure_index()
        logger.info("🔥 Warm-up: ChromaDB index ready (%s units loaded)", 
                     len(__import__('app.services.knowledge_loader', fromlist=['load_default_knowledge_units']).load_default_knowledge_units()))
    except Exception as e:
        logger.warning("Warm-up (embeddings): %s", e)

    # ── Warm-up: pre-load Ollama models ──────────────────────────────────
    # Sends a tiny request to each model to get them into GPU memory.
    _local_base = os.environ.get("OLLAMA_LOCAL_BASE_URL") or os.environ.get("OLLAMA_BASE_URL", "http://100.109.163.64:11434")
    ollama_url = f"{_local_base.rstrip('/')}/api/generate"
    fast_model = os.environ.get("OLLAMA_LOCAL_FAST_MODEL", "qwen2.5:3b")

    warmup_payload = {
        "model": fast_model,
        "prompt": "مرحباً",
        "stream": False,
        "options": {"num_predict": 1},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(ollama_url, json=warmup_payload)
            logger.info("🔥 Warm-up: Ollama %s ready (%s)", fast_model, r.status_code)
    except Exception as e:
        logger.warning("Warm-up (Ollama %s): %s", fast_model, e)

    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Tutor Guardian API",
    description="مساعد تربوي ذكي للأهل – واجهة API لنظام RAG مع Guardrails",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware — validates Bearer tokens on protected endpoints.
app.add_middleware(AuthMiddleware)

# Lightweight per-device rate limiting (falls back to per-IP if no token).
app.add_middleware(RateLimitMiddleware)

app.include_router(health.router)
app.include_router(assistant.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(program.router, prefix="/api")  # curriculum: paths/lessons/daily-tip
app.include_router(privacy.router)  # /privacy-policy (no /api prefix; public)
app.include_router(web.router)  # public SEO pages + share landing (/go, /l, /p; Phase 2)
app.include_router(children.router, prefix="/api")  # child profiles + progress (auth)
app.include_router(referral.router, prefix="/api")  # referral codes + attribution (auth)
app.include_router(stats.router, prefix="/api")  # community social-proof (public; Phase 3)
app.include_router(push.router, prefix="/api")  # FCM token storage (auth)
app.include_router(identity.router, prefix="/api")  # optional Google Sign-In (auth)

# ── Phase 1.1: admin push endpoint (for manual/cron sends) ─────────

@app.post("/api/admin/send-push")
def admin_send_push(request: Request, payload: dict) -> dict:
    """Manual push sender. Body: {device_id, title, body, data?}."""
    # Basic auth: require a configured admin key in header.
    expected = os.environ.get("TG_ADMIN_KEY", "")
    provided = request.headers.get("x-admin-key", "")
    if not expected or provided != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    result = send_to_device(
        device_id=payload.get("device_id", ""),
        title=payload.get("title", "المربّي"),
        body=payload.get("body", ""),
        data=payload.get("data"),
    )
    return result


DOCS_DIR = PROJECT_ROOT / "docs"
if DOCS_DIR.is_dir():
    app.mount("/docs", StaticFiles(directory=str(DOCS_DIR)), name="docs")

if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
