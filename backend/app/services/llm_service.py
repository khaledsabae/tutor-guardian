"""
LLM service — calls Ollama to generate a final response from retrieved knowledge.
Follows strict rules: no diagnosis, no fatwa, no invented info.
"""
import logging

from app.services.ai_gateway import get_gateway
from app.models.api import ConversationTurn

logger = logging.getLogger(__name__)


def _build_prompt(
    domain: str,
    behavior_type: str,
    age_group: str,
    severity: str,
    retrieved_units: list[dict],
    question_text: str = "",
    conversation_history: list[ConversationTurn] | None = None,
) -> tuple[str, str]:
    """Construct a strict prompt. Returns (user_prompt, source_line)."""

    parts: list[str] = []
    sources: list[str] = []
    domain_labels = {
        "fiqh": "🕌 شرعي/تربوي",
        "tarbiyah": "🕌 تربوي",
        "islamic_parenting": "🕌 تربية إسلامية",
        "medical": "🧠 نفسي/طبي",
        "cyber": "💻 رقمي/سيبراني",
        "development": "📈 تطور الطفل",
    }

    for unit in retrieved_units:
        doc = unit.get("document", "") or unit.get("metadata", {}).get("text_simplified", "")
        ref = unit.get("metadata", {}).get("reference_info", "مصدر غير مذكور")
        src_domain = unit.get("source_domain", domain)
        domain_label = domain_labels.get(src_domain, src_domain)
        parts.append(f"[{domain_label}]\n{doc}")
        if ref and ref not in sources:
            sources.append(ref)

    joined = "\n---\n".join(parts)
    source_line = " · ".join(sources[:3]) if sources else "مصدر غير مذكور"
    question_display = (question_text.strip() if question_text else "") or (behavior_type.strip() if behavior_type else "") or "سؤال تربوي"

    # Build conversation history block (reference only)
    history_block = ""
    if conversation_history:
        history_parts = []
        for turn in conversation_history[-6:]:  # keep last 6 turns to avoid context overflow
            role_ar = "الوالد" if turn.role == "user" else "المساعد"
            history_parts.append(f"[{role_ar}]: {turn.content[:200]}")
        history_block = "\n".join(history_parts) + "\n\n"

    user_prompt = (
        f"[سؤال الوالد/الوالدة الحالي — أجب على هذا فقط]\n"
        f"{question_display}\n"
        f"الفئة العمرية: {age_group} | شدة الحالة: {severity}\n\n"
        f"[مصادر ومعلومات موثقة]\n"
        f"{joined}\n\n"
        f"[REFERENCE_INFO]\n{source_line}\n\n"
    )
    if history_block:
        user_prompt += f"[سياق المحادثة — للمرجعية فقط، لا تعد الإجابة عن أسئلة سابقة]\n{history_block}"
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

    user_prompt, source_line = _build_prompt(
        domain, behavior_type, age_group, severity, retrieved_units, question_text, conversation_history
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
) -> tuple[str, str]:
    """Expose the composed (system + user) prompt and source line for streaming.

    The streaming endpoint needs the same prompt this function builds but must
    drive the gateway's stream() itself, so it can't reuse generate_reply().
    """
    user_prompt, source_line = _build_prompt(
        domain, behavior_type, age_group, severity, retrieved_units, question_text, conversation_history
    )
    return _compose_system_prompt(domain) + "\n\n" + user_prompt, source_line
