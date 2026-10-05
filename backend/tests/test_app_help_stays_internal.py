"""`app_help` is a server-side domain: no response, stream frame or chat row a
client reads ever carries it.

Every installed build labels the answer chip from the domain code
(mobile `Domain.fromWire`), and none of them knows `app_help` — an unknown code
renders «غير محدد» under every app answer, for every user, until a new build
reaches them all. So the server keeps the domain for routing, retrieval,
guardrails and the prompt label, and shows a client the general domain: the
code every build already receives for a general answer.

The pipeline below runs the real routers with only the heavy parts stubbed
(classification says `app_help`, retrieval returns an app_help unit, the model
is a scripted fake) and searches every byte a client could read for the
internal code.
"""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.taxonomy import client_domain
from app.models.api import AssistantReply
from app.routers import assistant
from app.services import ai_gateway, answer_cache
from app.services import conversation_store as store

INTERNAL = "app_help"


def test_the_mapping_touches_only_the_internal_domain():
    assert client_domain(INTERNAL) == "general"
    for known in ("medical", "cyber", "islamic_parenting", "development", "aqeedah", "fiqh", "general", ""):
        assert client_domain(known) == known
    assert client_domain(None) is None


def test_a_reply_never_carries_the_internal_domain():
    reply = AssistantReply(reply_text="…", domain=INTERNAL, severity="خفيف", needs_human_review=False)
    assert reply.domain == "general"
    assert INTERNAL not in reply.model_dump_json()


def test_chat_rows_are_written_and_read_back_as_a_client_may_see_them():
    session_id = store.create_session(f"apphelp-{uuid.uuid4().hex[:12]}")
    q = store.add_message(session_id, "user", "كيف أحذف حسابي؟")
    store.update_classification(q, domain=INTERNAL, severity="خفيف")
    store.add_message(session_id, "assistant", "من «المزيد» ثم «الإعدادات»…", domain=INTERNAL)
    # …and a row some future writer stored raw is still read back mapped.
    conn = store.get_conn()
    try:
        conn.execute("INSERT INTO chat_messages (session_id, role, content, domain) VALUES (?, 'assistant', 'x', ?)",
                     (session_id, INTERNAL))
        conn.commit()
        stored = [r[0] for r in conn.execute(
            "SELECT domain FROM chat_messages WHERE session_id = ? ORDER BY id", (session_id,))]
    finally:
        conn.close()
    assert stored[:2] == ["general", "general"]
    assert INTERNAL not in json.dumps(store.get_session(session_id), ensure_ascii=False)


# ── the real routers ───────────────────────────────────────────────────────

def _scripted_provider():
    class _Scripted:
        name = "fake"
        model = "fake-model"

        def __init__(self, *a, **k):
            self.timeout = 60

        def stream(self, prompt, *, options):
            for token in ("افتح «المزيد» ثم ", "«الإعدادات» ثم «الخصوصية وبياناتك»."):
                yield {"response": token, "done": False}
            yield {"response": "", "done": True, "prompt_eval_count": 1, "eval_count": 1}

        def generate(self, prompt, *, options):
            return {"response": "افتح «المزيد» ثم «الإعدادات».", "done": True}

    return _Scripted


@pytest.fixture
def app_question(monkeypatch):
    """Classification says app_help and retrieval returns an app_help unit."""
    seen = SimpleNamespace(domains=[])

    async def _classify(query_text):
        return [INTERNAL], ""

    def _retrieve(**kwargs):
        seen.domains.append(kwargs.get("domains"))
        return [{
            "unit_id": "app-2e094883",
            "document": "passage: حذف الحساب كله: «المزيد» ثم «الإعدادات» ثم «الخصوصية وبياناتك» ثم «حذف الحساب».",
            "metadata": {"domain": INTERNAL, "reference_info": "دليل تطبيق «المربّي» — الخصوصية وحذف الحساب",
                         "title": "حذف الحساب", "age_group": "unspecified"},
            "rerank_score": 2.0, "distance": 0.1, "source_domain": INTERNAL,
        }]

    async def _no_ayah(_q):
        return None

    monkeypatch.setattr(assistant, "_classify_and_rewrite", _classify)
    monkeypatch.setattr(answer_cache, "lookup", lambda *a, **k: None)
    monkeypatch.setattr(answer_cache, "store", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "retrieve_hybrid", _retrieve)
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", _no_ayah)
    monkeypatch.setattr(assistant, "log_session", lambda **kw: None)
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "OllamaProvider", _scripted_provider())
    ai_gateway._gateway = None
    yield seen
    ai_gateway._gateway = None
    getattr(assistant, "_ACTIVE_TURNS", {}).clear()


def _client_with_session():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()
    sess = client.post("/api/chat/sessions", json={"device_id": f"apphelp-{uuid.uuid4().hex[:12]}"}).json()
    client.headers["Authorization"] = f"Bearer {sess['token']}"
    return client, sess["session_id"]


def _ask(client, session_id, path):
    return client.post(path, json={
        "age_group": "7-9", "severity": "خفيف",
        "message_text": "كيف أحذف حسابي من التطبيق؟", "session_id": session_id,
    })


def _history(client, session_id) -> str:
    resp = client.get(f"/api/chat/sessions/{session_id}")
    assert resp.status_code == 200, resp.text
    return resp.text


def test_the_stream_never_carries_the_internal_domain(app_question):
    client, session_id = _client_with_session()
    try:
        resp = _ask(client, session_id, "/api/assistant/stream")
        assert resp.status_code == 200, resp.text
        body = resp.text
        assert "event: done" in body
        done = json.loads(body.split("event: done\ndata: ", 1)[1].split("\n", 1)[0])
        assert done["domain"] == "general"
        assert INTERNAL not in body
        assert app_question.domains == [[INTERNAL]]   # retrieval still searched app_help
        history = _history(client, session_id)
        assert INTERNAL not in history
        assert '"domain":"general"' in history.replace(" ", "")
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize("path", ["/api/assistant/draft", "/api/assistant/query"])
def test_the_blocking_answer_never_carries_the_internal_domain(app_question, path):
    client, session_id = _client_with_session()
    try:
        resp = _ask(client, session_id, path)
        assert resp.status_code == 200, resp.text
        assert resp.json()["domain"] == "general"
        assert INTERNAL not in resp.text
        assert INTERNAL not in _history(client, session_id)
    finally:
        client.__exit__(None, None, None)
