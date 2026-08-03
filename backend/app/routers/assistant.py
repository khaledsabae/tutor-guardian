"""
Assistant router — Multi-domain ChromaDB retrieval + guardrails + LLM.
Flow: banned check → emergency check → classify_domains → multi_retrieval → LLM → guardrails.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.api import ConversationTurn, UserMessage, AssistantReply
from app.services.guardrails import (
    apply_guardrails, is_emergency, emergency_reply, evaluate_guardrails,
    _build_fallback_message,
)
from app.services.retrieval import retrieve_hybrid, _ensure_index, log_retrieval
from app.services.reranker import RERANK_MIN_SCORE
from app.services.query_rewriter import rewrite_query
from app.services.llm_service import (
    generate_reply, build_full_prompt, generate_general_pivot, build_pivot_prompt,
    strip_pivot_citation, clean_model_output, _CJK_RE,
)
from app.services.ai_gateway import get_gateway
from app.services.session_logger import log_session
from app.services.intent_guard import check_banned_intent, check_emergency_keywords
from app.services.domain_classifier import (
    classify_domains, is_uncertain, matched_fast_path,
)
from app.services.tier_router import choose_tier
from app.services.privacy import redact_for_cloud
from app.services import answer_cache
from app.services import conversation_store as store
from app.services.tafsir_service import (
    detect_ayah_reference, fetch_tafsir, format_tafsir_for_context,
)

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# Fallback used when the off-topic pivot generation fails or returns empty.
_PIVOT_FALLBACK = (
    "هذا سؤال عام خارج مجال التربية، لكن يمكنك تحويله إلى لحظة جميلة مع طفلك: "
    "اجعله نشاطاً تستكشفانه معاً، فالمشاركة في أي نشاط يومي تقوّي الرابطة بينكما "
    "وتنمّي فضوله ومهاراته."
)


def _label_domain(domains: list[str], units: list[dict]) -> str:
    """The domain the reply is labelled (and guardrailed) with.

    Normally the classifier's top domain. But when classification FAILED we
    deliberately searched every domain instead of guessing one, so domains[0]
    carries no information — the label must come from the evidence we actually
    retrieved (the best reranked unit), never from an arbitrary list position.
    """
    if not domains:
        return "medical"
    if is_uncertain(domains) and units:
        return units[0].get("source_domain") or domains[0]
    return domains[0]


def _off_topic(units: list[dict]) -> tuple[bool, float | None]:
    """A question is off-topic when even the best reranked unit falls below
    the reranker's calibrated relevance floor (RERANK_MIN_SCORE). The reranker
    returns the single best unit even when everything is below the floor (so it
    never returns nothing), so we re-check the floor here to catch those."""
    scores = [
        u["rerank_score"] for u in units
        if isinstance(u.get("rerank_score"), (int, float))
    ]
    if not scores:
        return False, None
    top = max(scores)
    return top < RERANK_MIN_SCORE, top

async def _classify_and_rewrite(query_text: str) -> tuple[list[str], str]:
    """The two pre-retrieval model calls, run concurrently.

    Neither depends on the other: the rewriter is gated on matched_fast_path(),
    the cheap keyword check, not on the classifier's verdict. Running them back
    to back put both round-trips on the critical path before the first token.
    Measured on production, that is the whole gap between a question the
    keyword list catches (1.8s to first token) and one that needs the model
    (4.75s) — each call is roughly a second.

    A question the classifier then calls off-topic skips retrieval, so its
    rewrite was wasted work. That is one small call, accepted knowingly to keep
    the common case a full round-trip shorter.
    """
    fast_path = matched_fast_path(query_text)
    domains, rewritten = await asyncio.gather(
        asyncio.to_thread(classify_domains, query_text),
        asyncio.to_thread(rewrite_query, query_text, classifier_fast_path=fast_path),
    )
    return domains, rewritten


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/draft", response_model=AssistantReply)
async def draft_reply(request: Request, user_message: UserMessage):
    policies = request.app.state.guardrails_config

    # ── Session: validate + persist the incoming user message ────────
    # NB: every sqlite / model-inference call below goes through
    # asyncio.to_thread — this handler must never block the event loop
    # (single uvicorn worker; a blocked loop freezes /health too).
    session_id = user_message.session_id
    if session_id:
        if not await asyncio.to_thread(store.session_exists, session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        await asyncio.to_thread(
            store.add_message,
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
        return await asyncio.to_thread(_finalize, reply, session_id)

    # ── Step 0b: Emergency keyword check ─────────────────────────────
    if check_emergency_keywords(query_input):
        logger.info("Emergency keyword detected in message_text")
        user_message = user_message.model_copy(update={"severity": "طارئ"})

    # ── Step 1: Emergency severity check ─────────────────────────────
    if is_emergency(user_message):
        logger.info("Emergency severity — returning fallback immediately")
        return await asyncio.to_thread(_finalize, emergency_reply(user_message, policies), session_id)

    # ── Step 2: Build query text ──────────────────────────────────────
    query_text = (user_message.message_text or "").strip()
    if not query_text:
        query_text = f"{user_message.behavior_type} {user_message.age_group}"

    # ── Step 3: Auto-detect domains (من السؤال فقط — بدون دمج history) ────
    # Server owns history when a session is active; else trust the client's.
    if session_id:
        history = await asyncio.to_thread(store.get_history, session_id, limit=6)
    else:
        history = user_message.conversation_history or []
    # Both can make a model call (seconds) on a keyword fast-path miss, and
    # they are independent — so they run together, not one after the other.
    detected_domains, rewritten_query = await _classify_and_rewrite(query_text)
    is_general = detected_domains == ["general"]
    logger.info("Auto-detected domains: %s", detected_domains)

    primary_domain = _label_domain(detected_domains, [])
    severity = user_message.severity or "خفيف"

    # ── Step 3b: Pre-cache check ─────────────────────────────────────
    # Skipped when classification failed: the cache key contains the domain,
    # so looking up under a guessed one can only mislead.
    first_question = not any(
        getattr(t, "role", "") == "assistant" for t in history
    )
    if first_question and not is_general and not is_uncertain(detected_domains):
        decision = evaluate_guardrails(primary_domain, severity, policies)
        if not decision["force_fallback"]:
            cached = await asyncio.to_thread(
                answer_cache.lookup,
                query_text, user_message.age_group or "unspecified",
                primary_domain, severity
            )
            if cached:
                logger.info("Cache hit! Serving pre-cached answer.")
                reply = AssistantReply(
                    reply_text=cached, domain=primary_domain, severity=severity,
                    needs_human_review=decision["needs_human_review"],
                    escalation_target=decision["escalate_to"],
                    mode="llm_generated",
                )
                return await asyncio.to_thread(_finalize, reply, session_id)

    # ── Step 4: Hybrid retrieval (vector + BM25 → RRF → rerank) ──────
    # A general/off-topic question has no parenting KB to ground on, so skip
    # retrieval entirely and go straight to the pivot.
    if is_general:
        await asyncio.to_thread(_ensure_index)
        retrieved_units: list[dict] = []
    else:
        def _retrieve_blocking() -> list[dict]:
            # CPU-bound embedding + reranking — one thread hop. The rewrite has
            # already happened alongside classification (_classify_and_rewrite).
            _ensure_index()
            units = retrieve_hybrid(
                query_text=query_text,
                domains=detected_domains,
                age_group=user_message.age_group or "unspecified",
                rewritten_query=rewritten_query,
            )
            log_retrieval(query_text, detected_domains, rewritten_query, units)
            return units

        # ── Step 4b: Tafsir MCP — if the question references a specific ayah, ──
        # fetch its tafsir concurrently with KB retrieval. The tafsir text is
        # injected as an extra context block in the generation prompt, NOT as a
        # replacement for KB retrieval — the parenting advice still comes from
        # the KB. This is a one-shot best-effort enrichment: if the MCP server
        # is unreachable, the tafsir block is silently empty and the answer is
        # built from KB units alone, exactly as before.
        ayah_ref = detect_ayah_reference(query_text)
        if ayah_ref:
            tafsir_task = asyncio.create_task(
                fetch_tafsir(ayah_ref[0], ayah_ref[1])
            )
            retrieved_units = await asyncio.to_thread(_retrieve_blocking)
            tafsir_results = await tafsir_task
            tafsir_context = format_tafsir_for_context(tafsir_results)
            if tafsir_context:
                logger.info(
                    "Tafsir MCP enriched answer for %s:%d",
                    ayah_ref[0], ayah_ref[1],
                )
                # Inject as a synthetic retrieved unit so the prompt builder
                # and the merge fallback both carry it.
                retrieved_units.insert(0, {
                    "unit_id": f"tafsir_{ayah_ref[0]}_{ayah_ref[1]}",
                    "document": f"passage: {tafsir_context}",
                    "metadata": {
                        "domain": "fiqh",
                        "reference_info": "Tafsir MCP — مركز تفسير",
                        "title": "تفسير آية قرآنية",
                    },
                    "rerank_score": 1.0,  # authoritative — always included
                    "source_domain": "fiqh",
                })
        else:
            retrieved_units = await asyncio.to_thread(_retrieve_blocking)

    # Re-label from the retrieved evidence when classification was uncertain.
    primary_domain = _label_domain(detected_domains, retrieved_units)

    # ── Step 5: LLM generation → fallback to retrieval_only ──────────
    mode: str = "retrieval_only"
    draft = ""

    score_off_topic, top_rerank = _off_topic(retrieved_units)
    off_topic = is_general or score_off_topic

    if off_topic:
        # General/off-topic question (e.g. a recipe). Don't ground on the
        # irrelevant KB units — answer briefly then pivot to a parenting
        # activity. Local-only, no citations.
        mode = "general_pivot"
        try:
            generated = await generate_general_pivot(
                query_text, user_message.age_group or "unspecified"
            )
            draft = generated if (generated and generated.strip()) else _PIVOT_FALLBACK
        except Exception as e:
            logger.warning("Pivot generation failed: %s — using fallback", e)
            draft = _PIVOT_FALLBACK
    elif retrieved_units:
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
            def _redact_blocking():
                # redact_for_cloud reads child names from sqlite per call.
                return (
                    redact_for_cloud(query_text),
                    [
                        t.model_copy(update={"content": redact_for_cloud(t.content)})
                        for t in history
                    ],
                )

            gen_question, gen_history = await asyncio.to_thread(_redact_blocking)
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

    # Determine intervention type from retrieved units for guardrails
    intervention_type = None
    if retrieved_units:
        for unit in retrieved_units:
            if unit.get("intervention_type") == "إحالة_لطبيب":
                intervention_type = "إحالة_لطبيب"
                break
        if not intervention_type:
            intervention_type = retrieved_units[0].get("intervention_type")

    # ── Step 6: Apply guardrails ──────────────────────────────────────
    user_message_for_guardrails = user_message.model_copy(
        update={"domain": primary_domain}
    )
    reply = apply_guardrails(
        user_message_for_guardrails, draft, policies, mode=mode,
        intervention_type=intervention_type
    )
    reply.metadata = {
        **(reply.metadata or {}),
        "top_rerank": round(top_rerank, 2) if top_rerank is not None else None,
        "off_topic": off_topic,
    }

    await asyncio.to_thread(
        log_session,
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

    return await asyncio.to_thread(_finalize, reply, session_id)


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
async def stream_reply(request: Request, user_message: UserMessage) -> StreamingResponse:
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
    if session_id:
        history = await asyncio.to_thread(store.get_history, session_id, limit=6)
    else:
        history = user_message.conversation_history or []
    # Concurrent, not sequential — see _classify_and_rewrite. This is the path
    # the mobile app uses, so the round-trip saved here is one the user feels.
    detected_domains, rewritten_query = await _classify_and_rewrite(query_text)
    is_general = detected_domains == ["general"]

    primary_domain = _label_domain(detected_domains, [])
    severity = user_message.severity or "خفيف"

    # First question in the session? (no assistant turns yet). Only then may
    # the answer cache serve/store — a follow-up depends on conversation the
    # cache never saw. (§5.1 كاش الأسئلة المتكررة)
    first_question = not any(
        getattr(t, "role", "") == "assistant" for t in history
    )

    # ── Step 3b: Pre-cache check (skipped on a guessed domain — see /draft) ──
    if first_question and not is_general and not is_uncertain(detected_domains):
        decision = evaluate_guardrails(primary_domain, severity, policies)
        if not decision["force_fallback"]:
            cached = await asyncio.to_thread(
                answer_cache.lookup,
                query_text, user_message.age_group or "unspecified",
                primary_domain, severity
            )
            if cached:
                logger.info("Cache hit in stream! Serving pre-cached answer.")
                return _single(AssistantReply(
                    reply_text=cached, domain=primary_domain, severity=severity,
                    needs_human_review=decision["needs_human_review"],
                    escalation_target=decision["escalate_to"],
                    mode="llm_generated",
                ))

    # Cache missed, proceed with index assurance and hybrid retrieval
    if is_general:
        await asyncio.to_thread(_ensure_index)
        retrieved_units: list[dict] = []
    else:
        def _retrieve_blocking() -> list[dict]:
            # The rewrite already ran alongside classification above.
            _ensure_index()
            units = retrieve_hybrid(
                query_text=query_text, domains=detected_domains,
                age_group=user_message.age_group or "unspecified",
                rewritten_query=rewritten_query,
            )
            log_retrieval(query_text, detected_domains, rewritten_query, units)
            return units

        # ── Tafsir MCP enrichment (same logic as /draft) ────────────────
        ayah_ref = detect_ayah_reference(query_text)
        if ayah_ref:
            tafsir_task = asyncio.create_task(
                fetch_tafsir(ayah_ref[0], ayah_ref[1])
            )
            retrieved_units = await asyncio.to_thread(_retrieve_blocking)
            tafsir_results = await tafsir_task
            tafsir_context = format_tafsir_for_context(tafsir_results)
            if tafsir_context:
                logger.info(
                    "Tafsir MCP enriched stream for %s:%d",
                    ayah_ref[0], ayah_ref[1],
                )
                retrieved_units.insert(0, {
                    "unit_id": f"tafsir_{ayah_ref[0]}_{ayah_ref[1]}",
                    "document": f"passage: {tafsir_context}",
                    "metadata": {
                        "domain": "fiqh",
                        "reference_info": "Tafsir MCP — مركز تفسير",
                        "title": "تفسير آية قرآنية",
                    },
                    "rerank_score": 1.0,
                    "source_domain": "fiqh",
                })
        else:
            retrieved_units = await asyncio.to_thread(_retrieve_blocking)

    # Re-label from the retrieved evidence when classification was uncertain.
    primary_domain = _label_domain(detected_domains, retrieved_units)

    score_off_topic, _top_rerank = _off_topic(retrieved_units)
    off_topic = is_general or score_off_topic

    # No relevant KB and not an off-topic pivot → non-streamed fallback
    if not retrieved_units and not off_topic:
        draft = f"لا توجد معلومات كافية حاليًا حول '{query_text}'. نوصي باستشارة مختص."
        return _single(apply_guardrails(
            user_message.model_copy(update={"domain": primary_domain}),
            draft, policies, mode="retrieval_only",
        ))

    if off_topic:
        # General/off-topic question → stream a brief answer pivoted to a
        # parenting activity. No grounding, no citations, local-only.
        decision = {"needs_human_review": False, "escalate_to": None}
        tier, route_reason = "local_fast", "off_topic_pivot"
        stream_mode = "general_pivot"
        full_prompt = build_pivot_prompt(
            query_text, user_message.age_group or "unspecified"
        )
    else:
        # Determine intervention type from retrieved units for guardrails
        intervention_type = None
        if retrieved_units:
            for unit in retrieved_units:
                if unit.get("intervention_type") == "إحالة_لطبيب":
                    intervention_type = "إحالة_لطبيب"
                    break
            if not intervention_type:
                intervention_type = retrieved_units[0].get("intervention_type")

        # Guardrails would replace the whole text → don't stream, send fallback
        decision = evaluate_guardrails(primary_domain, severity, policies, intervention_type)
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
        stream_mode = "llm_generated"
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
            conversation_history=stream_history, tier=tier,
        )

    async def event_stream():
        import queue
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()

        def run_sync_stream():
            try:
                for chunk in get_gateway().stream(
                    full_prompt, tier=tier, route_reason=route_reason
                ):
                    loop.call_soon_threadsafe(q.put_nowait, ("chunk", chunk))
                loop.call_soon_threadsafe(q.put_nowait, ("done", None))
            except Exception as e:
                loop.call_soon_threadsafe(q.put_nowait, ("error", e))

        # Offload the blocking stream reader loop to a background worker thread
        asyncio.create_task(asyncio.to_thread(run_sync_stream))

        try:
            while True:
                msg_type, val = await q.get()
                if msg_type == "done":
                    break
                elif msg_type == "error":
                    raise val
                else:
                    chunk = val
                    if chunk.done:
                        final_text = (chunk.result.text if chunk.result else "").strip()
                        if stream_mode == "general_pivot":
                            final_text = strip_pivot_citation(final_text)
                        final_text = clean_model_output(final_text)
                        reply = AssistantReply(
                            reply_text=final_text, domain=primary_domain, severity=severity,
                            needs_human_review=decision["needs_human_review"],
                            escalation_target=decision["escalate_to"],
                            mode=stream_mode, session_id=session_id,
                        )
                        if session_id:
                            await asyncio.to_thread(
                                store.add_message,
                                session_id, "assistant", final_text,
                                domain=primary_domain, severity=severity,
                                mode=stream_mode,
                                needs_human_review=decision["needs_human_review"],
                            )
                        await asyncio.to_thread(
                            log_session,
                            domain=primary_domain, behavior_type=user_message.behavior_type or "",
                            age_group=user_message.age_group or "", severity=severity,
                            mode=stream_mode, needs_human_review=decision["needs_human_review"],
                            reply_length=len(final_text), retrieved_count=len(retrieved_units),
                        )
                        # Feed the answer cache: grounded, local, review-free,
                        # first-question answers only (§5.1).
                        if (
                            stream_mode == "llm_generated"
                            and first_question
                            and tier != "cloud_quality"
                            and not decision["needs_human_review"]
                        ):
                            await asyncio.to_thread(
                                answer_cache.store,
                                query_text, user_message.age_group or "unspecified",
                                primary_domain, severity, final_text,
                            )
                        yield _sse("done", reply.model_dump())
                    elif chunk.delta:
                        # Filter leaked CJK tokens from the live stream too.
                        yield _sse("token", {"delta": _CJK_RE.sub("", chunk.delta)})
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
    domains_ar = {"fiqh": "الفقه", "medical": "العادات والمهارات الحياتية",
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
