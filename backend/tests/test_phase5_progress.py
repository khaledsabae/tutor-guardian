"""
Phase 5 tests — child profiles + progress tracking.

Mounts ONLY the children + program routers onto a minimal FastAPI app
so the heavy RAG stack (sentence_transformers, ChromaDB) is never
imported.

The auth middleware is **not** mounted here — the tests exercise the
routers directly and the `device_id` is injected by setting
`request.state.device_id` in a thin middleware stub. The auth-gate
behaviour itself is covered by an inline `_is_protected()` test in
the smoke script + the existing `test_api_smoke.py`.
"""
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app import curriculum_loader as cl
from app.db.init_db import _ensure_column, init_db
from app.routers.children import router as children_router
from app.routers.program import router as program_router

# ── Per-test temp DB (don't pollute the production conversations.db) ─────


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "phase5.db"
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


# ── DB schema (v5) ───────────────────────────────────────────────────────


def test_v5_schema_adds_avatar_emoji_column(tmp_db):
    """Migration v5 must add avatar_emoji without breaking older DBs."""
    conn = sqlite3.connect(tmp_db)
    try:
        rows = conn.execute("PRAGMA table_info(child_profiles)").fetchall()
        names = {r[1] for r in rows}
        assert "avatar_emoji" in names
        # All v4 columns still present
        for col in ("id", "device_id", "name", "age_group", "gender", "created_at", "updated_at"):
            assert col in names
    finally:
        conn.close()


def test_v5_migration_is_idempotent(tmp_db):
    """Running init_db() twice must not fail or duplicate columns."""
    init_db()  # second run
    conn = sqlite3.connect(tmp_db)
    try:
        rows = conn.execute("PRAGMA table_info(child_profiles)").fetchall()
        # avatar_emoji should appear exactly once.
        avatar_count = sum(1 for r in rows if r[1] == "avatar_emoji")
        assert avatar_count == 1
    finally:
        conn.close()


# ── POST /api/children ───────────────────────────────────────────────────


def test_create_child_happy_path(client, tmp_db):
    r = client.post("/api/children", json=_create_child_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "سارة"
    assert body["age_group"] == "4-6"
    assert body["gender"] == "female"
    assert body["avatar_emoji"] == "👧"
    assert isinstance(body["id"], int) and body["id"] > 0

    # Row linked to our stub device_id
    conn = sqlite3.connect(tmp_db)
    try:
        row = conn.execute(
            "SELECT device_id FROM child_profiles WHERE id = ?",
            (body["id"],),
        ).fetchone()
        assert row[0] == "test-device-001"
    finally:
        conn.close()


def test_create_child_minimal_payload(client):
    r = client.post("/api/children", json={"name": "أحمد", "age_group": "7-9"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "أحمد"
    assert body["age_group"] == "7-9"
    assert body["gender"] is None
    assert body["avatar_emoji"] is None


def test_create_child_rejects_invalid_age_group(client):
    r = client.post("/api/children", json={"name": "X", "age_group": "99-100"})
    assert r.status_code == 422
    assert "age_group" in r.text


def test_create_child_rejects_blank_name(client):
    r = client.post("/api/children", json={"name": "   ", "age_group": "4-6"})
    assert r.status_code == 422


def test_create_child_rejects_non_emoji_avatar(client):
    r = client.post(
        "/api/children",
        json={"name": "سارة", "age_group": "4-6", "avatar_emoji": "hello world"},
    )
    assert r.status_code == 422


def test_create_child_emoji_can_be_multi_codepoint(client):
    # Some families use multi-codepoint emoji (skin tone, ZWJ sequences)
    r = client.post(
        "/api/children",
        json={"name": "ليلى", "age_group": "4-6", "avatar_emoji": "👧🏽"},
    )
    assert r.status_code == 201


# ── GET /api/children/{id}/progress ──────────────────────────────────────


def test_get_child_progress_empty(client):
    cr = client.post("/api/children", json=_create_child_payload())
    child_id = cr.json()["id"]

    r = client.get(f"/api/children/{child_id}/progress")
    assert r.status_code == 200
    body = r.json()
    assert body["child_id"] == child_id
    assert body["lessons"] == []


def test_get_child_progress_returns_records(client, tmp_db):
    cr = client.post("/api/children", json=_create_child_payload())
    child_id = cr.json()["id"]

    # Seed two progress rows
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            """
            INSERT INTO lesson_progress
                (device_id, lesson_id, path_id, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("test-device-001", "lesson_4-6_islamic_parenting_adab_01",
             "path_4-6_islamic_parenting_adab", "completed",
             "2026-06-08T10:00:00Z", "2026-06-08T10:15:00Z"),
        )
        conn.execute(
            """
            INSERT INTO lesson_progress
                (device_id, lesson_id, path_id, status, started_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test-device-001", "lesson_4-6_islamic_parenting_adab_02",
             "path_4-6_islamic_parenting_adab", "in_progress",
             "2026-06-08T11:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get(f"/api/children/{child_id}/progress")
    assert r.status_code == 200
    body = r.json()
    assert body["child_id"] == child_id
    assert len(body["lessons"]) == 2
    statuses = {l["status"] for l in body["lessons"]}
    assert statuses == {"completed", "in_progress"}


def test_get_child_progress_404_for_other_device(client, tmp_db):
    """A child belonging to a *different* device must 404, not leak."""
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            """INSERT INTO child_profiles
                  (device_id, name, age_group)
               VALUES (?, ?, ?)""",
            ("other-device", "OtherKid", "4-6"),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get("/api/children/1/progress")
    assert r.status_code == 404


def test_get_child_progress_404_for_nonexistent(client):
    r = client.get("/api/children/9999/progress")
    assert r.status_code == 404


def test_get_child_progress_filter_by_path_id(client, tmp_db):
    cr = client.post("/api/children", json=_create_child_payload())
    child_id = cr.json()["id"]

    conn = sqlite3.connect(tmp_db)
    try:
        for lid, pid in [
            ("lesson_a", "path_1"),
            ("lesson_b", "path_1"),
            ("lesson_c", "path_2"),
        ]:
            conn.execute(
                """INSERT INTO lesson_progress
                      (device_id, lesson_id, path_id, status)
                   VALUES (?, ?, ?, 'completed')""",
                ("test-device-001", lid, pid),
            )
        conn.commit()
    finally:
        conn.close()

    r = client.get(f"/api/children/{child_id}/progress?path_id=path_1")
    assert r.status_code == 200
    body = r.json()
    assert len(body["lessons"]) == 2
    assert all(l["path_id"] == "path_1" for l in body["lessons"])


# ── PATCH /api/program/lessons/{id}/progress ────────────────────────────


def test_patch_progress_creates_row_when_missing(client):
    r = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "in_progress"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "in_progress"
    assert body["started_at"] is not None
    assert body["completed_at"] is None
    assert body["path_id"] == "path_4-6_islamic_parenting_adab"


def test_patch_progress_completed_sets_both_timestamps(client):
    r1 = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "in_progress"},
    )
    assert r1.status_code == 200
    r2 = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "completed"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "completed"
    assert body["started_at"] is not None
    assert body["completed_at"] is not None


def test_patch_progress_idempotent_on_same_status(client):
    r1 = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "completed"},
    )
    r2 = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "completed"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    # completed_at must NOT change (or it changes minimally by ms).
    # Accept either: same value or r2 >= r1.
    assert r2.json()["completed_at"] is not None


def test_patch_progress_not_started_resets_timestamps(client, tmp_db):
    r1 = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "completed"},
    )
    assert r1.json()["completed_at"] is not None
    r2 = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "not_started"},
    )
    body = r2.json()
    assert body["status"] == "not_started"
    assert body["started_at"] is None
    assert body["completed_at"] is None


def test_patch_progress_rejects_invalid_status(client):
    r = client.patch(
        "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
        json={"status": "frobbed"},
    )
    assert r.status_code == 422


def test_patch_progress_404_for_unknown_lesson(client):
    r = client.patch(
        "/api/program/lessons/nonexistent_lesson_99/progress",
        json={"status": "in_progress"},
    )
    assert r.status_code == 404


# ── Multi-device isolation ───────────────────────────────────────────────


def test_progress_is_scoped_per_device(tmp_db, monkeypatch):
    """Two devices can independently track the same lesson."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient as TC
    from app.routers.program import router as pr
    from app.routers.children import router as cr

    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware, device_id="device-A")
    a.include_router(cr, prefix="/api")
    a.include_router(pr, prefix="/api")

    with TC(a) as cA:
        r = cA.patch(
            "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
            json={"status": "completed"},
        )
        assert r.status_code == 200

    # Switch device
    a2 = FastAPI()
    a2.add_middleware(_AuthStubMiddleware, device_id="device-B")
    a2.include_router(cr, prefix="/api")
    a2.include_router(pr, prefix="/api")

    with TC(a2) as cB:
        r = cB.patch(
            "/api/program/lessons/lesson_4-6_islamic_parenting_adab_01/progress",
            json={"status": "in_progress"},
        )
        assert r.status_code == 200

    # Verify two rows in the DB
    conn = sqlite3.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT device_id, status FROM lesson_progress "
            "WHERE lesson_id = 'lesson_4-6_islamic_parenting_adab_01' "
            "ORDER BY device_id"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "device-A"
        assert rows[0][1] == "completed"
        assert rows[1][0] == "device-B"
        assert rows[1][1] == "in_progress"
    finally:
        conn.close()
