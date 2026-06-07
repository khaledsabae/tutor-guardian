"""
Tutor Guardian – FastAPI Application
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config.guardrails_loader import load_guardrails_config
from app.db.init_db import init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import health, assistant, chat

# Project root (…/tutor-guardian), overridable for containers.
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[2]))
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# CORS origins from env (comma-separated); defaults to local dev.
_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load guardrails config + ensure conversation DB schema
    app.state.guardrails_config = load_guardrails_config()
    init_db()
    yield
    # Shutdown: nothing to clean up for now


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

# Lightweight per-IP rate limiting on the assistant endpoints (no extra deps).
app.add_middleware(RateLimitMiddleware)

app.include_router(health.router)
app.include_router(assistant.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

if FRONTEND_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")


@app.get("/test", response_class=HTMLResponse)
async def test_ui():
    path = PROJECT_ROOT / "test_ui.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"))
