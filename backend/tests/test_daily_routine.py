"""Tests for the «حِساب اليوم» daily-routine API.

Uses a minimal FastAPI app with the daily_routine router only, plus the
same _AuthStubMiddleware pattern used in test_phase7_settings.py.
"""
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.init_db import init_db
from app.routers.children import router as children_router
from app.routers.daily_routine import router as routine_router


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

    async def dispatch(self, request: Request, call_next):
        request.state.device_id = self.device_id
        return await call_next(request)


@pytest.fixture
def app(tmp_db):
    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware)
    a.include_router(children_router, prefix="/api")
    a.include_router(routine_router, prefix="/api")
    return a


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _create_child(client) -> int:
    r = client.post("/api/children", json={"name": "سارة", "age_group": "4-6"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_get_today_creates_empty_routine(client):
    cid = _create_child(client)
    r = client.get("/api/daily-routine/today", params={"child_id": cid})
    assert r.status_code == 200
    body = r.json()
    assert body["child_id"] == cid
    assert body["events"] == []


def test_create_and_list_event(client):
    cid = _create_child(client)
    iso = datetime.now(timezone.utc).isoformat()
    r = client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "feed", "started_at": iso, "feed_type": "breast", "side": "left"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["event_type"] == "feed"
    assert body["feed_type"] == "breast"
    assert body["side"] == "left"

    r2 = client.get("/api/daily-routine/today", params={"child_id": cid})
    assert len(r2.json()["events"]) == 1


def test_update_event(client):
    cid = _create_child(client)
    iso = datetime.now(timezone.utc).isoformat()
    created = client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "sleep", "started_at": iso, "ended_at": iso},
    ).json()
    event_id = created["id"]
    r = client.patch(
        f"/api/daily-routine/events/{event_id}",
        json={"event_type": "diaper", "started_at": iso, "diaper_type": "wet"},
    )
    assert r.status_code == 200
    assert r.json()["event_type"] == "diaper"


def test_delete_event(client):
    cid = _create_child(client)
    iso = datetime.now(timezone.utc).isoformat()
    created = client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "diaper", "started_at": iso, "diaper_type": "both"},
    ).json()
    event_id = created["id"]
    r = client.delete(f"/api/daily-routine/events/{event_id}")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1


def test_summary(client):
    cid = _create_child(client)
    iso = datetime.now(timezone.utc).isoformat()
    client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "feed", "started_at": iso, "amount_ml": 120},
    )
    client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "diaper", "started_at": iso, "diaper_type": "wet"},
    )
    r = client.get("/api/daily-routine/summary", params={"child_id": cid, "days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["total_feed_count"] == 1
    assert body["total_feed_amount_ml"] == 120
    assert body["diaper_count"] == 1


def test_rejects_medical_notes(client):
    cid = _create_child(client)
    iso = datetime.now(timezone.utc).isoformat()
    r = client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "feed", "started_at": iso, "notes": "أخذ جرعة دواء الحمى"},
    )
    assert r.status_code == 422


def test_invalid_datetime_format(client):
    cid = _create_child(client)
    r = client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "feed", "started_at": "not-an-iso-timestamp"},
    )
    assert r.status_code == 422


def test_nonexistent_child_id(client):
    iso = datetime.now(timezone.utc).isoformat()
    r = client.get("/api/daily-routine/today", params={"child_id": 99999})
    assert r.status_code == 404

    r2 = client.post(
        "/api/daily-routine/events",
        params={"child_id": 99999},
        json={"event_type": "feed", "started_at": iso},
    )
    assert r2.status_code == 404


def test_invalid_event_type(client):
    cid = _create_child(client)
    iso = datetime.now(timezone.utc).isoformat()
    r = client.post(
        "/api/daily-routine/events",
        params={"child_id": cid},
        json={"event_type": "growth", "started_at": iso},
    )
    assert r.status_code == 422


def test_other_device_cannot_access(client, tmp_db):
    cid = _create_child(client)
    # The device_id is test-device-001; create a different child under another device directly in DB
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
        ("other-device", "Other", "4-6"),
    )
    conn.commit()
    other_id = conn.execute(
        "SELECT id FROM child_profiles WHERE device_id = ?", ("other-device",)
    ).fetchone()[0]
    conn.close()
    r = client.get("/api/daily-routine/today", params={"child_id": other_id})
    assert r.status_code == 404


def test_requires_authentication(tmp_db):
    """Without the auth middleware the router must itself reject the request."""
    a = FastAPI()
    a.include_router(children_router, prefix="/api")
    a.include_router(routine_router, prefix="/api")
    with TestClient(a) as c:
        r = c.get("/api/daily-routine/today", params={"child_id": 1})
        assert r.status_code == 401


def test_auth_middleware_protects_daily_routine(tmp_db):
    """With the real AuthMiddleware, /api/daily-routine/* rejects missing tokens."""
    from app.main import app as real_app
    with TestClient(real_app) as c:
        r = c.get("/api/daily-routine/today", params={"child_id": 1})
        assert r.status_code == 401
        assert "توثيق" in r.json()["detail"]
