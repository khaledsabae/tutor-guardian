"""The time budget, tested from the outside in.

Most of these assert a refusal. The budget's only job is to say no at the
right moment, and a test suite that only proves the happy path proves the
thing that was never in doubt.

Time is injected by monkeypatching `child_budget._now` rather than sleeping,
so the clock-dependent cases — grace windows, rolling 24-hour floors, the
turn of the local day — run in milliseconds and are not flaky.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.config.guardrails_loader import load_child_surface_policy
from app.services import child_budget

_UTC = timezone.utc
_T0 = datetime(2026, 8, 15, 9, 0, 0, tzinfo=_UTC)


@pytest.fixture
def policy():
    return load_child_surface_policy()


@pytest.fixture
def clock(monkeypatch):
    """A movable clock. `clock.set(...)` / `clock.advance(seconds=...)`."""

    class Clock:
        def __init__(self):
            self.now = _T0

        def set(self, moment):
            self.now = moment

        def advance(self, seconds=0, minutes=0, hours=0):
            self.now += timedelta(seconds=seconds, minutes=minutes, hours=hours)
            return self.now

    c = Clock()
    monkeypatch.setattr(child_budget, "_now", lambda: c.now)
    return c


@pytest.fixture
def child():
    """Factory: make_child(age_group) -> child_id, all owned by DEVICE.

    The DB is the real migrated schema — conftest's autouse fixture points
    CONVERSATIONS_DB at a throwaway file and runs init_db, so these tests
    exercise the migration that ships rather than a hand-written copy of it.
    """
    from app.db import init_db as db

    DEVICE = "dev-test-1"

    def make(age_group: str) -> int:
        conn = db.get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
                (DEVICE, "طفل", age_group),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    make.device = DEVICE
    return make


def _run(policy, session_id, clock, heartbeats: int, interval: int = 30):
    """Send N heartbeats at the normal interval, returning the last result."""
    result = {"ok": True}
    for _ in range(heartbeats):
        clock.advance(seconds=interval)
        result = child_budget.heartbeat(session_id, policy)
        if not result.get("ok"):
            break
    return result


# ── The age gate ───────────────────────────────────────────────────────────

def test_infant_cannot_open_any_session(policy, child, clock):
    cid = child("prenatal-1")
    result = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert result["ok"] is False
    assert result["reason"] == "age_not_allowed"
    assert result["parent_message_key"] == "child_gate.under_2"
    assert result["parent_message_ar"]


def test_legacy_0_3_profile_is_refused_rather_than_guessed(policy, child, clock):
    """Four production profiles carry this label and it straddles infancy."""
    cid = child("0-3")
    result = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert result["ok"] is False
    assert result["reason"] == "age_not_allowed"


def test_unreadable_age_is_refused(policy, child, clock):
    for label in ("unspecified", "", "garbage"):
        cid = child(label)
        result = child_budget.open_session(child.device, cid, "story", 180, policy)
        assert result["ok"] is False, label
        assert result["reason"] == "age_not_allowed", label


def test_toddler_gets_audio_but_not_a_screen(policy, child, clock):
    cid = child("2-3")
    assert child_budget.open_session(child.device, cid, "screen_off", 180, policy)["ok"]
    denied = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert denied["ok"] is False
    assert denied["reason"] == "age_not_allowed"


def test_surface_outside_the_band_is_refused(policy, child, clock):
    """A 4-6 may see a story but not a game, and asking anyway does not work."""
    cid = child("4-6")
    result = child_budget.open_session(child.device, cid, "game", 180, policy)
    assert result["ok"] is False
    assert result["reason"] == "surface_not_allowed"


def test_another_devices_child_is_not_found(policy, child, clock):
    cid = child("7-9")
    result = child_budget.open_session("someone-else", cid, "story", 180, policy)
    assert result["ok"] is False
    assert result["reason"] == "child_not_found"


# ── The budget ─────────────────────────────────────────────────────────────

def test_session_is_capped_by_the_surface_not_only_the_day(policy, child, clock):
    """7-9 has 20 daily minutes; a story is 10. The first session gets 10."""
    cid = child("7-9")
    opened = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert opened["allowed_seconds"] == 10 * 60
    assert opened["remaining_today"] == 20 * 60


def test_budget_runs_out_and_the_next_heartbeat_refuses(policy, child, clock):
    cid = child("7-9")
    opened = child_budget.open_session(child.device, cid, "story", 180, policy)
    result = _run(policy, opened["session_id"], clock, heartbeats=25)
    assert result["ok"] is False
    assert result["reason"] == "budget_exhausted"


def test_exit_ritual_is_announced_before_the_end(policy, child, clock):
    cid = child("7-9")
    opened = child_budget.open_session(child.device, cid, "story", 180, policy)
    ritual = opened["exit_ritual_seconds"]
    seen = []
    for _ in range(25):
        clock.advance(seconds=30)
        r = child_budget.heartbeat(opened["session_id"], policy)
        if not r.get("ok"):
            break
        seen.append((r["remaining_seconds"], r["exit_ritual"]))
    assert any(flag for _, flag in seen), "the ritual never started"
    for remaining, flag in seen:
        assert flag == (remaining <= ritual)


def test_the_day_is_spent_across_sessions_not_per_session(policy, child, clock):
    """Two stories, ten minutes each, is the whole 7-9 day. A third is
    refused — the cap is the day, not the session."""
    cid = child("7-9")
    for _ in range(2):
        opened = child_budget.open_session(child.device, cid, "story", 180, policy)
        assert opened["ok"], opened
        _run(policy, opened["session_id"], clock, heartbeats=21)
    third = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert third["ok"] is False
    assert third["reason"] == "budget_exhausted"


def test_screen_off_does_not_spend_the_screen_budget(policy, child, clock):
    cid = child("7-9")
    opened = child_budget.open_session(child.device, cid, "screen_off", 180, policy)
    _run(policy, opened["session_id"], clock, heartbeats=40)
    after = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert after["ok"] is True
    assert after["remaining_today"] == 20 * 60


def test_audio_has_its_own_ceiling(policy, child, clock):
    """Not billing screen time is not the same as being unlimited."""
    cid = child("7-9")
    for _ in range(2):
        opened = child_budget.open_session(child.device, cid, "screen_off", 180, policy)
        assert opened["ok"], opened
        _run(policy, opened["session_id"], clock, heartbeats=95)
    third = child_budget.open_session(child.device, cid, "screen_off", 180, policy)
    assert third["ok"] is False
    assert third["reason"] == "audio_budget_exhausted"


def test_agreement_costs_the_child_nothing(policy, child, clock):
    """The Sprint 2 entry gate. A child does not pay screen time to read a
    covenant written about them."""
    cid = child("7-9")
    opened = child_budget.open_session(child.device, cid, "agreement", 180, policy)
    assert opened["ok"] is True
    _run(policy, opened["session_id"], clock, heartbeats=20)
    after = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert after["remaining_today"] == 20 * 60


# ── Silence is not free ────────────────────────────────────────────────────

def test_a_session_that_goes_silent_is_charged_for_its_grace(policy, child, clock):
    """The refill loop: open, send nothing, get reaped, open again. If the
    grace window were free this would be unlimited screen time."""
    cid = child("7-9")
    grace = policy.defaults.heartbeat_grace_seconds

    for _ in range(3):
        opened = child_budget.open_session(child.device, cid, "story", 180, policy)
        assert opened["ok"], opened
        clock.advance(seconds=grace + 1)  # vanish

    final = child_budget.open_session(child.device, cid, "story", 180, policy)
    usage = child_budget.today_usage(cid, "2026-08-15", policy)
    assert usage["counted_seconds"] >= 3 * grace, usage
    assert final["remaining_today"] < 20 * 60


def test_a_stale_session_is_reaped_when_the_next_one_opens(policy, child, clock):
    cid = child("7-9")
    first = child_budget.open_session(child.device, cid, "story", 180, policy)
    clock.advance(seconds=policy.defaults.heartbeat_grace_seconds + 5)
    child_budget.open_session(child.device, cid, "story", 180, policy)

    usage = child_budget.today_usage(cid, "2026-08-15", policy)
    reaped = [s for s in usage["sessions"] if s["ended_reason"] == "timeout"]
    assert len(reaped) == 1
    assert reaped[0]["counted_seconds"] > 0


def test_a_heartbeat_after_the_grace_window_closes_the_session(policy, child, clock):
    cid = child("7-9")
    opened = child_budget.open_session(child.device, cid, "story", 180, policy)
    clock.advance(seconds=policy.defaults.heartbeat_grace_seconds + 1)
    result = child_budget.heartbeat(opened["session_id"], policy)
    assert result["ok"] is False
    assert result["reason"] == "session_closed"


def test_only_one_session_is_open_per_child(policy, child, clock):
    cid = child("7-9")
    first = child_budget.open_session(child.device, cid, "story", 180, policy)
    clock.advance(seconds=10)
    second = child_budget.open_session(child.device, cid, "game", 180, policy)
    assert second["ok"] is True
    assert child_budget.heartbeat(first["session_id"], policy)["ok"] is False
    assert child_budget.active_session(cid)["id"] == second["session_id"]


def test_a_stretched_heartbeat_gap_is_billed_not_forgiven(policy, child, clock):
    """Sending late must not be cheaper than sending on time."""
    cid = child("7-9")
    honest = child("7-9")

    a = child_budget.open_session(child.device, cid, "story", 180, policy)
    for _ in range(4):
        clock.advance(seconds=60)          # double the interval
        child_budget.heartbeat(a["session_id"], policy)
    slow = child_budget.today_usage(cid, "2026-08-15", policy)["counted_seconds"]

    clock.set(_T0)
    b = child_budget.open_session(child.device, honest, "story", 180, policy)
    for _ in range(8):
        clock.advance(seconds=30)
        child_budget.heartbeat(b["session_id"], policy)
    fast = child_budget.today_usage(honest, "2026-08-15", policy)["counted_seconds"]

    assert slow == fast, (slow, fast)


# ── Dates and timezones ────────────────────────────────────────────────────

def test_the_budget_resets_on_the_next_local_day(policy, child, clock):
    cid = child("7-9")
    for _ in range(2):
        opened = child_budget.open_session(child.device, cid, "story", 180, policy)
        _run(policy, opened["session_id"], clock, heartbeats=21)
    assert child_budget.open_session(child.device, cid, "story", 180, policy)["ok"] is False

    clock.advance(hours=24)
    tomorrow = child_budget.open_session(child.device, cid, "story", 180, policy)
    assert tomorrow["ok"] is True
    assert tomorrow["remaining_today"] == 20 * 60


def test_jumping_the_timezone_does_not_buy_a_second_day(policy, child, clock):
    """Cairo to Sydney moves the calendar date without moving the instant, so
    a skew check on the clock passes. The rolling 24-hour floor is what
    actually refuses."""
    cid = child("7-9")
    for _ in range(2):
        opened = child_budget.open_session(child.device, cid, "story", 180, policy)
        _run(policy, opened["session_id"], clock, heartbeats=21)

    jumped = child_budget.open_session(child.device, cid, "story", 11 * 60, policy)
    assert jumped["ok"] is False
    assert jumped["reason"] == "budget_exhausted"


def test_an_impossible_offset_is_refused(policy, child, clock):
    cid = child("7-9")
    for offset in (15 * 60, -13 * 60, 99999):
        result = child_budget.open_session(child.device, cid, "story", offset, policy)
        assert result["ok"] is False, offset
        assert result["reason"] == "invalid_tz_offset", offset


def test_the_local_date_is_the_childs_not_the_servers(policy, child, clock):
    """20:00 UTC on the 15th is already 09:00 on the 16th in Auckland (+13).
    The session belongs to the child's day, not the server's."""
    cid = child("7-9")
    clock.set(datetime(2026, 8, 15, 20, 0, 0, tzinfo=_UTC))
    child_budget.open_session(child.device, cid, "story", 13 * 60, policy)
    assert child_budget.today_usage(cid, "2026-08-16", policy)["sessions"]
    assert not child_budget.today_usage(cid, "2026-08-15", policy)["sessions"]


# ── Reporting ──────────────────────────────────────────────────────────────

def test_usage_separates_screen_from_audio_for_the_parent(policy, child, clock):
    cid = child("7-9")
    a = child_budget.open_session(child.device, cid, "story", 180, policy)
    _run(policy, a["session_id"], clock, heartbeats=4)
    child_budget.close_session(a["session_id"], "completed", policy)

    b = child_budget.open_session(child.device, cid, "screen_off", 180, policy)
    _run(policy, b["session_id"], clock, heartbeats=10)
    child_budget.close_session(b["session_id"], "completed", policy)

    usage = child_budget.today_usage(cid, "2026-08-15", policy)
    assert usage["counted_seconds"] == 120
    assert usage["screen_off_seconds"] == 300
    assert set(usage["by_surface"]) == {"story", "screen_off"}
    assert [s["ended_reason"] for s in usage["sessions"]] == ["completed", "completed"]


def test_closing_a_session_twice_is_harmless(policy, child, clock):
    cid = child("7-9")
    opened = child_budget.open_session(child.device, cid, "story", 180, policy)
    clock.advance(seconds=30)
    child_budget.close_session(opened["session_id"], "parent_exit", policy)
    before = child_budget.today_usage(cid, "2026-08-15", policy)["counted_seconds"]
    child_budget.close_session(opened["session_id"], "completed", policy)
    after = child_budget.today_usage(cid, "2026-08-15", policy)["counted_seconds"]
    assert before == after
