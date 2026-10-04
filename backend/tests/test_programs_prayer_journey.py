"""«رحلة الصلاة» — tracks, stages, the child's tasks in the mission loop, graduation.

Two families of tests. The first is the program's own rules: who starts
where, how stages move, when graduation opens — and that none of it is
punitive (going back is silent, the weekly goal is not a gate). The second is
the integration the content was written for: a prayer task is a child_missions
row, so the child's «صلّيتها» must reach the parent's evening list, the batch
confirmation, the coins and the digest — without ever displacing the day's
off-screen mission card.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import child_missions as cm
from app.services import mission_digest
from app.services import prayer_journey as pj
from app.services import programs_common as pc
from tests.programs_support import (DEVICE, OTHER, add_child, child_headers, client, freeze,
                                    rows)


def _view(c, cid, **params):
    r = c.get(f"/api/children/{cid}/prayer-journey", params={"tz_offset_minutes": 0, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _enrol(c, cid, **body):
    return c.post(f"/api/children/{cid}/prayer-journey/enrol",
                  params={"tz_offset_minutes": 0}, json=body)


def _stage(c, cid, stage):
    return c.put(f"/api/children/{cid}/prayer-journey/stage",
                 params={"tz_offset_minutes": 0}, json={"stage": stage})


def _child_today(c, cid, lang=None):
    params = {"tz_offset_minutes": 0}
    if lang:
        params["lang"] = lang
    r = c.get("/api/value-tracking/child-mode/prayer/today", params=params,
              headers=child_headers(cid))
    assert r.status_code == 200, r.text
    return r.json()


def _claim(c, cid, task_id):
    return c.post("/api/value-tracking/child-mode/prayer/claim",
                  params={"task_id": task_id, "tz_offset_minutes": 0},
                  headers=child_headers(cid))


# ── Who starts where ───────────────────────────────────────────────────────

@pytest.mark.parametrize("birth_month,track", [
    ("2023-05", None),            # 3y5m — under four: not shown
    ("2022-09", "preparation"),   # 4y1m
    ("2019-10", "journey"),       # 7y0m — in the birthday month
    ("2016-10", "journey"),       # 10y0m — still the journey
    ("2015-10", "ownership"),     # 11y
    ("2011-10", "ownership"),     # 15y
    ("2010-10", None),            # 16y — over fifteen: not shown
])
def test_age_decides_the_track_when_the_birth_month_is_known(monkeypatch, birth_month, track):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    out = _view(c, add_child(c, age_group="7-9", birth_month=birth_month))
    assert out["age"]["basis"] == "birth_month"
    assert out["eligible_track"] == track


@pytest.mark.parametrize("band,track", [
    ("prenatal-1", None), ("2-3", None), ("4-6", "preparation"), ("7-9", "journey"),
    ("10-12", "ownership"), ("13-15", "ownership"), ("16-18", None), ("unspecified", None),
])
def test_the_band_decides_without_one(band, track):
    c = client()
    out = _view(c, add_child(c, age_group=band))
    assert out["age"]["basis"] == "age_group" and out["eligible_track"] == track


def test_preparation_shows_activities_and_has_nothing_to_record():
    c = client()
    cid = add_child(c, age_group="4-6")
    out = _view(c, cid, lang="en")
    assert out["preparation"]["activities"] and out["stage"] is None
    assert _enrol(c, cid).status_code == 200
    assert _view(c, cid)["enrolment"]["track"] == "preparation"
    assert _child_today(c, cid) == {"date": _child_today(c, cid)["date"], "available": True,
                                    "enrolled": False, "track": "preparation", "tasks": []}
    assert _claim(c, cid, "prayer_s1_pray_beside").json()["detail"]["error"] == "not_enrolled"


def test_enrolment_respects_age_and_never_starts_the_journey_before_seven():
    c = client()
    toddler = add_child(c, age_group="2-3")
    assert _enrol(c, toddler).json()["detail"]["error"] == "not_eligible"
    five = add_child(c, age_group="4-6")
    r = _enrol(c, five, track="journey")
    assert r.status_code == 409 and r.json()["detail"] == {
        "error": "track_not_for_age", "allowed_tracks": ["preparation"]}
    eight = add_child(c, age_group="7-9")
    assert _enrol(c, eight, track="ownership").json()["detail"]["error"] == "track_not_for_age"
    # A start stage means something only on the journey.
    r = _enrol(c, five, start_stage=2)
    assert r.status_code == 422 and r.json()["detail"]["error"] == "stage_only_for_journey"


def test_an_older_child_who_does_not_pray_yet_may_take_the_journey_mid_way():
    c = client()
    cid = add_child(c, age_group="10-12")
    view = _view(c, cid)
    assert view["allowed_tracks"] == ["ownership", "journey"]
    r = _enrol(c, cid, track="journey", start_stage=3)
    assert r.status_code == 200
    assert r.json()["enrolment"]["stage"] == 3 and r.json()["stage"]["key"] == "words_and_movements"


def test_enrolling_twice_needs_restart_and_restart_closes_the_old_row(monkeypatch):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    cid = add_child(c)
    assert _enrol(c, cid).status_code == 200
    r = _enrol(c, cid)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "already_enrolled"
    assert _enrol(c, cid, start_stage=2, restart=True).status_code == 200
    states = [(r["status"], r["stage"]) for r in rows("prayer_journeys", "child_id = ?", (cid,))]
    assert states == [("ended", 1), ("active", 2)]


# ── Stages: forward on the content's schedule, back without a word ─────────

def test_advancing_is_suggested_when_the_stages_weeks_are_up(monkeypatch):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    adv = _view(c, cid)["advancement"]
    assert adv == {"days_in_stage": 0, "stage_planned_days": 14, "next_stage": 2,
                   "advance_suggested": False, "advance_suggested_on": "2026-10-18",
                   "can_graduate": False, "graduation_available_on": None}
    freeze(monkeypatch, "2026-10-17T12:00:00")
    assert _view(c, cid)["advancement"]["advance_suggested"] is False
    freeze(monkeypatch, "2026-10-18T12:00:00")
    assert _view(c, cid)["advancement"]["advance_suggested"] is True


def test_the_weekly_goal_is_not_a_gate_on_moving_on(monkeypatch):
    """per_week is "a goal, not a condition": a parent may move on after a
    week with nothing recorded."""
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    r = _stage(c, cid, 2)
    assert r.status_code == 200 and r.json()["enrolment"]["stage"] == 2
    assert r.json()["enrolment"]["stage_started_on"] == "2026-10-04"


def test_one_stage_at_a_time_forward_any_stage_back(monkeypatch):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    cid = add_child(c)
    _enrol(c, cid, start_stage=2)
    r = _stage(c, cid, 4)
    assert r.status_code == 409 and r.json()["detail"] == {
        "error": "one_stage_at_a_time", "next_stage": 3}
    assert _stage(c, cid, 3).status_code == 200
    assert _stage(c, cid, 1).json()["enrolment"]["stage"] == 1   # back two: fine
    assert _stage(c, cid, 1).status_code == 200                  # same: no-op
    assert _stage(c, cid, 7).status_code == 422
    assert c.put(f"/api/children/{add_child(c, age_group='4-6')}/prayer-journey/stage",
                 json={"stage": 2}).json()["detail"]["error"] == "not_in_journey"


def test_going_back_is_silent_to_the_child(monkeypatch):
    """«ارجع إلى صلاتين أسبوعًا آخر، دون أن تقول له إنه تراجع» — nothing the child
    sees carries a stage number, and nothing records the step back."""
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    cid = add_child(c)
    _enrol(c, cid, start_stage=4)
    _stage(c, cid, 3)
    child_view = _child_today(c, cid)
    assert set(child_view) == {"date", "available", "enrolled", "track", "tasks"}
    assert [t["task_id"] for t in child_view["tasks"]] == [
        "prayer_s3_recite_fatiha", "prayer_s3_two_prayers"]
    text = str(child_view)
    for parent_only in ("if_struggling", "stage", "goal", "encouragement", "covenant"):
        assert parent_only not in text
    assert [r["status"] for r in rows("prayer_journeys", "child_id = ?", (cid,))] == ["active"]


# ── Graduation ─────────────────────────────────────────────────────────────

def test_graduation_opens_after_the_last_stages_weeks_and_starts_ownership(monkeypatch):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    cid = add_child(c)
    _enrol(c, cid, start_stage=5)
    url = f"/api/children/{cid}/prayer-journey/graduate"
    assert c.post(url, params={"tz_offset_minutes": 0}).json()["detail"]["error"] \
        == "graduation_not_yet"
    _stage(c, cid, 6)
    r = c.post(url, params={"tz_offset_minutes": 0})
    assert r.status_code == 409 and r.json()["detail"] == {
        "error": "graduation_not_yet", "last_stage": 6, "available_on": "2026-10-18"}
    freeze(monkeypatch, "2026-10-18T12:00:00")
    view = _view(c, cid)
    assert view["advancement"]["can_graduate"] is True
    r = c.post(url, params={"tz_offset_minutes": 0, "lang": "en"})
    assert r.status_code == 200
    out = r.json()
    assert out["enrolment"]["track"] == "ownership" and out["graduated_on"] == "2026-10-18"
    assert out["graduation"]["journey_milestone_keys"] == ["keeps_prayer"]
    assert out["graduation"]["certificate_text"].startswith("Prayer Journey certificate")
    assert [t["task_id"] for t in out["tasks"]] == ["prayer_own_five", "prayer_own_weekly_review"]
    assert [(r["track"], r["status"]) for r in rows("prayer_journeys", "child_id = ?", (cid,))] \
        == [("journey", "graduated"), ("ownership", "active")]


def test_stopping_the_journey(monkeypatch):
    c = client()
    cid = add_child(c)
    url = f"/api/children/{cid}/prayer-journey"
    assert c.delete(url).json()["detail"]["error"] == "not_enrolled"
    _enrol(c, cid)
    r = c.delete(url)
    assert r.status_code == 200 and r.json()["enrolment"] is None
    assert _child_today(c, cid)["enrolled"] is False


# ── The child's tasks ride the mission loop ────────────────────────────────

def test_a_task_has_ceil_per_week_over_seven_slots_a_day(monkeypatch):
    freeze(monkeypatch, "2026-10-04T12:00:00")
    c = client()
    cid = add_child(c)
    _enrol(c, cid, start_stage=3)
    tasks = {t["task_id"]: t for t in _child_today(c, cid)["tasks"]}
    assert tasks["prayer_s3_two_prayers"]["per_day"] == 2           # 14 a week
    assert tasks["prayer_s3_recite_fatiha"]["week_limit"] == 3      # 3 a week
    for slot in (1, 2):
        r = _claim(c, cid, "prayer_s3_two_prayers")
        assert r.status_code == 200 and r.json()["slot"] == slot
    r = _claim(c, cid, "prayer_s3_two_prayers")
    assert r.status_code == 409 and r.json()["detail"]["error"] == "day_complete"
    keys = sorted(r["mission_key"] for r in rows("child_missions", "child_id = ?", (cid,)))
    assert keys == ["prayer_s3_two_prayers#1", "prayer_s3_two_prayers#2"]
    assert {r["source"] for r in rows("child_missions", "child_id = ?", (cid,))} \
        == {"prayer_journey"}


def test_an_n_times_a_week_task_is_complete_for_the_week(monkeypatch):
    c = client()
    cid = add_child(c)
    freeze(monkeypatch, "2026-10-04T12:00:00")
    _enrol(c, cid)                                    # stage 1: my_place once a week
    assert _claim(c, cid, "prayer_s1_my_place").status_code == 200
    freeze(monkeypatch, "2026-10-05T12:00:00")
    r = _claim(c, cid, "prayer_s1_my_place")
    assert r.status_code == 409 and r.json()["detail"]["error"] == "week_complete"
    task = next(t for t in _child_today(c, cid)["tasks"] if t["task_id"] == "prayer_s1_my_place")
    assert task["slots_left_today"] == 0 and task["recorded_this_week"] == 1
    freeze(monkeypatch, "2026-10-11T12:00:00")        # week 2 of the journey
    assert _claim(c, cid, "prayer_s1_my_place").status_code == 200


def test_only_the_current_stages_tasks_can_be_recorded():
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    r = _claim(c, cid, "prayer_s5_five_prayers")
    assert r.status_code == 409 and r.json()["detail"]["error"] == "task_not_current"


def test_a_child_token_only_reaches_its_own_child():
    c = client()
    mine = add_child(c)
    _enrol(c, mine)
    theirs = add_child(c, device=OTHER)
    # A token minted for the other family's child cannot be replayed as mine:
    # v2 child tokens (PR #26) take the device from the child's own profile,
    # so it does not even verify — 401 before any route runs.
    r = c.get("/api/value-tracking/child-mode/prayer/today",
              headers=child_headers(theirs, device=DEVICE))
    assert r.status_code == 401


def test_the_parent_sees_the_task_in_the_evening_list_in_their_language(monkeypatch):
    c = client()
    cid = add_child(c, name="أحمد")
    _enrol(c, cid)
    mission_id = _claim(c, cid, "prayer_s1_pray_beside").json()["mission_id"]
    for lang, title in (("en", "I pray beside Mum or Dad"), (None, "أصلّي بجانب أبي أو أمي")):
        pending = c.get("/api/children/missions/pending",
                        params={"lang": lang} if lang else {}).json()["pending"]
        assert len(pending) == 1
        card = pending[0]
        assert card["mission_id"] == mission_id and card["title_ar"] == title
        assert (card["program"], card["task_id"], card["slot"], card["coins"]) == (
            "prayer_journey", "prayer_s1_pray_beside", 1, 10)
        assert card["child_name"] == "أحمد"


def test_confirming_returns_the_coins_and_a_not_yet_earns_none():
    c = client()
    cid = add_child(c)
    _enrol(c, cid, start_stage=3)
    a = _claim(c, cid, "prayer_s3_two_prayers").json()["mission_id"]
    b = _claim(c, cid, "prayer_s3_two_prayers").json()["mission_id"]
    r = c.post("/api/children/missions/confirm",
               json={"items": [{"mission_id": a, "confirmed": True},
                               {"mission_id": b, "confirmed": False}]})
    body = r.json()
    assert body["settled"] == 2
    assert body["coins"] == [{"mission_id": a, "child_id": cid,
                              "task_id": "prayer_s3_two_prayers", "coins": 6}]
    view = _view(c, cid)
    assert view["coins"] == {"confirmed_in_stage": 6, "covenant_target": 150}
    assert view["pending_confirmations"] == 0
    # "Not yet" frees the slot: nothing counts against the child.
    task = next(t for t in view["tasks"] if t["task_id"] == "prayer_s3_two_prayers")
    assert task["today"] == {"recorded": 1, "confirmed": 1, "slots_left": 1}


def test_a_prayer_task_never_becomes_the_days_mission_card(monkeypatch):
    """today_mission reads the newest row of the day; without the source
    filter a prayer recorded after the card was dealt would replace it."""
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    today = pc.local_today(0).isoformat()
    card = cm.today_mission(DEVICE, cid, "7-9", today)
    assert card["mission_key"].startswith("mission_")
    _claim(c, cid, "prayer_s1_pray_beside")
    again = cm.today_mission(DEVICE, cid, "7-9", today)
    assert again["mission_id"] == card["mission_id"]
    assert cm.today_mission(DEVICE, cid, "7-9", today, assign=False)["mission_id"] \
        == card["mission_id"]


def test_a_prayer_recorded_first_does_not_stop_the_day_card_being_dealt():
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    _claim(c, cid, "prayer_s1_pray_beside")
    today = pc.local_today(0).isoformat()
    assert cm.today_mission(DEVICE, cid, "7-9", today, assign=False) is None
    assert cm.today_mission(DEVICE, cid, "7-9", today)["mission_key"].startswith("mission_")


def test_prayer_minutes_are_not_off_screen_leverage():
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    mid = _claim(c, cid, "prayer_s1_pray_beside").json()["mission_id"]
    cm.confirm_batch(DEVICE, [{"mission_id": mid}])
    lev = cm.leverage(cid, "2000-01-01", screen_seconds=600)
    assert lev["confirmed_missions"] == 0 and lev["off_screen_minutes"] == 0


def test_the_digest_tells_the_parent_a_prayer_is_waiting(monkeypatch):
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    _claim(c, cid, "prayer_s1_pray_beside")
    assert DEVICE in mission_digest.devices_with_pending()
    sent = []
    monkeypatch.setattr(mission_digest.push_sender, "recently_pushed_since", lambda _c: set())
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda d, t, b, data=None, **k: sent.append((d, data)) or
                        {"ok": True, "sent": True})
    assert mission_digest.send_digest(DEVICE)["sent"] is True
    assert sent[0][1]["link"] == "/missions" and sent[0][1]["pending"] == "1"


def test_an_unanswered_prayer_card_expires_quietly(monkeypatch):
    c = client()
    cid = add_child(c)
    _enrol(c, cid)
    _claim(c, cid, "prayer_s1_pray_beside")
    later = datetime.now(timezone.utc) + timedelta(hours=49)
    assert cm.expire_stale(later) == 1
    assert c.get("/api/children/missions/pending").json()["pending"] == []


def test_deleting_the_child_takes_the_journey_and_its_tasks(monkeypatch):
    """From a session proven to hold the phone (PR #26): privacy.erase_child
    discovers prayer_journeys and child_missions by child_id."""
    from app.routers import children
    monkeypatch.setattr(children, "confirmed_session", lambda request: True)
    c = client()
    cid = add_child(c)
    keep = add_child(c, name="سارة")
    _enrol(c, cid)
    _enrol(c, keep)
    _claim(c, cid, "prayer_s1_pray_beside")
    _claim(c, keep, "prayer_s1_pray_beside")
    assert c.delete(f"/api/children/{cid}").status_code == 200
    assert rows("prayer_journeys", "child_id = ?", (cid,)) == []
    assert rows("child_missions", "child_id = ?", (cid,)) == []
    assert len(rows("prayer_journeys", "child_id = ?", (keep,))) == 1
    assert len(rows("child_missions", "child_id = ?", (keep,))) == 1


def test_the_content_keeps_a_stages_day_under_the_apps_coin_cap():
    """The server caps slots at ceil(per_week / 7); with the content's coins
    that keeps every stage's day ≤ CoinsService.dailyEarnCap (60)."""
    doc = pc.load_program(pj.PROGRAM)
    for tasks in [s["child_tasks"] for s in doc["stages"]] + [doc["ownership"]["child_tasks"]]:
        assert sum(t["coins"] * pj.per_day(t) for t in tasks) <= doc["reward_policy"]["daily_cap"]
