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
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Protocol

import httpx
import requests

from app.config.llm_config import LLM
from app.core.circuit_breaker import CircuitBreaker
from app.services import cloud_budget
from app.services.cloud_budget import (BudgetDenied, CloudBudget, record_call_reservations,
                                       unknown_usage_bounds, upper_token_bound)

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
# …and once it is answering: no new token for this long, or this long in all,
# is a hold too (a mid-answer keep-alive hold was never aborted).
PRIMARY_STALL_S = float(os.environ.get("LLM_PRIMARY_STALL_S", "60"))
PRIMARY_TOTAL_S = float(os.environ.get("LLM_PRIMARY_TOTAL_S", "300"))
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
    # The turn's stop check (assistant: the stream's cancel flag), tested on
    # every line: a cut turn closes its request instead of finishing it.
    stop: "Callable[[], bool] | None" = None


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
        # TimeoutError is one class in 3.11: the provider's own abort
        # (LLMDeadlineExceeded) lands here too. Keep its message.
        if fut.done() and not fut.cancelled():
            return fut.result()
        fut.cancel()  # a call still queued behind hung ones never starts
        raise LLMDeadlineExceeded(f"no reply within {deadline_s:.0f}s") from None


async def acall_with_deadline(fn, deadline_s: float, /, *args, lane: _Lane, **kwargs):
    """Async twin of `call_with_deadline` — awaits instead of blocking a thread."""
    fut = lane.submit(fn, *args, **kwargs)
    try:
        return await asyncio.wait_for(asyncio.wrap_future(fut), timeout=deadline_s)
    except (asyncio.TimeoutError, concurrent.futures.TimeoutError):
        # Same aliasing as above: re-raise the provider's own error unchanged.
        if fut.done() and not fut.cancelled():
            return fut.result()
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
    # The finish_reason when the text stopped short (length, content_filter,
    # aborted, insufficient_system_resource): usable, never cached.
    truncated: str | None = None


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
        self._budget_endpoint = endpoint
        self._client = AzureOpenAI(
            api_key=api_key, azure_endpoint=endpoint,
            api_version=api_version, timeout=timeout, max_retries=0, http_client=_HTTP,
        )

    def _report(self, ok: bool) -> None:
        try:
            from app.services.tier_router import record_cloud_result
            record_cloud_result(ok)
        except Exception:  # noqa: BLE001 — breaker is best-effort
            pass

    def generate(self, prompt: str, *, options: dict) -> dict:
        messages = [{"role": "user", "content": prompt}]
        output_cap = options.get("num_predict", 1024)
        charge = _reserve_wire_budget(self._budget_endpoint, self.name, messages, output_cap,
                                     model=self.model)
        try:
            try:
                r = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=options.get("temperature", 0.3),
                    max_tokens=output_cap,
                )
            except Exception:
                self._report(False)
                raise
            self._report(True)
            text = r.choices[0].message.content or ""
            flt = _ThinkFilter()
            text = flt.feed(text)
            usage = getattr(r, "usage", None)
            _settle_wire_budget(charge, getattr(usage, "prompt_tokens", None),
                                getattr(usage, "completion_tokens", None))
        finally:
            _settle_wire_budget(charge, None, None)  # no-op after a settled success
        return {
            "response": text, "done": True,
            "prompt_eval_count": getattr(usage, "prompt_tokens", None),
            "eval_count": getattr(usage, "completion_tokens", None),
        }

    def stream(self, prompt: str, *, options: dict) -> Iterator[dict]:
        messages = [{"role": "user", "content": prompt}]
        output_cap = options.get("num_predict", 1024)
        charge = _reserve_wire_budget(self._budget_endpoint, self.name, messages, output_cap,
                                     model=self.model)
        try:
            yield from self._stream_reserved(charge, messages, output_cap, options)
        finally:
            _settle_wire_budget(charge, None, None)  # no-op after a settled success

    def _stream_reserved(self, charge, messages, output_cap, options) -> Iterator[dict]:
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=options.get("temperature", 0.3),
                max_tokens=output_cap,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception:
            self._report(False)
            raise
        flt = _ThinkFilter()
        prompt_tokens = completion_tokens = None
        finished = False
        try:
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", None)
                    completion_tokens = getattr(usage, "completion_tokens", None)
                if not chunk.choices:
                    continue
                finished = finished or any(getattr(choice, "finish_reason", None)
                                          in ("stop", "length", "content_filter")
                                          for choice in chunk.choices)
                delta = chunk.choices[0].delta.content or ""
                delta = flt.feed(delta)
                if delta:
                    yield {"response": delta, "done": False}
            if not finished:
                raise ProviderStreamError("azure_deepseek: stream has no terminal choice")
        except Exception:
            self._report(False)
            raise
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                close()
        self._report(True)
        _settle_wire_budget(charge, prompt_tokens, completion_tokens)
        yield {
            "response": "", "done": True,
            "prompt_eval_count": prompt_tokens,
            "eval_count": completion_tokens,
        }


class ProviderHTTPError(RuntimeError):
    """The provider answered with an HTTP error status.

    The message carries the start of the response body: a bare "HTTP 402" or
    "HTTP 400" told nobody that the balance ran out or the model name was
    refused.
    """

    def __init__(self, name: str, status: int, body: str = "",
                 retry_after: float | None = None) -> None:
        super().__init__(f"{name} answered HTTP {status}" + (f": {body}" if body else ""))
        self.status = status
        self.body = body
        self.retry_after = retry_after


class ProviderStreamError(RuntimeError):
    """The stream was not a usable answer: an error event inside it, an end
    without [DONE], no content at all, or not an event stream in the first
    place. Raised before any token is yielded, it lets the gateway fall back.

    `usage` keeps the token counts the provider reported anyway: an empty
    answer is still a billed request, and the monthly cap is their sum.
    """

    def __init__(self, message: str, usage: tuple = (None, None)) -> None:
        super().__init__(message)
        self.usage = usage


class LLMCancelled(RuntimeError):
    """The turn this call was for has been cut (Stop, a newer question): stop
    working on it, and never fall back to another provider for it."""


# Statuses worth one more try before any byte of the answer arrived.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
# finish_reason values that mean the text stopped short of a full answer.
_TRUNCATING_FINISH = frozenset({"length", "content_filter", "aborted",
                                "insufficient_system_resource"})
PRIMARY_PREFLIGHT_RETRIES = max(0, int(os.environ.get("LLM_PRIMARY_PREFLIGHT_RETRIES", "2")))
_PREFLIGHT_BACKOFF_S = (0.5, 1.5)
_SNIPPET_BYTES = 300
_LINE_BREAK = re.compile(rb"\r\n|\r|\n")
# Process-wide memory of what DeepSeek refused, so it is asked once.
_MODEL_SWITCHED: dict[str, str] = {}      # configured model → model actually used
_NO_THINKING_FIELD: set[str] = set()      # endpoints that rejected "thinking"
_SERVED_MODELS_SEEN: set[tuple[str, str]] = set()


def _refuses_model(body: str) -> bool:
    b = body.lower()
    return "model" in b and any(k in b for k in (
        "not exist", "does not exist", "not found", "deprecat", "discontinu", "retired",
        "no longer", "unknown model", "invalid model"))


def _snippet(resp: httpx.Response) -> str:
    """The first ~300 bytes of a response body, without reading all of it."""
    got = b""
    for chunk in resp.iter_bytes():
        got += chunk
        if len(got) >= _SNIPPET_BYTES:
            break
    return got[:_SNIPPET_BYTES].decode("utf-8", errors="replace").strip()


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("retry-after")
    try:
        return max(0.0, float(raw)) if raw is not None else None
    except ValueError:
        return None  # an HTTP-date: fall back to our own back-off


def _sse_events(resp: httpx.Response, tick) -> Iterator[tuple[str | None, str]]:
    """(event, data) for each server-sent event in `resp`.

    Lines are split on CR, LF or CRLF only, over raw bytes: str.splitlines()
    (httpx's iter_lines) also breaks on U+2028/U+2029/U+0085, which JSON
    allows unescaped inside a string — the rest of that token was dropped.
    A CR at the end of a read is held back until the next byte shows whether
    it starts a CRLF. Several "data:" lines make one event, joined by "\n".
    `tick()` runs on every line, keep-alive comments included, so a wall
    clock is checked even while the provider only sends keep-alives.
    """
    buf = b""
    event: str | None = None
    data: list[str] = []

    def lines(final: bool):
        nonlocal buf
        while True:
            m = _LINE_BREAK.search(buf)
            if m is None or (not final and m.group() == b"\r" and m.end() == len(buf)):
                return
            raw, buf = buf[:m.start()], buf[m.end():]
            yield raw.decode("utf-8", errors="replace")

    def handle(line: str):
        nonlocal event, data
        tick()
        if not line:
            if data:
                yield (event, "\n".join(data))
            event, data = None, []
            return
        if line.startswith(":"):
            return  # comment — DeepSeek's ": keep-alive"
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "data":
            data.append(value)
        elif field == "event":
            event = value

    for chunk in resp.iter_bytes():
        buf += chunk
        for line in lines(final=False):
            yield from handle(line)
    for line in lines(final=True):
        yield from handle(line)
    if buf:
        yield from handle(buf.decode("utf-8", errors="replace"))
    if data:
        yield (event, "\n".join(data))


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

    Every call — blocking or streamed — is a streamed request read event by
    event, keep-alive comments included, with the wall clock and the turn's
    stop check (CallLimits) tested on every line. When a limit passes the
    response is closed: the request is aborted and the thread is free,
    instead of waiting out a DeepSeek hold that the per-read timeout never
    ends. Before any byte of the answer, a 429/5xx or a dropped connection is
    tried again (PRIMARY_PREFLIGHT_RETRIES, honouring Retry-After, within the
    first-token budget); after that there are no retries here — the gateway
    owns them and can see the deadline and the breaker. A read timeout is
    never retried.
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: int, name: str = "deepseek",
                 max_retries: int | None = None,
                 http_client: "httpx.Client | None" = None,
                 fallback_model: str | None = None) -> None:
        self.name = name
        self.model = model
        self.timeout = timeout
        self.max_retries = 0  # kept for old call sites; the SDK retries are gone
        self.fallback_model = fallback_model
        self._base = base_url.rstrip("/")
        self._url = self._base + "/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        self._http = http_client or _HTTP

    def _current_model(self) -> str:
        return _MODEL_SWITCHED.get(self.model, self.model)

    def _payload(self, prompt: str, options: dict) -> dict:
        payload = {
            "model": self._current_model(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": options.get("temperature", 0.3),
            "max_tokens": options.get("num_predict", 1024),
            "stream": True,
            # Token counts in a final chunk (DeepSeek sends them anyway; other
            # OpenAI-compatible hosts only on request). The monthly spend cap
            # is a sum of these counts — a stream without them reads as free.
            "stream_options": {"include_usage": True},
        }
        # DeepSeek's current models think by default: reasoning would count as
        # progress while eating max_tokens, and the answer could come back
        # empty. This assistant never wants the thinking mode.
        if self._base not in _NO_THINKING_FIELD:
            payload["thinking"] = {"type": "disabled"}
        return payload

    def _events(self, prompt: str, options: dict) -> Iterator[tuple]:
        """("delta", text) per piece of content, ("usage", p, c) for token
        counts, and finally ("final", finish_reason, served_model).

        Raises LLMDeadlineExceeded at a limit, LLMCancelled when the turn is
        cut, ProviderHTTPError / ProviderStreamError when the answer is not
        usable, httpx errors as they come.
        """
        limits = _CALL_LIMITS.get() or CallLimits()
        start = time.monotonic()
        first_budget = limits.first_token if limits.first_token is not None else PRIMARY_FIRST_TOKEN_S
        timeout = httpx.Timeout(float(self.timeout), connect=min(10.0, float(self.timeout)))
        state = {"last_progress": None, "bytes": False, "done": False, "attempted": False}

        def stopped() -> bool:
            return bool(limits.stop and limits.stop())

        def tick() -> None:
            state["bytes"] = True
            if state["done"]:
                return  # the answer is complete; only the body's tail is left
            now = time.monotonic()
            if stopped():
                raise LLMCancelled(f"{self.name}: turn cut")
            if limits.total is not None and now - start > limits.total:
                raise LLMDeadlineExceeded(f"{self.name}: over {limits.total:.0f}s in total")
            last = state["last_progress"]
            if last is None:
                if limits.first_token is not None and now - start > limits.first_token:
                    raise LLMDeadlineExceeded(
                        f"{self.name}: no first token after {limits.first_token:.0f}s")
            elif limits.stall is not None and now - last > limits.stall:
                raise LLMDeadlineExceeded(f"{self.name}: no new token for {limits.stall:.0f}s")

        def wait_or_give_up(seconds: float) -> bool:
            """Sleep before a retry, unless that would break the first-token
            budget or the turn is cut meanwhile."""
            if time.monotonic() - start + seconds > first_budget:
                return False
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                if stopped():
                    raise LLMCancelled(f"{self.name}: turn cut")
                time.sleep(min(0.1, max(0.0, end - time.monotonic())))
            return True

        attempt = 0
        while True:
            if stopped():
                raise LLMCancelled(f"{self.name}: turn cut")
            payload = self._payload(prompt, options)
            try:
                charge = _reserve_wire_budget(self._base, self.name,
                                              payload["messages"], payload["max_tokens"],
                                              model=payload["model"])
            except BudgetDenied as exc:
                if state["attempted"]:
                    exc.usage = (None, None)  # earlier retry's billing remains unknown
                raise
            final_usage = (None, None)
            try:
                state["attempted"] = True
                with self._http.stream("POST", self._url, json=payload,
                                       headers=self._headers, timeout=timeout) as resp:
                    if resp.status_code >= 400:
                        body = _snippet(resp)
                        err = ProviderHTTPError(self.name, resp.status_code, body, _retry_after(resp))
                        if (resp.status_code == 400 and self.fallback_model
                                and self._current_model() != self.fallback_model
                                and _refuses_model(body)):
                            _MODEL_SWITCHED[self.model] = self.fallback_model
                            logger.error(
                                "🚨 %s refused model %r (%s) — switching to %r for this process. "
                                "Set DEEPSEEK_MODEL to a documented model.",
                                self.name, self.model, body[:120], self.fallback_model)
                            continue
                        if (resp.status_code in (400, 422) and "thinking" in body.lower()
                                and self._base not in _NO_THINKING_FIELD):
                            _NO_THINKING_FIELD.add(self._base)
                            logger.warning("%s does not accept the 'thinking' field — sending "
                                           "requests without it", self.name)
                            continue
                        if (resp.status_code in _RETRYABLE_STATUS
                                and attempt < PRIMARY_PREFLIGHT_RETRIES):
                            wait = err.retry_after if err.retry_after is not None \
                                else _PREFLIGHT_BACKOFF_S[min(attempt, len(_PREFLIGHT_BACKOFF_S) - 1)]
                            if wait_or_give_up(wait):
                                attempt += 1
                                logger.info("%s answered %s — retry %d after %.1fs",
                                            self.name, resp.status_code, attempt, wait)
                                continue
                        raise err
                    ctype = resp.headers.get("content-type", "")
                    if not ctype.startswith("text/event-stream"):
                        body = _snippet(resp)
                        raise ProviderStreamError(
                            f"{self.name}: answered {ctype or 'no content type'}, not an event stream: {body}")
                    for ev in self._read_stream(resp, tick, state):
                        if ev[0] == "usage":
                            final_usage = (ev[1], ev[2])
                        yield ev
                    _settle_wire_budget(charge, *final_usage)
                    return
            except (httpx.NetworkError, httpx.RemoteProtocolError) as e:
                # Connect/read/protocol failures — never a timeout (R7) — and
                # before any byte only: once the answer has started, a retry
                # would repeat (and re-bill) what the parent already saw.
                if state["bytes"] or attempt >= PRIMARY_PREFLIGHT_RETRIES:
                    raise
                if not wait_or_give_up(_PREFLIGHT_BACKOFF_S[min(attempt, len(_PREFLIGHT_BACKOFF_S) - 1)]):
                    raise
                attempt += 1
                logger.info("%s connection failed (%s) — retry %d", self.name, type(e).__name__, attempt)
            finally:
                # This attempt ended without a settled answer: an error, a
                # retry (`continue`), a cut stream, or the consumer leaving
                # (GeneratorExit). Charge its own bound, not the context.
                _settle_wire_budget(charge, None, None)

    def _read_stream(self, resp: httpx.Response, tick, state: dict) -> Iterator[tuple]:
        finish: str | None = None
        served: str | None = None
        usage_seen: tuple = (None, None)
        got_content = False
        done = False
        for event, data in _sse_events(resp, tick):
            if done:
                continue  # read to the end of the body so the connection is reused
            if data.strip() == "[DONE]":
                done = state["done"] = True
                continue
            try:
                obj = json.loads(data)
            except ValueError:
                logger.warning("%s sent unparseable stream data: %r", self.name, data[:120])
                continue
            if not isinstance(obj, dict):
                continue
            if event == "error" or obj.get("error"):
                err = obj.get("error")
                msg = err.get("message") if isinstance(err, dict) else err
                raise ProviderStreamError(f"{self.name} reported an error: {str(msg)[:_SNIPPET_BYTES]}")
            if served is None and obj.get("model"):
                served = str(obj["model"])
            usage = obj.get("usage")
            if isinstance(usage, dict):
                usage_seen = (usage.get("prompt_tokens"), usage.get("completion_tokens"))
                yield ("usage", *usage_seen)
            for choice in obj.get("choices") or []:
                delta = (choice or {}).get("delta") or {}
                # Reasoning is progress (the model is alive) but not output.
                if delta.get("reasoning_content"):
                    state["last_progress"] = time.monotonic()
                content = delta.get("content")
                if content:
                    state["last_progress"] = time.monotonic()
                    got_content = True
                    yield ("delta", content)
                if choice and choice.get("finish_reason"):
                    finish = choice["finish_reason"]
        if not done:
            raise ProviderStreamError(f"{self.name}: the stream ended without [DONE]", usage_seen)
        if not got_content:
            raise ProviderStreamError(
                f"{self.name}: no answer (finish_reason={finish or 'none'})", usage_seen)
        if served and (self._current_model(), served) not in _SERVED_MODELS_SEEN:
            _SERVED_MODELS_SEEN.add((self._current_model(), served))
            logger.info("%s: asked for %r, served by %r", self.name, self._current_model(), served)
        yield ("final", finish, served)

    def generate(self, prompt: str, *, options: dict) -> dict:
        parts: list[str] = []
        prompt_tokens = completion_tokens = None
        finish = served = None
        for ev in self._events(prompt, options):
            if ev[0] == "delta":
                parts.append(ev[1])
            elif ev[0] == "usage":
                prompt_tokens, completion_tokens = ev[1], ev[2]
            else:
                finish, served = ev[1], ev[2]
        text = _ThinkFilter().feed("".join(parts))
        return {
            "response": text, "done": True,
            "prompt_eval_count": prompt_tokens, "eval_count": completion_tokens,
            "model": served or self._current_model(),
            "truncated": finish if finish in _TRUNCATING_FINISH else None,
        }

    def stream(self, prompt: str, *, options: dict) -> Iterator[dict]:
        flt = _ThinkFilter()
        prompt_tokens = completion_tokens = None
        finish = served = None
        for ev in self._events(prompt, options):
            if ev[0] == "usage":
                prompt_tokens, completion_tokens = ev[1], ev[2]
                continue
            if ev[0] == "final":
                finish, served = ev[1], ev[2]
                continue
            delta = flt.feed(ev[1])
            if delta:
                yield {"response": delta, "done": False}
        yield {
            "response": "", "done": True,
            "prompt_eval_count": prompt_tokens, "eval_count": completion_tokens,
            "model": served or self._current_model(),
            "truncated": finish if finish in _TRUNCATING_FINISH else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry (non-fatal)
# ─────────────────────────────────────────────────────────────────────────────
_telemetry_schema_ready = False


def _ensure_telemetry_schema(conn: sqlite3.Connection) -> None:
    """Validate/adopt this database; a process flag cannot identify its schema."""
    from app.db.migrations.runner import apply_migrations
    from app.db.migrations.telemetry_0001_llm_calls import MIGRATION as LLM_CALLS
    from app.db.migrations.telemetry_0002_usage_estimated import MIGRATION as USAGE_ESTIMATED

    global _telemetry_schema_ready
    if (_ledger().anchor_path.exists()
            or conn.execute("SELECT 1 FROM sqlite_master WHERE name='cloud_budget_identity'").fetchone()):
        # Diagnostic writes must not silently heal lost activated history:
        # an activated ledger whose llm_calls vanished fails here, before the
        # migration runner could recreate an empty table.
        conn.execute('SELECT ts,provider,prompt_tokens,completion_tokens FROM llm_calls LIMIT 0')
    apply_migrations(conn, "llm_telemetry", (LLM_CALLS, USAGE_ESTIMATED))
    # Retained for existing diagnostic/test callers, never used to skip a DB.
    _telemetry_schema_ready = True


# ── Token counts the provider did not report ───────────────────────────────
# DeepSeek reports usage in the LAST chunk of a stream. A stream cut before it
# (the parent left, the turn was cut, a deadline, a broken stream), a timeout,
# or a host that ignores include_usage leaves the counts unknown — and in
# October 2026 that was 26 paid rows with NULL tokens, which a monthly cap
# cannot sum. They are now estimated from the text sent and received and
# flagged usage_estimated=1: never NULL, never a silent zero.
#
# The estimate is UTF-8 bytes / 3, rounded up. DeepSeek documents ~0.3 token
# per English character and ~0.6 per Chinese one; bytes/3 gives 0.33 and 1.0,
# and 0.67 for Arabic (2 bytes a letter) — on the high side, which is the
# safe side for a spending cap. The completion estimate counts only the text
# that arrived, so for a cut stream it is a lower bound: the provider may
# have generated a little more before it saw the connection close.
_ESTIMATE_BYTES_PER_TOKEN = 3


def _estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return -(-len(text.encode("utf-8", "replace")) // _ESTIMATE_BYTES_PER_TOKEN)


def _never_generated(exc: BaseException | None) -> bool:
    """The provider refused the request or never received it: nothing was
    generated, so nothing is billed. The row then carries an explicit zero."""
    if exc is None:
        return False
    if isinstance(exc, (ProviderHTTPError, LLMProviderBusy,
                        httpx.ConnectError, httpx.ConnectTimeout)):
        return True
    # openai SDK errors (tools using record_chat_completion): an HTTP status
    # answer is a refusal; a timeout or a dropped connection is not.
    return isinstance(getattr(exc, "status_code", None), int)


def _fill_usage(prompt_tokens: int | None, completion_tokens: int | None,
                prompt: str | None, received: str,
                exc: BaseException | None) -> tuple[int | None, int | None, bool]:
    """(prompt_tokens, completion_tokens, estimated) for one llm_calls row."""
    if prompt_tokens is not None and completion_tokens is not None:
        return prompt_tokens, completion_tokens, False
    if prompt is None:
        # The caller knows nothing about the request (a local fallback with
        # no prompt at hand): unknown stays unknown, visibly.
        return prompt_tokens, completion_tokens, False
    if _never_generated(exc):
        return (prompt_tokens if prompt_tokens is not None else 0,
                completion_tokens if completion_tokens is not None else 0, True)
    return (prompt_tokens if prompt_tokens is not None else _estimate_tokens(prompt),
            completion_tokens if completion_tokens is not None else _estimate_tokens(received),
            True)


def _ledger() -> CloudBudget:
    """The cap's ledger on the telemetry DB, with the configured anchor."""
    return CloudBudget(_TELEMETRY_DB, anchor_path=getattr(LLM, "cloud_budget_anchor_path", "") or None)


def _connect_telemetry() -> sqlite3.Connection:
    ledger = _ledger()
    if ledger.anchor_path.exists():
        # A diagnostic call on a lost activated volume must not create a DB.
        return sqlite3.connect(ledger.path.as_uri() + '?mode=rw', uri=True)
    return sqlite3.connect(_TELEMETRY_DB)


def _log_call(provider: str, model: str, latency_ms: int,
              prompt_tokens: int | None, completion_tokens: int | None,
              streamed: bool, ok: bool,
              tier: str | None = None, route_reason: str | None = None, *,
              prompt: str | None = None, received: str = "",
              exc: BaseException | None = None,
              reservation_ids: list | None = None) -> None:
    """One llm_calls row. Pass `prompt` (and `received`, `exc`) for any call
    that may have reached a provider: counts it did not report are then
    estimated and flagged instead of left NULL. Never raises."""
    ids = list(reservation_ids) if reservation_ids is not None else _drain_reservations()
    try:
        prompt_tokens, completion_tokens, estimated = _fill_usage(
            prompt_tokens, completion_tokens, prompt, received, exc)
        _TELEMETRY_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = _connect_telemetry()
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        _ensure_telemetry_schema(conn)
        cur = conn.execute(
            "INSERT INTO llm_calls (provider,model,latency_ms,prompt_tokens,"
            "completion_tokens,streamed,ok,tier,route_reason,usage_estimated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (provider, model, latency_ms, prompt_tokens, completion_tokens,
             int(streamed), int(ok), tier, route_reason, int(estimated)),
        )
        if ids:
            record_call_reservations(conn, cur.lastrowid, ids)
        conn.commit()
        conn.close()
    except Exception as e:  # telemetry must never break a request
        logger.debug("telemetry skipped: %s", e)


# Sentinel returned when the telemetry DB can't be read. Callers that must not
# spend blind compare it against their cap and lose; local fallback stays live.
_BUDGET_UNKNOWN = 1 << 62
# This memo is an advisory routing shortcut ONLY. Every paid wire attempt
# independently reserves atomically; a stale routing total cannot grant spend.
_BUDGET_CACHE_TTL = 60.0
_budget_cache: dict[str, tuple[float, int]] = {}


def _monthly_tokens_used(provider_name: str) -> int:
    """Total tokens logged for a provider since the start of the current month.

    Fails CLOSED: if telemetry can't be read we report _BUDGET_UNKNOWN, an
    impossibly large number, so a budget-gated caller refuses to spend.
    """
    try:
        conn = _connect_telemetry()
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
    """Soft monthly ceiling on the PAID primary; with CLOUD_BUDGET_ENFORCE on,
    advisory routing only (paid-wire admission is atomic, below).

    Shared by the chat path (AIGateway._primary_within_budget) and the
    auxiliary path (aux_cloud_provider) so both spend from ONE wallet against
    ONE ceiling — a classifier that had its own budget would be an invisible
    second bill.

    Unreadable telemetry: switch off, fails OPEN as before the ledger (the
    primary is the app's main way of answering and broken telemetry must not
    silence it); switch on, fails closed to cloud, local chain stays live.
    """
    cap = LLM.deepseek_primary_monthly_token_cap
    if cap <= 0:
        return True  # 0 disables the ceiling
    used = _monthly_tokens_used_cached(provider_name)
    if used >= _BUDGET_UNKNOWN:
        return not getattr(LLM, "cloud_budget_enforce", False)
    if used >= cap:
        logger.warning(
            "primary provider budget exhausted (%d/%d tokens this month) — "
            "falling back to the local chain",
            used, cap,
        )
        return False
    return True


def _reserve_wire_budget(endpoint: str, provider_name: str, messages: list[dict],
                         output_cap: int, *, model: str):
    """Authorize one physical wire attempt, never a whole gateway operation.

    None (no reservation, no denial) unless CLOUD_BUDGET_ENFORCE is on.
    """
    from urllib.parse import urlsplit

    if not getattr(LLM, "cloud_budget_enforce", False):
        return None  # switch off: pre-ledger behaviour, nothing reserved or denied

    parsed = urlsplit(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise BudgetDenied("cloud budget cannot identify the provider wallet")
    # Route names, model changes and key rotation never create another wallet.
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    wallet = f"cloud:{parsed.scheme}://{parsed.hostname.lower()}:{port}"
    azure = provider_name == "azure_deepseek"
    primary = azure or getattr(LLM, "primary_provider", "deepseek") == "deepseek"
    cap = (LLM.deepseek_primary_monthly_token_cap if primary
           else LLM.deepseek_fallback_monthly_token_cap)
    if type(cap) is not int or cap < 0:
        raise BudgetDenied("cloud budget invalid monthly cap")
    if cap == 0 and primary:
        return None  # explicit documented unlimited opt-out, not a hard-cap mode
    bound = upper_token_bound(messages, output_cap, endpoint=endpoint, model=model,
                              profile_aliases=dict(getattr(LLM, "deepseek_billing_profile_aliases", ())))
    # Old telemetry has no endpoint/account identifier. It cannot prove that
    # these aliases spent from different wallets, so conservatively import all.
    aliases = tuple(sorted({"azure_deepseek", "deepseek", "deepseek_aux",
                            "deepseek_fallback", provider_name}))
    ledger = _ledger()
    ticket = ledger.reserve(wallet, cap, bound, legacy_aliases=aliases,
                            unknown_usage_bounds=unknown_usage_bounds(messages, output_cap))
    sink = _RESERVATION_SINK.get()
    if sink is not None:
        sink.append(ticket.id)
    return _WireCharge(ledger, ticket)


# The ledger attempts made since the last llm_calls row in this call scope.
# Set by each paid entry point (generate, _stream_provider, aux_generate,
# record_chat_completion); lanes copy the context into their worker threads,
# so a provider's reservation lands in its caller's list. _log_call drains it
# into llm_call_reservations, which the monthly rollover requires.
_RESERVATION_SINK: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "cloud_budget_reservations", default=None)


@contextlib.contextmanager
def _reservation_scope():
    token = _RESERVATION_SINK.set([])
    try:
        yield
    finally:
        try:
            _RESERVATION_SINK.reset(token)
        except ValueError:
            pass  # a generator finalised from another context


def _drain_reservations() -> list:
    sink = _RESERVATION_SINK.get()
    if not sink:
        return []
    ids = list(sink)
    sink.clear()
    return ids


class _WireCharge:
    """One reserved wire attempt; settled exactly once.

    Every exit settles: success with the reported usage, anything else
    (error, retry, cut stream, consumer gone) with unknown usage, which the
    ledger charges at the request's own bound instead of the whole context.
    """

    def __init__(self, ledger: CloudBudget, ticket):
        self.ledger, self.ticket, self.done = ledger, ticket, False

    def settle(self, prompt_tokens, completion_tokens) -> None:
        if not self.done:
            self.done = True
            # Never waits on the request path: inline if the ledger is free,
            # else the background settler (cloud_budget.SETTLER).
            cloud_budget.SETTLER.submit(self.ledger, self.ticket, prompt_tokens, completion_tokens)


def _settle_wire_budget(charge, prompt_tokens, completion_tokens) -> None:
    if charge is not None:
        charge.settle(prompt_tokens, completion_tokens)


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


def _fallback_model() -> str | None:
    """DEEPSEEK_MODEL_FALLBACK — read leniently: config stand-ins (tests,
    an older LLMConfig) may not carry it, and a missing fallback must not
    cost the primary."""
    return getattr(LLM, "deepseek_model_fallback", None) or None


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
            max_retries=0, fallback_model=_fallback_model(),
        )
    except Exception as e:  # missing openai pkg / bad config — degrade to local
        logger.warning("auxiliary cloud provider unavailable: %s", e)
        return None


_USE_AUX_BREAKER = object()


def aux_generate(provider: LLMProvider, prompt: str, *,
                 options: dict, tier: str,
                 breaker: "CircuitBreaker | None | object" = _USE_AUX_BREAKER) -> str | None:
    """See _aux_generate; its llm_calls row names its ledger reservations."""
    with _reservation_scope():
        return _aux_generate(provider, prompt, options=options, tier=tier, breaker=breaker)


def _aux_generate(provider: LLMProvider, prompt: str, *,
                  options: dict, tier: str,
                  breaker: "CircuitBreaker | None | object" = _USE_AUX_BREAKER) -> str | None:
    """Run ONE auxiliary call. Returns the text, or None on any failure.

    Never raises and never retries — the caller's own degraded path is cheaper
    than a second attempt. Every call is logged to llm_calls (paid auxiliary
    spend is as visible as chat spend) and reported to `aux_breaker`.

    `breaker=None` keeps a background caller out of the shared breaker: the
    child-memory extractor runs after the answer with a longer timeout, and two
    of its slow calls must not switch the classifier and the rewriter — which
    sit on the answer's critical path — to their degraded tier.
    """
    if breaker is _USE_AUX_BREAKER:
        breaker = aux_breaker
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
                  *getattr(e, "usage", (None, None)), streamed=False, ok=False, tier=tier,
                  route_reason=_failure_reason(e), prompt=prompt, exc=e)
        if breaker is not None and not isinstance(e, BudgetDenied):
            breaker.record(False)
        logger.warning("auxiliary %s call failed: %s", tier, e)
        return None
    latency = int((time.monotonic() - start) * 1000)
    _log_call(provider.name, model, latency,
              data.get("prompt_eval_count"), data.get("eval_count"),
              streamed=False, ok=True, tier=tier,
              prompt=prompt, received=data.get("response") or "")
    if breaker is not None:
        breaker.record(True)
    return (data.get("response") or "").strip()


# ── Paid calls made outside the gateway ────────────────────────────────────
# Batch tools (the weekly KB-gap judge on the VPS, eval/golden judges, the
# dataset generator, PDF ingestion) talk to an OpenAI-compatible API with
# their own client. In October 2026 the weekly judge spent 196 DeepSeek
# requests that llm_calls never saw. Every such call goes through
# record_chat_completion: same table, same provider identity, same usage
# rules as the gateway's own calls. tests/test_deepseek_callers_are_recorded.py
# fails on a new caller that does not.
def _provider_label(base_url: object) -> str:
    """llm_calls.provider for an OpenAI-compatible endpoint, by its host.

    api.deepseek.com is "deepseek" — the gateway's own name for that wallet,
    so batch spend counts against the same monthly sum as the app's."""
    try:
        host = (httpx.URL(str(base_url)).host or "").lower()
    except Exception:  # noqa: BLE001 — a label must never break the call
        host = ""
    if host == "deepseek.com" or host.endswith(".deepseek.com"):
        return "deepseek"
    if host == "ollama.com" or host.endswith(".ollama.com"):
        return "ollama_cloud"
    if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost"):
        return "ollama"
    if "azure" in host:
        return "azure"
    return host or "unknown"


def record_chat_completion(client, *, tier: str, provider: str | None = None,
                           route_reason: str | None = None, **create_kwargs):
    """See _record_chat_completion; its llm_calls row names its reservation."""
    with _reservation_scope():
        return _record_chat_completion(client, tier=tier, provider=provider,
                                       route_reason=route_reason, **create_kwargs)


def _record_chat_completion(client, *, tier: str, provider: str | None = None,
                            route_reason: str | None = None, **create_kwargs):
    """client.chat.completions.create(**create_kwargs), recorded in llm_calls.

    Returns the response unchanged and re-raises the client's errors after
    recording them; telemetry itself never raises. A request to DeepSeek's
    wallet is also reserved and settled in the monthly cap's ledger, like a
    gateway call: it needs a bounded max_tokens, and it raises BudgetDenied
    (before any request) when the cap is full or not activated. `tier` names the caller
    (e.g. "kb_gap_judge"); `provider` overrides the host-derived label. Not
    for streams: their usage arrives in the last chunk, which this wrapper
    would not see — stream through the gateway instead.
    """
    if create_kwargs.get("stream"):
        raise ValueError("record_chat_completion does not record streams; use the gateway")
    messages = create_kwargs.get("messages") or []
    prompt = "\n".join(str(m.get("content") or "") for m in messages if isinstance(m, dict))
    model = str(create_kwargs.get("model") or "unknown")
    name = provider or _provider_label(getattr(client, "base_url", None))
    start = time.monotonic()
    charge = None
    try:
        try:
            if _provider_label(getattr(client, "base_url", None)) == "deepseek":
                # DeepSeek's wallet is the capped one: reserve this wire attempt
                # exactly like the gateway does, or the cap never sees it.
                charge = _reserve_wire_budget(str(client.base_url), "deepseek", messages,
                                              create_kwargs.get("max_tokens"), model=model)
                if charge is not None and hasattr(client, "with_options"):
                    # An SDK retry is another paid attempt under one reservation.
                    client = client.with_options(max_retries=0)
            response = client.chat.completions.create(**create_kwargs)
        except Exception as e:
            usage = e.usage if isinstance(e, BudgetDenied) else (None, None)
            _log_call(name, model, int((time.monotonic() - start) * 1000), *usage,
                      streamed=False, ok=False, tier=tier,
                      route_reason=_failure_reason(e) or route_reason, prompt=prompt, exc=e)
            raise
        latency = int((time.monotonic() - start) * 1000)
        received, prompt_tokens, completion_tokens = "", None, None
        try:
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            received = "".join((getattr(getattr(c, "message", None), "content", None) or "")
                               for c in (getattr(response, "choices", None) or []))
            served = getattr(response, "model", None)
            if isinstance(served, str) and served:
                model = served
        except Exception:  # noqa: BLE001 — an odd response shape is estimated, not fatal
            pass
        _settle_wire_budget(charge, prompt_tokens, completion_tokens)
        _log_call(name, model, latency, prompt_tokens, completion_tokens,
                  streamed=False, ok=True, tier=tier, route_reason=route_reason,
                  prompt=prompt, received=received)
        return response
    finally:
        _settle_wire_budget(charge, None, None)  # an unsettled attempt: its own bound


def _failure_reason(exc: BaseException) -> str | None:
    """route_reason for a failed call's llm_calls row."""
    if isinstance(exc, BudgetDenied):
        return "budget_denied" if exc.usage == (0, 0) else "budget_denied_after_attempt"
    if isinstance(exc, LLMDeadlineExceeded):
        return "deadline"
    if isinstance(exc, LLMProviderBusy):
        return "lane_full"
    if isinstance(exc, httpx.TimeoutException):
        return "read_timeout"
    if isinstance(exc, ProviderHTTPError):
        return f"http_{exc.status}"
    if isinstance(exc, ProviderStreamError):
        return "bad_stream"
    if isinstance(exc, LLMCancelled):
        return "cancelled"
    # openai SDK errors, for callers recorded through record_chat_completion.
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return f"http_{status}"
    if "Timeout" in type(exc).__name__:
        return "read_timeout"
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
                    name="deepseek", fallback_model=_fallback_model(),
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
                fallback_model=_fallback_model(),
            )
        except Exception as e:
            logger.warning("cloud safety valve unavailable: %s", e)
            return None

    def _primary_within_budget(self) -> bool:
        """Is the paid primary still under its monthly ceiling?

        Checked per call — never in _default_provider() — because the gateway
        is a module-level singleton built once at startup: a construction-time
        check would be evaluated exactly once and the cap would never bite.

        Both lanes fail closed to paid cloud, while keeping local fallback.
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
        sink_token = _RESERVATION_SINK.set([])

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
                                      tier=tier, route_reason=route_reason,
                                      prompt=prompt, received=text)
                            return result
                        _log_call(cloud.name, cloud.model, latency,
                                  data.get("prompt_eval_count"), data.get("eval_count"),
                                  streamed=False, ok=False, tier=tier, route_reason="empty",
                                  prompt=prompt)
                    except Exception as e:
                        _log_call(cloud.name, cloud.model,
                                  int((time.monotonic() - start) * 1000),
                                  *getattr(e, "usage", (None, None)),
                                  streamed=False, ok=False,
                                  tier=tier, route_reason=_failure_reason(e) or route_reason,
                                  prompt=prompt, exc=e)
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
                        # A paid request that answered nothing is still a row:
                        # the monthly cap is a sum over llm_calls.
                        _log_call(self.provider.name, data.get("model") or self._provider_model(),
                                  latency, data.get("prompt_eval_count"), data.get("eval_count"),
                                  streamed=False, ok=False, route_reason="empty", prompt=prompt)
                        logger.warning("Primary returned empty response on attempt %d/%d", attempt, retries)
                        if attempt < retries:
                            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    result = LLMResult(
                        text=text, model=data.get("model") or self._provider_model(),
                        latency_ms=latency,
                        prompt_tokens=data.get("prompt_eval_count"),
                        completion_tokens=data.get("eval_count"),
                        truncated=data.get("truncated"),
                    )
                    _log_call(self.provider.name, result.model, latency,
                              result.prompt_tokens, result.completion_tokens,
                              streamed=False, ok=True,
                              route_reason=f"truncated:{result.truncated}" if result.truncated else None,
                              prompt=prompt, received=text)
                    if paid_primary:
                        primary_breaker.record(True)
                    return result
                except Exception as e:
                    last_err = e
                    if paid_primary and not isinstance(e, BudgetDenied):
                        primary_breaker.record(False)
                    # Recorded, not silently dropped. The monthly cap is a sum
                    # over this table, and a timeout here is the case where the
                    # provider most likely *did* count the tokens — the request
                    # reached it and the answer did not come back. Counts it did
                    # not report are estimated from the prompt and flagged
                    # (usage_estimated=1): a NULL here was 9 of October's 26
                    # unsummable rows.
                    _log_call(self.provider.name, self._provider_model(),
                              int((time.monotonic() - start) * 1000),
                              *getattr(e, "usage", (None, None)), streamed=False, ok=False,
                              route_reason=_failure_reason(e), prompt=prompt, exc=e)
                    logger.warning("Primary attempt %d/%d failed: %s", attempt, retries, e)
                    # A held, silent or saturated provider is not retried: each
                    # retry was another paid request into the same hold (all of
                    # them running at once), and a read timeout had already
                    # spent 60 s of the budget the fallback needs.
                    if isinstance(e, (BudgetDenied, LLMDeadlineExceeded, LLMProviderBusy,
                                      httpx.TimeoutException)):
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
                                  tier=tier, route_reason=route_reason,
                                  prompt=prompt, received=text)
                        return result
                    _log_call(valve.name, valve.model, latency,
                              data.get("prompt_eval_count"), data.get("eval_count"),
                              streamed=False, ok=False, tier=tier, route_reason="empty",
                              prompt=prompt)
                except Exception as e:
                    _log_call(valve.name, valve.model, int((time.monotonic() - start) * 1000),
                              *getattr(e, "usage", (None, None)),
                              streamed=False, ok=False,
                              tier=tier, route_reason=_failure_reason(e) or route_reason,
                              prompt=prompt, exc=e)
                    logger.warning("cloud safety valve failed: %s", e)

            # The failure of the whole call, as its own event. Not under the
            # provider's name: no request goes with this row (every attempt
            # above wrote its own), and in October 2026 seven such rows were
            # counted as paid DeepSeek calls with unknown usage.
            _log_call("gateway", self._provider_model(), 0, 0, 0,
                      streamed=False, ok=False, tier=tier, route_reason="all_failed")
            raise RuntimeError(f"LLM generation failed after all retries and fallbacks: {last_err}") from last_err
        finally:
            _GENERATE_DEADLINE.reset(budget_token)
            _RESERVATION_SINK.reset(sink_token)

    def _stream_provider(self, provider: LLMProvider, prompt: str,
                         opts: dict, tier: str | None = None,
                         route_reason: str | None = None) -> Iterator[StreamChunk]:
        """_stream_scoped inside its own reservation scope (see _RESERVATION_SINK)."""
        with _reservation_scope():
            yield from self._stream_scoped(provider, prompt, opts, tier, route_reason)

    def _stream_scoped(self, provider: LLMProvider, prompt: str,
                       opts: dict, tier: str | None = None,
                       route_reason: str | None = None) -> Iterator[StreamChunk]:
        """Stream from one provider. Raises on failure (caller decides to fall back)."""
        start = time.monotonic()
        text_parts: list[str] = []
        prompt_tokens = completion_tokens = None
        served = truncated = None
        ok = False
        limits = _CALL_LIMITS.get() or CallLimits()
        try:
            for obj in provider.stream(prompt, options=opts):
                # Local models are read chunk by chunk too: a cut turn stops here.
                if limits.stop and limits.stop():
                    raise LLMCancelled(f"{provider.name}: turn cut")
                delta = obj.get("response", "")
                if delta:
                    text_parts.append(delta)
                    yield StreamChunk(delta=delta, done=False)
                if obj.get("done"):
                    prompt_tokens = obj.get("prompt_eval_count")
                    completion_tokens = obj.get("eval_count")
                    served = obj.get("model")
                    truncated = obj.get("truncated")
                    ok = True
        except GeneratorExit:
            # The consumer closed us mid-answer (SSE client disconnected, see
            # assistant._pump_stream). Record the partial call so llm_calls
            # still shows the spend, then let the close unwind the provider.
            # DeepSeek's usage chunk comes last, so it never arrived: the
            # counts are estimated from what was sent and received.
            _log_call(provider.name, provider.model,
                      int((time.monotonic() - start) * 1000),
                      None, None, streamed=True, ok=False,
                      tier=tier, route_reason="client_disconnected",
                      prompt=prompt, received="".join(text_parts))
            raise
        except Exception as e:
            # Every other end of a stream that did not finish — a cut turn, a
            # deadline, a broken stream, an HTTP refusal — is recorded HERE,
            # where the elapsed time and the text already received are known
            # (stream() used to log these with latency 0 and no tokens).
            _log_call(provider.name, provider.model,
                      int((time.monotonic() - start) * 1000),
                      *getattr(e, "usage", (None, None)), streamed=True, ok=False,
                      tier=tier, route_reason=_failure_reason(e) or route_reason,
                      prompt=prompt, received="".join(text_parts), exc=e)
            raise
        latency = int((time.monotonic() - start) * 1000)
        result = LLMResult(
            text="".join(text_parts).strip(),
            model=served or provider.model,   # the model that really answered
            latency_ms=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            truncated=truncated,
        )
        _log_call(provider.name, result.model, latency,
                  prompt_tokens, completion_tokens, streamed=True, ok=ok,
                  tier=tier, route_reason=f"truncated:{truncated}" if truncated else route_reason,
                  prompt=prompt, received=result.text)
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
               tracker: "StreamTracker | None" = None,
               should_stop: "Callable[[], bool] | None" = None) -> Iterator[StreamChunk]:
        """Streaming generation with pre-flight fallback.

        Uses stream_chain() (local-fast first) for low latency. Falls back
        through each provider only if the previous one fails before emitting
        any tokens (once tokens are flowing we cannot fall back — we raise).
        When routed to the cloud quality tier, the Azure provider is tried
        first and the local chain stays behind it — a cloud pre-flight
        failure is invisible to the SSE consumer.

        The paid primary is held to PRIMARY_FIRST_TOKEN_S for its first token,
        PRIMARY_STALL_S between tokens and PRIMARY_TOTAL_S in all: a request
        DeepSeek is holding is aborted and the next provider gets the
        question, instead of the whole stream waiting out the hold.
        `tracker`, when given, always names the provider currently streaming.
        `should_stop`, when given, is the turn's cut flag: checked on every
        line and before each candidate — a dead turn is never handed to the
        next provider (LLMCancelled is raised instead).
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
            if should_stop is not None and should_stop():
                raise LLMCancelled(f"turn cut before trying {label}")
            tokens_sent = False
            is_primary = provider is self.provider and isinstance(provider, OpenAIChatProvider)
            if tracker is not None:
                tracker.begin(label, is_primary)
            limits = (CallLimits(first_token=PRIMARY_FIRST_TOKEN_S, stall=PRIMARY_STALL_S,
                                 total=PRIMARY_TOTAL_S, stop=should_stop)
                      if is_primary else CallLimits(stop=should_stop))
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
            except LLMCancelled:
                raise   # recorded by _stream_provider
            except Exception as e:
                if is_primary and not isinstance(e, BudgetDenied):
                    primary_breaker.record(False)
                # The failed attempt's row was written by _stream_provider.
                if should_stop is not None and should_stop():
                    raise LLMCancelled(f"turn cut while {label} failed") from e
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
