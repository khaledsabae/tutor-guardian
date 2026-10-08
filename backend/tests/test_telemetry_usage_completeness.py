"""Every paid call is an llm_calls row WITH token counts.

Production, October 2026: 26 DeepSeek rows had NULL prompt/completion tokens
(17 of them on 10-01), so the month's spend could not be summed honestly:

  * streams cut before DeepSeek's final usage chunk — the parent closed the
    SSE (client_disconnected, 11 rows) or the turn was cut (cancelled, 1);
  * failed attempts (timeouts) — the request reached DeepSeek, no usage came
    back (7 primary + 2 auxiliary rows);
  * one phantom row per totally failed generate(): latency 0, one second
    after the real failed attempt, written under the provider's name though
    no request was made (7 rows).

Counts the provider did not report are now ESTIMATED and flagged
(usage_estimated=1), never left NULL and never silently zero; a request the
provider refused (HTTP error, never connected) is an explicit, flagged zero.
"""
from __future__ import annotations

import asyncio
import dataclasses
import sqlite3
import threading
import types

import httpx
import pytest

from app.config import llm_config
from app.services import ai_gateway as gw
from tests import fake_deepseek as fk

PROMPT = "س" * 300   # ~600 UTF-8 bytes: an estimate of 0 or 1 is not one


@pytest.fixture(scope="module")
def server():
    srv, url = fk.start()
    yield url
    srv.shutdown()


@pytest.fixture
def wire(server, monkeypatch, tmp_path):
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "sessions.db")
    monkeypatch.setattr(gw, "_telemetry_schema_ready", False)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        llm_config.LLM, base_url=server, local_base_url=server,
        local_fast_model="local_ok", local_fallback_model="local_ok", fallback_model="local_ok",
        deepseek_fallback_enabled=False, cloud_tier_enabled=False,
    ))
    monkeypatch.setattr(gw, "primary_budget_available", lambda name: True)
    monkeypatch.setattr(gw, "_MODEL_SWITCHED", {}, raising=False)
    monkeypatch.setattr(gw, "_NO_THINKING_FIELD", set(), raising=False)
    gw.primary_breaker.reset()
    yield server
    gw.primary_breaker.reset()


def _provider(url, scenario, timeout=5):
    return gw.OpenAIChatProvider(base_url=url, api_key="test-placeholder", model=scenario,
                                 timeout=timeout, name="deepseek")


def _rows(db=None, provider="deepseek"):
    con = sqlite3.connect(db or gw._TELEMETRY_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM llm_calls ORDER BY id")]
    finally:
        con.close()
    return [r for r in rows if provider is None or r["provider"] == provider]


def _drain(chunks):
    out, err = [], None
    try:
        for ch in chunks:
            if not ch.done:
                out.append(ch.delta)
    except Exception as e:  # noqa: BLE001
        err = e
    return "".join(out), err


def _requests(scenario):
    with fk._LOCK:
        return [e for e in fk.CONN_LOG if e["scenario"] == scenario]


def _assert_estimated(row, *, min_prompt=100, min_completion=0):
    assert row["prompt_tokens"] is not None and row["completion_tokens"] is not None, row
    assert row.get("usage_estimated") == 1, row
    assert row["prompt_tokens"] >= min_prompt, row
    assert row["completion_tokens"] >= min_completion, row


# ── reported usage stays measured ──────────────────────────────────────────

def test_reported_usage_is_measured_not_estimated(wire):
    g = gw.AIGateway(provider=_provider(wire, "normal"))
    text, err = _drain(g.stream(PROMPT))
    assert err is None and text
    (row,) = _rows()
    assert (row["prompt_tokens"], row["completion_tokens"]) == (17, 9)
    assert row.get("usage_estimated") == 0


def test_a_host_that_reports_no_usage_is_estimated_not_null(wire):
    g = gw.AIGateway(provider=_provider(wire, "no_usage"))
    text, err = _drain(g.stream(PROMPT))
    assert err is None and text == "جواب كامل"
    (row,) = _rows()
    assert row["ok"] == 1
    _assert_estimated(row, min_completion=1)


# ── the production NULL rows, one by one ───────────────────────────────────

def test_client_disconnect_mid_stream_is_estimated(wire):
    """client_disconnected: the parent closed the SSE before the usage chunk."""
    g = gw.AIGateway(provider=_provider(wire, "slow_trickle"))
    stream = g.stream(PROMPT)
    got = [next(stream).delta for _ in range(3)]
    assert "".join(got)
    stream.close()
    (row,) = _rows()
    assert row["route_reason"] == "client_disconnected" and row["ok"] == 0
    _assert_estimated(row, min_completion=1)


def test_cut_turn_is_estimated_with_its_real_latency(wire, monkeypatch):
    """cancelled: logged with latency 0 and no tokens, though DeepSeek had
    the whole prompt."""
    monkeypatch.setattr(gw, "PRIMARY_FIRST_TOKEN_S", 5.0)
    cut = threading.Event()
    g = gw.AIGateway(provider=_provider(wire, "hold_long", timeout=60))
    threading.Timer(0.4, cut.set).start()
    _, err = _drain(g.stream(PROMPT, should_stop=cut.is_set))
    assert isinstance(err, gw.LLMCancelled)
    (row,) = _rows()
    assert row["route_reason"] == "cancelled"
    assert row["latency_ms"] >= 300
    _assert_estimated(row)


def test_mid_answer_deadline_is_estimated_with_the_text_received(wire, monkeypatch):
    monkeypatch.setattr(gw, "PRIMARY_STALL_S", 1.0)
    g = gw.AIGateway(provider=_provider(wire, "tokens_then_keepalive_hold"))
    text, err = _drain(g.stream(PROMPT))
    assert text == "بداية " and isinstance(err, gw.LLMDeadlineExceeded)
    (row,) = _rows()
    assert row["route_reason"] == "deadline"
    _assert_estimated(row, min_completion=1)


def test_blocking_timeout_is_estimated_and_no_phantom_row(wire, monkeypatch):
    """The 10-01 pattern: a failed attempt (NULL) and, a second later, a
    latency-0 row under the provider's name for the whole generate()."""
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [])
    g = gw.AIGateway(provider=_provider(wire, "silent_hold", timeout=1))
    before = len(_requests("silent_hold"))
    with pytest.raises(RuntimeError):
        asyncio.run(g.generate(PROMPT, max_retries=2))
    sent = len(_requests("silent_hold")) - before
    rows = _rows()
    assert sent == 1 and len(rows) == sent, rows   # one row per real request
    assert rows[0]["route_reason"] == "read_timeout"
    _assert_estimated(rows[0])
    # The failure itself stays visible — under no paid provider's name.
    (summary,) = _rows(provider="gateway")
    assert summary["route_reason"] == "all_failed"
    assert (summary["prompt_tokens"], summary["completion_tokens"]) == (0, 0)


def test_auxiliary_failure_is_estimated(wire):
    out = gw.aux_generate(_provider(wire, "silent_hold", timeout=1), PROMPT,
                          options={}, tier="classifier", breaker=None)
    assert out is None
    (row,) = _rows()
    assert row["tier"] == "classifier" and row["ok"] == 0
    _assert_estimated(row)


def test_a_refused_request_is_an_explicit_flagged_zero(wire):
    """HTTP 402/400…: DeepSeek generated nothing. Zero — but said so."""
    g = gw.AIGateway(provider=_provider(wire, "http_402"))
    _drain(g.stream(PROMPT))   # falls back to the local model
    (row,) = _rows()
    assert row["route_reason"] == "http_402"
    assert (row["prompt_tokens"], row["completion_tokens"]) == (0, 0)
    assert row.get("usage_estimated") == 1


@pytest.mark.parametrize("scenario", [
    "error_midstream", "error_event_midstream", "reset_midstream",
    "clean_close_no_done", "close_no_content", "finish_insufficient",
    "error_200_json", "eof_no_chunk_end", "http_503", "http_400",
])
def test_no_failure_leaves_a_paid_row_without_tokens(wire, scenario):
    g = gw.AIGateway(provider=_provider(wire, scenario))
    _drain(g.stream(PROMPT))
    rows = _rows()
    assert rows, "a paid attempt must be a row"
    for row in rows:
        assert row["prompt_tokens"] is not None and row["completion_tokens"] is not None, row
        if row.get("usage_estimated") != 1:   # then it is what the fake reported
            assert row["prompt_tokens"] == 17, row


# ── the shared recorder for callers outside the gateway ────────────────────

class _FakeCompletions:
    def __init__(self, outcome):
        self.outcome, self.calls = outcome, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _client(outcome, base_url="https://api.deepseek.com"):
    completions = _FakeCompletions(outcome)
    return types.SimpleNamespace(
        base_url=httpx.URL(base_url + "/"),
        chat=types.SimpleNamespace(completions=completions),
    ), completions


def _response(content, usage=(11, 4)):
    msg = types.SimpleNamespace(content=content)
    u = None if usage is None else types.SimpleNamespace(prompt_tokens=usage[0],
                                                         completion_tokens=usage[1])
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=u)


@pytest.fixture
def tdb(monkeypatch, tmp_path):
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "sessions.db")
    return tmp_path / "sessions.db"


def test_recorder_writes_the_reported_usage(tdb):
    resp = _response('{"درجة": "صلة"}')
    client, comp = _client(resp)
    out = gw.record_chat_completion(
        client, tier="kb_gap_judge", model="deepseek-chat",
        messages=[{"role": "user", "content": PROMPT}], temperature=0, max_tokens=200)
    assert out is resp
    # The legacy name goes out as its documented successor (2026-10-08).
    assert comp.calls[0]["model"] == "deepseek-flash" and comp.calls[0]["max_tokens"] == 200
    (row,) = _rows(tdb)
    assert row["model"] == "deepseek-flash" and row["tier"] == "kb_gap_judge"
    assert (row["prompt_tokens"], row["completion_tokens"], row["ok"]) == (11, 4, 1)
    assert row["usage_estimated"] == 0 and row["streamed"] == 0


def test_recorder_estimates_a_response_without_usage(tdb):
    client, _ = _client(_response("جواب", usage=None))
    gw.record_chat_completion(client, tier="eval_judge", model="deepseek-chat",
                              messages=[{"role": "user", "content": PROMPT}])
    (row,) = _rows(tdb)
    assert row["ok"] == 1
    _assert_estimated(row, min_completion=1)


def test_recorder_records_a_failure_and_reraises(tdb):
    client, _ = _client(httpx.ReadTimeout("slow"))
    with pytest.raises(httpx.ReadTimeout):
        gw.record_chat_completion(client, tier="kb_gap_judge", model="deepseek-chat",
                                  messages=[{"role": "user", "content": PROMPT}])
    (row,) = _rows(tdb)
    assert row["ok"] == 0 and row["route_reason"] == "read_timeout"
    _assert_estimated(row)


@pytest.mark.parametrize("base_url,label", [
    ("https://api.deepseek.com", "deepseek"),
    ("https://api.deepseek.com/v1", "deepseek"),
    ("https://ollama.com/v1", "ollama_cloud"),
    ("http://127.0.0.1:11434/v1", "ollama"),
])
def test_recorder_names_the_provider_by_its_host(tdb, base_url, label):
    client, _ = _client(_response("x"), base_url=base_url)
    gw.record_chat_completion(client, tier="t", model="m",
                              messages=[{"role": "user", "content": "x"}])
    assert _rows(tdb, provider=None)[0]["provider"] == label


def test_recorder_telemetry_failure_never_breaks_the_call(monkeypatch, tmp_path):
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    monkeypatch.setattr(gw, "_TELEMETRY_DB", blocked / "sessions.db")
    resp = _response("x")
    client, _ = _client(resp)
    assert gw.record_chat_completion(client, tier="t", model="m",
                                     messages=[{"role": "user", "content": "x"}]) is resp


# ── schema ─────────────────────────────────────────────────────────────────

def test_usage_flag_is_a_numbered_migration(tmp_path):
    path = tmp_path / "fresh.db"
    with sqlite3.connect(path) as c:
        gw._ensure_telemetry_schema(c)
        versions = c.execute("SELECT version, name FROM schema_migrations "
                             "WHERE namespace='llm_telemetry' ORDER BY version").fetchall()
        cols = {r[1]: r for r in c.execute("PRAGMA table_info(llm_calls)")}
    assert versions == [(1, "llm_calls"), (2, "usage_estimated")]
    assert cols["usage_estimated"][2].upper() == "INTEGER"
    assert cols["usage_estimated"][3] == 1 and cols["usage_estimated"][4] == "0"


def test_a_v1_store_keeps_its_rows_and_unknowns_stay_unknown(tmp_path):
    from app.db.migrations.runner import apply_migrations
    from app.db.migrations.telemetry_0001_llm_calls import MIGRATION
    path = tmp_path / "v1.db"
    with sqlite3.connect(path) as c:
        apply_migrations(c, "llm_telemetry", (MIGRATION,))
        c.execute("INSERT INTO llm_calls(ts,provider,model,prompt_tokens,completion_tokens,ok) "
                  "VALUES('2026-10-01 19:37:56','deepseek','deepseek-chat',NULL,NULL,0)")
    with sqlite3.connect(path) as c:
        gw._ensure_telemetry_schema(c)
        row = c.execute("SELECT ts,prompt_tokens,completion_tokens,usage_estimated "
                        "FROM llm_calls").fetchone()
    # History is not rewritten: an old NULL is still "unknown", not "estimated".
    assert row == ("2026-10-01 19:37:56", None, None, 0)
