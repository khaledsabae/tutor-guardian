"""The server-side gaps the mobile review of child memory (PR #36) found.

1. **The memory switch OFF must hold for follow-ups too.** «لا يتعلّم المربّي
   شيئًا جديدًا» — but `followups/due` still listed items and an answer still
   wrote an `outcome` fact. Off now pauses the loop (due → [], an answer keeps
   nothing), a parent cannot add a fact while off, and corrections still work.
2. **A memory fact carries no family name — any of them.** «أحمد يغار من نور»
   kept «نور» (a name that is also a word needs evidence of a person in a
   question). Facts are matched strictly. Questions keep the evidence rule,
   plus: a child recognised once in a question is the child at every mention.
3. **Sibling letters survive a deletion.** «الطفل ب» is a position in profile
   order; deleting a child moved it to the next sibling («عمر يغار من عمر»).
   The deletion now rewrites the siblings' memory: new letters, and «طفل آخر»
   for the deleted child.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.services import ai_gateway
from app.services import child_memory as cm
from app.services.privacy import (
    Family, _name_variants, family_for_device, family_mentions, redact_family,
    reletter_siblings, scrub_child_name,
)
from tests.device_proof_support import prove


# ── Helpers ───────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _session(client: TestClient, device: str, proven: bool = True) -> dict:
    tok = client.post("/api/chat/sessions", json={"device_id": device}).json()
    h = {"Authorization": f"Bearer {tok['token']}"}
    if proven:
        prove(client, h, push_token=f"fcm-{device}")
    return h


def _child(client, h, name: str, age: str = "4-6") -> int:
    r = client.post("/api/children", json={"name": name, "age_group": age}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _memory_build(monkeypatch, device: str) -> None:
    """A build with the memory screen (the push token is kept: the proof is
    bound to it)."""
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    conn = get_conn()
    conn.execute(
        "INSERT INTO push_tokens (device_id, token, build_number) VALUES (?, ?, 120) "
        "ON CONFLICT(device_id) DO UPDATE SET build_number = excluded.build_number",
        (device, f"fcm-{device}"))
    conn.commit()
    conn.close()


def _switch(client, h, on: bool) -> None:
    r = client.put("/api/children/memory/settings", headers=h, json={"enabled": on})
    assert r.status_code == 200 and r.json()["enabled"] is on, r.text


def _due_followup(device: str, cid: int, strategy: str = "روتين نوم ثابت مع قصة",
                  topic: str = "sleep") -> int:
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO followups (device_id, child_id, strategy, topic, lang, due_at) "
        "VALUES (?, ?, ?, ?, 'ar', ?)", (device, cid, strategy, topic, past))
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def _insert_fact(device: str, cid: int, text: str, status: str = "active",
                 category: str = "challenge") -> int:
    """A stored fact, written straight to the table (a legacy row, or one the
    memory routes are not the subject of)."""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO child_facts (device_id, child_id, category, fact, source, confidence, "
        "status, lang) VALUES (?, ?, ?, ?, 'chat', 0.9, ?, 'ar')",
        (device, cid, category, text, status))
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def _rows(sql: str, *params) -> list:
    conn = get_conn()
    try:
        return [tuple(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _fact_text(fact_id: int) -> str:
    return _rows("SELECT fact FROM child_facts WHERE id = ?", fact_id)[0][0]


# ── 1. The switch OFF holds for follow-ups and manual adds ───────────────


def test_switch_off_pauses_the_followup_loop(client):
    h = _session(client, "dev-off-loop")
    cid = _child(client, h, "يوسف")
    fid = _due_followup("dev-off-loop", cid)

    due = client.get("/api/children/followups/due", headers=h).json()
    assert [f["id"] for f in due["followups"]] == [fid] and due["memory_enabled"] is True

    _switch(client, h, False)
    assert client.get("/api/children/followups/due", headers=h).json() == {
        "followups": [], "memory_enabled": False}
    one = client.get(f"/api/children/followups/{fid}", headers=h).json()
    assert one["memory_enabled"] is False and one["followup"]["status"] == "pending"

    r = client.post(f"/api/children/followups/{fid}/answer", headers=h,
                    json={"outcome": "didnt_work", "note": "يوسف بكى كثيرًا"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["remembered"] is False and body["fact"] is None
    assert body["note_dropped"] is False
    assert body["followup"]["status"] == "pending" and body["followup"]["outcome"] is None
    # By effect: nothing learned, nothing recorded — not the outcome, not the note.
    assert _rows("SELECT COUNT(*) FROM child_facts WHERE device_id = 'dev-off-loop'") == [(0,)]
    assert _rows("SELECT status, outcome, note, answered_at FROM followups WHERE id = ?",
                 fid) == [("pending", None, None, None)]

    # Switched back on, the loop resumes where it was.
    _switch(client, h, True)
    due = client.get("/api/children/followups/due", headers=h).json()
    assert [f["id"] for f in due["followups"]] == [fid] and due["memory_enabled"] is True
    r = client.post(f"/api/children/followups/{fid}/answer", headers=h,
                    json={"outcome": "didnt_work"})
    assert r.json()["remembered"] is True and r.json()["fact"]["category"] == "outcome"


def test_the_switch_is_rechecked_inside_the_answer_transaction(client, monkeypatch):
    """Off between the first look and the write: still nothing written."""
    h = _session(client, "dev-off-race")
    cid = _child(client, h, "سالم")
    fid = _due_followup("dev-off-race", cid)
    _switch(client, h, False)
    monkeypatch.setattr(cm, "memory_enabled", lambda device_id: True)
    result = cm.answer_followup("dev-off-race", fid, "worked")
    assert result["remembered"] is False and result["fact"] is None
    assert _rows("SELECT COUNT(*) FROM child_facts WHERE device_id = 'dev-off-race'") == [(0,)]


def test_an_answer_cannot_write_after_an_erase(client, monkeypatch):
    """The follow-up read before the write is stale once the parent erased:
    no orphan outcome fact may outlive the erase."""
    h = _session(client, "dev-answer-erase")
    cid = _child(client, h, "سالم")
    fid = _due_followup("dev-answer-erase", cid)
    stale = cm.get_followup("dev-answer-erase", fid)
    cm.delete_child_memory("dev-answer-erase", cid)
    monkeypatch.setattr(cm, "get_followup", lambda device_id, followup_id: stale)
    assert cm.answer_followup("dev-answer-erase", fid, "worked") is None
    assert _rows("SELECT COUNT(*) FROM child_facts WHERE device_id = 'dev-answer-erase'") == [(0,)]


def test_dismissing_still_works_while_off(client):
    h = _session(client, "dev-off-dismiss")
    cid = _child(client, h, "سالم")
    fid = _due_followup("dev-off-dismiss", cid)
    _switch(client, h, False)
    r = client.post(f"/api/children/followups/{fid}/dismiss", headers=h)
    assert r.status_code == 200 and r.json()["followup"]["status"] == "dismissed"


def test_a_parent_cannot_add_while_off_but_can_still_correct(client):
    h = _session(client, "dev-off-add")
    cid = _child(client, h, "سالم")
    kept = client.post(f"/api/children/{cid}/memory", headers=h,
                       json={"category": "goal", "fact": "طفلي يحفظ سورة الملك"}).json()
    pending = _insert_fact("dev-off-add", cid, "طفلي يحب الرسم", status="pending")
    _switch(client, h, False)

    r = client.post(f"/api/children/{cid}/memory", headers=h,
                    json={"category": "other", "fact": "طفلي يحب الرسم كثيرًا"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "memory_off"
    assert _rows("SELECT COUNT(*) FROM child_facts WHERE device_id = 'dev-off-add'") == [(2,)]

    # The parent's control over what is kept never pauses.
    assert client.patch(f"/api/children/{cid}/memory/{kept['id']}", headers=h,
                        json={"fact": "طفلي يحفظ سورة الملك والنبأ"}).status_code == 200
    assert client.patch(f"/api/children/{cid}/memory/{pending}", headers=h,
                        json={"status": "active"}).json()["status"] == "active"
    assert client.patch(f"/api/children/{cid}/memory/{pending}", headers=h,
                        json={"status": "rejected"}).json()["status"] == "rejected"
    assert client.delete(f"/api/children/{cid}/memory/{kept['id']}",
                         headers=h).status_code == 200

    _switch(client, h, True)
    assert client.post(f"/api/children/{cid}/memory", headers=h,
                       json={"category": "other", "fact": "طفلي يحب الرسم كثيرًا"}
                       ).status_code == 201


def test_the_weekly_plan_leaves_memory_out_while_off(client, monkeypatch):
    h = _session(client, "dev-off-plan")
    cid = _child(client, h, "سالم")
    _memory_build(monkeypatch, "dev-off-plan")
    client.post(f"/api/children/{cid}/memory", headers=h,
                json={"category": "challenge", "fact": "طفلي يخاف من النوم وحده ويستيقظ ليلًا"})
    assert client.get(f"/api/children/{cid}/weekly-plan", headers=h
                      ).json()["focus"]["reason"] == "memory"
    _switch(client, h, False)
    assert client.get(f"/api/children/{cid}/weekly-plan", headers=h
                      ).json()["focus"]["reason"] != "memory"


def test_nothing_is_learned_from_a_question_while_off(client, monkeypatch):
    """Extraction (the other write path) is refused before any model call."""
    h = _session(client, "dev-off-extract")
    cid = _child(client, h, "سالم")
    _memory_build(monkeypatch, "dev-off-extract")
    _switch(client, h, False)
    calls = []
    monkeypatch.setattr(ai_gateway, "aux_cloud_provider", lambda **kw: calls.append(kw))
    assert cm.extract_and_store("dev-off-extract", cid, question="ابني يرفض النوم وحده كل ليلة",
                                answer="…", proven=True) is None
    assert calls == []


# ── 2. A fact carries no family name — any of them ──────────────────────

# The reviewer's probes (/tmp/review-pr36/pyprobe): (family, the fact's child, text).
REVIEW_PROBES = [
    (((1, "نور"),), 1, "تحب نور الرسم كثيرًا"),
    (((1, "سارة"), (2, "نور")), 1, "سارة تغار من نور عند اللعب"),
    (((1, "سارة"), (2, "أمل")), 1, "سارة تغار من أمل عند اللعب"),
    (((12, "أحمد"), (30, "نور")), 12, "أحمد يغار من نور عند اللعب كثيرًا"),
    (((12, "أحمد"), (30, "نور")), 12, "أحمد يتشاجر مع نور كل يوم"),
    (((12, "أحمد"), (30, "نور")), 12, "أحمد يضرب نور حين يغضب"),
    (((12, "أحمد"), (30, "نور")), 12, "أحمد يحب أخته نور كثيرًا"),
    (((12, "أحمد"), (30, "أمل")), 12, "أحمد يغار من أمل عند اللعب"),
    (((12, "أحمد"), (30, "أمل")), 12, "أحمد يضرب أمل حين يغضب"),
    (((1, "نور"),), 1, "جرّبنا مع نور روتين نوم ثابت"),
    (((1, "أمل"),), 1, "جُرِّب مع أمل: روتين نوم ثابت — ولم ينجح."),
    (((1, "هدى"), (2, "دعاء")), 1, "هدى تحب القصص قبل النوم مع دعاء"),
    (((1, "Nour"),), 1, "Nour is afraid of the dark"),
    (((1, "Hope"),), 1, "Hope gets angry when tired"),
]


@pytest.mark.parametrize("members,subject,text", REVIEW_PROBES)
def test_no_family_name_survives_in_a_fact(members, subject, text):
    family = Family(members)
    out = cm.clean_fact_text(text, family, subject)
    assert out and family_mentions(out, family, strict=True) == [], out
    assert _oracle_left(out, family.names) == [], out      # independent of the matcher


def test_a_sibling_keeps_its_letter_and_the_subject_is_my_child():
    family = Family(((12, "أحمد"), (30, "نور")))
    assert cm.clean_fact_text("أحمد يغار من نور عند اللعب كثيرًا", family, 12) == \
        "طفلي يغار من الطفل ب عند اللعب كثيرًا"
    assert cm.clean_fact_text("تحب نور الرسم كثيرًا", family, 30) == "تحب طفلي الرسم كثيرًا"


@pytest.mark.parametrize("name,text,expected", [
    ("نور", "اشتريت لنور لعبة ولنور أخرى", "اشتريت لطفلي لعبة ولطفلي أخرى"),
    ("أمل", "وبأمل نبدأ ولأمل نختم", "وبطفلي نبدأ ولطفلي نختم"),
    ("أحمد", "فبأحمد بدأنا وكأحمد ختمنا", "فبطفلي بدأنا وكطفلي ختمنا"),
    ("محمد", "رأيت محمدًا يبكي ثم محمداً يضحك", "رأيت طفلي يبكي ثم طفلي يضحك"),
    ("علي", "كافأنا عليًّا", "كافأنا طفلي"),
])
def test_strict_takes_attached_particles_and_the_accusative(name, text, expected):
    assert cm.clean_fact_text(text, Family(((1, name),)), 1) == expected


@pytest.mark.parametrize("name,text", [
    ("نور", "طفلي يحفظ سورة النور"),               # the article: a word, not a name
    ("محمد", "طفلي يحب سيرة النبي محمد ﷺ"),        # a religious reference
    ("علي", "طفلي يعتمد على نفسه"),                 # «على» is not «علي»
    ("منى", "طفلي يخاف مني"),                       # «مني» is not «منى»
])
def test_strict_still_leaves_words_that_are_not_the_name(name, text):
    assert cm.clean_fact_text(text, Family(((1, name),)), 1) == text


def test_a_word_name_is_over_redacted_in_a_fact_and_that_is_accepted():
    """The documented price: the app swaps the name back on the device, so the
    parent reads «نور القرآن» again; the model reads «طفلي القرآن»."""
    assert cm.clean_fact_text("طفلي يحب سماع نور القرآن", Family(((1, "نور"),)), 1) == \
        "طفلي يحب سماع طفلي القرآن"


def test_the_api_stores_no_family_name(client):
    h = _session(client, "dev-strict-api")
    ahmad = _child(client, h, "أحمد")
    nour = _child(client, h, "نور")
    r = client.post(f"/api/children/{ahmad}/memory", headers=h,
                    json={"category": "challenge", "fact": "أحمد يضرب نور حين يغضب"})
    assert r.status_code == 201 and r.json()["fact"] == "طفلي يضرب الطفل ب حين يغضب"
    added = client.post(f"/api/children/{nour}/memory", headers=h,
                        json={"category": "other", "fact": "طفلي يحب الرسم"}).json()
    r = client.patch(f"/api/children/{nour}/memory/{added['id']}", headers=h,
                     json={"fact": "تحب نور الرسم مع أحمد"})
    assert r.json()["fact"] == "تحب طفلي الرسم مع الطفل أ"


def test_a_stored_name_is_redacted_before_it_reaches_a_prompt(client):
    """A fact written before the strict rule (or straight to the table) is
    redacted strictly again on its way into the prompt."""
    h = _session(client, "dev-strict-inject")
    ahmad = _child(client, h, "أحمد")
    _child(client, h, "نور")
    _insert_fact("dev-strict-inject", ahmad, "طفلي يغار من نور عند اللعب")
    block, used = cm.facts_block("dev-strict-inject", ahmad, "الغيرة")
    assert used == 1 and "الطفل ب" in block and "نور" not in block


def test_strategies_and_outcome_notes_are_strict_too(client, monkeypatch):
    h = _session(client, "dev-strict-fu")
    ahmad = _child(client, h, "أحمد")
    _child(client, h, "نور")
    _memory_build(monkeypatch, "dev-strict-fu")
    family = family_for_device("dev-strict-fu")
    stats = cm.store_extraction(
        "dev-strict-fu", ahmad, [],
        {"strategy": "إبعاد أحمد عن نور وقت الغضب", "topic": "anger", "days": 3},
        lang="ar", family=family)
    fid = stats["followup"]
    assert _rows("SELECT strategy FROM followups WHERE id = ?", fid) == [
        ("إبعاد طفلي عن الطفل ب وقت الغضب",)]
    conn = get_conn()
    conn.execute("UPDATE followups SET due_at = '2026-01-01 00:00:00' WHERE id = ?", (fid,))
    conn.commit()
    conn.close()
    r = client.post(f"/api/children/followups/{fid}/answer", headers=h,
                    json={"outcome": "partly", "note": "نور بكت كثيرًا ثم هدأ أحمد"})
    fact = r.json()["fact"]["fact"]
    assert "نور" not in fact and "أحمد" not in fact and "الطفل ب بكت" in fact
    # The note itself is kept as the parent typed it — shown back, never sent.
    assert r.json()["followup"]["note"] == "نور بكت كثيرًا ثم هدأ أحمد"


# Questions keep the evidence rule — measured decision (privacy.py module doc).


def test_a_child_recognised_once_in_a_question_is_the_child_everywhere_in_it():
    family = Family(((1, "نور"),))
    assert redact_family("بنتي نور بتخاف من الظلام ونور كمان بترفض تنام", family, 1) == \
        "بنتي طفلي بتخاف من الظلام وطفلي كمان بترفض تنام"
    # …but a counter-sign still wins: the second «نور» is the Qur'an's light.
    assert redact_family("بنتي نور بتحب تسمع نور القرآن", family, 1) == \
        "بنتي طفلي بتحب تسمع نور القرآن"
    # A function word does not extend: «علي طول» stays a preposition.
    assert redact_family("علي بيعيط علي طول", Family(((1, "علي"),)), 1) == \
        "طفلي بيعيط علي طول"


def test_a_question_keeps_a_word_name_used_as_a_word():
    """The trade-off the strict rule would lose in a question."""
    family = Family(((1, "نور"),))
    q = "كيف أعلّم ابني حب نور القرآن؟"
    assert redact_family(q, family, 1) == q
    assert cm.clean_fact_text(q, family, 1) == "كيف أعلّم ابني حب طفلي القرآن؟"


class _Recorder:
    prompts: list[str] = []
    name, model = "fake", "fake-model"

    def __init__(self, *a, **k):
        pass

    def stream(self, prompt, *, options):
        _Recorder.prompts.append(prompt)
        yield {"response": "جرّب روتينًا ثابتًا قبل النوم مع قصة قصيرة.", "done": False}
        yield {"response": "", "done": True, "prompt_eval_count": 1, "eval_count": 1}


def test_the_second_mention_never_reaches_the_model(client, monkeypatch):
    from app.routers import assistant
    from app.services import answer_cache

    async def no_ayah(_t):
        return None

    _Recorder.prompts = []
    seen: list[str] = []
    monkeypatch.setattr(assistant, "classify_domains", lambda t: seen.append(t) or ["tarbiyah"])
    monkeypatch.setattr(assistant, "rewrite_query", lambda t, **k: seen.append(t) or "")
    monkeypatch.setattr(assistant, "retrieve_hybrid", lambda **kw: [{
        "unit_id": "u1", "document": "passage: الروتين الثابت يساعد على النوم.",
        "metadata": {"domain": "tarbiyah", "reference_info": "دليل"},
        "rerank_score": 2.0, "source_domain": "tarbiyah"}])
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", no_ayah)
    monkeypatch.setattr(answer_cache, "lookup", lambda *a, **k: None)
    monkeypatch.setattr(answer_cache, "store", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "OllamaProvider", _Recorder)
    ai_gateway._gateway = None
    try:
        h = _session(client, "dev-second-mention", proven=False)
        _child(client, h, "نور")
        r = client.post("/api/assistant/stream", headers=h, json={
            "age_group": "4-6", "severity": "خفيف",
            "message_text": "بنتي نور بتخاف من الظلام ونور كمان بترفض تنام لوحدها"})
        assert r.status_code == 200
        json.loads(r.text.split("event: done\ndata: ", 1)[1].split("\n", 1)[0])
    finally:
        ai_gateway._gateway = None
    redacted = "بنتي طفلي بتخاف من الظلام وطفلي كمان بترفض تنام لوحدها"
    assert _Recorder.prompts and redacted in _Recorder.prompts[-1]
    for payload in _Recorder.prompts + seen:
        assert "ونور كمان" not in payload and "بنتي نور" not in payload


# ── 3. Sibling letters survive a child's deletion ─────────────────────────


def _render(text: str, family: Family, child_name: str) -> str:
    """The app's on-device swap (mobile placeholder_names.dart): «طفلي» → the
    fact's child, «الطفل X» → the sibling at that position."""
    from app.services.privacy import sibling_placeholder
    for i, (_, name) in enumerate(family.members):
        ph = sibling_placeholder(i)
        text = text.replace("ل" + ph, "ل" + name).replace(ph, name)
    return text.replace("طفلي", child_name)


def test_deleting_a_child_reletters_its_siblings_memory(client, monkeypatch):
    h = _session(client, "dev-reletter")
    sara = _child(client, h, "سارة")          # أ
    ahmad = _child(client, h, "أحمد")         # ب — deleted below
    omar = _child(client, h, "عمر")           # ج → ب
    _memory_build(monkeypatch, "dev-reletter")
    jealous = client.post(f"/api/children/{omar}/memory", headers=h,
                          json={"category": "challenge", "fact": "عمر يغار من أحمد"}).json()
    plays = client.post(f"/api/children/{sara}/memory", headers=h,
                        json={"category": "other", "fact": "سارة تلعب مع عمر وتحب أحمد"}).json()
    assert jealous["fact"] == "طفلي يغار من الطفل ب"
    assert plays["fact"] == "طفلي تلعب مع الطفل ج وتحب الطفل ب"
    legacy = _insert_fact("dev-reletter", sara, "طفلي تقلّد ابن عمها أحمد")  # pre-profile wording
    fu = _due_followup("dev-reletter", sara, "لعب مشترك بين طفلي والطفل ج", "siblings")
    in_flight = cm._generation("dev-reletter")

    assert client.delete(f"/api/children/{ahmad}", headers=h).status_code == 200

    assert _fact_text(jealous["id"]) == "طفلي يغار من طفل آخر"
    assert _fact_text(plays["id"]) == "طفلي تلعب مع الطفل ب وتحب طفل آخر"
    assert _fact_text(legacy) == "طفلي تقلّد ابن عمها طفل آخر"
    assert _rows("SELECT strategy FROM followups WHERE id = ?", fu) == [
        ("لعب مشترك بين طفلي والطفل ب",)]
    # Rendered on the device with the family as it is now: the right names,
    # and never «عمر يغار من عمر».
    family = family_for_device("dev-reletter")
    assert _render(_fact_text(jealous["id"]), family, "عمر") == "عمر يغار من طفل آخر"
    assert _render(_fact_text(plays["id"]), family, "سارة") == "سارة تلعب مع عمر وتحب طفل آخر"
    # The question's redaction and the stored fact agree on the letter.
    assert redact_family("سارة تلعب مع عمر", family, sara) == "طفلي تلعب مع الطفل ب"
    # An extraction that began before the deletion (old letters) is refused.
    stats = cm.store_extraction(
        "dev-reletter", omar,
        [{"category": "challenge", "fact": "طفلي يضرب الطفل ب", "confidence": 0.9,
          "replaces": None}], None, lang="ar", family=family, generation=in_flight)
    assert stats["refused"] is True


def test_a_profile_only_delete_reletters_too(client):
    """A device that never proved deletes only the profile (PR #26 final
    review) — and the siblings' letters still follow."""
    h = _session(client, "dev-reletter-bare", proven=False)
    first = _child(client, h, "سارة")
    gone = _child(client, h, "أحمد")
    third = _child(client, h, "عمر")
    f1 = _insert_fact("dev-reletter-bare", third, "طفلي يغار من الطفل ب")
    f2 = _insert_fact("dev-reletter-bare", first, "طفلي تلعب مع الطفل ج")
    assert client.delete(f"/api/children/{gone}", headers=h).status_code == 200
    assert _fact_text(f1) == "طفلي يغار من طفل آخر"
    assert _fact_text(f2) == "طفلي تلعب مع الطفل ب"


def test_the_last_sibling_left_has_no_letters(client):
    h = _session(client, "dev-reletter-two")
    keep = _child(client, h, "سارة")
    gone = _child(client, h, "أحمد")
    fid = _insert_fact("dev-reletter-two", keep, "طفلي تغار من الطفل ب")
    assert client.delete(f"/api/children/{gone}", headers=h).status_code == 200
    assert _fact_text(fid) == "طفلي تغار من طفل آخر"


def test_reletter_siblings_rewrites_every_attached_form():
    before = Family(((1, "سارة"), (2, "أحمد"), (3, "عمر"), (4, "ليلى")))
    after = Family(((1, "سارة"), (3, "عمر"), (4, "ليلى")))
    assert reletter_siblings("وللطفل ب وبالطفل ج وكالطفل د فالطفل أ", before, after) == \
        "ولطفل آخر وبالطفل ب وكالطفل ج فالطفل أ"
    assert reletter_siblings("الطفلة ب تحب الطفلة د", before, after) == \
        "طفلة أخرى تحب الطفلة ج"
    assert reletter_siblings("My child hits الطفل ب", before, after) == \
        "My child hits another child"
    # A letter this family never had is left as it is.
    assert reletter_siblings("الطفل ك", before, after) == "الطفل ك"
    # One named child left: no letters any more. In a text of a child whose
    # name is too short to count (owner 7), the one left is «طفل آخر», never
    # «طفلي» — that would be the text's own child.
    two, one = Family(((1, "سارة"), (2, "أحمد"))), Family(((1, "سارة"),))
    assert reletter_siblings("طفلي يحب الطفل أ وللطفل ب", two, one, owner=7) == \
        "طفلي يحب طفل آخر ولطفل آخر"
    # Beyond the 14 letters, positions are numbers.
    many = Family(tuple((i, f"اسم{i}") for i in range(1, 17)))
    fewer = Family(tuple(m for m in many.members if m[0] != 2))
    assert reletter_siblings("الطفل 16 والطفل 15", many, fewer) == "الطفل 15 والطفل ن"


def test_scrubbing_a_deleted_childs_name_is_strict():
    assert scrub_child_name("طفلي تغار من نور ولنور لعبة", "نور") == \
        "طفلي تغار من طفل آخر ولطفل آخر لعبة"
    assert scrub_child_name("My child copies Adam", "Adam") == "My child copies another child"


# ── PR #39 review ─────────────────────────────────────────────────────────
#
# An independent oracle — a test that asks the matcher whether the matcher
# missed something cannot fail. This one folds spelling crudely and looks for
# every name, and every name token of 3+ letters, as a word: behind any
# particle, with or without the accusative alif or a final hamza. It
# over-reports by design, so cases where a name may rightly stay (a religious
# reference, «فعلا» for a child «علا») are not given to it.

_ORACLE_MARKS = re.compile("[ً-ْٰـ‌-‏؜]")
_ORACLE_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه",
                              "ى": "ي", "ئ": "ي", "ؤ": "و"})
_ORACLE_PARTICLES = ("وب", "ول", "وك", "فب", "فل", "فك", "و", "ف", "ب", "ل", "ك")


def _oracle_fold(text: str) -> str:
    folded = _ORACLE_MARKS.sub("", text or "").translate(_ORACLE_FOLD).lower()
    return re.sub(r"عبد\s+", "عبد", folded)


def _oracle_left(text: str, names) -> list[str]:
    """The names among `names` still readable in `text`."""
    folded = _oracle_fold(text)
    words = set(re.findall(r"[a-zء-ي]+", folded))
    stems = set(words)
    for w in words:
        stems |= {w[len(p):] for p in _ORACLE_PARTICLES if w.startswith(p)}
    stems |= {w[:-1] for w in stems if w.endswith("ا")}             # the accusative
    left = []
    for name in names:
        n = _oracle_fold(name.strip())
        if n in ("طفلي", "my child"):
            continue                                                 # a default: no name
        forms = {n} | {t for t in n.split() if len(t) >= 3}
        forms |= {f[:-1] for f in forms if f.endswith("اء")}         # «دعا» for «دعاء»
        forms |= {"ل" + f[2:] for f in forms if f.startswith("ال")}  # «للحسن»
        if forms & stems or (" " in n and n in folded):
            left.append(name)
    return left


def test_the_oracle_sees_what_it_must():
    assert _oracle_left("طفلي تغار من لـأحمدًا", ["أحمد"]) == ["أحمد"]
    assert _oracle_left("طفلي تغار من اسما", ["أسماء"]) == ["أسماء"]
    assert _oracle_left("طفلي تغار من الطفل أ", ["أحمد", "طفلي"]) == []


def _fake_llm(monkeypatch, fact_text: str) -> None:
    payload = json.dumps({"sensitive": False, "facts": [{
        "category": "challenge", "fact": fact_text, "confidence": 0.9,
        "replaces": None, "sensitive": False}], "followup": None}, ensure_ascii=False)
    monkeypatch.setattr(ai_gateway, "aux_cloud_provider", lambda **kw: object())
    monkeypatch.setattr(ai_gateway, "aux_generate", lambda *a, **k: payload)
    monkeypatch.setattr(cm, "extraction_budget_ok", lambda: True)


# 1 + 2. A default name — «طفلي», "My child" — is no name.


@pytest.mark.parametrize("proven", [True, False])
def test_deleting_a_child_named_tifli_keeps_its_siblings_subject(client, proven):
    """R1: «طفلي» is the onboarding default (3,323 of 4,375 children on
    production). Deleting such a child must not scrub the siblings' own
    «طفلي» into «طفل آخر» — by either delete path."""
    dev = f"dev-tifli-{proven}"
    h = _session(client, dev, proven=proven)
    first = _child(client, h, "طفلي")                      # أ
    ahmad = _child(client, h, "أحمد")
    own = _insert_fact(dev, ahmad, "طفلي يحب الرسم")
    sibling = _insert_fact(dev, ahmad, "طفلي يغار من الطفل أ")
    assert client.delete(f"/api/children/{first}", headers=h).status_code == 200
    assert _fact_text(own) == "طفلي يحب الرسم"
    assert _fact_text(sibling) == "طفلي يغار من طفل آخر"


def test_a_default_name_is_never_read_as_a_sibling():
    """R2: the subject's «طفلي» is not the sibling who carries «طفلي» as a
    name. Such a child keeps its place — its letter — in the family."""
    fam = Family(((1, "طفلي"), (2, "أحمد")))
    assert cm.clean_fact_text("طفلي يحب الرسم", fam, 2) == "طفلي يحب الرسم"
    assert redact_family("طفلي بيحب الرسم وأحمد بيغير", fam, 1) == \
        "طفلي بيحب الرسم والطفل ب بيغير"
    three = Family(((1, "طفلي"), (2, "أحمد"), (3, "سارة")))
    assert cm.clean_fact_text("سارة تغار من أحمد", three, 3) == "طفلي تغار من الطفل ب"
    # A real name with a default word in it keeps its real part.
    variants = {v for v, _, _ in _name_variants("طفلي أحمد")}
    assert "احمد" in variants and "طفلي" not in variants


def test_my_child_is_no_name_in_english_either():
    one = Family(((1, "My child"),))
    q = "My child refuses to pray and my husband says I should be strict with the child"
    assert redact_family(q, one, 1) == q
    fact = "My child refuses to pray when my husband is away"
    assert cm.clean_fact_text(fact, one, 1) == fact
    two = Family(((1, "My child"), (2, "Adam")))
    assert cm.clean_fact_text("My child is afraid of the dark", two, 2) == \
        "My child is afraid of the dark"
    assert scrub_child_name("My child is afraid of the dark", "My child") == \
        "My child is afraid of the dark"
    # A Latin name's word-tokens are not names either.
    assert {v for v, _, _ in _name_variants("Baby Adam")} == {"baby adam", "adam"}


def test_the_api_keeps_my_child_beside_a_sibling_named_my_child(client):
    """R2b, through the API: stored as typed, and still so after the
    default-named sibling is deleted."""
    dev = "dev-default-api"
    h = _session(client, dev)
    default = _child(client, h, "طفلي")
    ahmad = _child(client, h, "أحمد")
    stored = client.post(f"/api/children/{ahmad}/memory", headers=h,
                         json={"category": "other", "fact": "طفلي يحب الرسم"}).json()
    assert stored["fact"] == "طفلي يحب الرسم"
    assert client.delete(f"/api/children/{default}", headers=h).status_code == 200
    assert _fact_text(stored["id"]) == "طفلي يحب الرسم"


# 3. A child recognised in a question does not take over every word use.


@pytest.mark.parametrize("name,question,kept", [
    ("دعاء", "بنتي دعاء عندها ٥ سنين، أعلمها دعاء قبل النوم إزاي؟", "أعلمها دعاء قبل"),
    ("آية", "بنتي آية حافظة جزء عم، عايزة أحفظها آية كل يوم", "أحفظها آية كل"),
    ("جنة", "بنتي جنة بتسأل عن جنة ونار، أشرح لها إزاي؟", "عن جنة ونار"),
    ("إيمان", "بنتي إيمان عندها ١٠ سنين، إزاي أعلمها إن إيمان بالله أهم حاجة؟",
     "إن إيمان بالله"),
    ("أمل", "بنتي أمل عندها توحد، هل في أمل إنها تتكلم؟", "في أمل إنها"),
])
def test_a_recognised_child_does_not_take_every_word_use(name, question, kept):
    """R6: only a mention that opens a clause extends («…ونور كمان بترفض»,
    still redacted by test_a_child_recognised_once_…); not after «إن/أن»."""
    out = redact_family(question, Family(((1, name),)), 1)
    assert kept in out and out.startswith("بنتي طفلي"), out


# 4. A token two children share.


def test_a_token_two_children_share_is_nobodys():
    """R5: «محمد» is in both names — alone it is likelier their father than
    either child, and it must not swallow «سارة محمد» and leave «سارة»."""
    fam = Family(((1, "أحمد محمد"), (2, "سارة محمد")))
    out = cm.clean_fact_text("سارة محمد تغار من أحمد", fam, 2)
    assert out == "طفلي تغار من الطفل أ" and _oracle_left(out, ["أحمد", "سارة"]) == []
    assert cm.clean_fact_text("سارة تحب والدها محمد كثيرًا", fam, 2) == \
        "طفلي تحب والدها محمد كثيرًا"
    assert redact_family("سارة محمد بتغير من أحمد", fam, 2) == "طفلي بتغير من الطفل أ"
    assert family_mentions("سارة محمد بتغير من أحمد", fam) == [1, 2]
    assert family_mentions("والدها محمد مسافر", fam) == []
    # A whole name still beats another child's token.
    assert redact_family("محمد بيضرب أحمد", Family(((1, "محمد"), (2, "أحمد محمد")))) == \
        "الطفل أ بيضرب الطفل ب"


# 5. Races: a deletion while a question is being learned from.


def test_a_deletion_inside_the_extraction_is_refused(client, monkeypatch):
    """R4: deleted between the family read and the generation read."""
    from app.routers.privacy import erase_child
    dev = "dev-r4"
    h = _session(client, dev)
    sara = _child(client, h, "سارة")
    ahmad = _child(client, h, "أحمد")
    _child(client, h, "نور")
    _memory_build(monkeypatch, dev)
    _fake_llm(monkeypatch, "طفلي تغار من نور")

    def delete_then_ok():
        erase_child(dev, ahmad)
        return True
    monkeypatch.setattr(cm, "extraction_budget_ok", delete_then_ok)
    stats = cm.extract_and_store(dev, sara, question="سارة بتغار من نور وبتضربها كل يوم",
                                 answer="جرّب وقتًا خاصًا لكل طفل.", proven=True)
    assert stats is None or stats["refused"] is True
    assert _rows("SELECT COUNT(*) FROM child_facts WHERE device_id = ?", dev) == [(0,)]


def test_a_deletion_after_the_question_refuses_what_its_answer_teaches(client, monkeypatch):
    """R3: the question arrives (generation, then family), the parent deletes
    a child while the answer streams, the extraction runs after: refused —
    «أحمد» never lands in a fact."""
    dev = "dev-r3"
    h = _session(client, dev)
    sara = _child(client, h, "سارة")
    ahmad = _child(client, h, "أحمد")
    _memory_build(monkeypatch, dev)
    asked = cm.memory_generation(dev)
    assert client.delete(f"/api/children/{ahmad}", headers=h).status_code == 200
    _fake_llm(monkeypatch, "طفلي تغار من أحمد وتضربه")
    stats = cm.extract_and_store(dev, sara, question="سارة بتغار من أحمد وبتضربه كل يوم",
                                 answer="جرّب وقتًا خاصًا لكل طفل.", proven=True,
                                 generation=asked)
    assert stats["refused"] is True
    assert _rows("SELECT COUNT(*) FROM child_facts WHERE device_id = ?", dev) == [(0,)]


def _quiet_pipeline(monkeypatch) -> list[str]:
    """The assistant with retrieval and every model call replaced; returns the
    list the classifier and rewriter inputs are recorded in."""
    from app.routers import assistant
    from app.services import answer_cache

    async def no_ayah(_t):
        return None

    _Recorder.prompts = []
    seen: list[str] = []
    monkeypatch.setattr(assistant, "classify_domains", lambda t: seen.append(t) or ["tarbiyah"])
    monkeypatch.setattr(assistant, "rewrite_query", lambda t, **k: seen.append(t) or "")
    monkeypatch.setattr(assistant, "retrieve_hybrid", lambda **kw: [{
        "unit_id": "u1", "document": "passage: الروتين الثابت يساعد على النوم.",
        "metadata": {"domain": "tarbiyah", "reference_info": "دليل"},
        "rerank_score": 2.0, "source_domain": "tarbiyah"}])
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", no_ayah)
    monkeypatch.setattr(answer_cache, "lookup", lambda *a, **k: None)
    monkeypatch.setattr(answer_cache, "store", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "OllamaProvider", _Recorder)
    ai_gateway._gateway = None
    return seen


def test_the_assistant_reads_the_generation_before_the_family(client, monkeypatch):
    """The real path: the generation is read before the question's family and
    handed to the extraction, which a deletion in between then refuses."""
    from app.routers import assistant
    dev = "dev-gen-order"
    h = _session(client, dev)
    sara = _child(client, h, "سارة")
    ahmad = _child(client, h, "أحمد")
    _memory_build(monkeypatch, dev)
    _quiet_pipeline(monkeypatch)
    order: list[str] = []
    real_generation, real_family = cm.memory_generation, assistant.family_for_device
    monkeypatch.setattr(cm, "memory_generation",
                        lambda d: order.append("generation") or real_generation(d))
    monkeypatch.setattr(assistant, "family_for_device",
                        lambda d: order.append("family") or real_family(d))
    scheduled: dict = {}
    monkeypatch.setattr(cm, "schedule_extraction",
                        lambda *a, **k: scheduled.update(args=a, kwargs=k))
    try:
        r = client.post("/api/assistant/stream", headers=h, json={
            "age_group": "4-6", "severity": "خفيف", "child_id": sara,
            "message_text": "سارة بتغار من أحمد وبتضربه كل يوم، أعمل إيه؟"})
        assert r.status_code == 200
    finally:
        ai_gateway._gateway = None
    assert order[:2] == ["generation", "family"]
    assert scheduled["kwargs"]["generation"] == cm.memory_generation(dev)
    assert client.delete(f"/api/children/{ahmad}", headers=h).status_code == 200
    _fake_llm(monkeypatch, "طفلي تغار من أحمد وتضربه")
    stats = cm.extract_and_store(*scheduled["args"], **scheduled["kwargs"])
    assert stats["refused"] is True


def test_manual_writes_clean_with_the_family_as_it_is_now(client, monkeypatch):
    """add, edit and a follow-up answer read the family under their write
    lock — never a stale one from before a deletion (old letters)."""
    dev = "dev-stale-family"
    h = _session(client, dev)
    sara = _child(client, h, "سارة")
    ahmad = _child(client, h, "أحمد")
    _child(client, h, "عمر")                                # ج, then ب
    stale = family_for_device(dev)
    assert client.delete(f"/api/children/{ahmad}", headers=h).status_code == 200
    monkeypatch.setattr(cm, "family_for_device", lambda d: stale)
    added = client.post(f"/api/children/{sara}/memory", headers=h,
                        json={"category": "other", "fact": "سارة تلعب مع عمر"}).json()
    assert added["fact"] == "طفلي تلعب مع الطفل ب"
    edited = client.patch(f"/api/children/{sara}/memory/{added['id']}", headers=h,
                          json={"fact": "سارة تحب عمر كثيرًا"}).json()
    assert edited["fact"] == "طفلي تحب الطفل ب كثيرًا"
    fid = _due_followup(dev, sara, "لعب مشترك كل يوم", "siblings")
    answered = client.post(f"/api/children/followups/{fid}/answer", headers=h,
                           json={"outcome": "worked", "note": "عمر فرح كثيرًا"}).json()
    assert "الطفل ب فرح" in answered["fact"]["fact"]


# 6. Spelling gaps in strict matching.


@pytest.mark.parametrize("members,subject,text,expected", [
    ([(1, "الحسن"), (2, "سارة")], 2, "سارة تعطي ألعابها للحسن دائمًا",
     "طفلي تعطي ألعابها للطفل أ دائمًا"),
    ([(1, "عبد الله محمد"), (2, "سارة")], 2, "سارة تغار من عبدالله", "طفلي تغار من الطفل أ"),
    ([(1, "عبد الله"), (2, "سارة")], 2, "سارة تغار من عبد  الله", "طفلي تغار من الطفل أ"),
    ([(1, "أسماء"), (2, "أحمد")], 2, "أحمد يغار من اسما", "طفلي يغار من الطفل أ"),
    ([(1, "سماء"), (2, "أحمد")], 2, "أحمد يغار من سما", "طفلي يغار من الطفل أ"),
    ([(1, "دعاء"), (2, "أحمد")], 2, "أحمد يغار من دعا", "طفلي يغار من الطفل أ"),
    ([(1, "أحمد"), (2, "سارة")], 2, "اشتريت هدية لـأحمد وبـأحمد",
     "اشتريت هدية للطفل أ وبالطفل أ"),
    ([(1, "محمد"), (2, "سارة")], 2, "سارة تغار من ـمحمد", "طفلي تغار من الطفل أ"),
    ([(1, "محمد"), (2, "سارة")], 2, "سارة تغار من مح‌مد", "طفلي تغار من الطفل أ"),
    ([(1, "أحمد"), (2, "نور")], 1, "أحمد|نور يلعبان معًا", "طفلي الطفل ب يلعبان معًا"),
])
def test_strict_closes_the_spelling_gaps(members, subject, text, expected):
    fam = Family(tuple(members))
    out = cm.clean_fact_text(text, fam, subject)
    assert out == expected
    assert _oracle_left(out, fam.names) == [], out


def test_a_hamzaless_name_stays_a_verb_in_a_question():
    assert redact_family("أحمد دعا ربه قبل النوم", Family(((1, "دعاء"), (2, "أحمد"))), 2) == \
        "طفلي دعا ربه قبل النوم"


# 7. Rename, notes, particles.


def test_a_rename_across_the_floor_reletters(client):
    """A child renamed across the 2-character floor enters (or leaves) the
    letter order: its siblings' memory follows."""
    dev = "dev-rename-floor"
    h = _session(client, dev)
    sara = _child(client, h, "سارة")                       # أ
    short = _child(client, h, "م")                          # no letter
    _child(client, h, "عمر")                                # ب
    fid = _insert_fact(dev, sara, "طفلي تلعب مع الطفل ب")
    assert client.patch(f"/api/children/{short}", headers=h,
                        json={"name": "مريم"}).status_code == 200
    assert _fact_text(fid) == "طفلي تلعب مع الطفل ج"         # عمر is ج now
    assert client.patch(f"/api/children/{short}", headers=h,
                        json={"name": "م"}).status_code == 200
    assert _fact_text(fid) == "طفلي تلعب مع الطفل ب"


def test_a_renamed_childs_old_name_does_not_outlive_the_rename(client):
    """Written before he had a profile, «يوسف» was redacted on its way into
    a prompt only while it was his name; after the rename it is his letter."""
    dev = "dev-rename-old"
    h = _session(client, dev)
    sara = _child(client, h, "سارة")
    yusuf = _child(client, h, "يوسف")
    fid = _insert_fact(dev, sara, "طفلي تقلّد أخاها يوسف")
    assert client.patch(f"/api/children/{yusuf}", headers=h,
                        json={"name": "جود"}).status_code == 200
    assert _fact_text(fid) == "طفلي تقلّد أخاها الطفل ب"
    block, used = cm.facts_block(dev, sara, "")
    assert used == 1 and "يوسف" not in block


def test_a_deleted_childs_name_leaves_its_siblings_notes(client):
    dev = "dev-note-scrub"
    h = _session(client, dev)
    sara = _child(client, h, "سارة")
    ahmad = _child(client, h, "أحمد")
    fid = _due_followup(dev, sara)
    conn = get_conn()
    conn.execute("UPDATE followups SET note = ? WHERE id = ?", ("أحمد كان يضحك عليها", fid))
    conn.commit()
    conn.close()
    assert client.delete(f"/api/children/{ahmad}", headers=h).status_code == 200
    assert _rows("SELECT note FROM followups WHERE id = ?", fid) == [
        ("طفل آخر كان يضحك عليها",)]


@pytest.mark.parametrize("members,subject,text,word", [
    ([(1, "علا"), (2, "سارة")], 2, "سارة فعلا بتكذب", "فعلا"),
    ([(1, "ريم"), (2, "أحمد")], 2, "أحمد بيقول رمضان كريم لكل الناس", "رمضان كريم"),
])
def test_f_and_k_do_not_split_a_short_name_off_a_word(members, subject, text, word):
    fam = Family(tuple(members))
    assert word in redact_family(text, fam, subject)
    assert word in cm.clean_fact_text(text, fam, subject)
    # «و/ب/ل» still do, for every name.
    assert redact_family("سارة تلعب مع علا ولعلا لعبة", Family(((1, "علا"), (2, "سارة"))), 2) \
        == "طفلي تلعب مع الطفل أ وللطفل أ لعبة"


def test_huna_is_here_unless_it_is_the_child():
    fam = Family(((1, "هنا"), (2, "أحمد")))
    assert redact_family("أحمد بيحب يقعد هنا وهنا", fam, 2) == "طفلي بيحب يقعد هنا وهنا"
    assert redact_family("بنتي هنا بتخاف من الضلمة", fam, 1) == "بنتي طفلي بتخاف من الضلمة"
