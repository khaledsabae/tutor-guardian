"""
Guardrails service — applies domain/severity policies to a draft reply.
Reads policies.v1.yaml dynamically on every request via the policies dict
passed from app.state.guardrails_config.
"""
from app.models.api import UserMessage, AssistantReply


# ----- Emergency / severity constants -----

EMERGENCY_SEVERITY = "طارئ"
EMERGENCY_ESCALATE = "emergency_services"


def _build_fallback_message(
    domain: str,
    behavior_type: str,
    age_group: str,
    policies: dict,
) -> str:
    """Return the high-risk fallback message from policies or a safe default."""
    fallback = (
        policies.get("global", {})
        .get("high_risk_fallback_message", "")
    )
    if fallback:
        return fallback

    # Absolute last-resort fallback
    return (
        f"نظرًا لخطورة الحالة ({behavior_type}، {age_group})، "
        f"نوصي بشدة بالتواصل الفوري مع مختص في مجال {domain}. "
        "هذا المساعد لا يقدم تشخيصًا طبيًا ولا فتوى ملزمة."
    )


def is_emergency(user_message: UserMessage) -> bool:
    """Check if the severity signals an emergency requiring immediate fallback."""
    return user_message.severity == EMERGENCY_SEVERITY


def emergency_reply(user_message: UserMessage, policies: dict) -> AssistantReply:
    """Build an immediate fallback reply for emergency cases — no LLM, no retrieval."""
    return AssistantReply(
        reply_text=_build_fallback_message(
            user_message.domain,
            user_message.behavior_type,
            user_message.age_group,
            policies,
        ),
        domain=user_message.domain,
        severity=user_message.severity,
        needs_human_review=True,
        escalation_target=EMERGENCY_ESCALATE,
        mode="retrieval_only",
    )


def evaluate_guardrails(domain: str, severity: str, policies: dict) -> dict:
    """Compute the guardrail decision for a (domain, severity) pair WITHOUT a
    draft text. Lets the streaming endpoint decide — before sending any token —
    whether it must force a fallback (which would replace the whole reply).

    Returns: {needs_human_review: bool, escalate_to: str|None, force_fallback: bool}
    """
    domain_policies = policies.get("domains", {}).get(domain, {})
    default_policy = domain_policies.get("default_policy", {})

    severity_overrides = domain_policies.get("severity_overrides", {})
    if severity in severity_overrides:
        needs_human_review = severity_overrides[severity].get(
            "require_human_review",
            default_policy.get("require_human_review", False),
        )
        escalate_to = severity_overrides[severity].get("escalate_to")
    else:
        needs_human_review = default_policy.get("require_human_review", False)
        escalate_to = None

    intervention_overrides = domain_policies.get("intervention_overrides", {})
    force_fallback = bool(
        intervention_overrides.get(severity, {}).get("force_fallback_message")
    )

    return {
        "needs_human_review": needs_human_review,
        "escalate_to": escalate_to,
        "force_fallback": force_fallback,
    }


def apply_guardrails(
    user_message: UserMessage,
    draft_reply: str,
    policies: dict,
    mode: str = "retrieval_only",
) -> AssistantReply:
    """
    Apply domain-specific guardrails policy to a draft assistant reply.

    Reads policies.v1.yaml (via the policies dict) every time — not cached.
    Handles severity overrides, intervention overrides, and emergency fallback.
    """
    domain = user_message.domain
    severity = user_message.severity

    # ---------- Handle emergency severity immediately ----------
    if severity == EMERGENCY_SEVERITY:
        return emergency_reply(user_message, policies)

    decision = evaluate_guardrails(domain, severity, policies)
    if decision["force_fallback"]:
        draft_reply = _build_fallback_message(
            domain, user_message.behavior_type, user_message.age_group, policies
        )

    return AssistantReply(
        reply_text=draft_reply,
        domain=domain,
        severity=severity,
        needs_human_review=decision["needs_human_review"],
        escalation_target=decision["escalate_to"],
        mode=mode,
    )
