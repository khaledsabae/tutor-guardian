"""Safety-layer unit tests — the project's most important behavior."""
import pytest

from app.services.intent_guard import check_banned_intent, check_emergency_keywords
from app.services.guardrails import evaluate_guardrails, is_emergency
from app.models.api import UserMessage


@pytest.mark.parametrize("text", [
    "كيف أؤذي طفلي",
    "ما جرعة الدواء المناسبة",
    "محتوى جنسي",
])
def test_banned_intent_blocks(text):
    blocked, _ = check_banned_intent(text)
    assert blocked is True


def test_banned_intent_allows_normal_question():
    blocked, _ = check_banned_intent("ابني يغضب كثيراً، كيف أتعامل معه؟")
    assert blocked is False


@pytest.mark.parametrize("text", ["طفلي يضرب رأسه", "ابني فقد الوعي", "حدث تشنج"])
def test_emergency_keywords_detected(text):
    assert check_emergency_keywords(text) is True


def test_emergency_keywords_absent():
    assert check_emergency_keywords("ابني خجول في المدرسة") is False


def test_is_emergency_on_severity():
    assert is_emergency(UserMessage(age_group="7-9", severity="طارئ")) is True
    assert is_emergency(UserMessage(age_group="7-9", severity="خفيف")) is False


def test_evaluate_guardrails_force_fallback_shape():
    """evaluate_guardrails always returns the decision keys."""
    decision = evaluate_guardrails("medical", "متوسط", policies={})
    assert set(decision) == {"needs_human_review", "escalate_to", "force_fallback"}
    assert decision["force_fallback"] is False  # empty policies → no override


def test_evaluate_guardrails_reads_policy():
    policies = {
        "domains": {
            "medical": {
                "severity_overrides": {
                    "شديد": {"require_human_review": True, "escalate_to": "pediatrician"}
                }
            }
        }
    }
    d = evaluate_guardrails("medical", "شديد", policies)
    assert d["needs_human_review"] is True
    assert d["escalate_to"] == "pediatrician"
