"""
Tutor Guardian – FastAPI Application
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config.guardrails_loader import load_guardrails_config
from app.db.init_db import init_db
from app.routers import health, assistant, chat


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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(assistant.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

app.mount("/ui", StaticFiles(directory="/home/khalednew/projects/tutor-guardian/frontend", html=True), name="static")

@app.get("/test", response_class=HTMLResponse)
async def test_ui():
    path = "/home/khalednew/projects/tutor-guardian/test_ui.html"
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
