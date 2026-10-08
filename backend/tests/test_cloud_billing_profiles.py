"""Documented profiles and explicit opt-out, without paid transports."""
import dataclasses
import sqlite3
import pytest
from app.services import ai_gateway as gw
from app.services import cloud_budget as cb
from tests.budget_test_helpers import activate


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
    monkeypatch.setattr(gw, 'LLM', dataclasses.replace(gw.LLM, **{'cloud_budget_enforce': True, **kw}))
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
    activate(cb.CloudBudget(path), wallets=('cloud:https://api.deepseek.com:443',))
    gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek', [], 100, model='deepseek-flash')
    with pytest.raises(cb.BudgetDenied):
        gw._reserve_wire_budget('https://api.deepseek.com:443/v1', 'deepseek_aux', [], 100, model='deepseek-v4-pro')
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM cloud_budget_attempts').fetchone()[0] == 1


# ── deepseek-chat: an explicit, operator-attested profile alias ────────────
# DeepSeek's docs fetched 2026-10-08 no longer document deepseek-chat (model
# enum, pricing page and the 2026-09-10 compatibility list name only
# deepseek-flash / deepseek-v4-pro / deepseek-v4-flash*). Production still
# sends it, so the mapping is configuration, never a built-in profile.
CHAT = [{'role': 'user', 'content': 'سؤال'}]


def test_deepseek_chat_is_not_a_builtin_profile():
    assert ('https://api.deepseek.com:443', 'deepseek-chat') not in cb._BILLING_PROFILES
    with pytest.raises(cb.BudgetDenied, match='profile'):
        cb.upper_token_bound(CHAT, 100, endpoint='https://api.deepseek.com', model='deepseek-chat',
                             profile_aliases={})


def test_explicit_alias_bills_under_the_documented_target_profile():
    aliases = {'deepseek-chat': 'deepseek-flash'}
    assert cb.upper_token_bound(CHAT, 100, endpoint='https://api.deepseek.com', model='deepseek-chat',
                                profile_aliases=aliases) == 1048576
    # The target's documented output ceiling still binds the aliased name.
    with pytest.raises(cb.BudgetDenied):
        cb.upper_token_bound(CHAT, 393217, endpoint='https://api.deepseek.com', model='deepseek-chat',
                             profile_aliases=aliases)


@pytest.mark.parametrize('endpoint,model,aliases', [
    # target must itself be a verified profile on the same origin
    ('https://api.deepseek.com', 'deepseek-chat', {'deepseek-chat': 'deepseek-reasoner'}),
    ('https://api.deepseek.com', 'deepseek-chat', {'deepseek-chat': 'deepseek-chat'}),
    # an alias never moves a request to another origin's wallet
    ('https://compatible.example', 'deepseek-chat', {'deepseek-chat': 'deepseek-flash'}),
    # an alias for a different name does not leak onto this one
    ('https://api.deepseek.com', 'deepseek-reasoner', {'deepseek-chat': 'deepseek-flash'}),
])
def test_alias_cannot_widen_beyond_a_verified_profile(endpoint, model, aliases):
    with pytest.raises(cb.BudgetDenied, match='profile'):
        cb.upper_token_bound(CHAT, 100, endpoint=endpoint, model=model, profile_aliases=aliases)


def test_alias_cannot_remap_a_documented_model():
    # deepseek-v4-pro is documented with its own profile; config cannot
    # re-point it (a typo there must not silently change the bound).
    with pytest.raises(cb.BudgetDenied, match='alias'):
        cb.upper_token_bound(CHAT, 100, endpoint='https://api.deepseek.com', model='deepseek-v4-pro',
                             profile_aliases={'deepseek-v4-pro': 'deepseek-flash'})


@pytest.mark.parametrize('raw,expected', [
    ('', ()),
    ('deepseek-chat=deepseek-flash', (('deepseek-chat', 'deepseek-flash'),)),
    (' deepseek-chat = deepseek-flash , x=y ', (('deepseek-chat', 'deepseek-flash'), ('x', 'y'))),
])
def test_alias_config_parses(raw, expected):
    from app.config.llm_config import parse_billing_profile_aliases
    assert parse_billing_profile_aliases(raw) == expected


@pytest.mark.parametrize('raw', ['deepseek-chat', 'deepseek-chat=', '=deepseek-flash',
                                 'a=b=c', 'deepseek-chat=deepseek-flash,deepseek-chat=deepseek-v4-pro'])
def test_malformed_alias_config_maps_nothing(raw):
    # Fail closed: one malformed entry voids the whole setting, so a typo can
    # only deny cloud (visible, local fallback), never mis-attribute a bound.
    from app.config.llm_config import parse_billing_profile_aliases
    assert parse_billing_profile_aliases(raw) == ()


def test_default_config_maps_nothing(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_BILLING_PROFILE_ALIASES', raising=False)
    from app.config import llm_config
    assert llm_config.LLMConfig().deepseek_billing_profile_aliases == ()


def test_gateway_admits_deepseek_chat_only_with_the_configured_alias(monkeypatch, tmp_path):
    path = config(monkeypatch, tmp_path, primary_provider='deepseek',
                  deepseek_primary_monthly_token_cap=10 * 1048576)
    activate(cb.CloudBudget(path), wallets=('cloud:https://api.deepseek.com:443',))
    with pytest.raises(cb.BudgetDenied, match='profile'):
        gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek', CHAT, 100, model='deepseek-chat')
    monkeypatch.setattr(gw, 'LLM', dataclasses.replace(
        gw.LLM, deepseek_billing_profile_aliases=(('deepseek-chat', 'deepseek-flash'),)))
    assert gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek', CHAT, 100,
                                   model='deepseek-chat') is not None
