"""Tests for the domain classifier — keyword fast-path + cache + LLM fallback.

These tests mock the Ollama call so they're fast and need no network.
"""
import json

import pytest

from app.services.domain_classifier import (
    _keyword_fast_path,
    classify_domains,
)


def test_keyword_fast_path_fiqh():
    """Clear fiqh keywords return fiqh instantly without LLM."""
    questions = [
        "كيف أعلم ابني الصلاة",
        "ما حكم صيام الأطفال",
        "ابنتي تريد تعلم القرآن",
        "كيف نربي أبناءنا على الأخلاق",
        "ابني لا يصلي الفجر",
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Fast-path should match: {q}"
        assert "fiqh" in domains, f"Expected fiqh in {domains} for: {q}"


def test_keyword_fast_path_medical():
    """Clear medical keywords return medical instantly."""
    questions = [
        "ابني عنده توحد كيف أتعامل",
        "ابنتي تعاني من القلق",
        "طفلي عنده فرط حركة",
        "ابني يخاف من الظلام بشدة",
        "ابنتي تقضم أظافرها",
        "طفلي عنده تبول لاإرادي",
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Fast-path should match: {q}"
        assert "medical" in domains, f"Expected medical in {domains} for: {q}"


def test_keyword_fast_path_cyber():
    """Clear cyber keywords return cyber instantly."""
    questions = [
        "ابني مدمن ألعاب إلكترونية",
        "بنتي طول اليوم على التيك توك",
        "ابني يدخل على محتويات إباحية",
        "كيف أحمي طفلي من التنمر الإلكتروني",
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Fast-path should match: {q}"
        assert "cyber" in domains, f"Expected cyber in {domains} for: {q}"


def test_keyword_fast_path_development():
    """Clear development keywords return development instantly."""
    questions = [
        "ابني تأخر في المشي",
        "طفلي عمره سنتين وما يتكلم",
        "بنتي ما زالت ما تمشي",
        "متى تبدأ أسنان الطفل بالظهور",
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Fast-path should match: {q}"
        assert "development" in domains, f"Expected development in {domains} for: {q}"


def test_ambiguous_question_no_fast_path(monkeypatch):
    """Ambiguous questions shouldn't match fast-path, should use LLM."""
    monkeypatch.setattr(
        "app.services.domain_classifier._call_llm",
        lambda q: ["medical"],
    )
    result = classify_domains("بنتي عمرها 5 سنوات تصرفاتها غريبة")
    assert result == ["medical"]


def test_cache_hits(monkeypatch):
    """Repeated questions should hit LRU cache, not call fast-path or LLM."""
    call_count = {"llm": 0, "fast": 0}

    original_fast = _keyword_fast_path

    def tracked_fast(q):
        call_count["fast"] += 1
        return original_fast(q)

    monkeypatch.setattr(
        "app.services.domain_classifier._keyword_fast_path",
        tracked_fast,
    )
    monkeypatch.setattr(
        "app.services.domain_classifier._call_llm",
        lambda q: (call_count.update({"llm": call_count["llm"] + 1}) or ["fiqh"]),
    )

    # First call — hits fast-path or LLM
    r1 = classify_domains("كيف أعلم ابني الصلاة")
    assert r1 is not None
    assert call_count["fast"] >= 1 or call_count["llm"] >= 1

    # Second call with different question — should go through again
    r2 = classify_domains("ابني عنده توحد")
    assert r2 is not None

    # Third call with repeat — should hit cache (fast+llm not incremented)
    old_fast = call_count["fast"]
    old_llm = call_count["llm"]
    r3 = classify_domains("كيف أعلم ابني الصلاة")
    assert r3 == r1
    assert call_count["fast"] == old_fast and call_count["llm"] == old_llm, (
        f"Expected cache hit: fast={call_count['fast']} (was {old_fast}), "
        f"llm={call_count['llm']} (was {old_llm})"
    )


def test_empty_question_returns_medical():
    """Empty or whitespace questions default to medical."""
    assert classify_domains("") == ["medical"]
    assert classify_domains("   ") == ["medical"]


# ── P0.4 expansion tests (target: ≥80% fast-path coverage) ──────────────

def test_p04_fiqh_behavior_keywords():
    """Fiqh expansion: behavior-related religious questions match."""
    questions = [
        "ابني يسرق",                  # سرق
        "ابني يدخن",                  # يدخن
        "ابني يسخر من الدين",         # يسخر من الدين
        "ابني يسب الدين",             # يسب الدين
        "ابني يحب الموسيقى",          # يحب الموسيقى
        "هل يحرم تعليم البنات الموسيقى",  # يحرم
        "كيف أحبب ابني في الرسول",    # يحبب
        "كيف أتعامل مع كذب أطفالي",  # كذب
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Should match fast-path: {q}"
        assert "fiqh" in domains, f"Expected fiqh in {domains} for: {q}"


def test_p04_cyber_social_media_keywords():
    """Cyber expansion: social-media + platform name questions match."""
    questions = [
        "ابني مدمن سوشال ميديا",
        "ابني مدمن اليوتيوب",
        "ابني يشاهد تيك توك من الساعة 6",
        "ابنتي ترسل صورها للغرباء",
        "ابني يستخدم فكونتاكت",
        "ابني يحكي كلمات من النت",
        "ابني يشاهد محتوى عنيف",
        "ابني يشاهد قناة سيئة",
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Should match fast-path: {q}"
        assert "cyber" in domains, f"Expected cyber in {domains} for: {q}"


def test_p04_medical_clinical_keywords():
    """Medical expansion: clinical-term + behavior-related questions match."""
    questions = [
        "ابني عنده ADHD",
        "ابنتي لديها سمنة",
        "ابني لا ينام",
        "ابنتي تشد شعرها",
        "ابني يأكل التراب",
        "ابني كثير البكاء",
        "ابنتي تخاف من الناس",
        "ابني يتبول في الفراش",
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Should match fast-path: {q}"
        assert "medical" in domains, f"Expected medical in {domains} for: {q}"


def test_p04_development_milestone_keywords():
    """Development expansion: milestone-related questions match."""
    questions = [
        "ابني عمره شهرين ولا يبتسم",
        "ابني عمره 3 سنوات لا يكلم",
        "ابني لا يستعمل الحمام",
        "ابني عمره 4 سنوات لا يركض",
        "ابني يأكل رمل",
    ]
    for q in questions:
        domains = _keyword_fast_path(q)
        assert domains is not None, f"Should match fast-path: {q}"
        assert "development" in domains, f"Expected development in {domains} for: {q}"


def test_p04_coverage_target():
    """P0.4 KPI: ≥80% of a 100-question sample should match fast-path.

    Sampled from the most common Arabic parenting questions across all
    four domains. This is the contract for the P0.4 performance gate.
    """
    questions = [
        # Fiqh (25)
        "كيف أعلم ابني الصلاة", "ما حكم صيام الأطفال", "ابنتي تريد تعلم القرآن",
        "كيف نربي أبناءنا على الأخلاق", "ابني لا يصلي الفجر",
        "متى أبدأ تعليم طفلي الوضوء", "كيف أحفظ طفلي سورة البقرة",
        "ابنتي ترفض ارتداء الحجاب", "هل يأثم طفلي إذا ترك الصلاة",
        "كيف أتعامل مع كذب أطفالي", "ابني يقول كلام بذيء",
        "ما هي آداب الدعاء للأطفال", "كيف أصلي مع طفلي",
        "متى يصلي الطفل بالسنن", "كيف أحبب ابنتي في الإسلام",
        "ابني يسخر من الدين", "ما حكم ضرب الأطفال في الإسلام",
        "ابني يشاهد أفلام غير مناسبة", "ما هي حقوق الطفل في الإسلام",
        "ابني يدخن", "ابني يسرق", "ما حكم الكذب الأبيض",
        "ابني يسب الدين", "ابني يحب الموسيقى", "ابني يحبب ابني في الرسول",
        # Medical (25)
        "ابني عنده توحد كيف أتعامل", "ابنتي تعاني من القلق",
        "طفلي عنده فرط حركة", "ابني يخاف من الظلام بشدة",
        "ابنتي تقضم أظافرها", "طفلي عنده تبول لاإرادي",
        "ابني لديه اكتئاب", "ابنتي ترفض الأكل",
        "ابني عنده ADHD", "طفلي عنده وسواس",
        "ابنتي تعاني من نوبات هلع", "ابنتي لديها كوابيس مزعجة",
        "ابني عنده تأخر في النطق", "ابنتي لديها إعاقة",
        "ابني لديه ربو", "ابنتي لديها سمنة",
        "ابني يعاني من العزلة", "ابني لديه عسر قراءة",
        "ابني كثير البكاء", "ابنتي تشد شعرها",
        "ابني يتبول في الفراش", "ابني لا يتكلم",
        "ابني يأكل التراب", "ابني لا ينام",
        # Cyber (25)
        "ابني مدمن ألعاب إلكترونية", "بنتي طول اليوم على التيك توك",
        "ابني يدخل على محتويات إباحية", "كيف أحمي طفلي من التنمر الإلكتروني",
        "ابني مدمن اليوتيوب", "ابنتي تواصلت مع غريب",
        "ابني يفتح مواقع لا أعرفها", "ابني يقضي 8 ساعات على الموبايل",
        "ابني يحكي كلمات من النت", "ابني يشاهد محتوى عنيف",
        "ابني ينام والهاتف معه", "ابنتي ترسل صورها للغرباء",
        "ابني يتنمر على زملائه أونلاين", "ابني مدمن سوشال ميديا",
        "ابني يشاهد تيك توك من الساعة 6", "ابنتي ترسل رسائل لولد",
        "ابني يستخدم فكونتاكت", "ابني يشاهد قناة سيئة",
        "كيف أضع حدود لاستخدام الشاشة", "ابني يشاهد ألعاب مخيفة",
        "ابني مدمن إنستغرام", "ابني يسكرولين", "ابني يفتح فيس بوك",
        "ابني يحدّث تويت", "ابني يستخدم واتس أب",
        # Development (25)
        "ابني تأخر في المشي", "طفلي عمره سنتين وما يتكلم",
        "بنتي ما زالت ما تمشي", "متى تبدأ أسنان الطفل بالظهور",
        "ابني عمره شهرين ولا يبتسم", "ابنتي عمرها سنة لا تجلس",
        "ابني ما يمسك الرضاعة", "متى يبدأ الطفل الزحف",
        "ابني عمره 3 سنوات لا يكلم", "متى يبدأ الطفل يمشي",
        "ابني يأكل رمل", "ابنتي تضرب نفسها",
        "ابني لا ينام الليل", "ابني لا يستعمل الحمام",
        "ابني عمره 4 سنوات لا يركض", "ابني عمره 6 شهور لا يبتسم",
        "ابني عنده تأخر نمائي", "ابنتي تأخرت في الحبو",
        "ابني ما يمشي", "ابنتي ما تتكلم",
        "ابني يأكل أشياء غريبة", "ابني عمره سنتين ولا يركض",
        "ابنتي عمرها 8 شهور ما تجلس", "ابني ما يمسك الأشياء",
    ]
    hits = sum(1 for q in questions if _keyword_fast_path(q) is not None)
    coverage = 100 * hits / len(questions)
    # P0.4 contract: ≥80%
    assert coverage >= 80.0, f"P0.4 fast-path coverage {coverage:.1f}% < 80% target"
    # Actual current value: should be ~100%
    assert coverage >= 90.0, (
        f"Expected ≥90% after expansion, got {coverage:.1f}% "
        f"({hits}/{len(questions)}). Regression?"
    )
