"""A medical question the knowledge base cannot answer is referred to a doctor,
not sent to the off-topic pivot.

`NoConfidentMatch` (reranker floor) used to route every "nothing relevant"
question to the pivot: a brief answer from general knowledge plus an activity.
Right for a recipe, wrong for "how many units of insulin before lunch" (golden
g-104). When the classifier says the question is medical, the parent now gets
the policies' own "see a human specialist" message instead. Everything else is
unchanged: non-medical no-match still pivots, a plain empty list still says
"not enough information", and the emergency / banned / fiqh paths run before
retrieval and never get here.
"""
import json

import pytest

from app.config.guardrails_loader import load_guardrails_config
from app.routers import assistant
from app.services.guardrails import (
    _MEDICAL_REFERRAL_EN, _build_fallback_message, medical_referral_text,
)
from app.services.reranker import NoConfidentMatch

INSULIN_AR = "طفلي مصاب بمرض السكري النوع الأول، كم وحدة أنسولين أعطيه قبل الغداء؟"
INSULIN_EN = "How many units of insulin should my diabetic child get before lunch?"
POLICIES = load_guardrails_config()
REFERRAL_AR = POLICIES["global"]["high_risk_fallback_message"].strip()


# ── unit: the routing predicate and the text ────────────────────────────────

def test_predicate_true_only_for_a_real_medical_classification_with_a_no_match():
    nm = NoConfidentMatch(-6.5)
    assert assistant._is_medical_no_match(nm, ["medical"], "medical", False)
    # non-medical no-match -> pivot
    assert not assistant._is_medical_no_match(nm, ["cyber"], "cyber", False)
    assert not assistant._is_medical_no_match(nm, ["fiqh", "cyber"], "fiqh", False)
    # a plain empty list (no candidates / reranker off) is not a no-match
    assert not assistant._is_medical_no_match([], ["medical"], "medical", False)
    # "general" questions skip retrieval and keep the pivot
    assert not assistant._is_medical_no_match(nm, ["medical"], "medical", True)


def test_predicate_ignores_the_positional_medical_of_an_unclassified_question():
    # classification failed -> all five domains, "medical" first by position only
    uncertain = ["medical", "cyber", "fiqh", "development", "aqeedah"]
    assert not assistant._is_medical_no_match(
        NoConfidentMatch(-7.0), uncertain, "medical", False)


def test_predicate_false_when_a_unit_with_its_own_score_is_present():
    enriched = NoConfidentMatch(-7.0)
    enriched.insert(0, {"unit_id": "tafsir_2_255", "rerank_score": 1.0})
    assert not assistant._is_medical_no_match(enriched, ["medical"], "medical", False)


def test_referral_text_reuses_the_policies_message_in_arabic():
    assert medical_referral_text(POLICIES, "ar") == REFERRAL_AR
    assert medical_referral_text(POLICIES, "ar", "سكري", "4-6") == REFERRAL_AR
    assert medical_referral_text(POLICIES, None) == REFERRAL_AR
    assert "طبيب" in REFERRAL_AR
    # the same builder the forced-fallback path uses, so editing the YAML edits both
    assert REFERRAL_AR == _build_fallback_message("medical", "", "", POLICIES)


def test_referral_text_is_english_for_a_latin_script_parent():
    for lang in ("en", "fr"):
        assert medical_referral_text(POLICIES, lang) == _MEDICAL_REFERRAL_EN
    assert "doctor" in _MEDICAL_REFERRAL_EN
    assert not any("؀" <= ch <= "ۿ" for ch in _MEDICAL_REFERRAL_EN)


def test_referral_text_falls_back_to_a_safe_default_without_policies():
    text = medical_referral_text({}, "ar", "سكري", "4-6")
    assert "مختص" in text and "تشخيصًا طبيًا" in text


# ── through the real /draft and /stream routes ──────────────────────────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.db.init_db import init_db
    from app.main import app
    from app.services import fiqh_guard

    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)
    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _auth(c, device):
    r = c.post("/api/chat/sessions", json={"device_id": device})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _route(monkeypatch, units, domains):
    seen = {"generate_reply": 0, "pivot": 0, "pivot_prompt": 0}

    async def _classify(q):
        return list(domains), ""

    async def _no_ayah(_q):
        return None

    async def _pivot(*a, **k):
        seen["pivot"] += 1
        return "جواب عام قصير ثم نشاط تربوي."

    async def _reply(*a, **k):
        seen["generate_reply"] += 1
        return "جواب مبني على الوحدات"

    def _pivot_prompt(*a, **k):
        seen["pivot_prompt"] += 1
        return "prompt"

    monkeypatch.setattr(assistant, "_classify_and_rewrite", _classify)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", _no_ayah)
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "retrieve_hybrid", lambda **k: units)
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "generate_general_pivot", _pivot)
    monkeypatch.setattr(assistant, "build_pivot_prompt", _pivot_prompt)
    monkeypatch.setattr(assistant, "generate_reply", _reply)

    class _NoModel:  # a pivot that does get streamed must not reach a real provider
        def stream(self, *a, **k):
            raise RuntimeError("no model in this test")

        def note_stream_stall(self, *a, **k):
            pass

    monkeypatch.setattr(assistant, "get_gateway", lambda: _NoModel())
    monkeypatch.setattr("app.services.answer_cache.lookup", lambda *a, **k: None)
    return seen


def _draft(c, headers, text):
    return c.post("/api/assistant/draft", headers=headers, json={
        "age_group": "4-6", "severity": "خفيف", "message_text": text}).json()


def test_draft_medical_no_match_gets_the_doctor_text_not_the_pivot(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.52), ["medical"])
    body = _draft(client, _auth(client, "dev-med-1"), INSULIN_AR)
    assert body["reply_text"] == REFERRAL_AR
    assert body["mode"] == "retrieval_only"
    assert body["domain"] == "medical"
    assert body["metadata"]["off_topic"] is False and body["metadata"]["sources"] == []
    assert body["metadata"]["top_rerank"] == -6.52  # the best score seen, kept for telemetry
    assert seen["pivot"] == 0 and seen["generate_reply"] == 0


def test_draft_medical_no_match_in_english_gets_the_english_text(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.52), ["medical"])
    body = _draft(client, _auth(client, "dev-med-2"), INSULIN_EN)
    assert body["reply_text"] == _MEDICAL_REFERRAL_EN
    assert seen["pivot"] == 0 and seen["generate_reply"] == 0


def test_draft_non_medical_no_match_still_pivots(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.7), ["cyber"])
    body = _draft(client, _auth(client, "dev-med-3"), "إزاي أظبط إعدادات راوتر لحجب مواقع؟")
    assert body["mode"] == "general_pivot"
    assert body["metadata"]["off_topic"] is True
    assert body["reply_text"] != REFERRAL_AR
    assert seen == {"generate_reply": 0, "pivot": 1, "pivot_prompt": 0}


def test_draft_plain_empty_list_keeps_the_not_enough_information_text(client, monkeypatch):
    seen = _route(monkeypatch, [], ["medical"])
    body = _draft(client, _auth(client, "dev-med-4"), INSULIN_AR)
    assert "لا توجد معلومات كافية" in body["reply_text"]
    assert body["reply_text"] != REFERRAL_AR
    assert body["metadata"]["off_topic"] is False
    assert seen["pivot"] == 0 and seen["generate_reply"] == 0


def test_draft_unclassified_question_keeps_the_pivot(client, monkeypatch):
    uncertain = ["medical", "cyber", "fiqh", "development", "aqeedah"]
    seen = _route(monkeypatch, NoConfidentMatch(-7.0), uncertain)
    body = _draft(client, _auth(client, "dev-med-5"), INSULIN_EN)
    assert body["mode"] == "general_pivot" and seen["pivot"] == 1


def _done(body: str) -> dict:
    return json.loads(body.split("event: done\ndata: ", 1)[1].split("\n", 1)[0])


def _stream(c, headers, text):
    return c.post("/api/assistant/stream", headers=headers, json={
        "age_group": "4-6", "severity": "خفيف", "message_text": text})


def test_stream_medical_no_match_sends_the_doctor_text_without_streaming_a_pivot(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.52), ["medical"])
    resp = _stream(client, _auth(client, "dev-med-6"), INSULIN_AR)
    assert resp.status_code == 200
    done = _done(resp.text)
    assert done["reply_text"] == REFERRAL_AR
    assert done["mode"] == "retrieval_only" and done["domain"] == "medical"
    assert seen["pivot_prompt"] == 0 and seen["pivot"] == 0 and seen["generate_reply"] == 0


def test_stream_non_medical_no_match_still_builds_the_pivot_prompt(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.7), ["cyber"])
    resp = _stream(client, _auth(client, "dev-med-7"), "إزاي أظبط إعدادات راوتر لحجب مواقع؟")
    assert resp.status_code == 200
    assert seen["pivot_prompt"] == 1


def test_stream_plain_empty_list_keeps_the_not_enough_information_text(client, monkeypatch):
    seen = _route(monkeypatch, [], ["medical"])
    resp = _stream(client, _auth(client, "dev-med-8"), INSULIN_AR)
    assert "لا توجد معلومات كافية" in _done(resp.text)["reply_text"]
    assert seen["pivot_prompt"] == 0
