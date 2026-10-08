"""No paid DeepSeek call outside the recorded path.

October 2026: the weekly VPS cron (weekly_kb_gap_report → kb_gap_judge) judged
196 pairs on DEEPSEEK_API_KEY while llm_calls held 30 DeepSeek rows for that
window — the judge called the API with its own OpenAI client and wrote nothing.
feedback_auto_fix.py did the same (dead code), and the laptop/CI tools
(eval_answers, generate_dataset_v2, ingest_pdf) accept the same key.

Two guards:
  * behaviour — each caller, given a fake client, writes llm_calls rows;
  * structure — a scan of the tree: a file may name DeepSeek's host or key
    only from ALLOWED below, and only the gateway may send a chat-completion
    request itself; everyone else goes through
    ai_gateway.record_chat_completion (or the gateway proper).
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
import types
from pathlib import Path

import httpx
import pytest

from app.services import ai_gateway as gw

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "ops" / "tools"
needs_tools = pytest.mark.skipif(not TOOLS.is_dir(),
                                 reason="ops/tools not present (backend-only image)")

# Files allowed to name DeepSeek's host or key, and why. A new entry is a
# review decision: it must either be configuration/prose, or send its requests
# through record_chat_completion / the gateway (enforced below).
ALLOWED = {
    "backend/app/config/llm_config.py": "configuration read by the gateway",
    "backend/app/services/ai_gateway.py": "the recorded path itself",
    "backend/app/services/cloud_budget.py": "billing-profile table keyed by DeepSeek's origin; "
                                            "sends no requests",
    "ops/tools/kb_gap_judge.py": "record_chat_completion",
    "ops/tools/eval_answers.py": "record_chat_completion",
    "ops/tools/generate_dataset_v2.py": "record_chat_completion",
    "ops/tools/ingest_pdf.py": "record_chat_completion",
    "ops/tools/golden_ci.py": "credential preflight only; calls go through the gateway "
                              "and eval_answers",
    "ops/tools/feedback_digest.py": "docstring; calls go through get_gateway()",
    "ops/scripts/weekly_kb_gap_report.py": "docstring; runs kb_gap_judge.py",
    "ops/tools/deploy_gate.py": "stdlib copy of the price table and model aliases for the "
                                "--check-env preflight; sends no requests",
}
# Files that send chat-completion requests themselves but never to DeepSeek's
# wallet: Ollama Cloud (its own key) or Azure. They must not name DeepSeek.
OTHER_PROVIDERS = {
    "ops/tools/check_quoted_texts.py": "Ollama Cloud",
    "ops/tools/review_en_parity.py": "Ollama Cloud",
    "ops/tools/translate_curriculum.py": "Ollama Cloud",
    "ops/tools/build_golden_set.py": "Azure",
}
GATEWAY = "backend/app/services/ai_gateway.py"

DEEPSEEK = re.compile(r"api\.deepseek\.com|deepseek_api_key", re.I)
RAW_CALL = re.compile(r"chat\.completions\.create\b|/chat/completions")
CODE = re.compile(r"\.(py|sh|js|mjs|ts|dart|ya?ml)$")
SKIP = re.compile(r"(^|/)tests?/|^knowledge_base/|node_modules/")


def _code_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        out = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()]
    return [f for f in out if CODE.search(f) and not SKIP.search(f) and (ROOT / f).is_file()]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def test_only_allowlisted_files_name_deepseeks_host_or_key():
    offenders = sorted(f for f in _code_files() if DEEPSEEK.search(_text(f)) and f not in ALLOWED)
    assert not offenders, (
        "These files reach for DeepSeek outside the recorded path. Send the call "
        "through ai_gateway.record_chat_completion (or the gateway) and add the "
        f"file to ALLOWED with the reason: {offenders}")


def test_only_the_gateway_sends_chat_completions_itself():
    offenders = sorted(f for f in _code_files()
                       if RAW_CALL.search(_text(f)) and f != GATEWAY and f not in OTHER_PROVIDERS)
    assert not offenders, (
        "Raw chat-completion requests bypass llm_calls. Use "
        f"ai_gateway.record_chat_completion: {offenders}")


def test_other_provider_files_never_touch_deepseek():
    for f in OTHER_PROVIDERS:
        if (ROOT / f).is_file():
            assert not DEEPSEEK.search(_text(f)), f"{f} is allowlisted as not-DeepSeek"


def test_allowlisted_callers_use_the_recorder():
    for f, why in ALLOWED.items():
        if why == "record_chat_completion" and (ROOT / f).is_file():
            assert "record_chat_completion(" in _text(f), f


def test_the_dead_direct_caller_is_gone():
    assert not (ROOT / "backend/app/services/feedback_auto_fix.py").exists()


def test_the_guard_still_sees():
    """A guard that scans nothing passes everything."""
    files = _code_files()
    assert GATEWAY in files and "ops/tools/kb_gap_judge.py" in files
    assert DEEPSEEK.search(_text("backend/app/config/llm_config.py"))
    assert RAW_CALL.search(_text(GATEWAY))


# ── behaviour: the callers write rows ──────────────────────────────────────

class _FakeOpenAI:
    """Stands in for openai.OpenAI: same attributes the callers touch."""
    instances: list["_FakeOpenAI"] = []
    reply = '{"درجة": "صلة", "سبب": "يعالج السؤال"}'

    def __init__(self, api_key=None, base_url=None, **kw):
        self.base_url = httpx.URL((base_url or "https://api.deepseek.com").rstrip("/") + "/")
        self.calls: list[dict] = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))
        _FakeOpenAI.instances.append(self)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        msg = types.SimpleNamespace(content=self.reply)
        usage = types.SimpleNamespace(prompt_tokens=40, completion_tokens=12)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=usage)


@pytest.fixture
def tdb(monkeypatch, tmp_path):
    monkeypatch.setattr(gw, "_TELEMETRY_DB", tmp_path / "sessions.db")
    _FakeOpenAI.instances = []
    return tmp_path / "sessions.db"


def _rows(db):
    if not db.exists():
        return []
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT * FROM llm_calls ORDER BY id")]
    finally:
        con.close()


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_recorded_{name}", TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@needs_tools
def test_kb_gap_judge_on_deepseek_writes_a_row_per_request(tdb, monkeypatch, tmp_path):
    judge = _load("kb_gap_judge")
    monkeypatch.setattr(judge, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-placeholder")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    pairs = [{"question": f"سؤال {i}", "age_group": "4-6",
              "units": [{"text": "نص", "domain": "d", "reference": "r", "rerank": 0.5}]}
             for i in range(3)]
    inp, out = tmp_path / "pairs.json", tmp_path / "judged.json"
    inp.write_text(json.dumps(pairs, ensure_ascii=False), encoding="utf-8")
    assert judge.main(["--in", str(inp), "--out", str(out), "--quiet", "--concurrency", "2"]) == 0
    requests = sum(len(c.calls) for c in _FakeOpenAI.instances)
    rows = _rows(tdb)
    assert requests == 4 and len(rows) == requests          # preflight + 3 pairs
    assert {r["provider"] for r in rows} == {"deepseek"}
    assert {r["tier"] for r in rows} == {"kb_gap_judge"}
    assert all((r["prompt_tokens"], r["completion_tokens"], r["usage_estimated"]) == (40, 12, 0)
               for r in rows)


@needs_tools
def test_eval_judge_writes_a_row(tdb):
    ev = _load("eval_answers")
    client = _FakeOpenAI(base_url="https://api.deepseek.com")
    item = {"question": "س", "age_group": "4-6", "severity": "low",
            "reply_text": "ج", "retrieved_chunks": []}
    assert ev._judge(client, "deepseek-chat", item)["درجة"] == "صلة"
    (row,) = _rows(tdb)
    assert (row["provider"], row["tier"], row["prompt_tokens"]) == ("deepseek", "eval_judge", 40)


@needs_tools
def test_dataset_generator_writes_a_row(tdb, monkeypatch):
    gen = _load("generate_dataset_v2")
    monkeypatch.setattr(gen, "BACKEND", "deepseek")
    client = _FakeOpenAI(base_url="https://api.deepseek.com")
    assert gen.chat(client, "deepseek-chat", "اكتب") == _FakeOpenAI.reply
    (row,) = _rows(tdb)
    assert (row["provider"], row["tier"]) == ("deepseek", "dataset_v2")


@needs_tools
def test_pdf_ingest_writes_a_row(tdb, monkeypatch):
    ing = _load("ingest_pdf")
    import openai
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(ing, "DEEPSEEK_BASE", "https://api.deepseek.com")
    ing.call_deepseek("مقطع")
    (row,) = _rows(tdb)
    assert (row["provider"], row["tier"]) == ("deepseek", "ingest_pdf")


# ── reserved, not only recorded: batch writers on the capped wallet ────────
# A recorded-but-unreserved call is invisible to the cap's ledger: the weekly
# VPS judge would spend from the same wallet after activation and the cap
# would never see it. So record_chat_completion reserves (and settles)
# exactly like the gateway whenever the request goes to DeepSeek's wallet.
from app.services import cloud_budget as cb  # noqa: E402
from tests.budget_test_helpers import activate  # noqa: E402

WALLET = "cloud:https://api.deepseek.com:443"


def _attempts(db):
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT charged_tokens, settled FROM cloud_budget_attempts ORDER BY rowid").fetchall()


@pytest.fixture
def capped(monkeypatch, tmp_path):
    db = tmp_path / "sessions.db"
    monkeypatch.setattr(gw, "_TELEMETRY_DB", db)
    monkeypatch.setattr(gw, "_telemetry_schema_ready", False)
    monkeypatch.setattr(gw, "LLM", dataclasses.replace(
        gw.LLM, primary_provider="deepseek", deepseek_primary_monthly_token_cap=10 * 1048576,
        deepseek_billing_profile_aliases=(("deepseek-chat", "deepseek-flash"),),
        cloud_budget_enforce=True))
    _FakeOpenAI.instances = []
    return db


def _ask(client, **kw):
    return gw.record_chat_completion(client, tier="kb_gap_judge", model="deepseek-chat",
                                     messages=[{"role": "user", "content": "سؤال"}], **kw)


def test_recorder_reserves_and_settles_reported_usage(capped):
    activate(cb.CloudBudget(capped), wallets=(WALLET,))
    _ask(_FakeOpenAI(), max_tokens=200)
    assert _attempts(capped) == [(52, 1)]


def test_recorder_is_denied_before_the_wire_without_activation(capped):
    client = _FakeOpenAI()
    with sqlite3.connect(capped) as conn:   # history exists, cutover does not
        gw._ensure_telemetry_schema(conn)
    with pytest.raises(cb.BudgetDenied):
        _ask(client, max_tokens=200)
    assert client.calls == []
    (row,) = _rows(capped)
    assert (row["route_reason"], row["prompt_tokens"], row["completion_tokens"]) == ("budget_denied", 0, 0)


def test_recorder_requires_a_bounded_max_tokens_on_the_capped_wallet(capped):
    activate(cb.CloudBudget(capped), wallets=(WALLET,))
    client = _FakeOpenAI()
    with pytest.raises(cb.BudgetDenied):
        _ask(client)
    assert client.calls == []


def test_recorder_failure_settles_to_the_request_bound(capped):
    activate(cb.CloudBudget(capped), wallets=(WALLET,))
    client = _FakeOpenAI()

    def boom(**kwargs):
        client.calls.append(kwargs)
        raise httpx.ReadTimeout("slow")

    client.chat.completions.create = boom
    with pytest.raises(httpx.ReadTimeout):
        _ask(client, max_tokens=200)
    [(charged, settled)] = _attempts(capped)
    assert settled == 1 and 200 < charged < 1048576


def test_recorder_disables_hidden_sdk_retries_on_the_capped_wallet(capped):
    activate(cb.CloudBudget(capped), wallets=(WALLET,))
    seen = []

    class WithOptions(_FakeOpenAI):
        def with_options(self, **kw):
            seen.append(kw)
            return self

    _ask(WithOptions(), max_tokens=200)
    assert seen == [{"max_retries": 0}], "an SDK retry is a second wire attempt under one reservation"


def test_recorder_leaves_other_wallets_alone(capped):
    client = _FakeOpenAI(base_url="https://ollama.com/v1")
    gw.record_chat_completion(client, tier="t", model="m", messages=[{"role": "user", "content": "x"}])
    assert len(client.calls) == 1   # no ledger, no denial: not DeepSeek's wallet


def test_recorder_row_maps_to_its_attempt(capped):
    activate(cb.CloudBudget(capped), wallets=(WALLET,))
    _ask(_FakeOpenAI(), max_tokens=200)
    with sqlite3.connect(capped) as conn:
        [(call_id,)] = conn.execute("SELECT rowid FROM llm_calls").fetchall()
        [(attempt,)] = conn.execute("SELECT id FROM cloud_budget_attempts").fetchall()
        assert conn.execute("SELECT call_id, reservation_id FROM llm_call_reservations").fetchall() == \
            [(call_id, attempt)]
