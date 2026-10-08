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


@pytest.mark.parametrize("raw,on", [("1", True), ("true", True), ("YES", True),
                                    ("0", False), ("false", False), ("", False), ("enforce", False)])
def test_switch_parses_only_explicit_yes(monkeypatch, raw, on):
    monkeypatch.setenv("CLOUD_BUDGET_ENFORCE", raw)
    assert llm_config.LLMConfig().cloud_budget_enforce is on


def test_off_without_ledger_primary_answers_from_cloud_as_on_main(prod_like, monkeypatch):
    calls = []
    gateway = _gateway(monkeypatch, calls)
    assert asyncio.run(gateway.generate("سؤال")).text == "cloud answer"
    assert len(calls) == 1
    assert not any(t.startswith("cloud_budget") for t in _tables(prod_like))
    assert not cb.CloudBudget(prod_like).anchor_path.exists()
    with sqlite3.connect(prod_like) as conn:   # telemetry still recorded
        assert conn.execute("SELECT provider, prompt_tokens, completion_tokens FROM llm_calls "
                            "WHERE ok=1").fetchall() == [("deepseek", 5, 2)]


def test_on_without_bootstrap_primary_is_denied_and_local_answers(prod_like, monkeypatch):
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(gw.LLM, cloud_budget_enforce=True))
    calls = []
    gateway = _gateway(monkeypatch, calls)
    assert asyncio.run(gateway.generate("سؤال")).text == "local answer"
    assert calls == []


def test_off_unreadable_telemetry_fails_open_as_on_main(prod_like, monkeypatch, tmp_path):
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "nope" / "\0bad.db")
    assert gw.primary_budget_available("deepseek") is True
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(gw.LLM, cloud_budget_enforce=True))
    gw._budget_cache.clear()
    assert gw.primary_budget_available("deepseek") is False


def test_off_batch_tools_need_no_reservation_or_max_tokens(prod_like):
    calls = []
    msg = types.SimpleNamespace(content="تم")
    resp = types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)],
                                 usage=types.SimpleNamespace(prompt_tokens=3, completion_tokens=1))
    client = types.SimpleNamespace(base_url=httpx.URL("https://api.deepseek.com/"),
                                   chat=types.SimpleNamespace(completions=types.SimpleNamespace(
                                       create=lambda **kw: calls.append(kw) or resp)))
    assert gw.record_chat_completion(client, tier="kb_gap_judge", model="deepseek-chat",
                                     messages=[{"role": "user", "content": "x"}]) is resp
    assert len(calls) == 1
    assert not any(t.startswith("cloud_budget") for t in _tables(prod_like))


def test_on_batch_tools_are_denied_without_bootstrap(prod_like, monkeypatch):
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        gw.LLM, cloud_budget_enforce=True, deepseek_billing_profile_aliases=(("deepseek-chat", "deepseek-flash"),)))
    calls = []
    client = types.SimpleNamespace(base_url=httpx.URL("https://api.deepseek.com/"),
                                   chat=types.SimpleNamespace(completions=types.SimpleNamespace(
                                       create=lambda **kw: calls.append(kw))))
    with pytest.raises(cb.BudgetDenied):
        gw.record_chat_completion(client, tier="kb_gap_judge", model="deepseek-chat",
                                  messages=[{"role": "user", "content": "x"}], max_tokens=16)
    assert calls == []
