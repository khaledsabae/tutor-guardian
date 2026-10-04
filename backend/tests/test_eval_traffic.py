"""Eval traffic is marked, and the eval harness never writes to the live DB.

The 2026-09-24 baseline ran inside the production container, where
CONVERSATIONS_DB is the production database; the harness only `setdefault`-ed
its own path, so 92 eval sessions went into production. These tests pin both
halves of the fix: the marker other scripts import, and the forced isolation.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.core.eval_traffic import EVAL_DEVICE_LIKE, EVAL_DEVICE_PREFIX, is_eval_device

ROOT = Path(__file__).resolve().parents[2]


def test_marker():
    assert is_eval_device(f"{EVAL_DEVICE_PREFIX}real-12")
    assert not is_eval_device("3f2b8c1e-0000-4000-8000-000000000000")
    assert not is_eval_device(None) and not is_eval_device("")
    assert EVAL_DEVICE_LIKE == EVAL_DEVICE_PREFIX + "%"


def test_harness_names_devices_with_the_shared_marker():
    src = (ROOT / "ops" / "tools" / "eval_answers.py").read_text(encoding="utf-8")
    assert "EVAL_DEVICE_PREFIX" in src
    assert '"eval-harness-' not in src and "f\"eval-harness-" not in src


def test_harness_never_runs_against_the_configured_database(monkeypatch, tmp_path):
    import ops.tools.eval_answers as ev

    live = tmp_path / "production.db"
    monkeypatch.setenv("CONVERSATIONS_DB", str(live))
    monkeypatch.setenv("ANSWER_CACHE_ENABLED", "true")
    monkeypatch.setenv("ANSWER_CACHE_DB", str(tmp_path / "prod_cache.db"))
    throwaway = tmp_path / "eval.db"
    assert ev.run_pipeline([], "pytest", db=str(throwaway)) == []
    assert os.environ["CONVERSATIONS_DB"] == str(throwaway)
    assert os.environ["ANSWER_CACHE_ENABLED"] == "false"
    assert not live.exists()

    # Without --db it still refuses the configured path.
    ev.run_pipeline([], "pytest2")
    assert os.environ["CONVERSATIONS_DB"] != str(live)
    Path(os.environ["CONVERSATIONS_DB"]).unlink(missing_ok=True)
    assert not live.exists()
