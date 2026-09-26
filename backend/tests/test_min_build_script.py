"""ops/scripts/min_build.sh — the force-update floor is decided on evidence.

A floor above what Play actually serves locks everyone below it out with
nothing to update to. `plan` (and therefore `apply`) refuses a floor that no
recently active device runs yet; `census` shows who a floor would force.
"""
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "min_build.sh"

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists() or shutil.which("bash") is None,
    reason="ops scripts are not shipped in this environment",
)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "census.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE push_tokens (device_id TEXT PRIMARY KEY, token TEXT, "
        "platform TEXT, updated_at TEXT, app_version TEXT, build_number INTEGER)"
    )
    rows = [
        ("a", 111, "-1 days"), ("b", 109, "-2 days"), ("c", 109, "-3 days"),
        ("d", 106, "-10 days"), ("e", None, "-20 days"),
        ("gone", 90, "-200 days"),              # not active: not counted
    ]
    for dev, build, age in rows:
        conn.execute(
            "INSERT INTO push_tokens VALUES (?, 't', 'android', datetime('now', ?), NULL, ?)",
            (dev, age, build),
        )
    conn.commit()
    conn.close()
    return path


def _run(db, *args, **env):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env={**os.environ, "LOCAL": "1", "DB_PATH": str(db), **env},
        capture_output=True, text=True,
    )


def test_census_counts_active_devices_per_build(db):
    r = _run(db, "census", "30")
    assert r.returncode == 0, r.stderr
    assert "active devices, last 30 days: 5" in r.stdout
    lines = {l.split()[0]: l.split()[1] for l in r.stdout.splitlines()
             if l.strip() and l.split()[0] in {"111", "109", "106", "unknown", "90"}}
    assert lines == {"111": "1", "109": "2", "106": "1", "unknown": "1"}


def test_plan_reports_who_a_floor_forces(db):
    r = _run(db, "plan", "109")
    assert r.returncode == 0, r.stderr
    assert "forced to update: 2 (40.0%)  = 1 on a known older build + 1 unknown" in r.stdout
    assert "unaffected:       3" in r.stdout
    assert r.stdout.rstrip().endswith("OK")


def test_plan_refuses_a_floor_nobody_can_reach_yet(db):
    # 112 is not on anyone's phone: as far as the evidence goes, Play does not
    # serve it, and a floor there would lock every user out.
    r = _run(db, "plan", "112")
    assert r.returncode != 0
    assert "REFUSED" in r.stderr + r.stdout


def test_force_overrides_the_evidence_check(db):
    assert _run(db, "plan", "112", FORCE="1").returncode == 0


def test_proof_must_be_recent(db):
    # 110 is proven by device a alone, last seen a day ago. With a proof window
    # shorter than that, the same floor has no evidence behind it.
    assert _run(db, "plan", "110").returncode == 0
    assert _run(db, "plan", "110", PROOF_DAYS="0").returncode != 0


def test_apply_edits_env_backs_it_up_and_verifies(db, tmp_path):
    # A stand-in docker: `compose up` succeeds, and the recreated backend
    # serves whatever .env now says — the same contract as env_file.
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=1\nMINIMUM_BUILD_NUMBER=81\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "docker"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == exec ]]; then\n'
        f"  v=$(grep ^MINIMUM_BUILD_NUMBER= {env_file} | cut -d= -f2)\n"
        '  echo "{\\"minimum_build_number\\": $v}"\n'
        "fi\n"
    )
    fake.chmod(0o755)
    r = _run(db, "apply", "109", ENV_FILE=str(env_file),
             PATH=f"{bin_dir}:{os.environ['PATH']}")
    assert r.returncode == 0, r.stdout + r.stderr
    assert env_file.read_text() == "FOO=1\nMINIMUM_BUILD_NUMBER=109\n"
    backups = list(tmp_path.glob(".env.bak.*"))
    assert len(backups) == 1 and "MINIMUM_BUILD_NUMBER=81" in backups[0].read_text()
    assert "OK: /api/app-config serves minimum_build_number=109" in r.stdout
    assert "apply 81" in r.stdout                  # the way back is printed


def test_apply_changes_nothing_when_the_plan_is_refused(db, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MINIMUM_BUILD_NUMBER=81\n")
    r = _run(db, "apply", "112", ENV_FILE=str(env_file))
    assert r.returncode != 0
    assert env_file.read_text() == "MINIMUM_BUILD_NUMBER=81\n"
    assert not list(tmp_path.glob(".env.bak.*"))
