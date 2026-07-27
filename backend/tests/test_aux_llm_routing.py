"""Auxiliary LLM tier — domain classifier + query rewriter routing.

Both used to post straight at a hard-coded Ollama host with a 45s / 6s
timeout, bypassing the gateway entirely. When that host went offline while
generation had already moved to DeepSeek, every keyword-fast-path MISS cost
45 wasted seconds and then returned a single arbitrary domain ('medical'),
scoping retrieval to the wrong knowledge base without saying so.

These tests pin the four properties that fix must keep:
  1. the classifier follows the CONFIGURED primary provider,
  2. a dead host costs seconds once, then nothing (circuit breaker),
  3. paid auxiliary spend is logged to llm_calls and capped by the same
     monthly ceiling as chat,
  4. a failed classification never masquerades as a confident one.
"""
import sqlite3
from dataclasses import dataclass

import pytest

from app.services import ai_gateway, domain_classifier as dc, query_rewriter as qr

# Captured before the autouse fixtures replace them with stubs.
_REAL_CALL_LLM = dc._call_llm
_REAL_LOG_CALL = ai_gateway._log_call

# A question with no KB-aligned keyword — the case that pays for the LLM tier.
# (The real production question that exposed the 45s stall.)
MISS_Q = "ابني بيقارن نفسه بأصحابه على انستجرام وبقى حزين"


@dataclass
class _FakeLLM:
    primary_provider: str = "deepseek"
    deepseek_api_key: str = "sk-test"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_primary_monthly_token_cap: int = 1000
    local_base_url: str = "http://127.0.0.1:11434"
    local_fast_model: str = "qwen2.5:3b"


class _FakeCloud:
    """Stands in for OpenAIChatProvider — answers a fixed classification."""

    def __init__(self, *, name="deepseek", model="deepseek-chat", timeout=0, **kw):
        self.name, self.model, self.timeout, self.kwargs = name, model, timeout, kw
        self.calls = 0

    def generate(self, prompt, *, options):
        self.calls += 1
        return {"response": '{"domains": ["cyber"]}', "done": True,
                "prompt_eval_count": 120, "eval_count": 12}


class _DeadHost:
    """Any provider whose host is unreachable."""

    name, model = "ollama", "qwen2.5:3b"

    def __init__(self, *a, **kw):
        self.timeout = kw.get("timeout")

    def generate(self, prompt, *, options):
        raise TimeoutError("urlopen error timed out")


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """The classifier cache, the breaker and the budget memo are all process
    globals — a leak would answer the next test instead of the code under test."""
    dc._classify_cached.cache_clear()
    qr._rewrite_cached.cache_clear()
    ai_gateway.aux_breaker.reset()
    ai_gateway._budget_cache.clear()
    monkeypatch.setattr(dc, "_call_llm", _REAL_CALL_LLM)  # undo conftest's stub
    monkeypatch.setattr(ai_gateway, "_log_call", lambda *a, **k: None)
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 0)
    # The rewriter's second cache lives in ops/sessions.db and outlives the
    # process — a leftover row would answer instead of the provider.
    monkeypatch.setattr(qr, "_cache_get", lambda qhash: None)
    monkeypatch.setattr(qr, "_cache_put", lambda qhash, rewritten: None)
    yield
    dc._classify_cached.cache_clear()
    qr._rewrite_cached.cache_clear()
    ai_gateway.aux_breaker.reset()
    ai_gateway._budget_cache.clear()


@pytest.fixture()
def cloud(monkeypatch):
    """DeepSeek configured as primary, with a fake client."""
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM())
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _FakeCloud)
    monkeypatch.setattr(dc, "OllamaProvider", _DeadHost)
    return _FakeCloud


# ── 1. the classifier follows the configured primary ──────────────────────
def test_classifier_uses_deepseek_when_it_is_primary(cloud):
    provider = dc._classifier_provider()
    assert isinstance(provider, _FakeCloud)
    assert provider.kwargs["base_url"] == "https://api.deepseek.com"
    # Same telemetry identity as the gateway primary → one bill, one cap.
    assert provider.name == "deepseek"


def test_classifier_classifies_through_deepseek(cloud):
    assert dc.classify_domains(MISS_Q) == ["cyber"]


def test_classifier_stays_on_ollama_when_ollama_is_primary(monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(primary_provider="ollama"))
    assert isinstance(dc._classifier_provider(), ai_gateway.OllamaProvider)


# ── 2. a dead host costs seconds, then nothing ────────────────────────────
def test_classifier_timeout_is_seconds_not_a_minute(monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(primary_provider="ollama"))
    provider = dc._classifier_provider()
    assert dc.CLASSIFIER_TIMEOUT_S <= 10, "a 60-token classification must not wait ~45s"
    assert provider.timeout == dc.CLASSIFIER_TIMEOUT_S


def test_rewriter_timeout_is_seconds(monkeypatch):
    captured = {}
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(primary_provider="ollama"))
    monkeypatch.setattr(ai_gateway, "OllamaProvider",
                        lambda **kw: captured.update(kw) or _DeadHost(**kw))
    qr.rewrite_query("سؤال طويل بما يكفي ليعاد صياغته", classifier_fast_path=False)
    assert captured["timeout"] <= 10


def test_dead_host_is_probed_twice_then_short_circuited(monkeypatch):
    attempts = {"n": 0}

    class _Counting(_DeadHost):
        def generate(self, prompt, *, options):
            attempts["n"] += 1
            raise TimeoutError("timed out")

    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(primary_provider="ollama"))
    monkeypatch.setattr(dc, "OllamaProvider", _Counting)
    for q in (MISS_Q, MISS_Q + " ؟", MISS_Q + " ؟؟", MISS_Q + " ؟؟؟"):
        assert dc.classify_domains(q) == list(dc.UNCERTAIN_DOMAINS)
    # threshold=2: only the first two questions pay the timeout, the rest 0ms
    assert attempts["n"] == 2


def test_rewriter_shares_the_breaker_with_the_classifier(monkeypatch):
    """Once the classifier proved the host dead, the rewriter must not pay the
    timeout again to re-prove it on the very same request."""
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(primary_provider="ollama"))
    monkeypatch.setattr(dc, "OllamaProvider", _DeadHost)
    built = {"n": 0}

    def _never(**kw):
        built["n"] += 1
        return _DeadHost(**kw)

    dc.classify_domains(MISS_Q)
    dc.classify_domains(MISS_Q + " ؟")  # breaker opens here
    monkeypatch.setattr(ai_gateway, "OllamaProvider", _never)
    assert qr.rewrite_query("سؤال طويل بما يكفي ليعاد صياغته", classifier_fast_path=False) == ""
    assert built["n"] == 0


# ── 3. paid auxiliary spend is visible and capped ─────────────────────────
def test_classifier_spend_is_logged_to_telemetry(cloud, monkeypatch, tmp_path):
    db = tmp_path / "telemetry.db"
    monkeypatch.setattr(ai_gateway, "_TELEMETRY_DB", db)
    monkeypatch.setattr(ai_gateway, "_telemetry_schema_ready", False)
    monkeypatch.setattr(ai_gateway, "_log_call", _REAL_LOG_CALL)

    assert dc.classify_domains(MISS_Q) == ["cyber"]

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT provider, tier, prompt_tokens, completion_tokens, ok FROM llm_calls"
    ).fetchone()
    conn.close()
    assert row == ("deepseek", "classifier", 120, 12, 1)


def test_classifier_refuses_to_spend_past_the_monthly_cap(cloud, monkeypatch):
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used", lambda name: 1000)  # == cap
    ai_gateway._budget_cache.clear()
    # No cloud provider → the local path, which here is the dead host stub.
    assert not isinstance(dc._classifier_provider(), _FakeCloud)
    assert dc.classify_domains(MISS_Q) == list(dc.UNCERTAIN_DOMAINS)


def test_auxiliary_spend_counts_against_the_chat_budget(cloud, monkeypatch):
    """Classifier tokens must land in the SAME bucket the gateway meters, or
    the ceiling silently doubles."""
    seen = []
    monkeypatch.setattr(ai_gateway, "_monthly_tokens_used",
                        lambda name: seen.append(name) or 0)
    ai_gateway.aux_cloud_provider(timeout=8)
    assert seen == ["deepseek"]


# ── 4. a failure never masquerades as a confident classification ──────────
def test_failure_returns_a_broad_search_not_one_guessed_domain(monkeypatch):
    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM(primary_provider="ollama"))
    monkeypatch.setattr(dc, "OllamaProvider", _DeadHost)
    domains = dc.classify_domains(MISS_Q)
    assert domains != ["medical"], "the old silent wrong-domain fallback is back"
    assert len(domains) > 1 and dc.is_uncertain(domains)
    assert set(domains) == dc.VALID_DOMAINS


def test_failure_is_not_cached(monkeypatch):
    """An outage must not freeze the broad fallback into the LRU for the life
    of the process — the next question re-tries the provider."""
    state = {"dead": True}

    class _Flaky(_FakeCloud):
        def generate(self, prompt, *, options):
            if state["dead"]:
                raise TimeoutError("timed out")
            return super().generate(prompt, options=options)

    monkeypatch.setattr(ai_gateway, "LLM", _FakeLLM())
    monkeypatch.setattr(ai_gateway, "OpenAIChatProvider", _Flaky)
    monkeypatch.setattr(dc, "OllamaProvider", _DeadHost)

    assert dc.is_uncertain(dc.classify_domains(MISS_Q))
    state["dead"] = False
    ai_gateway.aux_breaker.reset()  # simulate the cool-down elapsing
    assert dc.classify_domains(MISS_Q) == ["cyber"]


def test_router_labels_the_reply_from_the_evidence_when_uncertain():
    """The reply's domain drives guardrails and the answer cache key, so an
    uncertain classification must take it from what retrieval actually found."""
    from app.routers.assistant import _label_domain

    units = [{"source_domain": "cyber"}, {"source_domain": "medical"}]
    assert _label_domain(list(dc.UNCERTAIN_DOMAINS), units) == "cyber"
    # a real classification is still authoritative
    assert _label_domain(["fiqh"], units) == "fiqh"
    # nothing retrieved → nothing better than the list head
    assert _label_domain(list(dc.UNCERTAIN_DOMAINS), []) == dc.UNCERTAIN_DOMAINS[0]
