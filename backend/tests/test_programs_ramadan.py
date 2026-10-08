"""«رمضان العائلة» over HTTP — the calendar, the day, the ladder, the marks, the card.

The dates are the hard part, so most tests pin the clock (programs_common
._utcnow) and the family's UTC offset, and look at where the day turns: at the
family's midnight rather than the server's, on the evening before its day for
the nights of the last ten, and a day late for a family whose country sighted
the moon a day late.
"""
import json
import os

import pytest

from app.services import programs_common as pc
from app.services import ramadan_program as rp
from tests.programs_support import (DEVICE, OTHER, add_child, add_child_row, client,
                                    freeze, rows)

START = "2027-02-08"          # the content's estimate for 1448


@pytest.fixture(autouse=True)
def _clean_ramadan_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("RAMADAN_START_", "RAMADAN_DAYS_")) or name == "PROGRAMS_AS_OF_ENABLED":
            monkeypatch.delenv(name, raising=False)


def _today(c, cid, **params):
    r = c.get(f"/api/children/{cid}/ramadan/today", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _mark(c, mark, **body):
    return c.post("/api/programs/ramadan/marks", json={"mark": mark, **body})


# ── The calendar ───────────────────────────────────────────────────────────

def test_the_estimate_is_used_and_labelled_until_the_start_is_configured(monkeypatch):
    freeze(monkeypatch, "2027-01-20T12:00:00")
    c = client()
    cid = add_child(c)
    out = _today(c, cid, tz_offset_minutes=120)
    assert out["state"] == "upcoming"
    assert out["season"]["starts_on"] == START
    assert out["season"]["start_source"] == "estimate"
    assert out["days_until_start"] == 19
    assert out["kickoff"]["setup_steps"]
    assert out["content"] is None


def test_a_configured_start_wins_over_the_estimate(monkeypatch):
    monkeypatch.setenv("RAMADAN_START_1448", "2027-02-09")
    freeze(monkeypatch, "2027-02-09T10:00:00")
    c = client()
    out = _today(c, add_child(c), tz_offset_minutes=0)
    assert out["season"]["start_source"] == "configured"
    assert out["state"] == "ramadan" and out["day"] == 1


def test_a_malformed_start_is_ignored_not_fatal(monkeypatch):
    monkeypatch.setenv("RAMADAN_START_1448", "8 Feb 2027")
    monkeypatch.setenv("RAMADAN_DAYS_1448", "31")
    seasons = rp.server_seasons()
    s1448 = rp.season_by_year(seasons, 1448)
    assert s1448.start.isoformat() == START and s1448.start_source == "estimate"
    assert s1448.days == 30 and not s1448.days_confirmed


@pytest.mark.parametrize("days,eid", [("30", "2027-03-10"), ("29", "2027-03-09")])
def test_the_announced_month_length_places_eid(monkeypatch, days, eid):
    monkeypatch.setenv("RAMADAN_DAYS_1448", days)
    s1448 = rp.season_by_year(rp.server_seasons(), 1448)
    assert s1448.eid.isoformat() == eid and s1448.days_confirmed
    freeze(monkeypatch, f"{eid}T12:00:00")
    c = client()
    assert _today(c, add_child(c), tz_offset_minutes=0)["state"] == "eid"


def test_day_thirty_is_the_contents_may_not_occur_day(monkeypatch):
    freeze(monkeypatch, "2027-03-09T12:00:00")
    c = client()
    out = _today(c, add_child(c), tz_offset_minutes=0)
    assert out["day"] == 30 and out["content"]["may_not_occur"] is True
    assert out["season"]["days_confirmed"] is False


def test_the_bridge_runs_four_weeks_after_eid_then_counts_down_to_1449(monkeypatch):
    c = client()
    cid = add_child(c)
    for iso, week in (("2027-03-11", 1), ("2027-03-17", 1), ("2027-03-18", 2),
                      ("2027-04-07", 4)):
        freeze(monkeypatch, f"{iso}T12:00:00")
        out = _today(c, cid, tz_offset_minutes=0)
        assert (out["state"], out["after_week"]) == ("after", week), iso
        assert out["after"]["week"]["week"] == week
    # The day after the bridge is not off-season: the content carries 1449's
    # estimate, so the countdown to next Ramadan starts (PR #32 review).
    freeze(monkeypatch, "2027-04-08T12:00:00")
    out = _today(c, cid, tz_offset_minutes=0)
    assert (out["state"], out["season"]["hijri_year"]) == ("upcoming", 1449)
    assert (out["season"]["starts_on"], out["season"]["start_source"]) == ("2028-01-28",
                                                                           "estimate")
    assert out["days_until_start"] == 295
    # 1449's own bridge ends on 26 March 2028 (a leap year); after that, with
    # no 1450 estimate yet, the program is off-season.
    freeze(monkeypatch, "2028-03-26T12:00:00")
    assert _today(c, cid, tz_offset_minutes=0)["after_week"] == 4
    freeze(monkeypatch, "2028-03-27T12:00:00")
    assert _today(c, cid, tz_offset_minutes=0)["state"] == "off_season"


def test_next_years_start_makes_the_next_countdown(monkeypatch):
    monkeypatch.setenv("RAMADAN_START_1449", "2028-01-28")
    freeze(monkeypatch, "2027-06-01T12:00:00")
    c = client()
    out = _today(c, add_child(c), tz_offset_minutes=0)
    assert out["state"] == "upcoming" and out["season"]["hijri_year"] == 1449


# ── The family's midnight, not the server's ───────────────────────────────

@pytest.mark.parametrize("instant,offset,state,day", [
    ("2027-02-07T22:30:00", 120, "ramadan", 1),     # 00:30 in Cairo: day 1
    ("2027-02-07T22:30:00", 0, "upcoming", None),   # 22:30 in London: not yet
    ("2027-02-08T03:00:00", -300, "upcoming", None),  # 22:00 in New York
    ("2027-02-08T05:00:00", -300, "ramadan", 1),
    ("2027-02-08T16:30:00", 480, "ramadan", 2),     # 00:30 in Kuala Lumpur
    ("2027-03-09T23:59:00", 0, "ramadan", 30),
    ("2027-03-09T22:00:00", 180, "eid", None),      # 01:00 on Eid in Riyadh
])
def test_the_day_turns_at_the_familys_midnight(monkeypatch, instant, offset, state, day):
    freeze(monkeypatch, instant)
    c = client()
    out = _today(c, add_child(c), tz_offset_minutes=offset)
    assert (out["state"], out["day"]) == (state, day)


def test_without_an_offset_the_date_is_utc_and_nothing_is_stored(monkeypatch):
    freeze(monkeypatch, "2027-02-07T22:30:00")
    c = client()
    cid = add_child(c)
    out = _today(c, cid)
    assert out["state"] == "upcoming" and out["tz_offset_minutes"] is None
    assert rows("program_settings", "device_id = ?", (DEVICE,)) == []


def test_the_offset_and_language_are_remembered_and_not_erased(monkeypatch):
    freeze(monkeypatch, "2027-02-10T12:00:00")
    c = client()
    cid = add_child(c)
    _today(c, cid, tz_offset_minutes=180, lang="en")
    _today(c, cid)                                     # no offset, no lang
    saved = rows("program_settings", "device_id = ?", (DEVICE,))[0]
    assert (saved["tz_offset_minutes"], saved["lang"]) == (180, "en")


@pytest.mark.parametrize("offset", [-721, 841])
def test_an_impossible_offset_is_refused(offset):
    c = client()
    r = c.get(f"/api/children/{add_child(c)}/ramadan/today",
              params={"tz_offset_minutes": offset})
    assert r.status_code == 422


def test_a_family_that_sighted_a_day_late_moves_its_own_month(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    cid = add_child(c)
    assert _today(c, cid, tz_offset_minutes=0)["day"] == 1
    r = c.put("/api/programs/ramadan/settings", params={"tz_offset_minutes": 0},
              json={"start_shift_days": 1})
    assert r.status_code == 200 and r.json()["season"]["shift_days"] == 1
    out = _today(c, cid, tz_offset_minutes=0)
    assert out["state"] == "upcoming" and out["days_until_start"] == 1
    # Another family is untouched.
    other = add_child(c, device=OTHER)
    r = c.get(f"/api/children/{other}/ramadan/today", params={"tz_offset_minutes": 0},
              headers={"X-Test-Device": OTHER})
    assert r.json()["day"] == 1


def test_a_family_can_set_its_month_to_29_days_and_clear_it(monkeypatch):
    freeze(monkeypatch, "2027-03-09T12:00:00")     # day 30 by the server's month
    c = client()
    cid = add_child(c)
    r = c.put("/api/programs/ramadan/settings", json={"month_days": 29})
    assert r.json()["state"] == "eid"
    assert _today(c, cid, tz_offset_minutes=0)["state"] == "eid"
    r = c.put("/api/programs/ramadan/settings", json={"month_days": None})
    assert r.json()["state"] == "ramadan" and r.json()["day"] == 30


def test_settings_need_a_season_and_a_value(monkeypatch):
    c = client()
    assert c.put("/api/programs/ramadan/settings", json={}).status_code == 422
    assert c.put("/api/programs/ramadan/settings",
                 json={"start_shift_days": 2}).status_code == 422
    freeze(monkeypatch, "2028-04-01T12:00:00")          # after 1449's bridge
    r = c.put("/api/programs/ramadan/settings", json={"start_shift_days": 1})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "not_in_season"


def test_last_years_sighting_is_not_carried_into_a_new_season(monkeypatch):
    monkeypatch.setenv("RAMADAN_START_1449", "2028-01-28")
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    c.put("/api/programs/ramadan/settings", json={"start_shift_days": 1, "month_days": 29})
    s1449 = rp.season_by_year(rp.family_seasons(pc.device_settings(DEVICE)), 1449)
    assert s1449.shift_days == 0 and s1449.days == 30


# ── as_of: a QA override, off by default ───────────────────────────────────

def test_as_of_is_refused_unless_the_server_enables_it(monkeypatch):
    c = client()
    cid = add_child(c)
    r = c.get(f"/api/children/{cid}/ramadan/today", params={"as_of": "2027-02-10"})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "as_of_disabled"
    monkeypatch.setenv("PROGRAMS_AS_OF_ENABLED", "1")
    assert _today(c, cid, as_of="2027-02-10")["day"] == 3
    assert c.get(f"/api/children/{cid}/ramadan/today",
                 params={"as_of": "10/02/2027"}).status_code == 422


# ── Who sees which variant ─────────────────────────────────────────────────

@pytest.mark.parametrize("age_group,variant", [
    ("0-3", "0-3"), ("2-3", "0-3"), ("4-6", "4-6"), ("7-9", "7-9"), ("10-12", "10-12"),
    ("13-15", "13-15"), ("16-18", "13-15"), ("prenatal-1", None), ("unspecified", None),
])
def test_the_band_map_picks_the_variant(monkeypatch, age_group, variant):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    # The legacy "0-3" can no longer be created through the API, but four
    # production profiles still carry it — and the content maps it.
    cid = add_child_row(age_group) if age_group == "0-3" else add_child(c, age_group=age_group)
    out = _today(c, cid, tz_offset_minutes=0)
    assert out["variant_band"] == variant
    got = out["content"]["variant"]
    assert (got or {}).get("band") == variant
    if variant in ("0-3", "4-6"):
        assert got["addressed_to"] == "parent"
    elif variant:
        assert got["addressed_to"] == "child"
    # The family challenge and its note are there for everyone.
    assert out["content"]["family_challenge"]["steps"]
    assert out["content"]["parent_note"]["text"]


def test_a_known_birth_month_beats_a_stale_band(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    out = _today(c, add_child(c, age_group="4-6", birth_month="2019-12"),
                 tz_offset_minutes=0)
    assert out["age"] == {"basis": "birth_month", "band": "7-9", "months": 86, "years": 7}
    assert out["variant_band"] == "7-9"


def test_english_and_arabic_are_the_same_day(monkeypatch):
    freeze(monkeypatch, "2027-02-10T12:00:00")
    c = client()
    cid = add_child(c)
    ar = _today(c, cid, tz_offset_minutes=0)
    en = _today(c, cid, tz_offset_minutes=0, lang="en")
    assert en["title"] == "Family Ramadan" and ar["title"] != en["title"]
    for k in ("day", "key", "story_id", "tracks", "quran"):
        assert ar["content"][k] == en["content"][k]
    assert en["content"]["story_id"] == "abdullah_bismillah"


def test_a_day_with_hadith_carries_the_cards_not_quotes(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    note = _today(c, add_child(c), tz_offset_minutes=0, lang="en")["content"]["parent_note"]
    ids = [e["id"] for e in note["evidence"]]
    assert ids == ["h_intention", "h_ramadan_faith"]
    assert all(e["provenance"]["book"] == "البخاري" and e["meaning"] for e in note["evidence"])


def test_eid_has_its_own_payload(monkeypatch):
    freeze(monkeypatch, "2027-03-10T09:00:00")
    c = client()
    out = _today(c, add_child(c, age_group="10-12"), tz_offset_minutes=0)
    assert out["state"] == "eid" and out["eid"]["activities"]
    assert out["eid"]["variant"]["band"] == "10-12"
    assert {e["id"] for e in out["eid"]["evidence"]} == {"h_eid_dates", "h_zakat_fitr"}
    assert out["recap_available"] is True


def test_someone_elses_child_is_404():
    c = client()
    cid = add_child(c, device=OTHER)
    assert c.get(f"/api/children/{cid}/ramadan/today").status_code == 404


# ── «requires_feature»: only a feature both sides have is promised ─────────

@pytest.mark.parametrize("server,declared,shown", [
    (True, "weekly_plan", True),
    (True, None, False),
    (False, "weekly_plan", False),
    (True, "other, weekly_plan", True),
])
def test_week_four_promises_the_weekly_plan_only_when_it_exists(monkeypatch, server,
                                                                declared, shown):
    freeze(monkeypatch, "2027-04-01T12:00:00")              # bridge week 4
    c = client(with_weekly_plan=server)
    params = {"tz_offset_minutes": 0, "lang": "en"}
    if declared:
        params["features"] = declared
    week = _today(c, add_child(c), **params)["after"]["week"]
    assert week["week"] == 4 and week["requires_feature"] == "weekly_plan"
    assert week["feature_available"] is shown
    if shown:
        assert "weekly plan" in week["text"]
    else:
        assert week["text"].startswith("Keep up the two habits")


# ── The fasting ladder ─────────────────────────────────────────────────────

def _fasting(c, cid, **params):
    r = c.get(f"/api/children/{cid}/ramadan/fasting", params={"tz_offset_minutes": 0, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _set_step(c, cid, **body):
    return c.put(f"/api/children/{cid}/ramadan/fasting", params={"tz_offset_minutes": 0},
                 json=body)


def test_the_ladder_follows_the_band_and_the_age(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    seven = add_child(c, birth_month="2020-01")              # 7y1m on day 1
    out = _fasting(c, seven)
    assert out["ladder_band"] == "7-9" and out["fasts"] == "partial"
    eligible = {s["key"]: s["eligible"] for s in out["steps"]}
    assert eligible == {"morning_hours": True, "until_dhuhr": True, "until_asr": False}
    assert out["guidance"]["stop_signs"] and out["guidance"]["urgent_action"]
    r = _set_step(c, seven, step_key="until_asr")
    assert r.status_code == 422 and r.json()["detail"] == {
        "error": "step_not_for_age", "min_age_years": 9}
    # Unknown age: the parent decides; the step still says it is for nine.
    unknown = add_child(c)
    steps = {s["key"]: s for s in _fasting(c, unknown)["steps"]}
    assert steps["until_asr"]["eligible"] and steps["until_asr"]["min_age_years"] == 9


@pytest.mark.parametrize("age_group", ["0-3", "2-3", "4-6"])
def test_no_fasting_before_seven(monkeypatch, age_group):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    cid = add_child_row(age_group) if age_group == "0-3" else add_child(c, age_group=age_group)
    out = _fasting(c, cid)
    assert out["fasts"] == "no"
    assert all(s["until"] == "none" and s["approx_hours"] == 0 for s in out["steps"])


def test_prenatal_has_no_ladder_at_all(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    cid = add_child(c, age_group="prenatal-1")
    assert _today(c, cid, tz_offset_minutes=0)["fasting"] is None
    assert _set_step(c, cid, step_key="at_the_table").status_code == 422


def test_puberty_moves_any_child_to_the_13_15_ladder(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    cid = add_child(c, birth_month="2017-05")                # 9 years old
    r = _set_step(c, cid, reached_puberty=True)
    assert r.status_code == 200 and r.json()["ladder_band"] == "13-15"
    assert [s["key"] for s in r.json()["steps"]] == ["full_day_supported"]
    assert _set_step(c, cid, step_key="full_day_supported").status_code == 200
    # And it can be undone.
    assert _set_step(c, cid, reached_puberty=False).json()["ladder_band"] == "7-9"


@pytest.mark.parametrize("age_group", ["13-15", "16-18"])
def test_a_teen_not_marked_pubertal_stays_on_the_training_steps(monkeypatch, age_group):
    """The 13-15 ladder is the obligatory full month; its own summary says a
    child who has not reached puberty continues the 10-12 steps, with their
    weekly cap. Before PG-01 (2026-10-08) such a child got only the full month."""
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    cid = add_child(c, age_group=age_group)
    out = _fasting(c, cid)
    assert out["ladder_band"] == "10-12" and out["fasts"] == "partial_to_full"
    steps = {s["key"]: s for s in out["steps"]}
    assert "full_day_supported" not in steps
    assert steps["full_day_rest_days"]["max_days_per_week"] == 2
    assert _set_step(c, cid, step_key="full_day_supported").status_code == 422
    assert _set_step(c, cid, step_key="full_day_rest_days").status_code == 200
    r = _set_step(c, cid, reached_puberty=True)
    assert r.json()["ladder_band"] == "13-15"
    assert [s["key"] for s in r.json()["steps"]] == ["full_day_supported"]


def test_a_climb_is_counted_and_a_step_down_is_not(monkeypatch):
    c = client()
    cid = add_child(c, age_group="10-12")
    freeze(monkeypatch, "2027-02-01T12:00:00")               # before Ramadan
    assert _set_step(c, cid, step_key="until_dhuhr").json()["climbed"] is False
    freeze(monkeypatch, "2027-02-12T12:00:00")               # day 5
    assert _set_step(c, cid, step_key="until_asr").json()["climbed"] is True
    freeze(monkeypatch, "2027-02-13T12:00:00")
    assert _set_step(c, cid, step_key="until_dhuhr").json()["climbed"] is False
    marks = rows("ramadan_marks", "child_id = ?", (cid,))
    assert [(m["mark"], m["day"], m["value"]) for m in marks] == [
        ("fasting_step_up", 5, "until_asr")]


def test_practice_is_positive_only_and_suggests_rest_at_the_steps_cap(monkeypatch):
    c = client()
    cid = add_child(c, birth_month="2019-06")
    freeze(monkeypatch, "2027-02-10T12:00:00")               # day 3
    url = f"/api/children/{cid}/ramadan/fasting/practice"
    r = c.post(url, params={"tz_offset_minutes": 0}, json={})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "no_step_set"
    _set_step(c, cid, step_key="morning_hours")             # max 3 days a week
    for day in (1, 2):
        assert c.post(url, params={"tz_offset_minutes": 0}, json={"day": day}).status_code == 200
    r = c.post(url, params={"tz_offset_minutes": 0}, json={})
    body = r.json()
    assert (body["day"], body["practised_today"], body["practised_this_week"],
            body["rest_suggested"]) == (3, True, 3, True)
    # A future day cannot be ticked; undo removes, and records nothing else.
    assert c.post(url, params={"tz_offset_minutes": 0}, json={"day": 4}).status_code == 422
    r = c.post(url, params={"tz_offset_minutes": 0}, json={"done": False})
    assert r.json()["practised_today"] is False
    assert {m["mark"] for m in rows("ramadan_marks", "child_id = ?", (cid,))} == {
        "fasting_practised"}


def test_practice_before_ramadan_is_refused(monkeypatch):
    freeze(monkeypatch, "2027-01-20T12:00:00")
    c = client()
    cid = add_child(c)
    _set_step(c, cid, step_key="morning_hours")
    r = c.post(f"/api/children/{cid}/ramadan/fasting/practice", json={})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "not_in_season"


# ── Family marks ───────────────────────────────────────────────────────────

def test_a_family_mark_is_the_familys_on_every_childs_card(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")
    c = client()
    a, b = add_child(c), add_child(c, age_group="4-6", name="سارة")
    r = _mark(c, "challenge_done")
    assert r.status_code == 200 and r.json()["marks"]["challenge_done"] is True
    assert _mark(c, "challenge_done").status_code == 200        # idempotent
    for cid in (a, b):
        assert _today(c, cid, tz_offset_minutes=0)["marks"] == {
            "challenge_done": True, "wird_done": False, "juz_read": False}
    assert len(rows("ramadan_marks", "mark = 'challenge_done'")) == 1
    r = _mark(c, "challenge_done", done=False)
    assert r.json()["marks"]["challenge_done"] is False


def test_marks_are_refused_where_the_card_does_not_offer_them(monkeypatch):
    freeze(monkeypatch, "2027-02-08T12:00:00")                   # day 1
    c = client()
    assert _mark(c, "story_heard").json()["detail"]["error"] == "mark_not_on_this_day"
    assert _mark(c, "wird_done", day=2).json()["detail"]["error"] == "day_not_markable"
    assert _mark(c, "naps").status_code == 422
    freeze(monkeypatch, "2027-01-20T12:00:00")
    assert _mark(c, "challenge_done").json()["detail"]["error"] == "not_in_season"


def test_the_night_belongs_to_the_evening_before_its_day(monkeypatch):
    """Night 21 is the evening of day 20 — the first odd night is ticked on
    day 20, and still on day 20 when the parent gets to it after midnight."""
    c = client()
    cid = add_child(c)
    freeze(monkeypatch, "2027-02-27T19:00:00")                   # day 20, evening
    day20 = _today(c, cid, tz_offset_minutes=0)
    assert day20["day"] == 20 and day20["content"]["odd_night"] is True
    assert day20["content"]["last_ten"] is False
    freeze(monkeypatch, "2027-02-28T00:20:00")                   # after midnight: day 21
    day21 = _today(c, cid, tz_offset_minutes=0)
    assert day21["day"] == 21 and day21["content"]["last_ten"] is True
    r = _mark(c, "night_joined", day=20)
    assert r.status_code == 200 and r.json()["day"] == 20
    freeze(monkeypatch, "2027-03-08T12:00:00")                   # day 29
    r = _mark(c, "night_joined")                                 # eve of Eid: no
    assert r.json()["detail"]["error"] == "mark_not_on_this_day"


def test_the_family_word_is_a_choice_not_free_text(monkeypatch):
    freeze(monkeypatch, "2027-03-07T12:00:00")                   # day 28
    c = client()
    cid = add_child(c)
    assert _mark(c, "family_word").json()["detail"]["error"] == "choice_index_required"
    assert _mark(c, "family_word", choice_index=8).status_code == 422
    day = _today(c, cid, tz_offset_minutes=0, lang="en")["content"]
    assert day["family_word_choices"][:2] == ["Mercy", "Patience"]
    assert len(day["family_word_choices"]) == 8
    r = _mark(c, "family_word", choice_index=1)
    assert r.json()["marks"]["family_word"] == {"choice_index": 1, "word": "صبر"}
    en = _today(c, cid, tz_offset_minutes=0, lang="en")["marks"]["family_word"]
    assert en == {"choice_index": 1, "word": "Patience"}


def test_any_day_can_be_previewed_but_only_past_days_carry_marks(monkeypatch):
    freeze(monkeypatch, "2027-02-10T12:00:00")                   # day 3
    c = client()
    cid = add_child(c, age_group="4-6")
    _mark(c, "challenge_done", day=2)
    past = c.get(f"/api/children/{cid}/ramadan/days/2", params={"tz_offset_minutes": 0}).json()
    assert past["markable"] is True and past["marks"]["challenge_done"] is True
    ahead = c.get(f"/api/children/{cid}/ramadan/days/4", params={"tz_offset_minutes": 0,
                                                                 "lang": "en"}).json()
    assert ahead["markable"] is False and ahead["marks"] is None
    assert ahead["content"]["day"] == 4 and ahead["content"]["variant"]["band"] == "4-6"
    assert ahead["content"]["family_word_choices"] is None
    assert c.get(f"/api/children/{cid}/ramadan/days/31").status_code == 404
    freeze(monkeypatch, "2027-01-10T12:00:00")                   # before the month
    early = c.get(f"/api/children/{cid}/ramadan/days/1").json()
    assert early["state"] == "upcoming" and early["markable"] is False


def test_past_days_stay_markable_until_the_bridge_ends(monkeypatch):
    c = client()
    freeze(monkeypatch, "2027-03-10T12:00:00")                   # Eid
    assert _mark(c, "wird_done").json()["detail"]["error"] == "day_required"
    assert _mark(c, "wird_done", day=29).status_code == 200
    freeze(monkeypatch, "2027-04-08T12:00:00")                   # bridge over
    assert _mark(c, "wird_done", day=28).json()["detail"]["error"] == "not_in_season"


# ── «رمضان عائلتنا» ────────────────────────────────────────────────────────

def _fill(monkeypatch, c, challenges=0, wird=0, nights=0, word=None, step_ups=0, cid=None):
    """Tick a season's marks from Eid day, when the whole month is markable."""
    freeze(monkeypatch, "2027-03-10T12:00:00")
    for day in range(1, challenges + 1):
        assert _mark(c, "challenge_done", day=day).status_code == 200
    for day in range(1, wird + 1):
        assert _mark(c, "wird_done", day=day).status_code == 200
    for day in range(20, 20 + nights):
        assert _mark(c, "night_joined", day=day).status_code == 200
    if word is not None:
        assert _mark(c, "family_word", day=28, choice_index=word).status_code == 200
    from app.db.init_db import get_conn
    conn = get_conn()
    for day in range(1, step_ups + 1):
        conn.execute("INSERT INTO ramadan_marks (device_id, child_id, hijri_year, day, mark, "
                     "value) VALUES (?, ?, 1448, ?, 'fasting_step_up', 'until_dhuhr')",
                     (DEVICE, cid, day))
    conn.commit()
    conn.close()


def test_before_eid_there_is_progress_but_no_card(monkeypatch):
    freeze(monkeypatch, "2027-02-12T12:00:00")
    c = client()
    _mark(c, "challenge_done", day=1)
    r = c.get("/api/programs/ramadan/recap", params={"tz_offset_minutes": 0})
    body = r.json()
    assert body["available"] is False and body["card"] is None
    assert body["available_on"] == "2027-03-10"
    assert {p["key"]: p["value"] for p in body["progress"]}["challenges_done"] == 1


def test_the_card_drops_small_lines_and_writes_arabic_digits(monkeypatch):
    c = client()
    cid = add_child(c)
    _fill(monkeypatch, c, challenges=12, wird=2, nights=3, word=4, step_ups=2, cid=cid)
    freeze(monkeypatch, "2027-03-10T12:00:00")
    body = c.get("/api/programs/ramadan/recap", params={"tz_offset_minutes": 0}).json()
    card = body["card"]
    assert card["headline"] == "رمضان عائلتنا ١٤٤٨"
    texts = [ln["text"] for ln in card["lines"]]
    assert texts == ["التحديات العائلية: ١٢",
                     "ليالٍ اجتمعنا فيها من العشر: ٣",
                     "كلمة رمضاننا: عطاء"]
    # wird_days = 2 < min_to_show 3 → no line, rather than a small number.
    assert "wird_days" not in {m["key"] for m in card["metrics"]}
    en = c.get("/api/programs/ramadan/recap", params={"lang": "en"}).json()["card"]
    assert en["headline"] == "Our Family's Ramadan 1448"
    assert "Family challenges: 12" in [ln["text"] for ln in en["lines"]]


def test_the_childrens_fasting_never_reaches_the_shared_card(monkeypatch):
    c = client()
    cid = add_child(c, name="يوسف")
    _fill(monkeypatch, c, challenges=5, step_ups=4, cid=cid)
    freeze(monkeypatch, "2027-03-12T12:00:00")
    for lang in (None, "en"):
        body = c.get("/api/programs/ramadan/recap", params={"lang": lang} if lang else {}).json()
        card_json = json.dumps(body["card"], ensure_ascii=False)
        assert "fasting" not in card_json
        private = body["family_only"][0]
        assert private["key"] == "fasting_steps" and private["value"] == 4
        assert private["label"] not in card_json
        assert "fasting_steps" not in {p["key"] for p in body["progress"]}
        # Nor does anything about the children: no name, no age.
        assert "يوسف" not in card_json and "7-9" not in card_json


def test_the_share_link_carries_the_familys_invite_code(monkeypatch):
    c = client()
    _fill(monkeypatch, c, challenges=3)
    freeze(monkeypatch, "2027-03-10T12:00:00")
    share = c.get("/api/programs/ramadan/recap").json()["card"]["share_text"]
    code = rows("referral_codes", "device_id = ?", (DEVICE,))[0]["code"]
    assert "play.google.com" in share and f"ref_{code}" in share
    assert "ramadan-1448" in share and "{app_link}" not in share


def test_a_year_with_no_season_is_404():
    c = client()
    r = c.get("/api/programs/ramadan/recap", params={"hijri_year": 1500})
    assert r.status_code == 404


def test_an_unpublished_program_is_503_not_a_crash(tmp_path, monkeypatch):
    (tmp_path / "ramadan_family.json").write_text(
        json.dumps({"program_type": "ramadan_family", "is_published": False}),
        encoding="utf-8")
    monkeypatch.setattr(pc, "PROGRAMS_DIR", tmp_path)
    c = client()
    r = c.get(f"/api/children/{add_child(c)}/ramadan/today")
    assert r.status_code == 503 and r.json()["detail"]["error"] == "program_unavailable"
