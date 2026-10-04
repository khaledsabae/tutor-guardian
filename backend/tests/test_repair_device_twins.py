"""ops/tools/repair_device_twins.py — the one-off backlog repair.

Dry run is the default and must not be able to write; --apply folds exactly
what the runtime rule would (minus the request credential) and nothing else.
"""
import importlib.util
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.db.init_db import db_path
from app.services import conversation_store as store
from app.services import device_twins as twins

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "tools" / "repair_device_twins.py"


def _load():
    spec = importlib.util.spec_from_file_location("repair_device_twins", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _born(device, at):
    _, token = store.create_session_with_token(device_id=device)
    with _db() as conn:
        conn.execute("UPDATE api_tokens SET created_at = ? WHERE device_id = ?", (at, device))
    return token


def _child(device):
    with _db() as conn:
        conn.execute("INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, 'c', '7-9')",
                     (device,))


def _push(device, fcm, updated_at):
    with _db() as conn:
        conn.execute("INSERT INTO push_tokens (device_id, token, platform, updated_at) "
                     "VALUES (?, ?, 'android', ?)", (device, fcm, updated_at))


@pytest.fixture()
def population():
    """Every shape the survey distinguishes, one install each."""
    tokens = {}
    # 1. The app came back as the twin (its push row is the recent one).
    tokens["U1"] = _born("U1", "2026-09-30 10:00:00"); _child("U1")
    tokens["H1"] = _born("H1", "2026-09-30 10:00:01")
    _push("U1", "fcm-1", "2026-09-30 10:00:05"); _push("H1", "fcm-1", "2026-10-03 19:00:00")
    # 2. The app runs as the family; the twin is a phantom.
    tokens["U2"] = _born("U2", "2026-09-30 11:00:00"); _child("U2")
    tokens["H2"] = _born("H2", "2026-09-30 11:00:00")
    _push("U2", "fcm-2", "2026-10-02 08:00:00"); _push("H2", "fcm-2", "2026-09-30 11:00:03")
    # 3. Same token, born days apart: an identity reset, never folded.
    _born("U3", "2026-09-01 09:00:00"); _child("U3"); _push("U3", "fcm-3", "2026-09-01 09:00:05")
    _born("R3", "2026-09-20 09:00:00"); _push("R3", "fcm-3", "2026-09-20 09:00:05")
    # 4. Two families on one token: ambiguous, never folded.
    _born("U4", "2026-09-30 12:00:00"); _child("U4"); _push("U4", "fcm-4", "2026-09-30 12:00:05")
    _born("V4", "2026-09-30 12:00:01"); _child("V4"); _push("V4", "fcm-4", "2026-09-30 12:00:05")
    _born("H4", "2026-09-30 12:00:01"); _push("H4", "fcm-4", "2026-09-30 12:00:05")
    # 5. No shared token (notifications refused): visible by birth time only.
    _born("U5", "2026-09-30 13:00:00"); _child("U5")
    _born("H5", "2026-09-30 13:00:01")
    return tokens


def _all_rows():
    with _db() as conn:
        return {t: conn.execute(f'SELECT COUNT(*), GROUP_CONCAT("{c}") FROM "{t}"').fetchone()[:]
                for t, c in twins.device_columns(conn)}


def _report(out: str) -> dict[str, int]:
    """The survey's `  <name>   <count>` lines."""
    rows = (re.match(r"^\s+(\S.*?)\s+(\d+)$", line) for line in out.splitlines())
    return {m.group(1): int(m.group(2)) for m in rows if m}


def test_dry_run_classifies_and_writes_nothing(population, capsys):
    before = _all_rows()
    assert _load().main(["--db", str(db_path())]) == 0
    out = capsys.readouterr().out
    assert _all_rows() == before
    assert _report(out) == {
        "twin:app_runs_as_twin": 1,
        "twin:app_runs_as_family": 1,
        "same_token_born_apart_not_folded": 1,
        "ambiguous_several_families_on_one_token": 1,
        "both_halves_have_a_child_reonboarded": 1,
        "time_only_twin_not_folded": 1,
        "time_only_twin_used_after_first_minute": 0,
        "=> foldable twins (what --apply would fold)": 2,
    }
    assert "dry run: nothing written" in out
    for device in ("U1", "H1", "U2", "H2"):                  # aggregates only
        assert device not in out


def test_the_dry_run_connection_cannot_write(population):
    conn = _load()._open(db_path(), readonly=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM push_tokens")


def test_it_folds_exactly_what_the_runtime_rule_would(population):
    survey = _load().survey(_db(), twins)
    foldable = {(t, f) for t, f, _ in survey["pairs"]}
    assert foldable == {("H1", "U1"), ("H2", "U2")}
    with _db() as conn:
        for twin, family in foldable:
            # The request-time rule, given the twin's own original token, agrees.
            assert twins.twin_canonical(conn, twin, credential=population[twin]) == family
        for device in ("R3", "H4", "H5"):
            assert twins.family_of(conn, device) is None


def test_apply_snapshots_then_folds_the_twins_only(population, tmp_path, capsys):
    assert _load().main(["--apply", "--db", str(db_path()), "--backup-dir", str(tmp_path)]) == 0
    assert "folded 2 of 2" in capsys.readouterr().out
    snapshots = list(tmp_path.glob("conversations.pre-twin-repair-*.db"))
    assert len(snapshots) == 1
    with sqlite3.connect(snapshots[0]) as snap:        # the snapshot is pre-fold
        assert snap.execute("SELECT COUNT(*) FROM api_tokens WHERE device_id = 'H1'").fetchone()[0] == 1
    assert store.validate_token(population["H1"])["device_id"] == "U1"
    with _db() as conn:
        left = {d: sum(conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{c}" = ?', (d,)).fetchone()[0]
                       for t, c in twins.device_columns(conn))
                for d in ("H1", "H2", "R3", "H4", "H5")}
    assert left["H1"] == 0 and left["H2"] == 0
    assert left["R3"] and left["H4"] and left["H5"]      # never folded


def test_the_bundle_runs_the_dry_run_in_a_container_without_the_module(population):
    """What the 2026-10-04 survey did: pipe --bundle into `python -`."""
    bundle = subprocess.run([sys.executable, str(SCRIPT), "--bundle"], capture_output=True,
                            text=True, check=True, env={**os.environ,
                                                        "PYTHONPATH": str(ROOT / "backend")}).stdout
    run = subprocess.run([sys.executable, "-"], input=bundle, capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": str(ROOT / "backend"),
                              "CONVERSATIONS_DB": str(db_path())})
    assert run.returncode == 0, run.stderr
    assert _report(run.stdout)["=> foldable twins (what --apply would fold)"] == 2
    assert "dry run: nothing written" in run.stdout
