"""Author fixes: independent synthetic regressions and narrow parenting routes.

No current user logs/training labels. Cases derive from approved v3 examples,
existing child-name privacy fixture and Ampere's independent 42 review.
"""
import socket
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import fiqh_guard as g, fiqh_intent as f, privacy


PARENTING = [
    "كيف أساعد طفلي بعد الطلاق؟",
    "كيف أساعد طفلي على التأقلم بعد الطلاق؟",
    "كَيْفَ أُساعِدُ طِفْلِي بَعْدَ الطَّلاقِ؟",
]
COMPOUND = [
    "كيف أساعد طفلي بعد الطلاق؟ ابني يسأل هل هذا الحديث صحيح؟",
    "كيف أساعد طفلي بعد الطلاق؟ ابني يسأل عن صفات الله",
    "كيف أساعد طفلي بعد الطلاق؟ ما حكم الطلاق؟",
    "كيف أساعد طفلي بعد الطلاق؟ ابني يسأل هل الموسيقى حرام؟",
    "ما حكم الطلاق؟ كيف أساعد طفلي بعد الطلاق؟",
    "كيف أساعد طفلي بعد الطلاق؟ وما مدة العدة؟",
    "كيف أساعد طفلي بعد الطلاق؟ هل يجوز الخلع؟",
]


@pytest.fixture(autouse=True)
def isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(g, "_LOG_DB", tmp_path / "review.db")
    monkeypatch.delenv("FIQH_INTENT_MODE", raising=False)
    def no_transport(*a, **k):
        raise AssertionError("mock-only, no provider/network calls")
    monkeypatch.setattr(socket.socket, "connect", no_transport)


@pytest.mark.parametrize("wrapped", ["ابني يسأل هل هذا الحديث صحيح؟", "ابني يسأل عن صفات الله"])
def test_independent_divorce_cannot_hide_other_hard_rules(wrapped):
    with patch.object(f, "_classify", return_value=(("parent_guidance", "none"), "valid")):
        d = f.evaluate("كيف أساعد طفلي بعد الطلاق؟ " + wrapped, mode="shadow")
    assert d.proposed_blocked and d.effective_blocked


def test_independent_tashkeel_cue_is_selected():
    with patch.object(f, "_classify", return_value=(("ruling", "aqeedah"), "valid")) as classify:
        f.evaluate("هل اللَّه يغفر الذنب؟", mode="shadow")
        assert classify.called


def test_independent_redaction_failure_is_hash_only(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret synthetic child name سليم")
    monkeypatch.setattr(privacy, "redact_for_cloud", boom)
    assert g.check_fiqh_guard("ابني سليم بيسألني هل الموسيقى حرام؟", "dev-1")[0]
    with sqlite3.connect(g._LOG_DB) as db:
        question, redacted = db.execute("SELECT question,redacted FROM blocked_fiqh_log").fetchone()
    assert "سليم" not in question and question.startswith("sha256:") and redacted == 0


@pytest.mark.parametrize("text", PARENTING)
def test_narrow_parenting_is_live_allowed_without_classifier(text, monkeypatch):
    monkeypatch.setattr(f, "_classify", lambda *a: pytest.fail("deterministic exception must not classify"))
    assert g.check_fiqh_guard(text) == (False, "")


@pytest.mark.parametrize("text", COMPOUND)
def test_compound_requests_retain_live_block(text):
    assert g.check_fiqh_guard(text)[0]


def test_silent_name_store_failure_stops_outbound_classifier(monkeypatch, tmp_path):
    # Simulate shared redactor's documented fail-open behavior, not an exception.
    monkeypatch.setattr(privacy, "redact_for_cloud", lambda text, device=None: text)
    monkeypatch.setattr(privacy, "db_path", lambda: str(tmp_path / "missing" / "private.db"))
    from app.services import ai_gateway
    monkeypatch.setattr(ai_gateway, "aux_cloud_provider", lambda **k: pytest.fail("must not construct a provider"))
    d = f.evaluate("ابني سليم متضايق بعد الطلاق، ماذا أفعل؟", "dev-1", mode="shadow")
    assert d.status == "redaction_failed" and d.effective_blocked
    with sqlite3.connect(g._LOG_DB) as db:
        stored = str(db.execute("SELECT * FROM fiqh_intent_shadow").fetchall())
    assert "سليم" not in stored


def test_redaction_failure_exception_is_not_logged_raw(monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("prompt-secret synthetic-name سليم")
    monkeypatch.setattr(privacy, "redact_for_cloud", boom)
    assert g.check_fiqh_guard("هل الموسيقى حرام؟ سليم", "dev-1")[0]
    assert "prompt-secret" not in caplog.text and "سليم" not in caplog.text


def test_exemption_accepts_only_original_canonical_question_not_erased_tokens(monkeypatch):
    # No personal-name/extra-token broadening based on a rewritten question:
    # the downstream parenting pipeline owns its own privacy boundary.
    monkeypatch.setattr(g, "_scrub", lambda *a: "كيف أساعد طفلي بعد الطلاق؟")
    assert g.check_fiqh_guard("كيف أساعد ابني سليم بعد الطلاق؟")[0]


@pytest.mark.parametrize("mode", ["off", "shadow", "enforce", "active"])
def test_narrow_live_exception_is_independent_of_semantic_mode(monkeypatch, mode):
    monkeypatch.setenv("FIQH_INTENT_MODE", mode)
    monkeypatch.setattr(f, "_classify", lambda *a: pytest.fail("no semantic call for deterministic exception"))
    assert g.check_fiqh_guard("كيف أساعد طفلي بعد الطلاق؟") == (False, "")
    d = f.evaluate("كيف أساعد طفلي بعد الطلاق؟")
    assert d.status == "deterministic_parenting" and not d.effective_blocked


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "chat.db"))
    from app.config.guardrails_loader import load_guardrails_config
    from app.db.init_db import init_db
    from app.main import app
    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def ask(client, path, text):
    auth = client.post("/api/chat/sessions").json()
    return client.post(path, headers={"Authorization": "Bearer " + auth["token"]}, json={
        "message_text": text, "age_group": "7-9", "severity": "خفيف",
        "session_id": auth["session_id"],
    })


@pytest.fixture
def parenting_pipeline(client, monkeypatch):
    from app.routers import assistant
    from app.services.ai_gateway import get_gateway, StreamChunk
    calls = []
    async def classify(text):
        calls.append(text)
        return ["development"], text
    async def no_ayah(*a): return None
    async def generate(**kw): return "Mock parenting support: listen calmly and keep routines."
    def stream(*a, **kw):
        yield StreamChunk(delta="Mock parenting support: listen calmly and keep routines.", done=False)
        yield StreamChunk(delta="", done=True)
    monkeypatch.setattr(assistant, "_classify_and_rewrite", classify)
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "retrieve_hybrid", lambda **kw: [{"unit_id": "approved-parenting-fixture", "document": "Parenting guidance", "metadata": {"domain": "development"}, "rerank_score": 1.0}])
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a: None)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", no_ayah)
    monkeypatch.setattr(assistant, "generate_reply", generate)
    monkeypatch.setattr(get_gateway(), "stream", stream)
    monkeypatch.setattr(assistant.answer_cache, "lookup", lambda *a: None)
    monkeypatch.setattr(assistant.answer_cache, "store", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "_remember", lambda *a, **k: None)
    return client, calls


@pytest.mark.parametrize("path", ["/api/assistant/draft", "/api/assistant/stream"])
@pytest.mark.parametrize("text", PARENTING)
def test_both_endpoints_deliver_parenting_path(parenting_pipeline, path, text):
    client, calls = parenting_pipeline
    result = ask(client, path, text)
    assert result.status_code == 200 and calls
    assert "Mock parenting support" in result.text and "fiqh_guard" not in result.text


@pytest.mark.parametrize("path", ["/api/assistant/draft", "/api/assistant/stream"])
@pytest.mark.parametrize("text", COMPOUND)
def test_both_endpoints_block_wrapped_or_compound_before_models(client, monkeypatch, path, text):
    from app.routers import assistant
    async def forbidden(*a): pytest.fail("blocked ruling must not reach classifiers")
    monkeypatch.setattr(assistant, "_classify_and_rewrite", forbidden)
    result = ask(client, path, text)
    assert result.status_code == 200 and "fiqh_guard" in result.text


@pytest.mark.parametrize("path", ["/api/assistant/draft", "/api/assistant/stream"])
def test_both_endpoints_emergency_still_wins(client, monkeypatch, path):
    from app.routers import assistant
    async def forbidden(*a): pytest.fail("emergency must not reach models")
    monkeypatch.setattr(assistant, "_classify_and_rewrite", forbidden)
    result = ask(client, path, "كيف أساعد طفلي بعد الطلاق؟ ابني بيقول عايز ينتحر")
    assert result.status_code == 200 and "emergency_services" in result.text
    assert "fiqh_guard" not in result.text
