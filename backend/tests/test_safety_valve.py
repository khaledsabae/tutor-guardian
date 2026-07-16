"""Cloud safety-valve tests — the hard-capped DeepSeek last-resort fallback.

The valve must stay SHUT unless all of: flag on, key present, primary is not
already DeepSeek, and the monthly token budget has headroom. Budget reads
fail closed.
"""
from dataclasses import dataclass

import pytest

from app.services import ai_gateway


@dataclass
class _FakeLLM:
    deepseek_fallback_enabled: bool = True
    deepseek_api_key: str = "sk-test"
    deepseek_fallback_monthly_token_cap: int = 1000
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    cloud_tier_timeout: int = 60


class _FakeProvider:
    name = "deepseek_fallback"
    model = "deepseek-chat"

    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture()
def gateway(monkeypatch):
    gw = ai_gateway.AIGateway.__new__(ai_gateway.AIGateway)
    gw.provider = object()  # anything that is not OpenAIChatProvider
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _FakeProvider)
    return gw


def test_valve_shut_when_flag_off(gateway, monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(deepseek_fallback_enabled=False))
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 0)
    assert gateway._safety_valve_provider() is None


def test_valve_shut_without_key(gateway, monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(deepseek_api_key=""))
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 0)
    assert gateway._safety_valve_provider() is None


def test_valve_shut_when_budget_exhausted(gateway, monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(deepseek_fallback_monthly_token_cap=1000))
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 1000)
    assert gateway._safety_valve_provider() is None


def test_valve_shut_when_primary_is_already_deepseek(monkeypatch):
    gw = ai_gateway.AIGateway.__new__(ai_gateway.AIGateway)
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _FakeProvider)
    gw.provider = _FakeProvider()
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM())
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 0)
    assert gw._safety_valve_provider() is None


def test_valve_opens_with_headroom(gateway, monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(deepseek_fallback_monthly_token_cap=1000))
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 999)
    valve = gateway._safety_valve_provider()
    assert valve is not None
    assert valve.kwargs["name"] == "deepseek_fallback"
    assert valve.kwargs["model"] == "deepseek-chat"


def test_budget_reader_fails_closed(monkeypatch, tmp_path):
    # Point telemetry at an unreadable path — the reader must return a huge
    # number so any cap comparison refuses to spend.
    monkeypatch.setattr(ai_gateway, "_TELEMETRY_DB", tmp_path / "nope" / "\0bad.db")
    assert ai_gateway._monthly_tokens_used("deepseek_fallback") >= 1 << 62


def test_budget_reader_sums_current_month_only(monkeypatch, tmp_path):
    import sqlite3

    db = tmp_path / "telemetry.db"
    monkeypatch.setattr(ai_gateway, "_TELEMETRY_DB", db)
    monkeypatch.setattr(ai_gateway, "_telemetry_schema_ready", False)
    conn = sqlite3.connect(db)
    ai_gateway._ensure_telemetry_schema(conn)
    conn.execute(
        "INSERT INTO llm_calls (ts, provider, prompt_tokens, completion_tokens) "
        "VALUES (strftime('%Y-%m-05 10:00:00','now'), 'deepseek_fallback', 100, 50)"
    )
    conn.execute(  # previous month — must NOT count
        "INSERT INTO llm_calls (ts, provider, prompt_tokens, completion_tokens) "
        "VALUES (datetime('now', 'start of month', '-1 day'), 'deepseek_fallback', 900, 900)"
    )
    conn.execute(  # other provider — must NOT count
        "INSERT INTO llm_calls (ts, provider, prompt_tokens, completion_tokens) "
        "VALUES (strftime('%Y-%m-05 10:00:00','now'), 'ollama', 700, 700)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(ai_gateway, "_telemetry_schema_ready", False)
    assert ai_gateway._monthly_tokens_used("deepseek_fallback") == 150
