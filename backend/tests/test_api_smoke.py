"""API smoke tests — endpoint wiring, guardrails, auth, and session persistence.

The LLM gateway and the vector retrieval are mocked, so these run fast and
need neither Ollama nor the ONNX model download.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_gateway import LLMResult


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(monkeypatch):
    # mock retrieval → one canned unit; skip index build
    monkeypatch.setattr("app.routers.assistant._ensure_index", lambda: None)
    monkeypatch.setattr(
        "app.routers.assistant.retrieve_multi_domain",
        lambda **kw: [{
            "unit_id": "test-1",
            "document": "نص إرشادي تجريبي للأهل.",
            "metadata": {"reference_info": "مرجع تجريبي"},
            "distance": 0.2,
        }],
    )

    # mock gateway → deterministic reply (no Ollama)
    class _GW:
        async def generate(self, prompt, **kw):
            return LLMResult(text="رد تجريبي مفيد.", model="test", latency_ms=1)

    monkeypatch.setattr("app.services.llm_service.get_gateway", lambda: _GW())
    with TestClient(app) as c:
        yield c


@pytest.fixture
def authed_client(client):
    """Create a session + return (TestClient, token) for auth'd requests."""
    r = client.post("/api/chat/sessions", json={})
    assert r.status_code == 201
    token = r.json()["token"]
    return client, token


def _post(client, token, path="/api/assistant/query", **json_kw):
    """Helper: POST with auth header."""
    if token:
        return client.post(path, json=json_kw, headers=_auth_headers(token))
    return client.post(path, json=json_kw)


def _get(client, token, path):
    """Helper: GET with auth header."""
    if token:
        return client.get(path, headers=_auth_headers(token))
    return client.get(path)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_create_session_returns_token(client):
    """Session creation returns both session_id and auth token."""
    r = client.post("/api/chat/sessions", json={"device_id": "test-device-1"})
    assert r.status_code == 201
    body = r.json()
    assert "session_id" in body
    assert "token" in body
    assert body["token"].startswith("tg_")


def test_banned_intent_returns_banned_mode(authed_client):
    client, token = authed_client
    r = _post(client, token, age_group="7-9", severity="متوسط", message_text="كيف أؤذي طفلي")
    assert r.status_code == 200
    assert r.json()["mode"] == "banned"
    assert r.json()["needs_human_review"] is True


def test_happy_path_llm_generated(authed_client):
    client, token = authed_client
    r = _post(client, token, age_group="7-9", severity="متوسط", message_text="ابني قلق من المدرسة")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "llm_generated"
    assert "رد تجريبي" in body["reply_text"]


def test_session_persists_history(authed_client):
    client, token = authed_client
    # Create session
    r = client.post("/api/chat/sessions", json={})
    body = r.json()
    sid, token2 = body["session_id"], body["token"]

    # Send query with this session
    _post(client, token2, age_group="7-9", severity="متوسط",
          message_text="سؤال أول", session_id=sid)

    # Get session details
    detail = _get(client, token2, f"/api/chat/sessions/{sid}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]


def test_without_token_returns_401(client):
    """Requests without auth token get 401."""
    r = client.post("/api/assistant/query", json={
        "age_group": "7-9", "severity": "متوسط", "message_text": "سؤال",
    })
    assert r.status_code == 401


def test_invalid_token_returns_401(client):
    """Requests with invalid token get 401."""
    r = client.post("/api/assistant/query", json={
        "age_group": "7-9", "severity": "متوسط", "message_text": "سؤال",
    }, headers=_auth_headers("tg_invalidtoken123"))
    assert r.status_code == 401


def test_unknown_session_404(authed_client):
    client, token = authed_client
    r = _post(client, token, age_group="7-9", severity="متوسط",
              message_text="x", session_id="does-not-exist")
    assert r.status_code == 404


def test_stateless_conversation_history(authed_client):
    """Client-sent conversation_history is accepted and doesn't break the endpoint."""
    client, token = authed_client
    r = _post(client, token, age_group="7-9", severity="متوسط",
              message_text="ابني ما يصلي",
              conversation_history=[
                  {"role": "user", "content": "كيف أعلّم الصلاة؟"},
                  {"role": "assistant", "content": "ابدأ بالقدوة الحسنة."},
              ])
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in ("llm_generated", "retrieval_only")
    assert body.get("session_id") is None  # stateless: no server session


def test_domain_field_optional(authed_client):
    """Requests without a domain field are accepted (domain auto-detected)."""
    client, token = authed_client
    r = _post(client, token, age_group="4-6", severity="خفيف",
              message_text="ابنتي خجولة جداً")
    assert r.status_code == 200
    assert r.json().get("domain")  # auto-detected domain must be non-empty
