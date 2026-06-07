"""
Assistant router — Multi-domain ChromaDB retrieval + guardrails + LLM.
Flow: banned check → emergency check → classify_domains → multi_retrieval → LLM → guardrails.
"""
import logging

from fastapi import APIRouter, Request

from app.models.api import ConversationTurn, UserMessage, AssistantReply
from app.services.guardrails import apply_guardrails, is_emergency, emergency_reply
from app.services.retrieval import retrieve_multi_domain, _ensure_index
from app.services.llm_service import generate_reply
from app.services.session_logger import log_session
from app.services.intent_guard import check_banned_intent, check_emergency_keywords
from app.services.domain_classifier import classify_domains

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/draft", response_model=AssistantReply)
async def draft_reply(request: Request, user_message: UserMessage):
    policies = request.app.state.guardrails_config

    # ── Step 0: Banned intent check ──────────────────────────────────
    query_input = user_message.message_text or user_message.behavior_type or ""
    is_banned, matched = check_banned_intent(query_input)
    if is_banned:
        logger.warning("Banned intent detected: %s", matched)
        return AssistantReply(
            reply_text="هذا الموضوع خارج نطاق ما يمكنني مساعدتك فيه. إذا كنت في حالة طارئة، يرجى التواصل مع الجهات المختصة فوراً.",
            domain="medical",
            severity="طارئ",
            needs_human_review=True,
            escalation_target="emergency_services",
            mode="banned",
        )

    # ── Step 0b: Emergency keyword check ─────────────────────────────
    if check_emergency_keywords(query_input):
        logger.info("Emergency keyword detected in message_text")
        user_message = user_message.model_copy(update={"severity": "طارئ"})

    # ── Step 1: Emergency severity check ─────────────────────────────
    if is_emergency(user_message):
        logger.info("Emergency severity — returning fallback immediately")
        return emergency_reply(user_message, policies)

    # ── Step 2: Build query text ──────────────────────────────────────
    query_text = (user_message.message_text or "").strip()
    if not query_text:
        query_text = f"{user_message.behavior_type} {user_message.age_group}"

    # ── Step 3: Auto-detect domains (من السؤال + history إن وجدت) ────
    history = user_message.conversation_history or []
    if history:
        last_user = next((t.content for t in reversed(history) if t.role == "user"), "")
        if last_user and last_user != query_text:
            query_text = f"{last_user} {query_text}"
    detected_domains = classify_domains(query_text)
    logger.info("Auto-detected domains: %s", detected_domains)

    # ── Step 4: Multi-domain retrieval ───────────────────────────────
    _ensure_index()
    results = retrieve_multi_domain(
        query_text=query_text,
        domains=detected_domains,
        age_group=user_message.age_group or "unspecified",
        top_k_per_domain=2,
        behavior_type=user_message.behavior_type or "",
    )

    retrieved_units = [r for r in results if r.get("distance", 1.0) < 1.0]
    retrieved_texts = [r["document"] for r in retrieved_units]

    primary_domain = detected_domains[0] if detected_domains else "medical"

    # ── Step 5: LLM generation → fallback to retrieval_only ──────────
    mode: str = "retrieval_only"
    draft = ""

    if retrieved_units:
        try:
            generated = await generate_reply(
                domain=primary_domain,
                behavior_type=user_message.behavior_type or "",
                age_group=user_message.age_group or "unspecified",
                severity=user_message.severity or "خفيف",
                retrieved_units=retrieved_units,
                question_text=query_text,
                conversation_history=history,
            )
            if generated and generated.strip():
                mode = "llm_generated"
                draft = generated
                logger.info("LLM generation succeeded (mode=%s, domains=%s)", mode, detected_domains)
            else:
                logger.warning("LLM returned empty — fallback to merged retrieval")
                draft = _merge_retrieved(user_message, retrieved_units, detected_domains)
        except Exception as e:
            logger.warning("LLM failed: %s — using retrieval_only", e)
            draft = _merge_retrieved(user_message, retrieved_units, detected_domains)
    else:
        logger.info("No relevant documents found for domains: %s", detected_domains)
        draft = (
            f"لا توجد معلومات كافية حاليًا حول '{query_text}'. "
            f"نوصي باستشارة مختص."
        )

    # ── Step 6: Apply guardrails ──────────────────────────────────────
    user_message_for_guardrails = user_message.model_copy(
        update={"domain": primary_domain}
    )
    reply = apply_guardrails(user_message_for_guardrails, draft, policies, mode=mode)

    log_session(
        domain=primary_domain,
        behavior_type=user_message.behavior_type or "",
        age_group=user_message.age_group or "",
        severity=user_message.severity or "",
        mode=mode,
        needs_human_review=reply.needs_human_review,
        reply_length=len(reply.reply_text or ""),
        retrieved_count=len(retrieved_units),
        flag="no_results" if not retrieved_units else "",
    )

    return reply


@router.post("/query", response_model=AssistantReply)
async def query_reply(request: Request, user_message: UserMessage):
    """Alias for /draft — used by external clients."""
    return await draft_reply(request, user_message)


def _merge_retrieved(
    user_message: UserMessage,
    units: list[dict],
    domains: list[str] | None = None,
) -> str:
    if not units:
        return "لا توجد معلومات كافية حاليًا. نوصي باستشارة مختص."
    domains_ar = {"fiqh": "الفقه", "medical": "الطب النفسي",
                  "cyber": "الأمان الرقمي", "development": "تطور الطفل",
                  "tarbiyah": "التربية"}
    domains_str = " + ".join(domains_ar.get(d, d) for d in (domains or []))
    header = f"بخصوص استفسارك"
    if domains_str:
        header += f" (من مجالات: {domains_str})"
    header += ":\n\n"
    parts = []
    for u in units:
        doc = u.get("document", "")
        ref = u.get("metadata", {}).get("reference_info", "مصدر غير مذكور")
        parts.append(f"{doc.strip()}\n📚 المصدر: {ref}")
    body = "\n\n".join(parts)
    footer = "\n\nملاحظة: يُنصح باستشارة مختص للحالات المستعصية."
    return header + body + footer
