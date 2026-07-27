"""Primary-provider monthly spend ceiling tests.

The app is free forever, so the paid primary path (DeepSeek) needs its own
ceiling — the safety-valve cap never covered it. Once the ceiling is spent the
gateway must behave exactly as if the provider had failed: fall through to the
local chain, never raise, never bill.

The check has to happen per call, because the gateway is a module-level
singleton built once at startup, and it must fail OPEN on an unreadable
telemetry DB — the opposite of the safety valve, which fails CLOSED.
"""
import asyncio
from dataclasses import dataclass

import pytest

from app.services import ai_gateway


@dataclass
class _FakeLLM:
    deepseek_primary_monthly_token_cap: int = 1000
    deepseek_fallback_enabled: bool = False
    deepseek_fallback_monthly_token_cap: int = 1000
    deepseek_api_key: str = "sk-test"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    cloud_tier_enabled: bool = False
    cloud_tier_timeout: int = 60
    max_retries: int = 1
    temperature: float = 0.3

    def fallback_chain(self) -> list[dict]:
        return [{"name": "local_fast", "url": "http://x", "model": "m", "timeout": 5}]

    def stream_chain(self) -> list[dict]:
        return [{"name": "local_fast", "url": "http://x", "model": "m", "timeout": 5}]


class _FakePrimary:
    """Stands in for OpenAIChatProvider — records whether it was billed."""

    name = "deepseek"
    model = "deepseek-chat"

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = 0

    def generate(self, prompt, *, options):
        self.calls += 1
        return {"response": "من الطبقة المدفوعة", "done": True,
                "prompt_eval_count": 10, "eval_count": 20}

    def stream(self, prompt, *, options):
        self.calls += 1
        yield {"response": "من الطبقة المدفوعة", "done": False}
        yield {"response": "", "done": True,
               "prompt_eval_count": 10, "eval_count": 20}


@pytest.fixture(autouse=True)
def _clean_budget_cache(monkeypatch):
    """The 60s memo is process-global — a leftover entry would leak between
    tests and silently answer the next one."""
    ai_gateway._budget_cache.clear()
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    yield
    ai_gateway._budget_cache.clear()


@pytest.fixture()
def gateway(monkeypatch):
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _FakePrimary)
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM())
    gw = ai_gateway.AIGateway.__new__(ai_gateway.AIGateway)
    gw.provider = _FakePrimary()
    gw.primary_model = gw.model = "deepseek-chat"
    return gw


def _used(monkeypatch, tokens: int) -> None:
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: tokens)


# ── the gate itself ───────────────────────────────────────────────────────
def test_primary_allowed_under_cap(gateway, monkeypatch):
    _used(monkeypatch, 999)
    assert gateway._primary_within_budget() is True


def test_primary_blocked_at_cap(gateway, monkeypatch):
    _used(monkeypatch, 1000)
    assert gateway._primary_within_budget() is False


def test_zero_cap_disables_the_ceiling(gateway, monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(deepseek_primary_monthly_token_cap=0))
    _used(monkeypatch, 10 ** 12)
    assert gateway._primary_within_budget() is True


def test_local_primary_is_never_budget_gated(monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM())
    gw = ai_gateway.AIGateway.__new__(ai_gateway.AIGateway)
    gw.provider = ai_gateway.OllamaProvider("http://x", "qwen2.5:3b", 5)
    _used(monkeypatch, 10 ** 12)
    assert gw._primary_within_budget() is True


def test_budget_total_is_cached(gateway, monkeypatch):
    calls = {"n": 0}

    def _counting(name):
        calls["n"] += 1
        return 0

    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", _counting)
    for _ in range(5):
        assert gateway._primary_within_budget() is True
    assert calls["n"] == 1  # one sqlite aggregate, not five


# ── fail-open vs fail-closed asymmetry ────────────────────────────────────
def test_telemetry_failure_does_not_block_the_primary(gateway, monkeypatch, tmp_path):
    # Real reader against an unreadable path — no stubbing of the sentinel.
    monkeypatch.setattr(ai_gateway, "_TELEMETRY_DB", tmp_path / "nope" / "\0bad.db")
    assert gateway._primary_within_budget() is True


def test_telemetry_failure_still_blocks_the_safety_valve(monkeypatch, tmp_path):
    """Same broken telemetry, opposite answer — the valve is optional spend."""
    monkeypatch.setattr(ai_gateway, "_TELEMETRY_DB", tmp_path / "nope" / "\0bad.db")
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _FakePrimary)
    monkeypatch.setattr(
        ai_gateway, "LLM", _FakeLLM(deepseek_fallback_enabled=True),
    )
    gw = ai_gateway.AIGateway.__new__(ai_gateway.AIGateway)
    gw.provider = object()  # local primary, so the valve is eligible
    assert gw._safety_valve_provider() is None


# ── end to end through generate() / stream() ──────────────────────────────
def test_generate_skips_primary_once_cap_exceeded(gateway, monkeypatch):
    _used(monkeypatch, 5000)

    async def _fake_try_provider(self, prompt, opts, url, model, timeout, label):
        return ai_gateway.LLMResult(text="من السلسلة المحلية", model=model, latency_ms=1)

    monkeypatch.setattr(ai_gateway.AIGateway, "_try_provider", _fake_try_provider)
    result = asyncio.run(gateway.generate("سؤال"))
    assert result.text == "من السلسلة المحلية"
    assert gateway.provider.calls == 0  # never billed


def test_generate_uses_primary_while_under_cap(gateway, monkeypatch):
    _used(monkeypatch, 10)
    result = asyncio.run(gateway.generate("سؤال"))
    assert result.text == "من الطبقة المدفوعة"
    assert gateway.provider.calls == 1


def test_stream_drops_primary_from_candidates_once_capped(gateway, monkeypatch):
    _used(monkeypatch, 5000)

    def _fake_stream(self, provider, prompt, opts, tier=None, route_reason=None):
        yield ai_gateway.StreamChunk(delta=f"من {provider.name}", done=False)
        yield ai_gateway.StreamChunk(
            delta="", done=True,
            result=ai_gateway.LLMResult(text="", model=provider.model, latency_ms=1),
        )

    monkeypatch.setattr(ai_gateway.AIGateway, "_stream_provider", _fake_stream)
    deltas = [c.delta for c in gateway.stream("سؤال") if not c.done]
    assert deltas == ["من ollama"]  # the local chain, not the paid provider
    assert gateway.provider.calls == 0


def test_stream_uses_primary_while_under_cap(gateway, monkeypatch):
    _used(monkeypatch, 10)
    deltas = [c.delta for c in gateway.stream("سؤال") if not c.done]
    assert deltas == ["من الطبقة المدفوعة"]
    assert gateway.provider.calls == 1
