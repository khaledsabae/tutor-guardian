import json
import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.init_db import init_db
from app.routers.children import router as children_router
from app.routers.daily_routine import router as routine_router
from app.routers.insights import router as insights_router

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "routine.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    init_db()
    return db

class _AuthStubMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, device_id: str = "test-device-001"):
        super().__init__(app)
        self.device_id = device_id

    async def dispatch(self, request, call_next):
        request.state.device_id = self.device_id
        return await call_next(request)

@pytest.fixture
def app(tmp_db):
    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware)
    a.include_router(children_router, prefix="/api")
    a.include_router(routine_router, prefix="/api")
    a.include_router(insights_router, prefix="/api")
    return a

class _FakeGateway:
    """Stands in for the LLM chain so the test never waits on real providers
    (the live chain spent ~3 min timing out per run on CI)."""

    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, 0

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(text=self.text)


_LLM_INSIGHTS = [
    {"title": f"t{i}", "description": "d", "category": "نوم", "type": kind}
    for i, kind in enumerate(["positive", "tip", "warning"])
]


@pytest.fixture
def fake_gateway(monkeypatch):
    gw = _FakeGateway(text="```json\n" + json.dumps(_LLM_INSIGHTS, ensure_ascii=False) + "\n```")
    monkeypatch.setattr("app.routers.insights.get_gateway", lambda: gw)
    return gw


@pytest.fixture
def client(app, fake_gateway):
    with TestClient(app) as c:
        yield c

def _create_child(client) -> int:
    r = client.post("/api/children", json={"name": "سارة", "age_group": "4-6"})
    assert r.status_code == 201
    return r.json()["id"]

def test_parenting_insights(client, fake_gateway):
    cid = _create_child(client)
    iso = datetime.now(timezone.utc).isoformat()
    
    # Log a few routine events
    client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "feed", "started_at": iso, "amount_ml": 120},
    )
    client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "sleep", "started_at": iso, "ended_at": iso},
    )

    r = client.get("/api/insights/parenting", params={"child_id": cid})
    assert r.status_code == 200
    body = r.json()
    assert "insights" in body
    assert len(body["insights"]) >= 3
    for insight in body["insights"]:
        assert "title" in insight
        assert "description" in insight
        assert "category" in insight
        assert "type" in insight
        assert insight["type"] in ["positive", "tip", "warning"]
    assert fake_gateway.calls == 1
    assert body["insights"] == _LLM_INSIGHTS


def test_parenting_insights_falls_back_when_llm_fails(client, fake_gateway):
    fake_gateway.error = RuntimeError("all providers failed")
    cid = _create_child(client)

    r = client.get("/api/insights/parenting", params={"child_id": cid})
    assert r.status_code == 200
    insights = r.json()["insights"]
    assert len(insights) >= 3
    assert all(i["type"] in ["positive", "tip", "warning"] for i in insights)
