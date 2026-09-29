"""scripts/gen_podcasts_cron.py — trigger sentinels are outcomes, never task ids.

`if tid:` used to run before `elif tid == "STALE_SOURCE"`, so the sentinel was
stored in ops/data/podcast_tasks.json as a task id (five prenatal lessons on
2026-09-29). No CLI is called: trigger() and poll() are replaced.
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# These test repo-level scripts/ (the NotebookLM pipeline). The deploy gate runs
# pytest inside the backend image, which does not ship scripts/ — skip there.
pytestmark = pytest.mark.skipif(
    not (REPO / "scripts" / "cron_gen_en_media.sh").exists(),
    reason="scripts/ not present (backend-only image)",
)

SCRIPT = REPO / "scripts" / "gen_podcasts_cron.py"
UUID_A = "3f49cd9e-1111-4a4d-9941-1f519470c471"
UUID_B = "8a8a8a8a-2222-4a4d-9941-1f519470c471"


@pytest.fixture
def gpc(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("gpc_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "podcast_tasks.json")
    monkeypatch.setattr(mod, "ERRORS_FILE", tmp_path / "podcast_poll_errors.json")
    monkeypatch.setattr(mod, "POLL_BUDGET_SEC", 0)
    monkeypatch.setattr(mod, "_has_pod", lambda lid, lang: False)
    return mod


def test_is_task_id_rejects_sentinels_and_junk(gpc):
    assert gpc._is_task_id(UUID_A)
    for bad in ("STALE_SOURCE", "RATELIMIT", "", None, 42, "-", "abc"):
        assert not gpc._is_task_id(bad), bad


def test_loader_drops_sentinels_so_old_files_self_heal(gpc):
    gpc.STATE_FILE.write_text(json.dumps({
        "lesson_prenatal-1_infant_pregnancy_01@en": "STALE_SOURCE",
        "lesson_x@en": "RATELIMIT",
        "lesson_ok@en": UUID_A,
        "lesson_ar": UUID_B,
    }))
    state = gpc._load_state()
    assert state == {"lesson_ok@en": UUID_A, "lesson_ar": UUID_B}


def _run_main(gpc, monkeypatch, outcomes: dict, argv=("--lang", "en")):
    async def trigger(source_id, lang, notebook=gpc.NOTEBOOK_ID):
        return outcomes[source_id]

    async def poll(task_id, notebook=gpc.NOTEBOOK_ID):
        return "pending"

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(gpc, "trigger", trigger)
    monkeypatch.setattr(gpc, "poll", poll)
    monkeypatch.setattr(gpc.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(gpc, "_targets", lambda: [
        ("lesson_stale", "src-stale", gpc.NOTEBOOK_ID),
        ("lesson_good", "src-good", gpc.NOTEBOOK_ID),
        ("lesson_none", "src-none", gpc.NOTEBOOK_ID),
    ])
    monkeypatch.setattr(sys, "argv", ["gen_podcasts_cron.py", *argv])
    asyncio.run(gpc.main())
    return json.loads(gpc.STATE_FILE.read_text())


def test_stale_source_is_reported_not_stored(gpc, monkeypatch, capsys):
    # A sentinel left by the old bug is purged on load and the lesson is
    # triggered again, instead of being skipped as "in flight" forever.
    gpc.STATE_FILE.write_text(json.dumps({"lesson_stale@en": "STALE_SOURCE"}))
    gpc.ERRORS_FILE.write_text(json.dumps({"lesson_stale@en": 2}))
    state = _run_main(gpc, monkeypatch, {
        "src-stale": "STALE_SOURCE", "src-good": UUID_A, "src-none": None,
    })
    assert state == {"lesson_good@en": UUID_A}
    assert all(gpc._is_task_id(v) for v in state.values())
    out = capsys.readouterr().out
    assert "lesson_stale: STALE SOURCE" in out
    assert "task STALE_SOURCE" not in out
    assert "lesson_none: no task id" in out
    assert json.loads(gpc.ERRORS_FILE.read_text()) == {}


def test_ratelimit_stops_the_run_without_storing(gpc, monkeypatch):
    state = _run_main(gpc, monkeypatch, {
        "src-stale": "RATELIMIT", "src-good": UUID_A, "src-none": None,
    })
    assert state == {}


def test_harvest_only_rewrites_a_healed_file(gpc, monkeypatch):
    gpc.STATE_FILE.write_text(json.dumps({"lesson_stale@en": "STALE_SOURCE",
                                          "lesson_good@en": UUID_A}))
    state = _run_main(gpc, monkeypatch, {}, argv=("--lang", "en", "--harvest-only"))
    assert state == {"lesson_good@en": UUID_A}
