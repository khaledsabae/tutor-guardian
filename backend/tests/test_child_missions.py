"""The mission card and the evening that settles it.

The card is where the product's central claim becomes checkable: a minute of
screen has to buy more than a minute away from it. So the first tests here are
about the bank refusing content that does not clear that ratio, and the last
are about a notification that stays out of a child's way.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.db.init_db import get_conn
from app.services import child_missions as cm
from app.services import mission_digest

DEVICE = "dev-missions-1"
_UTC = timezone.utc


@pytest.fixture
def child():
    def make(name: str = "أحمد", age_group: str = "7-9") -> int:
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
                (DEVICE, name, age_group),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    return make


# ── The bank enforces the ratio ────────────────────────────────────────────

def test_every_shipped_mission_clears_the_leverage_floor():
    """The number the parent dashboard reports is only meaningful if the
    content it is computed from was constrained. Three minutes of card must
    buy at least fifteen minutes away from it."""
    missions = cm.load_missions("7-9")
    assert missions
    for m in missions:
        assert m["estimated_minutes"] >= 15, m["id"]


def test_a_short_mission_would_be_dropped(tmp_path, monkeypatch):
    import json
    bank = {"age_band": "test", "is_published": True, "missions": [
        {"id": "long", "estimated_minutes": 20, "title_ar": "x", "instruction_ar": "y"},
        {"id": "short", "estimated_minutes": 4, "title_ar": "x", "instruction_ar": "y"},
    ]}
    (tmp_path / "missions_test.json").write_text(json.dumps(bank), encoding="utf-8")
    monkeypatch.setattr(cm, "MISSIONS_DIR", tmp_path)
    ids = [m["id"] for m in cm.load_missions("test")]
    assert ids == ["long"]


def test_an_unpublished_bank_yields_nothing(tmp_path, monkeypatch):
    import json
    (tmp_path / "missions_test.json").write_text(
        json.dumps({"is_published": False, "missions": [
            {"id": "a", "estimated_minutes": 30}]}), encoding="utf-8")
    monkeypatch.setattr(cm, "MISSIONS_DIR", tmp_path)
    assert cm.load_missions("test") == []


def test_an_unknown_band_yields_nothing():
    assert cm.load_missions("99-100") == []


# ── One card a day, and the same one ───────────────────────────────────────

def test_the_card_does_not_reroll_when_reopened(child):
    cid = child()
    first = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    for _ in range(5):
        again = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
        assert again["mission_key"] == first["mission_key"]
        assert again["mission_id"] == first["mission_id"]


def test_a_new_day_brings_a_new_card(child):
    cid = child()
    a = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    b = cm.today_mission(DEVICE, cid, "7-9", "2026-08-17")
    assert a["mission_id"] != b["mission_id"]


def test_nothing_repeats_inside_three_weeks(child):
    """A child who gets the same task every Tuesday learns the app has four
    ideas."""
    cid = child()
    seen = []
    start = datetime(2026, 8, 1, tzinfo=_UTC).date()
    for i in range(len(cm.load_missions("7-9"))):
        day = (start + timedelta(days=i)).isoformat()
        seen.append(cm.today_mission(DEVICE, cid, "7-9", day)["mission_key"])
    assert len(set(seen)) == len(seen), seen


def test_a_repeat_beats_a_blank_once_the_bank_is_exhausted(child):
    cid = child()
    start = datetime(2026, 8, 1, tzinfo=_UTC).date()
    for i in range(len(cm.load_missions("7-9")) + 3):
        day = (start + timedelta(days=i)).isoformat()
        card = cm.today_mission(DEVICE, cid, "7-9", day)
        assert card is not None
        assert card["title_ar"]


def test_two_children_can_get_different_cards(child):
    a, b = child("أحمد"), child("مريم")
    card_a = cm.today_mission(DEVICE, a, "7-9", "2026-08-16")
    card_b = cm.today_mission(DEVICE, b, "7-9", "2026-08-16")
    assert card_a["mission_id"] != card_b["mission_id"]


def test_a_band_with_no_bank_gets_no_card(child):
    # "2-3", not "16-18": the teen bank was written on 2026-08-16, and on
    # 2026-08-21 a 16-18 bank landed too — which is exactly what this comment
    # warned about, and the test failed on the content commit rather than on a
    # regression. Missions are a go-and-do card; the youngest supported band
    # (the child surface floors at two years) has no bank by design, so it is
    # the band that stays empty. If one is ever written for it, move this test
    # to whatever band is genuinely blank instead of deleting it.
    assert cm.load_missions("2-3") == [], (
        "the 2-3 bank is no longer empty; point this test at a blank band")
    cid = child("طفل", "2-3")
    assert cm.today_mission(DEVICE, cid, "2-3", "2026-08-16") is None


# ── Claiming is asynchronous ───────────────────────────────────────────────

def test_the_child_claims_without_waiting(child):
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    assert cm.claim(cid, card["mission_id"])["status"] == "claimed"
    after = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    assert after["status"] == "claimed"
    assert after["claimed_at"]


def test_another_childs_mission_cannot_be_claimed(child):
    mine, theirs = child("أحمد"), child("مريم")
    card = cm.today_mission(DEVICE, theirs, "7-9", "2026-08-16")
    assert cm.claim(mine, card["mission_id"])["reason"] == "mission_not_found"


def test_a_settled_mission_cannot_be_reclaimed(child):
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    cm.claim(cid, card["mission_id"])
    cm.confirm_batch(DEVICE, [{"mission_id": card["mission_id"], "confirmed": True}])
    assert cm.claim(cid, card["mission_id"])["reason"] == "already_settled"


# ── The parent's evening ───────────────────────────────────────────────────

def test_pending_gathers_every_child_at_once(child):
    a, b = child("أحمد"), child("مريم")
    for cid in (a, b):
        card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
        cm.claim(cid, card["mission_id"])
    pending = cm.pending_for_device(DEVICE)
    assert len(pending) == 2
    assert {p["child_name"] for p in pending} == {"أحمد", "مريم"}


def test_one_call_settles_several(child):
    a, b = child("أحمد"), child("مريم")
    ids = []
    for cid in (a, b):
        card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
        cm.claim(cid, card["mission_id"])
        ids.append(card["mission_id"])
    result = cm.confirm_batch(DEVICE, [
        {"mission_id": ids[0], "confirmed": True},
        {"mission_id": ids[1], "confirmed": False, "note": "لسه"},
    ])
    assert result["settled"] == 2
    assert cm.pending_for_device(DEVICE) == []


def test_another_devices_mission_cannot_be_confirmed(child):
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    cm.claim(cid, card["mission_id"])
    assert cm.confirm_batch("someone-else",
                            [{"mission_id": card["mission_id"]}])["settled"] == 0


def test_an_unanswered_card_expires_quietly(child):
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    cm.claim(cid, card["mission_id"])
    assert cm.expire_stale(datetime.now(_UTC) + timedelta(hours=49)) == 1
    assert cm.pending_for_device(DEVICE) == []


# ── The notification ───────────────────────────────────────────────────────

def test_nothing_pending_means_no_push(child, monkeypatch):
    """A digest that fires on an empty list teaches people to swipe it away."""
    sent = []
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda *a, **k: sent.append(a) or {"ok": True, "sent": True})
    child()
    result = mission_digest.send_digest(DEVICE)
    assert result["sent"] is False
    assert result["reason"] == "nothing_pending"
    assert sent == []


def test_one_push_carries_every_child(child, monkeypatch):
    captured = {}

    def fake_send(device_id, title, body, data=None):
        captured.update(device_id=device_id, title=title, body=body, data=data)
        return {"ok": True, "sent": True}

    monkeypatch.setattr(mission_digest.push_sender, "send_to_device", fake_send)
    monkeypatch.setattr(mission_digest.push_sender, "recently_pushed_since",
                        lambda cutoff: set())

    for name in ("أحمد", "مريم"):
        cid = child(name)
        card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
        cm.claim(cid, card["mission_id"])

    result = mission_digest.send_digest(DEVICE)
    assert result["sent"] is True
    assert result["pending"] == 2
    assert captured["device_id"] == DEVICE
    assert "أحمد" in captured["body"] and "مريم" in captured["body"]


def test_the_same_device_is_not_pushed_twice_in_a_day(child, monkeypatch):
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda *a, **k: {"ok": True, "sent": True})
    monkeypatch.setattr(mission_digest.push_sender, "recently_pushed_since",
                        lambda cutoff: {DEVICE})
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    cm.claim(cid, card["mission_id"])
    assert mission_digest.send_digest(DEVICE)["reason"] == "already_pushed_today"


def test_the_digest_reaches_the_parent_token_and_no_other_channel(child, monkeypatch):
    """Rule 4: zero notifications aimed at the child. The only send in this
    module is send_to_device, addressed to the parent's device."""
    import inspect
    source = inspect.getsource(mission_digest)
    assert "send_to_topic" not in source
    assert source.count("push_sender.send_to_device") == 1


def test_the_body_says_nothing_a_child_could_act_on(child, monkeypatch):
    """In many of these families the parent's phone is the phone the child
    uses, so the text has to survive being read over a shoulder."""
    captured = {}
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda d, t, b, data=None: captured.update(title=t, body=b)
                        or {"ok": True, "sent": True})
    monkeypatch.setattr(mission_digest.push_sender, "recently_pushed_since",
                        lambda cutoff: set())
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    cm.claim(cid, card["mission_id"])
    mission_digest.send_digest(DEVICE)
    text = captured["title"] + captured["body"]
    for bait in ("العب", "افتح التطبيق", "كوين", "جائزة", "مكافأة"):
        assert bait not in text


def test_the_sweep_expires_before_it_notifies(child, monkeypatch):
    """A card nobody answered for two days must not produce a third night's
    push."""
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda *a, **k: {"ok": True, "sent": True})
    monkeypatch.setattr(mission_digest.push_sender, "recently_pushed_since",
                        lambda cutoff: set())
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    cm.claim(cid, card["mission_id"])
    result = mission_digest.run_evening_digest(
        now=datetime.now(_UTC) + timedelta(hours=49))
    assert result["expired"] == 1
    assert result["sent"] == 0


# ── What the parent is shown at the end of a month ─────────────────────────

def test_leverage_counts_only_confirmed_missions(child):
    cid = child()
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    cm.claim(cid, card["mission_id"])
    before = cm.leverage(cid, "2026-08-01", screen_seconds=600)
    assert before["confirmed_missions"] == 0
    assert before["off_screen_minutes"] == 0

    cm.confirm_batch(DEVICE, [{"mission_id": card["mission_id"], "confirmed": True}])
    after = cm.leverage(cid, "2026-08-01", screen_seconds=600)
    assert after["confirmed_missions"] == 1
    assert after["off_screen_minutes"] >= 15
    assert after["ratio"] and after["ratio"] > 1


def test_leverage_with_no_screen_time_has_no_ratio(child):
    """Dividing by zero screen minutes would print an infinity next to a
    number a parent is meant to read."""
    cid = child()
    assert cm.leverage(cid, "2026-08-01", screen_seconds=0)["ratio"] is None


# ── The evening arrives at different times in different places ─────────────
#
# The digest logic was written, tested, and never scheduled: nothing in the
# app called it, so a parent waiting on a confirmation was never told. Wiring
# a timer to it raises a question the untimed version never had to answer —
# *when*. The spec says 9pm on the device, and a quarter of this user base is
# not in the server's timezone.

def _open_session_with_offset(child_id: int, offset_minutes: int) -> None:
    """The offset is not stored on its own; it is a column on the session the
    client opened. These tests write that column directly rather than going
    through open_session, which would also have to satisfy the age gate."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO child_screen_sessions (device_id, child_id, surface, "
            "local_date, tz_offset_minutes, started_at, last_heartbeat_at) "
            "VALUES (?, ?, 'mission', '2026-08-16', ?, ?, ?)",
            (DEVICE, child_id, offset_minutes,
             datetime.now(_UTC).isoformat(), datetime.now(_UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def _push_spy(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda device_id, *a, **k: sent.append(device_id)
                        or {"ok": True, "sent": True})
    monkeypatch.setattr(mission_digest.push_sender, "recently_pushed_since",
                        lambda cutoff: set())
    return sent


def _claimed_card(child_id: int) -> None:
    card = cm.today_mission(DEVICE, child_id, "7-9", "2026-08-16")
    cm.claim(child_id, card["mission_id"])


def test_the_digest_fires_at_nine_pm_on_the_device(child, _push_spy):
    cid = child()
    _claimed_card(cid)
    _open_session_with_offset(cid, 180)  # UTC+3 — Riyadh, Moscow

    # 18:00 UTC is 21:00 there.
    at_nine = datetime(2026, 8, 16, 18, 30, tzinfo=_UTC)
    result = mission_digest.run_due_digests(now=at_nine)
    assert result["sent"] == 1
    assert _push_spy == [DEVICE]


def test_the_digest_stays_silent_at_the_wrong_local_hour(child, _push_spy):
    """The bug this prevents is not a missing push — it is a push at 1am. A
    single UTC schedule would have done exactly that to the 38% of users
    outside Arabic-speaking timezones."""
    cid = child()
    _claimed_card(cid)
    _open_session_with_offset(cid, 180)

    # 21:00 UTC is midnight there. Nobody is confirming a mission at midnight.
    at_midnight = datetime(2026, 8, 16, 21, 0, tzinfo=_UTC)
    result = mission_digest.run_due_digests(now=at_midnight)
    assert result["sent"] == 0
    assert result["waiting"] == 1
    assert _push_spy == []


def test_a_device_that_never_opened_a_session_falls_back_to_utc(child, _push_spy):
    """A claimed mission implies a session, so this should not happen. If it
    does, an hour that is wrong for most of the world still beats never
    notifying at all."""
    cid = child()
    _claimed_card(cid)

    result = mission_digest.run_due_digests(
        now=datetime(2026, 8, 16, 21, 30, tzinfo=_UTC))
    assert result["sent"] == 1


def test_the_most_recent_offset_wins(child, _push_spy):
    """A family that travels should be followed, not pinned to wherever they
    first opened the app."""
    cid = child()
    _claimed_card(cid)
    _open_session_with_offset(cid, 180)
    _open_session_with_offset(cid, -300)  # moved to UTC-5

    # 02:00 UTC the next day is 21:00 at UTC-5, and 05:00 at the old offset.
    result = mission_digest.run_due_digests(
        now=datetime(2026, 8, 17, 2, 15, tzinfo=_UTC))
    assert result["sent"] == 1


def test_repeated_ticks_inside_the_hour_send_once(child, monkeypatch):
    """The scheduler wakes every 15 minutes and the match window is a whole
    hour, so a device matches four times a night. The frequency cap is what
    makes that harmless — this asserts the two are actually wired together."""
    pushed: list[str] = []
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda device_id, *a, **k: pushed.append(device_id)
                        or {"ok": True, "sent": True})
    # The real cap: once a device is in push_sends, it is skipped.
    monkeypatch.setattr(mission_digest.push_sender, "recently_pushed_since",
                        lambda cutoff: set(pushed))

    cid = child()
    _claimed_card(cid)
    _open_session_with_offset(cid, 180)

    base = datetime(2026, 8, 16, 18, 0, tzinfo=_UTC)
    for tick in range(4):
        mission_digest.run_due_digests(now=base + timedelta(minutes=15 * tick))
    assert pushed == [DEVICE]


def test_the_tick_is_shorter_than_the_match_window():
    """If the scheduler ever ticks slower than an hour, devices fall between
    ticks and simply never hear from us."""
    assert mission_digest.DIGEST_TICK_SECONDS < 3600


def test_the_teen_mission_bank_exists_and_is_not_the_child_one():
    """The owner's own thirteen-year-old had no missions on the day this
    shipped, because the only bank was 7-9. A teenager spots a task written
    for a seven-year-old immediately and stops taking the feature seriously."""
    child_bank = {m["id"] for m in cm.load_missions("7-9")}
    teen_bank = {m["id"] for m in cm.load_missions("13-15")}
    assert child_bank and teen_bank
    assert child_bank.isdisjoint(teen_bank)


def test_the_teen_missions_clear_the_same_leverage_floor():
    for m in cm.load_missions("13-15"):
        assert m["estimated_minutes"] >= 15, m["id"]
