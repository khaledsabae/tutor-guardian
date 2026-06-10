"""
Phase 6 tests — streak calculation + onboarding state.

Mounts the children + program routers onto a minimal FastAPI app so
the heavy RAG stack is never imported. The auth middleware is stubbed
via a tiny middleware that sets `request.state.device_id`.
"""
import sqlite3
from datetime import date, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app import curriculum_loader as cl
from app.db.init_db import init_db
from app.routers.children import (
    _compute_streak,
    _parse_iso_utc_date,
    router as children_router,
)
from app.routers.program import router as program_router


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "phase6.db"
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


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_child(client) -> int:
    r = client.post(
        "/api/children",
        json={"name": "سارة", "age_group": "4-6", "avatar_emoji": "👧"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def _seed_completion(
    tmp_db,
    device_id: str,
    lesson_id: str,
    completed_at: str,
    path_id: str = "path_4-6_islamic_parenting_adab",
) -> None:
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            """
            INSERT INTO lesson_progress
                (device_id, lesson_id, path_id, status, completed_at)
            VALUES (?, ?, ?, 'completed', ?)
            """,
            (device_id, lesson_id, path_id, completed_at),
        )
        conn.commit()
    finally:
        conn.close()


# ── Unit tests: _parse_iso_utc_date ──────────────────────────────────────


def test_parse_iso_utc_date_accepts_z_suffix():
    d = _parse_iso_utc_date("2026-06-08T12:00:00Z")
    assert d == date(2026, 6, 8)


def test_parse_iso_utc_date_accepts_offset():
    d = _parse_iso_utc_date("2026-06-08T12:00:00+00:00")
    assert d == date(2026, 6, 8)


def test_parse_iso_utc_date_returns_none_for_invalid():
    assert _parse_iso_utc_date(None) is None
    assert _parse_iso_utc_date("") is None
    assert _parse_iso_utc_date("not-a-date") is None


# ── Unit tests: _compute_streak ──────────────────────────────────────────


def test_streak_empty_returns_zero():
    streak, last = _compute_streak([], today=date(2026, 6, 8))
    assert streak == 0
    assert last is None


def test_streak_today_only():
    today = date(2026, 6, 8)
    streak, last = _compute_streak([today], today=today)
    assert streak == 1
    assert last == today


def test_streak_three_consecutive_ending_today():
    today = date(2026, 6, 8)
    dates = [today, today - timedelta(days=1), today - timedelta(days=2)]
    streak, last = _compute_streak(dates, today=today)
    assert streak == 3
    assert last == today


def test_streak_three_consecutive_anchored_yesterday():
    today = date(2026, 6, 8)
    dates = [
        today - timedelta(days=1),
        today - timedelta(days=2),
        today - timedelta(days=3),
    ]
    streak, last = _compute_streak(dates, today=today)
    assert streak == 3
    assert last == today - timedelta(days=1)


def test_streak_break_returns_zero():
    today = date(2026, 6, 8)
    dates = [today - timedelta(days=2)]  # 2-day gap
    streak, last = _compute_streak(dates, today=today)
    assert streak == 0
    assert last == today - timedelta(days=2)


def test_streak_deduplicates_same_day():
    today = date(2026, 6, 8)
    dates = [today, today, today]  # 3 completions on same day
    streak, last = _compute_streak(dates, today=today)
    assert streak == 1
    assert last == today


def test_streak_gap_inside_kills_count():
    today = date(2026, 6, 8)
    dates = [
        today,                              # day 0
        today - timedelta(days=1),          # day 1
        # day 2 missing
        today - timedelta(days=3),          # day 3 — should NOT count
    ]
    streak, last = _compute_streak(dates, today=today)
    assert streak == 2
    assert last == today


# ── Integration: GET /api/children/{id}/progress returns streak ──────────


def test_progress_endpoint_returns_streak_days_zero_when_empty(client):
    child_id = _create_child(client)
    r = client.get(f"/api/children/{child_id}/progress")
    assert r.status_code == 200
    body = r.json()
    assert body["streak_days"] == 0
    assert body["last_completed_at"] is None


def test_progress_endpoint_returns_streak_days(client, tmp_db):
    child_id = _create_child(client)
    # Relative to the real "today" — the endpoint computes streak against the
    # server's current date, so seeding a fixed date makes this time-dependent.
    today = date.today()
    _seed_completion(tmp_db, "test-device-001", "lesson_a", f"{today}T10:00:00Z")
    _seed_completion(
        tmp_db, "test-device-001", "lesson_b", f"{today - timedelta(days=1)}T10:00:00Z"
    )
    _seed_completion(
        tmp_db, "test-device-001", "lesson_c", f"{today - timedelta(days=2)}T10:00:00Z"
    )

    r = client.get(f"/api/children/{child_id}/progress")
    body = r.json()
    assert body["streak_days"] == 3
    assert body["last_completed_at"] == f"{today}T10:00:00Z"


def test_progress_endpoint_last_completed_at(client, tmp_db):
    child_id = _create_child(client)
    today = date(2026, 6, 8)
    _seed_completion(tmp_db, "test-device-001", "lesson_x", f"{today}T10:00:00Z")

    r = client.get(f"/api/children/{child_id}/progress")
    body = r.json()
    assert body["last_completed_at"] == f"{today}T10:00:00Z"


def test_progress_endpoint_streak_ignores_path_filter(client, tmp_db):
    """The path filter on GET progress doesn't affect the streak."""
    child_id = _create_child(client)
    today = date.today()  # relative to real now (endpoint uses server date)
    # Seed completions on two different paths
    _seed_completion(
        tmp_db, "test-device-001", "lesson_a", f"{today}T10:00:00Z", path_id="path_1"
    )
    _seed_completion(
        tmp_db,
        "test-device-001",
        "lesson_b",
        f"{today - timedelta(days=1)}T10:00:00Z",
        path_id="path_2",
    )

    # Filtered by path_1 — streak still counts both because it's
    # computed across all device completions.
    r = client.get(f"/api/children/{child_id}/progress?path_id=path_1")
    body = r.json()
    assert body["streak_days"] == 2
