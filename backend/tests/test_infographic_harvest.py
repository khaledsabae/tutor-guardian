"""scripts/generate_missing_infographics.py — the harvest must finish and remember.

Until 2026-09-29 the task list was saved only after the LAST poll; ~35 dead
tasks outran the cron's `timeout 600` every day, so no drop decision ever
survived. These tests pin: persistence after every poll, a clean budget exit,
and pruning of old / failed / thrice-erroring tasks. No CLI is ever called —
poll() and download() are replaced.
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "generate_missing_infographics.py"


@pytest.fixture
def gmi(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["generate_missing_infographics.py"])
    spec = importlib.util.spec_from_file_location("gmi_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = tmp_path / "ops" / "data"
    monkeypatch.setattr(mod, "STATE_FILE", data / "infographic_tasks.json")
    monkeypatch.setattr(mod, "ERRORS_FILE", data / "infographic_poll_errors.json")
    monkeypatch.setattr(mod, "META_FILE", data / "infographic_task_meta.json")
    monkeypatch.setattr(mod, "INFO_DIR", tmp_path / "infographics")
    monkeypatch.setattr(mod, "INDEX_PATH", tmp_path / "lesson_index.json")
    monkeypatch.setattr(mod, "BLOCKED_PATH", tmp_path / "blocked.json")
    monkeypatch.setattr(mod, "LANG", "en")
    return mod


def _disk(mod):
    return (json.loads(mod.STATE_FILE.read_text()),
            json.loads(mod.ERRORS_FILE.read_text()),
            json.loads(mod.META_FILE.read_text()))


class Killed(Exception):
    """Stands in for `timeout` killing the process mid-loop."""


def test_decisions_are_persisted_after_each_poll(gmi, monkeypatch):
    state = {"a@en": "task-a", "b@en": "task-b", "c@en": "task-c"}
    errors = {"a@en": 2, "b@en": 2, "c@en": 2}
    meta = {"a@en": {"first_seen": 1000, "last_polled": 1},
            "b@en": {"first_seen": 1000, "last_polled": 2},
            "c@en": {"first_seen": 1000, "last_polled": 3}}
    calls = []

    def poll(task_id):
        calls.append(task_id)
        if len(calls) == 2:
            raise Killed
        return "error"

    monkeypatch.setattr(gmi, "poll", poll)
    with pytest.raises(Killed):
        gmi.harvest(state, errors, meta, lambda *a: None,
                    budget_seconds=0, max_age_days=0, wall=lambda: 2000)
    on_disk, errs, m = _disk(gmi)
    # the third strike on task-a survived the "kill" during task-b's poll
    assert "a@en" not in on_disk and "a@en" not in errs and "a@en" not in m
    assert on_disk == {"b@en": "task-b", "c@en": "task-c"}
    assert errs == {"b@en": 2, "c@en": 2}
    # atomic writes leave no temp files behind
    assert not list(gmi.STATE_FILE.parent.glob(".*.tmp.*"))


def test_budget_stops_cleanly_and_reports_what_is_left(gmi, monkeypatch, capsys):
    state = {f"l{i}@en": f"t{i}" for i in range(5)}
    state["ar_only"] = "t-ar"  # another language's task is never polled
    t = {"now": 0.0}

    def poll(task_id):
        t["now"] += 100
        return "in_progress"

    monkeypatch.setattr(gmi, "poll", poll)
    downloaded, left = gmi.harvest(state, {}, {}, lambda *a: None,
                                   budget_seconds=250, max_age_days=7,
                                   clock=lambda: t["now"], wall=lambda: 5000)
    assert (downloaded, left) == (0, 2)  # polls at t=0,100,200; stop at 300
    out = capsys.readouterr().out
    assert "2 task(s) left unpolled" in out
    on_disk, _errs, meta = _disk(gmi)
    assert on_disk == state
    polled = [k for k, v in meta.items() if "last_polled" in v]
    assert len(polled) == 3
    assert "ar_only" not in meta


def test_budget_rotates_least_recently_polled_first(gmi, monkeypatch):
    state = {"old@en": "t-old", "new@en": "t-new", "never@en": "t-never"}
    meta = {"old@en": {"first_seen": 0, "last_polled": 10},
            "new@en": {"first_seen": 0, "last_polled": 99}}
    seen = []
    monkeypatch.setattr(gmi, "poll", lambda tid: seen.append(tid) or "in_progress")
    gmi.harvest(state, {}, meta, lambda *a: None, budget_seconds=0,
                max_age_days=0, wall=lambda: 100)
    assert seen == ["t-never", "t-old", "t-new"]


def test_pruning_by_age_errors_and_failure(gmi, monkeypatch):
    day = 86400
    now = 100 * day
    state = {"stale@en": "t-stale", "young@en": "t-young", "dead@en": "t-dead",
             "failed@en": "t-failed", "done_old@en": "t-done"}
    errors = {"dead@en": 2}
    meta = {"stale@en": {"first_seen": now - 8 * day},
            "young@en": {"first_seen": now - 1 * day},
            "dead@en": {"first_seen": now},
            "failed@en": {"first_seen": now},
            "done_old@en": {"first_seen": now - 30 * day}}
    status = {"t-stale": "in_progress", "t-young": "in_progress",
              "t-dead": "error", "t-failed": "failed", "t-done": "completed"}
    monkeypatch.setattr(gmi, "poll", lambda tid: status[tid])
    monkeypatch.setattr(gmi, "download", lambda tid, lid: None)  # download fails
    gmi.harvest(state, errors, meta, lambda *a: None, budget_seconds=0,
                max_age_days=7, wall=lambda: now)
    on_disk, errs, m = _disk(gmi)
    # a completed task whose download failed is retried, never aged out
    assert on_disk == {"young@en": "t-young", "done_old@en": "t-done"}
    assert errs == {}
    assert set(m) == {"young@en", "done_old@en"}


def test_completed_task_is_downloaded_and_removed(gmi, monkeypatch):
    state = {"x@en": "t-x"}
    attached = []
    monkeypatch.setattr(gmi, "poll", lambda tid: "completed")
    monkeypatch.setattr(gmi, "download", lambda tid, lid: {"id": tid})
    downloaded, left = gmi.harvest(state, {}, {}, lambda lid, a: attached.append(lid),
                                   budget_seconds=0, max_age_days=7)
    assert (downloaded, left) == (1, 0)
    assert attached == ["x"]
    assert _disk(gmi)[0] == {}


def test_harvest_only_main_exits_zero_when_budget_is_spent(gmi, monkeypatch, capsys):
    gmi.STATE_FILE.parent.mkdir(parents=True)
    gmi.STATE_FILE.write_text(json.dumps({"a@en": "t-a", "b@en": "t-b"}))
    gmi.INDEX_PATH.write_text(json.dumps({"lessons": []}))
    t = {"now": 0.0}

    def poll(task_id):
        t["now"] += 1000
        return "in_progress"

    fake_time = types.SimpleNamespace(monotonic=lambda: t["now"], time=lambda: 5000.0,
                                      sleep=lambda s: None)
    monkeypatch.setattr(gmi, "time", fake_time)
    monkeypatch.setattr(gmi, "poll", poll)
    monkeypatch.setattr(sys, "argv", ["x", "--lang", "en", "--harvest-only",
                                      "--budget-seconds", "10"])
    assert gmi.main() in (None, 0)
    out = capsys.readouterr().out
    assert "1 not polled this run (budget)" in out
    assert json.loads(gmi.STATE_FILE.read_text()) == {"a@en": "t-a", "b@en": "t-b"}
