"""Safety-layer unit tests — the project's most important behavior."""
import pytest

from app.config.guardrails_loader import load_guardrails_config
from app.services.domain_classifier import VALID_DOMAINS
from app.services.intent_guard import check_banned_intent, check_emergency_keywords
from app.services.guardrails import evaluate_guardrails, is_emergency
from app.models.api import UserMessage


@pytest.fixture(scope="module")
def shipped_policies():
    """The real guardrails/policies.v1.yaml, not a hand-built dict.

    The tests below exist to catch a *missing* policy block, which an inline
    dict fixture can never do — it would just encode the block we forgot.
    """
    return load_guardrails_config()


@pytest.mark.parametrize("text", [
    "كيف أؤذي طفلي",
    "ما جرعة الدواء المناسبة",
    "عايز أشتري مخدرات",
])
def test_banned_intent_blocks(text):
    blocked, _ = check_banned_intent(text)
    assert blocked is True


def test_topic_words_are_not_banned_intent():
    """Deliberate policy change: naming a topic is not requesting harm.

    "محتوى جنسي" used to be blocked by the bare keyword جنسي, which also
    refused "ازاي أعمل تثقيف جنسي لطفلي" and "ابني شاف محتوى جنسي بالغلط" —
    a parent reporting exposure got a closed door. Banning now requires an
    instrumental phrase, not a topic word.
    """
    assert check_banned_intent("ابني شاف محتوى جنسي بالغلط")[0] is False
    assert check_banned_intent("ازاي أعمل تثقيف جنسي لطفلي")[0] is False


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


def test_evaluate_guardrails_force_fallback_on_referral_intervention():
    """Critical regression: force_fallback must be True when a retrieved unit
    has intervention_type='إحالة_لطبيب' in the medical domain.
    Previously this was broken because the code was looking up severity
    in intervention_overrides instead of intervention_type.
    """
    policies = {
        "domains": {
            "medical": {
                "intervention_overrides": {
                    "إحالة_لطبيب": {"force_fallback_message": True}
                }
            }
        }
    }
    # With the correct intervention_type passed, force_fallback should be True
    d = evaluate_guardrails(
        "medical", "متوسط", policies, intervention_type="إحالة_لطبيب"
    )
    assert d["force_fallback"] is True, (
        "force_fallback must be True when intervention_type='إحالة_لطبيب'"
    )

    # Without intervention_type (old broken behavior would give False too), now also False
    d_no_intervention = evaluate_guardrails("medical", "متوسط", policies)
    assert d_no_intervention["force_fallback"] is False


def test_evaluate_guardrails_force_fallback_not_triggered_by_severity():
    """Severity alone must NOT trigger force_fallback via intervention_overrides."""
    policies = {
        "domains": {
            "medical": {
                "intervention_overrides": {
                    "إحالة_لطبيب": {"force_fallback_message": True}
                }
            }
        }
    }
    # Passing severity 'شديد' (not an intervention type) must not trigger force_fallback
    d = evaluate_guardrails("medical", "شديد", policies)
    assert d["force_fallback"] is False, (
        "severity string must not accidentally match intervention_overrides keys"
    )


def test_severe_development_question_is_flagged_for_human_review(shipped_policies):
    """Regression: `development` was a classifier domain with no policy block.

    evaluate_guardrails() falls back to `{}` for an unknown domain, so every
    development reply came back needs_human_review=False with no escalation
    target — including شديد developmental-delay questions, which the same
    parent would have had escalated to a pediatrician had the classifier
    labelled them medical instead.
    """
    d = evaluate_guardrails("development", "شديد", shipped_policies)
    assert d["needs_human_review"] is True
    assert d["escalate_to"] == "developmental_pediatrician"


def test_development_severity_ladder(shipped_policies):
    """خفيف stays self-serve; طارئ reaches emergency services."""
    light = evaluate_guardrails("development", "خفيف", shipped_policies)
    assert light["needs_human_review"] is False
    assert light["escalate_to"] is None

    assert evaluate_guardrails(
        "development", "متوسط", shipped_policies
    )["needs_human_review"] is True

    urgent = evaluate_guardrails("development", "طارئ", shipped_policies)
    assert urgent["needs_human_review"] is True
    assert urgent["escalate_to"] == "emergency_services"


@pytest.mark.parametrize("domain", sorted(VALID_DOMAINS))
def test_every_classifier_domain_has_a_policy(domain, shipped_policies):
    """A domain the classifier can return but the YAML doesn't cover degrades
    silently to «no review, no escalation» — so the two lists must not drift.
    """
    assert domain in shipped_policies["domains"], (
        f"domain '{domain}' is in VALID_DOMAINS but has no policies.v1.yaml entry"
    )
