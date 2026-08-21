"""What is actually installed out there — the number the force-update lever needs.

`MINIMUM_BUILD_NUMBER` is a lever that force-updates every device below it. On
2026-08-21 it sat at 81 with production on 96, and the decision to move it could
not be made either way, because nothing recorded what people were running.

The previous answer was `chat_sessions.metadata`, and it cannot work twice over:
371 of the last 400 sessions carried no version at all, and the 29 that did were
misleading — a session is created once per install and never updated, so a
device that installed on 1.0.29 and now runs 1.0.51 still reported 1.0.29. That
is why builds 74 and 75 looked like the majority of the active base.

`push_tokens` is the one row the app rewrites on every launch. This pins the
three properties that make it a census rather than another install-time stamp:
it records, it updates, and a client that says nothing cannot erase what an
earlier launch already reported.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.init_db import get_conn, init_db
from app.routers.push import router as push_router

DEVICE = "census-device-1"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "census.db"))
    init_db()

    class _Auth(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.device_id = DEVICE
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_Auth)
    app.include_router(push_router, prefix="/api")
    return TestClient(app)


def _row():
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT app_version, build_number FROM push_tokens WHERE device_id = ?",
            (DEVICE,),
        ).fetchone()
    finally:
        conn.close()


def test_a_registration_records_the_build(client):
    r = client.post("/api/push/register", json={
        "token": "tok-1", "app_version": "1.0.51", "build_number": 96})
    assert r.json()["ok"] is True
    row = _row()
    assert row["app_version"] == "1.0.51"
    assert row["build_number"] == 96


def test_the_next_launch_overwrites_it(client):
    """The whole point. An install-time stamp cannot answer "what is installed
    now", which is the only question the force-update lever asks."""
    client.post("/api/push/register", json={
        "token": "tok-1", "app_version": "1.0.29", "build_number": 74})
    client.post("/api/push/register", json={
        "token": "tok-1", "app_version": "1.0.51", "build_number": 96})
    row = _row()
    assert row["app_version"] == "1.0.51"
    assert row["build_number"] == 96


def test_a_silent_client_does_not_erase_a_known_version(client):
    """Every build already on Play sends no version — and there are thousands of
    them. If their registrations nulled the column, the census would be wiped by
    exactly the devices it exists to count."""
    client.post("/api/push/register", json={
        "token": "tok-1", "app_version": "1.0.51", "build_number": 96})
    client.post("/api/push/register", json={"token": "tok-2"})
    row = _row()
    assert row["app_version"] == "1.0.51"
    assert row["build_number"] == 96


@pytest.mark.parametrize("build", ["ninety-six", None, "", 3.5, {"a": 1}])
def test_a_junk_build_number_is_dropped_not_stored(client, build):
    client.post("/api/push/register", json={"token": "tok-1", "build_number": build})
    assert _row()["build_number"] in (None, 3)  # 3.5 → int() → 3; rest → None


def test_registration_still_works_with_no_census_fields(client):
    """The census must never be able to break push registration itself: a device
    that cannot report its version still has to receive notifications."""
    assert client.post("/api/push/register", json={"token": "tok-1"}).json()["ok"] is True
    assert _row() is not None


def test_a_missing_token_is_still_refused(client):
    assert client.post("/api/push/register", json={"app_version": "1.0.51"}).json() == {
        "ok": False, "error": "token_required"}


def test_an_absurd_version_string_is_truncated(client):
    client.post("/api/push/register", json={
        "token": "tok-1", "app_version": "9" * 500})
    assert len(_row()["app_version"]) == 32
