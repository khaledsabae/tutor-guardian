"""Tests for the «ميزان العادات» value-tracking API.

Uses a minimal FastAPI app with the value_tracking router only, plus the
same _AuthStubMiddleware pattern used in test_daily_routine.py.
"""
import sqlite3

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.init_db import init_db
from app.routers.children import router as children_router
from app.routers.value_tracking import router as value_router


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "habits.db"
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
    a.include_router(value_router, prefix="/api")
    return a


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _create_child(client, age_group="10-12") -> int:
    r = client.post("/api/children", json={"name": "أحمد", "age_group": age_group})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_get_today_empty(client):
    cid = _create_child(client)
    r = client.get("/api/value-tracking/today", params={"child_id": cid})
    assert r.status_code == 200
    body = r.json()
    assert body["child_id"] == cid
    assert body["events"] == []


def test_create_and_list_event(client):
    cid = _create_child(client)
    r = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "completed"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == "worship"
    assert body["habit_name"] == "صلاة الفجر"
    assert body["status"] == "completed"

    r2 = client.get("/api/value-tracking/today", params={"child_id": cid})
    assert len(r2.json()["events"]) == 1


def test_delete_event(client):
    cid = _create_child(client)
    created = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "study", "habit_name": "أداء الواجب", "status": "completed"},
    ).json()
    event_id = created["id"]
    r = client.delete(f"/api/value-tracking/events/{event_id}")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1


def test_summary(client):
    cid = _create_child(client)
    client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "completed"},
    )
    client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "study", "habit_name": "أداء الواجب", "status": "partially"},
    )
    client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "self_building", "habit_name": "التحكم بالغضب", "status": "missed"},
    )
    r = client.get("/api/value-tracking/summary", params={"child_id": cid, "days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["total_completed"] == 1
    assert body["total_partially"] == 1
    assert body["total_missed"] == 1
    assert body["by_category"]["worship"]["completed"] == 1
    assert body["by_category"]["study"]["partially"] == 1
    assert body["by_category"]["self_building"]["missed"] == 1


def test_rejects_invalid_category(client):
    cid = _create_child(client)
    r = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "sports", "habit_name": "تمرين", "status": "completed"},
    )
    assert r.status_code == 422


def test_rejects_invalid_status(client):
    cid = _create_child(client)
    r = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "worship", "habit_name": "صلاة", "status": "maybe"},
    )
    assert r.status_code == 422


def test_rejects_medical_terms_in_habit_name(client):
    cid = _create_child(client)
    r = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "self_building", "habit_name": "أخذ جرعة دواء", "status": "completed"},
    )
    assert r.status_code == 422


def test_rejects_wrong_age_group(client):
    """Habit tracking is for children 7–18 only."""
    cid = _create_child(client, age_group="4-6")
    r = client.get("/api/value-tracking/today", params={"child_id": cid})
    assert r.status_code == 400
    assert "7" in r.json()["detail"]


def test_7_9_age_group_allowed(client):
    """7-9 must use habit tracker, not routine."""
    cid = _create_child(client, age_group="7-9")
    r = client.get("/api/value-tracking/today", params={"child_id": cid})
    assert r.status_code == 200
    body = r.json()
    assert body["child_id"] == cid
    assert body["events"] == []
    assert body["points"] == 0.0


def test_points_calculation(client):
    """completed=1, partially=0.5, missed=0."""
    cid = _create_child(client, age_group="7-9")
    client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "completed"},
    )
    client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "study", "habit_name": "أداء الواجب", "status": "partially"},
    )
    client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "self_building", "habit_name": "النوم المبكر", "status": "missed"},
    )
    r = client.get("/api/value-tracking/today", params={"child_id": cid})
    assert r.json()["points"] == 1.5
    r2 = client.get("/api/value-tracking/summary", params={"child_id": cid, "days": 7})
    assert r2.json()["total_points"] == 1.5
    assert r2.json()["total_completed"] == 1
    assert r2.json()["total_partially"] == 1
    assert r2.json()["total_missed"] == 1


def test_nonexistent_child_id(client):
    r = client.get("/api/value-tracking/today", params={"child_id": 99999})
    assert r.status_code == 404


def test_other_device_cannot_access(client, tmp_db):
    cid = _create_child(client)
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
        ("other-device", "Other", "10-12"),
    )
    conn.commit()
    other_id = conn.execute(
        "SELECT id FROM child_profiles WHERE device_id = ?", ("other-device",)
    ).fetchone()[0]
    conn.close()
    r = client.get("/api/value-tracking/today", params={"child_id": other_id})
    assert r.status_code == 404


def test_requires_authentication(tmp_db):
    """Without the auth middleware the router must itself reject the request."""
    a = FastAPI()
    a.include_router(children_router, prefix="/api")
    a.include_router(value_router, prefix="/api")
    with TestClient(a) as c:
        r = c.get("/api/value-tracking/today", params={"child_id": 1})
        assert r.status_code == 401


def test_auth_middleware_protects_value_tracking(tmp_db):
    """With the real AuthMiddleware, /api/value-tracking/* rejects missing tokens."""
    from app.main import app as real_app
    with TestClient(real_app) as c:
        r = c.get("/api/value-tracking/today", params={"child_id": 1})
        assert r.status_code == 401
        assert "توثيق" in r.json()["detail"]