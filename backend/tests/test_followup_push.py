"""The follow-up push (services/followup_push.py) — schema v30.

It runs from the backend's in-process loop at 19:00 on each family's own
clock (PR #26 review F7: the 17 UTC cron could not reach UTC+4…+8 inside
09:00–21:00). Runs against the real init_db schema (the conftest temp DB),
not a hand-made fixture: the sweep joins four tables, and a fixture written
from memory is exactly how a column that production does not have gets past
a test.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.db.init_db import get_conn
from app.services import followup_push as fp
from app.services import push_sender

# A fixed clock: 16:00 UTC is 19:00 at UTC+3 (Riyadh, Cairo in summer).
NOW = datetime(2026, 10, 5, 16, 0, 0)
RIYADH = 180
# The simulated time of the current sweep: the send log must be written in it,
# or the caps would compare the real clock with a simulated one.
_CLOCK = {"now": NOW}


def _record(device_id: str, kind: str, at: datetime) -> None:
    conn = get_conn()
    conn.execute("INSERT INTO push_sends (device_id, kind, sent_at) VALUES (?, ?, ?)",
                 (device_id, kind, at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def _sweep(now: datetime = NOW, **kw) -> dict:
    _CLOCK["now"] = now
    return fp.run_due_followups(now, **kw)


@pytest.fixture
def sent(monkeypatch):
    calls: list[dict] = []

    def fake_send(device_id, title, body, data, **options):
        calls.append({"device": device_id, "title": title, "body": body, "data": data,
                      **options})
        _record(device_id, data.get("type", "unknown"), _CLOCK["now"])
        return {"ok": True, "sent": True}

    monkeypatch.setattr(push_sender, "send_to_device", fake_send)
    monkeypatch.setenv("CHILD_MEMORY_MIN_BUILD", "112")
    return calls


def _device(device: str, *, build: int | None = 120, name: str = "يوسف",
            tz: int | None = RIYADH) -> int:
    conn = get_conn()
    cid = conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, '4-6')",
        (device, name),
    ).lastrowid
    conn.execute(
        "INSERT INTO push_tokens (device_id, token, build_number) VALUES (?, 'tok', ?)",
        (device, build),
    )
    conn.execute(
        "INSERT INTO child_memory_settings (device_id, enabled, tz_offset_minutes) "
        "VALUES (?, 1, ?)", (device, tz))
    conn.commit()
    conn.close()
    return cid


def _followup(device: str, cid: int, *, hours_ago: float = 2, lang: str = "ar",
              strategy: str = "روتين نوم ثابت مع قصة", topic: str = "sleep",
              now: datetime = NOW) -> int:
    due = (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    fid = conn.execute(
        "INSERT INTO followups (device_id, child_id, strategy, topic, lang, due_at) "
        "VALUES (?, ?, ?, ?, ?, ?)", (device, cid, strategy, topic, lang, due),
    ).lastrowid
    conn.commit()
    conn.close()
    return fid


def _pushed_at(fid: int):
    conn = get_conn()
    v = conn.execute("SELECT pushed_at FROM followups WHERE id = ?", (fid,)).fetchone()[0]
    conn.close()
    return v


def test_off_until_the_memory_build_is_named(sent, monkeypatch):
    monkeypatch.delenv("CHILD_MEMORY_MIN_BUILD")
    cid = _device("dev-a")
    _followup("dev-a", cid)
    assert _sweep(NOW)["sent"] == 0
    assert sent == []


def test_due_followup_is_pushed_once_with_its_deep_link(sent):
    cid = _device("dev-a")
    fid = _followup("dev-a", cid)
    assert _sweep(NOW)["sent"] == 1
    assert len(sent) == 1
    push = sent[0]
    assert push["data"] == {"type": "followup_due", "link": f"/followup/{fid}",
                            "followup_id": str(fid), "child_id": str(cid)}
    # Generic and private: no strategy (it can be something the family keeps
    # to itself), no name, hidden on a locked screen (A8/P5).
    assert "روتين" not in push["body"] and "يوسف" not in push["title"] + push["body"]
    assert push["visibility"] == "private"
    assert _pushed_at(fid) is not None
    # The next tick, and the next evening: never twice.
    assert _sweep(NOW + timedelta(minutes=15))["sent"] == 0
    assert _sweep(NOW + timedelta(days=1))["sent"] == 0
    assert len(sent) == 1


def test_at_most_one_followup_push_per_device_per_week(sent):
    cid = _device("dev-a")
    _followup("dev-a", cid, hours_ago=5)
    second = _followup("dev-a", cid, hours_ago=3, strategy="ركن هدوء", topic="anger")
    _sweep(NOW)
    assert len(sent) == 1            # one per sweep, the oldest
    for day in range(1, 7):          # and nothing more this week
        _sweep(NOW + timedelta(days=day))
    assert len(sent) == 1 and _pushed_at(second) is None


def test_not_due_old_build_unknown_build_memory_off_or_pushed_today(sent):
    a = _device("dev-future")
    _followup("dev-future", a, hours_ago=-24)           # due tomorrow
    b = _device("dev-old", build=100)
    _followup("dev-old", b)
    c = _device("dev-unknown", build=None)
    _followup("dev-unknown", c)
    d = _device("dev-off")
    _followup("dev-off", d)
    conn = get_conn()
    conn.execute("UPDATE child_memory_settings SET enabled = 0 WHERE device_id = 'dev-off'")
    conn.commit()
    conn.close()
    e = _device("dev-capped")
    _followup("dev-capped", e)
    _record("dev-capped", "streak_at_risk", NOW - timedelta(hours=3))   # any push, today
    out = _sweep(NOW)
    assert out["sent"] == 0 and out["capped"] == 1 and sent == []


def test_answered_followups_are_not_pushed(sent):
    cid = _device("dev-a")
    fid = _followup("dev-a", cid)
    conn = get_conn()
    conn.execute("UPDATE followups SET status = 'answered' WHERE id = ?", (fid,))
    conn.commit()
    conn.close()
    assert _sweep(NOW)["sent"] == 0


def test_english_followup_gets_english_copy(sent):
    cid = _device("dev-en")
    _followup("dev-en", cid, lang="en", strategy="a fixed bedtime routine")
    _sweep(NOW)
    assert sent[0]["title"].startswith("A follow-up from Almorabbi")
    assert "bedtime" not in sent[0]["body"]


def test_expired_followups_are_not_pushed(sent):
    """Past FOLLOWUP_EXPIRE_DAYS a follow-up has expired — the push SQL says
    so itself, without waiting for the app to open (A8)."""
    cid = _device("dev-old-fu")
    _followup("dev-old-fu", cid, hours_ago=22 * 24)
    assert _sweep(NOW)["sent"] == 0 and sent == []


# ── Time zones (F7) ───────────────────────────────────────────────────────


@pytest.mark.parametrize("offset", [240, 300, 330, 345, 360, 420, 480])
def test_families_from_utc_plus_4_to_plus_8_are_reached_in_their_evening(sent, offset):
    """Dubai, Karachi, Delhi, Kathmandu, Dhaka, Jakarta, Kuala Lumpur: the 17 UTC
    run reached none of them inside 09:00–21:00."""
    device = f"dev-tz-{offset}"
    cid = _device(device, tz=offset)
    day = datetime(2026, 10, 5)
    _followup(device, cid, hours_ago=30, now=day)
    hours = []
    for tick in range(24 * 4):                       # every 15 minutes for a day
        now = day + timedelta(minutes=15 * tick)
        before = len(sent)
        _sweep(now)
        if len(sent) > before:
            hours.append((now + timedelta(minutes=offset)).hour)
    assert hours == [fp.FOLLOWUP_LOCAL_HOUR]
    assert fp.LOCAL_DAY_START <= hours[0] < fp.LOCAL_DAY_END


def test_never_at_night_in_any_time_zone(sent):
    """Every offset from UTC-12 to UTC+14, every 15-minute tick of a day:
    each device is asked exactly once, and only in its daytime."""
    day = datetime(2026, 10, 5)
    offsets = list(range(-12 * 60, 14 * 60 + 1, 30))
    for off in offsets:
        cid = _device(f"dev-z{off}", tz=off)
        _followup(f"dev-z{off}", cid, hours_ago=30, now=day)
    seen: dict[str, int] = {}
    for tick in range(24 * 4):
        now = day + timedelta(minutes=15 * tick)
        before = len(sent)
        _sweep(now)
        for push in sent[before:]:
            off = int(push["device"][len("dev-z"):])
            local = (now + timedelta(minutes=off)).hour
            assert fp.LOCAL_DAY_START <= local < fp.LOCAL_DAY_END, (off, local)
            seen[push["device"]] = seen.get(push["device"], 0) + 1
    assert len(seen) == len(offsets) and set(seen.values()) == {1}


def test_an_unknown_time_zone_is_never_guessed(sent):
    cid = _device("dev-notz", tz=None)
    _followup("dev-notz", cid)
    for tick in range(24 * 4):
        _sweep(NOW + timedelta(minutes=15 * tick))
    assert sent == []


# ── Exactly once, even with two workers ───────────────────────────────────


def test_a_claimed_followup_is_not_sent_twice(sent, monkeypatch):
    """Two workers in the same tick: the second finds it claimed."""
    cid = _device("dev-race")
    fid = _followup("dev-race", cid)
    real_claim = fp._claim
    calls = []

    def claim_twice(followup_id):
        calls.append(followup_id)
        first = real_claim(followup_id)
        assert real_claim(followup_id) is False          # the other worker loses
        return first

    monkeypatch.setattr(fp, "_claim", claim_twice)
    assert _sweep(NOW)["sent"] == 1 and len(sent) == 1
    assert calls == [fid]


def test_a_failed_send_is_released_for_a_later_tick(sent, monkeypatch):
    cid = _device("dev-fail")
    fid = _followup("dev-fail", cid)
    monkeypatch.setattr(push_sender, "send_to_device",
                        lambda *a, **k: {"ok": False, "error": "boom"})
    out = _sweep(NOW)
    assert out["failed"] == 1 and _pushed_at(fid) is None
    calls = []
    monkeypatch.setattr(push_sender, "send_to_device",
                        lambda d, t, b, data, **o: calls.append(d) or {"ok": True, "sent": True})
    assert _sweep(NOW + timedelta(minutes=15))["sent"] == 1
    assert calls == ["dev-fail"] and _pushed_at(fid) is not None


def test_dry_run_marks_nothing(sent):
    cid = _device("dev-a")
    fid = _followup("dev-a", cid)
    out = _sweep(NOW, dry_run=True)
    assert out["would_send"] == 1 and sent == [] and _pushed_at(fid) is None


_CRON = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "cron_push_triggers.py"


def test_the_backend_loop_runs_it():
    """No cron line: the in-process local-hour loop (main.py) owns it."""
    from app import main
    assert ("Follow-up push", fp.run_due_followups) in main._LOCAL_HOUR_JOBS


@pytest.mark.skipif(not _CRON.exists(), reason="ops/scripts not present (backend-only image)")
def test_the_cron_no_longer_sends_it():
    assert "followup_due(" not in _CRON.read_text(encoding="utf-8")
