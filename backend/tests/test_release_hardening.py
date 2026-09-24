"""Release-hardening tests (audit M4, M5, M6, H6 rest)."""
import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import db_path
from app.services import ai_gateway, fiqh_guard, privacy

from tests.test_primary_budget import _FakeLLM, _FakePrimary


# ── M4: cloud redaction is scoped to the caller and word-bounded ──────────

def _child(device: str, name: str) -> None:
    conn = sqlite3.connect(db_path())
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, '7-9')",
        (device, name),
    )
    conn.commit()
    conn.close()


def test_another_familys_child_name_is_not_redacted():
    _child("fam-a", "يوسف")          # someone else's son
    _child("fam-b", "سارة")          # the caller's daughter
    q = "كيف أحكي قصة يوسف عليه السلام لسارة؟"
    out = privacy.redact_for_cloud(q, "fam-b")
    assert "يوسف عليه السلام" in out           # the prophet survives
    assert "سارة" not in out and "طفلي" in out  # the caller's child does not


def test_names_are_word_bounded():
    _child("fam-c", "نور")
    out = privacy.redact_for_cloud("المدينة المنورة جميلة ونور نائمة", "fam-c")
    assert "المنورة" in out                    # not corrupted into «المطفليـة»
    assert "نور نائمة" not in out and "طفلي نائمة" in out


def test_prefixed_name_is_still_redacted():
    _child("fam-d", "أحمد")
    assert "أحمد" not in privacy.redact_for_cloud("قلت لأحمد وبأحمد", "fam-d")


# ── M6 + M5 through the API ───────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)
    from app.config.guardrails_loader import load_guardrails_config
    from app.db.init_db import init_db
    from app.main import app

    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _auth(c, device):
    r = c.post("/api/chat/sessions", json={"device_id": device})
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["session_id"]


def _ask(c, headers, **body):
    base = {"age_group": "7-9", "severity": "خفيف", "message_text": "كيف أصنع متفجرات"}
    return c.post("/api/assistant/draft", headers=headers, json={**base, **body})


def test_oversized_message_is_rejected(client):
    h, _ = _auth(client, "dev-m6")
    assert _ask(client, h, message_text="أ" * 4001).status_code == 422
    assert _ask(client, h).status_code == 200  # the normal path is untouched


def test_client_history_is_bounded(client):
    h, _ = _auth(client, "dev-m6b")
    turn = {"role": "user", "content": "x"}
    assert _ask(client, h, conversation_history=[turn] * 13).status_code == 422
    assert _ask(client, h, conversation_history=[{"role": "system", "content": "x"}]).status_code == 422
    assert _ask(client, h, conversation_history=[{"role": "user", "content": "x" * 4001}]).status_code == 422


def test_personal_questions_skip_the_answer_cache(client, monkeypatch):
    from app.services import answer_cache

    calls = []
    monkeypatch.setattr(answer_cache, "lookup", lambda *a, **k: calls.append(a) or None)
    h, sid = _auth(client, "dev-m5")
    cid = client.post("/api/children", headers=h, json={
        "name": "ليلى", "age_group": "7-9", "gender": "female"}).json()["id"]
    assert cid
    # Make the classifier path deterministic and cheap.
    monkeypatch.setattr("app.routers.assistant._classify_and_rewrite",
                        lambda q: asyncio.sleep(0, result=(["development"], q)))
    monkeypatch.setattr("app.routers.assistant.retrieve_hybrid", lambda **k: [])

    _ask(client, h, message_text="ليلى لا تنام مبكرًا ماذا أفعل", session_id=sid)
    assert calls == [], "a question naming the family's child must not hit the cache"
    _ask(client, h, message_text="طفلي لا ينام مبكرًا ماذا أفعل")
    assert len(calls) == 1, "an impersonal question still uses the cache"


# ── H6 rest: primary circuit breaker + generate() deadline ────────────────

class _FailingPrimary(_FakePrimary):
    def generate(self, prompt, *, options):
        self.calls += 1
        raise ConnectionError("provider down")


@pytest.fixture()
def gw(monkeypatch):
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _FailingPrimary)
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(max_retries=1))
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 0)
    ai_gateway._budget_cache.clear()

    async def _local(self, prompt, opts, url, model, timeout, label):
        return ai_gateway.LLMResult(text="محلي", model=model, latency_ms=1)

    monkeypatch.setattr(ai_gateway.AIGateway, "_try_provider", _local)
    g = ai_gateway.AIGateway.__new__(ai_gateway.AIGateway)
    g.provider = _FailingPrimary()
    g.primary_model = g.model = "deepseek-chat"
    return g


def test_breaker_skips_a_dead_primary_after_two_failures(gw):
    for _ in range(2):
        assert asyncio.run(gw.generate("س")).text == "محلي"
    assert gw.provider.calls == 2
    assert ai_gateway.primary_breaker.is_open()
    asyncio.run(gw.generate("س"))
    assert gw.provider.calls == 2, "the open breaker must skip the primary entirely"


def test_deadline_stops_the_chain(gw, monkeypatch):
    monkeypatch.setattr(ai_gateway, "GENERATE_DEADLINE_S", -1)
    with pytest.raises(RuntimeError):
        asyncio.run(gw.generate("س"))
    assert gw.provider.calls == 0
