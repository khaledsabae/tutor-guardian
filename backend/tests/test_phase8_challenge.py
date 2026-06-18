"""
«رحلة الطفل» Phase 3 tests — the per-child "current challenge" and its
integration with the proactive coach.

Mounts the children router onto a minimal FastAPI app with a stubbed auth
middleware (sets request.state.device_id), mirroring test_phase6_streak.
"""
import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app import curriculum_loader as cl
from app.db.init_db import init_db
from app.routers.children import router as children_router
from app.services import coach_service as cs


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "phase8.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    init_db()
    return db


class _AuthStubMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, device_id: str = "test-device-001"):
        super().__init__(app)
        self.device_id = device_id

    async def dispatch(self, request: Request, call_next):
        request.state.device_id = self.device_id
        return await call_next(request)


@pytest.fixture
def app(tmp_db):
    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware)
    a.include_router(children_router, prefix="/api")
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
        json={"name": "سعد", "age_group": "7-9", "gender": "male"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_get_challenge_none_initially(client):
    cid = _create_child(client)
    r = client.get(f"/api/children/{cid}/challenge")
    assert r.status_code == 200
    assert r.json()["challenge"] is None


def test_set_and_get_challenge(client):
    cid = _create_child(client)
    r = client.put(
        f"/api/children/{cid}/challenge",
        json={"challenge_key": "sleep", "note": "بيرفض ينام بدري"},
    )
    assert r.status_code == 200
    ch = r.json()["challenge"]
    assert ch["challenge_key"] == "sleep"
    assert "نوم" in ch["topic"]

    r2 = client.get(f"/api/children/{cid}/challenge")
    active = r2.json()["challenge"]
    assert active["challenge_key"] == "sleep"
    assert active["note"] == "بيرفض ينام بدري"


def test_invalid_challenge_key_422(client):
    cid = _create_child(client)
    r = client.put(
        f"/api/children/{cid}/challenge",
        json={"challenge_key": "not_a_real_key"},
    )
    assert r.status_code == 422


def test_replacing_challenge_keeps_only_one_active(client):
    cid = _create_child(client)
    client.put(f"/api/children/{cid}/challenge", json={"challenge_key": "sleep"})
    client.put(f"/api/children/{cid}/challenge", json={"challenge_key": "lying"})
    active = client.get(f"/api/children/{cid}/challenge").json()["challenge"]
    assert active["challenge_key"] == "lying"


def test_delete_challenge_clears_it(client):
    cid = _create_child(client)
    client.put(f"/api/children/{cid}/challenge", json={"challenge_key": "screens"})
    r = client.delete(f"/api/children/{cid}/challenge")
    assert r.status_code == 200
    assert client.get(f"/api/children/{cid}/challenge").json()["challenge"] is None


def test_challenge_on_missing_child_404(client):
    r = client.put("/api/children/99999/challenge", json={"challenge_key": "sleep"})
    assert r.status_code == 404


def test_active_challenge_feeds_coach(client):
    """The active challenge must outrank the (absent) recent question and
    surface a topic-matched tip with the challenge frame."""
    cid = _create_child(client)
    client.put(f"/api/children/{cid}/challenge", json={"challenge_key": "sleep"})

    tip = asyncio.run(
        cs.get_proactive_tip("test-device-001", cid, mark_shown=False)
    )
    assert "نوم" in tip["text"]          # topic-matched advice
    assert "تحدّي" in tip["text"]        # honest challenge framing
