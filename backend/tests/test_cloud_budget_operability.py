"""Operability before anyone enables the cap (re-review of c8597396, P3).

1. Settle never waits on the request path: it settles inline only if the
   ledger is free right now, otherwise a background settler (bounded queue,
   one worker, long retry) takes it; shutdown drains up to a bound and logs
   leftovers as orphans for --settle-orphans.
2. The anchor can live on another volume (CLOUD_BUDGET_ANCHOR_PATH), so a
   single-volume restore is detected.
3. The switch state and the ledger's activation state are visible
   (read-only status, readiness report) and an unrecognised switch value
   fails the deploy preflight.
"""
import dataclasses
import fcntl
import importlib.util
import json
import logging
import shutil
import sqlite3
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from app.config import llm_config
from app.services import ai_gateway as gw
from app.services import cloud_budget as cb
from tests.budget_test_helpers import activate

ROOT = Path(__file__).resolve().parents[2]
WALLET = "cloud:https://api.deepseek.com:443"


def _sse():
    obj = {"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}],
           "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    return ("data: " + json.dumps(obj) + "\n\ndata: [DONE]\n\n").encode()


@pytest.fixture
def capped(monkeypatch, tmp_path):
    monkeypatch.setattr(cb, "_BILLING_PROFILES", {
        ("https://api.deepseek.com:443", "test-model"): cb.BillingProfile(1048576, 4096)})
    db = tmp_path / "sessions.db"
    monkeypatch.setattr(gw, "_TELEMETRY_DB", db)
    monkeypatch.setattr(gw, "_telemetry_schema_ready", False)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        llm_config.LLM, primary_provider="deepseek", deepseek_primary_monthly_token_cap=10 * 1048576,
        cloud_budget_enforce=True, cloud_budget_anchor_path=""))
    activate(cb.CloudBudget(db), wallets=(WALLET,))
    yield db
    cb.SETTLER.flush(timeout=30)


def _provider(handler):
    return gw.OpenAIChatProvider("https://api.deepseek.com", "test-key", "test-model", 5, name="deepseek",
                                 http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def _attempts(db):
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT charged_tokens, settled FROM cloud_budget_attempts ORDER BY rowid").fetchall()


def _grab(ledger, seconds):
    """A stuck holder: another process holding the ledger's flock."""
    lock = open(str(ledger.anchor_path) + ".lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    threading.Timer(seconds, lock.close).start()


# ── 1. settle off the request path ─────────────────────────────────────────
def test_uncontended_settle_lands_inline(capped):
    assert _provider(lambda r: httpx.Response(200, headers={"content-type": "text/event-stream"},
                                              content=_sse())).generate("س", options={"num_predict": 100})
    assert _attempts(capped) == [(7, 1)]


def test_request_finishes_on_time_while_a_stuck_holder_has_the_ledger(capped):
    ledger = cb.CloudBudget(capped)

    def handler(request):
        _grab(ledger, 2.0)                     # grabbed after reserve, before settle
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=_sse())

    started = time.monotonic()
    assert _provider(handler).generate("س", options={"num_predict": 100})["response"] == "answer"
    assert time.monotonic() - started < 1.0, "settle must not hold the request"
    assert _attempts(capped) == [(1048576, 0)]   # queued, not lost
    assert cb.SETTLER.flush(timeout=30)
    assert _attempts(capped) == [(7, 1)]


def test_shutdown_drain_is_bounded_and_names_orphans(capped, caplog):
    ledger = cb.CloudBudget(capped)
    settler = cb.BackgroundSettler(maxsize=10)
    t = ledger.reserve(WALLET, 10 * 1048576, 1048576, legacy_aliases=cb.PAID_ALIASES,
                       unknown_usage_bounds=(10, 10))
    _grab(ledger, 3.0)
    settler.submit(ledger, t, 5, 2)
    started = time.monotonic()
    with caplog.at_level(logging.ERROR, logger="app.services.cloud_budget"):
        left = settler.drain(timeout=0.3)
    assert time.monotonic() - started < 1.5
    assert left == [t.id] and "--settle-orphans" in caplog.text


def test_a_full_queue_leaves_a_logged_orphan_not_a_blocked_request(capped, caplog):
    ledger = cb.CloudBudget(capped)
    settler = cb.BackgroundSettler(maxsize=1)
    tickets = [ledger.reserve(WALLET, 10 * 1048576, 1048576, legacy_aliases=cb.PAID_ALIASES)
               for _ in range(3)]
    _grab(ledger, 2.0)
    started = time.monotonic()
    with caplog.at_level(logging.ERROR, logger="app.services.cloud_budget"):
        accepted = [settler.submit(ledger, t, 1, 1) for t in tickets]
    assert time.monotonic() - started < 0.5
    assert accepted.count(False) >= 1 and "--settle-orphans" in caplog.text
    settler.flush(timeout=30)


# ── 2. anchor on another volume ────────────────────────────────────────────
def test_default_anchor_stays_next_to_the_db(tmp_path):
    led = cb.CloudBudget(tmp_path / "sessions.db")
    assert led.anchor_path == (tmp_path / "sessions.db.cloud-budget-anchor").resolve()


def test_configured_anchor_lives_elsewhere(tmp_path):
    (tmp_path / "ops").mkdir()
    (tmp_path / "witness").mkdir()
    db, anchor = tmp_path / "ops" / "sessions.db", tmp_path / "witness" / "tg.anchor"
    led = activate(cb.CloudBudget(db, anchor_path=anchor), wallets=("w",))
    led.reserve("w", 10**9, 1, legacy_aliases=("deepseek",))
    assert anchor.is_file() and not Path(str(db) + ".cloud-budget-anchor").exists()
    assert list((tmp_path / "ops").glob("*anchor*")) == []


def test_restoring_only_the_db_volume_is_detected_with_a_separate_anchor(tmp_path):
    (tmp_path / "ops").mkdir()
    (tmp_path / "witness").mkdir()
    db, anchor = tmp_path / "ops" / "sessions.db", tmp_path / "witness" / "tg.anchor"
    led = activate(cb.CloudBudget(db, anchor_path=anchor), wallets=("w",))
    shutil.copyfile(db, tmp_path / "backup.db")
    led.reserve("w", 10**9, 100, legacy_aliases=("deepseek",))
    shutil.copyfile(tmp_path / "backup.db", db)          # the DB volume is restored, the anchor's is not
    with pytest.raises(cb.BudgetDenied, match="continuity"):
        led.reserve("w", 10**9, 1, legacy_aliases=("deepseek",))


def test_same_volume_restore_is_why_the_anchor_should_move(tmp_path):
    db = tmp_path / "sessions.db"
    led = activate(cb.CloudBudget(db), wallets=("w",))
    shutil.copyfile(db, tmp_path / "backup.db")
    shutil.copyfile(led.anchor_path, tmp_path / "backup.anchor")
    led.reserve("w", 10**9, 100, legacy_aliases=("deepseek",))
    shutil.copyfile(tmp_path / "backup.db", db)
    shutil.copyfile(tmp_path / "backup.anchor", led.anchor_path)
    assert led.reserve("w", 10**9, 1, legacy_aliases=("deepseek",))   # undetectable by design


def test_gateway_and_cli_use_the_configured_anchor(monkeypatch, tmp_path):
    (tmp_path / "witness").mkdir()
    anchor = tmp_path / "witness" / "tg.anchor"
    monkeypatch.setenv("CLOUD_BUDGET_ANCHOR_PATH", str(anchor))
    assert llm_config.LLMConfig().cloud_budget_anchor_path == str(anchor)
    monkeypatch.delenv("CLOUD_BUDGET_ANCHOR_PATH")
    assert llm_config.LLMConfig().cloud_budget_anchor_path == ""
    db = tmp_path / "sessions.db"
    monkeypatch.setattr(gw, "_TELEMETRY_DB", db)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        llm_config.LLM, primary_provider="deepseek", deepseek_primary_monthly_token_cap=10 * 1048576,
        cloud_budget_enforce=True, cloud_budget_anchor_path=str(anchor)))
    sqlite3.connect(db).close()
    activate(cb.CloudBudget(db), wallets=(WALLET,))     # the helper's receipt, but at the default anchor…
    with pytest.raises(cb.BudgetDenied):                # …which the gateway does not read
        gw._reserve_wire_budget("https://api.deepseek.com", "deepseek", [], 100, model="deepseek-flash")
    (tmp_path / "default").mkdir()
    db2 = tmp_path / "default" / "sessions.db"
    sqlite3.connect(db2).close()
    activate(cb.CloudBudget(db2, anchor_path=anchor), wallets=(WALLET,))
    monkeypatch.setattr(gw, "_TELEMETRY_DB", db2)
    assert gw._reserve_wire_budget("https://api.deepseek.com", "deepseek", [], 100, model="deepseek-flash")
    from app.services import cloud_budget_bootstrap as cli
    assert cli.main(["--db", str(db2), "--anchor", str(anchor), "--list-unknown-rows", "2026-10"]) == 0


# ── 3. visible state ───────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,state", [(None, "off"), ("", "off"), ("off", "off"), ("TRUE", "on"),
                                       ("1", "on"), ("ture", "unrecognised"), ("enable", "unrecognised")])
def test_switch_state_is_three_valued(raw, state):
    assert llm_config.cloud_budget_enforce_state(raw) == state


def test_ledger_status_is_read_only_and_reports_activation(tmp_path):
    db = tmp_path / "sessions.db"
    sqlite3.connect(db).close()
    led = cb.CloudBudget(db)
    before = db.read_bytes()
    status = led.status()
    assert status["activated"] is False and status["anchor_present"] is False
    assert db.read_bytes() == before and not led.anchor_path.exists()
    activate(led, wallets=("w",))
    led.reserve("w", 10**9, 100, legacy_aliases=("deepseek",))
    status = led.status()
    month = led.clock().strftime("%Y-%m")
    assert status["activated"] is True and status["continuity"] is True
    assert status["wallets"]["w"] == {"activated_months": [month], "current_month_activated": True,
                                      "quarantined": False}
    assert status["unsettled_attempts"] == 1
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE cloud_budget_attempts SET charged_tokens=0")
    assert led.status()["continuity"] is False


def _readiness():
    spec = importlib.util.spec_from_file_location("readiness", ROOT / "ops/tools/runtime_readiness_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_readiness_report_shows_switch_and_ledger_state(monkeypatch, tmp_path):
    m = _readiness()
    monkeypatch.setenv("CLOUD_BUDGET_ENFORCE", "ture")
    monkeypatch.setattr(m, "database_report", lambda path, *a: {"path": str(path), "status": "unavailable"})
    r = m.collect_report([])
    budget = r["cloud"]["budget"]
    assert budget["enforce"] == "unrecognised"
    assert budget["anchor_path_configured"] is False
    assert "ledger" in budget and "ture" not in json.dumps(budget)
    assert set(r) == {"version", "collected_at_utc", "crypto_version", "cloud", "session_mint_enforced",
                      "mounts", "telemetry", "conversations"}


def _gate():
    spec = importlib.util.spec_from_file_location("deploy_gate_check", ROOT / "ops/tools/deploy_gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["deploy_gate_check"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("line,code", [("", 0), ("CLOUD_BUDGET_ENFORCE=false\n", 0),
                                       ("CLOUD_BUDGET_ENFORCE=on\n", 0), ('CLOUD_BUDGET_ENFORCE="true"\n', 0),
                                       ("CLOUD_BUDGET_ENFORCE=ture\n", 1),
                                       ("CLOUD_BUDGET_ENFORCE=false\nCLOUD_BUDGET_ENFORCE=maybe\n", 1)])
def test_deploy_preflight_fails_on_an_unrecognised_switch(tmp_path, line, code):
    env = tmp_path / ".env"
    env.write_text("DEEPSEEK_MODEL=deepseek-chat\n" + line)
    assert _gate().main(["--check-env", str(env)]) == code


def test_deploy_preflight_agrees_with_the_app(tmp_path):
    gate = _gate()
    for raw in ["", "0", "no", "off", "OFF", "1", "yes", "on", "True", "ture", "y", "2", " on "]:
        assert gate.cloud_budget_enforce_state(raw) == llm_config.cloud_budget_enforce_state(raw), raw


def test_deploy_runs_the_preflight_before_switching_the_checkout():
    text = (ROOT / ".github/workflows/deploy.yml").read_text()
    check = text.index("--check-env")
    reset = text.index('git reset --hard "$GITHUB_SHA"')
    assert check < reset
    assert 'git show "$GITHUB_SHA:ops/tools/deploy_gate.py"' in text[:check]


@pytest.mark.parametrize("line,code", [
    ("CLOUD_BUDGET_ENFORCE=1 # note", 0),
    ("CLOUD_BUDGET_ENFORCE=off # disabled", 0),
    ('CLOUD_BUDGET_ENFORCE="true" # enabled', 0),
    ("export CLOUD_BUDGET_ENFORCE='off' # disabled", 0),
    ("CLOUD_BUDGET_ENFORCE=\t # empty", 0),
    ('CLOUD_BUDGET_ENFORCE="on # literal"', 1),
    ("CLOUD_BUDGET_ENFORCE='off # literal' # outside", 1),
    ("CLOUD_BUDGET_ENFORCE=on#literal", 1),
    ('CLOUD_BUDGET_ENFORCE="on \\" # literal" # outside', 1),
    ("CLOUD_BUDGET_ENFORCE=ture # typo", 1),
    ("CLOUD_BUDGET_ENFORCE=maybe # old\nCLOUD_BUDGET_ENFORCE=1 # last wins", 0),
])
def test_deploy_preflight_handles_inline_comments(tmp_path, line, code):
    env = tmp_path / ".env"
    env.write_text(line + "\n")
    assert _gate().main(["--check-env", str(env)]) == code


@pytest.mark.parametrize("value,expected", [
    (' "on # literal" # outside', 'on # literal'),
    (" 'off # literal' # outside", 'off # literal'),
    (r''' "on \" # literal" # outside''', r'on \" # literal'),
    (r" 'off \' # literal' # outside", r"off \' # literal"),
])
def test_deploy_preflight_preserves_quoted_hashes(value, expected):
    assert _gate()._env_value(value) == expected
