"""The proactive milestones: the cards a parent sees, and the one push a month ahead.

The listing is about timing (birth month vs band fallback, the season for the
first fast) and audience (gender, puberty). The push is about restraint: the
family's 20:00 inside 09–21, never with an unknown offset, at most one a day
from any sender, one milestone a week per device and a month per child, never
the same one twice — even with two workers racing — and only to builds that
can open the link.
"""
import os
import threading
import time
from datetime import datetime, timezone

import pytest

from app.db.init_db import get_conn
from app.services import milestone_push as mp
from app.services import push_sender
from tests.programs_support import (DEVICE, OTHER, add_child, add_child_row, client, freeze,
                                    rows)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("RAMADAN_START_", "RAMADAN_DAYS_")) or name in (
                "MILESTONES_MIN_BUILD", "PROGRAMS_AS_OF_ENABLED"):
            monkeypatch.delenv(name, raising=False)


def _list(c, cid, **params):
    r = c.get(f"/api/children/{cid}/milestones", params={"tz_offset_minutes": 0, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _keys(cards):
    return [card["key"] for card in cards]


# ── What the parent sees ───────────────────────────────────────────────────

def test_an_age_milestone_opens_the_month_before_and_stays_due_ninety_days(monkeypatch):
    c = client()
    cid = add_child(c, birth_month="2020-03")             # seven in March 2027
    freeze(monkeypatch, "2027-01-31T12:00:00")
    out = _list(c, cid)
    up = next(m for m in out["upcoming"] if m["key"] == "prayer_start")
    assert (up["due_on"], up["alert_on"], up["basis"]) == ("2027-03-01", "2027-02-01",
                                                           "birth_month")
    assert out["alert_policy"]["pushes"] is True and out["needs_profile"] == []
    freeze(monkeypatch, "2027-02-01T00:00:00")
    assert "prayer_start" in _keys(_list(c, cid)["due"])
    freeze(monkeypatch, "2027-05-29T12:00:00")
    assert "prayer_start" in _keys(_list(c, cid)["due"])
    freeze(monkeypatch, "2027-05-30T12:00:00")
    assert "prayer_start" in _keys(_list(c, cid)["past"])


def test_without_a_birth_month_the_band_puts_cards_in_the_library_and_asks(monkeypatch):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    out = _list(c, add_child(c, age_group="7-9"))
    assert _keys(out["library"]) == ["prayer_start", "first_fasting"]
    assert all(card["due_on"] is None and card["basis"] == "age_group"
               for card in out["library"])
    assert out["due"] == [] and out["upcoming"] == []
    # Puberty cards are withheld until the gender is known — and it is asked for.
    assert out["needs_profile"] == ["birth_month", "gender"]
    assert out["alert_policy"]["pushes"] is False


@pytest.mark.parametrize("gender,shown,hidden", [
    ("female", "puberty_girls", "puberty_boys"),
    ("male", "puberty_boys", "puberty_girls"),
])
def test_a_gendered_card_shows_only_for_that_gender(monkeypatch, gender, shown, hidden):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    out = _list(c, add_child(c, age_group="10-12", gender=gender), lang="en")
    keys = _keys(out["library"])
    assert shown in keys and hidden not in keys
    assert out["needs_profile"] == ["birth_month"]
    card = next(m for m in out["library"] if m["key"] == shown)
    assert card["medical"] is True and card["red_flags"]


def test_the_first_fast_is_timed_by_the_season(monkeypatch):
    c = client()
    eight = add_child(c, birth_month="2019-01")            # 97 months on 8 Feb 2027
    too_young = add_child(c, birth_month="2020-03", name="سارة")   # 83 months
    freeze(monkeypatch, "2027-01-08T12:00:00")
    card = next(m for m in _list(c, eight)["upcoming"] if m["key"] == "first_fasting")
    assert (card["alert_on"], card["due_on"]) == ("2027-01-09", "2027-02-08")
    assert card["season"]["hijri_year"] == 1448
    freeze(monkeypatch, "2027-02-20T12:00:00")              # during Ramadan: still due
    assert "first_fasting" in _keys(_list(c, eight)["due"])
    # Too young at 1448's start (83 months); his first fast is 1449's.
    young = [m for g in ("due", "upcoming") for m in _list(c, too_young)[g]
             if m["key"] == "first_fasting"]
    assert [m["season"]["hijri_year"] for m in young] == [1449]
    freeze(monkeypatch, "2027-03-10T12:00:00")              # Eid: 1448 is over…
    later = next(m for m in _list(c, eight)["upcoming"] if m["key"] == "first_fasting")
    assert later["season"]["hijri_year"] == 1449            # …and 1449 is next
    assert (later["alert_on"], later["due_on"]) == ("2027-12-29", "2028-01-28")


def test_the_familys_own_sighting_moves_the_seasonal_card(monkeypatch):
    c = client()
    cid = add_child(c, birth_month="2019-01")
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c.put("/api/programs/ramadan/settings", json={"start_shift_days": 1})
    card = next(m for m in _list(c, cid)["due"] if m["key"] == "first_fasting")
    assert card["due_on"] == "2027-02-09"


def test_a_newborns_parent_is_not_shown_the_teenage_guide(monkeypatch):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    out = _list(c, add_child(c, age_group="prenatal-1", birth_month="2026-08"))
    assert out["due"] == out["upcoming"] == out["past"] == []


def test_puberty_marked_retires_the_before_puberty_card(monkeypatch):
    c = client()
    cid = add_child(c, birth_month="2019-01", gender="female")   # 8 in Jan 2027
    freeze(monkeypatch, "2027-01-05T12:00:00")
    assert "puberty_girls" in _keys(_list(c, cid)["due"])
    c.put(f"/api/children/{cid}/ramadan/fasting", json={"reached_puberty": True})
    out = _list(c, cid)
    assert "puberty_girls" in _keys(out["past"]) and "puberty_girls" not in _keys(out["due"])


def test_one_card_for_the_deep_link(monkeypatch):
    freeze(monkeypatch, "2027-02-10T12:00:00")
    c = client()
    cid = add_child(c, birth_month="2020-03", gender="male")
    r = c.get(f"/api/children/{cid}/milestones/prayer_start", params={"lang": "en"})
    assert r.status_code == 200
    card = r.json()["milestone"]
    assert card["state"] == "due" and card["alert"]["title"] == "Turning seven next month"
    assert card["links"]["program_ids"] == ["prayer_journey"]
    assert len(card["cards"]) >= 3
    for missing in ("puberty_girls", "no_such_milestone"):
        r = c.get(f"/api/children/{cid}/milestones/{missing}")
        assert r.status_code == 404 and r.json()["detail"]["error"] == "milestone_not_found"
    other = add_child(c, device=OTHER)
    assert c.get(f"/api/children/{other}/milestones").status_code == 404


# ── The push ───────────────────────────────────────────────────────────────

NOW = {"t": datetime(2027, 2, 1, 17, 0, tzinfo=timezone.utc)}   # 20:00 in UTC+3


def _at(iso: str) -> datetime:
    NOW["t"] = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    return NOW["t"]


@pytest.fixture
def sent(monkeypatch):
    """A fake FCM that logs to push_sends at the simulated time, as the real
    sender does at the real one."""
    monkeypatch.setenv("MILESTONES_MIN_BUILD", "150")
    calls: list[dict] = []

    def fake(device_id, title, body, data=None, channel_id=None, visibility=None):
        calls.append({"device": device_id, "title": title, "body": body, "data": data,
                      "visibility": visibility})
        conn = get_conn()
        conn.execute("INSERT INTO push_sends (device_id, kind, sent_at) VALUES (?, ?, ?)",
                     (device_id, (data or {}).get("type"), mp._sql_ts(NOW["t"])))
        conn.commit()
        conn.close()
        return {"ok": True, "sent": True, "message_id": "m1"}

    monkeypatch.setattr(push_sender, "send_to_device", fake)
    return calls


def _family(birth_month, *, device=DEVICE, gender=None, offset=180, build=200, lang=None,
            age_group="7-9", token=True):
    cid = add_child_row(age_group, device=device, birth_month=birth_month, gender=gender)
    conn = get_conn()
    try:
        if token:
            conn.execute("INSERT OR REPLACE INTO push_tokens (device_id, token, build_number) "
                         "VALUES (?, 'fcm-token', ?)", (device, build))
        if offset is not None or lang is not None:
            conn.execute("INSERT OR REPLACE INTO program_settings (device_id, tz_offset_minutes, "
                         "lang) VALUES (?, ?, ?)", (device, offset, lang))
        conn.commit()
    finally:
        conn.close()
    return cid


def _run(iso=None, **kw):
    if iso:
        _at(iso)
    return mp.run_due_milestones(NOW["t"], **kw)


def test_the_hour_sits_inside_the_quiet_hours():
    assert mp.LOCAL_DAY_START <= mp.MILESTONE_LOCAL_HOUR < mp.LOCAL_DAY_END
    assert (mp.LOCAL_DAY_START, mp.LOCAL_DAY_END) == (9, 21)


def test_nothing_is_sent_until_the_min_build_is_set(monkeypatch, sent):
    monkeypatch.delenv("MILESTONES_MIN_BUILD")
    _family("2020-03")
    assert _run("2027-02-01T17:00:00") == {"sent": 0, "off": True}
    assert sent == []


def test_it_sends_at_the_familys_eight_pm_with_the_contents_alert(sent):
    cid = _family("2020-03")
    assert _run("2027-02-01T16:00:00")["not_this_hour"] == 1      # 19:00 local
    out = _run("2027-02-01T17:30:00")                             # 20:30 local
    assert out["sent"] == 1 and len(sent) == 1
    push = sent[0]
    assert push["title"] == "يبلغ السابعة الشهر القادم"            # the content's alert
    assert push["data"] == {"type": "milestone", "kind": "milestone",
                            "link": f"/milestones/{cid}/prayer_start",
                            "child_id": str(cid), "milestone_key": "prayer_start"}
    assert push["visibility"] == "private"
    alert = rows("milestone_alerts", "child_id = ?", (cid,))[0]
    assert (alert["status"], alert["alert_key"]) == ("sent", "prayer_start")


def test_it_speaks_the_familys_language(sent):
    _family("2020-03", lang="en")
    _run("2027-02-01T17:00:00")
    assert sent[0]["title"] == "Turning seven next month"


@pytest.mark.parametrize("utc_hour,offset,expected", [
    (20, 0, 1), (19, 0, 0), (21, 0, 0),
    (1, -300, 1),       # 20:00 in New York is 01:00 UTC the next day
    (12, 480, 1),       # 20:00 in Kuala Lumpur
])
def test_the_hour_is_the_familys_not_the_servers(sent, utc_hour, offset, expected):
    _family("2020-03", offset=offset)
    day = "02" if utc_hour != 1 else "03"
    assert _run(f"2027-02-{day}T{utc_hour:02d}:00:00")["sent"] == expected


def test_an_unknown_offset_is_never_guessed(sent):
    _family("2020-03", offset=None)
    for hour in range(24):
        assert _run(f"2027-02-02T{hour:02d}:00:00")["sent"] == 0
    assert sent == []


def test_the_child_mode_offset_is_used_when_no_program_call_reported_one(sent):
    cid = _family("2020-03", offset=None)
    conn = get_conn()
    conn.execute("INSERT INTO child_screen_sessions (device_id, child_id, surface, local_date, "
                 "tz_offset_minutes, started_at, last_heartbeat_at) "
                 "VALUES (?, ?, 'habit', '2027-01-30', 120, '2027-01-30T10:00:00+00:00', "
                 "'2027-01-30T10:00:00+00:00')", (DEVICE, cid))
    conn.commit()
    conn.close()
    assert _run("2027-02-01T18:00:00")["sent"] == 1


@pytest.mark.parametrize("build,token", [(149, True), (None, True), (200, False)])
def test_old_builds_and_devices_without_a_token_are_not_candidates(sent, build, token):
    _family("2020-03", build=build, token=token)
    out = _run("2027-02-01T17:00:00")
    assert out["sent"] == 0 and sent == []


def test_no_birth_month_no_push(sent):
    _family(None)
    assert _run("2027-02-01T17:00:00")["sent"] == 0


def test_one_push_a_day_whoever_sent_the_first(sent):
    _family("2020-03")
    conn = get_conn()
    conn.execute("INSERT INTO push_sends (device_id, kind, sent_at) "
                 "VALUES (?, 'streak_at_risk', ?)", (DEVICE, "2027-02-01 07:00:00"))
    conn.commit()
    conn.close()
    assert _run("2027-02-01T17:00:00")["capped"] == 1
    assert _run("2027-02-02T17:00:00")["sent"] == 1


def test_a_waiting_mission_does_not_hold_the_milestone_back(sent):
    """The digest no longer counts a milestone push in its own cap, so the
    milestone need not stand aside for it (PR #32 review)."""
    cid = _family("2020-03")
    conn = get_conn()
    conn.execute("INSERT INTO child_missions (device_id, child_id, mission_key, local_date, "
                 "status) VALUES (?, ?, 'mission_7-9_green_hunt', '2027-02-01', 'claimed')",
                 (DEVICE, cid))
    conn.commit()
    conn.close()
    assert _run("2027-02-01T17:00:00")["sent"] == 1


def test_a_closed_window_is_not_caught_up(sent):
    _family("2020-03")
    # 1 March is the birthday month itself: "turning seven next month" is
    # wrong now, so it is not sent late.
    assert _run("2027-03-01T17:00:00")["sent"] == 0


def test_one_milestone_a_week_per_device_lowest_order_first(sent):
    a = _family("2020-03")             # prayer_start (order 3), window February
    b = _family("2017-03")             # first_fasting (4) to 8 Feb, age_ten (7) in February
    assert _run("2027-02-01T17:00:00")["sent"] == 1
    assert sent[0]["data"]["child_id"] == str(a)           # order 3 beats 4 and 7
    assert _run("2027-02-04T17:00:00")["capped"] == 1      # same week
    assert _run("2027-02-08T17:00:00")["capped"] == 1      # exactly seven days: still
    assert _run("2027-02-08T17:30:00")["sent"] == 1        # a week on
    # first_fasting's window closed on 8 February; age_ten's is still open.
    assert (sent[1]["data"]["child_id"], sent[1]["data"]["milestone_key"]) == (str(b), "age_ten")


def test_one_milestone_a_month_per_child_the_other_waits(sent, monkeypatch):
    monkeypatch.setattr(mp, "DEVICE_EVERY_DAYS", 0)
    cid = _family("2017-03")       # first_fasting window to 8 Feb, age_ten from 1 Feb
    assert _run("2027-02-01T17:00:00")["sent"] == 1
    assert sent[0]["data"]["milestone_key"] == "first_fasting"      # order 4 before 7
    for day in ("02", "15", "28"):
        out = _run(f"2027-02-{day}T17:00:00")
        assert out["sent"] == 0 and out["nothing_due"] == 1
    assert [r["milestone_key"] for r in rows("milestone_alerts", "child_id = ?", (cid,))] \
        == ["first_fasting"]


def test_the_same_milestone_is_never_sent_twice(sent, monkeypatch):
    monkeypatch.setattr(mp, "DEVICE_EVERY_DAYS", 0)
    monkeypatch.setattr(mp, "CHILD_EVERY_DAYS", 0)
    monkeypatch.setattr(mp, "ONE_PUSH_A_DAY", mp.ONE_PUSH_A_DAY * 0)
    _family("2020-03")
    assert _run("2027-02-01T17:00:00")["sent"] == 1
    assert _run("2027-02-01T17:10:00")["sent"] == 0
    assert _run("2027-02-10T17:00:00")["sent"] == 0
    assert len(sent) == 1


def test_a_claim_left_by_a_crash_is_not_resent(sent):
    """At most once: a worker that died between the claim and the send leaves
    the claim, and nothing sends it again."""
    cid = _family("2020-03")
    conn = get_conn()
    conn.execute("INSERT INTO milestone_alerts (device_id, child_id, alert_key, milestone_key, "
                 "status, claimed_at) VALUES (?, ?, 'prayer_start', 'prayer_start', 'claimed', "
                 "'2027-01-01 10:00:00')", (DEVICE, cid))
    conn.commit()
    conn.close()
    assert _run("2027-02-01T17:00:00")["sent"] == 0 and sent == []


def test_two_workers_at_the_same_tick_send_once(monkeypatch):
    monkeypatch.setenv("MILESTONES_MIN_BUILD", "150")
    _family("2020-03")
    _family("2019-01", gender="female")
    calls = []
    lock = threading.Lock()

    def slow(device_id, title, body, data=None, channel_id=None, visibility=None):
        time.sleep(0.3)                                   # the FCM round trip
        with lock:
            calls.append(data["milestone_key"])
        return {"ok": True, "sent": True}

    monkeypatch.setattr(push_sender, "send_to_device", slow)
    now = _at("2027-02-01T17:00:00")
    barrier = threading.Barrier(2)
    results = []

    def worker():
        barrier.wait()
        results.append(mp.run_due_milestones(now))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert calls == ["prayer_start"]
    assert sum(r["sent"] for r in results) == 1
    assert len(rows("milestone_alerts")) == 1


def test_a_claim_landing_between_the_check_and_the_claim_still_caps_the_week(sent, monkeypatch):
    """The interleaving the threaded test cannot force: worker A claims child
    a's milestone after worker B read the device as uncapped but before B
    picked — so B, seeing a's milestone taken, picks child b's instead. The
    weekly cap is re-checked inside B's claim transaction, so B stops."""
    a = _family("2020-03")             # prayer_start, order 3
    _family("2017-03")                 # age_ten / first_fasting for the other child
    real_state = mp._device_state

    def stale_state(device_id, now):
        state = real_state(device_id, now)
        conn = get_conn()                                  # A's claim lands now
        conn.execute("INSERT INTO milestone_alerts (device_id, child_id, alert_key, "
                     "milestone_key, status, claimed_at) VALUES (?, ?, 'prayer_start', "
                     "'prayer_start', 'claimed', ?)", (device_id, a, mp._sql_ts(now)))
        conn.commit()
        conn.close()
        return state                                       # …after B's read

    monkeypatch.setattr(mp, "_device_state", stale_state)
    out = _run("2027-02-01T17:00:00")
    assert out["sent"] == 0 and sent == []
    assert [r["child_id"] for r in rows("milestone_alerts")] == [a]


def test_a_failed_send_is_released_and_retried(sent, monkeypatch):
    cid = _family("2020-03")
    real = push_sender.send_to_device
    monkeypatch.setattr(push_sender, "send_to_device",
                        lambda *a, **k: {"ok": False, "error": "TimeoutError"})
    out = _run("2027-02-01T17:00:00")
    assert out["failed"] == 1 and rows("milestone_alerts", "child_id = ?", (cid,)) == []
    monkeypatch.setattr(push_sender, "send_to_device", real)
    assert _run("2027-02-02T17:00:00")["sent"] == 1


def test_gendered_and_puberty_rules_hold_in_the_push(sent):
    unknown = _family("2018-11", age_group="7-9")           # puberty_* due Oct/Nov 2026…
    out = _run("2026-10-15T17:00:00")
    assert out["sent"] == 0                                 # gender unknown: not sent
    conn = get_conn()
    conn.execute("UPDATE child_profiles SET gender = 'female' WHERE id = ?", (unknown,))
    conn.execute("INSERT INTO program_children (child_id, device_id, reached_puberty) "
                 "VALUES (?, ?, 1)", (unknown, DEVICE))
    conn.commit()
    conn.close()
    assert _run("2026-10-16T17:00:00")["sent"] == 0        # puberty marked: retired
    conn = get_conn()
    conn.execute("UPDATE program_children SET reached_puberty = 0 WHERE child_id = ?", (unknown,))
    conn.commit()
    conn.close()
    assert _run("2026-10-17T17:00:00")["sent"] == 1
    assert sent[0]["data"]["milestone_key"] == "puberty_girls"


def test_the_backend_loop_runs_the_sweep():
    from app import main
    jobs = dict(main._LOCAL_HOUR_JOBS)
    assert jobs["Milestone push"] is mp.run_due_milestones
    assert jobs["Mission digest"].__name__ == "run_due_digests"


def test_a_dry_run_counts_without_sending_or_claiming(sent):
    _family("2020-03")
    out = _run("2027-02-01T17:00:00", dry_run=True)
    assert out["would_send"] == 1 and sent == [] and rows("milestone_alerts") == []
