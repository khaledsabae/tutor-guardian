"""Admission must be atomic at the actual paid wire, including ambiguous failures."""
import asyncio
import concurrent.futures
import dataclasses
import importlib
import json
import multiprocessing
import sqlite3
import threading
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.services import ai_gateway as gw
from tests.budget_test_helpers import activate


def budget_module():
    # Missing feature is an assertion failure, not a collection/import error.
    assert importlib.util.find_spec("app.services.cloud_budget") is not None, "atomic ledger missing"
    return importlib.import_module("app.services.cloud_budget")


def _process_ticket(path):
    from app.services.cloud_budget import BudgetDenied, CloudBudget
    try:
        CloudBudget(path).reserve("wallet", 100, 60, legacy_aliases=())
        return True
    except BudgetDenied:
        return False


def sse(usage=True):
    obj = {"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}]}
    if usage:
        obj["usage"] = {"prompt_tokens": 5, "completion_tokens": 2}
    return ("data: " + json.dumps(obj) + "\n\ndata: [DONE]\n\n").encode()


@pytest.fixture
def wire(monkeypatch, tmp_path):
    m = budget_module()
    monkeypatch.setattr(m, "_BILLING_PROFILES", {
        ("https://api.deepseek.com:443", "test-model"): m.BillingProfile(1400, 1024),
        ("https://account.openai.azure.com:443", "model"): m.BillingProfile(1400, 1024),
    })
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "calls.db")
    monkeypatch.setattr(gw, "_telemetry_schema_ready", False)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        gw.LLM, primary_provider="deepseek", deepseek_primary_monthly_token_cap=1500,
        deepseek_fallback_monthly_token_cap=1500, deepseek_fallback_enabled=False,
        cloud_tier_enabled=False, max_retries=1, cloud_budget_enforce=True,
    ))
    monkeypatch.setattr(gw, "_PREFLIGHT_BACKOFF_S", (0, 0, 0))
    activate(m.CloudBudget(tmp_path / "calls.db"), wallets=(
        "cloud:https://api.deepseek.com:443", "cloud:https://account.openai.azure.com:443"))
    gw._budget_cache.clear()
    gw.primary_breaker.reset()
    yield tmp_path / "calls.db"
    gw._budget_cache.clear()
    gw.primary_breaker.reset()


def provider(handler, name="deepseek"):
    return gw.OpenAIChatProvider("https://api.deepseek.com", "test-key", "test-model", 3,
                                 name=name, http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_simultaneous_main_and_aux_cannot_both_spend_last_reservation(wire):
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def handler(request):
        calls.append(request)
        entered.set()
        if len(calls) == 1:
            assert release.wait(3)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse(False))

    main, aux = provider(handler), provider(handler, "deepseek_aux")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(main.generate, "سؤال", options={"num_predict": 100})
        assert entered.wait(3)
        second = pool.submit(gw.aux_generate, aux, "سؤال", options={"num_predict": 100},
                             tier="classifier", breaker=None)
        try:
            assert second.result(timeout=2) is None, "aux bypassed an in-flight main reservation"
        finally:
            release.set()
        assert first.result(timeout=3)["response"] == "answer"
    assert len(calls) == 1


def test_context_reservation_blocks_before_wire_when_cap_is_too_small(wire, monkeypatch):
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        gw.LLM, deepseek_primary_monthly_token_cap=1399))
    calls = []
    p = provider(lambda r: calls.append(r) or httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=sse()))
    with pytest.raises(RuntimeError, match="budget"):
        p.generate("س" * 1000, options={"num_predict": 10})
    assert calls == []


def test_each_network_retry_needs_its_own_reservation(wire):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadError("accepted by server, billing unknown")

    with pytest.raises(RuntimeError, match="budget"):
        provider(handler).generate("سؤال", options={"num_predict": 100})
    assert len(calls) == 1, "unknown first attempt was refunded or retry bypassed admission"


def test_closed_stream_without_usage_keeps_its_full_charge(wire):
    calls = []
    p = provider(lambda r: calls.append(r) or httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=sse(False)))
    chunks = p.stream("سؤال", options={"num_predict": 100})
    assert next(chunks)["response"] == "answer"
    chunks.close()
    with pytest.raises(RuntimeError, match="budget"):
        p.generate("سؤال", options={"num_predict": 100})
    assert len(calls) == 1


def test_unknown_budget_keeps_gateway_answering_locally(wire, monkeypatch, tmp_path):
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "\0invalid.db")
    calls = []
    gateway = gw.AIGateway.__new__(gw.AIGateway)
    gateway.provider = provider(lambda r: calls.append(r) or httpx.Response(500))
    gateway.primary_model = gateway.model = "test-model"

    async def local(self, *args, **kwargs):
        return gw.LLMResult(text="local answer", model="local", latency_ms=1)

    monkeypatch.setattr(gw.AIGateway, "_try_provider", local)
    result = asyncio.run(gateway.generate("سؤال"))
    assert result.text == "local answer"
    assert calls == [], "unreadable accounting must not fail open to paid cloud"


def test_independent_sqlite_connections_admit_only_one_last_slot(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    activate(m.CloudBudget(path))
    barrier = threading.Barrier(12)

    def contender(_):
        ledger = m.CloudBudget(path)
        barrier.wait(timeout=5)
        try:
            return ledger.reserve("wallet", 100, 60, legacy_aliases=())
        except m.BudgetDenied:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        tickets = list(pool.map(contender, range(12)))
    assert sum(t is not None for t in tickets) == 1


def test_separate_processes_share_the_same_last_slot(tmp_path):
    activate(budget_module().CloudBudget(tmp_path / "ledger.db"))
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=4, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        assert sum(pool.map(_process_ticket, [tmp_path / "ledger.db"] * 8, timeout=15)) == 1


def test_unknown_budget_stream_stays_on_local_chain(wire, monkeypatch, tmp_path):
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "\0invalid.db")
    calls = []
    gateway = gw.AIGateway.__new__(gw.AIGateway)
    gateway.provider = provider(lambda r: calls.append(r) or httpx.Response(500))
    gateway.primary_model = gateway.model = "test-model"

    def local(self, prompt, *, options):
        yield {"response": "local answer", "done": False}
        yield {"response": "", "done": True}

    monkeypatch.setattr(gw.OllamaProvider, "stream", local)
    assert "".join(c.delta for c in gateway.stream("سؤال") if not c.done) == "local answer"
    assert calls == []


def test_settlement_releases_only_verified_complete_usage(tmp_path):
    m = budget_module()
    ledger = activate(m.CloudBudget(tmp_path / "ledger.db"))
    ticket = ledger.reserve("wallet", 100, 90, legacy_aliases=())
    ledger.settle(ticket, 5, 5)
    assert ledger.reserve("wallet", 100, 90, legacy_aliases=()) is not None
    # Repeated settlement cannot overwrite charged usage or free another ticket.
    ledger.settle(ticket, 0, 0)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())


def test_missing_or_over_bound_usage_never_frees_budget(tmp_path):
    m = budget_module()
    ledger = activate(m.CloudBudget(tmp_path / "ledger.db"))
    ticket = ledger.reserve("wallet", 100, 90, legacy_aliases=())
    ledger.settle(ticket, None, 1)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 20, legacy_aliases=())
    ledger.settle(ticket, 100, 100)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 1000, 1, legacy_aliases=())


def test_legacy_main_and_fallback_are_one_opening_balance(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE llm_calls (ts TEXT,provider TEXT,prompt_tokens INTEGER,completion_tokens INTEGER)")
        for alias in ("deepseek", "deepseek_fallback"):
            conn.execute("INSERT INTO llm_calls VALUES(datetime('now'),?,40,0)", (alias,))
    ledger = activate(m.CloudBudget(path), opening=80)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 21, legacy_aliases=("deepseek", "deepseek_fallback"))
    assert ledger.reserve("wallet", 100, 20, legacy_aliases=("deepseek", "deepseek_fallback"))


def test_late_completion_is_charged_to_both_potential_billing_months(tmp_path):
    m = budget_module()
    now = [datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)]
    path = tmp_path / "ledger.db"
    old = activate(m.CloudBudget(path, clock=lambda: now[0])).reserve("wallet", 100, 100, legacy_aliases=())
    with pytest.raises(m.BudgetDenied):
        m.CloudBudget(path, clock=lambda: now[0]).reserve("wallet", 100, 1, legacy_aliases=())
    now[0] = datetime(2026, 11, 1, tzinfo=timezone.utc)
    ledger = activate(m.CloudBudget(path, clock=lambda: now[0]))
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())
    ledger.settle(old, 1, 1)
    ledger.reserve("wallet", 100, 98, legacy_aliases=())
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())


def test_unknown_legacy_billing_blocks_admission(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE llm_calls (ts TEXT,provider TEXT,prompt_tokens INTEGER,completion_tokens INTEGER)")
        conn.execute("INSERT INTO llm_calls VALUES(datetime('now'),'deepseek',NULL,NULL)")
    with pytest.raises(m.BudgetDenied, match="unknown"):
        activate(m.CloudBudget(path))


def test_busy_accounting_denies_instead_of_spending_blind(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    activate(m.CloudBudget(path)).reserve("wallet", 100, 1, legacy_aliases=())
    with sqlite3.connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(m.BudgetDenied):
            m.CloudBudget(path).reserve("wallet", 100, 1, legacy_aliases=())


@pytest.mark.parametrize("value", [0, -1, True, 1.5, None])
def test_unbounded_or_invalid_output_is_not_admitted(wire, value):
    calls = []
    p = provider(lambda r: calls.append(r) or httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=sse()))
    with pytest.raises(RuntimeError, match="budget"):
        p.generate("question", options={"num_predict": value})
    assert calls == []


def test_azure_sdk_disables_hidden_retries_and_reserves_every_call(wire, monkeypatch):
    constructors, calls = [], []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
                               usage=None)

    def sdk(**kwargs):
        constructors.append(kwargs)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AzureOpenAI=sdk))
    p = gw.OpenAICompatProvider("https://account.openai.azure.com", "test-key", "v1", "model", 3)
    assert constructors[0].get("max_retries") == 0, "SDK retry bypasses per-attempt admission"
    assert constructors[0].get("http_client") is not None
    assert constructors[0]["http_client"].follow_redirects is False
    assert p.generate("سؤال", options={"num_predict": 100})["response"] == "answer"
    with pytest.raises(RuntimeError, match="budget"):
        p.generate("سؤال", options={"num_predict": 100})
    assert len(calls) == 1


def test_budget_denial_does_not_poison_next_small_request_or_provider_health(wire, monkeypatch):
    calls = []
    p = provider(lambda r: calls.append(r) or httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=sse()))
    gateway = gw.AIGateway.__new__(gw.AIGateway)
    gateway.provider = p
    gateway.primary_model = gateway.model = "test-model"

    async def local(self, *args, **kwargs):
        return gw.LLMResult(text="local", model="local", latency_ms=1)

    monkeypatch.setattr(gw.AIGateway, "_try_provider", local)
    for _ in range(2):
        assert asyncio.run(gateway.generate("س" * 1000, options={"num_predict": 1025})).text == "local"
    assert not gw.primary_breaker.is_open(), "budget denial is not a provider outage"
    assert p.generate("سؤال", options={"num_predict": 100})["response"] == "answer"
    assert len(calls) == 1


def test_azure_abort_closes_transport_and_retains_charge(wire, monkeypatch):
    closed = []

    class Stream:
        def __iter__(self):
            yield SimpleNamespace(usage=None, choices=[SimpleNamespace(
                delta=SimpleNamespace(content="answer"), finish_reason=None)])
        def close(self):
            closed.append(True)

    def sdk(**kwargs):
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: Stream())))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AzureOpenAI=sdk))
    p = gw.OpenAICompatProvider("https://account.openai.azure.com", "test-key", "v1", "model", 3)
    chunks = p.stream("سؤال", options={"num_predict": 100})
    assert next(chunks)["response"] == "answer"
    chunks.close()
    assert closed == [True]
    with pytest.raises(RuntimeError, match="budget"):
        p.generate("سؤال", options={"num_predict": 100})


def test_settlement_failure_retains_durable_upper_bound(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    ledger = activate(m.CloudBudget(path))
    ticket = ledger.reserve("wallet", 100, 100, legacy_aliases=())
    with sqlite3.connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        ledger.settle(ticket, 1, 1)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())


def test_unknown_orphan_is_carried_across_months_until_billing_is_known(tmp_path):
    m = budget_module()
    now = [datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)]
    ledger = activate(m.CloudBudget(tmp_path / "ledger.db", clock=lambda: now[0]))
    ledger.reserve("wallet", 100, 100, legacy_aliases=())
    now[0] = datetime(2026, 11, 1, tzinfo=timezone.utc)
    activate(ledger)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())
    now[0] = datetime(2026, 12, 1, tzinfo=timezone.utc)
    activate(ledger)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())


def test_completed_missing_usage_charges_bound_but_is_not_an_inflight_orphan(tmp_path):
    m = budget_module()
    now = [datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)]
    ledger = activate(m.CloudBudget(tmp_path / "ledger.db", clock=lambda: now[0]))
    ticket = ledger.reserve("wallet", 100, 100, legacy_aliases=())
    ledger.settle(ticket, None, None)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())
    now[0] = datetime(2026, 11, 1, tzinfo=timezone.utc)
    activate(ledger)
    assert ledger.reserve("wallet", 100, 100, legacy_aliases=())


def test_azure_usage_without_terminal_choice_never_refunds_reservation(wire, monkeypatch):
    def create(**kwargs):
        return iter([SimpleNamespace(usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
            choices=[SimpleNamespace(delta=SimpleNamespace(content="partial"), finish_reason=None)])])

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AzureOpenAI=lambda **k:
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))))
    p = gw.OpenAICompatProvider("https://account.openai.azure.com", "test-key", "v1", "model", 3)
    with pytest.raises(gw.ProviderStreamError):
        list(p.stream("سؤال", options={"num_predict": 100}))
    with pytest.raises(RuntimeError, match="budget"):
        p.generate("سؤال", options={"num_predict": 100})


def test_legacy_paid_aliases_without_endpoint_metadata_are_imported_conservatively(wire, monkeypatch, tmp_path):
    wire = tmp_path / 'legacy-calls.db'
    monkeypatch.setattr(gw, '_TELEMETRY_DB', wire)
    monkeypatch.setattr(gw, '_telemetry_schema_ready', False)
    with sqlite3.connect(wire) as conn:
        gw._ensure_telemetry_schema(conn)
        conn.execute("INSERT INTO llm_calls(provider,prompt_tokens,completion_tokens) VALUES('deepseek',1000,0)")
    activate(budget_module().CloudBudget(wire), wallets=("cloud:https://account.openai.azure.com:443",), opening=1000)
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
        choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))])
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AzureOpenAI=lambda **k:
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response)))))
    p = gw.OpenAICompatProvider("https://account.openai.azure.com", "test-key", "v1", "model", 3)
    with pytest.raises(RuntimeError, match="budget"):
        p.generate("سؤال", options={"num_predict": 100})


def test_unverified_input_billing_contract_is_denied_before_any_paid_wire(wire):
    """MERGE BLOCKER: framing allowance is not a proven provider billing bound.

    This model has no verified tokenizer/framing/billing contract. A provider
    may add hidden billable input; learning that only from usage is too late.
    Quarantine after an over-bound response cannot prevent this first overspend.
    """
    calls = []

    def handler(request):
        calls.append(request)
        obj = {"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}],
               "usage": {"prompt_tokens": 10000, "completion_tokens": 2}}
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content=("data: " + json.dumps(obj) + "\n\ndata: [DONE]\n\n").encode())

    unverified = provider(handler)
    unverified.model = "unverified-input-billing-model"
    with pytest.raises(RuntimeError, match="budget|billing|bound"):
        unverified.generate("سؤال", options={"num_predict": 100})
    assert calls == [], "unverified billing cannot authorize the first paid wire"


def test_unknown_billing_profile_stays_on_local_chain(wire, monkeypatch):
    calls = []
    gateway = gw.AIGateway.__new__(gw.AIGateway)
    gateway.provider = provider(lambda r: calls.append(r) or httpx.Response(500))
    gateway.provider.model = 'unverified-input-billing-model'
    gateway.primary_model = gateway.model = gateway.provider.model

    async def local(self, *args, **kwargs):
        return gw.LLMResult(text='local answer', model='local', latency_ms=1)

    monkeypatch.setattr(gw.AIGateway, '_try_provider', local)
    assert asyncio.run(gateway.generate('سؤال')).text == 'local answer'
    assert calls == []
    assert not gw.primary_breaker.is_open()


def test_model_switch_rechecks_profile_before_second_wire(wire, monkeypatch):
    monkeypatch.setattr(gw, 'LLM', dataclasses.replace(
        gw.LLM, deepseek_primary_monthly_token_cap=10000))
    monkeypatch.setattr(gw, '_MODEL_SWITCHED', {})
    calls = []

    def rejected(request):
        calls.append(request)
        return httpx.Response(400, json={'error': {'message': 'model not found'}})

    p = provider(rejected)
    p.fallback_model = 'unverified-input-billing-model'
    with pytest.raises(RuntimeError, match='profile'):
        p.generate('سؤال', options={'num_predict': 100})
    assert len(calls) == 1


@pytest.mark.parametrize('damage', ['missing', 'uninitialized', 'lost_schema', 'restored'])
@pytest.mark.parametrize('streamed', [False, True])
def test_cutover_damage_denies_wire_and_keeps_local_fallback(wire, monkeypatch, tmp_path, damage, streamed):
    import shutil
    if damage == 'missing':
        wire.unlink()
    elif damage == 'uninitialized':
        wire = tmp_path / 'fresh-history.db'
        monkeypatch.setattr(gw, '_TELEMETRY_DB', wire)
        with sqlite3.connect(wire) as conn:
            monkeypatch.setattr(gw, '_telemetry_schema_ready', False)
            gw._ensure_telemetry_schema(conn)
    elif damage == 'lost_schema':
        with sqlite3.connect(wire) as conn:
            conn.execute('DROP TABLE cloud_budget_attempts')
    else:
        snapshot = tmp_path / 'snapshot.db'
        shutil.copyfile(wire, snapshot)
        gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek', [], 100, model='test-model')
        shutil.copyfile(snapshot, wire)
    calls = []
    gateway = gw.AIGateway.__new__(gw.AIGateway)
    gateway.provider = provider(lambda r: calls.append(r) or httpx.Response(500))
    gateway.primary_model = gateway.model = 'test-model'
    async def local(self, *args, **kwargs):
        return gw.LLMResult(text='local answer', model='local', latency_ms=1)
    def local_stream(self, prompt, *, options):
        yield {'response': 'local answer', 'done': False}
        yield {'response': '', 'done': True}
    monkeypatch.setattr(gw.AIGateway, '_try_provider', local)
    monkeypatch.setattr(gw.OllamaProvider, 'stream', local_stream)
    if streamed:
        assert ''.join(c.delta for c in gateway.stream('question') if not c.done) == 'local answer'
    else:
        assert asyncio.run(gateway.generate('question')).text == 'local answer'
    assert calls == []
    assert not gw.primary_breaker.is_open()


def test_diagnostics_never_recreate_lost_activated_history(wire, monkeypatch):
    with sqlite3.connect(wire) as conn:
        conn.execute('DROP TABLE llm_calls')
    monkeypatch.setattr(gw, '_telemetry_schema_ready', False)
    gw._log_call('deepseek', 'test-model', 1, 0, 0, False, False)
    gw._monthly_tokens_used('deepseek')
    with sqlite3.connect(wire) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='llm_calls'").fetchone()
    with pytest.raises(budget_module().BudgetDenied):
        gw._reserve_wire_budget('https://api.deepseek.com', 'deepseek', [], 100, model='test-model')


# ── Unknown usage settles to the request's own bound, not the whole context ──
# Production, October 2026: 26 paid rows without usage. Holding the full
# 1,048,576-token reservation for each would have parked ~27M tokens of a
# 100M cap for <1M of real spend, and 10 of them exhaust the 10M fallback.
def _charges(path):
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT charged_tokens, settled FROM cloud_budget_attempts "
                            "ORDER BY rowid").fetchall()


def test_request_bound_covers_every_byte_plus_framing_and_the_output_cap():
    m = budget_module()
    messages = [{"role": "user", "content": "س" * 3000 + "123 456 !?"}]
    input_bound, output_bound = m.unknown_usage_bounds(messages, 700)
    payload = len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))
    assert input_bound >= payload + m.UNKNOWN_USAGE_FRAMING_TOKENS
    assert input_bound >= 3 * gw._estimate_tokens(messages[0]["content"])  # never below the telemetry estimate
    assert output_bound == 700


def test_unknown_usage_settles_to_the_request_bound(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    ledger = activate(m.CloudBudget(path))
    ticket = ledger.reserve("wallet", 1000, 900, legacy_aliases=(), unknown_usage_bounds=(300, 50))
    ledger.settle(ticket, None, None)
    assert _charges(path) == [(350, 1)]
    ledger.reserve("wallet", 1000, 650, legacy_aliases=())
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 1000, 1, legacy_aliases=())


def test_partial_usage_keeps_the_reported_half(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    ledger = activate(m.CloudBudget(path))
    ticket = ledger.reserve("wallet", 1000, 900, legacy_aliases=(), unknown_usage_bounds=(300, 50))
    ledger.settle(ticket, 10, None)
    assert _charges(path) == [(60, 1)]


def test_request_bound_never_exceeds_reservation_or_quarantines(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    ledger = activate(m.CloudBudget(path))
    ticket = ledger.reserve("wallet", 1000, 900, legacy_aliases=(), unknown_usage_bounds=(5000, 5000))
    ledger.settle(ticket, None, None)
    assert _charges(path) == [(900, 1)]
    ledger.reserve("wallet", 1000, 100, legacy_aliases=())   # not quarantined


@pytest.mark.parametrize("bounds", [(-1, 5), (5, 0), (True, 5), (1.5, 5), ("5", 5), (5,)])
def test_invalid_request_bounds_are_refused(tmp_path, bounds):
    m = budget_module()
    ledger = activate(m.CloudBudget(tmp_path / "ledger.db"))
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 1000, 900, legacy_aliases=(), unknown_usage_bounds=bounds)


@pytest.fixture
def big_wire(wire, monkeypatch):
    """A real-size context: 1M profile, cap = one reservation + headroom."""
    m = budget_module()
    monkeypatch.setattr(m, "_BILLING_PROFILES", {
        ("https://api.deepseek.com:443", "test-model"): m.BillingProfile(1048576, 4096),
        ("https://account.openai.azure.com:443", "model"): m.BillingProfile(1048576, 4096),
    })
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        gw.LLM, deepseek_primary_monthly_token_cap=1048576 + 100000))
    return wire


def _sse_cut():
    obj = {"choices": [{"delta": {"content": "half an ans"}, "finish_reason": None}]}
    return ("data: " + json.dumps(obj) + "\n\n").encode()   # no usage, no [DONE]


def _assert_request_bound(charge, *, max_tokens=100):
    m = budget_module()
    assert charge[1] == 1, "an ended attempt is settled, not an in-flight orphan"
    assert max_tokens < charge[0] <= 50000 + m.UNKNOWN_USAGE_FRAMING_TOKENS + max_tokens, charge


def test_cut_stream_settles_to_request_bound_and_frees_the_context(big_wire):
    calls = []
    p = provider(lambda r: calls.append(r) or httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=_sse_cut()))
    with pytest.raises(gw.ProviderStreamError):
        p.generate("سؤال", options={"num_predict": 100})
    [charge] = _charges(big_wire)
    _assert_request_bound(charge)
    # The old full-context hold would deny this second full-size admission.
    with pytest.raises(gw.ProviderStreamError):
        p.generate("سؤال", options={"num_predict": 100})
    assert len(calls) == 2


def test_consumer_leaving_mid_stream_settles_to_request_bound(big_wire):
    body = (b'data: {"choices":[{"delta":{"content":"one"},"finish_reason":null}]}\n\n'
            b'data: {"choices":[{"delta":{"content":"two"},"finish_reason":null}]}\n\n')
    p = provider(lambda r: httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body))
    chunks = p.stream("سؤال", options={"num_predict": 100})
    assert next(chunks)["response"]
    chunks.close()
    [charge] = _charges(big_wire)
    _assert_request_bound(charge)


def test_success_without_usage_settles_to_request_bound(big_wire):
    p = provider(lambda r: httpx.Response(200, headers={"content-type": "text/event-stream"},
                                          content=sse(usage=False)))
    assert p.generate("سؤال", options={"num_predict": 100})["response"] == "answer"
    [charge] = _charges(big_wire)
    _assert_request_bound(charge)


def test_retried_attempt_is_settled_not_orphaned(big_wire):
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, content=b"busy")
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse())

    p = provider(handler)
    assert p.generate("سؤال", options={"num_predict": 100})["response"] == "answer"
    first, second = _charges(big_wire)
    _assert_request_bound(first)
    assert second == (7, 1)


def test_azure_failure_settles_to_request_bound(big_wire, monkeypatch):
    def create(**kwargs):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AzureOpenAI=lambda **k:
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))))
    p = gw.OpenAICompatProvider("https://account.openai.azure.com", "test-key", "v1", "model", 3)
    with pytest.raises(httpx.ReadTimeout):
        p.generate("سؤال", options={"num_predict": 100})
    with pytest.raises(httpx.ReadTimeout):
        list(p.stream("سؤال", options={"num_predict": 100}))
    for charge in _charges(big_wire):
        _assert_request_bound(charge)
