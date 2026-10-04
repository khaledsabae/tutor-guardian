"""
AI Gateway — البوابة الموحّدة لكل نداءات الـ LLM
=================================================
The tutor-guardian analog of analytics-platform's ZAIService: every LLM call
in the app goes through ONE gateway. Here it is **local-only by design**
(Ollama) — children's/parenting/medical data never leaves the machine — but
the provider is abstracted behind an interface so a future swap is one class.

Provides over the old direct-`requests` call:
  • retry with exponential backoff (was: flat retry)
  • native streaming (token-by-token) for SSE
  • telemetry: latency + token counts per call → ops/sessions.db (llm_calls)
  • env-driven config via app.config.llm_config

Usage:
    gw = get_gateway()
    result = await gw.generate(prompt)          # blocking → LLMResult
    for chunk in gw.stream(prompt):             # streaming → StreamChunk
        ...
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import contextvars
import json
import logging
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

import httpx
import requests

from app.config.llm_config import LLM
from app.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_TELEMETRY_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


# ─────────────────────────────────────────────────────────────────────────────
# Wall-clock limits, provider lanes and stream tracking
# ─────────────────────────────────────────────────────────────────────────────
# A provider `timeout` is a per-READ timeout (requests and httpx both), not a
# limit on the whole call. DeepSeek, when loaded, holds a request open and
# trickles keep-alive lines (blank lines, or ": keep-alive" when streaming)
# until it gets to it — up to 30 minutes — and every line resets the read
# timer. Measured in production (llm_calls, 60 days to 2026-10-04): an 8 s
# classifier call took 236 s, a 6 s rewriter call 237 s, and 48 blocking calls
# ran past 300 s (max 35 min).
#
# Those calls ran on asyncio's DEFAULT executor — 8 threads on the 4-CPU VPS —
# which is also where every sqlite read/write and every retrieval of the chat
# pipeline runs. A handful of hung calls froze the whole assistant: questions
# sat between classification and retrieval for 2–31 minutes and were left
# with no reply (most of the September "orphan" questions).
#
# Three layers now:
#   1. OpenAIChatProvider reads the raw SSE lines itself and checks a wall
#      clock on every line, keep-alives included — so a held request is
#      ABORTED (socket closed, thread freed) at its limit instead of waited out.
#   2. Blocking calls run on lanes — primary (paid), local (Ollama) and aux
#      (classifier/rewriter) — never on the default executor, and never on each
#      other's threads: a DeepSeek hold cannot take the local fallback down
#      with it. A lane whose slots are all held fails fast (LLMProviderBusy)
#      instead of queueing.
#   3. The caller stops waiting at its own deadline as a backstop.
_DEADLINE_SLACK_S = float(os.environ.get("LLM_DEADLINE_SLACK_S", "4"))
# A streamed answer from the paid primary that has not produced its first
# token by now is a held request: abort it and let the stream fall back.
PRIMARY_FIRST_TOKEN_S = float(os.environ.get("LLM_PRIMARY_FIRST_TOKEN_S", "30"))
# Do not start a blocking attempt with less time than this left.
_MIN_ATTEMPT_S = float(os.environ.get("LLM_MIN_ATTEMPT_S", "10"))


class LLMDeadlineExceeded(TimeoutError):
    """A provider call outlived its wall-clock limit."""


class LLMProviderBusy(RuntimeError):
    """Every slot of a provider lane is held by calls still in flight."""


@dataclass(frozen=True)
class CallLimits:
    """Wall-clock limits for one provider call, in seconds from its start.

    first_token: until the first content arrives (keep-alives do not count);
    stall: between two pieces of content; total: the whole call. None = none.
    """

    first_token: float | None = None
    stall: float | None = None
    total: float | None = None


# Set by the gateway around a provider call and read by OpenAIChatProvider —
# a context variable, so providers keep the plain (prompt, *, options) shape
# that every test fake implements.
_CALL_LIMITS: contextvars.ContextVar[CallLimits | None] = contextvars.ContextVar(
    "llm_call_limits", default=None,
)


# The absolute deadline (time.monotonic()) of the generate() call in progress,
# so a fallback attempt can be capped by what is left of it.
_GENERATE_DEADLINE: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "llm_generate_deadline", default=None,
)


@contextlib.contextmanager
def call_limits(limits: CallLimits):
    token = _CALL_LIMITS.set(limits)
    try:
        yield
    finally:
        _CALL_LIMITS.reset(token)


def _deadline_for(provider: object, cap: float | None = None) -> float:
    """Wall-clock ceiling for one call to `provider`, never above `cap`."""
    limit = float(getattr(provider, "timeout", 60) or 60) + _DEADLINE_SLACK_S
    if cap is not None:
        limit = min(limit, cap)
    return max(0.1, limit)


class _Lane:
    """A bounded set of threads for one kind of provider call.

    A slot is held until the call really ends — not when its caller stops
    waiting — so calls still stuck on a provider count against the lane, and
    when all of them are stuck new calls fail at once (LLMProviderBusy).
    """

    def __init__(self, name: str, workers: int) -> None:
        self.name = name
        self.workers = max(1, workers)
        self._pool = ThreadPoolExecutor(max_workers=self.workers,
                                        thread_name_prefix=f"llm-{name}")
        self._slots = threading.BoundedSemaphore(self.workers)

    def submit(self, fn, *args, **kwargs) -> concurrent.futures.Future:
        if not self._slots.acquire(blocking=False):
            raise LLMProviderBusy(f"{self.name} lane: {self.workers} calls already held")
        ctx = contextvars.copy_context()
        try:
            fut = self._pool.submit(ctx.run, fn, *args, **kwargs)
        except BaseException:
            self._slots.release()
            raise
        fut.add_done_callback(lambda _f: self._slots.release())
        return fut

    def held(self) -> int:
        return self.workers - self._slots._value  # noqa: SLF001 — read-only gauge


PRIMARY_LANE = _Lane("primary", int(os.environ.get("LLM_PRIMARY_WORKERS", "6")))
LOCAL_LANE = _Lane("local", int(os.environ.get("LLM_LOCAL_WORKERS", "4")))
AUX_LANE = _Lane("aux", int(os.environ.get("LLM_AUX_WORKERS", "6")))


def call_with_deadline(fn, deadline_s: float, /, *args, lane: _Lane, **kwargs):
    """Run blocking `fn` on `lane`; give up after `deadline_s` seconds.

    For synchronous callers. Raises LLMDeadlineExceeded on timeout and
    LLMProviderBusy when the lane is full.
    """
    fut = lane.submit(fn, *args, **kwargs)
    try:
        return fut.result(timeout=deadline_s)
    except concurrent.futures.TimeoutError:
        fut.cancel()  # a call still queued behind hung ones never starts
        raise LLMDeadlineExceeded(f"no reply within {deadline_s:.0f}s") from None


async def acall_with_deadline(fn, deadline_s: float, /, *args, lane: _Lane, **kwargs):
    """Async twin of `call_with_deadline` — awaits instead of blocking a thread."""
    fut = lane.submit(fn, *args, **kwargs)
    try:
        return await asyncio.wait_for(asyncio.wrap_future(fut), timeout=deadline_s)
    except (asyncio.TimeoutError, concurrent.futures.TimeoutError):
        fut.cancel()
        raise LLMDeadlineExceeded(f"no reply within {deadline_s:.0f}s") from None


@dataclass
class StreamTracker:
    """Which provider a stream is on right now, and since when.

    Written by the gateway's stream() (worker thread), read by the assistant's
    watchdog (event loop): a stall is charged to the provider that was
    actually streaming — not to the paid primary by default, and not at all
    when the stream never started (a queued worker contacted nobody).
    """

    label: str | None = None
    is_primary: bool = False
    attempt_started: float | None = None   # time.monotonic()
    first_token_at: float | None = None

    def begin(self, label: str, is_primary: bool) -> None:
        self.label, self.is_primary = label, is_primary
        self.first_token_at = None
        self.attempt_started = time.monotonic()


# ─────────────────────────────────────────────────────────────────────────────
# Result / chunk types
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class StreamChunk:
    delta: str            # incremental token text ("" on the final chunk)
    done: bool            # True only on the terminating chunk
    result: LLMResult | None = None  # populated on the final chunk


# ─────────────────────────────────────────────────────────────────────────────
# Provider interface + Ollama implementation
# ─────────────────────────────────────────────────────────────────────────────
class LLMProvider(Protocol):
    name: str

    def generate(self, prompt: str, *, options: dict) -> dict: ...
    def stream(self, prompt: str, *, options: dict) -> Iterator[dict]: ...


class OllamaProvider:
    """Local Ollama via /api/generate. No data leaves the host."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, *, options: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False, "options": options},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def stream(self, prompt: str, *, options: dict) -> Iterator[dict]:
        """Yield Ollama's newline-delimited JSON objects as they arrive."""
        with requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": True, "options": options},
            timeout=self.timeout,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    yield json.loads(line)


class _ThinkFilter:
    """Strips DeepSeek-R1-style <think>…</think> reasoning from a token
    stream. Buffers partial tag fragments that span chunk boundaries.
    No-op overhead for non-reasoning deployments (V3/V4-Flash)."""

    _OPEN, _CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self._in_think = False
        self._pending = ""

    def feed(self, delta: str) -> str:
        text = self._pending + delta
        self._pending = ""
        out: list[str] = []
        while text:
            if self._in_think:
                idx = text.find(self._CLOSE)
                if idx == -1:
                    # keep a tail in case </think> is split across chunks
                    self._pending = text[-(len(self._CLOSE) - 1):]
                    return "".join(out)
                text = text[idx + len(self._CLOSE):]
                self._in_think = False
            else:
                idx = text.find(self._OPEN)
                if idx == -1:
                    # emit all but a possible partial "<think" tail
                    for tail in range(min(len(self._OPEN) - 1, len(text)), 0, -1):
                        if self._OPEN.startswith(text[-tail:]):
                            self._pending = text[-tail:]
                            text = text[:-tail]
                            break
                    out.append(text)
                    return "".join(out)
                out.append(text[:idx])
                text = text[idx + len(self._OPEN):]
                self._in_think = True
        return "".join(out)


class OpenAICompatProvider:
    """Azure OpenAI-compatible chat provider (cloud quality tier).

    Emits the SAME dict shape as Ollama's NDJSON ({"response", "done",
    "prompt_eval_count", "eval_count"}) so the gateway's stream/generate
    plumbing works unchanged. Reports outcomes to the tier router's
    circuit breaker.
    """

    name = "azure_deepseek"

    def __init__(self, endpoint: str, api_key: str, api_version: str,
                 model: str, timeout: int) -> None:
        from openai import AzureOpenAI  # lazy import — optional dependency

        self.model = model
        self.timeout = timeout
        self._client = AzureOpenAI(
            api_key=api_key, azure_endpoint=endpoint,
            api_version=api_version, timeout=timeout,
        )

    def _report(self, ok: bool) -> None:
        try:
            from app.services.tier_router import record_cloud_result
            record_cloud_result(ok)
        except Exception:  # noqa: BLE001 — breaker is best-effort
            pass

    def generate(self, prompt: str, *, options: dict) -> dict:
        try:
            r = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=options.get("temperature", 0.3),
                max_tokens=options.get("num_predict", 1024),
            )
        except Exception:
            self._report(False)
            raise
        self._report(True)
        text = r.choices[0].message.content or ""
        flt = _ThinkFilter()
        text = flt.feed(text)
        usage = getattr(r, "usage", None)
        return {
            "response": text, "done": True,
            "prompt_eval_count": getattr(usage, "prompt_tokens", None),
            "eval_count": getattr(usage, "completion_tokens", None),
        }

    def stream(self, prompt: str, *, options: dict) -> Iterator[dict]:
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=options.get("temperature", 0.3),
                max_tokens=options.get("num_predict", 1024),
                stream=True,
            )
        except Exception:
            self._report(False)
            raise
        flt = _ThinkFilter()
        prompt_tokens = completion_tokens = None
        try:
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", None)
                    completion_tokens = getattr(usage, "completion_tokens", None)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                delta = flt.feed(delta)
                if delta:
                    yield {"response": delta, "done": False}
        except Exception:
            self._report(False)
            raise
        self._report(True)
        yield {
            "response": "", "done": True,
            "prompt_eval_count": prompt_tokens,
            "eval_count": completion_tokens,
        }


class ProviderHTTPError(RuntimeError):
    """The provider answered with an HTTP error status."""

    def __init__(self, name: str, status: int) -> None:
        super().__init__(f"{name} answered HTTP {status}")
        self.status = status


# One connection pool for every OpenAI-compatible call (thread-safe; the
# timeout is set per request). Building a client per call — as the SDK
# client used to be built per auxiliary call — paid a TLS handshake each time.
_HTTP = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))


class OpenAIChatProvider:
    """Generic OpenAI-compatible chat provider (DeepSeek / GLM / OpenRouter…).

    Unlike OpenAICompatProvider (Azure-specific), this targets a plain
    OpenAI-style base_url (e.g. https://api.deepseek.com). Emits the same dict
    shape as Ollama so the gateway plumbing is unchanged. Used as the PRIMARY
    provider when LLM_PRIMARY_PROVIDER=deepseek, with the local Ollama chain
    kept behind it as automatic fallback.

    Every call — blocking or streamed — is a streamed request read line by
    line, keep-alive comments included, with the wall clock checked on each
    line against the CallLimits the gateway set (see call_limits). When a
    limit passes the response is closed: the request is aborted and the
    thread is free, instead of waiting out a 30-minute DeepSeek hold that the
    per-read timeout never ends. The SDK client this replaces also retried
    twice by default, restarting that timeout each time; there are no
    retries here — the gateway owns retries, and it can see the deadline and
    the circuit breaker.
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: int, name: str = "deepseek",
                 max_retries: int | None = None,
                 http_client: "httpx.Client | None" = None) -> None:
        self.name = name
        self.model = model
        self.timeout = timeout
        self.max_retries = 0  # kept for old call sites; one attempt per call
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        self._http = http_client or _HTTP

    def _events(self, prompt: str, options: dict) -> Iterator[tuple]:
        """("delta", text) for each piece of content, ("usage", p, c) when the
        provider reports token counts. Raises LLMDeadlineExceeded at a limit."""
        limits = _CALL_LIMITS.get() or CallLimits()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": options.get("temperature", 0.3),
            "max_tokens": options.get("num_predict", 1024),
            "stream": True,
            # Token counts in a final chunk (DeepSeek sends them anyway; other
            # OpenAI-compatible hosts only on request). The monthly spend cap
            # is a sum of these counts — a stream without them reads as free.
            "stream_options": {"include_usage": True},
        }
        start = time.monotonic()
        last_progress: float | None = None
        timeout = httpx.Timeout(float(self.timeout), connect=min(10.0, float(self.timeout)))
        with self._http.stream("POST", self._url, json=payload,
                               headers=self._headers, timeout=timeout) as resp:
            if resp.status_code >= 400:
                raise ProviderHTTPError(self.name, resp.status_code)
            for line in resp.iter_lines():
                now = time.monotonic()
                if limits.total is not None and now - start > limits.total:
                    raise LLMDeadlineExceeded(f"{self.name}: over {limits.total:.0f}s in total")
                if last_progress is None:
                    if limits.first_token is not None and now - start > limits.first_token:
                        raise LLMDeadlineExceeded(
                            f"{self.name}: no first token after {limits.first_token:.0f}s")
                elif limits.stall is not None and now - last_progress > limits.stall:
                    raise LLMDeadlineExceeded(
                        f"{self.name}: no new token for {limits.stall:.0f}s")
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue  # blank keep-alive, SSE comment, or another field
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if obj.get("error"):
                    raise RuntimeError(f"{self.name} reported an error mid-stream")
                usage = obj.get("usage")
                if isinstance(usage, dict):
                    yield ("usage", usage.get("prompt_tokens"), usage.get("completion_tokens"))
                for choice in obj.get("choices") or []:
                    delta = (choice or {}).get("delta") or {}
                    # Reasoning is progress (the model is alive) but not output.
                    if delta.get("reasoning_content"):
                        last_progress = now
                    content = delta.get("content")
                    if content:
                        last_progress = now
                        yield ("delta", content)

    def generate(self, prompt: str, *, options: dict) -> dict:
        parts: list[str] = []
        prompt_tokens = completion_tokens = None
        for ev in self._events(prompt, options):
            if ev[0] == "delta":
                parts.append(ev[1])
            else:
                prompt_tokens, completion_tokens = ev[1], ev[2]
        text = _ThinkFilter().feed("".join(parts))
        return {
            "response": text, "done": True,
            "prompt_eval_count": prompt_tokens, "eval_count": completion_tokens,
        }

    def stream(self, prompt: str, *, options: dict) -> Iterator[dict]:
        flt = _ThinkFilter()
        prompt_tokens = completion_tokens = None
        for ev in self._events(prompt, options):
            if ev[0] == "usage":
                prompt_tokens, completion_tokens = ev[1], ev[2]
                continue
            delta = flt.feed(ev[1])
            if delta:
                yield {"response": delta, "done": False}
        yield {
            "response": "", "done": True,
            "prompt_eval_count": prompt_tokens, "eval_count": completion_tokens,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry (non-fatal)
# ─────────────────────────────────────────────────────────────────────────────
_telemetry_schema_ready = False


def _ensure_telemetry_schema(conn: sqlite3.Connection) -> None:
    """Run the llm_calls DDL once per process, not on every LLM call."""
    global _telemetry_schema_ready
    if _telemetry_schema_ready:
        return
    conn.execute(
        """CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            provider TEXT, model TEXT, latency_ms INTEGER,
            prompt_tokens INTEGER, completion_tokens INTEGER,
            streamed INTEGER, ok INTEGER
        )"""
    )
    for col in ("tier TEXT", "route_reason TEXT"):
        try:
            conn.execute(f"ALTER TABLE llm_calls ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # column already exists
    _telemetry_schema_ready = True


def _log_call(provider: str, model: str, latency_ms: int,
              prompt_tokens: int | None, completion_tokens: int | None,
              streamed: bool, ok: bool,
              tier: str | None = None, route_reason: str | None = None) -> None:
    try:
        _TELEMETRY_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_TELEMETRY_DB)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        _ensure_telemetry_schema(conn)
        conn.execute(
            "INSERT INTO llm_calls (provider,model,latency_ms,prompt_tokens,"
            "completion_tokens,streamed,ok,tier,route_reason) VALUES (?,?,?,?,?,?,?,?,?)",
            (provider, model, latency_ms, prompt_tokens, completion_tokens,
             int(streamed), int(ok), tier, route_reason),
        )
        conn.commit()
        conn.close()
    except Exception as e:  # telemetry must never break a request
        logger.debug("telemetry skipped: %s", e)


# Sentinel returned when the telemetry DB can't be read. Callers that must not
# spend blind (the safety valve) compare it against their cap and lose; callers
# that must not go mute (the primary path) test for it explicitly and proceed.
_BUDGET_UNKNOWN = 1 << 62
# A sqlite SUM per request is pure overhead for a soft monthly budget, so the
# total is memoised. A staleness window this short can overshoot the ceiling by
# at most one minute of traffic — noise against a cap counted in millions.
_BUDGET_CACHE_TTL = 60.0
_budget_cache: dict[str, tuple[float, int]] = {}


def _monthly_tokens_used(provider_name: str) -> int:
    """Total tokens logged for a provider since the start of the current month.

    Fails CLOSED: if telemetry can't be read we report _BUDGET_UNKNOWN, an
    impossibly large number, so a budget-gated caller refuses to spend.
    """
    try:
        conn = sqlite3.connect(_TELEMETRY_DB)
        conn.execute("PRAGMA busy_timeout = 5000")
        _ensure_telemetry_schema(conn)
        row = conn.execute(
            "SELECT COALESCE(SUM(COALESCE(prompt_tokens,0)+COALESCE(completion_tokens,0)),0) "
            "FROM llm_calls WHERE provider = ? AND ts >= strftime('%Y-%m-01 00:00:00','now')",
            (provider_name,),
        ).fetchone()
        conn.close()
        return int(row[0] or 0)
    except Exception as e:
        logger.warning("budget check unavailable (failing closed): %s", e)
        return _BUDGET_UNKNOWN


def _monthly_tokens_used_cached(provider_name: str) -> int:
    """_monthly_tokens_used memoised for _BUDGET_CACHE_TTL seconds."""
    now = time.monotonic()
    cached = _budget_cache.get(provider_name)
    if cached is not None and now - cached[0] < _BUDGET_CACHE_TTL:
        return cached[1]
    used = _monthly_tokens_used(provider_name)
    _budget_cache[provider_name] = (now, used)
    return used


def primary_budget_available(provider_name: str) -> bool:
    """Soft monthly spend ceiling on the PAID primary provider.

    Shared by the chat path (AIGateway._primary_within_budget) and the
    auxiliary path (aux_cloud_provider) so both spend from ONE wallet against
    ONE ceiling — a classifier that had its own budget would be an invisible
    second bill.

    Fails OPEN on an unreadable telemetry DB: unlike the optional safety valve
    (which fails closed), the primary is the app's main way of answering at
    all, and broken telemetry must not silence it.
    """
    cap = LLM.deepseek_primary_monthly_token_cap
    if cap <= 0:
        return True  # 0 disables the ceiling
    used = _monthly_tokens_used_cached(provider_name)
    if used >= _BUDGET_UNKNOWN:
        return True  # telemetry unreadable — fail OPEN, see docstring
    if used >= cap:
        logger.warning(
            "primary provider budget exhausted (%d/%d tokens this month) — "
            "falling back to the local chain",
            used, cap,
        )
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Auxiliary (non-chat) call sites — classifier, query rewriter
# ─────────────────────────────────────────────────────────────────────────────
# Both make ONE short sync LLM call each. They must follow the configured
# primary provider — a call site pinned to Ollama keeps hammering a host the
# main path has already abandoned (that is exactly how a dead home server cost
# 45s per classification while generation itself ran on DeepSeek in 5s) — but
# they must NOT go through AIGateway.generate(): it is async, retries with
# backoff, and walks a fallback chain whose timeouts total minutes. For a
# 60-token side call the right shape is one attempt, short timeout, no
# fallback: failing fast beats answering slowly.
AUX_TIMEOUT_S = int(os.environ.get("AUX_LLM_TIMEOUT_S", "8"))

# ONE breaker for the whole auxiliary tier: the classifier and the rewriter
# talk to the same host, so once either has proved it dead the other must not
# pay the timeout again to re-prove it. Short cool-down — a home server that
# just woke up should be picked up again within minutes, not half an hour.
aux_breaker = CircuitBreaker("auxiliary LLM", failure_threshold=2, cooldown_seconds=120)

# The paid primary (DeepSeek when LLM_PRIMARY_PROVIDER=deepseek) had no breaker:
# with the provider down, EVERY chat request paid its full timeout — times
# LLM.max_retries on the blocking path — before reaching the local chain
# (audit H6). Same semantics as the auxiliary breaker: two consecutive
# failures skip the primary for two minutes, one success closes it.
primary_breaker = CircuitBreaker("primary LLM", failure_threshold=2, cooldown_seconds=120)

# End-to-end ceiling for one blocking generate(): cloud tier + primary
# retries + the whole fallback chain + safety valve could otherwise add up to
# well over ten minutes while a request (and its worker) waits.
GENERATE_DEADLINE_S = float(os.environ.get("LLM_GENERATE_DEADLINE_S", "150"))

# Deliberately the SAME telemetry identity as the gateway primary: auxiliary
# tokens then count against the same monthly cap and show up in the same bill.
# The `tier` column is what tells the call sites apart.
_AUX_PRIMARY_NAME = "deepseek"


def aux_cloud_provider(*, timeout: int = AUX_TIMEOUT_S) -> "OpenAIChatProvider | None":
    """The paid primary for a short auxiliary call, or None to stay local.

    None means: DeepSeek isn't the configured primary, or the shared monthly
    ceiling is spent, or the client can't be built — in every case the caller
    falls back to its own local Ollama path.
    """
    if not (LLM.primary_provider == "deepseek" and LLM.deepseek_api_key):
        return None
    if not primary_budget_available(_AUX_PRIMARY_NAME):
        return None
    try:
        return OpenAIChatProvider(
            base_url=LLM.deepseek_base_url, api_key=LLM.deepseek_api_key,
            model=LLM.deepseek_model, timeout=timeout, name=_AUX_PRIMARY_NAME,
            max_retries=0,
        )
    except Exception as e:  # missing openai pkg / bad config — degrade to local
        logger.warning("auxiliary cloud provider unavailable: %s", e)
        return None


def aux_generate(provider: LLMProvider, prompt: str, *,
                 options: dict, tier: str) -> str | None:
    """Run ONE auxiliary call. Returns the text, or None on any failure.

    Never raises and never retries — the caller's own degraded path is cheaper
    than a second attempt. Every call is logged to llm_calls (paid auxiliary
    spend is as visible as chat spend) and reported to `aux_breaker`.
    """
    model = getattr(provider, "model", "unknown")
    start = time.monotonic()
    deadline = _deadline_for(provider)
    # A short call: its first token within the provider timeout, all of it
    # within the wall-clock deadline.
    limits = CallLimits(first_token=deadline, total=deadline + float(getattr(provider, "timeout", 8) or 8))
    try:
        with call_limits(limits):
            data = call_with_deadline(
                provider.generate, limits.total, prompt, options=options, lane=AUX_LANE,
            )
    except Exception as e:
        _log_call(provider.name, model, int((time.monotonic() - start) * 1000),
                  None, None, streamed=False, ok=False, tier=tier,
                  route_reason=_failure_reason(e))
        aux_breaker.record(False)
        logger.warning("auxiliary %s call failed: %s", tier, e)
        return None
    latency = int((time.monotonic() - start) * 1000)
    _log_call(provider.name, model, latency,
              data.get("prompt_eval_count"), data.get("eval_count"),
              streamed=False, ok=True, tier=tier)
    aux_breaker.record(True)
    return (data.get("response") or "").strip()


def _failure_reason(exc: BaseException) -> str | None:
    """route_reason for a failed call's llm_calls row."""
    if isinstance(exc, LLMDeadlineExceeded):
        return "deadline"
    if isinstance(exc, LLMProviderBusy):
        return "lane_full"
    return None


def _lane_for(provider: object) -> _Lane:
    """Paid/cloud providers and the local chain never share threads."""
    if isinstance(provider, (OpenAIChatProvider, OpenAICompatProvider)):
        return PRIMARY_LANE
    return LOCAL_LANE


# ─────────────────────────────────────────────────────────────────────────────
# Gateway
# ─────────────────────────────────────────────────────────────────────────────
class AIGateway:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or self._default_provider()
        self.primary_model = self._provider_model()
        self.model = self.primary_model

    @staticmethod
    def _default_provider() -> LLMProvider:
        """DeepSeek (or any OpenAI-compatible) as primary when configured;
        otherwise the local Ollama model. Local chain stays as fallback."""
        if LLM.primary_provider == "deepseek" and LLM.deepseek_api_key:
            try:
                return OpenAIChatProvider(
                    base_url=LLM.deepseek_base_url, api_key=LLM.deepseek_api_key,
                    model=LLM.deepseek_model, timeout=LLM.cloud_tier_timeout,
                    name="deepseek",
                )
            except Exception as e:  # missing openai pkg / bad config — degrade
                logger.warning("DeepSeek primary unavailable, using local: %s", e)
        return OllamaProvider(
            base_url=LLM.base_url, model=LLM.primary_model, timeout=LLM.request_timeout
        )

    def _provider_model(self) -> str:
        """Safely read the provider runtime model."""
        provider_model = getattr(self.provider, "model", None)
        if isinstance(provider_model, str) and provider_model:
            return provider_model
        return LLM.primary_model

    def _options(self, overrides: dict | None) -> dict:
        opts = {"temperature": LLM.temperature}
        if overrides:
            opts.update(overrides)
        return opts

    async def _try_provider(self, prompt: str, opts: dict, base_url: str, model: str,
                            timeout: int, label: str) -> LLMResult | None:
        """Try a single provider/model combo. Returns result or None on failure."""
        provider = OllamaProvider(base_url=base_url, model=model, timeout=timeout)
        start = time.monotonic()
        try:
            # Wall-clock bound: the provider's own timeout, never past what is
            # left of the generate() budget (a 180 s local model must not
            # outlive a 150 s request).
            budget = _GENERATE_DEADLINE.get()
            cap = max(0.1, budget - time.monotonic()) if budget is not None else None
            data = await acall_with_deadline(
                provider.generate, _deadline_for(provider, cap), prompt,
                options=opts, lane=_lane_for(provider),
            )
            latency = int((time.monotonic() - start) * 1000)
            text = (data.get("response") or "").strip()
            if not text:
                logger.warning("%s returned empty response", label)
                return None
            result = LLMResult(
                text=text, model=model, latency_ms=latency,
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
            )
            _log_call(provider.name, model, latency,
                      result.prompt_tokens, result.completion_tokens,
                      streamed=False, ok=True)
            return result
        except Exception as e:
            _log_call(provider.name, model, 0, None, None, streamed=False, ok=False)
            logger.warning("%s failed: %s", label, e)
            return None

    _FALLBACK_PROVIDER_NAME = "deepseek_fallback"

    def _safety_valve_provider(self) -> "OpenAIChatProvider | None":
        """Last-resort DeepSeek provider — the «صمام الأمان» of the plan.

        Returns None unless: the flag is on, a key exists, the primary isn't
        already DeepSeek, and the monthly hard cap has headroom (fail-closed).
        """
        if not (LLM.deepseek_fallback_enabled and LLM.deepseek_api_key):
            return None
        if isinstance(self.provider, OpenAIChatProvider):
            return None  # DeepSeek already primary — nothing to add
        used = _monthly_tokens_used(self._FALLBACK_PROVIDER_NAME)
        if used >= LLM.deepseek_fallback_monthly_token_cap:
            logger.warning(
                "cloud safety valve budget exhausted (%d/%d tokens this month) — staying local-only",
                used, LLM.deepseek_fallback_monthly_token_cap,
            )
            return None
        try:
            return OpenAIChatProvider(
                base_url=LLM.deepseek_base_url, api_key=LLM.deepseek_api_key,
                model=LLM.deepseek_model, timeout=LLM.cloud_tier_timeout,
                name=self._FALLBACK_PROVIDER_NAME,
            )
        except Exception as e:
            logger.warning("cloud safety valve unavailable: %s", e)
            return None

    def _primary_within_budget(self) -> bool:
        """Is the paid primary still under its monthly ceiling?

        Checked per call — never in _default_provider() — because the gateway
        is a module-level singleton built once at startup: a construction-time
        check would be evaluated exactly once and the cap would never bite.

        The asymmetry with the safety valve is deliberate; see
        primary_budget_available(), which the auxiliary tier shares.
        """
        if not isinstance(self.provider, OpenAIChatProvider):
            return True  # local primary — nothing is being billed
        return primary_budget_available(self.provider.name)

    def _cloud_provider(self) -> "OpenAICompatProvider | None":
        """Build the Azure quality-tier provider if fully configured."""
        if not (LLM.cloud_tier_enabled and LLM.azure_endpoint and LLM.azure_api_key):
            return None
        try:
            return OpenAICompatProvider(
                endpoint=LLM.azure_endpoint, api_key=LLM.azure_api_key,
                api_version=LLM.azure_api_version, model=LLM.azure_model,
                timeout=LLM.cloud_tier_timeout,
            )
        except Exception as e:  # missing openai package etc. — degrade to local
            logger.warning("cloud tier unavailable: %s", e)
            return None

    async def _blocking(self, provider: LLMProvider, prompt: str, opts: dict,
                        remaining: float) -> dict:
        """One blocking call on the provider's lane, inside its limits.

        An OpenAI-compatible provider aborts itself (CallLimits): a held
        request at its first-token limit, a slow-but-alive one only at the end
        of the budget. Anything else is cut by the caller's wall clock.
        """
        if isinstance(provider, OpenAIChatProvider):
            limits = CallLimits(first_token=_deadline_for(provider, remaining), total=remaining)
            wait = remaining + _DEADLINE_SLACK_S
        else:
            limits = CallLimits()
            wait = _deadline_for(provider, remaining)
        with call_limits(limits):
            return await acall_with_deadline(
                provider.generate, wait, prompt, options=opts, lane=_lane_for(provider),
            )

    async def generate(self, prompt: str, *, options: dict | None = None,
                       max_retries: int | None = None,
                       tier: str = "local_fast",
                       route_reason: str | None = None) -> LLMResult:
        """Blocking generation with primary + full fallback chain. Raises on total failure."""
        retries = max_retries if max_retries is not None else LLM.max_retries
        opts = self._options(options)
        last_err: Exception | None = None
        deadline = time.monotonic() + GENERATE_DEADLINE_S
        budget_token = _GENERATE_DEADLINE.set(deadline)

        def _remaining() -> float:
            return max(0.1, deadline - time.monotonic())

        def _out_of_time(stage: str) -> bool:
            if time.monotonic() < deadline:
                return False
            logger.warning("generate() deadline (%.0fs) reached before %s",
                           GENERATE_DEADLINE_S, stage)
            return True

        try:
            # Cloud quality tier first when routed there; local chain remains
            # the fallback so a cloud failure is invisible to the caller.
            if tier == "cloud_quality":
                cloud = self._cloud_provider()
                if cloud is not None:
                    start = time.monotonic()
                    try:
                        data = await self._blocking(cloud, prompt, opts, _remaining())
                        latency = int((time.monotonic() - start) * 1000)
                        text = (data.get("response") or "").strip()
                        if text:
                            result = LLMResult(
                                text=text, model=cloud.model, latency_ms=latency,
                                prompt_tokens=data.get("prompt_eval_count"),
                                completion_tokens=data.get("eval_count"),
                            )
                            _log_call(cloud.name, cloud.model, latency,
                                      result.prompt_tokens, result.completion_tokens,
                                      streamed=False, ok=True,
                                      tier=tier, route_reason=route_reason)
                            return result
                    except Exception as e:
                        _log_call(cloud.name, cloud.model, 0, None, None,
                                  streamed=False, ok=False,
                                  tier=tier, route_reason=route_reason)
                        logger.warning("cloud quality tier failed, using local: %s", e)

            # 1. Try primary model with retries — unless the paid primary has
            #    burnt its monthly ceiling, in which case we skip the loop
            #    outright (range(1, 1) is empty) and drop into the local
            #    fallback chain below, exactly as if the provider had failed.
            if not self._primary_within_budget():
                retries = 0
            paid_primary = isinstance(self.provider, OpenAIChatProvider)
            for attempt in range(1, retries + 1):
                if _out_of_time(f"primary attempt {attempt}"):
                    break
                # Re-checked every attempt: two failures open it, and retrying
                # a provider the breaker just declared dead is a paid request
                # into the same hole.
                if paid_primary and primary_breaker.is_open():
                    logger.warning("primary LLM circuit open — going straight to the local chain")
                    break
                if _remaining() < _MIN_ATTEMPT_S:
                    logger.warning("generate(): %.0fs left — not starting primary attempt %d",
                                   _remaining(), attempt)
                    break
                start = time.monotonic()
                try:
                    data = await self._blocking(self.provider, prompt, opts, _remaining())
                    latency = int((time.monotonic() - start) * 1000)
                    text = (data.get("response") or "").strip()
                    if not text:
                        logger.warning("Primary returned empty response on attempt %d/%d", attempt, retries)
                        if attempt < retries:
                            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    result = LLMResult(
                        text=text, model=self._provider_model(), latency_ms=latency,
                        prompt_tokens=data.get("prompt_eval_count"),
                        completion_tokens=data.get("eval_count"),
                    )
                    _log_call(self.provider.name, result.model, latency,
                              result.prompt_tokens, result.completion_tokens,
                              streamed=False, ok=True)
                    if paid_primary:
                        primary_breaker.record(True)
                    return result
                except Exception as e:
                    last_err = e
                    if paid_primary:
                        primary_breaker.record(False)
                    # Recorded, not silently dropped. The monthly cap is a sum
                    # over this table, and a timeout here is the case where the
                    # provider most likely *did* count the tokens — the request
                    # reached it and the answer did not come back. Tokens stay
                    # null because they are genuinely unknown; inventing an
                    # estimate would be the same mistake with the opposite sign.
                    _log_call(self.provider.name, self._provider_model(),
                              int((time.monotonic() - start) * 1000),
                              None, None, streamed=False, ok=False,
                              route_reason=_failure_reason(e))
                    logger.warning("Primary attempt %d/%d failed: %s", attempt, retries, e)
                    # A held or saturated provider is not retried: each retry
                    # used to be another paid request into the same hold, all
                    # of them running at once.
                    if isinstance(e, (LLMDeadlineExceeded, LLMProviderBusy)):
                        break
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

            # 2. Try fallback chain
            for fb in LLM.fallback_chain():
                if _out_of_time(f"fallback {fb['name']}"):
                    break
                logger.warning("⚠️ trying fallback: %s (%s@%s)", fb["name"], fb["model"], fb["url"])
                result = await self._try_provider(
                    prompt, opts, fb["url"], fb["model"], fb["timeout"], fb["name"]
                )
                if result:
                    return result

            # 3. Cloud safety valve — only when the whole local chain is down.
            valve = None if _out_of_time("safety valve") else self._safety_valve_provider()
            if valve is not None:
                logger.warning("⚠️ local chain exhausted — trying cloud safety valve (%s)", valve.model)
                start = time.monotonic()
                try:
                    data = await self._blocking(valve, prompt, opts, _remaining())
                    latency = int((time.monotonic() - start) * 1000)
                    text = (data.get("response") or "").strip()
                    if text:
                        result = LLMResult(
                            text=text, model=valve.model, latency_ms=latency,
                            prompt_tokens=data.get("prompt_eval_count"),
                            completion_tokens=data.get("eval_count"),
                        )
                        _log_call(valve.name, valve.model, latency,
                                  result.prompt_tokens, result.completion_tokens,
                                  streamed=False, ok=True,
                                  tier=tier, route_reason=route_reason)
                        return result
                except Exception as e:
                    _log_call(valve.name, valve.model, 0, None, None,
                              streamed=False, ok=False,
                              tier=tier, route_reason=route_reason)
                    logger.warning("cloud safety valve failed: %s", e)

            _log_call(self.provider.name, self._provider_model(), 0, None, None,
                      streamed=False, ok=False)
            raise RuntimeError(f"LLM generation failed after all retries and fallbacks: {last_err}") from last_err
        finally:
            _GENERATE_DEADLINE.reset(budget_token)

    def _stream_provider(self, provider: LLMProvider, prompt: str,
                         opts: dict, tier: str | None = None,
                         route_reason: str | None = None) -> Iterator[StreamChunk]:
        """Stream from one provider. Raises on failure (caller decides to fall back)."""
        start = time.monotonic()
        text_parts: list[str] = []
        prompt_tokens = completion_tokens = None
        ok = False
        try:
            for obj in provider.stream(prompt, options=opts):
                delta = obj.get("response", "")
                if delta:
                    text_parts.append(delta)
                    yield StreamChunk(delta=delta, done=False)
                if obj.get("done"):
                    prompt_tokens = obj.get("prompt_eval_count")
                    completion_tokens = obj.get("eval_count")
                    ok = True
        except GeneratorExit:
            # The consumer closed us mid-answer (SSE client disconnected, see
            # assistant._pump_stream). Record the partial call so llm_calls
            # still shows the spend, then let the close unwind the provider.
            _log_call(provider.name, provider.model,
                      int((time.monotonic() - start) * 1000),
                      None, None, streamed=True, ok=False,
                      tier=tier, route_reason="client_disconnected")
            raise
        latency = int((time.monotonic() - start) * 1000)
        result = LLMResult(
            text="".join(text_parts).strip(),
            model=provider.model,
            latency_ms=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        _log_call(provider.name, result.model, latency,
                  prompt_tokens, completion_tokens, streamed=True, ok=ok,
                  tier=tier, route_reason=route_reason)
        yield StreamChunk(delta="", done=True, result=result)

    def note_stream_stall(self, tracker: "StreamTracker | None" = None) -> None:
        """The SSE consumer gave up waiting for tokens (assistant watchdog).

        Charged to the provider that was actually streaming: the paid primary
        only when the tracker shows it was the one on the line. A stream that
        never started (its worker was queued) contacted nobody, and a stall on
        the cloud tier or a local model says nothing about DeepSeek.
        """
        if tracker is None or not tracker.is_primary or tracker.attempt_started is None:
            return
        if not primary_breaker.is_open():
            primary_breaker.record(False)

    def stream(self, prompt: str, *, options: dict | None = None,
               tier: str = "local_fast",
               route_reason: str | None = None,
               tracker: "StreamTracker | None" = None) -> Iterator[StreamChunk]:
        """Streaming generation with pre-flight fallback.

        Uses stream_chain() (local-fast first) for low latency. Falls back
        through each provider only if the previous one fails before emitting
        any tokens (once tokens are flowing we cannot fall back — we raise).
        When routed to the cloud quality tier, the Azure provider is tried
        first and the local chain stays behind it — a cloud pre-flight
        failure is invisible to the SSE consumer.

        The paid primary is held to PRIMARY_FIRST_TOKEN_S for its first token:
        a request DeepSeek is holding is aborted and the next provider gets
        the question, instead of the whole stream waiting out the hold.
        `tracker`, when given, always names the provider currently streaming.
        """
        opts = self._options(options)

        candidates: list[tuple[str, LLMProvider]] = [
            (fb["name"], OllamaProvider(fb["url"], fb["model"], fb["timeout"]))
            for fb in LLM.stream_chain()
        ]
        # Primary OpenAI-compatible provider (DeepSeek) streams first; the
        # local Ollama chain above stays behind it as automatic fallback.
        # Dropped from the candidate list once the monthly ceiling is spent.
        if (isinstance(self.provider, OpenAIChatProvider)
                and self._primary_within_budget()
                and not primary_breaker.is_open()):
            candidates.insert(0, (self.provider.name, self.provider))
        if tier == "cloud_quality":
            cloud = self._cloud_provider()
            if cloud is not None:
                candidates.insert(0, ("cloud_quality", cloud))
        # Cloud safety valve streams LAST — reached only when every local
        # provider fails pre-flight (e.g. home server unreachable).
        valve = self._safety_valve_provider()
        if valve is not None:
            candidates.append((valve.name, valve))

        for label, provider in candidates:
            tokens_sent = False
            is_primary = provider is self.provider and isinstance(provider, OpenAIChatProvider)
            if tracker is not None:
                tracker.begin(label, is_primary)
            limits = CallLimits(first_token=PRIMARY_FIRST_TOKEN_S) if is_primary else CallLimits()
            try:
                with call_limits(limits):
                    for chunk in self._stream_provider(
                        provider, prompt, opts, tier=tier, route_reason=route_reason
                    ):
                        if not chunk.done:
                            tokens_sent = True
                            if tracker is not None and tracker.first_token_at is None:
                                tracker.first_token_at = time.monotonic()
                        yield chunk
                if is_primary:
                    primary_breaker.record(True)
                return  # success
            except Exception as e:
                if is_primary:
                    primary_breaker.record(False)
                _log_call(provider.name, provider.model, 0, None, None,
                          streamed=True, ok=False,
                          tier=tier, route_reason=_failure_reason(e) or route_reason)
                if tokens_sent:
                    # Can't undo sent tokens — propagate
                    logger.warning("Stream failed mid-stream on %s: %s", label, e)
                    raise
                logger.warning("Stream pre-flight failed on %s, trying next: %s", label, e)

        raise RuntimeError("All stream providers failed")


# Singleton accessor
_gateway: AIGateway | None = None


def get_gateway() -> AIGateway:
    global _gateway
    if _gateway is None:
        _gateway = AIGateway()
    return _gateway
