"""
Guardrails service — applies domain/severity policies to a draft reply.
Reads policies.v1.yaml dynamically on every request via the policies dict
passed from app.state.guardrails_config.
"""
import re

from app.models.api import UserMessage, AssistantReply


# ----- Emergency / severity constants -----

EMERGENCY_SEVERITY = "طارئ"
EMERGENCY_ESCALATE = "emergency_services"


def _build_fallback_message(
    domain: str,
    behavior_type: str,
    age_group: str,
    policies: dict,
    is_emergency_case: bool = False,
) -> str:
    """Return the high-risk or emergency fallback message from policies or a safe default."""
    if is_emergency_case:
        fallback = (
            policies.get("global", {})
            .get("emergency_fallback_message", "")
        )
        if fallback:
            return fallback.strip()

    fallback = (
        policies.get("global", {})
        .get("high_risk_fallback_message", "")
    )
    if fallback:
        return fallback.strip()

    # Absolute last-resort fallback
    if is_emergency_case:
        return (
            "هذا المساعد لا يقدّم تشخيصًا طبيًا أو تدخلاً في الأزمات الطارئة. "
            "يُرجى التوجه فورًا لأقرب قسم طوارئ أو الاتصال بالإسعاف في بلدك "
            "(مصر: 123 / 16000، السعودية: 997 / 911 / 116111، أو 112)."
        )

    return (
        f"نظرًا لخطورة الحالة ({behavior_type}، {age_group})، "
        f"نوصي بشدة بالتواصل الفوري مع مختص في مجال {domain}. "
        "هذا المساعد لا يقدم تشخيصًا طبيًا ولا فتوى ملزمة."
    )


# A "medical no-match" is only a medical question when the words say so: the
# classifier's `medical` domain is also the catch-all for a child's behaviour
# and feelings (jealousy, fear of the dark, sleep, lying), and those must keep
# the gentle off-topic pivot rather than an alarming "no diagnosis / no doses"
# referral. Matched on text normalised by _norm_ar (diacritics and tatweel
# gone, alef forms folded, ى -> ي), so the Arabic patterns are written with a
# bare alef. No bare «أعراض»: it is just as common in «أعراض إدمان الشاشات»
# (cyber) and no bare "symptoms" for the same reason.
_ARABIC_MARKS = re.compile("[\u064b-\u065f\u0670\u0640]")
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"})


def _norm_ar(text: str) -> str:
    return _ARABIC_MARKS.sub("", text or "").translate(_ARABIC_FOLD)


# Arabic has no usable \b for a prefixed word (الربو, وبالدوا), so the short
# or ambiguous stems get an explicit "not inside a longer word" guard instead:
# ربو must not fire on الربوبية (aqeedah), nor صرع on مصرع, nor قرص on قرصان.
_W_START = r"(?<![\u0621-\u064a])(?:ال|لل|بال|وال|فال|كال)?"
_W_END = r"(?![\u0621-\u064a])"

_MEDICAL_QUERY_RE = re.compile(
    r"جرع[هة]|جرعات|ادوي[هة]|دواء|ادويت|"
    + _W_START + r"(?:دوا|قرص|اقراص|ربو|صرع|سكري|سكر\s*الدم)" + _W_END
    + r"|انسولين|مضاد(?:ات)?\s*حيو|كورتيزون|ريتالين|بنادول|باراسيتامول|بروفين"
    r"|مسكن|منوم|ميلاتونين|حقن[هة]|تحاميل|بخاخ|فيتامين|مكملات|مكمل\s*غذائ"
    r"|تطعيم|لقاح|تشخيص|[تين]شخ\w*ص"
    r"|حرارة\s*(?:عالي|مرتفع)|حرارته|حرارتها|سخون[هة]|سخن[هة]|سخنان"
    r"|تشنج|اغماء|قيء|قيئ|استفراغ|اسهال|طفح|ضغط\s*الدم"
    r"|\b(?:doses?|dosage|dosing|medic(?:ation|ine)s?|drugs?|pills?|tablets?"
    r"|insulin|antibiotics?|ibuprofen|paracetamol|acetaminophen|tylenol|calpol"
    r"|melatonin|ritalin|prescri\w+|diagnos\w+|fever|seizures?|vaccin\w+"
    r"|supplements?)\b",
    re.I,
)

# Something that cannot wait for a pharmacist: overdose / wrong medicine /
# swallowed pills or chemicals / a seizure / not responding / not breathing.
_URGENT_QUERY_RE = re.compile(
    r"ابتلا?ع\w*|" + r"(?<![\u0621-\u064a])(?:بيبلع|ببلع|يبلع|بلع)\w{0,3}" + _W_END
    + r"|جرع[هة]\s*(?:زياد|زايد|قاتل)|القاتل[هة]|جرع[هة]\s*زايدة"
    r"|ا[خذ][ذد]\w*.{0,15}(?:زياد|زايد|غلط)|شرب\w*.{0,15}(?:زياد|زايد|غلط)"
    r"|تسمم|تشنج|اغماء|مش\s*بيرد|مبيرد|مش\s*بيستجيب|مش\s*بيفوق|فاقد\w*\s*الوعي"
    r"|مش\s*بيتنفس|مش\s*قادر\s*يتنفس|صعوب[هة]\s*(?:في\s*)?(?:ال)?تنفس|زرقان|ازرق"
    r"|\b(?:overdos\w*|swallow\w*|seizures?|convuls\w*|unresponsive|unconscious"
    r"|not\s+breathing|can'?t\s+breathe|stopped\s+breathing|poison\w*"
    r"|wrong\s+(?:medicine|medication|dose|drug)"
    r"|too\s+much\s+(?:medicine|medication|insulin)"
    r"|(?:gave|took|given)\b.{0,20}\b(?:double|too\s+much))\b",
    re.I,
)


def is_medical_query(text: str | None) -> bool:
    """True when the wording is a real health question (a medicine, a dose, a
    vaccine, a diagnosis, a clear medical symptom), not a behaviour question
    that merely landed in the `medical` domain."""
    return bool(_MEDICAL_QUERY_RE.search(_norm_ar(text or "")))


def is_urgent_medical_query(text: str | None) -> bool:
    """True for wording that describes a possible emergency right now."""
    return bool(_URGENT_QUERY_RE.search(_norm_ar(text or "")))


_MEDICAL_REFERRAL_EN = (
    "I can't answer this from the app's knowledge base, and I don't give "
    "medical diagnoses or advise on doses or medication. Please check with "
    "your child's doctor or pharmacist. If your child seems seriously unwell "
    "right now (a seizure, trouble breathing, unresponsive, swallowed "
    "medicine), call your local emergency number immediately."
)

# Appended to the Arabic referral (the English text carries its own).
_URGENCY_LINE_AR = (
    "إذا ظهرت على طفلك أعراض شديدة الآن (تشنج، إغماء، صعوبة تنفس، ابتلاع دواء) "
    "فاتصل بالإسعاف فورًا."
)

_MEDICAL_EMERGENCY_EN = (
    "This could be an emergency. Call your local emergency number now "
    "(Egypt: 123, Saudi Arabia: 997 or 911, anywhere: 112 or 911) or go to the "
    "nearest emergency department right away. This assistant can't give medical "
    "diagnoses or advise on doses or medication."
)


def medical_referral_text(
    policies: dict,
    lang: str | None = "ar",
    behavior_type: str = "",
    age_group: str = "",
) -> str:
    """The reply for a medical question the knowledge base cannot answer.

    Arabic is the policies' own high-risk fallback message (a human specialist,
    no diagnosis), via the same builder the forced-fallback path uses, so the
    wording is edited in one place, followed by one short urgency line. Other
    languages get an English text of the same meaning (the Arabic one would be
    unreadable to them) that already carries its urgency sentence.
    """
    if lang and lang != "ar":
        return _MEDICAL_REFERRAL_EN
    base = _build_fallback_message("medical", behavior_type, age_group, policies)
    return f"{base}\n\n{_URGENCY_LINE_AR}"


def medical_referral_reply(
    user_message: UserMessage,
    policies: dict,
    lang: str | None,
    query_text: str,
) -> AssistantReply:
    """The reply to a medical question the knowledge base has no answer to.

    An urgent one (overdose, swallowed medicine, seizure, unresponsive...)
    gets the emergency fallback (emergency numbers, escalation to emergency
    services) instead of a "ask your doctor" referral that a parent in a
    crisis would read as "nothing to do right now". Anything else gets the
    referral text through the normal guardrails, so a severity override
    (شديد -> pediatrician) still applies.
    """
    if is_urgent_medical_query(query_text):
        reply = emergency_reply(user_message, policies)
        if lang and lang != "ar":
            reply.reply_text = _MEDICAL_EMERGENCY_EN
        return reply
    return apply_guardrails(
        user_message,
        medical_referral_text(
            policies, lang, user_message.behavior_type or "",
            user_message.age_group or ""),
        policies, mode="retrieval_only",
    )


def is_emergency(user_message: UserMessage) -> bool:
    """Check if the severity signals an emergency requiring immediate fallback."""
    return user_message.severity == EMERGENCY_SEVERITY


def emergency_reply(user_message: UserMessage, policies: dict) -> AssistantReply:
    """Build an immediate fallback reply for emergency cases — no LLM, no retrieval."""
    domain = user_message.domain or "general"
    return AssistantReply(
        reply_text=_build_fallback_message(
            domain,
            user_message.behavior_type,
            user_message.age_group,
            policies,
            is_emergency_case=True,
        ),
        domain=domain,
        severity=user_message.severity,
        needs_human_review=True,
        escalation_target=EMERGENCY_ESCALATE,
        mode="retrieval_only",
    )


def evaluate_guardrails(
    domain: str,
    severity: str,
    policies: dict,
    intervention_type: str | None = None,
) -> dict:
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
    force_fallback = False
    
    # Bug Fix: Look up force_fallback_message using intervention_type if provided
    lookup_key = intervention_type if intervention_type else severity
    if lookup_key in intervention_overrides:
        force_fallback = bool(
            intervention_overrides[lookup_key].get("force_fallback_message", False)
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
    intervention_type: str | None = None,
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

    decision = evaluate_guardrails(domain, severity, policies, intervention_type)
    if decision["force_fallback"]:
        draft_reply = _build_fallback_message(
            domain,
            user_message.behavior_type,
            user_message.age_group,
            policies,
            is_emergency_case=(decision.get("escalate_to") == EMERGENCY_ESCALATE),
        )

    return AssistantReply(
        reply_text=draft_reply,
        domain=domain,
        severity=severity,
        needs_human_review=decision["needs_human_review"],
        escalation_target=decision["escalate_to"],
        mode=mode,
    )
