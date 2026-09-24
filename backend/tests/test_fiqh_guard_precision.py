"""FIQH guard precision + pipeline order (2026-09 audit).

Two defects, both reproduced before the fix:

1. Order. The fiqh guard ran before the emergency check, so a parent writing
   «ابني بيقول عايز ينتحر بعد الطلاق» — suicidal talk, plus the word for
   divorce — got "please ask a religious authority" instead of the emergency
   escalation. Emergency must win.

2. Precision. The regexes matched substrings of *different words*: a newborn
   (حديث الولادة) with low weight, backbiting (الغيبة ⊃ الغيب), eyesight
   (الرؤية), parental controls (التحكم ⊃ حكم) … all received the fiqh reply,
   while «ما حكم الموسيقى» — the plainest fatwa question — passed. The blocked
   categories are unchanged; only those collisions are fixed.
"""
import pytest
from fastapi.testclient import TestClient

from app.services import fiqh_guard


@pytest.fixture(autouse=True)
def _no_block_log(monkeypatch):
    # The block log writes to ops/sessions.db; keep tests off the real file.
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)


# Questions the product exists to answer — none of these may be blocked.
NOT_FIQH = [
    "ابني حديث الولادة ووزنه ضعيف، هل هذا طبيعي؟",          # newborn, medical
    "طفلي حديثي الولادة لا ينام",                            # newborn (plural form)
    "كيف أعلم ابني ترك الغيبة والنميمة؟",                    # backbiting
    "ابني عنده ضعف في الرؤية ويقرب من الشاشة",              # eyesight
    "كيف أمنع الصور غير اللائقة باستخدام التحكم الأبوي؟",   # parental controls
    "ابني يحب الرسم لكنه لا يتحكم في غضبه",                  # self-control
    "ما موضوع الحديث المناسب مع ابني عن البلوغ؟",           # topic of a talk
    "ابني ضعيف في القراءة، هل أشتري له رواية؟",              # weak reader, novel
    "تحديث التطبيق صحيح؟",                                   # app update
    "ابني يرسم بحكمة",                                        # wisdom
    # FIQH_GUARD.md v3 §أ — managing the discussion is allowed:
    "ابني بيسألني عن الموسيقي — أتعامل مع الموضوع إزاي بحيث ماحرمنوش من حاجة نعملها غلط؟",
]

# Explicit ruling questions from FIQH_GUARD.md — every one must still block.
FIQH = [
    "هل الموسيقي حرام؟",
    "ما حكم الموسيقى؟",                       # ruling word first — was missed
    "ابني بيسألني: هل الموسيقي حرام ولا حلال؟",  # wrapped prompt (v3 §أ)
    "حكم الأغاني في الإسلام",
    "هل الرسم حرام؟",
    "ما حكم التصوير؟",
    "هل هذا الحديث صحيح؟",
    "هل حديث من صام رمضان صحيح؟",
    "الفرق بين الحديث القوي والضعيف",
    "هذا حديث موضوع؟",
    "صحيح أن هذا حديث؟",
    "ملك اليمين ليه الإسلام لم يمنعه",
    "ما هو علم الغيب",
    "هل رؤية الله ممكنة",
    "أرواح الأموات هل تزورنا",               # hamza pattern — was dead code
    "هل يجوز الطلاق وأنا حامل",
    "ما حكم الصلاة في المذهب الحنفي بدون وضوء",
]


@pytest.mark.parametrize("question", NOT_FIQH)
def test_parenting_and_medical_questions_are_not_blocked(question):
    blocked, rule = fiqh_guard.check_fiqh_guard(question)
    assert not blocked, f"false positive on rule {rule}: {question}"


@pytest.mark.parametrize("question", FIQH)
def test_explicit_ruling_questions_still_block(question):
    blocked, _ = fiqh_guard.check_fiqh_guard(question)
    assert blocked, question


# ── Pipeline order: emergency beats the fiqh guard ────────────────────────

_SUICIDE_AFTER_DIVORCE = "ابني بيقول عايز ينتحر بعد الطلاق"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "test.db"))
    from app.config.guardrails_loader import load_guardrails_config
    from app.db.init_db import init_db
    from app.main import app

    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _auth(c: TestClient) -> tuple[dict, str]:
    r = c.post("/api/chat/sessions")
    assert r.status_code == 201
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["session_id"]


def test_precondition_both_checks_match_this_message():
    # Guards the test below: it only proves the ORDER if both would fire.
    from app.services.intent_guard import check_emergency_keywords

    assert check_emergency_keywords(_SUICIDE_AFTER_DIVORCE)
    assert fiqh_guard.check_fiqh_guard(_SUICIDE_AFTER_DIVORCE)[0]


def test_draft_escalates_emergency_instead_of_fiqh_deflection(client):
    headers, sid = _auth(client)
    r = client.post("/api/assistant/draft", headers=headers, json={
        "age_group": "13-15", "severity": "خفيف",
        "message_text": _SUICIDE_AFTER_DIVORCE, "session_id": sid,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] != "fiqh_guard"
    assert body["reply_text"] != fiqh_guard.SAFE_REPLY
    assert body["escalation_target"] == "emergency_services"
    assert body["needs_human_review"] is True


def test_stream_escalates_emergency_instead_of_fiqh_deflection(client):
    headers, sid = _auth(client)
    r = client.post("/api/assistant/stream", headers=headers, json={
        "age_group": "13-15", "severity": "خفيف",
        "message_text": _SUICIDE_AFTER_DIVORCE, "session_id": sid,
    })
    assert r.status_code == 200
    assert "emergency_services" in r.text
    assert "fiqh_guard" not in r.text
