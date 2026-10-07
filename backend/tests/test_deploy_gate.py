"""The deploy gate: production only gets a commit whose hosted tests passed.

Two halves. The decision logic of ops/tools/deploy_gate.py, on recorded API
shapes. And the wiring between the workflows, which no single file can see:
deploy.yml waits for jobs *named* in backend.yml, for runs that only exist if
backend.yml's push filter matched — a rename or a narrowed filter in one file
would quietly turn every deploy red, or leave a merge with nothing to wait for.
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
SHA = "a" * 40


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops" / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gate = _load("deploy_gate")


def _run(**kw):
    base = {"id": 1, "head_sha": SHA, "head_branch": "main", "event": "push",
            "status": "completed", "created_at": "2026-10-04T10:00:00Z"}
    return {**base, **kw}


def _jobs(**conclusions):
    names = {"pytest": "pytest", "kb": "KB integrity", "ruff": "ruff"}
    return [{"id": i, "name": names[k], "status": "completed", "conclusion": c}
            for i, (k, c) in enumerate(conclusions.items())]


# ── which run counts ─────────────────────────────────────────────────────

def test_only_main_runs_of_this_commit_count():
    runs = [_run(id=1, head_branch="feature"), _run(id=2, event="pull_request"),
            _run(id=3, head_sha="b" * 40)]
    assert gate.pick_run(runs, SHA) is None


def test_the_newest_matching_run_wins():
    runs = [_run(id=1, created_at="2026-10-04T10:00:00Z"),
            _run(id=2, event="workflow_dispatch", created_at="2026-10-04T11:00:00Z")]
    assert gate.pick_run(runs, SHA)["id"] == 2


# ── what passes ──────────────────────────────────────────────────────────

def test_all_three_green_passes():
    assert gate.judge(_jobs(pytest="success", kb="success", ruff="success"))[0] == "pass"


@pytest.mark.parametrize("bad", ["failure", "cancelled", "skipped", "timed_out", None])
def test_any_required_job_not_green_fails(bad):
    verdict, lines = gate.judge(_jobs(pytest=bad, kb="success", ruff="success"))
    assert verdict == "fail", lines


def test_a_missing_required_job_fails_closed():
    # A rename in backend.yml must stop deploys, not wave them through.
    jobs = [j for j in _jobs(pytest="success", kb="success", ruff="success")
            if j["name"] != "ruff"]
    verdict, lines = gate.judge(jobs)
    assert verdict == "fail" and any("MISSING" in line for line in lines)


def test_unfinished_jobs_wait():
    jobs = _jobs(pytest="success", kb="success", ruff="success")
    jobs[0].update(status="in_progress", conclusion=None)
    assert gate.judge(jobs)[0] == "wait"


def test_only_main_may_deploy():
    assert gate.main(["--sha", SHA, "--repo", "o/r", "--ref", "refs/heads/feature"]) == 1


# ── the wiring between the workflows (repo files: skipped in the image) ──

repo_files = pytest.mark.skipif(
    not WORKFLOWS.exists(),
    reason="repo-file check; the backend image has no .github (runs in PR CI)",
)


def _workflow(name: str) -> dict:
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # YAML 1.1 reads the key `on` as True
    return doc


def _covered(path: str, patterns: list[str]) -> bool:
    return any(path == p or (p.endswith("/**") and path.startswith(p[:-2]))
               for p in patterns)


@repo_files
def test_every_deploy_path_also_runs_the_tests_the_gate_waits_for():
    deploy = _workflow("deploy.yml")["on"]["push"]["paths"]
    tests = _workflow("backend.yml")["on"]["push"]["paths"]
    uncovered = [p for p in deploy if not _covered(p, tests)]
    assert not uncovered, (
        f"deploy.yml deploys on {uncovered} but backend.yml does not test on them — "
        "such a merge would have no run for the gate to wait for")


@repo_files
def test_the_gate_names_jobs_that_exist_and_run_on_main():
    jobs = _workflow("backend.yml")["jobs"]
    by_name = {j["name"]: j for j in jobs.values()}
    for name in gate.REQUIRED_JOBS:
        assert name in by_name, f"deploy gate requires a backend.yml job named {name!r}"
        assert by_name[name]["runs-on"] == "ubuntu-latest", name


@repo_files
def test_main_runs_of_the_tests_are_never_cancelled():
    # A newer push cancelling an older main run would fail that run's deploy.
    cancel = str(_workflow("backend.yml")["concurrency"]["cancel-in-progress"])
    assert "pull_request" in cancel and cancel != "True"


@repo_files
def test_production_jobs_wait_for_the_gate_and_never_cancel_a_deploy():
    deploy = _workflow("deploy.yml")
    assert deploy["concurrency"] == {"group": "deploy-production", "cancel-in-progress": False}
    jobs = deploy["jobs"]
    assert set(jobs["deploy"]["needs"]) == {"gate", "image"}
    assert jobs["image"]["needs"] == "gate"
    for hosted in ("gate", "image"):  # neither holds the production runner
        assert jobs[hosted]["runs-on"] == "ubuntu-latest", hosted
    assert any("ops/tools/deploy_gate.py" in step.get("run", "") for step in jobs["gate"]["steps"])


@repo_files
def test_the_production_host_builds_and_tests_nothing():
    # 2026-10-04: a cached image build on the CPU-throttled host took 44 min and
    # was cancelled. It pulls the image the hosted `image` job smoked — by digest.
    deploy = _workflow("deploy.yml")
    for job_id, job in deploy["jobs"].items():
        if "self-hosted" not in str(job["runs-on"]):
            continue
        script = "\n".join(step.get("run", "") for step in job["steps"])
        uses = " ".join(str(step.get("uses", "")) for step in job["steps"])
        for heavy in (r"\bdocker build\b", r"\bbuildx build\b", r"\bcompose(\s+-f\s+\S+)*\s+build\b",
                      r"\bpytest\b", r"candidate_smoke"):
            assert not re.search(heavy, script), (job_id, heavy)
        assert "actions/checkout" not in uses, job_id
    pull = "\n".join(step.get("run", "") for step in deploy["jobs"]["deploy"]["steps"])
    assert 'docker pull "$IMAGE@$DIGEST"' in pull
    assert deploy["jobs"]["deploy"]["env"]["DIGEST"] == "${{ needs.image.outputs.digest }}"


@repo_files
def test_no_test_job_runs_on_the_production_host():
    for name in ("backend.yml", "flutter.yml"):
        for job_id, job in _workflow(name)["jobs"].items():
            assert "self-hosted" not in str(job["runs-on"]), f"{name}:{job_id}"


# ── the in-image smoke ───────────────────────────────────────────────────

def test_every_smoke_test_file_exists():
    # Renaming one would otherwise surface only on the production host.
    smoke = _load("candidate_smoke")
    missing = [p for p in smoke.PYTEST_SUBSET if not (ROOT / p).exists()]
    assert not missing, missing


@repo_files
def test_docker_ci_never_prunes_or_builds_on_the_production_runner():
    # Opening a source PR triggers both Docker jobs. Their disk-prune/build
    # steps must execute on a disposable hosted runner, away from live images.
    workflow = _workflow("docker.yml")
    assert "pull_request" in workflow["on"]
    assert set(workflow["jobs"]) == {"build", "smoke"}
    for name, job in workflow["jobs"].items():
        assert job["runs-on"] == "ubuntu-latest", name
    assert workflow["jobs"]["smoke"]["needs"] == "build"
