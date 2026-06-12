"""
LLM service — calls Ollama to generate a final response from retrieved knowledge.
Follows strict rules: no diagnosis, no fatwa, no invented info.
"""
import logging

from app.services.ai_gateway import get_gateway
from app.models.api import ConversationTurn

logger = logging.getLogger(__name__)


_DOMAIN_LABELS = {
    "fiqh": "🕌 شرعي/تربوي",
    "tarbiyah": "🕌 تربوي",
    "islamic_parenting": "🕌 تربية إسلامية",
    "medical": "🧠 نفسي/طبي",
    "cyber": "💻 رقمي/سيبراني",
    "development": "📈 تطور الطفل",
}

# Length guidance by severity — replaces the old rigid «4-6 جمل» cap.
_LENGTH_BY_SEVERITY = {
    "خفيف": "أوجز — حوالي ٤ إلى ٦ جمل.",
    "متوسط": "أجب بتفصيل عملي — حوالي ٨ إلى ١٢ جملة.",
    "شديد": "أجب بتفصيل، واذكر بوضوح متى تلزم مراجعة المتخصص.",
}

# The local 3B model degrades with long instruction lists — variants:
#   rich    → cloud quality tier (structured template + per-point citations)
#   compact → local models (same template, ⅓ the instructions)
#   legacy  → the pre-Phase-3 instruction block (revert knob)
import os as _os

PROMPT_VARIANT_LOCAL = _os.environ.get("PROMPT_VARIANT_LOCAL", "compact")


def _build_prompt(
    domain: str,
    behavior_type: str,
    age_group: str,
    severity: str,
    retrieved_units: list[dict],
    question_text: str = "",
    conversation_history: list[ConversationTurn] | None = None,
    variant: str = "compact",
) -> tuple[str, str]:
    """Construct the generation prompt. Returns (user_prompt, source_line)."""

    parts: list[str] = []
    sources: list[str] = []
    for n, unit in enumerate(retrieved_units, 1):
        doc = unit.get("document", "") or unit.get("metadata", {}).get("text_simplified", "")
        doc = doc.removeprefix("passage: ")
        ref = unit.get("metadata", {}).get("reference_info", "مصدر غير مذكور")
        src_domain = unit.get("source_domain") or unit.get("metadata", {}).get("domain", domain)
        domain_label = _DOMAIN_LABELS.get(src_domain, src_domain)
        parts.append(f"【{n}】 ({domain_label}) {doc}\nالمرجع: {ref}")
        if ref and ref not in sources:
            sources.append(ref)

    joined = "\n---\n".join(parts)
    source_line = " · ".join(sources[:4]) if sources else "مصدر غير مذكور"
    question_display = (question_text.strip() if question_text else "") or \
        (behavior_type.strip() if behavior_type else "") or "سؤال تربوي"
    length_rule = _LENGTH_BY_SEVERITY.get(severity, _LENGTH_BY_SEVERITY["خفيف"])

    # Conversation history block (reference only)
    history_block = ""
    if conversation_history:
        history_parts = []
        for turn in conversation_history[-6:]:  # cap context size
            role_ar = "الوالد" if turn.role == "user" else "المساعد"
            history_parts.append(f"[{role_ar}]: {turn.content[:200]}")
        history_block = "\n".join(history_parts) + "\n\n"

    user_prompt = (
        f"[سؤال الوالد/الوالدة الحالي — أجب على هذا فقط]\n"
        f"{question_display}\n"
        f"الفئة العمرية: {age_group} | شدة الحالة: {severity}\n\n"
        f"[مصادر ومعلومات موثقة — مرقّمة]\n"
        f"{joined}\n\n"
    )
    if history_block:
        user_prompt += (
            f"[سياق المحادثة — للمرجعية فقط، لا تعد الإجابة عن أسئلة سابقة]\n"
            f"{history_block}"
        )

    if variant == "rich":
        user_prompt += (
            f"تعليمات الرد (التزم بها كلها):\n"
            f"1. ابدأ بالجواب المباشر على السؤال في جملة أو جملتين.\n"
            f"2. ثم خطوات عملية مرقّمة يستطيع الوالد تنفيذها فعلاً.\n"
            f"3. اجمع بين المصادر المرقّمة عند الحاجة، وانسب كل نقطة مهمة "
            f"لمصدرها بالرقم 【n】.\n"
            f"4. إن كان للموضوع جانب صحي أو شرعي دقيق، أضف فقرة قصيرة "
            f"بعنوان «متى تراجع متخصصاً».\n"
            f"5. {length_rule}\n"
            f"6. لا تذكر أي حكم أو رقم أو دواء أو معلومة غير واردة في "
            f"المصادر أعلاه. إن لم تكفِ المصادر للإجابة قل ذلك صراحة: "
            f"«لا تتوفر لديّ معلومات موثقة حول هذا — يُنصح بمراجعة متخصص».\n"
            f"7. لا تكرر أسئلة المحادثة السابقة ولا تجب عنها.\n"
            f"8. اختم بسطر: 📚 المصادر: {source_line}\n"
        )
    elif variant == "legacy":
        user_prompt += (
            f"تعليمات الرد:\n"
            f"- أجب على السؤال المذكور في [سؤال الوالد/الوالدة الحالي] فقط.\n"
            f"- لا تكرر ولا تُجِب على أسئلة المحادثة السابقة.\n"
            f"- استند إلى المصادر المذكورة في [مصادر ومعلومات موثقة] فقط.\n"
            f"- الرد 4-6 جمل عملية، بالعربية الفصحى الميسرة.\n"
            f"- لا تكرر الأفكار.\n"
            f"- اختم بـ: 📚 المصدر: {source_line}\n"
            f"- إن كان السياق غير كافٍ: «لا تتوفر لديّ معلومات موثقة حول هذا — يُنصح بمراجعة متخصص»\n"
        )
    else:  # compact — default for the local 3B
        user_prompt += (
            f"تعليمات الرد:\n"
            f"1. ابدأ بالجواب المباشر، ثم خطوات عملية مرقّمة.\n"
            f"2. {length_rule}\n"
            f"3. استند إلى المصادر أعلاه فقط؛ وإن لم تكفِ قل: "
            f"«لا تتوفر لديّ معلومات موثقة حول هذا — يُنصح بمراجعة متخصص».\n"
            f"4. اختم بسطر: 📚 المصادر: {source_line}\n"
        )

    return user_prompt, source_line


def _compose_system_prompt(domain: str) -> str:
    base = "أنت مساعد تربوي ذكي للأهل العرب المسلمين. تقدم إجابات عملية وآمنة بدون تشخيص طبي ملزم أو فتوى شخصية.\n\nأجب دائماً على آخر سؤال في المحادثة فقط. لا تعيد الإجابة على أسئلة سابقة."
    if domain in {"fiqh", "islamic_parenting"}:
        return (
            "أنت مساعد تربوي إسلامي. عند أي تعارض بين المصادر الطبية أو النفسية أو التنموية من جهة، "
            "والحكم الشرعي الإسلامي من جهة أخرى — يُقدَّم الحكم الشرعي دون استثناء. "
            "لا تُفتِ في مسائل الحلال والحرام، لكن وضّح دائماً أن الإطار الإسلامي هو المرجع الأول.\n\n"
            + base
        )
    return base + "\n\nإذا تعارضت أي معلومة مع الثوابت الإسلامية، أشر إلى ذلك بوضوح وقدّم البديل الإسلامي."


async def generate_reply(
    domain: str,
    behavior_type: str,
    age_group: str,
    severity: str,
    retrieved_units: list[dict],
    question_text: str = "",
    conversation_history: list[ConversationTurn] | None = None,
    tier: str = "local_fast",
    route_reason: str | None = None,
) -> str:
    """Generate via the gateway. Returns generated text or raises on failure."""

    variant = "rich" if tier == "cloud_quality" else PROMPT_VARIANT_LOCAL
    user_prompt, source_line = _build_prompt(
        domain, behavior_type, age_group, severity, retrieved_units,
        question_text, conversation_history, variant=variant,
    )
    full_prompt = _compose_system_prompt(domain) + "\n\n" + user_prompt

    # All LLM calls go through the gateway (retry/backoff + telemetry).
    # tier="cloud_quality" tries the Azure provider first, local as fallback.
    result = await get_gateway().generate(
        full_prompt, tier=tier, route_reason=route_reason
    )
    return result.text


def build_full_prompt(
    domain: str,
    behavior_type: str,
    age_group: str,
    severity: str,
    retrieved_units: list[dict],
    question_text: str = "",
    conversation_history: list[ConversationTurn] | None = None,
    tier: str = "local_fast",
) -> tuple[str, str]:
    """Expose the composed (system + user) prompt and source line for streaming.

    The streaming endpoint needs the same prompt this function builds but must
    drive the gateway's stream() itself, so it can't reuse generate_reply().
    """
    variant = "rich" if tier == "cloud_quality" else PROMPT_VARIANT_LOCAL
    user_prompt, source_line = _build_prompt(
        domain, behavior_type, age_group, severity, retrieved_units,
        question_text, conversation_history, variant=variant,
    )
    return _compose_system_prompt(domain) + "\n\n" + user_prompt, source_line
