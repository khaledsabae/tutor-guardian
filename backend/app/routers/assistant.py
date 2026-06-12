"""
Assistant router — Multi-domain ChromaDB retrieval + guardrails + LLM.
Flow: banned check → emergency check → classify_domains → multi_retrieval → LLM → guardrails.
"""
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.api import ConversationTurn, UserMessage, AssistantReply
from app.services.guardrails import (
    apply_guardrails, is_emergency, emergency_reply, evaluate_guardrails,
    _build_fallback_message,
)
from app.services.retrieval import retrieve_multi_domain, _ensure_index
from app.services.llm_service import generate_reply, build_full_prompt
from app.services.ai_gateway import get_gateway
from app.services.session_logger import log_session
from app.services.intent_guard import check_banned_intent, check_emergency_keywords
from app.services.domain_classifier import classify_domains
from app.services.tier_router import choose_tier
from app.services.privacy import redact_for_cloud
from app.services import conversation_store as store

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/draft", response_model=AssistantReply)
async def draft_reply(request: Request, user_message: UserMessage):
    policies = request.app.state.guardrails_config

    # ── Session: validate + persist the incoming user message ────────
    session_id = user_message.session_id
    if session_id:
        if not store.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        store.add_message(
            session_id, "user",
            user_message.message_text or user_message.behavior_type or "",
        )

    # ── Step 0: Banned intent check ──────────────────────────────────
    query_input = user_message.message_text or user_message.behavior_type or ""
    is_banned, matched = check_banned_intent(query_input)
    if is_banned:
        logger.warning("Banned intent detected: %s", matched)
        reply = AssistantReply(
            reply_text="هذا الموضوع خارج نطاق ما يمكنني مساعدتك فيه. إذا كنت في حالة طارئة، يرجى التواصل مع الجهات المختصة فوراً.",
            domain="medical",
            severity="طارئ",
            needs_human_review=True,
            escalation_target="emergency_services",
            mode="banned",
        )
        return _finalize(reply, session_id)

    # ── Step 0b: Emergency keyword check ─────────────────────────────
    if check_emergency_keywords(query_input):
        logger.info("Emergency keyword detected in message_text")
        user_message = user_message.model_copy(update={"severity": "طارئ"})

    # ── Step 1: Emergency severity check ─────────────────────────────
    if is_emergency(user_message):
        logger.info("Emergency severity — returning fallback immediately")
        return _finalize(emergency_reply(user_message, policies), session_id)

    # ── Step 2: Build query text ──────────────────────────────────────
    query_text = (user_message.message_text or "").strip()
    if not query_text:
        query_text = f"{user_message.behavior_type} {user_message.age_group}"

    # ── Step 3: Auto-detect domains (من السؤال فقط — بدون دمج history) ────
    # Server owns history when a session is active; else trust the client's.
    if session_id:
        history = store.get_history(session_id, limit=6)
    else:
        history = user_message.conversation_history or []
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

    retrieved_units = [r for r in results if r.get("distance", 1.0) < 0.85]
    retrieved_texts = [r["document"] for r in retrieved_units]

    primary_domain = detected_domains[0] if detected_domains else "medical"

    # ── Step 5: LLM generation → fallback to retrieval_only ──────────
    mode: str = "retrieval_only"
    draft = ""

    if retrieved_units:
        # Quality-tier routing: hard/high-stakes questions go to the cloud
        # quality model (flag-gated, $0 tier); the question and history are
        # PII-redacted before leaving the machine. Local chain is always
        # the fallback, so cloud failure is invisible here.
        tier, route_reason = choose_tier(
            query_text, detected_domains, user_message.severity or "خفيف",
            retrieved_units, history_len=len(history),
        )
        gen_question, gen_history = query_text, history
        if tier == "cloud_quality":
            gen_question = redact_for_cloud(query_text)
            gen_history = [
                t.model_copy(update={"content": redact_for_cloud(t.content)})
                for t in history
            ]
        try:
            generated = await generate_reply(
                domain=primary_domain,
                behavior_type=user_message.behavior_type or "",
                age_group=user_message.age_group or "unspecified",
                severity=user_message.severity or "خفيف",
                retrieved_units=retrieved_units,
                question_text=gen_question,
                conversation_history=gen_history,
                tier=tier,
                route_reason=route_reason,
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

    return _finalize(reply, session_id)


def _finalize(reply: AssistantReply, session_id: str | None) -> AssistantReply:
    """Tag the reply with its session and persist it server-side (if any)."""
    reply.session_id = session_id
    if session_id:
        store.add_message(
            session_id, "assistant", reply.reply_text or "",
            domain=reply.domain, severity=reply.severity, mode=reply.mode,
            needs_human_review=reply.needs_human_review,
        )
    return reply


@router.post("/query", response_model=AssistantReply)
async def query_reply(request: Request, user_message: UserMessage):
    """Alias for /draft — used by external clients."""
    return await draft_reply(request, user_message)


@router.post("/stream")
def stream_reply(request: Request, user_message: UserMessage) -> StreamingResponse:
    """
    SSE streaming variant of /draft (mobile-ready).

    Contract — every response is a stream of Server-Sent Events:
        event: token   data: {"delta": "..."}      (0+ times, LLM tokens)
        event: done    data: {<full AssistantReply>} (always, terminal)
        event: error   data: {"detail": "..."}       (on failure)

    Safety: all guardrail/banned/emergency decisions run BEFORE any token is
    sent (you can't un-send a streamed token). Banned/emergency/no-context/
    force-fallback replies are emitted as a single `done` event (not streamed).
    """
    policies = request.app.state.guardrails_config
    session_id = user_message.session_id

    # ── Session: validate + persist incoming user message ────────────
    if session_id:
        if not store.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        store.add_message(
            session_id, "user",
            user_message.message_text or user_message.behavior_type or "",
        )

    def _single(reply: AssistantReply) -> StreamingResponse:
        """Emit a non-streamed reply as one terminal `done` event."""
        _finalize(reply, session_id)

        def one():
            yield _sse("done", reply.model_dump())
        return StreamingResponse(one(), media_type="text/event-stream", headers=_SSE_HEADERS)

    # ── Pre-flight safety (identical order to /draft) ────────────────
    query_input = user_message.message_text or user_message.behavior_type or ""
    is_banned, matched = check_banned_intent(query_input)
    if is_banned:
        logger.warning("Banned intent detected (stream): %s", matched)
        return _single(AssistantReply(
            reply_text="هذا الموضوع خارج نطاق ما يمكنني مساعدتك فيه. إذا كنت في حالة طارئة، يرجى التواصل مع الجهات المختصة فوراً.",
            domain="medical", severity="طارئ", needs_human_review=True,
            escalation_target="emergency_services", mode="banned",
        ))

    if check_emergency_keywords(query_input):
        user_message = user_message.model_copy(update={"severity": "طارئ"})
    if is_emergency(user_message):
        return _single(emergency_reply(user_message, policies))

    # ── Build query + history + retrieve ─────────────────────────────
    query_text = (user_message.message_text or "").strip() or \
        f"{user_message.behavior_type} {user_message.age_group}"
    history = (
        store.get_history(session_id, limit=6)
        if session_id else (user_message.conversation_history or [])
    )
    detected_domains = classify_domains(query_text)
    _ensure_index()
    results = retrieve_multi_domain(
        query_text=query_text, domains=detected_domains,
        age_group=user_message.age_group or "unspecified",
        top_k_per_domain=2, behavior_type=user_message.behavior_type or "",
    )
    retrieved_units = [r for r in results if r.get("distance", 1.0) < 0.85]
    primary_domain = detected_domains[0] if detected_domains else "medical"
    severity = user_message.severity or "خفيف"

    # No context → non-streamed fallback
    if not retrieved_units:
        draft = f"لا توجد معلومات كافية حاليًا حول '{query_text}'. نوصي باستشارة مختص."
        return _single(apply_guardrails(
            user_message.model_copy(update={"domain": primary_domain}),
            draft, policies, mode="retrieval_only",
        ))

    # Guardrails would replace the whole text → don't stream, send fallback
    decision = evaluate_guardrails(primary_domain, severity, policies)
    if decision["force_fallback"]:
        draft = _build_fallback_message(
            primary_domain, user_message.behavior_type or "",
            user_message.age_group or "unspecified", policies,
        )
        return _single(AssistantReply(
            reply_text=draft, domain=primary_domain, severity=severity,
            needs_human_review=decision["needs_human_review"],
            escalation_target=decision["escalate_to"], mode="llm_generated",
        ))

    # ── Stream the LLM generation token-by-token ─────────────────────
    # Quality-tier routing (flag-gated). The cloud provider is tried
    # pre-flight only — if it fails before the first token, the local
    # chain takes over and the SSE consumer never notices.
    tier, route_reason = choose_tier(
        query_text, detected_domains, severity,
        retrieved_units, history_len=len(history),
    )
    stream_question, stream_history = query_text, history
    if tier == "cloud_quality":
        stream_question = redact_for_cloud(query_text)
        stream_history = [
            t.model_copy(update={"content": redact_for_cloud(t.content)})
            for t in history
        ]
    full_prompt, _source = build_full_prompt(
        domain=primary_domain, behavior_type=user_message.behavior_type or "",
        age_group=user_message.age_group or "unspecified", severity=severity,
        retrieved_units=retrieved_units, question_text=stream_question,
        conversation_history=stream_history,
    )

    def event_stream():
        try:
            for chunk in get_gateway().stream(
                full_prompt, tier=tier, route_reason=route_reason
            ):
                if chunk.done:
                    final_text = (chunk.result.text if chunk.result else "").strip()
                    reply = AssistantReply(
                        reply_text=final_text, domain=primary_domain, severity=severity,
                        needs_human_review=decision["needs_human_review"],
                        escalation_target=decision["escalate_to"],
                        mode="llm_generated", session_id=session_id,
                    )
                    if session_id:
                        store.add_message(
                            session_id, "assistant", final_text,
                            domain=primary_domain, severity=severity,
                            mode="llm_generated",
                            needs_human_review=decision["needs_human_review"],
                        )
                    log_session(
                        domain=primary_domain, behavior_type=user_message.behavior_type or "",
                        age_group=user_message.age_group or "", severity=severity,
                        mode="llm_generated", needs_human_review=decision["needs_human_review"],
                        reply_length=len(final_text), retrieved_count=len(retrieved_units),
                    )
                    yield _sse("done", reply.model_dump())
                elif chunk.delta:
                    yield _sse("token", {"delta": chunk.delta})
        except Exception as e:
            logger.warning("Stream generation failed: %s", e)
            yield _sse("error", {"detail": "تعذّر توليد الرد، يُرجى المحاولة لاحقاً."})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


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
