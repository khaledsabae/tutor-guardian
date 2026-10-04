"""
Assistant router — Multi-domain ChromaDB retrieval + guardrails + LLM.
Flow: self-worry support → banned check → emergency check → discipline guard → fiqh guard → classify_domains → multi_retrieval → LLM → guardrails.
"""
import asyncio
import functools
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.api import ConversationTurn, UserMessage, AssistantReply
from app.services.guardrails import (
    apply_guardrails, is_emergency, emergency_reply, evaluate_guardrails,
    _build_fallback_message,
)
from app.services.retrieval import (retrieve_hybrid, _ensure_index,
                                    log_retrieval, detect_query_language)
from app.services.reranker import RERANK_MIN_SCORE
from app.services.query_rewriter import rewrite_query
from app.services.llm_service import (
    generate_reply, build_full_prompt, generate_general_pivot, build_pivot_prompt,
    strip_pivot_citation, clean_model_output, reply_sources, usable_reference, _CJK_RE,
)
from app.services.ai_gateway import StreamTracker, get_gateway
from app.services.session_logger import log_session
from app.services.intent_guard import (
    check_banned_intent, check_emergency_keywords,
    check_abusive_language, check_conversational_shortcut, detect_reply_language,
)
from app.services.fiqh_guard import check_fiqh_guard, SAFE_REPLY as FIQH_SAFE_REPLY
from app.services.discipline_guard import check_physical_discipline, discipline_reply
from app.services.domain_classifier import (
    UNCERTAIN_DOMAINS, classify_domains, is_uncertain, matched_fast_path,
)
from app.services.tier_router import choose_tier
from app.services.privacy import mentions_any, names_for_device, redact_with_names
from app.services import child_memory
from app.services import answer_cache
from app.services import conversation_store as store
from app.services.tafsir_service import (
    resolve_ayah_reference, fetch_tafsir, format_tafsir_for_context,
)

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

# Shown to the parent *and* stored as the turn when generation fails outright,
# so the conversation keeps a visible answer instead of a question that hangs.
# In the parent's own language: English and French parents used to get the
# Arabic sentence verbatim.
_STREAM_ERROR_TEXTS = {
    "ar": "تعذّر توليد الرد، يُرجى المحاولة لاحقاً.",
    "en": "Sorry, the answer could not be generated. Please try again in a moment.",
    "fr": "Désolé, la réponse n'a pas pu être générée. Veuillez réessayer dans un instant.",
}
_STREAM_ERROR_TEXT = _STREAM_ERROR_TEXTS["ar"]


def _error_text(lang: str | None) -> str:
    return _STREAM_ERROR_TEXTS.get(lang or "ar", _STREAM_ERROR_TEXT)


# ── LLM stream workers (audit H6) ─────────────────────────────────────────
# Each SSE answer holds one thread for as long as the model is talking. They
# used to come from the DEFAULT executor — the same small pool every
# `asyncio.to_thread` sqlite call uses — so a handful of concurrent answers
# stalled every DB-backed request in the app. They get their own bounded pool
# now; beyond it, new streams queue instead of starving everything else.
_STREAM_WORKERS = max(1, int(os.environ.get("LLM_STREAM_WORKERS", "8")))
_STREAM_DEADLINE_S = float(os.environ.get("LLM_STREAM_DEADLINE_S", "300"))
_STREAM_EXECUTOR = ThreadPoolExecutor(
    max_workers=_STREAM_WORKERS, thread_name_prefix="llm-stream"
)
# An SSE comment every few seconds while the model is silent (retrieval, a
# cold local model, the fallback chain — the first token can take minutes).
# The app treats a stream with no bytes for 45 s as dead (audit M13); this is
# what lets it tell "still thinking" from "the connection is gone".
# The classifier and the rewriter: one short model call each (see
# _classify_and_rewrite). Bounded by the auxiliary call's own deadline.
_AUX_CALLERS = ThreadPoolExecutor(
    max_workers=max(2, int(os.environ.get("AUX_CALLER_WORKERS", "8"))),
    thread_name_prefix="aux-caller",
)
_AUX_WAIT_S = float(os.environ.get("AUX_WAIT_S", "20"))
_STREAM_KEEPALIVE_S = float(os.environ.get("SSE_KEEPALIVE_S", "15"))
_SSE_KEEPALIVE = ": keep-alive\n\n"
# …but the keep-alive also defeats that 45 s check: a provider that never
# sends a token kept the parent on «يكتب…» until DeepSeek dropped the request
# (up to 30 min — the 2026-10-01 incident). The server therefore gives up on
# its own: no first token within _FIRST_TOKEN_TIMEOUT_S, or no new token for
# _STREAM_STALL_S mid-answer, ends the turn with an error the app can retry.
# Normal answers start in seconds (p99 of a whole answer: 78 s).
_FIRST_TOKEN_TIMEOUT_S = float(os.environ.get("LLM_FIRST_TOKEN_TIMEOUT_S", "75"))
_STREAM_STALL_S = float(os.environ.get("LLM_STREAM_STALL_S", "60"))
# Once the stream has moved past the paid primary to a fallback model, that
# attempt gets its own, longer first-token budget: a 7B model on the home
# CPU box needs 32–95 s before its first token, and killing it at 75 s from
# the start of the request threw away the only answer still coming.
_FALLBACK_FIRST_TOKEN_S = float(os.environ.get("LLM_FALLBACK_FIRST_TOKEN_S", "150"))

# `sessions.flag` values for turns that end without an answer. The weekly
# funnel report counts them (ops/scripts/weekly_funnel_report._OUTCOME_FLAGS):
# without them, "no reply row" could not tell a parent who walked away from a
# server that never answered.
_FLAG_CLIENT_LEFT = "client_left_before_first_token"
_FLAG_FIRST_TOKEN_TIMEOUT = "first_token_timeout"
_FLAG_STREAM_STALLED = "stream_stalled"
_FLAG_PIPELINE_ERROR = "pipeline_error"
_FLAG_COMPLETED_AFTER_DISCONNECT = "completed_after_disconnect"
# The turn was cut on purpose: a new question arrived in the same session, or
# the parent pressed Stop (new app builds send POST /api/chat/sessions/{id}/stop).
_FLAG_SUPERSEDED = "superseded"
_FLAG_STOPPED = "stopped_by_parent"

# Answers being finished after their reader left (see event_stream's finally),
# and the pre-stream pipelines of /stream requests (classification,
# retrieval). Held here so the tasks are not garbage-collected mid-flight.
_BACKGROUND_COMPLETIONS: set[asyncio.Task] = set()
_PIPELINES: set[asyncio.Task] = set()


class _StreamStalled(TimeoutError):
    """The provider stopped (or never started) sending tokens."""

    def __init__(self, flag: str, waited_s: float) -> None:
        super().__init__(f"{flag} after {waited_s:.0f}s")
        self.flag = flag


def _pump_stream(make_stream, emit, cancel: threading.Event,
                 deadline_s: float = _STREAM_DEADLINE_S) -> None:
    """Drive a blocking LLM stream on a worker thread until done or cancelled.

    `emit(kind, value)` hands ("chunk", c) / ("done", None) / ("error", e) back
    to the event loop. When `cancel` is set — the SSE client went away — the
    loop stops at the next chunk and the generator is CLOSED, which unwinds the
    provider's `with requests.post(..., stream=True)` and drops the upstream
    connection. Previously the thread kept reading the whole answer after the
    parent left, holding its worker until generation finished.

    `deadline_s` bounds a single answer end to end; the gateway's own timeouts
    are per read, so a slow trickle could otherwise run for many minutes.
    """
    started = time.monotonic()
    gen = None
    try:
        gen = make_stream()
        for chunk in gen:
            if cancel.is_set():
                # Tell a consumer still listening (a turn cut while live) that
                # nothing more is coming, rather than leave it to the watchdog.
                emit("cancelled", None)
                return
            if time.monotonic() - started > deadline_s:
                emit("error", TimeoutError(f"stream exceeded {deadline_s:.0f}s"))
                return
            emit("chunk", chunk)
        emit("done", None)
    except Exception as e:  # noqa: BLE001 — surfaced to the SSE consumer
        # A cut turn (LLMCancelled, or anything raised once it was cut) is
        # not a failure: whoever still listens is told nothing more comes.
        emit("cancelled", None) if cancel.is_set() else emit("error", e)
    finally:
        if gen is not None:
            close = getattr(gen, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:  # noqa: BLE001 — best effort
                    pass


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _turn_frame(user_msg_id: int | None) -> str:
    """First SSE frame: the stored question's id, so the app can find THIS
    turn's answer in the session history later. Additive — clients that
    predate it ignore unknown events."""
    return _sse("turn", {"message_id": user_msg_id}) if user_msg_id is not None else ""


def _stall_flag(now: float, started: float, tracker: StreamTracker,
                last_token_at: float | None) -> str | None:
    """Why a silent stream should end now, or None to keep waiting.

    The first-token budget is timed per provider attempt: the paid primary
    (which also aborts itself at PRIMARY_FIRST_TOKEN_S) gets
    _FIRST_TOKEN_TIMEOUT_S, a fallback model the longer
    _FALLBACK_FIRST_TOKEN_S. A stream whose worker never started — queued
    behind busy ones — is timed from the request. _STREAM_DEADLINE_S caps it all.
    """
    if now - started > _STREAM_DEADLINE_S:
        return _FLAG_STREAM_STALLED if last_token_at is not None else _FLAG_FIRST_TOKEN_TIMEOUT
    if last_token_at is not None:
        return _FLAG_STREAM_STALLED if now - last_token_at > _STREAM_STALL_S else None
    if tracker.attempt_started is None:
        return _FLAG_FIRST_TOKEN_TIMEOUT if now - started > _FIRST_TOKEN_TIMEOUT_S else None
    limit = _FIRST_TOKEN_TIMEOUT_S if tracker.is_primary else _FALLBACK_FIRST_TOKEN_S
    return _FLAG_FIRST_TOKEN_TIMEOUT if now - tracker.attempt_started > limit else None


class _TurnControl:
    """Handle on the answer a session is producing, for cutting it short.

    Registered the moment the question row is stored (T1) — not when the
    answer starts streaming, seconds later, after classification and
    retrieval: a newer question or a Stop arriving in that window used to
    find nothing to cut, and the old answer was generated and stored after
    the new question anyway.

    `cut` is the reason once cut. `cancel_work(flag)` runs on the event loop
    (stops the model worker and any background completion); `settle(flag)`
    writes the cut turn and may run in a thread. Until the answer starts,
    both only record the cut — there is nothing to stop and nothing to write.
    """

    def __init__(self, session_id: str, user_msg_id: int | None = None) -> None:
        self.session_id = session_id
        self.user_msg_id = user_msg_id
        self.cut = ""
        self.reader_gone = False   # the client left before the answer began
        self._cancel_hook = None
        self._settle_hook = None

    def attach(self, cancel_hook, settle_hook) -> None:
        """The answer's stream is starting: cuts now reach its worker and row."""
        self._cancel_hook, self._settle_hook = cancel_hook, settle_hook

    def cancel_work(self, flag: str) -> None:
        self.cut = self.cut or flag
        if self._cancel_hook is not None:
            self._cancel_hook(flag)

    def settle(self, flag: str) -> None:
        if self._settle_hook is not None:
            self._settle_hook(flag)
        else:
            # Cut before any word was produced: no row, but the reason counts.
            try:
                log_session(domain="", behavior_type="", age_group="", severity="",
                            mode="abandoned", needs_human_review=False, reply_length=0,
                            retrieved_count=0, flag=flag)
            except Exception:  # noqa: BLE001 — telemetry only
                pass

    def release(self) -> None:
        """Forget this turn — unless a newer one has already taken its place."""
        if _ACTIVE_TURNS.get(self.session_id) is self:
            del _ACTIVE_TURNS[self.session_id]


# session_id → the answer it is producing. One event loop, one worker: plain
# dict access from coroutines needs no lock.
_ACTIVE_TURNS: dict[str, _TurnControl] = {}


async def cut_pending_turn(session_id: str | None, flag: str,
                           only_message_id: int | None = None) -> bool:
    """Cut the answer this session is still producing, if any.

    Called before a new question is stored (flag 'superseded'): the old turn's
    row is written first, so the conversation keeps its order — Q1, A1, Q2 —
    instead of the old answer landing after the new question. Also called by
    the explicit stop endpoint ('stopped_by_parent') with the question the
    parent is stopping, so a late stop can never cut a newer turn. True when
    a turn was cut.
    """
    if not session_id:
        return False
    control = _ACTIVE_TURNS.get(session_id)
    if control is None:
        return False
    if only_message_id is not None and control.user_msg_id != only_message_id:
        return False
    _ACTIVE_TURNS.pop(session_id, None)
    control.cancel_work(flag)
    await asyncio.to_thread(control.settle, flag)
    return True


async def _register_turn(control: _TurnControl) -> None:
    """Make `control` its session's turn — unless a newer question already is.

    Two requests for one session interleave at their awaits, so the one whose
    question was stored later is the newer turn, whichever gets here first
    (T1: a late registration used to replace the newer turn's control, and
    a Stop for the newer question then found the wrong turn). An older turn
    already registered is cut as superseded; an older newcomer is cut at
    birth and never reaches the model.
    """
    current = _ACTIVE_TURNS.get(control.session_id)
    if current is not None and (current.user_msg_id or 0) > (control.user_msg_id or 0):
        control.cancel_work(_FLAG_SUPERSEDED)
        await asyncio.to_thread(control.settle, _FLAG_SUPERSEDED)
        return
    _ACTIVE_TURNS[control.session_id] = control
    if current is not None:
        current.cancel_work(_FLAG_SUPERSEDED)
        await asyncio.to_thread(current.settle, _FLAG_SUPERSEDED)


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
    loop = asyncio.get_running_loop()
    # Their own threads, never asyncio's default executor: that one runs every
    # sqlite call and retrieval in the app, and a model call held by the
    # provider used to sit on it (G4). Awaited with a deadline — past it the
    # question is searched broadly and unrewritten, never left waiting.
    classify = loop.run_in_executor(_AUX_CALLERS, classify_domains, query_text)
    rewrite = loop.run_in_executor(
        _AUX_CALLERS,
        functools.partial(rewrite_query, query_text, classifier_fast_path=fast_path),
    )
    await asyncio.wait({classify, rewrite}, timeout=_AUX_WAIT_S)
    domains = classify.result() if classify.done() and not classify.exception() \
        else list(UNCERTAIN_DOMAINS)
    rewritten = rewrite.result() if rewrite.done() and not rewrite.exception() else ""
    if not (classify.done() and rewrite.done()):
        logger.warning("classifier/rewriter still waiting after %.0fs — answering without them",
                       _AUX_WAIT_S)
    return domains, rewritten


async def _tag_user_message(
    message_id: int | None, domain: str, severity: str
) -> None:
    """Backfill the classification onto the stored user question.

    The question row is written before classification so it survives a failed
    answer; this puts the domain/severity back on it once they exist. Telemetry
    must never break the answer, so a write failure is logged, not raised.
    """
    if message_id is None:
        return
    try:
        await asyncio.to_thread(
            store.update_classification,
            message_id, domain=domain, severity=severity,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("tagging user message %s failed: %s", message_id, exc)


def _record_failed_turn(session_id: str | None, flag: str, *,
                        severity: str = "", lang: str = "ar") -> None:
    """Store the apology as the turn and count why. Synchronous, like
    _persist in _stream_answer: callers run it via to_thread or inline."""
    try:
        if session_id:
            store.add_message(
                session_id, "assistant", _error_text(lang),
                severity=severity or None, mode="error",
            )
        log_session(
            domain="", behavior_type="", age_group="", severity=severity,
            mode="error", needs_human_review=False, reply_length=0,
            retrieved_count=0, flag=flag,
        )
    except Exception as exc:  # noqa: BLE001 — never mask the original failure
        logger.warning("recording the failed turn failed: %s", exc)


def _redact_turns(history, names: tuple[str, ...]):
    """History turns with the family's child names replaced (see privacy.py)."""
    return [
        t.model_copy(update={"content": redact_with_names(t.content, names)})
        for t in history
    ]


async def _memory_context(caller_device, user_message: UserMessage, query_text: str):
    """(child_id, facts block, facts used) — off the event loop, never raises."""
    return await asyncio.to_thread(
        child_memory.prompt_context, caller_device,
        child_id=user_message.child_id, age_group=user_message.age_group,
        question=query_text,
    )


def _remember(caller_device, child_id, query_text: str, answer: str,
              age_group: str | None) -> None:
    """Hand the finished turn to the background extractor. Fire-and-forget:
    submitting is microseconds, and nothing downstream waits on it."""
    if child_id is None or not answer:
        return
    child_memory.schedule_extraction(
        caller_device, child_id, question=query_text, answer=answer,
        age_group=age_group or "",
    )


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/draft", response_model=AssistantReply)
async def draft_reply(request: Request, user_message: UserMessage):
    policies = request.app.state.guardrails_config
    # The caller's own device: cloud redaction and the answer cache are scoped
    # to THIS family's children (audit M4/M5).
    caller_device = getattr(request.state, "device_id", None)

    # ── Session: validate + persist the incoming user message ────────
    # NB: every sqlite / model-inference call below goes through
    # asyncio.to_thread — this handler must never block the event loop
    # (single uvicorn worker; a blocked loop freezes /health too).
    session_id = user_message.session_id
    user_msg_id: int | None = None
    if session_id:
        await _require_owned_session(request, session_id)
        # Any answer still being produced for this session is cut first, so
        # its row lands before this question (see cut_pending_turn).
        await cut_pending_turn(session_id, _FLAG_SUPERSEDED)
        user_msg_id = await asyncio.to_thread(
            store.add_message,
            session_id, "user",
            user_message.message_text or user_message.behavior_type or "",
        )

    try:
        return await _draft_answer(
            user_message, policies, caller_device, session_id, user_msg_id,
        )
    except HTTPException:
        raise
    except Exception:
        # The question row is already written: leave a reply row behind it,
        # or the failure is indistinguishable from a parent who walked away.
        logger.exception("draft pipeline failed (session=%s)", session_id)
        await asyncio.to_thread(
            functools.partial(
                _record_failed_turn, session_id, _FLAG_PIPELINE_ERROR,
                lang=detect_reply_language(user_message.message_text or ""),
            ),
        )
        raise


async def _draft_answer(
    user_message: UserMessage, policies: dict, caller_device: str | None,
    session_id: str | None, user_msg_id: int | None,
) -> AssistantReply:
    """/draft after the question is stored: guards → retrieval → LLM."""
    # ── Step 0: Banned intent check ──────────────────────────────────
    query_input = user_message.message_text or user_message.behavior_type or ""
    # A parent afraid of hurting their child («أخاف أؤذي طفلي لما أضربه») trips the
    # banned first-person-harm pairs; they need support, not a closed door. Checked
    # first — but never ahead of an emergency.
    if (check_physical_discipline(query_input) == "self_worry"
            and not check_emergency_keywords(query_input)):
        reply = discipline_reply("self_worry", query_input)
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        return await asyncio.to_thread(_finalize, reply, session_id)
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
        # These two paths return before the classifier ever runs, so without
        # this the question rows that matter most — banned and emergency —
        # would be the ones left unlabelled.
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        return await asyncio.to_thread(_finalize, reply, session_id)

    # ── Step 0a: Abusive language refusal (firm, polite boundary, no LLM) ──
    is_abusive, matched_abusive = check_abusive_language(query_input)
    if is_abusive:
        logger.warning("Abusive language detected: %s", matched_abusive)
        reply = AssistantReply(
            reply_text="نعتذر، لا نقبل العبارات المسيئة أو غير اللائقة. المساعد مخصص للإرشاد التربوي والأسري فقط.",
            domain="general",
            severity="خفيف",
            needs_human_review=False,
            escalation_target=None,
            mode="refusal",
        )
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        return await asyncio.to_thread(_finalize, reply, session_id)

    # ── Step 0c: Conversational shortcut (thanks/greetings — zero latency, no unprompted activity) ──
    is_conv, conv_reply = check_conversational_shortcut(
        query_input, detect_reply_language(query_input),
    )
    if is_conv:
        reply = AssistantReply(
            reply_text=conv_reply,
            domain="general",
            severity="خفيف",
            needs_human_review=False,
            escalation_target=None,
            mode="conversational",
        )
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        return await asyncio.to_thread(_finalize, reply, session_id)

    # ── Step 0b: Emergency keyword check ─────────────────────────────
    if check_emergency_keywords(query_input):
        logger.info("Emergency keyword detected in message_text")
        user_message = user_message.model_copy(update={"severity": "طارئ"})

    # ── Step 1: Emergency severity check ─────────────────────────────
    # Runs BEFORE the fiqh guard: «ابني بيقول عايز ينتحر بعد الطلاق» matches
    # both, and a parent disclosing a child's suicidal talk must get the
    # emergency escalation, never the "ask a religious authority" deflection.
    if is_emergency(user_message):
        logger.info("Emergency severity — returning fallback immediately")
        reply = emergency_reply(user_message, policies)
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        return await asyncio.to_thread(_finalize, reply, session_id)

    # ── Step 1a: Physical discipline — the clearest cases only ───────
    # «هل أضرب ابني لأنه لا يصلي؟» gets the ruling deferred to scholars and the
    # app's non-physical alternatives; bodily harm described gets the safety
    # reply. Deliberately narrow (discipline_guard.py): everything else goes to
    # the model, which carries the same no-hitting policy. After the emergency
    # check, before the fiqh guard (whose generic deflection gives no alternative).
    discipline = check_physical_discipline(query_input)
    if discipline:
        logger.info("Discipline guard: %s", discipline)
        reply = discipline_reply(discipline, query_input)
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        return await asyncio.to_thread(_finalize, reply, session_id)

    # ── Step 1b: FIQH guard (hard block — FIQH_GUARD.md v3) ───────────
    fiqh_blocked, fiqh_rule = await asyncio.to_thread(check_fiqh_guard, query_input, caller_device)
    if fiqh_blocked:
        logger.warning("FIQH guard block: rule=%s", fiqh_rule)
        reply = AssistantReply(
            reply_text=FIQH_SAFE_REPLY,
            domain="fiqh_aqeedah",
            severity="عادي",
            needs_human_review=False,
            mode="fiqh_guard",
        )
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        return await asyncio.to_thread(_finalize, reply, session_id)

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
    # Every text that leaves for a model has the family's child names
    # replaced first. The primary provider is a cloud API, so "the cloud
    # tier" is every tier — the classifier and rewriter calls included.
    names = await asyncio.to_thread(names_for_device, caller_device)
    llm_query = redact_with_names(query_text, names)
    llm_history = _redact_turns(history, names)
    # Both can make a model call (seconds) on a keyword fast-path miss, and
    # they are independent — so they run together, not one after the other.
    detected_domains, rewritten_query = await _classify_and_rewrite(llm_query)
    is_general = detected_domains == ["general"]
    logger.info("Auto-detected domains: %s", detected_domains)

    primary_domain = _label_domain(detected_domains, [])
    severity = user_message.severity or "خفيف"
    await _tag_user_message(user_msg_id, primary_domain, severity)

    # ── Step 3b: Pre-cache check ─────────────────────────────────────
    # Skipped when classification failed: the cache key contains the domain,
    # so looking up under a guessed one can only mislead.
    first_question = not any(
        getattr(t, "role", "") == "assistant" for t in history
    )
    # A question naming the family's own child gets a personalised answer:
    # never serve it from, or store it into, the cross-family cache (M5).
    # Neither does one we have remembered facts for: a cached answer cannot
    # know that the strategy it recommends already failed for this child.
    mem_child, mem_block, mem_used = await _memory_context(
        caller_device, user_message, query_text)
    personal = mentions_any(query_text, names) or mem_used > 0
    if (first_question and not personal and not is_general
            and not is_uncertain(detected_domains)):
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
                lang=detect_query_language(query_text),
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
        ayah_task = asyncio.create_task(resolve_ayah_reference(query_text))
        retrieved_units = await asyncio.to_thread(_retrieve_blocking)
        ayah_ref = await ayah_task
        if ayah_ref:
            tafsir_task = asyncio.create_task(
                fetch_tafsir(ayah_ref[0], ayah_ref[1])
            )
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
                llm_query, user_message.age_group or "unspecified"
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
        try:
            generated = await generate_reply(
                domain=primary_domain,
                behavior_type=user_message.behavior_type or "",
                age_group=user_message.age_group or "unspecified",
                severity=user_message.severity or "خفيف",
                retrieved_units=retrieved_units,
                question_text=llm_query,
                conversation_history=llm_history,
                tier=tier,
                route_reason=route_reason,
                child_context=mem_block,
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
        # The app's "Sources (n)" disclosure. Grounded answers only: a pivot
        # answer is told not to cite, and an empty retrieval has nothing to cite.
        "sources": reply_sources(retrieved_units)
        if mode in ("llm_generated", "retrieval_only") else [],
        # Which child the answer was personalised for, and with how many
        # remembered facts (0 = none used). Additive; old clients ignore it.
        "child_id": mem_child,
        "memory_facts_used": mem_used if mode == "llm_generated" else 0,
    }
    if mode == "llm_generated" and not reply.needs_human_review:
        _remember(caller_device, mem_child, query_text, reply.reply_text,
                  user_message.age_group)

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


async def _require_owned_session(request: Request, session_id: str) -> None:
    """404 unless the session exists AND belongs to the calling device.

    Existence alone used to be the check, so any authenticated device could
    name another device's session_id: its history was read into the prompt and
    the new turn was written into it. Same rule as GET /api/chat/sessions/{id}
    (a session with no recorded owner stays reachable), but answered with 404
    rather than 403 so a foreign id is indistinguishable from a missing one —
    and the mobile client already recovers from 404 by opening a new session.
    """
    exists, owner = await asyncio.to_thread(store.session_owner, session_id)
    caller = getattr(request.state, "device_id", None)
    if not exists or (owner and owner != caller):
        raise HTTPException(status_code=404, detail="Session not found")


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
        event: turn    data: {"message_id": N}       (first, when the question
                                                      was stored — since 2026-10)
        event: token   data: {"delta": "..."}      (0+ times, LLM tokens)
        event: done    data: {<full AssistantReply>} (always, terminal)
        event: error   data: {"detail": "..."}       (on failure)

    A client that leaves mid-answer does not cancel it: the answer's row is
    reserved and the server finishes it (see event_stream). A new question in
    the same session, or POST /api/chat/sessions/{id}/stop, cuts it instead.

    Safety: all guardrail/banned/emergency decisions run BEFORE any token is
    sent (you can't un-send a streamed token). Banned/emergency/no-context/
    force-fallback replies are emitted as a single `done` event (not streamed).
    """
    policies = request.app.state.guardrails_config
    # The caller's own device: cloud redaction and the answer cache are scoped
    # to THIS family's children (audit M4/M5).
    caller_device = getattr(request.state, "device_id", None)
    session_id = user_message.session_id

    # ── Session: validate + persist incoming user message ────────────
    # Both calls go through to_thread like /draft does: a sqlite lock or
    # commit on the event loop stalls every other request this worker holds,
    # including the streams already in flight.
    user_msg_id: int | None = None
    control: _TurnControl | None = None
    if session_id:
        await _require_owned_session(request, session_id)
        # Any answer still being produced for this session is cut first, so
        # its row lands before this question (see cut_pending_turn).
        await cut_pending_turn(session_id, _FLAG_SUPERSEDED)
        user_msg_id = await asyncio.to_thread(
            store.add_message,
            session_id, "user",
            user_message.message_text or user_message.behavior_type or "",
        )
        control = _TurnControl(session_id, user_msg_id)
        await _register_turn(control)

    lang = detect_reply_language(user_message.message_text or "")
    work = asyncio.create_task(_stream_answer(
        user_message, policies, caller_device, session_id, user_msg_id, control,
    ))
    _PIPELINES.add(work)
    work.add_done_callback(_PIPELINES.discard)
    return StreamingResponse(
        _relay(work, control, user_msg_id, session_id, lang),
        media_type="text/event-stream", headers=_SSE_HEADERS,
    )


async def _relay(work: "asyncio.Task", control: _TurnControl | None,
                 user_msg_id: int | None, session_id: str | None, lang: str):
    """The SSE body: the `turn` frame at once, then the answer.

    T2 — the frame used to come only after classification and retrieval, so
    a Stop pressed in those seconds had no question id to name and never
    reached the server. Keep-alives cover the wait. If the reader leaves
    before the answer begins, the pipeline still finishes and its answer is
    produced detached (background completion), exactly as after a cut
    mid-answer; if it leaves mid-answer, closing the inner stream does that.
    """
    inner = None
    try:
        if user_msg_id is not None:
            yield _turn_frame(user_msg_id)
        while not work.done():
            done, _ = await asyncio.wait({work}, timeout=_STREAM_KEEPALIVE_S)
            if not done:
                yield _SSE_KEEPALIVE
        try:
            response = work.result()
        except Exception as exc:  # noqa: BLE001 — answered below, never a bare 500
            await _pipeline_failed(exc, control, session_id, lang)
            yield _sse("error", {"detail": _error_text(lang)})
            return
        inner = response.body_iterator
        async for frame in inner:
            yield frame
        inner = None
    finally:
        if inner is not None:
            await inner.aclose()  # the reader left mid-answer
        elif not work.done():
            if control is not None:
                control.reader_gone = True
            work.add_done_callback(functools.partial(_detached, control, session_id, lang))


def _detached(control: _TurnControl | None, session_id: str | None, lang: str,
              work: "asyncio.Task") -> None:
    """The pipeline finished after its reader left: produce the answer anyway."""
    loop = asyncio.get_running_loop()
    if work.cancelled():
        return
    exc = work.exception()
    if exc is not None:
        task = loop.create_task(_pipeline_failed(exc, control, session_id, lang))
    else:
        task = loop.create_task(_drain(work.result()))
    _BACKGROUND_COMPLETIONS.add(task)
    task.add_done_callback(_BACKGROUND_COMPLETIONS.discard)


async def _drain(response: StreamingResponse) -> None:
    async for _ in response.body_iterator:
        pass


async def _pipeline_failed(exc: BaseException, control: _TurnControl | None,
                           session_id: str | None, lang: str) -> None:
    """Everything between the stored question and the first token used to end
    as a bare 500 with no reply row — in the data, the same as a parent who
    walked away. Now it is a stored, counted error turn."""
    logger.error("stream pipeline failed before streaming (session=%s)", session_id,
                 exc_info=(type(exc), exc, exc.__traceback__))
    if control is not None:
        control.release()
    await asyncio.to_thread(functools.partial(
        _record_failed_turn, session_id,
        f"{_FLAG_PIPELINE_ERROR}:{type(exc).__name__}", lang=lang,
    ))


async def _stream_answer(
    user_message: UserMessage, policies: dict, caller_device: str | None,
    session_id: str | None, user_msg_id: int | None,
    control: _TurnControl | None = None,
) -> StreamingResponse:
    """/stream after the question is stored: guards → retrieval → SSE."""

    async def _single(reply: AssistantReply) -> StreamingResponse:
        """Emit a non-streamed reply as one terminal `done` event."""
        if control is not None and control.cut:
            # Cut while it was being worked out: writing it now would put it
            # after the newer question.
            control.release()

            def nothing():
                return
                yield  # noqa: B901 — an empty generator
            return StreamingResponse(nothing(), media_type="text/event-stream",
                                     headers=_SSE_HEADERS)
        # Banned and emergency return through here, before the classifier
        # runs — tag the question from the reply so the rows that matter
        # most are not the ones left unlabelled. Both writes go through
        # to_thread: this handler runs on the event loop.
        await _tag_user_message(user_msg_id, reply.domain, reply.severity)
        await asyncio.to_thread(_finalize, reply, session_id)
        if control is not None:
            control.release()

        def one():
            yield _sse("done", reply.model_dump())
        return StreamingResponse(one(), media_type="text/event-stream", headers=_SSE_HEADERS)

    # ── Pre-flight safety (identical order to /draft) ────────────────
    query_input = user_message.message_text or user_message.behavior_type or ""
    if (check_physical_discipline(query_input) == "self_worry"
            and not check_emergency_keywords(query_input)):
        return await _single(discipline_reply("self_worry", query_input))
    is_banned, matched = check_banned_intent(query_input)
    if is_banned:
        logger.warning("Banned intent detected (stream): %s", matched)
        return await _single(AssistantReply(
            reply_text="هذا الموضوع خارج نطاق ما يمكنني مساعدتك فيه. إذا كنت في حالة طارئة، يرجى التواصل مع الجهات المختصة فوراً.",
            domain="medical", severity="طارئ", needs_human_review=True,
            escalation_target="emergency_services", mode="banned",
        ))

    is_abusive, matched_abusive = check_abusive_language(query_input)
    if is_abusive:
        logger.warning("Abusive language detected (stream): %s", matched_abusive)
        return await _single(AssistantReply(
            reply_text="نعتذر، لا نقبل العبارات المسيئة أو غير اللائقة. المساعد مخصص للإرشاد التربوي والأسري فقط.",
            domain="general", severity="خفيف", needs_human_review=False,
            mode="refusal",
        ))

    reply_lang = detect_reply_language(query_input)
    is_conv, conv_reply = check_conversational_shortcut(query_input, reply_lang)
    if is_conv:
        return await _single(AssistantReply(
            reply_text=conv_reply,
            domain="general", severity="خفيف", needs_human_review=False,
            mode="conversational",
        ))

    # Emergency before the fiqh guard — same order and reason as /draft.
    if check_emergency_keywords(query_input):
        user_message = user_message.model_copy(update={"severity": "طارئ"})
    if is_emergency(user_message):
        return await _single(emergency_reply(user_message, policies))

    # Physical discipline — same place and reason as /draft.
    discipline = check_physical_discipline(query_input)
    if discipline:
        logger.info("Discipline guard (stream): %s", discipline)
        return await _single(discipline_reply(discipline, query_input))

    # ── FIQH guard (hard block — FIQH_GUARD.md v3) ────────────────────
    fiqh_blocked, fiqh_rule = await asyncio.to_thread(check_fiqh_guard, query_input, caller_device)
    if fiqh_blocked:
        logger.warning("FIQH guard block (stream): rule=%s", fiqh_rule)
        return await _single(AssistantReply(
            reply_text=FIQH_SAFE_REPLY,
            domain="fiqh_aqeedah", severity="عادي", needs_human_review=False,
            mode="fiqh_guard",
        ))

    # ── Build query + history + retrieve ─────────────────────────────
    query_text = (user_message.message_text or "").strip() or \
        f"{user_message.behavior_type} {user_message.age_group}"
    if session_id:
        history = await asyncio.to_thread(store.get_history, session_id, limit=6)
    else:
        history = user_message.conversation_history or []
    # Names out of every model-bound text — see /draft.
    names = await asyncio.to_thread(names_for_device, caller_device)
    llm_query = redact_with_names(query_text, names)
    llm_history = _redact_turns(history, names)
    # Concurrent, not sequential — see _classify_and_rewrite. This is the path
    # the mobile app uses, so the round-trip saved here is one the user feels.
    detected_domains, rewritten_query = await _classify_and_rewrite(llm_query)
    is_general = detected_domains == ["general"]

    primary_domain = _label_domain(detected_domains, [])
    severity = user_message.severity or "خفيف"
    await _tag_user_message(user_msg_id, primary_domain, severity)

    # First question in the session? (no assistant turns yet). Only then may
    # the answer cache serve/store — a follow-up depends on conversation the
    # cache never saw. (§5.1 كاش الأسئلة المتكررة)
    first_question = not any(
        getattr(t, "role", "") == "assistant" for t in history
    )

    # ── Step 3b: Pre-cache check (skipped on a guessed domain — see /draft) ──
    # Remembered facts make an answer personal, exactly like a name does.
    mem_child, mem_block, mem_used = await _memory_context(
        caller_device, user_message, query_text)
    personal = mentions_any(query_text, names) or mem_used > 0
    if (first_question and not personal and not is_general
            and not is_uncertain(detected_domains)):
        decision = evaluate_guardrails(primary_domain, severity, policies)
        if not decision["force_fallback"]:
            cached = await asyncio.to_thread(
                answer_cache.lookup,
                query_text, user_message.age_group or "unspecified",
                primary_domain, severity
            )
            if cached:
                logger.info("Cache hit in stream! Serving pre-cached answer.")
                return await _single(AssistantReply(
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
                lang=detect_query_language(query_text),
            )
            log_retrieval(query_text, detected_domains, rewritten_query, units)
            return units

        # ── Tafsir MCP enrichment (same logic as /draft) ────────────────
        ayah_task = asyncio.create_task(resolve_ayah_reference(query_text))
        retrieved_units = await asyncio.to_thread(_retrieve_blocking)
        ayah_ref = await ayah_task
        if ayah_ref:
            tafsir_task = asyncio.create_task(
                fetch_tafsir(ayah_ref[0], ayah_ref[1])
            )
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

    # Re-label from the retrieved evidence when classification was uncertain.
    primary_domain = _label_domain(detected_domains, retrieved_units)

    score_off_topic, _top_rerank = _off_topic(retrieved_units)
    off_topic = is_general or score_off_topic

    # No relevant KB and not an off-topic pivot → non-streamed fallback
    if not retrieved_units and not off_topic:
        draft = f"لا توجد معلومات كافية حاليًا حول '{query_text}'. نوصي باستشارة مختص."
        return await _single(apply_guardrails(
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
            llm_query, user_message.age_group or "unspecified"
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
                is_emergency_case=(decision.get("escalate_to") == "emergency_services" or severity == "طارئ"),
            )
            return await _single(AssistantReply(
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
        full_prompt, _source = build_full_prompt(
            domain=primary_domain, behavior_type=user_message.behavior_type or "",
            age_group=user_message.age_group or "unspecified", severity=severity,
            retrieved_units=retrieved_units, question_text=llm_query,
            conversation_history=llm_history, tier=tier,
            child_context=mem_block,
        )

    async def event_stream():
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        # Everything the model has produced for this answer — what the parent
        # saw live, plus what a background completion added after they left.
        sent_parts: list[str] = []
        persisted = False
        reserved_id: int | None = None
        persist_lock = threading.Lock()
        cancel = threading.Event()
        tracker = StreamTracker()
        background: asyncio.Task | None = None
        cut_flag = ""  # set before a deliberate cut cancels the work
        started = time.monotonic()
        last_token_at: float | None = None
        # How many of sent_parts the parent actually received before leaving;
        # None while they are still reading. A cut keeps only that much (T7):
        # what a background completion added after they left was never shown.
        seen_count: int | None = None
        # The finished answer, set BEFORE it is written: if the reader leaves
        # during that write, the background completion stores this instead of
        # a partial.
        pending_final: tuple[str, str] | None = None

        if control is not None and control.cut:
            # T1 — cut (a newer question, Stop) while it was still being
            # worked out: the model is never started for it.
            control.release()
            return

        def _emit(kind, value):
            try:
                loop.call_soon_threadsafe(q.put_nowait, (kind, value))
            except RuntimeError:
                pass  # loop already closed (shutdown) — nobody is listening

        # Blocking stream reader on the dedicated LLM pool (see _pump_stream).
        # Keep a reference to the future so it is not garbage-collected. The
        # cancel flag goes into the gateway too: a cut turn closes its request
        # on the next line and is never handed to a fallback model (R1).
        worker = loop.run_in_executor(
            _STREAM_EXECUTOR,
            _pump_stream,
            lambda: get_gateway().stream(
                full_prompt, tier=tier, route_reason=route_reason, tracker=tracker,
                should_stop=cancel.is_set,
            ),
            _emit,
            cancel,
        )

        def _log(mode: str, flag: str, length: int) -> None:
            try:
                log_session(
                    domain=primary_domain, behavior_type=user_message.behavior_type or "",
                    age_group=user_message.age_group or "", severity=severity,
                    mode=mode, needs_human_review=decision["needs_human_review"],
                    reply_length=length, retrieved_count=len(retrieved_units),
                    flag=flag,
                )
            except Exception as exc:  # noqa: BLE001 — telemetry only
                logger.warning("turn telemetry failed: %s", exc)

        def _persist(text: str, mode: str, flag: str = "") -> None:
            """Record the assistant turn — a new row, or the row reserved when
            the reader left. Synchronous on purpose.

            Also called from `finally` blocks, which may run while the task is
            being cancelled — `asyncio.to_thread` would just raise
            CancelledError again there, so the (millisecond) sqlite write is
            done inline instead.
            """
            nonlocal persisted
            # Several writers can race here — the reply's own to_thread write,
            # a background completion, a new question cutting the turn — and
            # exactly one must win.
            with persist_lock:
                if persisted:
                    return
                persisted = True
                rid = reserved_id
            try:
                if session_id:
                    if rid is not None:
                        store.update_reply(rid, content=text, mode=mode)
                    else:
                        store.add_message(
                            session_id, "assistant", text,
                            domain=primary_domain, severity=severity, mode=mode,
                            needs_human_review=decision["needs_human_review"],
                        )
                _log(mode, flag, len(text))
            except Exception as exc:  # noqa: BLE001
                logger.warning("persisting %s turn failed: %s", mode, exc)

        def _reserve() -> None:
            """The reader left mid-answer: write the answer's row NOW, with
            what the parent saw, as 'interrupted'.

            The background completion fills it in later. Inserting only at
            the end let a question asked meanwhile land first — Q1, Q2, A1 —
            so A1 showed under Q2 and Q2's prompt never saw A1.
            """
            nonlocal reserved_id
            if not session_id:
                return
            with persist_lock:
                if persisted or reserved_id is not None:
                    return
                try:
                    # 'pending' (T5): still being written — the app keeps
                    # looking until it turns into the answer or 'interrupted'.
                    reserved_id = store.add_message(
                        session_id, "assistant", _seen_text(),
                        domain=primary_domain, severity=severity, mode="pending",
                        needs_human_review=decision["needs_human_review"],
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("reserving the reply row failed: %s", exc)

        def _settle_cut(flag: str) -> None:
            """End the turn without a full answer: keep what was produced (as
            'interrupted') or, if nothing was, no row at all — and count why."""
            nonlocal persisted
            with persist_lock:
                if persisted:
                    return
                persisted = True
                rid = reserved_id
            partial = _seen_text()
            try:
                if session_id:
                    if rid is not None:
                        if partial:
                            store.update_reply(rid, content=partial, mode="interrupted")
                        else:
                            store.discard_reply(rid)
                    elif partial:
                        store.add_message(
                            session_id, "assistant", partial,
                            domain=primary_domain, severity=severity, mode="interrupted",
                            needs_human_review=decision["needs_human_review"],
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("settling the cut turn failed: %s", exc)
            _log("interrupted" if partial else "abandoned", flag, len(partial))

        def _seen_text() -> str:
            parts = sent_parts if seen_count is None else sent_parts[:seen_count]
            return "".join(parts).strip()

        def _cancel_work(flag: str) -> None:
            nonlocal cut_flag
            cut_flag = flag
            cancel.set()
            # A reader still connected hears now that nothing more comes —
            # not at the model's next token, which a held or slow model may
            # not send for a minute.
            q.put_nowait(("cancelled", None))
            if background is not None and not background.done():
                background.cancel()

        def _release() -> None:
            if control is not None:
                control.release()

        if control is not None:
            control.attach(_cancel_work, _settle_cut)

        def _final_text(chunk) -> str:
            text = (chunk.result.text if chunk.result else "").strip()
            if stream_mode == "general_pivot":
                text = strip_pivot_citation(text)
            return clean_model_output(text)

        async def _complete_after_disconnect() -> None:
            """Finish an answer whose reader left, and store it whole.

            Older app builds close the stream when the phone goes to the
            background or the notification shade comes down, and the answer
            used to be cancelled with it: 23 of 290 questions in September
            ended as a few words and «تم الإيقاف». The model is mid-answer
            and the app reloads the conversation from the server, so the
            answer is finished into the row _reserve() wrote. Bounded by the
            same per-attempt limits as a live stream; a stall here is charged
            to the provider that was streaming, like a live one.
            """
            nonlocal last_token_at
            outcome = ""
            try:
                while not persisted:
                    try:
                        kind, val = await asyncio.wait_for(q.get(), timeout=_STREAM_KEEPALIVE_S)
                    except asyncio.TimeoutError:
                        flag = _stall_flag(time.monotonic(), started, tracker, last_token_at)
                        if flag:
                            get_gateway().note_stream_stall(tracker)
                            outcome = flag
                            break
                        continue
                    if kind == "error":
                        outcome = f"stream_error:{type(val).__name__}"
                        break
                    if kind != "chunk":
                        outcome = outcome or "stream_error:no_final"
                        break
                    if val.done:
                        text = _final_text(val)
                        if text:
                            await asyncio.to_thread(
                                _persist, text, stream_mode, _FLAG_COMPLETED_AFTER_DISCONNECT,
                            )
                        else:
                            outcome = "stream_error:empty"
                        break
                    if val.delta:
                        last_token_at = time.monotonic()
                        sent_parts.append(_CJK_RE.sub("", val.delta))
            except asyncio.CancelledError:
                outcome = cut_flag or "cancelled"
            except Exception as exc:  # noqa: BLE001
                outcome = f"stream_error:{type(exc).__name__}"
            finally:
                if not persisted and pending_final is not None:
                    _persist(*pending_final)
                if not persisted:
                    _settle_cut(cut_flag or outcome or _FLAG_CLIENT_LEFT)
                cancel.set()
                worker.cancel()
                _release()

        # Stays True only when the generator is closed under us — the client
        # went away. Any way out of the loop below means a reader was there.
        reader_gone = True
        try:
            if control is not None and control.reader_gone:
                return  # nobody to stream to: finish it detached (finally)
            while True:
                try:
                    msg_type, val = await asyncio.wait_for(
                        q.get(), timeout=_STREAM_KEEPALIVE_S
                    )
                except asyncio.TimeoutError:
                    # Silence is fine for a while (retrieval, a cold fallback
                    # model) — but not forever. See _stall_flag.
                    now = time.monotonic()
                    flag = _stall_flag(now, started, tracker, last_token_at)
                    if flag:
                        get_gateway().note_stream_stall(tracker)
                        raise _StreamStalled(flag, now - (last_token_at or started))
                    yield _SSE_KEEPALIVE
                    continue
                if msg_type in ("done", "cancelled"):
                    break
                elif msg_type == "error":
                    raise val
                else:
                    chunk = val
                    if chunk.done:
                        final_text = _final_text(chunk)
                        pending_final = (final_text, stream_mode)
                        reply = AssistantReply(
                            reply_text=final_text, domain=primary_domain, severity=severity,
                            needs_human_review=decision["needs_human_review"],
                            escalation_target=decision["escalate_to"],
                            mode=stream_mode, session_id=session_id,
                            metadata={
                                "sources": reply_sources(retrieved_units)
                                if stream_mode == "llm_generated" else [],
                                "child_id": mem_child,
                                "memory_facts_used": mem_used
                                if stream_mode == "llm_generated" else 0,
                            },
                        )
                        truncated = chunk.result.truncated if chunk.result else None
                        await asyncio.to_thread(
                            _persist, final_text, stream_mode,
                            f"truncated:{truncated}" if truncated else "",
                        )
                        # Learn from the finished turn — after it is saved,
                        # before the done frame, and without waiting: the
                        # extractor runs on its own pool (child_memory).
                        if (stream_mode == "llm_generated"
                                and not decision["needs_human_review"]):
                            _remember(caller_device, mem_child, query_text,
                                      final_text, user_message.age_group)
                        # Feed the answer cache: grounded, local, review-free,
                        # first-question answers only (§5.1) — and only whole
                        # ones: an answer cut by max_tokens or a filter (R3)
                        # would be served to every parent who asks the same.
                        if (
                            stream_mode == "llm_generated"
                            and first_question
                            and not personal
                            and tier != "cloud_quality"
                            and not decision["needs_human_review"]
                            and not truncated
                        ):
                            await asyncio.to_thread(
                                answer_cache.store,
                                query_text, user_message.age_group or "unspecified",
                                primary_domain, severity, final_text,
                            )
                        yield _sse("done", reply.model_dump())
                    elif chunk.delta:
                        last_token_at = time.monotonic()
                        # Filter leaked CJK tokens from the live stream too.
                        delta = _CJK_RE.sub("", chunk.delta)
                        sent_parts.append(delta)
                        yield _sse("token", {"delta": delta})
            reader_gone = False
        except Exception as exc:
            reader_gone = False
            failure_flag = getattr(exc, "flag", "") or f"stream_error:{type(exc).__name__}"
            logger.exception("Stream generation failed (session=%s)", session_id)
            _persist(
                "".join(sent_parts).strip() or _error_text(reply_lang), "error",
                flag=failure_flag,
            )
            yield _sse("error", {"detail": _error_text(reply_lang)})
        finally:
            # Reached on client disconnect too, where the generator is closed
            # with CancelledError/GeneratorExit — neither is an Exception, so
            # the handler above never sees them. Without this, an answer the
            # parent watched stream in was dropped on the floor: no row, no
            # log, nothing. That silent path was 176 of 1,617 questions
            # (10.9%) as of 2026-08-13, and it is why they were undiagnosable.
            if not persisted and reader_gone and not cancel.is_set():
                seen_count = len(sent_parts)
                logger.warning(
                    "Stream reader left before completion (session=%s, chars=%d) "
                    "— finishing in the background",
                    session_id, len("".join(sent_parts)),
                )
                _reserve()
                try:
                    background = loop.create_task(_complete_after_disconnect())
                    _BACKGROUND_COMPLETIONS.add(background)
                    background.add_done_callback(_BACKGROUND_COMPLETIONS.discard)
                except RuntimeError:
                    # Loop shutting down: keep what the parent saw, as before.
                    _settle_cut(_FLAG_CLIENT_LEFT)
                    cancel.set()
                    worker.cancel()
                    _release()
            else:
                if not persisted:
                    # The turn was cut (new question / Stop) or the provider
                    # ended without a final answer.
                    _settle_cut(cut_flag or "stream_error:no_final")
                # Cooperative cancellation (audit H6): asyncio cannot interrupt
                # a running thread, so the worker checks this flag between
                # chunks, stops, and closes the stream generator — which closes
                # the provider connection.
                cancel.set()
                worker.cancel()
                _release()

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
        # Same filter as the generated path: a bare "medical" or a placeholder
        # is not a citation, so such a passage carries no source line at all.
        ref = usable_reference(u.get("metadata", {}).get("reference_info"))
        parts.append(f"{doc.strip()}\n📚 المصدر: {ref}" if ref else doc.strip())
    body = "\n\n".join(parts)
    footer = "\n\nملاحظة: يُنصح باستشارة مختص للحالات المستعصية."
    return header + body + footer
