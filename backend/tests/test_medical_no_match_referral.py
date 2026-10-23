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
    _MEDICAL_REFERRAL_EN, _MEDICAL_EMERGENCY_EN, _URGENCY_LINE_AR,
    _build_fallback_message, is_medical_query, is_urgent_medical_query,
    medical_referral_text,
)
from app.services.reranker import NoConfidentMatch

INSULIN_AR = "طفلي مصاب بمرض السكري النوع الأول، كم وحدة أنسولين أعطيه قبل الغداء؟"
INSULIN_EN = "How many units of insulin should my diabetic child get before lunch?"
POLICIES = load_guardrails_config()
POLICY_AR = POLICIES["global"]["high_risk_fallback_message"].strip()
EMERGENCY_AR = POLICIES["global"]["emergency_fallback_message"].strip()
# the Arabic referral: the policies' message plus the one-line urgency pointer
REFERRAL_AR = f"{POLICY_AR}\n\n{_URGENCY_LINE_AR}"


# ── unit: the routing predicate and the text ────────────────────────────────

def test_predicate_true_only_for_a_real_medical_classification_with_a_no_match():
    nm = NoConfidentMatch(-6.5)
    assert assistant._is_medical_no_match(nm, ["medical"], "medical", False, INSULIN_AR)
    # non-medical no-match -> pivot
    assert not assistant._is_medical_no_match(nm, ["cyber"], "cyber", False, INSULIN_AR)
    assert not assistant._is_medical_no_match(nm, ["fiqh", "cyber"], "fiqh", False, INSULIN_AR)
    # a plain empty list (no candidates / reranker off) is not a no-match
    assert not assistant._is_medical_no_match([], ["medical"], "medical", False, INSULIN_AR)
    # "general" questions skip retrieval and keep the pivot
    assert not assistant._is_medical_no_match(nm, ["medical"], "medical", True, INSULIN_AR)
    # no domains at all is not a classification
    assert not assistant._is_medical_no_match(nm, [], "medical", False, INSULIN_AR)
    # the wording must be medical too: behaviour in the `medical` domain pivots
    assert not assistant._is_medical_no_match(
        nm, ["medical"], "medical", False, "ابني بيغير من أخوه الصغير")
    assert not assistant._is_medical_no_match(nm, ["medical"], "medical", False)


def test_predicate_ignores_the_positional_medical_of_an_unclassified_question():
    # classification failed -> all five domains, "medical" first by position only
    uncertain = ["medical", "cyber", "fiqh", "development", "aqeedah"]
    assert not assistant._is_medical_no_match(
        NoConfidentMatch(-7.0), uncertain, "medical", False, INSULIN_AR)


def test_predicate_false_when_a_unit_with_its_own_score_is_present():
    enriched = NoConfidentMatch(-7.0)
    enriched.insert(0, {"unit_id": "tafsir_2_255", "rerank_score": 1.0})
    assert not assistant._is_medical_no_match(
        enriched, ["medical"], "medical", False, INSULIN_AR)


def test_referral_text_reuses_the_policies_message_in_arabic():
    assert medical_referral_text(POLICIES, "ar") == REFERRAL_AR
    assert medical_referral_text(POLICIES, "ar", "سكري", "4-6") == REFERRAL_AR
    assert medical_referral_text(POLICIES, None) == REFERRAL_AR
    assert "طبيب" in REFERRAL_AR
    # the same builder the forced-fallback path uses, so editing the YAML edits both
    assert REFERRAL_AR.startswith(_build_fallback_message("medical", "", "", POLICIES))
    # ... and it ends with the one short urgency line
    assert REFERRAL_AR.endswith("فاتصل بالإسعاف فورًا.")
    assert REFERRAL_AR.count("\n\n") == 1


def test_referral_text_is_english_for_a_latin_script_parent():
    for lang in ("en", "fr"):
        assert medical_referral_text(POLICIES, lang) == _MEDICAL_REFERRAL_EN
    assert "doctor" in _MEDICAL_REFERRAL_EN
    # generic wording, and the urgency sentence is part of it
    assert "knowledge base" in _MEDICAL_REFERRAL_EN
    assert _MEDICAL_REFERRAL_EN.endswith("call your local emergency number immediately.")
    assert not any("؀" <= ch <= "ۿ" for ch in _MEDICAL_REFERRAL_EN)


def test_referral_text_falls_back_to_a_safe_default_without_policies():
    text = medical_referral_text({}, "ar", "سكري", "4-6")
    assert "مختص" in text and "تشخيصًا طبيًا" in text
    assert text.endswith(_URGENCY_LINE_AR)


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


# ── the wording gate: a medical question vs behaviour filed under `medical` ──

MEDICAL_POSITIVES = [
    INSULIN_AR,
    INSULIN_EN,
    "كم جرعة بنادول أديها وهي سخنة؟",
    "هل أديه ميلاتونين عشان ينام؟",
    "ابني عنده تشنجات هل أديه دواء؟",
    "هل التطعيم آمن؟",
    "can I give ibuprofen with paracetamol",
    "is melatonin safe for my 6 year old",
    "ممكن تشخصلي حالة ابني؟",
    "بنتي عندها ربو وبتكح بالليل",
    "الدَّوَاء ده ينفع للرضيع؟",  # with diacritics
]

BEHAVIOUR_NEGATIVES = [
    "بنتي بتخاف من الضلمة بالليل",
    "ابني بيغير من أخوه الصغير",
    "ابني مابينامش بدري",
    "ابني بيكذب كتير",
    "ابني خجول ومش بيتكلم مع حد",
    "بدأت أحضنه قبل النوم وبقى أهدى",
    "my son is jealous of the baby",
    "he wakes up at night scared",
    "أعراض إدمان الشاشات",  # bare «أعراض» is a cyber phrase too
    "إزاي أعلم ابني الربوبية؟",  # ربو inside a longer word
    "ابني بيحب قصة القرصان",  # قرص inside a longer word
]


@pytest.mark.parametrize("text", MEDICAL_POSITIVES)
def test_gate_accepts_a_real_health_question(text):
    assert is_medical_query(text)


@pytest.mark.parametrize("text", BEHAVIOUR_NEGATIVES)
def test_gate_rejects_behaviour_filed_under_medical(text):
    assert not is_medical_query(text)


def test_gate_over_the_golden_set_hits_only_health_questions():
    """Which golden questions the gate lets through (all genuinely health
    questions); the rest of the 126 never become a medical referral."""
    from pathlib import Path
    gold = Path(__file__).resolve().parents[2] / "ops" / "eval" / "golden_set.jsonl"
    if not gold.exists():
        pytest.skip("golden set not in this checkout")
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line.strip()]
    hits = sorted(r["id"] for r in rows if is_medical_query(r["question"]))
    assert hits == ["g-048", "g-049", "g-057", "g-104", "g-109", "g-116", "g-120"]


@pytest.mark.parametrize("text", MEDICAL_POSITIVES)
def test_draft_medical_wording_gets_the_referral(client, monkeypatch, text):
    seen = _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    body = _draft(client, _auth(client, "dev-gate-pos"), text)
    assert body["mode"] == "retrieval_only" and body["metadata"]["off_topic"] is False
    assert seen["pivot"] == 0
    # urgent wording (the seizure one) is the emergency fallback; the rest the referral
    assert body["reply_text"] in (REFERRAL_AR, _MEDICAL_REFERRAL_EN, EMERGENCY_AR, _MEDICAL_EMERGENCY_EN)


@pytest.mark.parametrize("text", BEHAVIOUR_NEGATIVES)
def test_draft_behaviour_under_medical_keeps_the_pivot(client, monkeypatch, text):
    seen = _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    body = _draft(client, _auth(client, "dev-gate-neg"), text)
    assert body["mode"] == "general_pivot" and body["metadata"]["off_topic"] is True
    assert seen["pivot"] == 1
    assert body["reply_text"] not in (REFERRAL_AR, _MEDICAL_REFERRAL_EN, EMERGENCY_AR)


@pytest.mark.parametrize("text", BEHAVIOUR_NEGATIVES[:4] + ["my son is jealous of the baby"])
def test_stream_behaviour_under_medical_keeps_the_pivot(client, monkeypatch, text):
    seen = _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    resp = _stream(client, _auth(client, "dev-gate-neg-s"), text)
    assert resp.status_code == 200
    assert seen["pivot_prompt"] == 1


# ── urgency (168-B) ─────────────────────────────────────────────────────────

URGENT = [
    "ابني بلع قرص دوا من علبة جدته",
    "ابني أخد جرعة زيادة من الدوا",
    "أخدت له دوا غلط، أعمل إيه؟",
    "ابني عنده تشنج وجرعة الدوا فاتت",
    "طفلي مش بيرد وكان واخد دوا",
    "my child swallowed some pills, what dose is dangerous",
    "I gave him the wrong medicine",
    "can an overdose of paracetamol hurt a toddler",
]
NOT_URGENT = [INSULIN_AR, INSULIN_EN, "كم جرعة بنادول أديها وهي سخنة؟",
              "is melatonin safe for my 6 year old", "هل التطعيم آمن؟"]


@pytest.mark.parametrize("text", URGENT)
def test_urgent_wording_is_detected(text):
    assert is_medical_query(text) and is_urgent_medical_query(text)


@pytest.mark.parametrize("text", NOT_URGENT)
def test_calm_medical_wording_is_not_urgent(text):
    assert not is_urgent_medical_query(text)


def test_draft_urgent_medical_no_match_gets_the_emergency_fallback(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    body = _draft(client, _auth(client, "dev-urg-1"), "ابني بلع قرص دوا من علبة جدته")
    assert body["reply_text"] == EMERGENCY_AR
    assert body["escalation_target"] == "emergency_services"
    assert body["needs_human_review"] is True and body["mode"] == "retrieval_only"
    assert body["metadata"]["off_topic"] is False and body["metadata"]["sources"] == []
    assert seen["pivot"] == 0 and seen["generate_reply"] == 0


def test_draft_urgent_english_gets_an_english_emergency_text(client, monkeypatch):
    _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    body = _draft(client, _auth(client, "dev-urg-2"), "I gave him the wrong medicine, what now?")
    assert body["reply_text"] == _MEDICAL_EMERGENCY_EN
    assert body["escalation_target"] == "emergency_services"


def test_stream_urgent_medical_no_match_gets_the_emergency_fallback(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    done = _done(_stream(client, _auth(client, "dev-urg-3"),
                         "ابني أخد جرعة زيادة من الدوا").text)
    assert done["reply_text"] == EMERGENCY_AR
    assert done["escalation_target"] == "emergency_services"
    assert seen["pivot_prompt"] == 0 and seen["pivot"] == 0


def test_draft_calm_referral_ends_with_the_urgency_line(client, monkeypatch):
    _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    ar = _draft(client, _auth(client, "dev-urg-4"), INSULIN_AR)
    assert ar["reply_text"].endswith("فاتصل بالإسعاف فورًا.")
    assert ar["escalation_target"] is None
    en = _draft(client, _auth(client, "dev-urg-5"), INSULIN_EN)
    assert "emergency number" in en["reply_text"]


# ── /stream parity and policy escalation (168-d, 168-e) ─────────────────────

def test_stream_referral_carries_the_same_metadata_as_draft(client, monkeypatch):
    _route(monkeypatch, NoConfidentMatch(-6.52), ["medical"])
    d = _draft(client, _auth(client, "dev-par-1"), INSULIN_AR)
    s = _done(_stream(client, _auth(client, "dev-par-2"), INSULIN_AR).text)
    for key in ("top_rerank", "off_topic", "sources"):
        assert s["metadata"][key] == d["metadata"][key]
    assert s["metadata"] == {"top_rerank": -6.52, "off_topic": False, "sources": []}
    assert s["reply_text"] == d["reply_text"]


def test_stream_english_referral(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.52), ["medical"])
    done = _done(_stream(client, _auth(client, "dev-en-1"), INSULIN_EN).text)
    assert done["reply_text"] == _MEDICAL_REFERRAL_EN
    assert done["mode"] == "retrieval_only"
    assert seen["pivot_prompt"] == 0


def test_severe_medical_referral_keeps_the_policy_escalation(client, monkeypatch):
    _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    c, h = client, _auth(client, "dev-sev-1")
    body = c.post("/api/assistant/draft", headers=h, json={
        "age_group": "4-6", "severity": "شديد", "message_text": INSULIN_AR}).json()
    assert body["reply_text"] == REFERRAL_AR
    assert body["escalation_target"] == "pediatrician"
    assert body["needs_human_review"] is True
    s = _done(c.post("/api/assistant/stream", headers=_auth(c, "dev-sev-2"), json={
        "age_group": "4-6", "severity": "شديد", "message_text": INSULIN_AR}).text)
    assert s["reply_text"] == REFERRAL_AR and s["escalation_target"] == "pediatrician"


def test_emergency_severity_still_short_circuits_before_retrieval(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    body = client.post("/api/assistant/draft", headers=_auth(client, "dev-sev-3"), json={
        "age_group": "4-6", "severity": "طارئ", "message_text": INSULIN_AR}).json()
    assert body["reply_text"] == EMERGENCY_AR
    assert body["escalation_target"] == "emergency_services"
    assert seen["pivot"] == 0 and seen["generate_reply"] == 0


# ── a tafsir unit is evidence: never a referral (168-e) ─────────────────────

def _tafsir_route(monkeypatch, units, domains):
    seen = _route(monkeypatch, units, domains)

    async def _ayah(_q):
        return (2, 255)

    async def _tafsir(*a, **k):
        return [{"text": "x"}]

    monkeypatch.setattr(assistant, "resolve_ayah_reference", _ayah)
    monkeypatch.setattr(assistant, "fetch_tafsir", _tafsir)
    monkeypatch.setattr(assistant, "format_tafsir_for_context", lambda r: "تفسير آية الكرسي")
    return seen


def test_draft_tafsir_with_no_confident_match_is_not_a_medical_referral(client, monkeypatch):
    seen = _tafsir_route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    body = _draft(client, _auth(client, "dev-taf-1"),
                  "ما تفسير آية الكرسي؟ وهل أعطي ابني دواء لو خاف؟")
    assert body["reply_text"] not in (REFERRAL_AR, _MEDICAL_REFERRAL_EN, EMERGENCY_AR)
    assert body["metadata"]["off_topic"] is False
    assert seen["generate_reply"] == 1 and seen["pivot"] == 0


def test_stream_tafsir_with_no_confident_match_is_not_a_medical_referral(client, monkeypatch):
    seen = _tafsir_route(monkeypatch, NoConfidentMatch(-6.5), ["medical"])
    resp = _stream(client, _auth(client, "dev-taf-2"),
                   "ما تفسير آية الكرسي؟ وهل أعطي ابني دواء لو خاف؟")
    assert REFERRAL_AR not in resp.text and EMERGENCY_AR not in resp.text
    assert seen["pivot_prompt"] == 0
