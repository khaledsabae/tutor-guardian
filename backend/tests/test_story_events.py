"""«صورة حيّة» experiment — the remote switch and the events endpoint.

Pins:
  1. /api/app-config carries `story_motion_mode`: "ab" by default and for
     anything unknown; "motion" / "static" from STORY_MOTION_MODE — the
     month-end switch, no release needed.
  2. POST /api/stories/events stores a batch for the calling device, and
     refuses a batch with anything outside the vocabulary (no free text can
     ride in), an empty or oversized batch, and a call without a device.
"""
import sqlite3

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.init_db import db_path, init_db
from app.routers.story_events import router as story_router


def test_app_config_story_motion_mode(monkeypatch):
    from app.main import app

    client = TestClient(app)
    monkeypatch.delenv("STORY_MOTION_MODE", raising=False)
    assert client.get("/api/app-config").json()["story_motion_mode"] == "ab"
    for value, expected in (("motion", "motion"), ("STATIC", "static"),
                            (" ab ", "ab"), ("both", "ab"), ("", "ab")):
        monkeypatch.setenv("STORY_MOTION_MODE", value)
        assert client.get("/api/app-config").json()["story_motion_mode"] == expected


class _Device(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        device = request.headers.get("X-Test-Device")
        if device:
            request.state.device_id = device
        return await call_next(request)


@pytest.fixture
def events_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "events.db"))
    init_db()
    app = FastAPI()
    app.add_middleware(_Device)
    app.include_router(story_router, prefix="/api")
    with TestClient(app) as c:
        yield c


def _event(**kw):
    e = {"name": "story_opened", "story_id": "maryam_toys", "lang": "ar",
         "variant": "motion", "narration_on": False, "reduce_motion": False}
    e.update(kw)
    return e


def _rows():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT * FROM story_events ORDER BY id")]
    finally:
        con.close()


def test_a_batch_is_stored_for_the_calling_device(events_client):
    r = events_client.post("/api/stories/events", headers={"X-Test-Device": "dev-1"}, json={
        "events": [
            _event(),
            _event(name="story_page_viewed", page_index=2, narration_on=True),
            _event(name="story_rated", rating=3, variant="static", reduce_motion=True),
        ]})
    assert r.status_code == 204, r.text
    rows = _rows()
    assert [r["name"] for r in rows] == ["story_opened", "story_page_viewed", "story_rated"]
    assert {r["device_id"] for r in rows} == {"dev-1"}
    assert rows[1]["page_index"] == 2 and rows[1]["narration_on"] == 1
    assert rows[2]["rating"] == 3 and rows[2]["reduce_motion"] == 1
    assert rows[2]["variant"] == "static"


@pytest.mark.parametrize("bad", [
    {"name": "story_liked_the_motion"},
    {"variant": "both"},
    {"story_id": "مريم"},
    {"story_id": "a" * 65},
    {"lang": "arabic"},
    {"rating": 4},
    {"rating": 0},
    {"page_index": -1},
    {"note": "free text"},
])
def test_anything_outside_the_vocabulary_refuses_the_batch(events_client, bad):
    r = events_client.post("/api/stories/events", headers={"X-Test-Device": "dev-1"},
                           json={"events": [_event(), _event(**bad)]})
    assert r.status_code == 422
    con = sqlite3.connect(db_path())
    try:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE name='story_events'").fetchone()
        assert exists is None or con.execute(
            "SELECT COUNT(*) FROM story_events").fetchone()[0] == 0
    finally:
        con.close()


def test_empty_and_oversized_batches_are_refused(events_client):
    h = {"X-Test-Device": "dev-1"}
    assert events_client.post("/api/stories/events", headers=h,
                              json={"events": []}).status_code == 422
    assert events_client.post("/api/stories/events", headers=h,
                              json={"events": [_event()] * 51}).status_code == 422


def test_no_device_no_write(events_client):
    r = events_client.post("/api/stories/events", json={"events": [_event()]})
    assert r.status_code == 401
