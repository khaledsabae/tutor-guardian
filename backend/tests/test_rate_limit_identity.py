"""Rate-limit identity tests — the bucket key must not collapse to the IP.

RateLimitMiddleware runs BEFORE AuthMiddleware (Starlette's add_middleware
prepends, so the last one registered runs first), which means
request.state.device_id is still unset when the limiter looks at it. Every
request therefore fell back to request.client.host: a household on one wifi —
or an entire carrier CGNAT pool — shared a single AI_DAILY_LIMIT bucket.

These tests pin the replacement identity chain: device_id → token hash → IP.
Every request below comes from the SAME client IP (TestClient always presents
"testclient"), so anything that still passes proves the key is no longer the IP.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.middleware import rate_limit as rl


def _make_app(*, set_device_id: str | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(rl.RateLimitMiddleware)

    if set_device_id is not None:
        class _AuthStub(BaseHTTPMiddleware):
            """Stands in for a hypothetical auth middleware running first."""

            async def dispatch(self, request, call_next):
                request.state.device_id = set_device_id
                return await call_next(request)

        # Registered last → runs first, so device_id IS set by the time the
        # limiter reads it. This is the ordering production does NOT have.
        app.add_middleware(_AuthStub)

    @app.post("/api/assistant/stream")
    def ai_post():
        return {"ok": True}

    return app


def _request(headers: list[tuple[bytes, bytes]] | None = None,
             client: tuple[str, int] | None = ("1.2.3.4", 5000)) -> Request:
    return Request({"type": "http", "headers": headers or [], "client": client})


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(rl, "_AI_DAILY_LIMIT", 2)
    monkeypatch.setattr(rl, "_LIMIT", 1000)  # keep the minute window out of the way
    monkeypatch.setattr(rl, "_GENERAL_LIMIT", 1000)
    return TestClient(_make_app())


def _burn_quota(client: TestClient, headers: dict, times: int = 2) -> None:
    for _ in range(times):
        assert client.post("/api/assistant/stream", headers=headers).status_code == 200


# ── the bug: two tokens, one IP ───────────────────────────────────────────
def test_two_tokens_from_same_ip_get_independent_daily_buckets(client):
    """THE regression. Pre-fix both tokens shared one per-IP bucket and the
    second family's very first question was refused."""
    _burn_quota(client, {"Authorization": "Bearer token-family-a"})
    blocked = client.post(
        "/api/assistant/stream", headers={"Authorization": "Bearer token-family-a"}
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "daily_limit"

    # Same IP, different token → untouched budget.
    fresh = client.post(
        "/api/assistant/stream", headers={"Authorization": "Bearer token-family-b"}
    )
    assert fresh.status_code == 200


def test_same_token_shares_one_bucket(client):
    """The flip side: keying per token must not become keying per request."""
    headers = {"Authorization": "Bearer token-family-a"}
    _burn_quota(client, headers)
    assert client.post("/api/assistant/stream", headers=headers).status_code == 429


# ── fallbacks ─────────────────────────────────────────────────────────────
def test_no_authorization_header_falls_back_to_ip(client):
    """Unauthenticated callers keep sharing the per-IP bucket (the story
    endpoint is public, so this path must stay limited)."""
    _burn_quota(client, {})
    assert client.post("/api/assistant/stream").status_code == 429
    # ...and that exhaustion is per-IP, not global: a token caller is fine.
    assert client.post(
        "/api/assistant/stream", headers={"Authorization": "Bearer some-token"}
    ).status_code == 200


def test_identity_prefixes_cannot_collide():
    assert rl._client_identity(_request()).startswith("ip:")
    assert rl._client_identity(
        _request([(b"authorization", b"Bearer abc")])
    ).startswith("tok:")
    # An IP-shaped device id and an IP must not land on the same key.
    ip_req = _request(client=("1.2.3.4", 5000))
    dev_req = _request(client=("9.9.9.9", 1))
    dev_req.state.device_id = "1.2.3.4"
    assert rl._client_identity(dev_req) == "dev:1.2.3.4"
    assert rl._client_identity(ip_req) != rl._client_identity(dev_req)


def test_unknown_client_does_not_crash():
    assert rl._client_identity(_request(client=None)) == "ip:unknown"


def test_empty_or_unknown_scheme_falls_back_to_ip():
    for header in (b"", b"Bearer ", b"Basic dXNlcjpwYXNz", b"Child-Bearer   "):
        ident = rl._client_identity(_request([(b"authorization", header)]))
        assert ident.startswith("ip:"), header


# ── child mode ────────────────────────────────────────────────────────────
def test_child_bearer_is_keyed_and_does_not_collide_with_bearer(client):
    """Child-mode tokens get their own bucket, and the scheme is part of the
    key so an identical token string under the two schemes stays separate."""
    same_token = "identical-string"
    _burn_quota(client, {"Authorization": f"Child-Bearer {same_token}"})
    assert client.post(
        "/api/assistant/stream", headers={"Authorization": f"Child-Bearer {same_token}"}
    ).status_code == 429
    assert client.post(
        "/api/assistant/stream", headers={"Authorization": f"Bearer {same_token}"}
    ).status_code == 200


def test_token_hash_is_stable_and_never_leaks_the_token():
    header = "Bearer super-secret-token"
    ident = rl._client_identity(_request([(b"authorization", header.encode())]))
    assert ident == rl._client_identity(_request([(b"authorization", header.encode())]))
    assert "super-secret-token" not in ident
    assert len(ident) == len("tok:") + rl._TOKEN_KEY_LEN


# ── device_id still wins when it is available ─────────────────────────────
def test_request_state_device_id_takes_priority(monkeypatch):
    """Priority 1 keeps working if the middleware order ever changes: two
    device ids sharing one token still get separate buckets."""
    monkeypatch.setattr(rl, "_AI_DAILY_LIMIT", 1)
    monkeypatch.setattr(rl, "_LIMIT", 1000)
    headers = {"Authorization": "Bearer shared-token"}

    client_a = TestClient(_make_app(set_device_id="device-a"))
    assert client_a.post("/api/assistant/stream", headers=headers).status_code == 200
    assert client_a.post("/api/assistant/stream", headers=headers).status_code == 429

    # A different device on the same app instance would need a shared limiter
    # to prove isolation; the identity helper shows it directly instead.
    req = _request([(b"authorization", b"Bearer shared-token")])
    req.state.device_id = "device-b"
    assert rl._client_identity(req) == "dev:device-b"
