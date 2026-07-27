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


class OpenAIChatProvider:
    """Generic OpenAI-compatible chat provider (DeepSeek / GLM / OpenRouter…).

    Unlike OpenAICompatProvider (Azure-specific), this targets a plain
    OpenAI-style base_url (e.g. https://api.deepseek.com). Emits the same dict
    shape as Ollama so the gateway plumbing is unchanged. Used as the PRIMARY
    provider when LLM_PRIMARY_PROVIDER=deepseek, with the local Ollama chain
    kept behind it as automatic fallback.
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: int, name: str = "deepseek") -> None:
        from openai import OpenAI  # lazy import — optional dependency

        self.name = name
        self.model = model
        self.timeout = timeout
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def generate(self, prompt: str, *, options: dict) -> dict:
        r = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=options.get("temperature", 0.3),
            max_tokens=options.get("num_predict", 1024),
        )
        text = r.choices[0].message.content or ""
        text = _ThinkFilter().feed(text)
        usage = getattr(r, "usage", None)
        return {
            "response": text, "done": True,
            "prompt_eval_count": getattr(usage, "prompt_tokens", None),
            "eval_count": getattr(usage, "completion_tokens", None),
        }

    def stream(self, prompt: str, *, options: dict) -> Iterator[dict]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=options.get("temperature", 0.3),
            max_tokens=options.get("num_predict", 1024),
            stream=True,
        )
        flt = _ThinkFilter()
        prompt_tokens = completion_tokens = None
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
        """Soft monthly spend ceiling on the PAID primary provider.

        Checked per call — never in _default_provider() — because the gateway
        is a module-level singleton built once at startup: a construction-time
        check would be evaluated exactly once and the cap would never bite.

        The asymmetry with the safety valve is deliberate. _monthly_tokens_used
        fails CLOSED so the *optional* valve never spends against an unknown
        budget; that is right for an extra we can simply do without. The
        primary path is the app's main way of answering at all, so an
        unreadable telemetry DB must NOT silence it — here we fail OPEN. Worst
        case we overspend for as long as telemetry stays broken; the
        alternative is every user getting nothing.
        """
        if not isinstance(self.provider, OpenAIChatProvider):
            return True  # local primary — nothing is being billed
        cap = LLM.deepseek_primary_monthly_token_cap
        if cap <= 0:
            return True  # 0 disables the ceiling
        used = _monthly_tokens_used_cached(self.provider.name)
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

        # 1. Try primary model with retries — unless the paid primary has burnt
        #    its monthly ceiling, in which case we skip the loop outright
        #    (range(1, 1) is empty) and drop into the local fallback chain
        #    below, exactly as if the provider had failed.
        if not self._primary_within_budget():
            retries = 0
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

        # 3. Cloud safety valve — only when the whole local chain is down.
        valve = self._safety_valve_provider()
        if valve is not None:
            logger.warning("⚠️ local chain exhausted — trying cloud safety valve (%s)", valve.model)
            start = time.monotonic()
            try:
                data = await asyncio.to_thread(valve.generate, prompt, options=opts)
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
        # Primary OpenAI-compatible provider (DeepSeek) streams first; the
        # local Ollama chain above stays behind it as automatic fallback.
        # Dropped from the candidate list once the monthly ceiling is spent.
        if isinstance(self.provider, OpenAIChatProvider) and self._primary_within_budget():
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
