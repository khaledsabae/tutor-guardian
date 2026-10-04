"""The DeepSeek wire, against a simulated server on a real socket.

PR #24 review, round 2 (R1–R8): the provider reads DeepSeek's SSE itself, so
what the OpenAI SDK used to handle — framing, retries, finish reasons, the
end of the stream — is ours now. tests/fake_deepseek.py (from the review's
probes) speaks the protocol byte by byte: keep-alive holds, CRLF, a UTF-8
character split across writes, U+2028 inside JSON, 429/503 with and without
Retry-After, resets, 200s that are not event streams, every finish_reason.
"""
from __future__ import annotations

import dataclasses
import logging
import sqlite3
import threading
import time

import pytest

from app.config import llm_config
from app.services import ai_gateway as gw
from tests import fake_deepseek as fk


@pytest.fixture(scope="module")
def server():
    srv, url = fk.start()
    yield url
    srv.shutdown()


@pytest.fixture
def wire(server, monkeypatch, tmp_path):
    """Telemetry to a temp DB, the local chain pointed at the fake Ollama."""
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "sessions.db")
    monkeypatch.setattr(gw, "_telemetry_schema_ready", False)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        llm_config.LLM, base_url=server, local_base_url=server,
        local_fast_model="local_ok", local_fallback_model="local_ok", fallback_model="local_ok",
        deepseek_fallback_enabled=False, cloud_tier_enabled=False,
    ))
    monkeypatch.setattr(gw, "primary_budget_available", lambda name: True)
    # raising=False: on code without the fix these names do not exist, and
    # the tests must fail on behaviour, not in this fixture.
    monkeypatch.setattr(gw, "_MODEL_SWITCHED", {}, raising=False)
    monkeypatch.setattr(gw, "_NO_THINKING_FIELD", set(), raising=False)
    gw.primary_breaker.reset()
    yield server
    gw.primary_breaker.reset()


def _provider(url, scenario, timeout=5, **kw):
    return gw.OpenAIChatProvider(base_url=url, api_key="test-placeholder", model=scenario,
                                 timeout=timeout, name="deepseek", **kw)


def _requests(scenario):
    with fk._LOCK:
        return [e for e in fk.CONN_LOG if e["scenario"] == scenario]


def _rows(tmp_db):
    con = sqlite3.connect(tmp_db)
    try:
        return con.execute("SELECT provider, model, prompt_tokens, completion_tokens, ok, "
                           "route_reason FROM llm_calls ORDER BY id").fetchall()
    finally:
        con.close()


def _drain(chunks):
    out, final, err = [], None, None
    try:
        for ch in chunks:
            if ch.done:
                final = ch.result
            else:
                out.append(ch.delta)
    except Exception as e:  # noqa: BLE001
        err = e
    return "".join(out), final, err


def _text(provider):
    return "".join(c["response"] for c in provider.stream("س", options={}) if not c["done"])


# ── R4: framing ────────────────────────────────────────────────────────────

def test_unicode_line_separators_inside_json_are_kept(wire):
    """R4 — iter_lines() also split on U+2028/U+2029/U+0085, which JSON allows
    raw inside a string: the rest of that token was dropped."""
    assert _text(_provider(wire, "u2028")) == "سطر أول سطر ثان و\u0085نهاية"


def test_a_multi_line_data_event_is_joined(wire):
    assert _text(_provider(wire, "multiline_data")) == "قبل وسط بعد"


def test_crlf_and_a_character_split_across_writes(wire):
    assert _text(_provider(wire, "crlf")) == "أب"
    assert _text(_provider(wire, "utf8_split")) == "سلام عليكم ورحمة"


def test_unparseable_data_is_logged(wire, caplog):
    caplog.set_level(logging.WARNING, logger="app.services.ai_gateway")
    assert _text(_provider(wire, "empty_data_lines")) == "أب"
    assert "unparseable" in caplog.text


# ── R5: the connection is reused ───────────────────────────────────────────

def test_connections_are_reused_across_streams(wire):
    """R5 — stopping at [DONE] left the chunked terminator unread, so every
    call paid a new connection (and TLS handshake)."""
    p = _provider(wire, "normal")
    before = len(fk.CONN_LOG)
    for _ in range(4):
        assert _text(p) == "مرحبًا بك، كيف أساعدك؟"
        time.sleep(0.05)
    new = [e for e in fk.CONN_LOG[before:] if e["scenario"] == "normal"]
    assert len({e["conn_id"] for e in new}) == 1


# ── R3: finish reasons and malformed endings ───────────────────────────────

@pytest.mark.parametrize("scenario", [
    "finish_insufficient", "finish_content_filter", "error_200_json", "close_no_content",
])
def test_no_answer_falls_back_to_the_next_provider(wire, scenario):
    """R3 — an empty answer (insufficient_system_resource, content_filter, a
    200 that is not an event stream, a close with nothing) counted as a
    success: an empty reply was stored and sent, and the breaker was told
    DeepSeek was fine."""
    gw.primary_breaker.record(False)  # one earlier failure on record
    g = gw.AIGateway(provider=_provider(wire, scenario))
    text, final, err = _drain(g.stream("س"))
    assert err is None
    assert text == "رد محلي احتياطي."             # the local fallback answered
    assert gw.primary_breaker._consecutive_failures == 2


def test_truncated_answer_is_flagged_never_silent(wire):
    """R3 — finish_reason=length is a usable but incomplete answer: it is
    returned, flagged, and (assistant side) never cached."""
    g = gw.AIGateway(provider=_provider(wire, "finish_length"))
    text, final, err = _drain(g.stream("س"))
    assert err is None and text == "جواب مقطوع في"
    assert final.truncated == "length"
    assert ("deepseek", "deepseek-flash", 17, 9, 1, "truncated:length") in _rows(gw._TELEMETRY_DB)


def test_stream_ending_without_done_is_an_error(wire):
    with pytest.raises(gw.ProviderStreamError, match="without \\[DONE\\]"):
        _text(_provider(wire, "clean_close_no_done"))


def test_every_paid_generate_attempt_is_a_row(wire, monkeypatch):
    """R3 — empty answers were retried three times (three paid requests) and
    none of them reached llm_calls, which the monthly cap sums."""
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [])
    g = gw.AIGateway(provider=_provider(wire, "finish_insufficient"))
    before = len(_requests("finish_insufficient"))
    with pytest.raises(RuntimeError):
        import asyncio
        asyncio.run(g.generate("س", max_retries=2))
    paid = len(_requests("finish_insufficient")) - before
    attempt_rows = [r for r in _rows(gw._TELEMETRY_DB) if r[0] == "deepseek" and r[5] == "bad_stream"]
    assert paid == 2 and len(attempt_rows) == paid
    # …with the prompt tokens DeepSeek reported for the empty answer.
    assert all(r[2] == 17 for r in attempt_rows)


# ── R2: transient failures before the first byte ──────────────────────────

def test_a_503_blip_is_retried_before_falling_back(wire):
    """R2 — one 503 sent the answer to the weak local model and two opened
    the breaker for 120 s; the SDK used to retry these."""
    g = gw.AIGateway(provider=_provider(wire, "flaky_503"))
    text, final, err = _drain(g.stream("س"))
    assert text == "مرحبًا بك، كيف أساعدك؟"
    assert len(_requests("flaky_503")) == 2
    assert gw.primary_breaker._consecutive_failures == 0


def test_retry_after_is_honoured(wire):
    g = gw.AIGateway(provider=_provider(wire, "flaky_429_retry_after"))
    t0 = time.monotonic()
    text, _, err = _drain(g.stream("س"))
    assert text == "مرحبًا بك، كيف أساعدك؟"
    assert time.monotonic() - t0 >= 1.0


def test_a_reset_before_any_byte_is_retried(wire):
    g = gw.AIGateway(provider=_provider(wire, "flaky_reset"))
    text, _, err = _drain(g.stream("س"))
    assert text == "مرحبًا بك، كيف أساعدك؟"


def test_persistent_503_counts_once_against_the_breaker(wire):
    g = gw.AIGateway(provider=_provider(wire, "http_503"))
    before = len(_requests("http_503"))
    text, _, err = _drain(g.stream("س"))
    assert text == "رد محلي احتياطي."
    assert len(_requests("http_503")) - before == 1 + gw.PRIMARY_PREFLIGHT_RETRIES
    assert gw.primary_breaker._consecutive_failures == 1


def test_retries_never_exceed_the_first_token_budget(wire, monkeypatch):
    monkeypatch.setattr(gw, "PRIMARY_FIRST_TOKEN_S", 0.3)
    g = gw.AIGateway(provider=_provider(wire, "http_503"))
    before = len(_requests("http_503"))
    _drain(g.stream("س"))
    assert len(_requests("http_503")) - before == 1  # a 0.5 s back-off does not fit


def test_error_body_is_in_the_error(wire):
    """R2 — 402 Insufficient Balance and 400 Model Not Exist were logged as
    a bare status."""
    with pytest.raises(gw.ProviderHTTPError, match="Insufficient Balance"):
        _text(_provider(wire, "http_402"))


# ── R7: a silent provider is not retried ───────────────────────────────────

def test_read_timeout_is_not_retried(wire, monkeypatch):
    """R7 — a silent DeepSeek (no keep-alives) hit the 60 s read timeout and
    was tried again: 120 s of a 150 s budget gone before the fallback."""
    monkeypatch.setattr(llm_config.LLMConfig, "fallback_chain", lambda self: [
        {"name": "local_fast", "url": wire, "model": "local_ok", "timeout": 5}])
    g = gw.AIGateway(provider=_provider(wire, "silent_hold", timeout=1))
    before = len(_requests("silent_hold"))
    import asyncio
    result = asyncio.run(g.generate("س", max_retries=3))
    assert result.text == "رد محلي احتياطي."
    assert len(_requests("silent_hold")) - before == 1


# ── R6: the provider's own abort keeps its message ─────────────────────────

def test_provider_abort_is_not_relabelled():
    def held():
        raise gw.LLMDeadlineExceeded("deepseek: no first token after 30s")

    with pytest.raises(gw.LLMDeadlineExceeded, match="no first token after 30s"):
        gw.call_with_deadline(held, 5, lane=gw.AUX_LANE)


# ── R8: thinking off, served model logged, retired model switched ─────────

def test_thinking_is_disabled_and_the_served_model_logged(wire):
    g = gw.AIGateway(provider=_provider(wire, "normal"))
    text, final, _ = _drain(g.stream("س"))
    assert _requests("normal")[-1]["body"]["thinking"] == {"type": "disabled"}
    assert final.model == "deepseek-flash"          # what DeepSeek says served it
    assert _rows(gw._TELEMETRY_DB)[-1][1] == "deepseek-flash"


def test_a_refused_model_switches_to_the_fallback_for_the_process(wire, caplog):
    """R8 — production runs deepseek-chat, a name DeepSeek's docs list as
    retired. When it is refused, switch once, loudly, and stay switched."""
    caplog.set_level(logging.ERROR, logger="app.services.ai_gateway")
    p = _provider(wire, "http_400", fallback_model="normal")
    assert _text(p) == "مرحبًا بك، كيف أساعدك؟"
    assert "refused model" in caplog.text
    before = len(_requests("http_400"))
    assert _text(_provider(wire, "http_400", fallback_model="normal")) == "مرحبًا بك، كيف أساعدك؟"
    assert len(_requests("http_400")) == before  # remembered: not asked again


def test_a_host_without_the_thinking_field_is_asked_without_it(wire):
    p = _provider(wire, "no_thinking_field")
    assert _text(p) == "مرحبًا بك، كيف أساعدك؟"
    assert "thinking" not in _requests("no_thinking_field")[-1]["body"]


# ── R1: a cut turn stops the wire and never reaches a fallback ─────────────

def test_cut_turn_closes_the_request_and_starts_no_fallback(wire, monkeypatch):
    """R1 — the gateway never saw the cancel: a Stop during a DeepSeek hold
    still waited the 30 s first-token limit, then STARTED the local fallback
    for a turn nobody wanted."""
    monkeypatch.setattr(gw, "PRIMARY_FIRST_TOKEN_S", 2.0)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(gw.LLM, local_fast_model="local_slow:3",
                                                       local_fallback_model="local_slow:3",
                                                       fallback_model="local_slow:3"))
    cut = threading.Event()
    g = gw.AIGateway(provider=_provider(wire, "hold_long", timeout=60))
    before_local = len(_requests("local_slow:3"))
    threading.Timer(0.3, cut.set).start()
    t0 = time.monotonic()
    text, _, err = _drain(g.stream("س", should_stop=cut.is_set))
    assert isinstance(err, gw.LLMCancelled)
    assert time.monotonic() - t0 < 1.5
    time.sleep(0.3)
    held = _requests("hold_long")[-1]
    assert held["closed_by_client_at"] is not None
    assert len(_requests("local_slow:3")) == before_local  # no fallback for a dead turn


def test_mid_answer_hold_on_the_primary_is_aborted(wire, monkeypatch):
    """R1 — the primary stream had a first-token limit only: a hold after
    the first tokens was never aborted."""
    monkeypatch.setattr(gw, "PRIMARY_STALL_S", 1.0)
    g = gw.AIGateway(provider=_provider(wire, "tokens_then_keepalive_hold"))
    t0 = time.monotonic()
    text, _, err = _drain(g.stream("س"))
    assert text == "بداية "
    assert isinstance(err, gw.LLMDeadlineExceeded)
    assert time.monotonic() - t0 < 3.0
