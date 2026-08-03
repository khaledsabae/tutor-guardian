"""
Coach tip tap endpoint tests — guards against mobile crash on stale tap.

The POST /api/program/coach-tip/{tip_id}/tap endpoint records an analytics
tap. It must never return 404 because the Flutter client crashes on 404.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app import curriculum_loader as cl
from app.db.init_db import init_db
from app.routers.children import router as children_router
from app.routers.program import router as program_router


class _AuthStubMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, device_id: str = "test-device-001"):
        super().__init__(app)
        self.device_id = device_id

    async def dispatch(self, request: Request, call_next):
        request.state.device_id = self.device_id
        return await call_next(request)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "coach_tap.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    init_db()
    return db


@pytest.fixture
def app(tmp_db):
    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware)
    a.include_router(children_router, prefix="/api")
    a.include_router(program_router, prefix="/api")
    return a


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _ensure_loaded():
    cl.load_curriculum()


def _create_child(client) -> int:
    r = client.post(
        "/api/children",
        json={"name": "سارة", "age_group": "4-6", "avatar_emoji": "👧"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_tap_coach_tip_returns_ok(client):
    """Happy path: tapping an existing tip succeeds."""
    child_id = _create_child(client)
    r = client.get("/api/program/coach-tip", params={"child_id": child_id})
    assert r.status_code == 200
    tip_id = r.json()["id"]

    r2 = client.post(f"/api/program/coach-tip/{tip_id}/tap")
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


def test_tap_missing_coach_tip_returns_ok_not_404(client):
    """Stale/missing tip_id must not crash the mobile app with a 404."""
    r = client.post("/api/program/coach-tip/999999/tap")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_tap_other_device_tip_returns_ok_not_404(client):
    """Tapping a tip belonging to another device must not crash the app."""
    child_id = _create_child(client)
    r = client.get("/api/program/coach-tip", params={"child_id": child_id})
    assert r.status_code == 200
    tip_id = r.json()["id"]

    # Switch device_id via a fresh app+client that reuses the same DB.
    a2 = FastAPI()
    a2.add_middleware(_AuthStubMiddleware, device_id="other-device")
    a2.include_router(program_router, prefix="/api")
    with TestClient(a2) as c2:
        r2 = c2.post(f"/api/program/coach-tip/{tip_id}/tap")
        assert r2.status_code == 200
        assert r2.json()["ok"] is True


def test_tap_coach_tip_requires_auth(client):
    """Without device_id the endpoint must still require authentication."""
    a = FastAPI()
    a.include_router(program_router, prefix="/api")
    with TestClient(a) as c:
        r = c.post("/api/program/coach-tip/1/tap")
        assert r.status_code == 401
