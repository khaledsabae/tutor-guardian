"""
Tutor Guardian – FastAPI Application
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config.guardrails_loader import load_guardrails_config
from app.db.init_db import init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.auth import AuthMiddleware
from app.routers import health, assistant, chat

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

if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
