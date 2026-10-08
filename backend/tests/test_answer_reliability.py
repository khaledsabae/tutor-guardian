"""Unanswered questions — one test per mechanism, each failing without its fix.

Production, 30 days to 2026-10-04: 44 of 290 parent questions (15.2%) ended
with no answer. 23 were cut by the app mid-answer, ~18 sat for 2–31 minutes
behind DeepSeek calls that ignored their 6–8 s "timeouts" (a per-READ limit
that keep-alive lines reset) while holding the event loop's default thread
pool. The PR #24 reviews then found regressions in the first fix (round 1:
G1–G4, S1–S8, M1–M6; round 2: R1–R8, T1–T8); the tests for those are
labelled with the finding's id. The follow-up topic inheritance (S2/S3) was
taken out of this PR (T3) — production's behaviour is kept.

Names introduced by the fix are reached through the module (`ai_gateway.x`)
inside each test, never imported at the top — so on old code a test fails on
its behaviour, not on a collection-time ImportError.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
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
from app.services.llm_service import build_pivot_prompt, strip_pivot_citation

_RELEASE = threading.Event()  # frees every provider thread a test left blocked


@pytest.fixture(autouse=True)
def _release_blocked_threads(monkeypatch):
    _RELEASE.clear()
    ai_gateway.aux_breaker.reset()
    # These are transport-reliability tests on fake "deepseek" providers with
    # fake model names. The paid-wire cap (fail closed without an activated
    # ledger and a verified profile) is exercised per attempt — including
    # retries, aborts and cut streams — in test_cloud_budget_reservations.
    monkeypatch.setattr(ai_gateway, "_reserve_wire_budget", lambda *a, **k: None)
    yield
    _RELEASE.set()
    ai_gateway.aux_breaker.reset()


# ── Fakes ──────────────────────────────────────────────────────────────────

class _HangingProvider:
    """Holds the call open the way DeepSeek does when loaded: no answer."""

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


def _sse_body(*texts: str, usage=(11, 22), hold_s: float = 0.0, gap_s: float = 0.0):
    """A DeepSeek-style streamed body: optional keep-alive hold, then content."""
    def gen():
        end = time.monotonic() + hold_s
        while time.monotonic() < end:
            yield b": keep-alive\n\n"
            time.sleep(0.05)
        for t in texts:
            yield ("data: " + json.dumps({"choices": [{"delta": {"content": t}}]}) + "\n\n").encode()
            if gap_s:
                time.sleep(gap_s)
        yield ("data: " + json.dumps({"choices": [], "usage": {
            "prompt_tokens": usage[0], "completion_tokens": usage[1]}}) + "\n\n").encode()
        yield b"data: [DONE]\n\n"
    return gen()


def _sse_ok(body) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/event-stream; charset=utf-8"},
                          content=body)


class _DeepSeekFake:
    """An httpx transport that plays DeepSeek; counts the requests it gets."""

    def __init__(self, respond) -> None:
        self.respond = respond
        self.requests = 0

    def client(self) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests += 1
            return self.respond(request)
        return httpx.Client(transport=httpx.MockTransport(handler))


def _deepseek(fake: _DeepSeekFake, timeout: float = 0.3) -> "ai_gateway.OpenAIChatProvider":
    return ai_gateway.OpenAIChatProvider(
        base_url="https://deepseek.test", api_key="test-placeholder", model="deepseek-chat",
        timeout=timeout, http_client=fake.client(),
    )


def _scripted_provider(script, calls: list | None = None):
    """An Ollama stand-in whose stream follows `script`:
    ("token", text) | ("sleep", s) | ("hang", s) | ("finish", reason)."""

    class _Scripted:
        name = "fake"
        model = "fake-model"

        def __init__(self, *a, **k):
            self.timeout = 60

        def stream(self, prompt, *, options):
            if calls is not None:
                calls.append(prompt)
            final = {"response": "", "done": True, "prompt_eval_count": 1, "eval_count": 1}
            for kind, value in script:
                if kind == "token":
                    yield {"response": value, "done": False}
                elif kind == "sleep":
                    time.sleep(value)
                elif kind == "hang":
                    _RELEASE.wait(value)
                elif kind == "finish":  # the answer stopped short (R3)
                    final["truncated"] = value
            yield final

        def generate(self, prompt, *, options):
            return {"response": "رد قصير", "done": True}

    return _Scripted


def _unit(domain="medical", doc="نصيحة تربوية موثقة عن النوم."):
    return {
        "unit_id": f"u-{domain}-1",
        "document": f"passage: {doc}",
        "metadata": {"domain": domain, "reference_info": "مرجع تربوي موثق",
                     "title": "النوم", "age_group": "4-6"},
        "rerank_score": 0.5,
        "distance": 0.2,
        "source_domain": domain,
    }


@pytest.fixture
def pipeline(monkeypatch):
    """The assistant pipeline minus its heavy parts: classification, cache,
    retrieval and telemetry are stubbed; the model is a scripted fake."""
    calls = SimpleNamespace(retrieve=[], sessions=[], domains=["medical"],
                            unit_domain="medical", prompts=[])

    async def _classify(query_text):
        return list(calls.domains), ""

    def _retrieve(**kwargs):
        calls.retrieve.append(kwargs)
        return [_unit(calls.unit_domain)]

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
        monkeypatch.setattr(ai_gateway, "OllamaProvider", _scripted_provider(script, calls.prompts))
        ai_gateway._gateway = None

    calls.use_script = use_script
    yield calls
    ai_gateway._gateway = None
    getattr(assistant, "_ACTIVE_TURNS", {}).clear()


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
            "SELECT id, role, content, mode, domain FROM chat_messages WHERE session_id = ? ORDER BY id",
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


def _done_payload(body: str) -> dict:
    return json.loads(body.split("event: done\ndata: ", 1)[1].split("\n", 1)[0])


# ── G1/G2: real abort, separate lanes, bounded retries ─────────────────────

def test_held_request_is_aborted_and_the_thread_freed():
    """G1 — the old code abandoned a held call at its deadline but its thread
    stayed stuck in the read for as long as DeepSeek kept the socket alive."""
    fake = _DeepSeekFake(lambda r: _sse_ok(_sse_body("late", hold_s=5)))
    provider = _deepseek(fake, timeout=0.3)
    t0 = time.monotonic()
    with ai_gateway.call_limits(ai_gateway.CallLimits(first_token=0.4)):
        with pytest.raises(ai_gateway.LLMDeadlineExceeded):
            provider.generate("س", options={})
    assert time.monotonic() - t0 < 1.5  # returned in this thread at the limit


def test_slow_but_alive_answer_is_not_cut_at_the_first_token_limit():
    """G2 — a provider streaming its answer slowly is alive: only a hold (no
    content at all) is cut early. Previously cut at 64 s and retried."""
    fake = _DeepSeekFake(lambda r: _sse_ok(_sse_body(
        "أ", "ب", "ج", "د", gap_s=0.2)))
    provider = _deepseek(fake, timeout=0.3)
    with ai_gateway.call_limits(ai_gateway.CallLimits(first_token=0.4, total=5)):
        out = provider.generate("س", options={})
    assert out["response"] == "أبجد"
    assert (out["prompt_eval_count"], out["eval_count"]) == (11, 22)
    assert fake.requests == 1


def test_held_primary_is_not_retried(monkeypatch):
    """G2 — after a deadline the loop retried, each retry another paid request
    into the same hold, all of them running at once."""
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "primary_budget_available", lambda name: True)
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [])
    fake = _DeepSeekFake(lambda r: _sse_ok(_sse_body("late", hold_s=3)))
    gw = ai_gateway.AIGateway(provider=_deepseek(fake, timeout=0.3))

    t0 = time.monotonic()
    with pytest.raises(RuntimeError):
        asyncio.run(gw.generate("سؤال", max_retries=3))
    assert time.monotonic() - t0 < 2.0
    assert fake.requests == 1


def test_open_breaker_stops_the_retry_loop(monkeypatch):
    """G2 — the breaker was only checked before the loop: once two failures
    opened it, the third attempt still went out."""
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "primary_budget_available", lambda name: True)
    monkeypatch.setattr(ai_gateway, "PRIMARY_PREFLIGHT_RETRIES", 0, raising=False)
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [])
    fake = _DeepSeekFake(lambda r: httpx.Response(503))
    gw = ai_gateway.AIGateway(provider=_deepseek(fake))

    with pytest.raises(RuntimeError):
        asyncio.run(gw.generate("سؤال", max_retries=3))
    assert ai_gateway.primary_breaker.is_open()
    assert fake.requests == 2


def test_no_attempt_is_started_with_seconds_left(monkeypatch):
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "primary_budget_available", lambda name: True)
    monkeypatch.setattr(ai_gateway, "_MIN_ATTEMPT_S", 1000.0, raising=False)
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [])
    fake = _DeepSeekFake(lambda r: _sse_ok(_sse_body("x")))
    gw = ai_gateway.AIGateway(provider=_deepseek(fake))
    with pytest.raises(RuntimeError):
        asyncio.run(gw.generate("سؤال", max_retries=3))
    assert fake.requests == 0


def test_one_request_per_attempt_no_sdk_retries(monkeypatch):
    """G2 — the SDK client retried twice per call, each retry restarting the
    per-read timeout. The classifier's provider makes exactly one request."""
    fake = _DeepSeekFake(lambda r: httpx.Response(503))
    monkeypatch.setattr(ai_gateway, "_HTTP", fake.client(), raising=False)
    monkeypatch.setattr(ai_gateway, "PRIMARY_PREFLIGHT_RETRIES", 0, raising=False)
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    cfg = dataclasses.replace(llm_config.LLM, primary_provider="deepseek",
                              deepseek_api_key="test-placeholder")
    monkeypatch.setattr(ai_gateway, "LLM", cfg)
    monkeypatch.setattr(ai_gateway, "primary_budget_available", lambda name: True)
    from app.services import domain_classifier

    provider = domain_classifier._classifier_provider()
    assert isinstance(provider, ai_gateway.OpenAIChatProvider)
    assert ai_gateway.aux_generate(provider, "صنّف", options={}, tier="classifier") is None
    assert fake.requests == 1


def test_fallback_still_runs_while_the_primary_lane_is_held(monkeypatch):
    """G1 — one pool served the primary, the local fallback and aux calls:
    during a DeepSeek hold it filled up and the healthy local model never ran
    (review probe: local ran 0 times, RuntimeError)."""
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    monkeypatch.setattr(ai_gateway, "PRIMARY_LANE", ai_gateway._Lane("primary", 1), raising=False)
    hung = _HangingProvider(timeout=0.2, hang_s=5.0)

    class _Healthy:
        name, ran = "ollama", 0

        def __init__(self, base_url=None, model="m", timeout=1.0):
            self.model, self.timeout = model, timeout

        def generate(self, prompt, *, options):
            _Healthy.ran += 1
            return {"response": "ok-local", "done": True}

    monkeypatch.setattr(ai_gateway, "OllamaProvider", _Healthy)
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [
        {"name": "local_fast", "url": "http://x", "model": "m", "timeout": 1.0}])
    # The paid primary, held: its only lane slot is taken by a stuck call.
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _HangingProvider)
    ai_gateway.PRIMARY_LANE.submit(hung.generate, "x", options={})
    gw = ai_gateway.AIGateway(provider=hung)

    result = asyncio.run(gw.generate("سؤال", max_retries=3))
    assert result.text == "ok-local"
    assert _Healthy.ran == 1
    assert hung.calls == 1  # the held call only — nothing queued behind it


def test_full_lane_fails_fast_instead_of_queueing(monkeypatch):
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    monkeypatch.setattr(ai_gateway, "AUX_LANE", ai_gateway._Lane("aux", 1), raising=False)
    provider = _HangingProvider(timeout=0.2, hang_s=5.0)

    t0 = time.monotonic()
    assert ai_gateway.aux_generate(provider, "أ", options={}, tier="classifier") is None
    assert ai_gateway.aux_generate(provider, "ب", options={}, tier="classifier") is None
    assert time.monotonic() - t0 < 2.0
    assert provider.calls == 1  # the second call never started


def test_aux_call_gives_up_at_a_wall_clock_deadline(monkeypatch):
    """The classifier's 8 s timeout let a call run 236 s in production."""
    logged = []
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: logged.append(k))
    monkeypatch.setattr(ai_gateway, "_DEADLINE_SLACK_S", 0.1, raising=False)
    provider = _HangingProvider(timeout=0.2, hang_s=5.0)

    t0 = time.monotonic()
    out = ai_gateway.aux_generate(provider, "صنّف", options={}, tier="classifier")
    assert out is None
    assert time.monotonic() - t0 < 1.5
    assert logged and logged[-1].get("route_reason") == "deadline"


# ── G3: stalls are charged to the provider that was streaming ──────────────

def test_stall_is_charged_only_to_the_provider_that_was_streaming():
    gw = ai_gateway.AIGateway.__new__(ai_gateway.AIGateway)
    tracker = ai_gateway.StreamTracker()
    gw.note_stream_stall(tracker)          # never started: a queued worker
    assert not ai_gateway.primary_breaker._consecutive_failures

    tracker.begin("cloud_quality", is_primary=False)
    gw.note_stream_stall(tracker)          # the Azure tier, not DeepSeek
    assert not ai_gateway.primary_breaker._consecutive_failures

    tracker.begin("deepseek", is_primary=True)
    gw.note_stream_stall(tracker)
    assert ai_gateway.primary_breaker._consecutive_failures == 1


def test_held_primary_stream_falls_back_and_the_tracker_follows(monkeypatch):
    """S4/G3 — the held primary is aborted at its own first-token limit and
    the next provider answers; the tracker names the one actually streaming."""
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "primary_budget_available", lambda name: True)
    monkeypatch.setattr(ai_gateway, "PRIMARY_FIRST_TOKEN_S", 0.3, raising=False)
    monkeypatch.setattr(ai_gateway, "OllamaProvider", _scripted_provider([("token", "محلي")]))
    fake = _DeepSeekFake(lambda r: _sse_ok(_sse_body("late", hold_s=3)))
    gw = ai_gateway.AIGateway(provider=_deepseek(fake, timeout=5))
    tracker = ai_gateway.StreamTracker()

    t0 = time.monotonic()
    deltas = [c.delta for c in gw.stream("س", tracker=tracker) if not c.done]
    assert deltas == ["محلي"]
    assert time.monotonic() - t0 < 2.0
    assert tracker.label == "local_fast" and tracker.is_primary is False


# ── G4: the default executor is never blocked by a model wait ──────────────

def _sqlite_ping() -> int:
    conn = store.get_conn()
    try:
        return conn.execute("SELECT 1").fetchone()[0]
    finally:
        conn.close()


def test_classification_does_not_occupy_the_default_executor(monkeypatch):
    """G4 — classification ran on asyncio's default pool and waited there up
    to 12 s per call; sqlite (token checks, history) queued behind it."""
    def _slow_classify(q):
        _RELEASE.wait(2.0)
        return ["medical"]

    monkeypatch.setattr(assistant, "classify_domains", _slow_classify)
    monkeypatch.setattr(assistant, "rewrite_query", lambda *a, **k: "")
    monkeypatch.setattr(assistant, "_AUX_WAIT_S", 0.3, raising=False)

    async def scenario():
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        task = asyncio.create_task(assistant._classify_and_rewrite("سؤال جديد تمامًا"))
        await asyncio.sleep(0.05)
        ping = await asyncio.wait_for(asyncio.to_thread(_sqlite_ping), timeout=0.5)
        domains, _ = await task
        return ping, domains

    ping, domains = asyncio.run(scenario())
    assert ping == 1
    # Past the deadline the question is searched broadly instead of waiting.
    from app.services.domain_classifier import UNCERTAIN_DOMAINS
    assert domains == list(UNCERTAIN_DOMAINS)


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


# ── S4: stall limits per attempt ──────────────────────────────────────────

def test_stall_limits_default_to_75s_first_token_and_60s_between_tokens():
    assert assistant._FIRST_TOKEN_TIMEOUT_S == 75.0
    assert assistant._STREAM_STALL_S == 60.0
    assert assistant._FALLBACK_FIRST_TOKEN_S == 150.0


def test_no_first_token_ends_the_turn_with_an_error(pipeline, monkeypatch):
    """The SSE keep-alive defeats the app's 45 s idle check, so a provider
    that never sends a token kept the parent on «يكتب…» for up to 30 min."""
    monkeypatch.setattr(assistant, "_FIRST_TOKEN_TIMEOUT_S", 0.3, raising=False)
    monkeypatch.setattr(assistant, "_FALLBACK_FIRST_TOKEN_S", 0.3, raising=False)
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


def test_fallback_model_gets_its_own_longer_first_token_budget(pipeline, monkeypatch):
    """S4 — 75 s from the start of the request covered the whole provider
    chain, so a slow-but-healthy local model (32–95 s on the home box) was
    killed. A fallback attempt is timed on its own, longer budget."""
    monkeypatch.setattr(assistant, "_FIRST_TOKEN_TIMEOUT_S", 0.3, raising=False)
    monkeypatch.setattr(assistant, "_FALLBACK_FIRST_TOKEN_S", 3.0, raising=False)
    pipeline.use_script([("sleep", 0.8), ("token", "إجابة بطيئة لكنها حية")])
    client, sid = _client_with_session()
    try:
        resp = _ask(client, sid)
    finally:
        client.__exit__(None, None, None)
    assert "event: done" in resp.text and "event: error" not in resp.text
    assert _rows(sid)[-1]["mode"] == "llm_generated"


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


# ── Pre-stream failure + S7 localization ───────────────────────────────────

def test_pre_stream_failure_stores_an_error_turn(pipeline, monkeypatch):
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


@pytest.mark.parametrize("question,expected", [
    ("My son refuses to sleep before midnight, what can I do?",
     "Sorry, the answer could not be generated"),
    ("Mon fils refuse de dormir avant minuit, que faire ?",
     "Désolé, la réponse n'a pas pu être générée"),
])
def test_error_text_follows_the_parents_language(pipeline, monkeypatch, question, expected):
    """S7 — English and French parents got the Arabic apology verbatim."""
    def _boom(**kwargs):
        raise RuntimeError("retrieval exploded")

    monkeypatch.setattr(assistant, "retrieve_hybrid", _boom)
    client, sid = _client_with_session()
    try:
        resp = _ask(client, sid, question)
    finally:
        client.__exit__(None, None, None)
    assert expected in resp.text
    assert _rows(sid)[-1]["content"].startswith(expected)


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


@pytest.mark.parametrize("finish,cached", [(None, True), ("length", False)])
def test_a_truncated_answer_is_stored_flagged_and_never_cached(pipeline, monkeypatch,
                                                                finish, cached):
    """R3 — an answer cut short by max_tokens or a content filter went into
    the answer cache, to be served whole to every parent asking the same."""
    stored = []
    monkeypatch.setattr(answer_cache, "store", lambda *a, **k: stored.append(a))
    pipeline.domains = ["tarbiyah"]
    pipeline.unit_domain = "tarbiyah"
    pipeline.use_script([("token", "جواب")] + ([("finish", finish)] if finish else []))
    client, sid = _client_with_session()
    try:
        resp = _ask(client, sid)
    finally:
        client.__exit__(None, None, None)
    assert "event: done" in resp.text
    assert _rows(sid)[-1]["content"] == "جواب"
    assert bool(stored) is cached
    assert ("truncated:length" in _flags(pipeline)) is (finish == "length")


def test_first_frame_names_the_stored_question(pipeline):
    """M1 — the app needs the id of THIS question to find its answer in the
    history later; matching by text picked a different turn's answer."""
    pipeline.use_script([("token", "رد")])
    client, sid = _client_with_session()
    try:
        resp = _ask(client, sid)
        hist = client.get(f"/api/chat/sessions/{sid}").json()
    finally:
        client.__exit__(None, None, None)
    first = resp.text.split("\n\n", 1)[0]
    assert first.startswith("event: turn")
    qid = json.loads(first.split("data: ", 1)[1])["message_id"]
    assert [m["id"] for m in hist["messages"] if m["role"] == "user"] == [qid]


# ── S1/S5/S6: the answer survives the reader leaving, in order ─────────────

def _request(device_id: str) -> Request:
    app = SimpleNamespace(state=SimpleNamespace(guardrails_config=load_guardrails_config()))
    return Request({
        "type": "http", "method": "POST", "path": "/api/assistant/stream",
        "headers": [], "query_string": b"", "app": app,
        "state": {"device_id": device_id},
    })


def _msg(session_id: str, text="ابني لا ينام إلا متأخرًا، ماذا أفعل؟") -> UserMessage:
    return UserMessage(age_group="4-6", severity="خفيف", message_text=text, session_id=session_id)


async def _read_until(resp, stop_at: str) -> list[str]:
    seen: list[str] = []
    gen = resp.body_iterator
    async for frame in gen:
        seen.append(frame)
        if stop_at in frame:
            break
    await gen.aclose()  # what Starlette does when the client disconnects
    return seen


async def _drain_background() -> None:
    """Wait for everything the server keeps doing after the reader left:
    pre-stream pipelines, detached answers, background completions."""
    for _ in range(200):
        pending = (list(getattr(assistant, "_PIPELINES", ()))
                   + list(getattr(assistant, "_BACKGROUND_COMPLETIONS", ())))
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.sleep(0)  # let done-callbacks schedule their follow-ups


def test_answer_is_finished_into_the_row_reserved_when_the_reader_left(pipeline):
    """S1 — the row is written the moment the reader leaves (what they saw,
    as 'interrupted') and completed in place, keeping its position."""
    pipeline.use_script([
        ("token", "أولًا "), ("sleep", 0.3), ("token", "ثانيًا "),
        ("sleep", 0.3), ("token", "ثالثًا"),
    ])
    sid = store.create_session("leaver")

    async def scenario():
        resp = await assistant.stream_reply(_request("leaver"), _msg(sid))
        await _read_until(resp, "event: token")
        reserved = _rows(sid)  # right after the reader left
        await _drain_background()
        return reserved

    reserved = asyncio.run(scenario())
    assert [r["role"] for r in reserved] == ["user", "assistant"]
    # T5 — 'pending' while it is being finished, distinct from a final cut.
    assert reserved[1]["mode"] == "pending" and reserved[1]["content"] == "أولًا"
    rows = _rows(sid)
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[1]["id"] == reserved[1]["id"]  # the same row, filled in
    assert rows[1]["content"] == "أولًا ثانيًا ثالثًا"
    assert rows[1]["mode"] == "llm_generated"
    assert "completed_after_disconnect" in _flags(pipeline)
    assert store.get_history(sid)[-1].content == "أولًا ثانيًا ثالثًا"


def test_new_question_cuts_the_pending_completion_and_keeps_order(pipeline):
    """S1/S5 — a question asked while the previous answer was being finished
    in the background landed before it (Q1, Q2, A1): A1 then showed under Q2
    and Q2's prompt never saw it. The old turn is now cut and written first."""
    pipeline.use_script([
        ("token", "بداية الجواب الأول "), ("sleep", 0.4), ("token", "بقية لن تُكتب"),
    ])
    sid = store.create_session("asker")

    async def scenario():
        r1 = await assistant.stream_reply(_request("asker"), _msg(sid, "السؤال الأول عن النوم"))
        await _read_until(r1, "event: token")
        pipeline.use_script([("token", "الجواب الثاني")])
        r2 = await assistant.stream_reply(_request("asker"), _msg(sid, "السؤال الثاني عن الشاشات"))
        async for _frame in r2.body_iterator:
            pass
        await _drain_background()

    asyncio.run(scenario())
    rows = _rows(sid)
    assert [(r["role"], r["mode"]) for r in rows] == [
        ("user", None), ("assistant", "interrupted"), ("user", None), ("assistant", "llm_generated"),
    ]
    assert rows[1]["content"] == "بداية الجواب الأول"  # cut: the rest was never written
    assert "superseded" in _flags(pipeline)
    assert "completed_after_disconnect" not in _flags(pipeline)
    # Q2's prompt saw A1 — the conversation is in order.
    assert "بداية الجواب الأول" in pipeline.prompts[-1]


def test_stop_cancels_generation_instead_of_finishing_it(pipeline):
    """S5 — Stop looked exactly like the app going to the background, so the
    server finished (and paid for, and stored) an answer the parent rejected.
    New builds send an explicit stop; the work is cancelled."""
    pipeline.use_script([
        ("token", "جواب سيوقفه الأب "), ("sleep", 0.5), ("token", "ولا يُكمل"),
    ])
    sid = store.create_session("stopper")

    async def scenario():
        resp = await assistant.stream_reply(_request("stopper"), _msg(sid))
        await _read_until(resp, "event: token")
        stopped = await assistant.cut_pending_turn(sid, "stopped_by_parent")
        await _drain_background()
        return stopped

    assert asyncio.run(scenario()) is True
    rows = _rows(sid)
    assert rows[-1]["mode"] == "interrupted" and rows[-1]["content"] == "جواب سيوقفه الأب"
    assert "stopped_by_parent" in _flags(pipeline)
    assert "completed_after_disconnect" not in _flags(pipeline)


def test_late_stop_for_an_older_turn_does_not_cut_a_newer_one(pipeline):
    """S5 — a stop names the question it stops; arriving after a newer
    question started, it must not cut that one."""
    pipeline.use_script([("token", "جواب "), ("sleep", 0.3), ("token", "كامل")])
    sid = store.create_session("late")

    async def scenario():
        resp = await assistant.stream_reply(_request("late"), _msg(sid))
        await _read_until(resp, "event: token")
        cut = await assistant.cut_pending_turn(sid, "stopped_by_parent", only_message_id=-1)
        await _drain_background()
        return cut

    assert asyncio.run(scenario()) is False
    assert _rows(sid)[-1]["content"] == "جواب كامل"
    assert "completed_after_disconnect" in _flags(pipeline)


def test_stop_endpoint_is_owned_and_quota_free(pipeline):
    client, sid = _client_with_session()
    try:
        ok = client.post(f"/api/chat/sessions/{sid}/stop")
        other = client.post("/api/chat/sessions/not-a-session/stop")
    finally:
        client.__exit__(None, None, None)
    assert ok.status_code == 200 and ok.json() == {"stopped": False}
    assert other.status_code == 404


def test_background_stall_is_counted_as_a_stall_not_a_parent(pipeline, monkeypatch):
    """S6 — after the reader left, a provider that never answered was logged
    as 'client_left_before_first_token'; it is a provider stall."""
    monkeypatch.setattr(assistant, "_FIRST_TOKEN_TIMEOUT_S", 0.3, raising=False)
    monkeypatch.setattr(assistant, "_FALLBACK_FIRST_TOKEN_S", 0.3, raising=False)
    pipeline.use_script([("hang", 3.0), ("token", "متأخر")])
    sid = store.create_session("silent")

    async def scenario():
        resp = await assistant.stream_reply(_request("silent"), _msg(sid))
        await _read_until(resp, ": keep-alive")
        await _drain_background()

    asyncio.run(scenario())
    assert [r["role"] for r in _rows(sid)] == ["user"]  # no empty bubble left behind
    assert "first_token_timeout" in _flags(pipeline)
    assert "client_left_before_first_token" not in _flags(pipeline)


# ── T1/T2/T7: a turn is cut from the moment its question is stored ────────

def _run(coro, timeout: float = 20.0):
    """asyncio.run with a ceiling: on a regression these scenarios wait for
    a frame or a task that never comes — fail, don't hang the suite."""
    return asyncio.run(asyncio.wait_for(coro, timeout))


def _gate_classifier(monkeypatch, slow_text: str) -> "asyncio.Event":
    """Classification of `slow_text` waits for the returned event: the
    seconds of "thinking" before an answer starts streaming."""
    gate = asyncio.Event()

    async def _classify(query_text):
        if query_text == slow_text:
            await gate.wait()
        return ["medical"], ""

    monkeypatch.setattr(assistant, "_classify_and_rewrite", _classify)
    return gate


def _turn_id(frame: str) -> int:
    assert frame.startswith("event: turn"), frame
    return json.loads(frame.split("data: ", 1)[1])["message_id"]


def test_turn_frame_comes_before_classification(pipeline, monkeypatch):
    """T2 — the frame came only after classification and retrieval, so a
    Stop pressed in those seconds had no question id and never reached the
    server: the whole answer was generated and stored."""
    pipeline.use_script([("token", "رد")])
    sid = store.create_session("early")

    async def scenario():
        gate = _gate_classifier(monkeypatch, "سؤال بطيء")
        resp = await assistant.stream_reply(_request("early"), _msg(sid, "سؤال بطيء"))
        first = await asyncio.wait_for(resp.body_iterator.__anext__(), 2)
        registered = assistant._ACTIVE_TURNS.get(sid)
        gate.set()
        rest = [frame async for frame in resp.body_iterator]
        return first, registered, rest

    first, registered, rest = _run(scenario())
    qid = _rows(sid)[0]["id"]
    assert _turn_id(first) == qid
    # T1 — registered with the stored question, before any of the pipeline.
    assert registered is not None and registered.user_msg_id == qid
    assert any("event: done" in f for f in rest)


def test_new_question_while_thinking_never_starts_the_old_answer(pipeline, monkeypatch):
    """T1 — the turn was registered only when its answer began to stream. A
    question asked during the "thinking" seconds found nothing to cut:
    Q1, Q2, A1, A2 — A1 paid for, and shown under Q2."""
    pipeline.use_script([("token", "الجواب")])
    sid = store.create_session("thinker")

    async def scenario():
        gate = _gate_classifier(monkeypatch, "السؤال الأول")
        r1 = await assistant.stream_reply(_request("thinker"), _msg(sid, "السؤال الأول"))
        await r1.body_iterator.__anext__()  # the turn frame; Q1 is thinking
        r2 = await assistant.stream_reply(_request("thinker"), _msg(sid, "السؤال الثاني"))
        out2 = [frame async for frame in r2.body_iterator]
        gate.set()
        out1 = [frame async for frame in r1.body_iterator]
        await _drain_background()
        return out1, out2

    out1, out2 = _run(scenario())
    assert [(r["role"], r["content"]) for r in _rows(sid)] == [
        ("user", "السؤال الأول"), ("user", "السؤال الثاني"), ("assistant", "الجواب"),
    ]
    assert len(pipeline.prompts) == 1  # Q1 never reached the model
    assert "superseded" in _flags(pipeline)
    assert not any("event: done" in f for f in out1)
    assert any("event: done" in f for f in out2)


def test_stop_while_thinking_never_starts_the_model(pipeline, monkeypatch):
    """T1/T2 — with the id from the first frame, a Stop during the thinking
    seconds cuts the turn before any model call."""
    pipeline.use_script([("token", "لن يُكتب")])
    sid = store.create_session("early-stop")

    async def scenario():
        gate = _gate_classifier(monkeypatch, "سؤال سيوقف")
        resp = await assistant.stream_reply(_request("early-stop"), _msg(sid, "سؤال سيوقف"))
        qid = _turn_id(await resp.body_iterator.__anext__())
        stopped = await assistant.cut_pending_turn(sid, "stopped_by_parent", only_message_id=qid)
        gate.set()
        out = [frame async for frame in resp.body_iterator]
        await _drain_background()
        return stopped, out

    stopped, out = _run(scenario())
    assert stopped is True
    assert pipeline.prompts == []
    assert [r["role"] for r in _rows(sid)] == ["user"]
    assert "stopped_by_parent" in _flags(pipeline)
    assert not any("event: done" in f for f in out)


def test_reader_leaving_while_thinking_still_gets_its_answer(pipeline, monkeypatch):
    """The app going to the background before the first token is not a Stop:
    the answer is produced anyway and stored for the app to reload."""
    pipeline.use_script([("token", "جواب "), ("token", "كامل")])
    sid = store.create_session("pocket")

    async def scenario():
        gate = _gate_classifier(monkeypatch, "سؤال ثم جيب")
        resp = await assistant.stream_reply(_request("pocket"), _msg(sid, "سؤال ثم جيب"))
        await resp.body_iterator.__anext__()
        await resp.body_iterator.aclose()  # the reader leaves while thinking
        gate.set()
        await _drain_background()

    _run(scenario())
    rows = _rows(sid)
    assert [(r["role"], r["mode"]) for r in rows] == [("user", None), ("assistant", "llm_generated")]
    assert rows[1]["content"] == "جواب كامل"
    assert "completed_after_disconnect" in _flags(pipeline)


def test_a_late_registration_never_replaces_a_newer_turn(pipeline, monkeypatch):
    """T1 — Q1 stored first but registered after Q2 replaced Q2's control:
    a Stop for Q2 then answered stopped:false and Q1 was answered after Q2."""
    pipeline.use_script([("token", "جواب الثاني "), ("sleep", 0.3), ("token", "يكمل")])
    sid = store.create_session("racer")
    real_add = store.add_message

    def slow_add(session_id, role, content, **kw):
        mid = real_add(session_id, role, content, **kw)
        if role == "user" and content == "السؤال الأول":
            time.sleep(0.3)  # stored first, back on the loop last
        return mid

    monkeypatch.setattr(store, "add_message", slow_add)

    async def scenario():
        t1 = asyncio.create_task(
            assistant.stream_reply(_request("racer"), _msg(sid, "السؤال الأول")))
        await asyncio.sleep(0.1)  # Q1's row exists; its request is still in add_message
        r2 = await assistant.stream_reply(_request("racer"), _msg(sid, "السؤال الثاني"))
        r1 = await t1
        owner = assistant._ACTIVE_TURNS[sid].user_msg_id
        q2 = _turn_id(await r2.body_iterator.__anext__())
        await _read_until(r2, "event: token")
        stopped = await assistant.cut_pending_turn(sid, "stopped_by_parent", only_message_id=q2)
        out1 = [frame async for frame in r1.body_iterator]
        await _drain_background()
        return owner, q2, stopped, out1

    owner, q2, stopped, out1 = _run(scenario())
    assert owner == q2 and stopped is True
    assert len(pipeline.prompts) == 1  # Q1 was cut at birth
    assert not any("event: done" in f for f in out1)
    assert [(r["role"], r["content"], r["mode"]) for r in _rows(sid)] == [
        ("user", "السؤال الأول", None), ("user", "السؤال الثاني", None),
        ("assistant", "جواب الثاني", "interrupted"),
    ]


def test_a_cut_keeps_only_what_the_parent_saw(pipeline):
    """T7 — a cut after the reader left stored the words a background
    completion added later as the 'interrupted' answer: text the parent
    never saw, fed into the next prompt as if they had."""
    pipeline.use_script([
        ("token", "ما رآه "), ("sleep", 0.05), ("token", "وما لم يره "),
        ("token", "أيضًا"), ("hang", 3.0),
    ])
    sid = store.create_session("unseen")

    async def scenario():
        resp = await assistant.stream_reply(_request("unseen"), _msg(sid))
        await _read_until(resp, "event: token")
        await asyncio.sleep(0.4)  # the background completion takes in the rest
        stopped = await assistant.cut_pending_turn(sid, "stopped_by_parent")
        await _drain_background()
        return stopped

    assert _run(scenario()) is True
    rows = _rows(sid)
    assert rows[-1]["mode"] == "interrupted" and rows[-1]["content"] == "ما رآه"


def test_a_cut_turn_tells_the_gateway_to_stop(pipeline, monkeypatch):
    """R1 — the gateway never saw the cancel: at its first-token limit it
    treated the abort as a failure and started a fallback model for a turn
    nobody was waiting for. The stop check now goes into stream()."""
    seen = {}
    real_stream = ai_gateway.AIGateway.stream

    def spying_stream(self, prompt, **kw):
        seen["should_stop"] = kw.get("should_stop")
        return real_stream(self, prompt, **kw)

    monkeypatch.setattr(ai_gateway.AIGateway, "stream", spying_stream)
    pipeline.use_script([("token", "بداية "), ("hang", 3.0), ("token", "لن تأتي")])
    sid = store.create_session("r1")

    async def scenario():
        resp = await assistant.stream_reply(_request("r1"), _msg(sid))
        frames = resp.body_iterator
        async for frame in frames:
            if "event: token" in frame:
                break
        before = seen["should_stop"]()
        await assistant.cut_pending_turn(sid, "stopped_by_parent")
        after = seen["should_stop"]()
        await frames.aclose()
        await _drain_background()
        return before, after

    assert _run(scenario()) == (False, True)


# ── Pivot prompt, S8 pleasantries, minor ───────────────────────────────────

def test_pivot_prompt_forbids_inventing_a_question_or_app_menus():
    prompt = build_pivot_prompt("عندي سؤال", "4-6")
    assert "لا تخترع سؤالاً ولا جواباً" in prompt
    assert "لا تخترع خطوات ولا أسماء قوائم" in prompt
    assert "«شاركنا رأيك»" in prompt
    assert "ضع هنا" not in prompt  # no fill-in template for the model to copy


def test_pivot_prompt_answers_in_the_parents_language_and_asks_no_sources():
    english = build_pivot_prompt("How do I make pizza dough at home?", "4-6")
    arabic = build_pivot_prompt("كيف أصنع عجينة البيتزا في البيت؟", "4-6")
    assert english.startswith("🔴 LANGUAGE")
    assert not arabic.startswith("🔴 LANGUAGE")
    # The pivot cites nothing (rule 6): its language rule must not ask for a
    # closing sources line.
    assert "sources line" not in english


def test_pivot_strips_english_source_lines():
    assert strip_pivot_citation("Paris is the capital.\n\nSource: Wikipedia") == "Paris is the capital."
    assert strip_pivot_citation("Try a calm routine.\n**Sources:** AAP, NHS") == "Try a calm routine."
    assert strip_pivot_citation("The source of the noise matters.") == "The source of the noise matters."


@pytest.mark.parametrize("text,expected", [
    ("سلام", "وعليكم السلام"),
    ("كيف الحال؟", "الحمد لله"),
    ("Hi", "Hello"),
    ("Thank you!", "You're welcome"),
    ("Salam", "Wa alaikum assalam"),            # S8: a salam is returned as a salam
    ("Assalamu alaikum", "Wa alaikum assalam"),
    ("merci", "Avec plaisir"),
    ("bonjour", "Bonjour et bienvenue"),
    # T8 — the spellings that missed the shortcut or got an English reply.
    ("Salaam alaikum", "Wa alaikum assalam"),
    ("salamualaikum", "Wa alaikum assalam"),
    ("Assalam o alaikum", "Wa alaikum assalam"),
    ("Assalamu alaikum wa rahmatullah", "Wa alaikum assalam wa rahmatullahi"),
    ("As-salamu alaykum wa rahmatullahi wa barakatuh!", "Wa alaikum assalam"),
    ("Salam alaykoum", "Wa alaykoum assalam"),
    ("Salam alikoum", "Wa alaykoum assalam"),
    ("Assalamou alaykoum", "Wa alaykoum assalam"),
    ("Salamalekoum", "Wa alaykoum assalam"),
])
def test_pleasantries_get_a_direct_reply_in_kind(text, expected):
    is_conv, reply = check_conversational_shortcut(text)
    assert is_conv is True
    assert expected in reply


def test_a_french_style_salam_is_answered_in_french():
    """T8 — "Assalamou alaykoum" is how French speakers write it; it got
    the English welcome."""
    for text in ("Assalamou alaykoum", "Salam alikoum"):
        reply = check_conversational_shortcut(text)[1]
        assert "Comment puis-je vous aider" in reply, text


@pytest.mark.parametrize("text,lang", [
    ("My son José won't sleep at night", "en"),     # T8: an accented name is not French
    ("Chloé hits her little brother", "en"),
    ("Ma fille Chloé ne dort pas", "fr"),
    ("Mon fils refuse de manger", "fr"),
    ("Problème de sommeil", "fr"),
    ("Salam alaykoum, mon fils a peur du noir", "fr"),
    ("How do I calm a tantrum?", "en"),
    ("ابني لا ينام", "ar"),
])
def test_reply_language(text, lang):
    from app.services.intent_guard import detect_reply_language

    assert detect_reply_language(text) == lang


@pytest.mark.parametrize("text", [
    "hello, my son hits his little sister",
    "سلام عليكم ابني لا ينام",
    "Salam alaikum, my son hits his little sister",
    "Salami for a toddler?",
])
def test_greeting_with_a_question_is_not_short_circuited(text):
    assert check_conversational_shortcut(text)[0] is False
