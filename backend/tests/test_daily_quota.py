"""Fair-use daily AI quota tests (growth plan §5.1).

The daily cap must: count only AI-scope POSTs, refuse with the gentle Arabic
message (never a paywall), reset on UTC-day change, and leave the general API
scope untouched.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import rate_limit as rl


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(rl.RateLimitMiddleware)

    @app.post("/api/assistant/stream")
    def ai_post():
        return {"ok": True}

    @app.get("/api/program/story-themes")
    def themes():
        return {"ok": True}

    @app.post("/api/children")
    def general_post():
        return {"ok": True}

    return app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(rl, "_AI_DAILY_LIMIT", 3)
    monkeypatch.setattr(rl, "_LIMIT", 1000)  # keep the minute window out of the way
    monkeypatch.setattr(rl, "_GENERAL_LIMIT", 1000)
    return TestClient(_make_app())


def test_daily_quota_blocks_after_limit_with_gentle_message(client):
    for _ in range(3):
        assert client.post("/api/assistant/stream").status_code == 200
    resp = client.post("/api/assistant/stream")
    assert resp.status_code == 429
    body = resp.json()
    assert body["code"] == "daily_limit"
    assert "غدًا بإذن الله" in body["detail"]
    assert "ادفع" not in body["detail"]
    assert int(resp.headers["Retry-After"]) <= 24 * 3600


def test_get_catalogue_does_not_consume_quota(client):
    for _ in range(10):
        assert client.get("/api/program/story-themes").status_code == 200
    # Quota untouched — the three POSTs still pass.
    for _ in range(3):
        assert client.post("/api/assistant/stream").status_code == 200


def test_general_scope_unaffected_by_daily_quota(client):
    for _ in range(3):
        client.post("/api/assistant/stream")
    assert client.post("/api/assistant/stream").status_code == 429
    assert client.post("/api/children").status_code == 200


def test_quota_resets_on_utc_day_change(client, monkeypatch):
    for _ in range(3):
        client.post("/api/assistant/stream")
    assert client.post("/api/assistant/stream").status_code == 429
    monkeypatch.setattr(
        rl.RateLimitMiddleware, "_utc_today", staticmethod(lambda: "2099-01-01")
    )
    assert client.post("/api/assistant/stream").status_code == 200


def test_zero_disables_daily_quota(monkeypatch):
    monkeypatch.setattr(rl, "_AI_DAILY_LIMIT", 0)
    monkeypatch.setattr(rl, "_LIMIT", 1000)
    client = TestClient(_make_app())
    for _ in range(30):
        assert client.post("/api/assistant/stream").status_code == 200
