import pytest
from datetime import datetime, timezone
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

@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c

def _create_child(client) -> int:
    r = client.post("/api/children", json={"name": "سارة", "age_group": "4-6"})
    assert r.status_code == 201
    return r.json()["id"]

def test_parenting_insights(client):
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
