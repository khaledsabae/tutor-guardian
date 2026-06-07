"""API smoke tests — endpoint wiring, guardrails, and session persistence.

The LLM gateway and the vector retrieval are mocked, so these run fast and
need neither Ollama nor the ONNX model download.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_gateway import LLMResult


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


def test_banned_intent_returns_banned_mode(client):
    r = client.post("/api/assistant/query", json={
        "age_group": "7-9", "severity": "متوسط", "message_text": "كيف أؤذي طفلي",
    })
    assert r.status_code == 200
    assert r.json()["mode"] == "banned"
    assert r.json()["needs_human_review"] is True


def test_happy_path_llm_generated(client):
    r = client.post("/api/assistant/query", json={
        "age_group": "7-9", "severity": "متوسط", "message_text": "ابني قلق من المدرسة",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "llm_generated"
    assert "رد تجريبي" in body["reply_text"]


def test_session_persists_history(client):
    sid = client.post("/api/chat/sessions", json={}).json()["session_id"]
    client.post("/api/assistant/query", json={
        "age_group": "7-9", "severity": "متوسط",
        "message_text": "سؤال أول", "session_id": sid,
    })
    detail = client.get(f"/api/chat/sessions/{sid}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]


def test_unknown_session_404(client):
    r = client.post("/api/assistant/query", json={
        "age_group": "7-9", "severity": "متوسط",
        "message_text": "x", "session_id": "does-not-exist",
    })
    assert r.status_code == 404
