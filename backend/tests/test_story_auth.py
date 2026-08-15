"""/api/program/story used to be reachable by anyone, and it generates on the
model. Locking it outright would 401 every build already on Play the moment
this deploys — and pushing to main deploys — so it is soft-protected: the
identity is read when the caller has one, and STORY_AUTH_ENFORCE turns the
grace off once the forced-update floor clears the last anonymous build.

These tests pin both halves. The grace one is the one that will look wrong in
six months; it is deliberate, and the flag is how it ends.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.db.init_db import get_conn, init_db
from app.middleware.auth import AuthMiddleware, _is_protected
from app.services import conversation_store as store

STORY_PATH = "/api/program/story"


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "story.db"))
    init_db()


@pytest.fixture
def client(tmp_db):
    """A stand-in route at the story path — the middleware is what is under
    test, and the real handler would call a model."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post(STORY_PATH)
    def story(request: Request):
        return {"device_id": getattr(request.state, "device_id", None)}

    with TestClient(app) as c:
        yield c


@pytest.fixture
def token(tmp_db):
    _session_id, token = store.create_session_with_token("test-device-story")
    return token


# ── The grace window ───────────────────────────────────────────────────────

def test_an_anonymous_caller_still_gets_through(client, monkeypatch):
    monkeypatch.delenv("STORY_AUTH_ENFORCE", raising=False)
    r = client.post(STORY_PATH, json={})
    assert r.status_code == 200
    assert r.json()["device_id"] is None


def test_a_token_is_read_even_though_it_is_not_required(client, token, monkeypatch):
    """The point of soft protection: identity when available, no 401 when not.
    Without this the route could not bind a story to a device during grace."""
    monkeypatch.delenv("STORY_AUTH_ENFORCE", raising=False)
    r = client.post(STORY_PATH, json={},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["device_id"] == "test-device-story"


def test_a_bad_token_degrades_to_anonymous_rather_than_401(client, monkeypatch):
    monkeypatch.delenv("STORY_AUTH_ENFORCE", raising=False)
    r = client.post(STORY_PATH, json={},
                    headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 200
    assert r.json()["device_id"] is None


# ── After the flag ─────────────────────────────────────────────────────────

def test_enforcement_makes_it_a_normal_protected_route(client, monkeypatch):
    monkeypatch.setenv("STORY_AUTH_ENFORCE", "1")
    assert client.post(STORY_PATH, json={}).status_code == 401


def test_enforcement_still_accepts_a_real_token(client, token, monkeypatch):
    monkeypatch.setenv("STORY_AUTH_ENFORCE", "1")
    r = client.post(STORY_PATH, json={},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["device_id"] == "test-device-story"


def test_the_flag_is_read_per_request_not_at_import(monkeypatch):
    """So the VPS can flip it on restart without a redeploy."""
    monkeypatch.delenv("STORY_AUTH_ENFORCE", raising=False)
    assert _is_protected(STORY_PATH, "POST") is False
    monkeypatch.setenv("STORY_AUTH_ENFORCE", "true")
    assert _is_protected(STORY_PATH, "POST") is True


def test_the_flag_does_not_touch_other_program_routes(monkeypatch):
    monkeypatch.setenv("STORY_AUTH_ENFORCE", "1")
    assert _is_protected("/api/program/paths", "GET") is False
    assert _is_protected("/api/program/story-themes", "GET") is False
