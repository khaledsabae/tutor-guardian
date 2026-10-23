"""«ليه ربنا خلق الشر؟» is a creed question: it must reach `aqeedah` (and `fiqh`).

The aqeedah unit `aqe-why-evil-7-9-01` is stored under `aqeedah`; retrieval filters
by domain, so a classifier answer of `fiqh` / `development` / `medical` alone made
it unreachable. And the age rule («سنين» -> development) sent «ابني ٩ سنين سألني
ليه ربنا خلق الشر؟» to `development` ONLY. The phrases are anchored (bare «شر» is
also «شرح»/«شرب»/«شريط»), so everyday sentences must stay out.
"""
import pytest

from app.routers.assistant import _label_domain
from app.services import domain_classifier as classifier
from app.services.domain_classifier import _keyword_fast_path, classify_domains


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
    # Variants of the Creator-doing-the-creating shape.
    "ليه ربنا بيخلق الشر؟",
    "هل يخلق الله الشر؟",
    "وليه ربنا بيسيب الناس تتعذب",
    "ليه الله بيسيب الأطفال يموتوا",
    # The same creed question about Iblis.
    "ليه ربنا خلق الشيطان؟",
    "ابني ٨ سنين سألني لماذا خلق الله إبليس",
])
def test_evil_question_routes_to_aqeedah_and_fiqh(question):
    domains = _keyword_fast_path(question) or []
    assert "aqeedah" in domains
    assert "fiqh" in domains  # alias of islamic_parenting


def test_creed_domain_leads_so_the_label_is_aqeedah():
    """The reply is labelled and guardrailed with domains[0]
    (assistant._label_domain); rule order alone put `fiqh` first."""
    for q in [
        "ليه ربنا خلق الشر؟",
        "ابني ٩ سنين سألني ليه ربنا خلق الشر؟ كيف أجاوبه بما يناسب سنه",
        "ابني بيسأل ليه ربنا بيسيب الناس تتعذب",
        "ليه ربنا خلق إبليس؟",
    ]:
        domains = _keyword_fast_path(q)
        assert domains[0] == "aqeedah", (q, domains)
        assert "fiqh" in domains  # still searched
        assert _label_domain(domains, []) == "aqeedah"


@pytest.fixture
def no_llm(monkeypatch):
    """Stub the LLM tier so a test through classify_domains proves the
    KEYWORD tier decided (the stub fails the test if it is ever consulted)."""
    monkeypatch.setattr(classifier, "_call_llm",
                        lambda _: pytest.fail("LLM tier consulted"))
    classifier._classify_cached.cache_clear()
    yield
    classifier._classify_cached.cache_clear()


def test_classify_domains_end_to_end_without_llm(no_llm):
    domains = classify_domains("ابني ٩ سنين سألني ليه ربنا خلق الشر؟")
    assert domains[:2] == ["aqeedah", "fiqh"]
    assert "development" in domains
    assert _label_domain(domains, []) == "aqeedah"


def test_classify_domains_idiom_falls_through_to_the_llm_tier(monkeypatch):
    """The idiom no longer decides at the keyword tier: the (stubbed) model does."""
    seen = []
    monkeypatch.setattr(classifier, "_call_llm", lambda q: seen.append(q) or ["medical"])
    classifier._classify_cached.cache_clear()
    try:
        assert classify_domains("ابني بيخلق شر في البيت") == ["medical"]
    finally:
        classifier._classify_cached.cache_clear()
    assert seen, "the idiom should have reached the LLM tier"


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
    # 167-A: «بيخلق شر» is the Egyptian idiom for causing trouble — no Creator.
    "ابني بيخلق شر في البيت",
    "ابني بيخلق الشر مع إخواته",
    "ابني بيخلق شرور كل يوم",
    "بنتي بتخلق شر بين صحباتها",
    "ابني خلق شر في المدرسة",
    "ابني رسم شريط وخلق شريط جديد",
    # 167-B: «شر بين / عند / مع» is a conflict between people, not the world.
    "ليه في شر بين أخواتي",
    "ليه فيه شر بين الولدين",
    "ليه في شر عند ابني مع زمايله",
    "ليه في شر مع الجيران",
    # 167-C: the noun needs its own right boundary.
    "ليه ربنا بيسيب عيالي يضربوا بعض",
    "ليه ربنا يسمح بالشرك",
])
def test_everyday_sentences_do_not_route_to_aqeedah(question):
    assert "aqeedah" not in (_keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    "ابني ٩ سنين مابياكلش كويس",
    "ابني ٧ سنين بيشرح لي لعبته",
])
def test_age_rule_still_routes_everyday_age_questions_to_development(question):
    assert _keyword_fast_path(question) == ["development"]
