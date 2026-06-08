"""
Phase 7 tests — list / update / reset-progress on /api/children/*.

Mounts children + program routers on a minimal FastAPI app so the
heavy RAG stack is never imported. A tiny middleware sets
`request.state.device_id` to simulate what AuthMiddleware would do
after Bearer validation.
"""
import sqlite3
from datetime import date, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app import curriculum_loader as cl
from app.db.init_db import init_db
from app.routers.children import router as children_router
from app.routers.program import router as program_router


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "phase7.db"
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
    a.include_router(program_router, prefix="/api")
    return a


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _ensure_loaded():
    cl.load_curriculum()


def _create_child(client, **overrides) -> int:
    body = {"name": "سارة", "age_group": "4-6", "avatar_emoji": "👧"}
    body.update(overrides)
    r = client.post("/api/children", json=body)
    assert r.status_code == 201
    return r.json()["id"]


# ── GET /api/children (list) ─────────────────────────────────────────────


def test_list_children_empty(client):
    r = client.get("/api/children")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["children"] == []
    assert body["device_id"] == "test-device-001"


def test_list_children_returns_all_owned(client):
    _create_child(client, name="سارة", age_group="4-6")
    _create_child(client, name="أحمد", age_group="7-9")
    r = client.get("/api/children")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    names = {c["name"] for c in body["children"]}
    assert names == {"سارة", "أحمد"}


def test_list_children_excludes_other_devices(client, tmp_db):
    """A second device's children must NOT leak into the first list."""
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) "
            "VALUES (?, ?, ?)",
            ("other-device", "Other", "4-6"),
        )
        conn.commit()
    finally:
        conn.close()
    r = client.get("/api/children")
    assert r.json()["count"] == 0


# ── PATCH /api/children/{id} (update) ────────────────────────────────────


def test_update_child_name_only(client):
    cid = _create_child(client, name="سارة")
    r = client.patch(f"/api/children/{cid}", json={"name": "سارة الصغيرة"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "سارة الصغيرة"
    assert body["age_group"] == "4-6"  # unchanged
    assert body["avatar_emoji"] == "👧"  # unchanged


def test_update_child_age_group_changes_path_pool(client):
    """Updating age_group should affect what the curriculum serves.

    Phase 7 doesn't expose a 'which age_group has which paths' endpoint,
    so we just verify the row is updated and the response reflects it.
    """
    cid = _create_child(client, age_group="4-6")
    r = client.patch(f"/api/children/{cid}", json={"age_group": "7-9"})
    assert r.status_code == 200
    assert r.json()["age_group"] == "7-9"


def test_update_child_avatar_emoji(client):
    cid = _create_child(client, avatar_emoji="👧")
    r = client.patch(f"/api/children/{cid}", json={"avatar_emoji": "🧒🏽"})
    assert r.status_code == 200
    assert r.json()["avatar_emoji"] == "🧒🏽"


def test_update_child_all_fields_at_once(client):
    cid = _create_child(client, name="سارة", age_group="4-6", avatar_emoji="👧")
    r = client.patch(
        f"/api/children/{cid}",
        json={
            "name": "ليلى",
            "age_group": "7-9",
            "gender": "female",
            "avatar_emoji": "🧒",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "ليلى"
    assert body["age_group"] == "7-9"
    assert body["gender"] == "female"
    assert body["avatar_emoji"] == "🧒"


def test_update_child_empty_payload_is_422(client):
    cid = _create_child(client)
    r = client.patch(f"/api/children/{cid}", json={})
    assert r.status_code == 422
    assert "حقل" in r.text or "على الأقل" in r.text


def test_update_child_invalid_age_group_is_422(client):
    cid = _create_child(client)
    r = client.patch(f"/api/children/{cid}", json={"age_group": "99-100"})
    assert r.status_code == 422


def test_update_child_blank_name_is_422(client):
    cid = _create_child(client)
    r = client.patch(f"/api/children/{cid}", json={"name": "   "})
    assert r.status_code == 422


def test_update_child_non_emoji_avatar_is_422(client):
    cid = _create_child(client)
    r = client.patch(
        f"/api/children/{cid}", json={"avatar_emoji": "hello world"}
    )
    assert r.status_code == 422


def test_update_child_404_for_other_device(client, tmp_db):
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) "
            "VALUES (?, ?, ?)",
            ("other-device", "Other", "4-6"),
        )
        conn.commit()
    finally:
        conn.close()
    r = client.patch("/api/children/1", json={"name": "hacked"})
    assert r.status_code == 404


def test_update_child_404_for_nonexistent(client):
    r = client.patch("/api/children/9999", json={"name": "ghost"})
    assert r.status_code == 404


# ── DELETE /api/children/{id}/progress (reset) ──────────────────────────


def test_reset_progress_returns_zero_when_no_progress(client):
    cid = _create_child(client)
    r = client.delete(f"/api/children/{cid}/progress")
    assert r.status_code == 200
    body = r.json()
    assert body["child_id"] == cid
    assert body["deleted"] == 0


def test_reset_progress_deletes_lesson_progress(client, tmp_db):
    cid = _create_child(client)
    # Seed a completed lesson
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            """
            INSERT INTO lesson_progress
                (device_id, lesson_id, path_id, status, completed_at)
            VALUES (?, ?, ?, 'completed', ?)
            """,
            (
                "test-device-001",
                "lesson_4-6_islamic_parenting_adab_01",
                "path_4-6_islamic_parenting_adab",
                "2026-06-08T10:00:00Z",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.delete(f"/api/children/{cid}/progress")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1

    # GET progress should now show zero streak
    r2 = client.get(f"/api/children/{cid}/progress")
    body = r2.json()
    assert body["streak_days"] == 0
    assert body["last_completed_at"] is None
    assert body["lessons"] == []


def test_reset_progress_preserves_child_profile(client):
    """Reset must NOT touch the child_profiles row."""
    cid = _create_child(client, name="سارة", age_group="4-6", avatar_emoji="👧")
    client.delete(f"/api/children/{cid}/progress")
    r = client.get("/api/children")
    body = r.json()
    assert body["count"] == 1
    assert body["children"][0]["name"] == "سارة"
    assert body["children"][0]["age_group"] == "4-6"
    assert body["children"][0]["avatar_emoji"] == "👧"


def test_reset_progress_is_idempotent(client, tmp_db):
    """Second reset returns deleted=0 (no error)."""
    cid = _create_child(client)
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO lesson_progress (device_id, lesson_id, path_id, status) "
            "VALUES (?, ?, ?, 'completed')",
            ("test-device-001", "lesson_x", "path_x"),
        )
        conn.commit()
    finally:
        conn.close()
    r1 = client.delete(f"/api/children/{cid}/progress")
    assert r1.json()["deleted"] == 1
    r2 = client.delete(f"/api/children/{cid}/progress")
    assert r2.json()["deleted"] == 0


def test_reset_progress_only_affects_requesting_device(client, tmp_db):
    """A second device's progress must NOT be wiped by the first device's reset."""
    cid = _create_child(client)
    conn = sqlite3.connect(tmp_db)
    try:
        # Seed progress for *both* devices
        for dev, lid in [
            ("test-device-001", "lesson_a"),
            ("other-device", "lesson_b"),
        ]:
            conn.execute(
                "INSERT INTO lesson_progress (device_id, lesson_id, path_id, status) "
                "VALUES (?, ?, ?, 'completed')",
                (dev, lid, "path_x"),
            )
        conn.commit()
    finally:
        conn.close()

    r = client.delete(f"/api/children/{cid}/progress")
    assert r.json()["deleted"] == 1

    # The other device's row is still there
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT device_id, lesson_id FROM lesson_progress ORDER BY device_id"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["device_id"] == "other-device"
    finally:
        conn.close()


def test_reset_progress_404_for_other_device(client, tmp_db):
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) "
            "VALUES (?, ?, ?)",
            ("other-device", "Other", "4-6"),
        )
        conn.commit()
    finally:
        conn.close()
    r = client.delete("/api/children/1/progress")
    assert r.status_code == 404


def test_reset_progress_404_for_nonexistent(client):
    r = client.delete("/api/children/9999/progress")
    assert r.status_code == 404


# ── Auth gate ────────────────────────────────────────────────────────────


def test_update_requires_auth(tmp_db, monkeypatch):
    """Without the device_id in request.state, the auth stub doesn't
    set it — the endpoint should 401."""
    from app.routers.children import router as cr
    from app.routers.program import router as pr

    a = FastAPI()
    # Note: NO _AuthStubMiddleware — device_id is never set.

    a.include_router(cr, prefix="/api")
    a.include_router(pr, prefix="/api")
    with TestClient(a) as c:
        r = c.patch("/api/children/1", json={"name": "x"})
        assert r.status_code == 401
