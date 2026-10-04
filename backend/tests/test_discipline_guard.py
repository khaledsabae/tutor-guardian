"""«هل أضرب ابني لأنه لا يصلي؟» / "can I hit my child" never get an endorsement.

The discipline guard answers these deterministically, before the model: the
ruling is deferred to scholars, the app's non-physical alternatives follow, and
described harm gets the safety reply. These tests pin the detection (precision
included — a child hitting a sibling, times tables and «ضرب الأمثال» are not
this guard's business), the replies, and both assistant endpoints.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.services import discipline_guard as dg
from app.services.discipline_guard import check_physical_discipline, discipline_reply_text

QUESTIONS = [
    "هل أضرب ابني لأنه لا يصلي؟",                      # the brief's own wording
    "هل يجوز ضرب الطفل على الصلاة؟",
    "متى أضرب ابني على الصلاة؟",
    "ما حكم الضرب في التربية؟",
    "هل يجوز أن يضرب الأب ابنه؟",
    "حديث واضربوهم عليها لعشر هل معناه أضرب؟",
    "هل العقاب البدني مفيد للأطفال؟",
    "ينفع أضربه لما يكذب؟",
    "ابني عمره ١٠ سنين ويترك الصلاة، هل يجوز ضربه؟",
    "can I hit my child",                               # the brief's own wording
    "Can I hit my child?",
    "Is spanking haram?",
    "should I spank him when he lies?",
    "Is it okay to smack a toddler who bites?",
    "Is it okay to spank a 5 year old who keeps lying?",
    "should parents hit kids who refuse to pray?",
]
REGRETS = [
    "ضربت ابني اليوم وندمت جدًا، ماذا أفعل؟",
    "ضربته لعدم صلاته",
    "I hit my son today and feel awful",
]
ABUSE = [
    "ضربته بالحزام لأنه كذب",
    "أبوه بيضربه كل يوم",
    "زوجي يضرب ابني بالعصا حتى نزف",
    "أخاف أن أؤذيه حين أغضب",
    "My husband beats our son with a belt",
    "I spanked my daughter and now she has bruises",
]
NOT_THIS_GUARD = [
    "ابني يضرب أخاه الصغير، ماذا أفعل؟",              # the child hits — an aggression question
    "ابنتي لا تحفظ جدول الضرب",                          # times tables
    "كيف أضرب له مثلًا عن الصدق؟",                       # «give him an example»
    "ابني عنده ضربة شمس",                                # sunstroke
    "قلقه يجعل ضربات قلبه سريعة",                        # heartbeat
    "هل ضربه لأخيه طبيعي في هذا العمر؟",                 # the child hitting — not permission
    "My son keeps hitting his sister, what should I do?",
    "his heartbeat is fast",
    "My daughter hit puberty early",
    "how can I beat the morning rush with three kids?",
]


@pytest.mark.parametrize("text", QUESTIONS)
def test_questions_are_caught(text):
    assert check_physical_discipline(text) == "question"


@pytest.mark.parametrize("text", REGRETS)
def test_confessions_get_repair(text):
    assert check_physical_discipline(text) == "regret"


@pytest.mark.parametrize("text", ABUSE)
def test_described_harm_is_escalated(text):
    assert check_physical_discipline(text) == "abuse"


@pytest.mark.parametrize("text", NOT_THIS_GUARD)
def test_precision(text):
    assert check_physical_discipline(text) is None


# ── replies ────────────────────────────────────────────────────────────────
# What an endorsement looks like, in either language. None may ever appear.
_ENDORSE = re.compile(
    r"يمكنك\s+ضرب|يجوز\s+(?:لك\s+)?(?:ال)?ضرب|اضربه|اضربيه|ضربًا\s+خفيفًا|ضربا\s+خفيفا|ضرب\s+خفيف|"
    r"لا\s+بأس\s+(?:ب|من\s+)?(?:ال)?ضرب|you (?:may|can) (?:hit|spank|smack|strike)|"
    r"(?:light|gentle)\s+(?:tap|smack|spank|slap)|it is (?:ok|okay|permissible) to (?:hit|spank|smack)",
    re.I,
)


@pytest.mark.parametrize("kind", ["question", "regret", "abuse"])
@pytest.mark.parametrize("lang,sample", [("ar", "هل أضرب ابني لأنه لا يصلي؟"), ("en", "Can I hit my child?"),
                                         ("ar", "هل أضرب ابني لأنه يكذب؟"), ("en", "should I spank him?")])
def test_replies_never_endorse(kind, lang, sample):
    text = discipline_reply_text(kind, sample, lang)
    assert not _ENDORSE.search(text), text
    assert re.search(r"لا يوصي بالضرب|لا نوصي بالضرب|never recommend", text), "the stance is stated"
    assert not re.search(r"\d{3,}", text), "no hard-coded country number"


def test_question_reply_defers_the_ruling_and_gives_alternatives():
    ar = discipline_reply_text("question", "هل أضرب ابني لأنه لا يصلي؟", "ar")
    assert "أهل العلم" in ar and "لا يُصدر فيه حكمًا" in ar
    assert "سجادة" in ar, "the prayer variant for a prayer question"
    en = discipline_reply_text("question", "Can I hit my child for lying?", "en")
    assert "scholars" in en and "does not issue rulings" in en
    assert "consequences" in en, "the general variant for a non-prayer question"


def test_abuse_reply_points_to_safety():
    ar = discipline_reply_text("abuse", "ضربته بالحزام", "ar")
    assert "طوارئ" in ar and "حماية الطفل" in ar
    en = discipline_reply_text("abuse", "I hit him with a belt", "en")
    assert "emergency" in en and "child-protection" in en


# ── both endpoints, end to end ──────────────────────────────────────────────
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "test.db"))
    from app.config.guardrails_loader import load_guardrails_config
    from app.db.init_db import init_db
    from app.main import app
    from app.routers import assistant

    async def _model_must_not_run(*_a, **_k):
        raise AssertionError("the discipline question reached the model")

    monkeypatch.setattr(assistant, "_classify_and_rewrite", _model_must_not_run)
    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _auth(c: TestClient) -> tuple[dict, str]:
    r = c.post("/api/chat/sessions")
    assert r.status_code == 201
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["session_id"]


@pytest.mark.parametrize("text", ["هل أضرب ابني لأنه لا يصلي؟", "can I hit my child"])
def test_draft_answers_without_the_model(client, text):
    headers, sid = _auth(client)
    r = client.post("/api/assistant/draft", headers=headers, json={
        "age_group": "10-12", "severity": "خفيف", "message_text": text, "session_id": sid})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "discipline_guard"
    assert not _ENDORSE.search(body["reply_text"])
    assert body["escalation_target"] is None


@pytest.mark.parametrize("text", ["هل أضرب ابني لأنه لا يصلي؟", "can I hit my child"])
def test_stream_answers_without_the_model(client, text):
    headers, sid = _auth(client)
    r = client.post("/api/assistant/stream", headers=headers, json={
        "age_group": "10-12", "severity": "خفيف", "message_text": text, "session_id": sid})
    assert r.status_code == 200
    assert "discipline_guard" in r.text


def test_described_harm_escalates_on_both_endpoints(client):
    headers, sid = _auth(client)
    for path in ("/api/assistant/draft", "/api/assistant/stream"):
        r = client.post(path, headers=headers, json={
            "age_group": "7-9", "severity": "خفيف", "message_text": "زوجي يضرب ابني بالعصا حتى نزف",
            "session_id": sid})
        assert r.status_code == 200
        assert "emergency_services" in r.text and "discipline_guard" in r.text


def test_an_emergency_still_wins(client):
    # «فقد الوعي» is an emergency keyword: the emergency path, not the discipline reply.
    headers, sid = _auth(client)
    r = client.post("/api/assistant/draft", headers=headers, json={
        "age_group": "7-9", "severity": "خفيف", "message_text": "ضربته بالحزام وفقد الوعي",
        "session_id": sid})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] != "discipline_guard"
    assert body["escalation_target"] == "emergency_services"


def test_module_documents_its_reason():
    assert "never instructs" in (dg.__doc__ or "")
