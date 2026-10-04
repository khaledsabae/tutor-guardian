"""Unanswered questions — the September 2026 causes, one test per fix.

Production, 30 days to 2026-10-04: 44 of 290 parent questions (15.2%) ended
with no answer. 23 were cut by the app mid-answer, ~18 sat for 2–31 minutes
behind DeepSeek calls that ignored their 6–8 s "timeouts" (a per-READ limit
that keep-alive blank lines reset) while holding the event loop's default
thread pool, and the rest left no trace at all. Each test below targets one
of those mechanisms and fails on the code before the fix (checked against
origin/main in a detached worktree).

Names introduced by the fix are reached through the module (`ai_gateway.x`)
inside each test, never imported at the top — so on the old code a test fails
on its behaviour, not on a collection-time ImportError.
"""
from __future__ import annotations

import asyncio
import dataclasses
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import llm_config
from app.config.guardrails_loader import load_guardrails_config
from app.models.api import UserMessage
from app.routers import assistant
from app.services import ai_gateway, answer_cache
from app.services import conversation_store as store
from app.services.intent_guard import check_conversational_shortcut
from app.services.llm_service import build_pivot_prompt

_RELEASE = threading.Event()  # frees every provider thread a test left blocked


@pytest.fixture(autouse=True)
def _release_blocked_threads():
    _RELEASE.clear()
    yield
    _RELEASE.set()


# ── Fakes ──────────────────────────────────────────────────────────────────

class _HangingProvider:
    """A provider that holds the call open the way DeepSeek does when loaded:
    the per-read timeout never fires, the call just does not return."""

    name = "deepseek"
    model = "fake-hang"

    def __init__(self, timeout: float = 0.2, hang_s: float = 5.0) -> None:
        self.timeout = timeout
        self.hang_s = hang_s
        self.calls = 0

    def generate(self, prompt, *, options):
        self.calls += 1
        _RELEASE.wait(self.hang_s)
        return {"response": "متأخر جدًا", "done": True}


def _scripted_provider(script):
    """An Ollama stand-in whose stream follows `script`:
    ("token", text) | ("sleep", s) | ("hang", s)."""

    class _Scripted:
        name = "fake"
        model = "fake-model"

        def __init__(self, *a, **k):
            self.timeout = 60

        def stream(self, prompt, *, options):
            for kind, value in script:
                if kind == "token":
                    yield {"response": value, "done": False}
                elif kind == "sleep":
                    time.sleep(value)
                elif kind == "hang":
                    _RELEASE.wait(value)
            yield {"response": "", "done": True, "prompt_eval_count": 1, "eval_count": 1}

        def generate(self, prompt, *, options):
            return {"response": "رد قصير", "done": True}

    return _Scripted


_UNIT = {
    "unit_id": "u-medical-1",
    "document": "passage: نصيحة تربوية موثقة عن النوم.",
    "metadata": {"domain": "medical", "reference_info": "مرجع تربوي موثق",
                 "title": "النوم", "age_group": "4-6"},
    "rerank_score": 0.5,
    "distance": 0.2,
    "source_domain": "medical",
}


@pytest.fixture
def pipeline(monkeypatch):
    """The assistant pipeline minus its heavy parts: classification, cache,
    retrieval and telemetry are stubbed; the model is a scripted fake."""
    calls = SimpleNamespace(retrieve=[], sessions=[], domains=["medical"])

    async def _classify(query_text):
        return list(calls.domains), ""

    def _retrieve(**kwargs):
        calls.retrieve.append(kwargs)
        return [dict(_UNIT)]

    async def _no_ayah(_q):
        return None

    monkeypatch.setattr(assistant, "_classify_and_rewrite", _classify)
    monkeypatch.setattr(answer_cache, "lookup", lambda *a, **k: None)
    monkeypatch.setattr(answer_cache, "store", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "retrieve_hybrid", _retrieve)
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", _no_ayah)
    monkeypatch.setattr(assistant, "log_session", lambda **kw: calls.sessions.append(kw))
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "_STREAM_KEEPALIVE_S", 0.05)
    ai_gateway._gateway = None

    def use_script(script):
        monkeypatch.setattr(ai_gateway, "OllamaProvider", _scripted_provider(script))
        ai_gateway._gateway = None

    calls.use_script = use_script
    yield calls
    ai_gateway._gateway = None


def _client_with_session():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()
    # A fresh device per test: the in-process daily AI quota is per device and
    # outlives a single test.
    device = f"reliability-{uuid.uuid4().hex[:12]}"
    sess = client.post("/api/chat/sessions", json={"device_id": device}).json()
    client.headers["Authorization"] = f"Bearer {sess['token']}"
    return client, sess["session_id"]


def _rows(session_id: str) -> list[sqlite3.Row]:
    conn = store.get_conn()
    try:
        return conn.execute(
            "SELECT role, content, mode, domain FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()


def _ask(client, session_id, text="ابني لا ينام إلا متأخرًا، ماذا أفعل؟"):
    return client.post("/api/assistant/stream", json={
        "age_group": "4-6", "severity": "خفيف",
        "message_text": text, "session_id": session_id,
    })


def _flags(calls) -> list[str]:
    return [kw.get("flag", "") for kw in calls.sessions]


# ── 1. Wall-clock deadlines on blocking calls ──────────────────────────────

def test_aux_call_gives_up_at_a_wall_clock_deadline(monkeypatch):
    """The classifier's 8 s timeout let a call run 236 s: per-read timeouts
    restart on every keep-alive line. The caller must stop waiting anyway."""
    logged = []
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: logged.append(k))
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    provider = _HangingProvider(timeout=0.2, hang_s=5.0)

    t0 = time.monotonic()
    out = ai_gateway.aux_generate(provider, "صنّف", options={}, tier="classifier")
    elapsed = time.monotonic() - t0

    assert out is None  # the classifier's degraded path takes over
    assert elapsed < 1.5, f"waited {elapsed:.1f}s for a hung auxiliary call"
    assert logged and logged[-1].get("route_reason") == "deadline"


def test_blocking_generate_attempt_is_bounded(monkeypatch):
    """gateway.generate checked its 150 s deadline only BETWEEN attempts, so
    one hung attempt ran as long as the provider kept the socket (35 min on
    2026-09-14)."""
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [])
    gw = ai_gateway.AIGateway(provider=_HangingProvider(timeout=0.2, hang_s=5.0))

    t0 = time.monotonic()
    with pytest.raises(RuntimeError):
        asyncio.run(gw.generate("سؤال", max_retries=1))
    assert time.monotonic() - t0 < 1.5


def test_queued_call_behind_hung_ones_is_cancelled_not_run(monkeypatch):
    """When every LLM thread is stuck, a new call must still return at its
    deadline — and never start later, holding a thread for nobody."""
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    monkeypatch.setattr(ai_gateway, "_BLOCKING_LLM_EXECUTOR",
                        ThreadPoolExecutor(max_workers=1), raising=False)
    provider = _HangingProvider(timeout=0.2, hang_s=5.0)

    t0 = time.monotonic()
    assert ai_gateway.aux_generate(provider, "أ", options={}, tier="classifier") is None
    assert ai_gateway.aux_generate(provider, "ب", options={}, tier="classifier") is None
    assert time.monotonic() - t0 < 2.0

    _RELEASE.set()
    ai_gateway._BLOCKING_LLM_EXECUTOR.shutdown(wait=True)
    assert provider.calls == 1  # the queued second call never ran


# ── 2. Auxiliary calls get no SDK retries ─────────────────────────────────

def test_classifier_provider_has_no_sdk_retries(monkeypatch):
    """The OpenAI SDK retries twice by default, each retry restarting the
    per-read timeout — tripling a hang for a call whose fallback is free."""
    pytest.importorskip("openai")
    cfg = dataclasses.replace(
        llm_config.LLM, primary_provider="deepseek",
        deepseek_api_key="test-placeholder-not-a-key",
    )
    monkeypatch.setattr(ai_gateway, "LLM", cfg)
    monkeypatch.setattr(ai_gateway, "primary_budget_available", lambda name: True)
    from app.services import domain_classifier

    ai_gateway.aux_breaker.reset()
    provider = domain_classifier._classifier_provider()
    assert isinstance(provider, ai_gateway.OpenAIChatProvider)
    assert provider._client.max_retries == 0

    # The chat path keeps the SDK default: there a retry is worth a wait.
    primary = ai_gateway.OpenAIChatProvider(
        base_url=cfg.deepseek_base_url, api_key=cfg.deepseek_api_key,
        model=cfg.deepseek_model, timeout=60,
    )
    assert primary._client.max_retries == 2


# ── 3. The default executor cannot be starved by LLM calls ─────────────────

def _sqlite_ping() -> int:
    conn = store.get_conn()
    try:
        return conn.execute("SELECT 1").fetchone()[0]
    finally:
        conn.close()


def test_hung_classifier_calls_do_not_starve_sqlite(monkeypatch):
    """Classification runs aux calls from asyncio's default pool — the same
    pool every sqlite read/write and retrieval uses. Two hung calls on a
    two-thread pool used to freeze the whole assistant."""
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    provider = _HangingProvider(timeout=0.2, hang_s=5.0)

    async def scenario():
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=2))
        hung = [asyncio.create_task(asyncio.to_thread(
            ai_gateway.aux_generate, provider, "س", options={}, tier="classifier"))
            for _ in range(2)]
        await asyncio.sleep(0.05)
        ping = await asyncio.wait_for(asyncio.to_thread(_sqlite_ping), timeout=2.0)
        await asyncio.gather(*hung)
        return ping

    assert asyncio.run(scenario()) == 1


def test_blocking_generate_does_not_use_the_default_executor(monkeypatch):
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [])
    gw = ai_gateway.AIGateway(provider=_HangingProvider(timeout=3.0, hang_s=5.0))

    async def scenario():
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        gen = asyncio.create_task(gw.generate("سؤال", max_retries=1))
        await asyncio.sleep(0.05)
        ping = await asyncio.wait_for(asyncio.to_thread(_sqlite_ping), timeout=1.0)
        gen.cancel()
        return ping

    assert asyncio.run(scenario()) == 1


# ── 4. Stall limits on the stream ─────────────────────────────────────────

def test_stall_limits_default_to_75s_first_token_and_60s_between_tokens():
    assert assistant._FIRST_TOKEN_TIMEOUT_S == 75.0
    assert assistant._STREAM_STALL_S == 60.0


def test_no_first_token_ends_the_turn_with_an_error(pipeline, monkeypatch):
    """The SSE keep-alive defeats the app's 45 s idle check, so a provider
    that never sends a token kept the parent on «يكتب…» until DeepSeek gave
    up — up to 30 minutes on 2026-10-01."""
    monkeypatch.setattr(assistant, "_FIRST_TOKEN_TIMEOUT_S", 0.3, raising=False)
    pipeline.use_script([("hang", 3.0), ("token", "متأخر")])
    client, sid = _client_with_session()
    try:
        t0 = time.monotonic()
        resp = _ask(client, sid)
        elapsed = time.monotonic() - t0
    finally:
        client.__exit__(None, None, None)

    assert resp.status_code == 200
    assert "event: error" in resp.text and "event: done" not in resp.text
    assert elapsed < 2.5
    rows = _rows(sid)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["mode"] == "error"
    assert "first_token_timeout" in _flags(pipeline)


def test_tokens_that_stop_mid_answer_end_the_turn(pipeline, monkeypatch):
    monkeypatch.setattr(assistant, "_STREAM_STALL_S", 0.3, raising=False)
    pipeline.use_script([("token", "بداية الرد"), ("hang", 3.0), ("token", " ونهايته")])
    client, sid = _client_with_session()
    try:
        t0 = time.monotonic()
        resp = _ask(client, sid)
        elapsed = time.monotonic() - t0
    finally:
        client.__exit__(None, None, None)

    assert "event: error" in resp.text and "event: done" not in resp.text
    assert elapsed < 2.5
    rows = _rows(sid)
    assert rows[-1]["mode"] == "error"
    assert rows[-1]["content"] == "بداية الرد"  # what the parent saw stays
    assert "stream_stalled" in _flags(pipeline)


# ── 5. A failure before the first token leaves a reply row ─────────────────

def test_pre_stream_failure_stores_an_error_turn(pipeline, monkeypatch):
    """Anything that raised between the stored question and the first token
    was a bare 500 and a question with no reply — in the data, identical to
    a parent who walked away."""
    def _boom(**kwargs):
        raise RuntimeError("retrieval exploded")

    monkeypatch.setattr(assistant, "retrieve_hybrid", _boom)
    pipeline.use_script([("token", "لن يصل")])
    client, sid = _client_with_session()
    try:
        resp = _ask(client, sid)
    finally:
        client.__exit__(None, None, None)

    assert resp.status_code == 200
    assert "event: error" in resp.text
    rows = _rows(sid)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["mode"] == "error"
    assert any(f.startswith("pipeline_error:RuntimeError") for f in _flags(pipeline))


def test_draft_failure_stores_an_error_turn_and_still_fails(pipeline, monkeypatch):
    def _boom(**kwargs):
        raise RuntimeError("retrieval exploded")

    monkeypatch.setattr(assistant, "retrieve_hybrid", _boom)
    client, sid = _client_with_session()
    try:
        resp = client.post("/api/assistant/draft", json={
            "age_group": "4-6", "severity": "خفيف",
            "message_text": "ابني لا ينام إلا متأخرًا، ماذا أفعل؟", "session_id": sid,
        })
    finally:
        client.__exit__(None, None, None)

    assert resp.status_code == 500  # the API contract is unchanged
    rows = _rows(sid)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["mode"] == "error"


# ── 6. The answer survives the reader leaving ──────────────────────────────

def _request(device_id: str) -> Request:
    app = SimpleNamespace(state=SimpleNamespace(guardrails_config=load_guardrails_config()))
    return Request({
        "type": "http", "method": "POST", "path": "/api/assistant/stream",
        "headers": [], "query_string": b"", "app": app,
        "state": {"device_id": device_id},
    })


async def _leave_after(session_id: str, device_id: str, stop_at: str) -> list[str]:
    """Read the stream until `stop_at` appears, then close it the way
    Starlette does when the client disconnects; wait for any work the
    server keeps doing after that."""
    resp = await assistant.stream_reply(_request(device_id), UserMessage(
        age_group="4-6", severity="خفيف",
        message_text="ابني لا ينام إلا متأخرًا، ماذا أفعل؟", session_id=session_id,
    ))
    seen: list[str] = []
    gen = resp.body_iterator
    async for frame in gen:
        seen.append(frame)
        if stop_at in frame:
            break
    await gen.aclose()
    for _ in range(200):
        pending = list(getattr(assistant, "_BACKGROUND_COMPLETIONS", ()))
        if not pending:
            break
        await asyncio.gather(*pending, return_exceptions=True)
    return seen


def test_answer_is_finished_and_stored_after_the_reader_leaves(pipeline):
    """The app stopped the stream whenever the phone went to the background;
    the answer was cancelled with it (23 of 290 questions). The app reloads
    the conversation from the server on its next start — so finish it."""
    pipeline.use_script([
        ("token", "أولًا "), ("sleep", 0.15), ("token", "ثانيًا "),
        ("sleep", 0.15), ("token", "ثالثًا"),
    ])
    sid = store.create_session("leaver")
    seen = asyncio.run(_leave_after(sid, "leaver", "event: token"))

    assert any("event: token" in f for f in seen)
    assert not any("event: done" in f for f in seen)  # the reader really left early
    rows = _rows(sid)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["content"] == "أولًا ثانيًا ثالثًا"
    assert rows[1]["mode"] == "llm_generated"
    assert "completed_after_disconnect" in _flags(pipeline)
    assert store.get_history(sid)[-1].content == "أولًا ثانيًا ثالثًا"


def test_reader_gone_and_model_silent_is_counted_not_stored(pipeline, monkeypatch):
    """Left before the first word and the model never produced one: no blank
    bubble in the conversation, but the cause is recorded."""
    monkeypatch.setattr(assistant, "_FIRST_TOKEN_TIMEOUT_S", 0.3, raising=False)
    pipeline.use_script([("hang", 3.0), ("token", "متأخر")])
    sid = store.create_session("silent")
    asyncio.run(_leave_after(sid, "silent", ": keep-alive"))

    assert [r["role"] for r in _rows(sid)] == ["user"]
    assert "client_left_before_first_token" in _flags(pipeline)


# ── 7. Follow-ups stay in their conversation ──────────────────────────────

def _seed_answered_turn(session_id: str, domain: str, reply_mode: str) -> None:
    qid = store.add_message(session_id, "user", "ابني يرفض أداء الصلاة، كيف أشجعه؟")
    store.update_classification(qid, domain=domain, severity="خفيف")
    store.add_message(session_id, "assistant", "ابدأ بالقدوة والتحبيب.", mode=reply_mode)


def test_followup_classified_general_keeps_the_previous_topic(pipeline):
    """«وإذا رفض؟» has no topic words, so the classifier says general and the
    question went to the off-topic pivot with no history: 26% of follow-ups to
    a grounded answer, and where 10 of 18 linked 👎 ratings landed."""
    pipeline.domains = ["general"]
    pipeline.use_script([("token", "جرّب أن تصلي أمامه.")])
    client, sid = _client_with_session()
    try:
        _seed_answered_turn(sid, "fiqh", "llm_generated")
        resp = _ask(client, sid, "وإذا رفض مرة أخرى؟")
    finally:
        client.__exit__(None, None, None)

    assert len(pipeline.retrieve) == 1
    call = pipeline.retrieve[0]
    assert call["domains"] == ["fiqh"]
    assert "يرفض أداء الصلاة" in call["query_text"]
    assert "وإذا رفض مرة أخرى" in call["query_text"]
    assert '"mode": "llm_generated"' in resp.text


def test_followup_after_an_off_topic_reply_stays_general(pipeline):
    pipeline.domains = ["general"]
    pipeline.use_script([("token", "إجابة عامة")])
    client, sid = _client_with_session()
    try:
        _seed_answered_turn(sid, "general", "general_pivot")
        resp = _ask(client, sid, "وماذا عن الحلوى؟")
    finally:
        client.__exit__(None, None, None)

    assert pipeline.retrieve == []
    assert '"mode": "general_pivot"' in resp.text


def test_followup_context_requires_a_grounded_reply_and_a_real_domain():
    sid = store.create_session("ctx")
    _seed_answered_turn(sid, "medical", "llm_generated")
    store.add_message(sid, "assistant", "تعذّر توليد الرد", mode="error")  # skipped
    nxt = store.add_message(sid, "user", "وإذا لم ينفع؟")
    assert store.followup_context(sid, nxt) == (
        "medical", "ابني يرفض أداء الصلاة، كيف أشجعه؟",
    )

    sid2 = store.create_session("ctx2")
    _seed_answered_turn(sid2, "fiqh_aqeedah", "fiqh_guard")
    assert store.followup_context(sid2, store.add_message(sid2, "user", "ولماذا؟")) is None
    assert store.followup_context(sid2, None) is None


# ── 8. The off-topic fallback: no invented questions, menus or language ────

def test_pivot_prompt_forbids_inventing_a_question_or_app_menus():
    prompt = build_pivot_prompt("عندي سؤال", "4-6")
    assert "لا تخترع سؤالاً ولا جواباً" in prompt
    assert "لا تخترع خطوات ولا أسماء قوائم" in prompt
    assert "«شاركنا رأيك»" in prompt
    assert "ضع هنا" not in prompt  # no fill-in template for the model to copy


def test_pivot_prompt_answers_in_the_parents_language():
    english = build_pivot_prompt("How do I make pizza dough at home?", "4-6")
    arabic = build_pivot_prompt("كيف أصنع عجينة البيتزا في البيت؟", "4-6")
    assert english.startswith("🔴 LANGUAGE")
    assert not arabic.startswith("🔴 LANGUAGE")


@pytest.mark.parametrize("text,expected", [
    ("سلام", "وعليكم السلام"),
    ("كيف الحال؟", "الحمد لله"),
    ("Hi", "Hello"),
    ("Thank you!", "You're welcome"),
])
def test_pleasantries_that_reached_the_pivot_now_get_a_direct_reply(text, expected):
    is_conv, reply = check_conversational_shortcut(text)
    assert is_conv is True
    assert expected in reply


@pytest.mark.parametrize("text", [
    "hello, my son hits his little sister",
    "سلام عليكم ابني لا ينام",
])
def test_greeting_with_a_question_is_not_short_circuited(text):
    assert check_conversational_shortcut(text)[0] is False
