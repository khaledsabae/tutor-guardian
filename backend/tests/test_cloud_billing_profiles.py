"""Documented profiles and explicit opt-out, without paid transports."""
import dataclasses
import sqlite3
import pytest
from app.services import ai_gateway as gw
from app.services import cloud_budget as cb


def test_documented_context_reserves_entire_window_not_utf8_estimate():
    for text in ['tiny', 'س' * 20000]:
        assert cb.upper_token_bound([{'role': 'user', 'content': text}], 100,
            endpoint='https://api.deepseek.com/v1', model='deepseek-flash') == 1048576


@pytest.mark.parametrize('endpoint,model', [
    ('https://api.deepseek.com', 'unknown'),
    ('https://compatible.example', 'deepseek-flash'),
    ('http://api.deepseek.com', 'deepseek-flash'),
    ('https://api.deepseek.com/other', 'deepseek-flash'),
    ('https://account.openai.azure.com', 'DeepSeek-V4-Flash'),
    ('https://api.deepseek.com', 'deepseek-chat'),
])
def test_unknown_contract_is_denied(endpoint, model):
    with pytest.raises(cb.BudgetDenied, match='profile'):
        cb.upper_token_bound([], 100, endpoint=endpoint, model=model)


def test_known_profile_requires_actual_enforced_output_limit():
    for value in [0, -1, True, None, 393217]:
        with pytest.raises(cb.BudgetDenied):
            cb.upper_token_bound([], value, endpoint='https://api.deepseek.com', model='deepseek-v4-pro')


def config(monkeypatch, tmp_path, **kw):
    path = tmp_path / 'ledger.db'
    monkeypatch.setattr(gw, '_TELEMETRY_DB', path)
    monkeypatch.setattr(gw, 'LLM', dataclasses.replace(gw.LLM, **kw))
    return path


def test_tiny_cap_cannot_admit_even_a_small_known_request(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path, primary_provider='deepseek', deepseek_primary_monthly_token_cap=1000)
    with pytest.raises(cb.BudgetDenied):
        gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek', [], 100, model='deepseek-flash')


def test_zero_primary_cap_is_explicit_unlimited_optout(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path, primary_provider='deepseek', deepseek_primary_monthly_token_cap=0)
    assert gw._reserve_wire_budget('https://unverified.example', 'deepseek', [], 100, model='unverified') is None
    assert not gw._TELEMETRY_DB.exists()


def test_fallback_zero_remains_disabled_not_unlimited(monkeypatch, tmp_path):
    config(monkeypatch, tmp_path, primary_provider='ollama', deepseek_fallback_monthly_token_cap=0)
    with pytest.raises(cb.BudgetDenied):
        gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek_fallback', [], 100, model='deepseek-flash')


def test_same_origin_v1_aliases_share_one_reserved_wallet(monkeypatch, tmp_path):
    path = config(monkeypatch, tmp_path, primary_provider='deepseek', deepseek_primary_monthly_token_cap=1048576)
    gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek', [], 100, model='deepseek-flash')
    with pytest.raises(cb.BudgetDenied):
        gw._reserve_wire_budget('https://api.deepseek.com:443/v1', 'deepseek_aux', [], 100, model='deepseek-v4-pro')
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM cloud_budget_attempts').fetchone()[0] == 1
