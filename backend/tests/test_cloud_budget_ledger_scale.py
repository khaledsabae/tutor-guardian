"""Ledger under contention and history (review of PR #71, P1).

A settle is never a denial: it waits for the ledger instead of being
swallowed after 0.2 s (15/49 settles were lost at 5k rows x 4 streams,
each leaving a 1,048,576-token orphan that blocks rollover). The continuity
witness is O(1) per transaction — a trigger-maintained sequence and running
totals mirrored in the anchor — instead of hashing every row twice. Closed
months are archived at rollover, and an offline tool settles real orphans
with an audit record.
"""
import fcntl
import json
import random
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import cloud_budget as cb
from app.services import cloud_budget_bootstrap as cli
from tests.budget_test_helpers import activate

ALIASES = ("deepseek",)


def seeded(tmp_path, n, **kw):
    db = tmp_path / "sessions.db"
    sqlite3.connect(db).close()
    led = activate(cb.CloudBudget(db, **kw), wallets=("w",))
    with sqlite3.connect(db) as conn:
        conn.executemany("INSERT INTO cloud_budget_attempts VALUES(?,?,?,?,?,1)",
                         [(uuid.uuid4().hex, "w", "2026-01", 1048576, 3000) for _ in range(n)])
        led._write_anchor(conn)          # test-only: witness the seeded history
    return led


def unsettled(led):
    with sqlite3.connect(led.path) as conn:
        return conn.execute("SELECT COUNT(*) FROM cloud_budget_attempts WHERE settled=0").fetchone()[0]


def hold_lock(led, seconds):
    lock = open(str(led.anchor_path) + ".lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    threading.Timer(seconds, lock.close).start()


def test_settle_waits_out_a_busy_ledger_instead_of_losing_the_charge(tmp_path):
    led = seeded(tmp_path, 0)
    t = led.reserve("w", 10**9, 1048576, legacy_aliases=ALIASES, unknown_usage_bounds=(5000, 1024))
    hold_lock(led, 1.0)                  # 5x the old 0.2 s give-up
    led.settle(t, 5, 5)
    with sqlite3.connect(led.path) as conn:
        assert conn.execute("SELECT charged_tokens, settled FROM cloud_budget_attempts").fetchall() == [(10, 1)]


def test_reserve_waits_through_brief_contention(tmp_path):
    led = seeded(tmp_path, 0)
    hold_lock(led, 0.6)
    assert led.reserve("w", 10**9, 1048576, legacy_aliases=ALIASES)


def test_reserve_still_gives_up_after_its_own_timeout(tmp_path, monkeypatch):
    led = seeded(tmp_path, 0)
    monkeypatch.setattr(cb, "RESERVE_TIMEOUT_S", 0.3)
    hold_lock(led, 1.5)
    with pytest.raises(cb.BudgetDenied, match="busy"):
        led.reserve("w", 10**9, 1048576, legacy_aliases=ALIASES)


def test_hot_path_never_scans_history(tmp_path, monkeypatch):
    led = seeded(tmp_path, 50000)

    def full_scan(*a, **k):
        raise AssertionError("reserve/settle must not recount the whole ledger")

    monkeypatch.setattr(cb.CloudBudget, "_recount", full_scan)
    started = time.monotonic()
    t = led.reserve("w", 10**12, 1048576, legacy_aliases=ALIASES, unknown_usage_bounds=(5000, 1024))
    led.settle(t, 100, 100)
    assert time.monotonic() - started < 1.0


def test_no_settle_is_lost_at_50k_rows_with_8_concurrent_streams(tmp_path):
    led = seeded(tmp_path, 50000)
    outcome = {"reserved": 0, "denied": []}
    guard = threading.Lock()
    rnd = random.Random(1)

    def stream():
        for _ in range(8):
            try:
                t = led.reserve("w", 10**12, 1048576, legacy_aliases=ALIASES,
                                unknown_usage_bounds=(5000, 1024))
            except cb.BudgetDenied as exc:
                with guard:
                    outcome["denied"].append(str(exc))
                continue
            with guard:
                outcome["reserved"] += 1
            time.sleep(rnd.uniform(0.0, 0.05))
            led.settle(t, 1500, 300)

    threads = [threading.Thread(target=stream) for _ in range(8)]
    [x.start() for x in threads]
    [x.join() for x in threads]
    assert outcome["denied"] == [] and outcome["reserved"] == 64
    assert unsettled(led) == 0


def test_direct_edit_of_a_ledger_row_breaks_continuity(tmp_path):
    led = seeded(tmp_path, 10)
    with sqlite3.connect(led.path) as conn:
        conn.execute("UPDATE cloud_budget_attempts SET charged_tokens=0 WHERE rowid=1")
    with pytest.raises(cb.BudgetDenied, match="continuity"):
        led.reserve("w", 10**9, 1, legacy_aliases=ALIASES)


def test_deleted_ledger_row_breaks_continuity(tmp_path):
    led = seeded(tmp_path, 10)
    with sqlite3.connect(led.path) as conn:
        conn.execute("DELETE FROM cloud_budget_attempts WHERE rowid=1")
    with pytest.raises(cb.BudgetDenied, match="continuity"):
        led.reserve("w", 10**9, 1, legacy_aliases=ALIASES)


def test_dropped_trigger_breaks_continuity(tmp_path):
    led = seeded(tmp_path, 1)
    with sqlite3.connect(led.path) as conn:
        name = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' "
                            "AND tbl_name='cloud_budget_attempts' LIMIT 1").fetchone()[0]
        conn.execute(f"DROP TRIGGER {name}")
    with pytest.raises(cb.BudgetDenied, match="continuity"):
        led.reserve("w", 10**9, 1, legacy_aliases=ALIASES)


def test_unrelated_schema_changes_in_the_same_db_do_not_break_continuity(tmp_path):
    # sessions.db also holds the app's own tables and telemetry migrations.
    led = seeded(tmp_path, 1)
    with sqlite3.connect(led.path) as conn:
        conn.execute("CREATE TABLE answer_cache_v9(x)")
        conn.execute("ALTER TABLE llm_calls ADD COLUMN reservation_note TEXT")
    assert led.reserve("w", 10**9, 1, legacy_aliases=ALIASES)


# ── rollover: full audit, archive of closed months ─────────────────────────
OCT = datetime(2026, 10, 7, tzinfo=timezone.utc)


def clocked(tmp_path):
    now = [OCT]
    db = tmp_path / "sessions.db"
    sqlite3.connect(db).close()
    led = activate(cb.CloudBudget(db, clock=lambda: now[0]), wallets=("w",))
    return led, now


def test_forged_witness_is_caught_by_the_monthly_full_audit(tmp_path):
    led, now = clocked(tmp_path)
    t = led.reserve("w", 10**9, 100, legacy_aliases=ALIASES)
    led.settle(t, 10, 10)
    with sqlite3.connect(led.path) as conn:   # edit a row, then put the witness back
        before = conn.execute("SELECT * FROM cloud_budget_witness").fetchone()
        conn.execute("UPDATE cloud_budget_attempts SET charged_tokens=1")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(cloud_budget_witness)")]
        conn.execute(f"UPDATE cloud_budget_witness SET {', '.join(c + '=?' for c in cols)}", before)
    now[0] = datetime(2026, 11, 1, 0, 1, tzinfo=timezone.utc)
    with pytest.raises(cb.BudgetDenied):
        led.reserve("w", 10**9, 1, legacy_aliases=ALIASES)


def test_rollover_archives_months_before_the_previous_one(tmp_path):
    led, now = clocked(tmp_path)
    with sqlite3.connect(led.path) as conn:
        conn.executemany("INSERT INTO cloud_budget_attempts VALUES(?,?,?,?,?,1)",
                         [(uuid.uuid4().hex, "w", "2026-08", 1000, 7) for _ in range(5)])
        led._write_anchor(conn)
    t = led.reserve("w", 10**9, 100, legacy_aliases=ALIASES)
    led.settle(t, 10, 10)
    now[0] = datetime(2026, 11, 1, 0, 1, tzinfo=timezone.utc)
    led.reserve("w", 10**9, 1, legacy_aliases=ALIASES)
    with sqlite3.connect(led.path) as conn:
        months = dict(conn.execute("SELECT month, COUNT(*) FROM cloud_budget_attempts GROUP BY month"))
        archived = conn.execute("SELECT COUNT(*), SUM(charged_tokens) FROM cloud_budget_attempts_archive "
                                "WHERE month='2026-08'").fetchone()
    assert "2026-08" not in months and months == {"2026-10": 1, "2026-11": 1}
    assert archived == (5, 35)


# ── offline orphan settlement, audited ─────────────────────────────────────
def test_orphan_tool_settles_old_orphans_at_their_request_bound_with_audit(tmp_path, capsys):
    led, now = clocked(tmp_path)
    old = led.reserve("w", 10**9, 1048576, legacy_aliases=ALIASES, unknown_usage_bounds=(5000, 1024))
    now[0] = OCT + timedelta(hours=3)
    young = led.reserve("w", 10**9, 1048576, legacy_aliases=ALIASES, unknown_usage_bounds=(5000, 1024))
    args = ["--db", str(led.path), "--settle-orphans", "--older-than-minutes", "60",
            "--evidence", "process restart 2026-10-07; usage unknown", "--now", now[0].isoformat()]
    assert cli.main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["orphans"] == [old.id]
    assert unsettled(led) == 2                       # dry run writes nothing
    assert cli.main(args) == 0
    with sqlite3.connect(led.path) as conn:
        rows = dict(conn.execute("SELECT id, charged_tokens||'/'||settled FROM cloud_budget_attempts"))
        audit = conn.execute("SELECT action, attempt_id, old_charge, new_charge, evidence "
                             "FROM cloud_budget_audit").fetchall()
    assert rows == {old.id: "6024/1", young.id: "1048576/0"}
    assert audit == [("settle_orphan", old.id, 1048576, 6024, "process restart 2026-10-07; usage unknown")]
    led.settle(old, 1, 1)                            # a late real settle cannot rewrite it
    with sqlite3.connect(led.path) as conn:
        assert conn.execute("SELECT charged_tokens FROM cloud_budget_attempts WHERE id=?",
                            (old.id,)).fetchone() == (6024,)


def test_orphan_tool_requires_evidence_and_an_age(tmp_path):
    led, _ = clocked(tmp_path)
    assert cli.main(["--db", str(led.path), "--settle-orphans", "--older-than-minutes", "60"]) != 0
    assert cli.main(["--db", str(led.path), "--settle-orphans", "--evidence", "x"]) != 0
