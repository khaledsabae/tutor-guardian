"""DeepSeek's documented model IDs, the legacy-name alias, and a USD-derived cap.

Ground truth (fetched 2026-10-08, URLs + SHA-256 in
docs/cloud-budget-reservations.md, "Documented model and the US$ cap"):
api-docs.deepseek.com/quick_start/pricing names only deepseek-flash and
deepseek-v4-pro; deepseek-chat was announced for discontinuation on
2026-07-24 and was the non-thinking mode of deepseek-v4-flash until then.
"""
import importlib.util
import sys
import types
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import httpx
import pytest

from app.config import llm_config
from app.services import ai_gateway as gw
from app.services import cloud_budget as cb

ROOT = Path(__file__).resolve().parents[2]
DS = "https://api.deepseek.com"
CONFIG_ENV = ("DEEPSEEK_MODEL", "DEEPSEEK_MODEL_FALLBACK", "DEEPSEEK_BASE_URL",
              "DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP", "DEEPSEEK_PRIMARY_MONTHLY_USD_CAP")


def fresh_config(monkeypatch, **env):
    """A private copy of llm_config read under `env` (the module's defaults
    are evaluated at import, so the shared singleton cannot be re-read)."""
    for key in CONFIG_ENV:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location(
        "llm_config_probe", ROOT / "backend/app/config/llm_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LLM


# ── 1. documented default, legacy names aliased on DeepSeek's own host ─────

def test_default_model_is_a_documented_id(monkeypatch):
    cfg = fresh_config(monkeypatch)
    assert cfg.deepseek_model == "deepseek-flash"
    assert cfg.deepseek_model in llm_config.DOCUMENTED_DEEPSEEK_MODELS


@pytest.mark.parametrize("legacy", ["deepseek-chat", "deepseek-v4-flash", " DeepSeek-Chat "])
def test_legacy_name_resolves_to_documented_flash_on_deepseek(legacy):
    assert llm_config.resolve_deepseek_model(legacy, DS) == "deepseek-flash"
    assert llm_config.resolve_deepseek_model(legacy, DS + "/v1") == "deepseek-flash"


@pytest.mark.parametrize("name", ["deepseek-flash", "deepseek-v4-pro"])
def test_documented_names_are_left_alone(name):
    assert llm_config.resolve_deepseek_model(name, DS) == name


def test_reasoner_is_not_aliased():
    # deepseek-reasoner was the THINKING mode; this assistant never thinks, so
    # it is not silently turned into something else — it stays unprofiled.
    assert llm_config.resolve_deepseek_model("deepseek-reasoner", DS) == "deepseek-reasoner"


@pytest.mark.parametrize("host", ["https://openrouter.ai/api/v1", "https://api.z.ai",
                                  "http://api.deepseek.com"])
def test_alias_never_applies_to_another_host(host):
    # On a compatible host "deepseek-chat" is that host's name, not DeepSeek's.
    assert llm_config.resolve_deepseek_model("deepseek-chat", host) == "deepseek-chat"


def test_production_env_with_legacy_name_sends_documented_model(monkeypatch):
    cfg = fresh_config(monkeypatch, DEEPSEEK_MODEL="deepseek-chat")
    assert cfg.deepseek_model == "deepseek-flash"
    assert cfg.deepseek_model_fallback == "deepseek-flash"


def test_resolved_model_reserves_without_any_billing_alias():
    # No DEEPSEEK_BILLING_PROFILE_ALIASES needed once the wire carries the
    # documented name.
    model = llm_config.resolve_deepseek_model("deepseek-chat", DS)
    assert cb.upper_token_bound([], 1024, endpoint=DS, model=model, profile_aliases={}) == 1048576


# ── 2. price table (peak = pessimistic; off-peak is half) ──────────────────

def test_price_table_matches_the_documented_peak_prices():
    flash = cb.DEEPSEEK_PRICES_USD_PER_M[("https://api.deepseek.com:443", "deepseek-flash")]
    pro = cb.DEEPSEEK_PRICES_USD_PER_M[("https://api.deepseek.com:443", "deepseek-v4-pro")]
    assert (flash.input_cache_hit, flash.input_cache_miss, flash.output) == (
        Decimal("0.006"), Decimal("0.30"), Decimal("1.20"))
    assert (pro.input_cache_hit, pro.input_cache_miss, pro.output) == (
        Decimal("0.044"), Decimal("1.32"), Decimal("3.96"))
    # Every billed model has a price, and every priced model a billing profile.
    assert set(cb.DEEPSEEK_PRICES_USD_PER_M) == set(cb._BILLING_PROFILES)


# ── 3. USD → token cap ─────────────────────────────────────────────────────

@pytest.mark.parametrize("models,expected", [
    (["deepseek-flash"], 25_000_000),            # 30 / 1.20 per 1M
    (["deepseek-v4-pro"], 7_575_757),            # floor(30 / 3.96 per 1M)
    (["deepseek-flash", "deepseek-v4-pro"], 7_575_757),  # the dearest model binds
])
def test_thirty_dollars_becomes_a_token_cap(models, expected):
    assert cb.monthly_token_cap_for_usd(Decimal("30"), models, endpoint=DS) == expected


@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro"])
def test_cap_cannot_cost_more_than_the_usd_for_any_input_output_split(model):
    """The ledger counts prompt+completion as one sum, so the cap must hold for
    every split: input at the cache-miss price, output at the output price."""
    usd = Decimal("30")
    cap = cb.monthly_token_cap_for_usd(usd, [model], endpoint=DS)
    price = cb.DEEPSEEK_PRICES_USD_PER_M[("https://api.deepseek.com:443", model)]
    for out in (0, 1, cap // 3, cap // 2, cap - 1, cap):
        cost = (Fraction(cap - out) * Fraction(price.input_cache_miss)
                + Fraction(out) * Fraction(price.output)) / 10**6
        assert cost <= Fraction(usd), (model, out)
    # ...and is the largest such cap: one more all-output token would exceed.
    assert Fraction(cap + 1) * Fraction(price.output) / 10**6 > Fraction(usd)


@pytest.mark.parametrize("models,endpoint", [
    (["deepseek-chat"], DS),                       # undocumented: no price
    (["deepseek-flash"], "https://openrouter.ai/api/v1"),
    ([], DS),
])
def test_unpriced_model_cannot_derive_a_cap(models, endpoint):
    with pytest.raises(ValueError):
        cb.monthly_token_cap_for_usd(Decimal("30"), models, endpoint=endpoint)


@pytest.mark.parametrize("usd", [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
def test_usd_must_be_positive_and_finite(usd):
    with pytest.raises(ValueError):
        cb.monthly_token_cap_for_usd(usd, ["deepseek-flash"], endpoint=DS)


# ── 4. the config derives the primary cap from DEEPSEEK_PRIMARY_MONTHLY_USD_CAP

def test_usd_cap_sets_the_primary_token_cap(monkeypatch):
    cfg = fresh_config(monkeypatch, DEEPSEEK_PRIMARY_MONTHLY_USD_CAP="30")
    assert cfg.deepseek_primary_monthly_usd_cap == Decimal("30")
    assert cfg.deepseek_primary_monthly_token_cap == 25_000_000


def test_usd_cap_with_legacy_model_name_prices_the_documented_model(monkeypatch):
    cfg = fresh_config(monkeypatch, DEEPSEEK_PRIMARY_MONTHLY_USD_CAP="30",
                       DEEPSEEK_MODEL="deepseek-chat")
    assert cfg.deepseek_primary_monthly_token_cap == 25_000_000


def test_usd_cap_prices_the_dearest_configured_model(monkeypatch):
    cfg = fresh_config(monkeypatch, DEEPSEEK_PRIMARY_MONTHLY_USD_CAP="30",
                       DEEPSEEK_MODEL="deepseek-flash", DEEPSEEK_MODEL_FALLBACK="deepseek-v4-pro")
    assert cfg.deepseek_primary_monthly_token_cap == 7_575_757


def test_lower_explicit_token_cap_still_wins(monkeypatch):
    cfg = fresh_config(monkeypatch, DEEPSEEK_PRIMARY_MONTHLY_USD_CAP="30",
                       DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP="10000000")
    assert cfg.deepseek_primary_monthly_token_cap == 10_000_000


@pytest.mark.parametrize("token_cap", ["0", "100000000"])
def test_usd_cap_overrides_unlimited_or_higher_token_cap(monkeypatch, token_cap):
    cfg = fresh_config(monkeypatch, DEEPSEEK_PRIMARY_MONTHLY_USD_CAP="30",
                       DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP=token_cap)
    assert cfg.deepseek_primary_monthly_token_cap == 25_000_000


@pytest.mark.parametrize("env", [
    {"DEEPSEEK_PRIMARY_MONTHLY_USD_CAP": "30$"},
    {"DEEPSEEK_PRIMARY_MONTHLY_USD_CAP": "-5"},
    {"DEEPSEEK_PRIMARY_MONTHLY_USD_CAP": "30", "DEEPSEEK_MODEL": "deepseek-reasoner"},
    {"DEEPSEEK_PRIMARY_MONTHLY_USD_CAP": "30", "DEEPSEEK_BASE_URL": "https://openrouter.ai/api/v1"},
])
def test_unusable_usd_cap_fails_closed(monkeypatch, env):
    # A typo in a spending cap is never "no cap": cloud is denied (the local
    # chain answers) and deploy_gate --check-env refuses the file first.
    cfg = fresh_config(monkeypatch, **env)
    assert cfg.deepseek_primary_monthly_token_cap == 1


def test_without_usd_cap_the_token_cap_is_unchanged(monkeypatch):
    assert fresh_config(monkeypatch).deepseek_primary_monthly_token_cap == 100_000_000
    cfg = fresh_config(monkeypatch, DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP="0")
    assert cfg.deepseek_primary_monthly_token_cap == 0
    assert cfg.deepseek_primary_monthly_usd_cap is None


# ── 5. batch callers (record_chat_completion) get the same alias ───────────

class _Completions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = types.SimpleNamespace(content="ok")
        usage = types.SimpleNamespace(prompt_tokens=5, completion_tokens=2)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=usage)


def _client(base_url=DS):
    comp = _Completions()
    return types.SimpleNamespace(base_url=httpx.URL(base_url + "/"),
                                 chat=types.SimpleNamespace(completions=comp)), comp


@pytest.fixture
def tdb(monkeypatch, tmp_path):
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "sessions.db")


def test_batch_call_with_legacy_name_goes_out_documented_and_non_thinking(tdb):
    client, comp = _client()
    gw.record_chat_completion(client, tier="kb_gap_judge", model="deepseek-chat",
                              messages=[{"role": "user", "content": "x"}], max_tokens=16)
    (call,) = comp.calls
    assert call["model"] == "deepseek-flash"
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}


def test_batch_call_on_documented_model_defaults_to_non_thinking(tdb):
    client, comp = _client()
    gw.record_chat_completion(client, tier="t", model="deepseek-flash", max_tokens=16,
                              messages=[{"role": "user", "content": "x"}],
                              extra_body={"keep": 1})
    assert comp.calls[0]["extra_body"] == {"keep": 1, "thinking": {"type": "disabled"}}


@pytest.mark.parametrize("kwargs", [{"extra_body": {"thinking": {"type": "enabled"}}},
                                    {"reasoning_effort": "high"}])
def test_batch_caller_that_asks_for_thinking_keeps_it(tdb, kwargs):
    client, comp = _client()
    gw.record_chat_completion(client, tier="t", model="deepseek-flash", max_tokens=16,
                              messages=[{"role": "user", "content": "x"}], **kwargs)
    call = comp.calls[0]
    assert call.get("extra_body", {}).get("thinking") == kwargs.get("extra_body", {}).get("thinking")
    assert call.get("reasoning_effort") == kwargs.get("reasoning_effort")


def test_batch_call_to_another_host_is_untouched(tdb):
    client, comp = _client("https://ollama.com/v1")
    gw.record_chat_completion(client, tier="t", model="deepseek-chat",
                              messages=[{"role": "user", "content": "x"}])
    assert comp.calls[0]["model"] == "deepseek-chat" and "extra_body" not in comp.calls[0]


# ── 6. deploy_gate --check-env validates the cap settings ─────────────────

def _gate():
    spec = importlib.util.spec_from_file_location("deploy_gate_ds", ROOT / "ops/tools/deploy_gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["deploy_gate_ds"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("body,code,shown", [
    ("DEEPSEEK_PRIMARY_MONTHLY_USD_CAP=30\n", 0, "25000000"),
    ("DEEPSEEK_MODEL=deepseek-chat\nDEEPSEEK_PRIMARY_MONTHLY_USD_CAP=30\n", 0, "25000000"),
    ("DEEPSEEK_PRIMARY_MONTHLY_USD_CAP=\"30\"\nDEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP=0\n", 0, "25000000"),
    ("DEEPSEEK_PRIMARY_MONTHLY_USD_CAP=30\nDEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP=10000000\n", 0, "10000000"),
    ("DEEPSEEK_MODEL_FALLBACK=deepseek-v4-pro\nDEEPSEEK_PRIMARY_MONTHLY_USD_CAP=30\n", 0, "7575757"),
    ("DEEPSEEK_PRIMARY_MONTHLY_USD_CAP=30$\n", 1, "DEEPSEEK_PRIMARY_MONTHLY_USD_CAP"),
    ("DEEPSEEK_MODEL=deepseek-reasoner\nDEEPSEEK_PRIMARY_MONTHLY_USD_CAP=30\n", 1, "deepseek-reasoner"),
    ("DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP=1e7\n", 1, "DEEPSEEK_PRIMARY_MONTHLY_TOKEN_CAP"),
    ("", 0, "100000000"),
])
def test_preflight_validates_and_shows_the_effective_cap(tmp_path, capsys, body, code, shown):
    env = tmp_path / ".env"
    env.write_text("CLOUD_BUDGET_ENFORCE=false\n" + body)
    assert _gate().main(["--check-env", str(env)]) == code
    assert shown in capsys.readouterr().out


def test_preflight_copy_agrees_with_the_app():
    gate = _gate()
    assert gate.DOCUMENTED_DEEPSEEK_MODELS == llm_config.DOCUMENTED_DEEPSEEK_MODELS
    assert gate.LEGACY_DEEPSEEK_MODEL_ALIASES == llm_config.LEGACY_DEEPSEEK_MODEL_ALIASES
    assert {k: (v.input_cache_hit, v.input_cache_miss, v.output)
            for k, v in cb.DEEPSEEK_PRICES_USD_PER_M.items()} == gate.DEEPSEEK_PRICES_USD_PER_M
    for name in ["deepseek-chat", "deepseek-v4-flash", "deepseek-flash", "deepseek-reasoner", "x"]:
        for base in [DS, DS + "/v1", "https://openrouter.ai/api/v1"]:
            assert gate.resolve_deepseek_model(name, base) == llm_config.resolve_deepseek_model(name, base)
    for usd in ["30", "2.5", "1000"]:
        for models in (["deepseek-flash"], ["deepseek-v4-pro"], ["deepseek-flash", "deepseek-v4-pro"]):
            assert gate.monthly_token_cap_for_usd(Decimal(usd), models, endpoint=DS) == \
                cb.monthly_token_cap_for_usd(Decimal(usd), models, endpoint=DS)
