"""«ليه ربنا خلق الشر؟» is a creed question: it must reach `aqeedah` (and `fiqh`).

The aqeedah unit `aqe-why-evil-7-9-01` is stored under `aqeedah`; retrieval filters
by domain, so a classifier answer of `fiqh` / `development` / `medical` alone made
it unreachable. And the age rule («سنين» -> development) sent «ابني ٩ سنين سألني
ليه ربنا خلق الشر؟» to `development` ONLY. The phrases are anchored (bare «شر» is
also «شرح»/«شرب»/«شريط»), so everyday sentences must stay out.
"""
import pytest

from app.services.domain_classifier import _keyword_fast_path


@pytest.mark.parametrize("question", [
    "طيب هو سألني ليه ربنا خلق الشر؟ مش عارف أجاوبه إزاي بما يناسب سنه",
    "ليه ربنا خلق الشر؟",
    "لماذا خلق الله الشر؟",
    "ابني بيسأل ليه في شر في الدنيا",
    "بنتي سألتني ليه فيه شر",
    "ابني بيسأل ليه ربنا بيسيب الناس تتعذب",
    "ليه ربنا بيسمح بالظلم؟",
    "ابني ٩ سنين سألني ليه ربنا خلق الشر؟ كيف أجاوبه بما يناسب سنه",
    "ابني 9 سنين بيسأل ليه ربنا خلق الشر",
    "مشكلة الشر والألم عند طفل صغير",
    "لماذا خلق الله الشر؟ ابني ٨ سنين",
    "ابني ٧ سنين بيسأل ليه ربنا بيسيب الأطفال تتعذب",
    "بنتي ١٠ سنين سألتني ليه ربنا خلق الشرور في الدنيا",
])
def test_evil_question_routes_to_aqeedah_and_fiqh(question):
    domains = _keyword_fast_path(question) or []
    assert "aqeedah" in domains
    assert "fiqh" in domains  # alias of islamic_parenting


def test_age_in_years_does_not_hide_the_creed_domain():
    domains = _keyword_fast_path("ابني ٩ سنين سألني ليه ربنا خلق الشر؟")
    assert domains and domains != ["development"]
    assert "aqeedah" in domains


@pytest.mark.parametrize("question", [
    "ابني ٩ سنين مابياكلش كويس",
    "ابني بيشرب ميه كتير",
    "المدرس بيشرح الدرس بسرعة",
    "ليه في شريط على الشاشة؟",
    "ابني ٩ سنين بيخلق مشاكل في المدرسة",
    "بنتي بتخلق شرطة في لعبتها",
    "ليه في ظلم بين إخواتي في المعاملة",
    # Realistic parent questions that mention evil/villains/permission but are NOT
    # the creed question: fears about films, cartoon villains, sibling conflict.
    "ابني بيخاف من الشر في الأفلام",
    "ابني بيحب أفلام الشر والأبطال",
    "بنتي ٨ سنين بتخاف من شرير في الكرتون",
    "ليه ربنا يسمح لأخويا يضربني",
    "ابني ١٠ سنين بيسأل ليه ربنا خلق الأسد",
    "ابني بيشتكي من شرخ في الحيطة",
    "لماذا يوجد شرطي في الشارع",
])
def test_everyday_sentences_do_not_route_to_aqeedah(question):
    assert "aqeedah" not in (_keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    "ابني ٩ سنين مابياكلش كويس",
    "ابني ٧ سنين بيشرح لي لعبته",
])
def test_age_rule_still_routes_everyday_age_questions_to_development(question):
    assert _keyword_fast_path(question) == ["development"]
