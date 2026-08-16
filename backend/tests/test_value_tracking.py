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
from app.routers.child_mode import router as child_mode_router
from app.routers.children import router as children_router
from app.routers.habit_templates import router as templates_router
from app.routers.value_tracking import router as value_router
from app.services import child_token


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
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Child-Bearer "):
            token = auth_header[13:].strip()
            payload = child_token.verify_child_token(token)
            if payload is None:
                from starlette.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "توكن وضع الطفل غير صالح"})
            request.state.child_mode = True
            request.state.device_id = payload["device_id"]
            request.state.child_id = payload["child_id"]
        else:
            request.state.device_id = self.device_id
        return await call_next(request)


@pytest.fixture
def app(tmp_db):
    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware)
    a.include_router(children_router, prefix="/api")
    a.include_router(value_router, prefix="/api")
    a.include_router(templates_router, prefix="/api")
    a.include_router(child_mode_router, prefix="/api")
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


# ── Custom habit template tests ──────────────────────────────────────────────


def _create_template(client, child_id, name, category="self_building"):
    r = client.post(
        "/api/habit-templates",
        params={"child_id": child_id},
        json={"category": category, "custom_name": name},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_custom_template(client):
    cid = _create_child(client)
    t = _create_template(client, cid, "مساعدة الوالدة")
    assert t["child_id"] == cid
    assert t["category"] == "self_building"
    assert t["custom_name"] == "مساعدة الوالدة"
    assert t["is_active"] is True


def test_duplicate_template_name_rejected(client):
    cid = _create_child(client)
    _create_template(client, cid, "مساعدة الوالدة")
    r = client.post(
        "/api/habit-templates",
        params={"child_id": cid},
        json={"category": "self_building", "custom_name": "مساعدة الوالدة"},
    )
    assert r.status_code == 409


def test_list_templates_and_filter_active(client):
    cid = _create_child(client)
    a = _create_template(client, cid, "مساعدة الوالدة")
    b = _create_template(client, cid, "تمرين السباحة")
    client.patch(f"/api/habit-templates/{b['id']}", json={"is_active": False})
    r = client.get("/api/habit-templates", params={"child_id": cid})
    assert len(r.json()) == 2
    r2 = client.get("/api/habit-templates", params={"child_id": cid, "active_only": True})
    assert len(r2.json()) == 1
    assert r2.json()[0]["custom_name"] == "مساعدة الوالدة"


def test_soft_delete_keeps_history(client, tmp_db):
    cid = _create_child(client, age_group="10-12")
    t = _create_template(client, cid, "تمرين السباحة")
    # Record an event before archiving.
    client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "self_building", "habit_name": "تمرين السباحة", "status": "completed"},
    )
    # Archive the template.
    r = client.patch(f"/api/habit-templates/{t['id']}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    # Historical event is still present.
    r2 = client.get("/api/value-tracking/today", params={"child_id": cid})
    assert r2.json()["points"] == 1.0


def test_today_merges_defaults_and_active_customs(client):
    cid = _create_child(client, age_group="10-12")
    _create_template(client, cid, "تمرين السباحة", category="self_building")
    r = client.get("/api/value-tracking/today", params={"child_id": cid})
    body = r.json()
    names = {h["habit_name"] for h in body["habits"]}
    assert "صلاة الفجر" in names
    assert "تمرين السباحة" in names
    sources = {h["habit_name"]: h["source"] for h in body["habits"]}
    assert sources["صلاة الفجر"] == "default"
    assert sources["تمرين السباحة"] == "custom"


def test_event_for_archived_custom_rejected(client):
    cid = _create_child(client, age_group="10-12")
    t = _create_template(client, cid, "تمرين السباحة")
    client.patch(f"/api/habit-templates/{t['id']}", json={"is_active": False})
    r = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "self_building", "habit_name": "تمرين السباحة", "status": "completed"},
    )
    assert r.status_code == 400


def test_event_for_unknown_habit_rejected(client):
    cid = _create_child(client, age_group="10-12")
    r = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "self_building", "habit_name": "عادة غير موجودة", "status": "completed"},
    )
    assert r.status_code == 400


def test_custom_template_requires_auth(tmp_db):
    from app.main import app as real_app
    with TestClient(real_app) as c:
        r = c.get("/api/habit-templates", params={"child_id": 1})
        assert r.status_code == 401
        assert "توثيق" in r.json()["detail"]


# ── Child mode tests ─────────────────────────────────────────────────────────


def _sign_family_agreement(child_id: int, device_id: str = "test-device-001") -> None:
    """Since Sprint 2 a signed media agreement is an entry condition for any
    band that has a clause bank, and child mode issues no token without one.
    These tests are about habits, so they start past that gate."""
    from app.core.taxonomy import map_profile_age_to_band
    from app.services import family_agreement

    band = map_profile_age_to_band(_child_age_group(child_id))
    clauses = family_agreement.suggested_clauses(band)[:4] \
        or family_agreement.suggested_clauses("7-9")[:4]
    family_agreement.save_draft(device_id, child_id, clauses)
    current = family_agreement.get_current(device_id, child_id)
    for c in current["clauses"]:
        if c["applies_to"] in ("child", "both"):
            family_agreement.acknowledge_clause(device_id, child_id, c["id"])
    family_agreement.sign(device_id, child_id, "parent")
    family_agreement.sign(device_id, child_id, "child")


def _child_age_group(child_id: int) -> str:
    from app.db.init_db import get_conn
    conn = get_conn()
    try:
        row = conn.execute("SELECT age_group FROM child_profiles WHERE id = ?",
                           (child_id,)).fetchone()
        return row["age_group"] if row else "7-9"
    finally:
        conn.close()


def _issue_child_token(client, child_id) -> str:
    _sign_family_agreement(child_id)
    r = client.post(
        "/api/value-tracking/child-sessions",
        params={"child_id": child_id},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_child_session_issued_by_parent(client):
    cid = _create_child(client, age_group="7-9")
    token = _issue_child_token(client, cid)
    assert token
    payload = child_token.verify_child_token(token)
    assert payload is not None
    assert payload["child_id"] == cid
    assert payload["scope"] == "habit_child"


def test_child_mode_today_returns_merged_habits(client):
    cid = _create_child(client, age_group="7-9")
    token = _issue_child_token(client, cid)
    r = client.get(
        "/api/value-tracking/child-mode/today",
        headers={"Authorization": f"Child-Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["child_id"] == cid
    names = {h["habit_name"] for h in body["habits"]}
    assert "صلاة الفجر" in names
    assert "النوم المبكر" in names


def test_child_mode_records_event_submit_only(client):
    cid = _create_child(client, age_group="7-9")
    token = _issue_child_token(client, cid)
    headers = {"Authorization": f"Child-Bearer {token}"}
    r = client.post(
        "/api/value-tracking/child-mode/events",
        headers=headers,
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "completed"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["child_id"] == cid
    assert body["submitted_by"] == "child"
    assert body["device_timestamp"] is not None
    # Submit-only: second attempt for the same habit today is rejected.
    r2 = client.post(
        "/api/value-tracking/child-mode/events",
        headers=headers,
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "partially"},
    )
    assert r2.status_code == 409


def test_child_mode_event_inherits_parent_view_as_child_source(client):
    cid = _create_child(client, age_group="7-9")
    token = _issue_child_token(client, cid)
    client.post(
        "/api/value-tracking/child-mode/events",
        headers={"Authorization": f"Child-Bearer {token}"},
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "completed"},
    )
    # Parent-facing today view exposes the event with submitted_by child.
    r = client.get("/api/value-tracking/today", params={"child_id": cid})
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) == 1
    assert events[0]["submitted_by"] == "child"


def test_parent_event_defaults_to_submitted_by_parent(client):
    cid = _create_child(client, age_group="7-9")
    r = client.post(
        "/api/value-tracking/events",
        params={"child_id": cid},
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "completed"},
    )
    assert r.status_code == 200
    assert r.json()["submitted_by"] == "parent"


def test_child_mode_event_rejects_missing_device_timestamp(client):
    cid = _create_child(client, age_group="7-9")
    token = _issue_child_token(client, cid)
    r = client.post(
        "/api/value-tracking/child-mode/events",
        headers={"Authorization": f"Child-Bearer {token}"},
        json={"category": "worship", "habit_name": "صلاة الفجر", "status": "completed"},
    )
    assert r.status_code == 200
    assert r.json()["device_timestamp"] is not None


def test_child_mode_rejects_unknown_habit(client):
    cid = _create_child(client, age_group="7-9")
    token = _issue_child_token(client, cid)
    r = client.post(
        "/api/value-tracking/child-mode/events",
        headers={"Authorization": f"Child-Bearer {token}"},
        json={"category": "worship", "habit_name": "عادة غير موجودة", "status": "completed"},
    )
    assert r.status_code == 400


def test_child_mode_requires_child_bearer_header(client):
    r = client.get("/api/value-tracking/child-mode/today")
    assert r.status_code == 401


def test_child_mode_rejects_parent_bearer_token(client):
    cid = _create_child(client, age_group="7-9")
    r = client.get(
        "/api/value-tracking/child-mode/today",
        headers={"Authorization": "Bearer fake-parent-token"},
    )
    assert r.status_code == 401


def test_child_mode_cannot_access_parent_routes(client):
    cid = _create_child(client, age_group="7-9")
    token = _issue_child_token(client, cid)
    # Parent routes accept Child-Bearer header in the stub middleware, but
    # the production AuthMiddleware only allows Child-Bearer on /child-mode/*.
    from app.main import app as real_app
    with TestClient(real_app) as c:
        r = c.get(
            "/api/value-tracking/summary",
            headers={"Authorization": f"Child-Bearer {token}"},
            params={"child_id": cid},
        )
        assert r.status_code == 401