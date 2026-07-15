"""
Multi-child progress tracking tests.

These verify the fix that makes PATCH /api/program/lessons/{id}/progress
aware of child_id, and that GET progress / streaks are isolated per child.
"""
import sqlite3

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app import curriculum_loader as cl
from app.db.init_db import init_db
from app.routers.children import router as children_router
from app.routers.program import router as program_router

# ── Per-test temp DB (don't pollute the production conversations.db) ─────


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "multi_child_progress.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    init_db()
    return db


# ── Auth stub: injects a fixed device_id so we can drive the routers ────


class _AuthStubMiddleware(BaseHTTPMiddleware):
    """Sets `request.state.device_id` for all requests — simulates
    what AuthMiddleware would do after validating a Bearer token."""

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


# ── Helpers ───────────────────────────────────────────────────────────────


def _create_child_payload(**overrides):
    base = {
        "name": "سارة",
        "age_group": "4-6",
        "gender": "female",
        "avatar_emoji": "👧",
    }
    base.update(overrides)
    return base


# ── Multi-child PATCH attribution ──────────────────────────────────────────


def test_patch_with_child_id_attributes_to_that_child(client):
    """PATCH with child_id=B writes the completed row only for child B."""
    a = client.post("/api/children", json=_create_child_payload(name="طفل A")).json()
    b = client.post("/api/children", json=_create_child_payload(name="طفل B")).json()
    child_a_id = a["id"]
    child_b_id = b["id"]

    lesson_id = "lesson_4-6_islamic_parenting_adab_01"
    r = client.patch(
        f"/api/program/lessons/{lesson_id}/progress",
        json={"status": "completed", "child_id": child_b_id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"

    progress_a = client.get(f"/api/children/{child_a_id}/progress").json()
    progress_b = client.get(f"/api/children/{child_b_id}/progress").json()

    assert lesson_id not in {item["lesson_id"] for item in progress_a["lessons"]}
    assert lesson_id in {item["lesson_id"] for item in progress_b["lessons"]}


def test_patch_without_child_id_falls_back_to_first_child(client):
    """Legacy clients omit child_id; the row is attributed to the
    first-created child."""
    first = client.post("/api/children", json=_create_child_payload(name="أول")).json()
    second = client.post("/api/children", json=_create_child_payload(name="ثانٍ")).json()
    first_id = first["id"]
    second_id = second["id"]

    lesson_id = "lesson_4-6_islamic_parenting_adab_01"
    r = client.patch(
        f"/api/program/lessons/{lesson_id}/progress",
        json={"status": "completed"},
    )
    assert r.status_code == 200, r.text

    progress_first = client.get(f"/api/children/{first_id}/progress").json()
    progress_second = client.get(f"/api/children/{second_id}/progress").json()

    assert lesson_id in {item["lesson_id"] for item in progress_first["lessons"]}
    assert lesson_id not in {item["lesson_id"] for item in progress_second["lessons"]}


def test_patch_with_foreign_child_id_404(client, tmp_db):
    """A device cannot attribute progress to a child owned by another device.
    No DB row is written."""
    local_child = client.post(
        "/api/children", json=_create_child_payload(name="محلي")
    ).json()

    # Create a child under a different device directly in the DB.
    conn = sqlite3.connect(tmp_db)
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group) "
            "VALUES (?, ?, ?)",
            ("other-device", "غريب", "4-6"),
        )
        foreign_child_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    lesson_id = "lesson_4-6_islamic_parenting_adab_01"
    r = client.patch(
        f"/api/program/lessons/{lesson_id}/progress",
        json={"status": "completed", "child_id": foreign_child_id},
    )
    assert r.status_code == 404, r.text

    # Neither local nor foreign child has progress.
    local_progress = client.get(f"/api/children/{local_child['id']}/progress").json()
    assert local_progress["lessons"] == []

    conn = sqlite3.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT child_id FROM lesson_progress WHERE lesson_id = ?",
            (lesson_id,),
        ).fetchall()
        assert rows == []
    finally:
        conn.close()


# ── Per-child reset and streaks ──────────────────────────────────────────


def test_reset_deletes_only_target_child_rows(client):
    """DELETE /api/children/{id}/progress wipes only that child's rows
    (plus legacy child_id=0 rows), leaving siblings untouched."""
    a = client.post("/api/children", json=_create_child_payload(name="A")).json()
    b = client.post("/api/children", json=_create_child_payload(name="B")).json()
    child_a_id = a["id"]
    child_b_id = b["id"]

    lesson_a = "lesson_4-6_islamic_parenting_adab_01"
    lesson_b = "lesson_4-6_islamic_parenting_adab_02"

    ra = client.patch(
        f"/api/program/lessons/{lesson_a}/progress",
        json={"status": "completed", "child_id": child_a_id},
    )
    rb = client.patch(
        f"/api/program/lessons/{lesson_b}/progress",
        json={"status": "completed", "child_id": child_b_id},
    )
    assert ra.status_code == 200
    assert rb.status_code == 200

    reset = client.delete(f"/api/children/{child_a_id}/progress")
    assert reset.status_code == 200, reset.text

    progress_a = client.get(f"/api/children/{child_a_id}/progress").json()
    progress_b = client.get(f"/api/children/{child_b_id}/progress").json()

    assert progress_a["lessons"] == []
    assert progress_a["streak_days"] == 0
    assert lesson_b in {item["lesson_id"] for item in progress_b["lessons"]}


def test_streak_isolated_per_child(client):
    """Completing a lesson for child B gives B a streak but leaves A at 0."""
    a = client.post("/api/children", json=_create_child_payload(name="A")).json()
    b = client.post("/api/children", json=_create_child_payload(name="B")).json()
    child_a_id = a["id"]
    child_b_id = b["id"]

    r = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "completed", "child_id": child_b_id},
    )
    assert r.status_code == 200, r.text

    progress_a = client.get(f"/api/children/{child_a_id}/progress").json()
    progress_b = client.get(f"/api/children/{child_b_id}/progress").json()

    assert progress_a["streak_days"] == 0
    assert progress_b["streak_days"] >= 1
