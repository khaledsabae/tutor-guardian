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
    cid = child("طفل", "13-15")
    assert cm.today_mission(DEVICE, cid, "13-15", "2026-08-16") is None


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
