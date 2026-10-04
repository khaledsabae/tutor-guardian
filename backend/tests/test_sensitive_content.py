"""What child memory must never keep (PR #26 review F6).

The reviewer's probe table, row for row (Egyptian euphemisms, conjugations,
feminine and plural forms, brand-name spellings, and the «جرعة حنان» false
positive), the false positives the context rules exist to avoid, and the
extractor's own "sensitive" label.
"""
from __future__ import annotations

import json

import pytest

from app.services import child_memory as cm
from app.services.sensitive_content import is_harmful, mentions_medication


def _kind(text: str) -> str:
    return "harm" if is_harmful(text) else ("med" if mentions_medication(text) else "ok")


REVIEW_PROBE = [
    ("harm", "ابني بيقول انه عايز يموت"),
    ("harm", "بنتي بتقول نفسها تموت"),
    ("harm", "ابني بيأذي نفسه لما يزعل"),
    ("harm", "ابني بيضرب نفسه في الحيطة لما يتعصب"),
    ("harm", "بنتي بتجرح نفسها بالموس"),
    ("harm", "بنتي بتشرّط إيدها"),
    ("harm", "ابني شاف فيديوهات قلة أدب على النت"),
    ("harm", "ابني بيتفرج على أفلام وحشة في السر"),
    ("harm", "ابني دخل على مواقع إباحية"),
    ("harm", "واحد بيكلم بنتي على النت وطلب منها صورها من غير هدوم"),
    ("harm", "حد بعتلها صور عريانة"),
    ("harm", "ابن خالته لمسه في حتة وحشة"),
    ("harm", "المدرس عمل فيه حاجة وحشة في الحمام"),
    ("harm", "ابني اتعرض لتحرش في الباص"),
    ("harm", "ابني بيشم كُلّة مع صحابه"),
    ("harm", "ابني بيشرب بيرة مع صحابه"),
    ("harm", "ابني بيشرب حشيش"),
    ("med", "بياخد ريتالين ١٠ مللي الصبح"),
    ("med", "الدكتور كتبله دوا للتركيز"),
    ("med", "بياخد علاج للتركيز من الدكتور النفسي"),
    ("med", "بياخد كونسرتا ٣٦"),
    ("med", "بياخد ريسبريدون نص حباية"),
    ("med", "بياخد حباية منومة بالليل"),
    ("med", "بنديله حبوب منومة"),
    ("med", "بنديله حقنة كل شهر"),
    ("med", "بياخد ميلاتونين قبل النوم"),
    ("med", "he takes 10mg of ritalin"),
    ("med", "she is on concerta"),
    ("ok", "ابني بيخاف من الظلام"),
    ("ok", "ابني عنيد ومش بيسمع الكلام"),
    ("ok", "محتاجة جرعة حنان زيادة"),
    ("ok", "كيف أعلّم ابني التربية الجنسية المناسبة لعمره"),
    ("ok", "ابني عنده ربو"),
]

# The same words in their innocent senses — what the context rules are for.
INNOCENT = [
    "ابني عنده قلة أدب مع جدته",           # rudeness, a behaviour to work on
    "ابني عمل حاجة وحشة في المدرسة",        # a misdeed, not something done to him
    "ابني بيقول كلام وحش",
    "ابني بيقطع نفسه من العياط",            # breath-holding while crying
    "عنده حبوب في وشه من الشوكولاتة",        # spots, not pills
    "بشرط إنه يخلص واجبه",                  # «شرط»: a condition
    "الشرطة جت البيت",
    "بيشم الورد",
    "بيشرب لبن قبل النوم",
    "جنسيته مصرية", "ابني مزدوج الجنسية",
    "مهدي بيخاف من الظلام",                 # a name, not «مهدئ»
]

MORE_FORMS = [
    ("med", "بنديلها حبايات منومة"),          # plural + feminine
    ("med", "زودنا الجرعة الأسبوع ده"),
    ("med", "بياخد جرعتين في اليوم"),
    ("med", "جرعة من الدوا قبل النوم"),
    ("med", "بياخد مهدئات"),
    ("harm", "بتعض نفسها لما تتعصب"),
    ("harm", "ابني بيتفرج على حاجات وحشة على الموبايل"),
    ("harm", "ضربت نفسها بالقلم لما زعلت"),
    ("harm", "my son hits himself when angry"),
    ("harm", "she sniffs glue"),
]


@pytest.mark.parametrize("want,text", REVIEW_PROBE)
def test_the_reviewers_probe(want, text):
    assert _kind(text) == want


@pytest.mark.parametrize("text", INNOCENT)
def test_innocent_uses_are_not_screened(text):
    assert _kind(text) == "ok"


@pytest.mark.parametrize("want,text", MORE_FORMS)
def test_conjugations_plurals_and_feminine_forms(want, text):
    assert _kind(text) == want


# ── The extractor labels what it returns ──────────────────────────────────


def _raw(facts, followup=None, sensitive=None) -> str:
    data: dict = {"facts": facts, "followup": followup}
    if sensitive is not None:
        data["sensitive"] = sensitive
    return json.dumps(data, ensure_ascii=False)


def _fact(text, sensitive=None) -> dict:
    f = {"category": "challenge", "fact": text, "confidence": 0.9, "replaces": None}
    if sensitive is not None:
        f["sensitive"] = sensitive
    return f


def test_a_fact_the_extractor_labels_sensitive_is_dropped():
    facts, _ = cm.parse_extraction(_raw([_fact("طفلي يخاف من الظلام"),
                                         _fact("طفلي يتعرض لأذى من قريب", True)]))
    assert [f["fact"] for f in facts] == ["طفلي يخاف من الظلام"]


@pytest.mark.parametrize("label", [True, "true", "True", 1, "yes"])
def test_a_label_in_any_spelling_drops(label):
    facts, _ = cm.parse_extraction(_raw([_fact("طفلي حساس", label)]))
    assert facts == []


@pytest.mark.parametrize("label", [False, "false", 0, None])
def test_no_label_or_a_false_one_keeps(label):
    facts, _ = cm.parse_extraction(_raw([_fact("طفلي حساس", label)]))
    assert len(facts) == 1


def test_a_message_labelled_sensitive_keeps_nothing():
    fu = {"strategy": "حوار هادئ", "topic": "other", "days": 4}
    assert cm.parse_extraction(_raw([_fact("طفلي يخاف من الظلام")], fu, True)) == ([], None)


def test_a_followup_labelled_sensitive_is_dropped():
    fu = {"strategy": "حوار هادئ عن الصور", "topic": "other", "days": 4, "sensitive": True}
    facts, followup = cm.parse_extraction(_raw([_fact("طفلي يخاف من الظلام")], fu))
    assert len(facts) == 1 and followup is None


def test_the_prompt_asks_for_the_label():
    prompt = cm.EXTRACT_PROMPT
    assert '"sensitive": false' in prompt and "when unsure, label" in prompt
