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


def _real_bearer(device_id: str) -> dict:
    """A token that AuthMiddleware would accept. The AI scope validates tokens
    (audit H4), so made-up strings no longer earn a bucket of their own."""
    from app.services import conversation_store as store

    _, token = store.create_session_with_token(device_id=device_id)
    return {"Authorization": f"Bearer {token}"}


def _burn_quota(client: TestClient, headers: dict, times: int = 2) -> None:
    for _ in range(times):
        assert client.post("/api/assistant/stream", headers=headers).status_code == 200


# ── the bug: two tokens, one IP ───────────────────────────────────────────
def test_two_tokens_from_same_ip_get_independent_daily_buckets(client):
    """THE regression. Pre-fix both tokens shared one per-IP bucket and the
    second family's very first question was refused."""
    family_a, family_b = _real_bearer("family-a"), _real_bearer("family-b")
    _burn_quota(client, family_a)
    blocked = client.post("/api/assistant/stream", headers=family_a)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "daily_limit"

    # Same IP, different device → untouched budget.
    fresh = client.post("/api/assistant/stream", headers=family_b)
    assert fresh.status_code == 200


def test_same_token_shares_one_bucket(client):
    """The flip side: keying per token must not become keying per request."""
    headers = _real_bearer("family-a")
    _burn_quota(client, headers)
    assert client.post("/api/assistant/stream", headers=headers).status_code == 429


def test_second_session_of_same_device_shares_the_daily_quota(client):
    """Minting a new session used to reset the quota (new token, new bucket).
    The AI scope keys on the validated DEVICE now."""
    _burn_quota(client, _real_bearer("family-a"))
    again = client.post("/api/assistant/stream", headers=_real_bearer("family-a"))
    assert again.status_code == 429


def test_random_bearer_values_do_not_buy_fresh_ai_buckets(client):
    """THE bypass (audit H4): a new random Bearer per request used to get a new
    per-minute bucket and a new daily quota on the public story route."""
    for i in range(2):
        assert client.post(
            "/api/assistant/stream", headers={"Authorization": f"Bearer forged-{i}"}
        ).status_code == 200
    assert client.post(
        "/api/assistant/stream", headers={"Authorization": "Bearer forged-99"}
    ).status_code == 429


# ── fallbacks ─────────────────────────────────────────────────────────────
def test_no_authorization_header_falls_back_to_ip(client):
    """Unauthenticated callers keep sharing the per-IP bucket (the story
    endpoint is public, so this path must stay limited)."""
    _burn_quota(client, {})
    assert client.post("/api/assistant/stream").status_code == 429
    # ...and that exhaustion is per-IP, not global: a token caller is fine.
    assert client.post(
        "/api/assistant/stream", headers=_real_bearer("family-c")
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
    from app.services import child_token

    child = {"Authorization": f"Child-Bearer {child_token.issue_child_token('fam', 7)}"}
    _burn_quota(client, child)
    assert client.post("/api/assistant/stream", headers=child).status_code == 429
    assert client.post(
        "/api/assistant/stream", headers=_real_bearer("fam")
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


# ── scopes added by the H4 hardening ──────────────────────────────────────
def _scoped_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(rl.RateLimitMiddleware)

    @app.post("/api/chat/sessions")
    def mint():
        return {"ok": True}

    @app.get("/api/insights/parenting")
    def insights():
        return {"ok": True}

    return app


def test_session_minting_is_ip_limited_whatever_the_bearer(monkeypatch):
    monkeypatch.setattr(rl, "_SESSION_LIMIT", 2)
    c = TestClient(_scoped_app())
    for i in range(2):
        assert c.post("/api/chat/sessions",
                      headers={"Authorization": f"Bearer x{i}"}).status_code == 200
    assert c.post("/api/chat/sessions",
                  headers={"Authorization": "Bearer another"}).status_code == 429


def test_insights_gets_count_against_the_daily_ai_quota(monkeypatch):
    monkeypatch.setattr(rl, "_AI_DAILY_LIMIT", 2)
    monkeypatch.setattr(rl, "_LIMIT", 1000)
    c = TestClient(_scoped_app())
    headers = _real_bearer("insights-family")
    assert c.get("/api/insights/parenting", headers=headers).status_code == 200
    assert c.get("/api/insights/parenting", headers=headers).status_code == 200
    blocked = c.get("/api/insights/parenting", headers=headers)
    assert blocked.status_code == 429 and blocked.json()["code"] == "daily_limit"
