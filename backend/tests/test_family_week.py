"""«قناديل الأسبوع» — GET /api/family/week (نور والقناديل, Phase 3).

The lantern counter reads the same registry as the weekly funnel report
(services/family_actions.ACTION_SOURCES), in the family's LOCAL ISO week — the
week weekly_plan.py uses, Monday to Sunday. What these tests pin:

* one lantern per act, deduplicated per source row per local day, and a
  question at most once a local day;
* worship acts never light a lantern (plan rule: «أفعال العبادة مابتولّعش
  قناديل العدّاد الأسبوعي») — Ramadan marks, the Prayer Journey, a habit in the
  worship category, the weekly plan's worship item;
* `lit_weeks_total` counts every lit week ever and `last_8` is the last eight
  local weeks, oldest first;
* nothing personal leaves: no child name, no chat text, no memory text.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.db.init_db import get_conn
from app.services import family_actions as fa

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)      # a Wednesday
MONDAY = "2026-10-12"
DEV = "dev-lanterns"
LESSON = "lesson_7-9_medical_emotional_health_02"
MISSION = "mission_7-9_green_hunt"
ACTION = "sleep_school_1"
WORSHIP_ITEM = "worship_school_3"


@pytest.fixture(scope="module", autouse=True)
def _curriculum():
    cl.load_curriculum()


def _sql(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _iso(dt: datetime) -> str:
    """The ISO-with-offset shape missions and follow-ups are written in."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")


def _child(conn, device: str = DEV, name: str = "سالم", age: str = "7-9") -> int:
    return conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, ?)",
        (device, name, age)).lastrowid


def _question(conn, device: str, at: datetime, session: str | None = None) -> None:
    session = session or f"s-{device}"
    conn.execute("INSERT OR IGNORE INTO chat_sessions (id, device_id) VALUES (?, ?)",
                 (session, device))
    conn.execute("INSERT INTO chat_messages (session_id, role, content, created_at) "
                 "VALUES (?, 'user', 'سؤالي عن سالم وعناده', ?)", (session, _sql(at)))


def _ramadan_mark(conn, device: str, cid: int, at: datetime) -> None:
    conn.execute("INSERT INTO ramadan_marks (device_id, child_id, hijri_year, day, mark, "
                 "created_at) VALUES (?, ?, 1448, 5, 'challenge_done', ?)",
                 (device, cid, _sql(at)))


def _habit(conn, device: str, cid: int, at: datetime, category: str = "self_building",
           name: str = "بر الوالدين") -> None:
    conn.execute("INSERT INTO habits_value_events (device_id, child_id, category, habit_name, "
                 "status, created_at) VALUES (?, ?, ?, ?, 'completed', ?)",
                 (device, cid, category, name, _sql(at)))


def _seed_week(conn, cid: int) -> None:
    """One of every act this week, plus every worship act — all on DEV."""
    tue = NOW - timedelta(days=1)                                  # Tue 13 Oct 12:00 UTC
    # A bank mission assigned, claimed and confirmed the same day: ONE lantern.
    conn.execute(
        "INSERT INTO child_missions (device_id, child_id, mission_key, local_date, status, "
        "assigned_at, claimed_at, confirmed_at) VALUES (?, ?, ?, '2026-10-13', 'confirmed', "
        "?, ?, ?)", (DEV, cid, MISSION, _iso(tue - timedelta(hours=3)),
                     _iso(tue - timedelta(hours=2)), _iso(tue)))
    # A lesson started and completed the same day: ONE lantern.
    conn.execute(
        "INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, "
        "started_at, completed_at, updated_at) VALUES (?, ?, 'p', ?, 'completed', ?, ?, ?)",
        (DEV, cid, LESSON, _sql(tue - timedelta(hours=1)), _sql(tue), _sql(tue)))
    # Three questions on Tuesday and one on Wednesday: TWO lanterns.
    for at in (tue, tue + timedelta(hours=1), tue + timedelta(hours=2),
               NOW - timedelta(hours=1)):
        _question(conn, DEV, at)
    conn.execute("INSERT INTO chat_messages (session_id, role, content, created_at) "
                 "VALUES (?, 'assistant', 'جواب', ?)", (f"s-{DEV}", _sql(tue)))
    _habit(conn, DEV, cid, tue + timedelta(hours=3))
    conn.execute(
        "INSERT INTO followups (device_id, child_id, strategy, topic, due_at, status, outcome, "
        "note, answered_at) VALUES (?, ?, 'اخفض صوتك حين يغضب سالم', 'anger', ?, 'answered', "
        "'worked', 'سالم هدأ بسرعة', ?)",
        (DEV, cid, _iso(NOW - timedelta(days=2)), _iso(NOW - timedelta(hours=3))))
    conn.execute(
        "INSERT INTO weekly_plan_marks (device_id, child_id, item_id, marked_on, created_at) "
        "VALUES (?, ?, ?, ?, ?)", (DEV, cid, ACTION, MONDAY, _sql(NOW - timedelta(hours=2))))

    # ── Worship: never a lantern ────────────────────────────────────────
    _ramadan_mark(conn, DEV, cid, tue)
    conn.execute(
        "INSERT INTO prayer_journeys (device_id, child_id, track, stage, started_on, "
        "stage_started_on, created_at) VALUES (?, ?, 'journey', 1, '2026-10-13', "
        "'2026-10-13', ?)", (DEV, cid, _sql(tue)))
    conn.execute(
        "INSERT INTO child_missions (device_id, child_id, mission_key, local_date, status, "
        "assigned_at, claimed_at, confirmed_at, source) VALUES (?, ?, 'fajr#1', "
        "'2026-10-14', 'confirmed', ?, ?, ?, 'prayer_journey')",
        (DEV, cid, _iso(NOW - timedelta(hours=6)), _iso(NOW - timedelta(hours=6)),
         _iso(NOW - timedelta(hours=5))))
    _habit(conn, DEV, cid, tue, category="worship", name="صلاة الفجر")
    conn.execute(
        "INSERT INTO weekly_plan_marks (device_id, child_id, item_id, marked_on, created_at) "
        "VALUES (?, ?, ?, ?, ?)", (DEV, cid, WORSHIP_ITEM, MONDAY,
                                   _sql(NOW - timedelta(hours=4))))


def _seeded(device_extra=None) -> int:
    conn = get_conn()
    try:
        cid = _child(conn)
        _seed_week(conn, cid)
        if device_extra:
            device_extra(conn)
        conn.commit()
    finally:
        conn.close()
    return cid


# ── The service ───────────────────────────────────────────────────────────


def test_every_parenting_act_lights_one_lantern_and_worship_none():
    cid = _seeded()
    week = fa.family_week(DEV, tz_offset_minutes=0, now=NOW, lang="ar")
    assert week["week_start"] == MONDAY
    kinds = [a["kind"] for a in week["acts"]]
    assert kinds == ["mission", "lesson", "question", "habit", "followup", "plan_tick",
                     "question"], week["acts"]
    assert [a["at"] for a in week["acts"]] == [
        "2026-10-13T09:00:00Z", "2026-10-13T11:00:00Z", "2026-10-13T12:00:00Z",
        "2026-10-13T15:00:00Z", "2026-10-14T09:00:00Z", "2026-10-14T10:00:00Z",
        "2026-10-14T11:00:00Z"]
    by_kind = {a["kind"]: a for a in week["acts"]}
    assert by_kind["lesson"]["child_id"] == cid
    assert by_kind["mission"]["child_id"] == cid
    assert by_kind["plan_tick"]["child_id"] == cid
    assert by_kind["question"]["child_id"] is None          # a question is the family's
    assert week["lit_this_week"] is True
    assert week["lit_weeks_total"] == 1
    assert week["last_8"][-1] == {"week_start": MONDAY, "lit": True}


def test_titles_are_bank_text_and_never_personal():
    _seeded()
    week = fa.family_week(DEV, tz_offset_minutes=0, now=NOW, lang="ar")
    titles = {a["kind"]: a["title"] for a in week["acts"]}
    assert titles["lesson"] == cl.get_lesson(LESSON)["title"]
    assert titles["mission"] == "صيّاد الأخضر"
    assert titles["plan_tick"].startswith("ثبّت موعد النوم")
    # No cheap, safe label for these: a habit may be a name the parent typed,
    # a follow-up's text is memory, a question is the parent's own words.
    assert titles["habit"] is None and titles["followup"] is None
    assert titles["question"] is None
    blob = json.dumps(week, ensure_ascii=False)
    for personal in ("سالم", "سؤالي", "اخفض صوتك", "هدأ", "بر الوالدين"):
        assert personal not in blob, personal


def test_titles_follow_the_language():
    _seeded()
    week = fa.family_week(DEV, tz_offset_minutes=0, now=NOW, lang="en")
    titles = {a["kind"]: a["title"] for a in week["acts"]}
    assert titles["mission"] == "Green Hunter"
    for kind in ("lesson", "mission", "plan_tick"):
        assert titles[kind] and not re.search(r"[؀-ۿ]", titles[kind]), (kind, titles[kind])


def test_worship_alone_never_lights_a_week():
    conn = get_conn()
    try:
        cid = _child(conn, device="dev-worship-only")
        _ramadan_mark(conn, "dev-worship-only", cid, NOW - timedelta(hours=2))
        _habit(conn, "dev-worship-only", cid, NOW - timedelta(hours=1), category="worship",
               name="ورد القرآن")
        conn.commit()
    finally:
        conn.close()
    week = fa.family_week("dev-worship-only", tz_offset_minutes=0, now=NOW)
    assert week["acts"] == [] and week["lit_this_week"] is False
    assert week["lit_weeks_total"] == 0


def test_the_report_still_counts_what_the_lanterns_leave_out():
    """The North Star numerator is unchanged: the registry keeps the worship
    sources (the report counts every row); only the lantern view filters them."""
    assert ("ramadan_marks", "created_at") in {(s.table, s.column) for s in fa.ACTION_SOURCES}
    assert ("prayer_journeys", "created_at") in {(s.table, s.column) for s in fa.ACTION_SOURCES}
    lantern_tables = {s.table for s in fa.lantern_sources()}
    assert "ramadan_marks" not in lantern_tables and "prayer_journeys" not in lantern_tables


def test_another_device_sees_nothing_of_this_one():
    _seeded()
    week = fa.family_week("dev-stranger", tz_offset_minutes=0, now=NOW)
    assert week["acts"] == [] and week["lit_weeks_total"] == 0


def test_the_local_week_and_the_local_day_follow_the_offset():
    """Sunday 22:30 UTC is already Monday 01:30 in Riyadh (+180): it belongs
    to the new week there and to the old one in UTC. Two questions either
    side of UTC midnight are one local day in Riyadh, two in UTC."""
    sunday_late = datetime(2026, 10, 11, 22, 30, tzinfo=timezone.utc)
    conn = get_conn()
    try:
        cid = _child(conn, device="dev-tz")
        _habit(conn, "dev-tz", cid, sunday_late)
        _question(conn, "dev-tz", datetime(2026, 10, 13, 23, 30, tzinfo=timezone.utc))
        _question(conn, "dev-tz", datetime(2026, 10, 14, 0, 30, tzinfo=timezone.utc))
        conn.commit()
    finally:
        conn.close()
    utc = fa.family_week("dev-tz", tz_offset_minutes=0, now=NOW)
    riyadh = fa.family_week("dev-tz", tz_offset_minutes=180, now=NOW)
    assert [a["kind"] for a in utc["acts"]] == ["question", "question"]
    assert [a["kind"] for a in riyadh["acts"]] == ["habit", "question"]
    # The Sunday act lit last week in UTC; this week in Riyadh.
    assert utc["last_8"][-2] == {"week_start": "2026-10-05", "lit": True}
    assert riyadh["last_8"][-2] == {"week_start": "2026-10-05", "lit": False}
    assert utc["lit_weeks_total"] == 2 and riyadh["lit_weeks_total"] == 1


def test_lit_weeks_total_never_forgets_and_last_8_is_oldest_first():
    conn = get_conn()
    try:
        cid = _child(conn, device="dev-history")
        for weeks_ago in (0, 1, 3, 10):          # lit weeks; 10 is outside last_8
            _habit(conn, "dev-history", cid, NOW - timedelta(weeks=weeks_ago, hours=1))
        _ramadan_mark(conn, "dev-history", cid, NOW - timedelta(weeks=2))  # worship only
        conn.commit()
    finally:
        conn.close()
    week = fa.family_week("dev-history", tz_offset_minutes=0, now=NOW)
    assert week["lit_weeks_total"] == 4
    starts = [w["week_start"] for w in week["last_8"]]
    monday = date.fromisoformat(MONDAY)
    assert starts == [(monday - timedelta(weeks=k)).isoformat() for k in range(7, -1, -1)]
    assert [w["lit"] for w in week["last_8"]] == [False, False, False, False, True, False,
                                                 True, True]


def test_a_device_level_lesson_has_no_child():
    """lesson_progress rows from before per-child progress carry child_id 0."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, "
            "started_at) VALUES ('dev-legacy', 0, 'p', ?, 'in_progress', ?)",
            (LESSON, _sql(NOW - timedelta(hours=1))))
        conn.commit()
    finally:
        conn.close()
    acts = fa.family_week("dev-legacy", tz_offset_minutes=0, now=NOW)["acts"]
    assert [(a["kind"], a["child_id"]) for a in acts] == [("lesson", None)]


# ── The route ─────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, device: str) -> dict:
    tok = client.post("/api/chat/sessions", json={"device_id": device}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_route_needs_a_device_session(client):
    assert client.get("/api/family/week").status_code == 401


def test_route_shape_for_a_new_family(client):
    h = _auth(client, "dev-week-new")
    r = client.get("/api/family/week?tz_offset_minutes=180", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"week_start", "acts", "lit_this_week", "lit_weeks_total", "last_8"}
    assert date.fromisoformat(body["week_start"]).weekday() == 0      # a Monday
    assert body["acts"] == [] and body["lit_this_week"] is False
    assert body["lit_weeks_total"] == 0
    assert len(body["last_8"]) == 8
    assert body["last_8"][-1] == {"week_start": body["week_start"], "lit": False}


def test_route_rejects_an_impossible_offset(client):
    h = _auth(client, "dev-week-tz")
    assert client.get("/api/family/week?tz_offset_minutes=900", headers=h).status_code == 422


def test_a_plan_tick_lights_this_weeks_lantern_and_unticking_puts_it_out(client):
    h = _auth(client, "dev-week-tick")
    cid = client.post("/api/children", json={"name": "سالم", "age_group": "7-9"},
                      headers=h).json()["id"]
    plan = client.get(f"/api/children/{cid}/weekly-plan?tz_offset_minutes=0",
                      headers=h).json()
    item = plan["actions"][0]
    body = {"week_start": plan["week_start"], "item_key": item["key"]}
    assert client.put(f"/api/children/{cid}/weekly-plan/marks", json=body,
                      headers=h).status_code == 200

    week = client.get("/api/family/week?tz_offset_minutes=0", headers=h).json()
    assert [(a["kind"], a["child_id"], a["title"]) for a in week["acts"]] == [
        ("plan_tick", cid, item["text"])]
    assert week["lit_this_week"] is True and week["lit_weeks_total"] == 1
    assert "سالم" not in json.dumps(week, ensure_ascii=False)
    # Another family sees none of it.
    other = client.get("/api/family/week", headers=_auth(client, "dev-week-other")).json()
    assert other["acts"] == []

    assert client.request("DELETE", f"/api/children/{cid}/weekly-plan/marks", json=body,
                          headers=h).status_code == 200
    week = client.get("/api/family/week?tz_offset_minutes=0", headers=h).json()
    assert week["acts"] == [] and week["lit_this_week"] is False


def test_route_uses_the_offset_the_family_last_reported(client, monkeypatch):
    """An omitted offset is not UTC (PR #26 F7): the stored one is used."""
    from app.services import child_memory as cm
    h = _auth(client, "dev-week-stored")
    cm.record_tz_offset("dev-week-stored", 180)
    conn = get_conn()
    cid = _child(conn, device="dev-week-stored")
    _habit(conn, "dev-week-stored", cid, datetime(2026, 10, 11, 22, 30, tzinfo=timezone.utc))
    conn.commit()
    conn.close()
    monkeypatch.setattr(fa, "_utcnow", lambda: NOW)
    week = client.get("/api/family/week", headers=h).json()
    assert [a["kind"] for a in week["acts"]] == ["habit"]          # Monday 01:30 in Riyadh
    week = client.get("/api/family/week?tz_offset_minutes=0", headers=h).json()
    assert week["acts"] == []                                      # Sunday in UTC
