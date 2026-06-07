"""
LLM service — calls Ollama to generate a final response from retrieved knowledge.
Follows strict rules: no diagnosis, no fatwa, no invented info.
"""
import logging
import asyncio

import requests

from app.config.llm_config import LLM
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

    # Build conversation context if history exists
    history_block = ""
    if conversation_history:
        history_parts = []
        for turn in conversation_history[-6:]:  # keep last 6 turns to avoid context overflow
            role_ar = "الوالد" if turn.role == "user" else "المساعد"
            history_parts.append(f"[{role_ar}]: {turn.content[:200]}")
        history_block = "\n".join(history_parts) + "\n\n"

    user_prompt = (
        f"[CONTEXT]\n"
        f"{joined}\n\n"
        f"[REFERENCE_INFO]\n{source_line}\n\n"
    )
    if history_block:
        user_prompt += f"[محادثة_سابقة]\n{history_block}"
    user_prompt += (
        f"[سؤال الوالد/الوالدة]\n"
        f"{question_display}\n"
        f"الفئة العمرية: {age_group}\n"
        f"شدة الحالة: {severity}\n\n"
        f"تعليمات الرد:\n"
        f"- اقرأ [CONTEXT] جيداً ثم أجب بناءً عليه فقط.\n"
        f"- الرد 3-5 جمل، بالعربية الفصحى الميسرة.\n"
        f"- لا تكرر أفكاراً.\n"
        f"- اختم بـ: 📚 المصدر: {source_line}\n"
        f"- إن كان السياق غير كافٍ: لا تتوفر لديّ معلومات موثقة — يُنصح بمراجعة متخصص\n"
    )

    return user_prompt, source_line


def _compose_system_prompt(domain: str) -> str:
    base = "أنت مساعد تربوي ذكي للأهل العرب المسلمين. تقدم إجابات عملية وآمنة بدون تشخيص طبي ملزم أو فتوى شخصية."
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
) -> str:
    """Call Ollama /api/generate. Returns generated text or raises on failure."""

    user_prompt, source_line = _build_prompt(
        domain, behavior_type, age_group, severity, retrieved_units, question_text, conversation_history
    )

    payload = {
        "model": LLM.model,
        "prompt": _compose_system_prompt(domain) + "\n\n" + user_prompt,
        "stream": False,
    }

    url = f"{LLM.base_url}/api/generate"

    last_error = None
    for attempt in range(1, LLM.max_retries + 1):
        try:
            resp = await asyncio.to_thread(
                requests.post, url, json=payload, timeout=LLM.request_timeout
            )
            resp.raise_for_status()
            data = resp.json()
            content: str = data.get("response", "")
            return content.strip()
        except requests.RequestException as e:
            last_error = e
            logger.warning("Ollama attempt %d/%d failed: %s", attempt, LLM.max_retries, e)
        except Exception as e:
            last_error = e
            logger.warning("Ollama attempt %d/%d unexpected: %s", attempt, LLM.max_retries, e)

    raise RuntimeError(
        f"LLM call failed after {LLM.max_retries} attempts: {last_error}"
    ) from last_error
