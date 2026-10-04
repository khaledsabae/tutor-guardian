"""ops/tools/repair_device_twins.py — the one-off backlog repair.

Dry run is the default and must not be able to write; --apply folds only what
the rule allows (services/device_twins.repairable), re-decided under the write
lock for every pair, and nothing else.
"""
import importlib.util
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.db.init_db import db_path, hash_token
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
        conn.execute("UPDATE api_tokens SET created_at = ? WHERE token = ?", (at, hash_token(token)))
    return token


def _child(device, at):
    with _db() as conn:
        conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at, updated_at) "
                     "VALUES (?, 'c', '7-9', ?, ?)", (device, at, at))


def _push(device, fcm, updated_at):
    with _db() as conn:
        conn.execute("INSERT INTO push_tokens (device_id, token, platform, updated_at) "
                     "VALUES (?, ?, 'android', ?)", (device, fcm, updated_at))


@pytest.fixture(autouse=True)
def _default_cohort(monkeypatch):
    monkeypatch.delenv("TWIN_FOLD_BORN_BEFORE", raising=False)


@pytest.fixture()
def population():
    """Every shape the survey distinguishes, one install each."""
    t = {}
    # 1. The app came back as the twin: the family went quiet after onboarding,
    #    the twin is in use — and renewed its token once.
    t["U1"] = _born("U1", "2026-09-30 10:00:00"); _child("U1", "2026-09-30 10:01:00")
    t["H1"] = _born("H1", "2026-09-30 10:00:01")
    t["H1-later"] = _born("H1", "2026-10-02 18:00:00")
    _push("U1", "fcm-1", "2026-09-30 10:00:05"); _push("H1", "fcm-1", "2026-10-03 19:00:00")
    # 2. The app runs as the family; the twin is a phantom nobody uses.
    t["U2"] = _born("U2", "2026-09-30 11:00:00"); _child("U2", "2026-09-30 11:01:00")
    t["H2"] = _born("H2", "2026-09-30 11:00:00")
    _push("U2", "fcm-2", "2026-10-02 08:00:00"); _push("H2", "fcm-2", "2026-09-30 11:00:03")
    # 3. Same token, born days apart: an identity reset, never folded.
    _born("U3", "2026-09-01 09:00:00"); _child("U3", "2026-09-01 09:01:00")
    _push("U3", "fcm-3", "2026-09-01 09:00:05")
    _born("R3", "2026-09-20 09:00:00"); _push("R3", "fcm-3", "2026-09-20 09:00:05")
    # 4. Two families on one token: ambiguous, never folded.
    _born("U4", "2026-09-30 12:00:00"); _child("U4", "2026-09-30 12:01:00")
    _push("U4", "fcm-4", "2026-09-30 12:00:05")
    _born("V4", "2026-09-30 12:00:01"); _child("V4", "2026-09-30 12:01:00")
    _push("V4", "fcm-4", "2026-09-30 12:00:05")
    _born("H4", "2026-09-30 12:00:01"); _push("H4", "fcm-4", "2026-09-30 12:00:05")
    # 5. No shared token (notifications refused): visible by birth time only.
    _born("U5", "2026-09-30 13:00:00"); _child("U5", "2026-09-30 13:01:00")
    _born("H5", "2026-09-30 13:00:01")
    # 6. A family on an id the API now refuses (stored before validation).
    _born("abcd efgh ijkl mnop", "2026-09-12 15:57:50"); _child("abcd efgh ijkl mnop", "2026-09-12 15:58:00")
    # 7. A twin pair born before the first splitting build: outside the cohort.
    _born("U7", "2026-09-05 10:00:00"); _child("U7", "2026-09-05 10:01:00")
    _push("U7", "fcm-7", "2026-09-05 10:00:05")
    _born("H7", "2026-09-05 10:00:01"); _push("H7", "fcm-7", "2026-09-08 10:00:00")
    # 8. Both halves in use: never folded.
    _born("U8", "2026-09-30 14:00:00"); _child("U8", "2026-09-30 14:01:00")
    _push("U8", "fcm-8", "2026-10-02 10:00:00")
    _born("H8", "2026-09-30 14:00:01"); _push("H8", "fcm-8", "2026-10-03 10:00:00")
    return t


def _all_rows():
    with _db() as conn:
        return {t: conn.execute(f'SELECT COUNT(*), GROUP_CONCAT("{c}") FROM "{t}"').fetchone()[:]
                for t, c in twins.device_columns(conn, include_excluded=True)}


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
        "twin:app_runs_as_twin:twin_has_later_tokens": 1,
        "twin:phantom": 1,
        "twin:both_halves_in_use_not_folded": 1,
        "twin_outside_cohort_not_folded": 1,
        "same_token_born_apart_not_folded": 1,
        "ambiguous_several_families_on_one_token": 1,
        "both_halves_have_a_child_reonboarded": 1,
        "time_only_twin_not_folded": 1,
        "time_only_twin_used_after_first_minute": 0,
        "refused_id_devices": 1,
        "refused_id_devices_with_children": 1,
        "=> foldable twins (what --apply would fold)": 2,
        "of which the twin has later tokens": 1,
    }
    assert "dry run: nothing written" in out
    for device in ("U1", "H1", "U2", "H2"):                  # aggregates only
        assert device not in out


def test_the_dry_run_connection_cannot_write(population):
    conn = _load()._open(db_path(), readonly=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM push_tokens")


def test_it_folds_only_what_the_rule_allows(population):
    pairs = {(twin, family, kind) for twin, family, kind, _ in _load().survey(_db(), twins)["pairs"]}
    assert pairs == {("H1", "U1", "app_runs_as_twin"), ("H2", "U2", "phantom")}
    with _db() as conn:
        # The app-came-back case is exactly what the request-time rule folds,
        # given the twin's own birth-minute token…
        assert twins.twin_canonical(conn, "H1", credential=population["H1"]) == "U1"
        # …while a phantom is folded only here: its family is in use, so a
        # request never folds it — the twin went quiet, which is what makes
        # cleaning it up safe.
        assert twins.twin_canonical(conn, "H2", credential=population["H2"]) is None
        for device in ("R3", "H4", "H5", "H7", "H8"):
            family = twins.family_of(conn, device)
            assert family is None or twins.repairable(conn, device, family) is None, device


def test_apply_snapshots_then_folds_only_those_pairs(population, tmp_path, capsys):
    assert _load().main(["--apply", "--db", str(db_path()), "--backup-dir", str(tmp_path)]) == 0
    assert "folded 2 of 2" in capsys.readouterr().out
    snapshots = list(tmp_path.glob("conversations.pre-twin-repair-*.db"))
    assert len(snapshots) == 1
    with sqlite3.connect(snapshots[0]) as snap:        # the snapshot is pre-fold
        assert snap.execute("SELECT COUNT(*) FROM api_tokens WHERE device_id = 'H1'").fetchone()[0] == 2
    assert store.validate_token(population["H1"])["device_id"] == "U1"
    assert store.validate_token(population["H1-later"])["device_id"] == "H1"   # not without the flag
    assert store.validate_token(population["H2"])["device_id"] == "U2"
    with _db() as conn:
        for device in ("R3", "H4", "H5", "H7", "H8"):
            assert conn.execute("SELECT COUNT(*) FROM api_tokens WHERE device_id = ?",
                                (device,)).fetchone()[0] == 1, device
        assert conn.execute("SELECT COUNT(*) FROM device_fold_log").fetchone()[0] > 0


def test_later_tokens_move_only_when_the_operator_says_so(population, tmp_path):
    assert _load().main(["--apply", "--include-later-twin-tokens", "--db", str(db_path()),
                         "--backup-dir", str(tmp_path)]) == 0
    assert store.validate_token(population["H1-later"])["device_id"] == "U1"


def test_each_pair_is_re_decided_under_the_write_lock(population):
    # The family came back to life between the survey and the fold.
    with _db() as conn:
        conn.execute("UPDATE push_tokens SET updated_at = '2026-10-04 09:00:00' WHERE device_id = 'U1'")
    with _db() as conn:
        assert twins.fold_pair(conn, "H1", "U1") == (None, None)
    assert store.validate_token(population["H1"])["device_id"] == "H1"


def test_the_bundle_runs_the_dry_run_in_a_container_without_the_module(population):
    """What the 2026-10-04 surveys did: pipe --bundle into `python -`."""
    bundle = subprocess.run([sys.executable, str(SCRIPT), "--bundle"], capture_output=True,
                            text=True, check=True, env={**os.environ,
                                                        "PYTHONPATH": str(ROOT / "backend")}).stdout
    # The container predates this change: no service module, and none of the
    # helpers it imports. Remove them before the bundle runs.
    old_container = (
        "import app.core.log_safety as l, app.models.api as a, app.db.init_db as d\n"
        "del l.describe_rejected_id, a.DEVICE_ID_PATTERN, a.DEVICE_ID_MAX_LENGTH\n"
        "del d.ensure_device_twin_tables, d._CREATE_DEVICE_TWIN_TABLES\n"
        "import sys; sys.modules.pop('app.services.device_twins', None)\n"
        f"exec(compile({bundle!r}, '<stdin>', 'exec'), {{'__name__': '__main__'}})\n"
    )
    run = subprocess.run([sys.executable, "-"], input=old_container, capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": str(ROOT / "backend"),
                              "CONVERSATIONS_DB": str(db_path())})
    assert run.returncode == 0, run.stderr
    assert _report(run.stdout)["=> foldable twins (what --apply would fold)"] == 2
    assert "dry run: nothing written" in run.stdout
