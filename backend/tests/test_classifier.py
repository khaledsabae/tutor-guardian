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
