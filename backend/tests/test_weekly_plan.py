"""«خطة الأسبوع» — the bank's integrity and the plan's behaviour (schema v30)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import curriculum_loader as cl
from app.db.init_db import get_conn
from app.services import weekly_plan as wp

CURRICULUM = Path(__file__).resolve().parents[2] / "knowledge_base" / "curriculum"
BANDS = ("prenatal-1", "0-3", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18")


@pytest.fixture(scope="module", autouse=True)
def _curriculum():
    cl.load_curriculum()
    wp._load.cache_clear()


def _ar(group):
    return json.loads((CURRICULUM / "weekly_plan" / f"weekly_plan_{group}.json").read_text())


def _en(group):
    return json.loads((CURRICULUM / "i18n" / "en" / "weekly_plan" / f"weekly_plan_{group}.json").read_text())


# ── The bank ──────────────────────────────────────────────────────────────


def test_every_band_has_a_bank_and_every_bank_lists_its_bands():
    for band in BANDS:
        group = wp.BAND_GROUP[band]
        assert band in _ar(group)["age_bands"], band


@pytest.mark.parametrize("group", ["baby", "early", "school", "teen"])
def test_every_lesson_in_the_bank_is_real_and_in_its_band(group):
    for topic in _ar(group)["topics"]:
        assert topic.get("lessons"), (group, topic["key"])
        for band, ids in topic["lessons"].items():
            assert band in _ar(group)["age_bands"], (group, topic["key"], band)
            assert ids, (group, topic["key"], band)
            for lid in ids:
                lesson = cl.get_lesson(lid)
                assert lesson is not None, f"{lid} is not a published lesson"
                assert lesson["age_group"] == band, (lid, lesson["age_group"], band)


@pytest.mark.parametrize("group", ["baby", "early", "school", "teen"])
def test_english_overlay_translates_every_key(group):
    ar, en = _ar(group), _en(group)
    assert [t["key"] for t in ar["topics"]] == [t["key"] for t in en["topics"]]
    for ta, te in zip(ar["topics"], en["topics"]):
        assert [a["key"] for a in ta["actions"]] == [a["key"] for a in te["actions"]]
        for a in te["actions"]:
            assert not re.search(r"[؀-ۿ]", a["text"]), a["key"]
    assert [w["key"] for w in ar["worship"]] == [w["key"] for w in en["worship"]]


@pytest.mark.parametrize("group", ["baby", "early", "school", "teen"])
def test_bank_quotes_no_scripture(group):
    """The bank names acts of worship; it never quotes a verse or a hadith,
    and never attributes words to the Prophet ﷺ. Generated or hand-written,
    an unsourced quotation is the one thing this product does not ship."""
    banned = re.compile(r"﴿|﴾|ﷺ|صلى الله عليه وسلم|قال رسول|قال النبي|قال تعالى|يقول الله|"
                        r"Prophet said|Allah says|Allah said|hadith", re.I)
    for doc in (_ar(group), _en(group)):
        texts = [t["focus"] for t in doc["topics"]]
        texts += [a["text"] for t in doc["topics"] for a in t["actions"]]
        texts += [w["text"] for w in doc["worship"]]
        for t in texts:
            assert not banned.search(t), t


# ── The plan ──────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, device):
    tok = client.post("/api/chat/sessions", json={"device_id": device}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _child(client, h, age="7-9"):
    if age == "0-3":
        # Legacy label: the API no longer accepts it, but production still
        # has profiles that carry it (it aliases to prenatal-1).
        device = client.get("/api/children", headers=h)  # binds nothing; just auth
        assert device.status_code == 200
        cid = client.post("/api/children", json={"name": "سالم", "age_group": "prenatal-1"},
                          headers=h).json()["id"]
        conn = get_conn()
        conn.execute("UPDATE child_profiles SET age_group = '0-3' WHERE id = ?", (cid,))
        conn.commit()
        conn.close()
        return cid
    return client.post("/api/children", json={"name": "سالم", "age_group": age}, headers=h).json()["id"]


@pytest.mark.parametrize("age", BANDS)
def test_plan_shape_for_every_band(client, age):
    h = _auth(client, f"dev-plan-{age}")
    cid = _child(client, h, age)
    r = client.get(f"/api/children/{cid}/weekly-plan", headers=h)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert re.fullmatch(r"\d{4}-W\d{2}", plan["week"])
    assert len(plan["actions"]) == 3 and all(a["text"] for a in plan["actions"])
    assert plan["worship"]["text"]
    assert plan["focus"]["reason"] == "age_default"
    lesson = plan["lesson"]
    assert lesson is not None and cl.get_lesson(lesson["id"]) is not None
    assert cl.get_lesson(lesson["id"])["age_group"] in wp.age_equivalents(wp.canonical_age_group(age))
    assert plan["lang"] == "ar"


def test_plan_is_cached_for_the_week_and_per_language(client):
    h = _auth(client, "dev-plan-cache")
    cid = _child(client, h)
    first = client.get(f"/api/children/{cid}/weekly-plan", headers=h).json()
    again = client.get(f"/api/children/{cid}/weekly-plan", headers=h).json()
    assert first == again
    en = client.get(f"/api/children/{cid}/weekly-plan?lang=en", headers=h).json()
    assert en["lang"] == "en" and en["focus"]["topic"] == first["focus"]["topic"]
    assert not re.search(r"[؀-ۿ]", en["focus"]["title"] + en["actions"][0]["text"])
    conn = get_conn()
    rows = conn.execute("SELECT lang FROM weekly_plans WHERE child_id = ?", (cid,)).fetchall()
    conn.close()
    assert sorted(r["lang"] for r in rows) == ["ar", "en"]


def test_focus_follows_the_parents_challenge_then_memory(client):
    h = _auth(client, "dev-plan-signal")
    cid = _child(client, h, "4-6")
    client.post(f"/api/children/{cid}/memory", headers=h,
                json={"category": "challenge", "fact": "طفلي يخاف من النوم وحده ويستيقظ ليلًا"})
    plan = wp.build_plan("dev-plan-signal", cid, today=date(2026, 10, 5), lang=None)
    assert plan["focus"]["topic"] == "sleep" and plan["focus"]["reason"] == "memory"

    assert client.put(f"/api/children/{cid}/challenge", headers=h,
                      json={"challenge_key": "screens"}).status_code in (200, 201)
    plan = wp.build_plan("dev-plan-signal", cid, today=date(2026, 10, 5), lang=None)
    assert plan["focus"]["topic"] == "screens" and plan["focus"]["reason"] == "parent_challenge"


def test_a_failed_strategy_is_swapped_for_the_spare_action(client):
    h = _auth(client, "dev-plan-adapt")
    cid = _child(client, h, "4-6")
    conn = get_conn()
    conn.execute(
        "INSERT INTO followups (device_id, child_id, strategy, topic, due_at, status, outcome, answered_at) "
        "VALUES ('dev-plan-adapt', ?, 'ثبّت موعد النوم نفسه كل ليلة', 'sleep', '2026-01-01 00:00:00', "
        "'answered', 'didnt_work', '2026-01-02 00:00:00')", (cid,))
    conn.commit()
    conn.close()
    plan = wp.build_plan("dev-plan-adapt", cid, today=date(2026, 10, 5), lang=None)
    assert plan["focus"]["topic"] == "sleep"
    keys = [a["key"] for a in plan["actions"]]
    assert "sleep_early_1" not in keys and len(keys) == 3
    assert plan["adapted_from_outcomes"] is True


def test_completed_lessons_are_skipped(client):
    h = _auth(client, "dev-plan-lesson")
    cid = _child(client, h, "7-9")
    # 2026-W42 → 42 % 7 = 0 → the first topic of the demand map: prayer,
    # which has two 7-9 lessons in the bank.
    monday = date(2026, 10, 12)
    first = wp.build_plan("dev-plan-lesson", cid, today=monday, lang=None)
    assert first["focus"]["topic"] == "prayer"
    conn = get_conn()
    conn.execute(
        "INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status) "
        "VALUES ('dev-plan-lesson', ?, 'p', ?, 'completed')", (cid, first["lesson"]["id"]))
    conn.commit()
    conn.close()
    second = wp.build_plan("dev-plan-lesson", cid, today=monday, lang=None)
    assert second["lesson"]["id"] != first["lesson"]["id"]
    assert second["lesson"]["completed"] is False


def test_week_is_the_parents_local_iso_week():
    # Sunday 23:30 UTC is already Monday in Riyadh (+180).
    sunday_late = datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc)
    assert wp.iso_week(sunday_late.date())[0] == "2026-W40"
    local = (sunday_late + wp.timedelta(minutes=180)).date()
    assert wp.iso_week(local)[0] == "2026-W41"
