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
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

import requests

from app.config.llm_config import LLM

logger = logging.getLogger(__name__)

_TELEMETRY_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


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


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry (non-fatal)
# ─────────────────────────────────────────────────────────────────────────────
def _log_call(provider: str, model: str, latency_ms: int,
              prompt_tokens: int | None, completion_tokens: int | None,
              streamed: bool, ok: bool,
              tier: str | None = None, route_reason: str | None = None) -> None:
    try:
        _TELEMETRY_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_TELEMETRY_DB)
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


# ─────────────────────────────────────────────────────────────────────────────
# Gateway
# ─────────────────────────────────────────────────────────────────────────────
class AIGateway:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or OllamaProvider(
            base_url=LLM.base_url, model=LLM.primary_model, timeout=LLM.request_timeout
        )
        self.primary_model = self._provider_model()
        self.model = self.primary_model

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
            data = await asyncio.to_thread(provider.generate, prompt, options=opts)
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

    async def generate(self, prompt: str, *, options: dict | None = None,
                       max_retries: int | None = None,
                       tier: str = "local_fast",
                       route_reason: str | None = None) -> LLMResult:
        """Blocking generation with primary + full fallback chain. Raises on total failure."""
        retries = max_retries if max_retries is not None else LLM.max_retries
        opts = self._options(options)
        last_err: Exception | None = None

        # Cloud quality tier first when routed there; local chain remains
        # the fallback so a cloud failure is invisible to the caller.
        if tier == "cloud_quality":
            cloud = self._cloud_provider()
            if cloud is not None:
                start = time.monotonic()
                try:
                    data = await asyncio.to_thread(cloud.generate, prompt, options=opts)
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

        # 1. Try primary model with retries
        for attempt in range(1, retries + 1):
            start = time.monotonic()
            try:
                data = await asyncio.to_thread(self.provider.generate, prompt, options=opts)
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
                return result
            except Exception as e:
                last_err = e
                logger.warning("Primary attempt %d/%d failed: %s", attempt, retries, e)
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        # 2. Try fallback chain
        for fb in LLM.fallback_chain():
            logger.warning("⚠️ trying fallback: %s (%s@%s)", fb["name"], fb["model"], fb["url"])
            result = await self._try_provider(
                prompt, opts, fb["url"], fb["model"], fb["timeout"], fb["name"]
            )
            if result:
                return result

        _log_call(self.provider.name, self._provider_model(), 0, None, None,
                  streamed=False, ok=False)
        raise RuntimeError(f"LLM generation failed after all retries and fallbacks: {last_err}") from last_err

    def _stream_provider(self, provider: LLMProvider, prompt: str,
                         opts: dict, tier: str | None = None,
                         route_reason: str | None = None) -> Iterator[StreamChunk]:
        """Stream from one provider. Raises on failure (caller decides to fall back)."""
        start = time.monotonic()
        text_parts: list[str] = []
        prompt_tokens = completion_tokens = None
        ok = False
        for obj in provider.stream(prompt, options=opts):
            delta = obj.get("response", "")
            if delta:
                text_parts.append(delta)
                yield StreamChunk(delta=delta, done=False)
            if obj.get("done"):
                prompt_tokens = obj.get("prompt_eval_count")
                completion_tokens = obj.get("eval_count")
                ok = True
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

    def stream(self, prompt: str, *, options: dict | None = None,
               tier: str = "local_fast",
               route_reason: str | None = None) -> Iterator[StreamChunk]:
        """Streaming generation with pre-flight fallback.

        Uses stream_chain() (local-fast first) for low latency. Falls back
        through each provider only if the previous one fails before emitting
        any tokens (once tokens are flowing we cannot fall back — we raise).
        When routed to the cloud quality tier, the Azure provider is tried
        first and the local chain stays behind it — a cloud pre-flight
        failure is invisible to the SSE consumer.
        """
        opts = self._options(options)

        candidates: list[tuple[str, LLMProvider]] = [
            (fb["name"], OllamaProvider(fb["url"], fb["model"], fb["timeout"]))
            for fb in LLM.stream_chain()
        ]
        if tier == "cloud_quality":
            cloud = self._cloud_provider()
            if cloud is not None:
                candidates.insert(0, ("cloud_quality", cloud))

        for label, provider in candidates:
            tokens_sent = False
            try:
                for chunk in self._stream_provider(
                    provider, prompt, opts, tier=tier, route_reason=route_reason
                ):
                    if not chunk.done:
                        tokens_sent = True
                    yield chunk
                return  # success
            except Exception as e:
                _log_call(provider.name, provider.model, 0, None, None,
                          streamed=True, ok=False,
                          tier=tier, route_reason=route_reason)
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
