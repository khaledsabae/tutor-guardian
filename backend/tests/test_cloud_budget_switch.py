"""CLOUD_BUDGET_ENFORCE: the branch is safe to deploy before any bootstrap.

Off (the default) is production's behaviour before this branch: no wire
reservation, no denial, the soft monthly ceiling over llm_calls failing OPEN on
unreadable telemetry, telemetry still recorded, batch tools unreserved. On is
the full fail-closed reservation design (test_cloud_budget_reservations).
"""
import asyncio
import dataclasses
import json
import sqlite3
import types

import httpx
import pytest

from app.config import llm_config
from app.services import ai_gateway as gw
from app.services import cloud_budget as cb


def _sse():
    obj = {"model": "deepseek-chat", "choices": [{"delta": {"content": "cloud answer"}, "finish_reason": "stop"}],
           "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    return ("data: " + json.dumps(obj) + "\n\ndata: [DONE]\n\n").encode()


@pytest.fixture
def prod_like(monkeypatch, tmp_path):
    """Production's config today: deepseek-chat, default 100M cap, no ledger."""
    db = tmp_path / "sessions.db"
    monkeypatch.setattr(gw, "_TELEMETRY_DB", db)
    monkeypatch.setattr(gw, "_telemetry_schema_ready", False)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        llm_config.LLM, primary_provider="deepseek", deepseek_model="deepseek-chat",
        deepseek_primary_monthly_token_cap=100_000_000, deepseek_fallback_enabled=False,
        cloud_tier_enabled=False, deepseek_billing_profile_aliases=(), cloud_budget_enforce=False))
    gw._budget_cache.clear()
    gw.primary_breaker.reset()
    yield db
    gw._budget_cache.clear()
    gw.primary_breaker.reset()


def _gateway(monkeypatch, calls):
    p = gw.OpenAIChatProvider("https://api.deepseek.com", "test-key", "deepseek-chat", 3, name="deepseek",
                              http_client=httpx.Client(transport=httpx.MockTransport(
                                  lambda r: calls.append(r) or httpx.Response(
                                      200, headers={"content-type": "text/event-stream"}, content=_sse()))))
    gateway = gw.AIGateway.__new__(gw.AIGateway)
    gateway.provider = p
    gateway.primary_model = gateway.model = p.model

    async def local(self, *args, **kwargs):
        return gw.LLMResult(text="local answer", model="local", latency_ms=1)

    monkeypatch.setattr(gw.AIGateway, "_try_provider", local)
    return gateway


def _tables(db):
    if not db.exists():
        return set()
    with sqlite3.connect(db) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_switch_defaults_off(monkeypatch):
    monkeypatch.delenv("CLOUD_BUDGET_ENFORCE", raising=False)
    assert llm_config.LLMConfig().cloud_budget_enforce is False


@pytest.mark.parametrize("raw,on", [("1", True), ("true", True), (" YES ", True), ("on", True),
                                    ("0", False), ("false", False), ("", False), ("no", False),
                                    ("Off", False)])
def test_switch_parses_explicit_values(monkeypatch, caplog, raw, on):
    monkeypatch.setenv("CLOUD_BUDGET_ENFORCE", raw)
    with caplog.at_level("WARNING", logger="app.config.llm_config"):
        assert llm_config.LLMConfig().cloud_budget_enforce is on
    assert "CLOUD_BUDGET_ENFORCE" not in caplog.text


@pytest.mark.parametrize("raw", ["ture", "enforce", "2", "y"])
def test_unknown_switch_value_is_enforced_loudly_never_silently_off(monkeypatch, caplog, raw):
    # A typo means the operator meant to turn it on: the safe reading for
    # spend is ON (cloud fails closed, local answers), and it is logged.
    monkeypatch.setenv("CLOUD_BUDGET_ENFORCE", raw)
    with caplog.at_level("WARNING", logger="app.config.llm_config"):
        assert llm_config.LLMConfig().cloud_budget_enforce is True
    assert "CLOUD_BUDGET_ENFORCE" in caplog.text and raw in caplog.text


def test_malformed_alias_setting_is_logged_and_maps_nothing(monkeypatch, caplog):
    monkeypatch.setenv("DEEPSEEK_BILLING_PROFILE_ALIASES", "deepseek-chat:deepseek-flash")
    with caplog.at_level("WARNING", logger="app.config.llm_config"):
        assert llm_config.LLMConfig().deepseek_billing_profile_aliases == ()
    assert "DEEPSEEK_BILLING_PROFILE_ALIASES" in caplog.text


def test_default_model_is_a_documented_id():
    # Khaled moved production off deepseek-chat on 2026-10-08
    # (tests/test_deepseek_documented_model.py covers the legacy alias).
    import inspect
    assert 'os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")' in inspect.getsource(llm_config)
    assert '"deepseek-chat")' not in inspect.getsource(llm_config)
