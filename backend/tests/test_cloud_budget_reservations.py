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
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "calls.db")
    monkeypatch.setattr(gw, "_telemetry_schema_ready", False)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        gw.LLM, primary_provider="deepseek", deepseek_primary_monthly_token_cap=1500,
        deepseek_fallback_monthly_token_cap=1500, deepseek_fallback_enabled=False,
        cloud_tier_enabled=False, max_retries=1,
    ))
    monkeypatch.setattr(gw, "_PREFLIGHT_BACKOFF_S", (0, 0, 0))
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


def test_utf8_input_plus_output_bound_blocks_before_any_wire(wire):
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
    ledger = m.CloudBudget(tmp_path / "ledger.db")
    ticket = ledger.reserve("wallet", 100, 90, legacy_aliases=())
    ledger.settle(ticket, 5, 5)
    assert ledger.reserve("wallet", 100, 90, legacy_aliases=()) is not None
    # Repeated settlement cannot overwrite charged usage or free another ticket.
    ledger.settle(ticket, 0, 0)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())


def test_missing_or_over_bound_usage_never_frees_budget(tmp_path):
    m = budget_module()
    ledger = m.CloudBudget(tmp_path / "ledger.db")
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
    ledger = m.CloudBudget(path)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 21, legacy_aliases=("deepseek", "deepseek_fallback"))
    assert ledger.reserve("wallet", 100, 20, legacy_aliases=("deepseek", "deepseek_fallback"))


def test_late_completion_is_charged_to_both_potential_billing_months(tmp_path):
    m = budget_module()
    now = [datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)]
    path = tmp_path / "ledger.db"
    old = m.CloudBudget(path, clock=lambda: now[0]).reserve("wallet", 100, 100, legacy_aliases=())
    with pytest.raises(m.BudgetDenied):
        m.CloudBudget(path, clock=lambda: now[0]).reserve("wallet", 100, 1, legacy_aliases=())
    now[0] = datetime(2026, 11, 1, tzinfo=timezone.utc)
    ledger = m.CloudBudget(path, clock=lambda: now[0])
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
        m.CloudBudget(path).reserve("wallet", 100, 1, legacy_aliases=("deepseek",))


def test_busy_accounting_denies_instead_of_spending_blind(tmp_path):
    m = budget_module()
    path = tmp_path / "ledger.db"
    m.CloudBudget(path).reserve("wallet", 100, 1, legacy_aliases=())
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
        assert asyncio.run(gateway.generate("س" * 1000, options={"num_predict": 100})).text == "local"
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
    ledger = m.CloudBudget(path)
    ticket = ledger.reserve("wallet", 100, 100, legacy_aliases=())
    with sqlite3.connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        ledger.settle(ticket, 1, 1)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())


def test_unknown_orphan_is_carried_across_months_until_billing_is_known(tmp_path):
    m = budget_module()
    now = [datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)]
    ledger = m.CloudBudget(tmp_path / "ledger.db", clock=lambda: now[0])
    ledger.reserve("wallet", 100, 100, legacy_aliases=())
    now[0] = datetime(2026, 11, 1, tzinfo=timezone.utc)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())
    now[0] = datetime(2026, 12, 1, tzinfo=timezone.utc)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())


def test_completed_missing_usage_charges_bound_but_is_not_an_inflight_orphan(tmp_path):
    m = budget_module()
    now = [datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)]
    ledger = m.CloudBudget(tmp_path / "ledger.db", clock=lambda: now[0])
    ticket = ledger.reserve("wallet", 100, 100, legacy_aliases=())
    ledger.settle(ticket, None, None)
    with pytest.raises(m.BudgetDenied):
        ledger.reserve("wallet", 100, 1, legacy_aliases=())
    now[0] = datetime(2026, 11, 1, tzinfo=timezone.utc)
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


def test_legacy_paid_aliases_without_endpoint_metadata_are_imported_conservatively(wire, monkeypatch):
    with sqlite3.connect(wire) as conn:
        gw._ensure_telemetry_schema(conn)
        conn.execute("INSERT INTO llm_calls(provider,prompt_tokens,completion_tokens) VALUES('deepseek',1000,0)")
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
