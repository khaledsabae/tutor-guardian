"""A2 / P4 / A6 (PR #26 review): child-name redaction, in both directions.

Every model call is redacted since PR #26, so the matcher's mistakes became
live: names typed another way leaked (احمد, فاطمه, عبد الرحمن, Mohamed…), and
names that are ordinary words broke questions (أركان الإسلام → أركان طفلي,
آية الكرسي → طفلي الكرسي). Siblings all became one «طفلي». Each case the
review probed is pinned here.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.services import ai_gateway
from app.services.privacy import (
    Family, family_mentions, redact_family, redact_for_cloud, redact_with_names,
)


def _one(name: str, text: str) -> str:
    return redact_family(text, Family(((1, name),)))


SHOULD_REDACT = [
    ("أحمد", "احمد بيضرب أخته"), ("فاطمة", "فاطمه بتعيط"), ("ليلى", "ليلي مش بتاكل"),
    ("محمد", "محمّد عنيد"), ("عبدالرحمن", "عبد الرحمن بيكذب"),
    ("عبد الرحمن", "عبدالرحمن بيكذب"), ("Adam", "adam won't sleep"),
    ("adam", "Adam won't sleep"), ("محمد", "Mohamed refuses to pray"),
    ("Mohamed", "محمد يرفض الصلاة"), ("محمد علي", "محمد مش بيذاكر"),
    ("يوسف", "جنبي يوسف قاعد"), ("يوسف", "ذنبي يوسف"), ("نور", "ونور نائمة"),
    ("أحمد", "قلت لأحمد وبأحمد"), ("علي", "علي عنيد جدًا"), ("منة", "منة بتغير من أخوها"),
    ("آية", "آية بتصرخ كل يوم"), ("إيمان", "ايمان مش بتصلي"),
]

SHOULD_KEEP = [
    ("إسلام", "ما هي أركان الإسلام؟"), ("فجر", "كيف أوقظه لصلاة الفجر"),
    ("آية", "معنى آية الكرسي"), ("دعاء", "علمته دعاء النوم"),
    ("جمعة", "صلاة الجمعة مع أبيه"), ("رمضان", "هل يصوم رمضان وعمره سبع؟"),
    ("نور", "بيخاف ينام من غير نور"), ("يوسف", "قصة النبي يوسف"),
    ("يوسف", "سورة يوسف"), ("محمد", "النبي محمد ﷺ"), ("مريم", "مريم عليها السلام"),
    ("علي", "اعتمد على نفسه"), ("منة", "خد منه اللعبة"), ("نور", "سورة النور"),
    ("نور", "للنور"), ("رحمة", "رحمه الله"), ("محمد", "سيدنا محمد صلّى الله عليه وسلّم"),
    ("عبدالرحمن", "الرحمن الرحيم"),
]


# F5 (PR #26 review, round 2): a name that is also a word is the child only on
# positive evidence of a person. The reviewer's probe rows first, then more.
EVIDENCE_OF_A_PERSON = [
    ("آية", "آية الكبيرة بتغير من أختها"),          # age adjective after
    ("إسلام", "إسلام عنده ٧ سنين ومش بيصلي"),        # opens the clause + predicate
    ("نور", "بنتي نور بتخاف من الظلام"),             # kinship before
    ("علي", "علي بيضرب أخته"),                       # opens the clause + verb
    ("محمد علي", "اتكلمت مع علي عن الصلاة"),         # «مع» before
    ("دعاء", "يا دعاء تعالي هنا"),                   # vocative
    ("أمل", "لما أمل بتزعل بتكسر حاجات"),            # «لما» opens the clause
    ("إيمان", "إيمان بقت عنيدة جدًا"),
    ("فجر", "ابني فجر مبيسمعش الكلام"),
    ("رمضان", "ابني رمضان عنده ٤ سنين"),
    ("علي", "علي ما بيسمعش الكلام"),                 # negation, then the verb
    ("علي", "اشتريت لعلي لعبة"),                     # «ل»+«على» is not a word
    ("هدى", "هدى بتكذب كتير"),
    ("سلام", "أخوها سلام بيضربها"),
    ("جنى", "جنى عمرها ٣ سنين"),
    ("دعاء", "دعاء، عمرها ٦ سنين"),
]

NO_EVIDENCE_OF_A_PERSON = [
    ("فجر", "ازاي اصحيه لصلاة فجر كل يوم"),
    ("دعاء", "ما هو دعاء قبل النوم للأطفال"),
    ("دعاء", "كيف أعلمه دعاء دخول الخلاء"),
    ("دعاء", "اريد دعاء لابني بالهداية"),
    ("رمضان", "كيف أجهز ابني نفسيا استعدادا لرمضان"),
    ("أمل", "عندي أمل إن ابني يتحسن"),
    ("إيمان", "كيف أقوي إيمان ابني بالله"),
    ("علي", "ازاي اعوده علي الصلاة"),                # Egyptian spelling of «على»
    ("آية", "كيف أحفّظ ابني آية الكرسي"),            # kinship, but a construct wins
    ("دعاء", "دعاء يحفظ الطفل من العين"),            # a masculine verb: not a girl
    ("علي", "علي طول بيعيط"),
    ("مني", "بنتي بتخاف مني"),
    ("سلام", "سلام عليكم عندي سؤال"),
    ("أمل", "أمل كبير إنه يتغير"),
    ("نور", "نور القرآن في البيت"),
    ("جمعة", "يوم جمعة سعيد"),
    ("علي", "قال لي علي فكرة"),
    ("فرح", "فرح كبير لما نجح"),
]


@pytest.mark.parametrize("name,text", EVIDENCE_OF_A_PERSON)
def test_a_word_name_is_redacted_on_evidence_of_a_person(name, text):
    out = _one(name, text)
    assert "طفلي" in out and out != text


@pytest.mark.parametrize("name,text", NO_EVIDENCE_OF_A_PERSON)
def test_a_word_name_without_evidence_of_a_person_is_left_alone(name, text):
    assert _one(name, text) == text
    assert family_mentions(text, Family(((1, name),))) == []


def test_only_the_mention_with_evidence_is_redacted():
    # The child «مني» and the word «مني» (from me) in one sentence.
    assert _one("مني", "بنتي مني بتخاف مني") == "بنتي طفلي بتخاف مني"
    assert _one("علي", "علي بيعيط علي طول") == "طفلي بيعيط علي طول"
    # Siblings stay distinct, and the age adjective marks the subject child.
    fam = Family(((1, "آية"), (2, "سارة")))
    assert redact_family("آية الكبيرة بتغير من أختها", fam, subject_id=1) == \
        "طفلي الكبيرة بتغير من أختها"
    assert redact_family("آية الكبيرة بتغير من سارة", fam) == "الطفل أ الكبيرة بتغير من الطفل ب"


@pytest.mark.parametrize("name,text", SHOULD_REDACT)
def test_every_spelling_of_the_childs_name_is_replaced(name, text):
    out = _one(name, text)
    assert "طفلي" in out and out != text
    # Nothing of the name survives (Latin case-insensitively).
    for token in name.lower().split():
        assert token not in out.lower() or token in ("عبد",)


@pytest.mark.parametrize("name,text", SHOULD_KEEP)
def test_a_name_that_is_also_a_word_or_a_prophet_is_left_alone(name, text):
    assert _one(name, text) == text


def test_siblings_get_distinct_placeholders():
    fam = Family(((1, "سارة"), (2, "أحمد")))
    assert redact_family("سارة بتضرب أحمد", fam) == "الطفل أ بتضرب الطفل ب"
    # The child the question is about is «طفلي»; the sibling keeps a letter.
    assert redact_family("سارة بتضرب أحمد", fam, subject_id=1) == "طفلي بتضرب الطفل ب"
    assert redact_family("ولأحمد عادة العناد", fam) == "وللطفل ب عادة العناد"
    assert family_mentions("سارة بتضرب أحمد", fam) == [1, 2]


def test_generic_redaction_keeps_one_placeholder():
    assert redact_with_names("سارة وأحمد", ("سارة", "أحمد")) == "طفلي وطفلي"


def test_redact_for_cloud_uses_the_family(client):
    h = _auth(client, "dev-fam")
    client.post("/api/children", json={"name": "سارة", "age_group": "4-6"}, headers=h)
    client.post("/api/children", json={"name": "أحمد", "age_group": "7-9"}, headers=h)
    assert redact_for_cloud("سارة بتضرب أحمد", "dev-fam") == "الطفل أ بتضرب الطفل ب"


# ── Through the assistant ─────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, device):
    tok = client.post("/api/chat/sessions", json={"device_id": device}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


class _Recorder:
    prompts: list[str] = []
    name, model = "fake", "fake-model"

    def __init__(self, *a, **k):
        pass

    def stream(self, prompt, *, options):
        _Recorder.prompts.append(prompt)
        yield {"response": "جرّب روتينًا ثابتًا قبل النوم مع قصة قصيرة كل ليلة.", "done": False}
        yield {"response": "", "done": True, "prompt_eval_count": 1, "eval_count": 1}


@pytest.fixture
def pipeline(monkeypatch):
    from app.routers import assistant
    from app.services import answer_cache

    async def no_ayah(_t):
        return None

    _Recorder.prompts = []
    calls = {"lookup": 0, "store": 0}
    monkeypatch.setattr(assistant, "classify_domains", lambda t: ["tarbiyah"])
    monkeypatch.setattr(assistant, "rewrite_query", lambda t, **k: "")
    monkeypatch.setattr(assistant, "retrieve_hybrid", lambda **kw: [{
        "unit_id": "u1", "document": "passage: الروتين الثابت يساعد على النوم.",
        "metadata": {"domain": "tarbiyah", "reference_info": "دليل"},
        "rerank_score": 2.0, "source_domain": "tarbiyah"}])
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", no_ayah)
    monkeypatch.setattr(answer_cache, "lookup",
                        lambda *a, **k: calls.__setitem__("lookup", calls["lookup"] + 1))
    monkeypatch.setattr(answer_cache, "store",
                        lambda *a, **k: calls.__setitem__("store", calls["store"] + 1))
    monkeypatch.setattr(ai_gateway, "OllamaProvider", _Recorder)
    ai_gateway._gateway = None
    yield calls
    ai_gateway._gateway = None


def _ask(client, h, text, age="4-6"):
    r = client.post("/api/assistant/stream", headers=h,
                    json={"age_group": age, "severity": "خفيف", "message_text": text})
    assert r.status_code == 200
    return json.loads(r.text.split("event: done\ndata: ", 1)[1].split("\n", 1)[0])


def test_a_question_naming_the_child_in_another_spelling_skips_the_shared_cache(client, pipeline):
    """The «personal» check uses the same matcher: «احمد» names «أحمد» (P4)."""
    h = _auth(client, "dev-cache-variant")
    client.post("/api/children", json={"name": "أحمد", "age_group": "4-6"}, headers=h)
    _ask(client, h, "احمد يرفض النوم مبكرًا كل ليلة")
    assert pipeline == {"lookup": 0, "store": 0}
    assert "احمد" not in _Recorder.prompts[-1] and "أحمد" not in _Recorder.prompts[-1]


def test_a_prayer_question_reaches_the_model_intact(client, pipeline):
    """A2: a child named «فجر» must not turn «صلاة الفجر» into «صلاة طفلي»."""
    h = _auth(client, "dev-fajr")
    client.post("/api/children", json={"name": "فجر", "age_group": "7-9"}, headers=h)
    _ask(client, h, "كيف أوقظه لصلاة الفجر بلطف؟", age="7-9")
    assert "لصلاة الفجر" in _Recorder.prompts[-1]


def test_a_sibling_question_stays_coherent_in_the_prompt(client, pipeline):
    h = _auth(client, "dev-sib")
    client.post("/api/children", json={"name": "سارة", "age_group": "4-6"}, headers=h)
    client.post("/api/children", json={"name": "أحمد", "age_group": "7-9"}, headers=h)
    _ask(client, h, "سارة بتضرب أحمد كل يوم، أعمل إيه؟")
    prompt = _Recorder.prompts[-1]
    assert "الطفل أ بتضرب الطفل ب" in prompt or "طفلي بتضرب الطفل ب" in prompt
    assert "سارة" not in prompt and "أحمد" not in prompt


def test_resolve_child_ignores_a_name_used_as_a_word(client):
    from app.services import child_memory as cm
    h = _auth(client, "dev-nour")
    client.post("/api/children", json={"name": "نور", "age_group": "4-6"}, headers=h)
    other = client.post("/api/children", json={"name": "زياد", "age_group": "7-9"},
                        headers=h).json()["id"]
    assert cm.resolve_child("dev-nour", age_group="7-9", text="بيخاف ينام من غير نور") == other
