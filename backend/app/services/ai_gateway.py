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


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry (non-fatal)
# ─────────────────────────────────────────────────────────────────────────────
def _log_call(provider: str, model: str, latency_ms: int,
              prompt_tokens: int | None, completion_tokens: int | None,
              streamed: bool, ok: bool) -> None:
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
        conn.execute(
            "INSERT INTO llm_calls (provider,model,latency_ms,prompt_tokens,"
            "completion_tokens,streamed,ok) VALUES (?,?,?,?,?,?,?)",
            (provider, model, latency_ms, prompt_tokens, completion_tokens,
             int(streamed), int(ok)),
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
            base_url=LLM.base_url, model=LLM.model, timeout=LLM.request_timeout
        )

    def _options(self, overrides: dict | None) -> dict:
        opts = {"temperature": LLM.temperature}
        if overrides:
            opts.update(overrides)
        return opts

    async def generate(self, prompt: str, *, options: dict | None = None,
                       max_retries: int | None = None) -> LLMResult:
        """Blocking generation with exponential backoff. Raises on total failure."""
        retries = max_retries if max_retries is not None else LLM.max_retries
        opts = self._options(options)
        last_err: Exception | None = None

        for attempt in range(1, retries + 1):
            start = time.monotonic()
            try:
                data = await asyncio.to_thread(self.provider.generate, prompt, options=opts)
                latency = int((time.monotonic() - start) * 1000)
                result = LLMResult(
                    text=(data.get("response") or "").strip(),
                    model=self.provider.model,
                    latency_ms=latency,
                    prompt_tokens=data.get("prompt_eval_count"),
                    completion_tokens=data.get("eval_count"),
                )
                _log_call(self.provider.name, result.model, latency,
                          result.prompt_tokens, result.completion_tokens,
                          streamed=False, ok=True)
                return result
            except Exception as e:
                last_err = e
                logger.warning("Gateway attempt %d/%d failed: %s", attempt, retries, e)
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))  # 0.5s, 1s, 2s...

        _log_call(self.provider.name, self.provider.model, 0, None, None,
                  streamed=False, ok=False)
        raise RuntimeError(f"LLM generation failed after {retries} attempts: {last_err}") from last_err

    def stream(self, prompt: str, *, options: dict | None = None) -> Iterator[StreamChunk]:
        """Streaming generation. Yields StreamChunk(delta=...) then a final
        StreamChunk(done=True, result=LLMResult). No retry (can't un-send tokens)."""
        opts = self._options(options)
        start = time.monotonic()
        text_parts: list[str] = []
        prompt_tokens = completion_tokens = None
        ok = False
        try:
            for obj in self.provider.stream(prompt, options=opts):
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
                model=self.provider.model,
                latency_ms=latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            _log_call(self.provider.name, result.model, latency,
                      prompt_tokens, completion_tokens, streamed=True, ok=ok)
            yield StreamChunk(delta="", done=True, result=result)
        except Exception as e:
            _log_call(self.provider.name, self.provider.model, 0, None, None,
                      streamed=True, ok=False)
            logger.warning("Gateway stream failed: %s", e)
            raise


# Singleton accessor
_gateway: AIGateway | None = None


def get_gateway() -> AIGateway:
    global _gateway
    if _gateway is None:
        _gateway = AIGateway()
    return _gateway
