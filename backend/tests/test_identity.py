"""Tests for Google identity linking with token verification.

Uses the same _AuthStubMiddleware pattern used in test_daily_routine.py.
"""
import json
from unittest.mock import patch, AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.init_db import init_db
from app.routers.identity import router as identity_router


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "identity.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(db))
    init_db()
    return db


class _AuthStubMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, device_id: str = "test-device-identity"):
        super().__init__(app)
        self.device_id = device_id

    async def dispatch(self, request: Request, call_next):
        request.state.device_id = self.device_id
        return await call_next(request)


@pytest.fixture
def app(tmp_db):
    a = FastAPI()
    a.add_middleware(_AuthStubMiddleware)
    a.include_router(identity_router, prefix="/api")
    return a


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


_WEB_CLIENT_ID = "620240456244-d7a3fd35ianuu34i1sobb0pj4ncttmdu.apps.googleusercontent.com"

_FAKE_TOKENINFO = {
    "iss": "https://accounts.google.com",
    "sub": "google-12345",
    "email": "parent@example.com",
    "email_verified": "true",
    "name": "Test Parent",
    "aud": _WEB_CLIENT_ID,
    "exp": "9999999999",
}


def test_link_google_requires_id_token(client):
    r = client.post("/api/identity/link-google", json={})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error"] == "id_token_and_device_required"


def test_link_google_rejects_invalid_token(client):
    with patch(
        "app.routers.identity.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=Response(400, text="Invalid token"),
    ):
        r = client.post(
            "/api/identity/link-google",
            json={"id_token": "bad.token.here"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error"] == "invalid_google_id_token"


def test_link_google_success(client):
    with patch(
        "app.routers.identity.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=Response(200, json=_FAKE_TOKENINFO),
    ):
        r = client.post(
            "/api/identity/link-google",
            json={"id_token": "valid.id.token"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["google_id"] == "google-12345"
    assert body["email"] == "parent@example.com"

    # /identity/me now reports linked
    r2 = client.get("/api/identity/me")
    assert r2.status_code == 200
    assert r2.json()["linked"] is True


def test_link_google_rejects_non_google_issuer(client):
    payload = dict(_FAKE_TOKENINFO)
    payload["iss"] = "https://evil.com"
    with patch(
        "app.routers.identity.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=Response(200, json=payload),
    ):
        r = client.post(
            "/api/identity/link-google",
            json={"id_token": "valid.id.token"},
        )
    assert r.json()["ok"] is False
    assert r.json()["error"] == "invalid_google_id_token"


def test_link_google_requires_sub_claim(client):
    payload = dict(_FAKE_TOKENINFO)
    payload.pop("sub")
    with patch(
        "app.routers.identity.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=Response(200, json=payload),
    ):
        r = client.post(
            "/api/identity/link-google",
            json={"id_token": "valid.id.token"},
        )
    assert r.json()["ok"] is False
    assert r.json()["error"] == "invalid_google_id_token"


def test_link_google_rejects_wrong_audience(client):
    payload = dict(_FAKE_TOKENINFO)
    payload["aud"] = "wrong-client-id.apps.googleusercontent.com"
    with patch(
        "app.routers.identity.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=Response(200, json=payload),
    ):
        r = client.post(
            "/api/identity/link-google",
            json={"id_token": "valid.id.token"},
        )
    assert r.json()["ok"] is False
    assert r.json()["error"] == "invalid_google_id_token"


def _link_with(client, payload):
    with patch(
        "app.routers.identity.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=Response(200, json=payload),
    ):
        return client.post("/api/identity/link-google", json={"id_token": "valid.id.token"})


def test_link_google_rejects_token_for_another_audience_even_if_we_requested_it(client):
    # `azp` names who asked for the token, not who it is for. The old check
    # accepted either field, so aud=someone-else + azp=us got through.
    payload = dict(_FAKE_TOKENINFO)
    payload["aud"] = "another-service.apps.googleusercontent.com"
    payload["azp"] = _WEB_CLIENT_ID
    r = _link_with(client, payload)
    assert r.json() == {"ok": False, "error": "invalid_google_id_token"}


def test_link_google_rejects_expired_token(client):
    payload = dict(_FAKE_TOKENINFO)
    payload["exp"] = "1000000000"          # 2001
    r = _link_with(client, payload)
    assert r.json() == {"ok": False, "error": "invalid_google_id_token"}


def test_unverified_email_is_not_stored(client):
    # Identity is the Google `sub`; the email is only what the account claims.
    # An address Google has not verified must not be recorded as the parent's.
    payload = dict(_FAKE_TOKENINFO)
    payload["email"] = "someone-else@example.com"
    payload["email_verified"] = "false"
    r = _link_with(client, payload)
    assert r.json()["ok"] is True
    assert r.json()["email"] == ""
    me = client.get("/api/identity/me").json()
    assert me["linked"] is True and me["email"] is None


def test_missing_email_verified_counts_as_unverified(client):
    payload = dict(_FAKE_TOKENINFO)
    payload.pop("email_verified")
    assert _link_with(client, payload).json()["email"] == ""


def test_jwt_style_boolean_email_verified_is_accepted(client):
    payload = dict(_FAKE_TOKENINFO)
    payload["email_verified"] = True
    assert _link_with(client, payload).json()["email"] == "parent@example.com"
