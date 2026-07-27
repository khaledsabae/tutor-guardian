"""A "general" verdict on a question about the parent's own child is vetoed.

`general` is the one classification that skips retrieval entirely and answers
from nothing, so a false positive costs the parent the whole knowledge base.
Measured on production before the fix: DeepSeek called «بنتي اتخانقت مع صاحبتها
في المدرسة وقافلة على نفسها» and «ابني مابيحبش يروح المدرسة وبيعيط الصبح»
off-topic — 2 of 8 ordinary parenting questions sampled.
"""
import pytest

from app.services.domain_classifier import (
    UNCERTAIN_DOMAINS,
    _mentions_own_child,
    _parse_domains,
)

_GENERAL = '{"domains": ["general"]}'


@pytest.mark.parametrize("question", [
    "بنتي اتخانقت مع صاحبتها في المدرسة وقافلة على نفسها",
    "ابني مابيحبش يروح المدرسة وبيعيط الصبح",
    "طفلي بيعيط كتير من غير سبب",
    "ولدي بقى منطوي بعد ما نقلنا بيت",
    "ابنتي حزينة من امبارح",
    "طفلتي خايفة من المدرسة",
    "عيالي بيتخانقوا طول اليوم",
])
def test_general_is_vetoed_for_own_child(question):
    """The model's off-topic verdict is refused; we search broadly instead."""
    assert _parse_domains(_GENERAL, question) == list(UNCERTAIN_DOMAINS)


@pytest.mark.parametrize("question", [
    "ازاي أعمل كيكة الشوكولاتة",
    "ما هو الطقس غدًا",
    "أخبار الرياضة النهارده",
    "ازاي أتعلم برمجة بايثون",
])
def test_general_survives_for_genuinely_off_topic(question):
    """A real off-topic question still pivots — the veto must not swallow it."""
    assert _parse_domains(_GENERAL, question) == ["general"]


def test_third_person_children_is_not_own_child():
    """«الأطفال» in general is not the same as «ابني» — no veto."""
    assert not _mentions_own_child("الأطفال بيتكلموا امتى عمومًا")
    assert _parse_domains(_GENERAL, "الأطفال بيتكلموا امتى عمومًا") == ["general"]


def test_a_real_domain_still_wins_over_general():
    """The veto sits on the general branch only; it must not shadow a hit."""
    raw = '{"domains": ["cyber", "general"]}'
    assert _parse_domains(raw, "ابني على تيك توك طول اليوم") == ["cyber"]
