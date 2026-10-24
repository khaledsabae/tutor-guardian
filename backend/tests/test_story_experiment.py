"""«صورة حيّة» — the numbers behind the weekly section and the month-end
verdict (app/services/story_experiment.py, ops/scripts/story_motion_verdict.py).
"""
import importlib.util
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.services import story_experiment as se

_T0 = datetime(2026, 11, 20, 18, 0, 0)


def ev(name, arm="motion", device="d1", story="maryam_toys", at=_T0, **kw):
    r = {"name": name, "variant": arm, "device_id": device, "story_id": story,
         "lang": "ar", "narration_on": 0, "reduce_motion": 0, "page_index": None,
         "rating": None, "created_at": at.strftime("%Y-%m-%d %H:%M:%S")}
    r.update(kw)
    return r


def arm(opens, finished, arm_name, loved=0, liked=0, meh=0, devices=None):
    rows = []
    for i in range(opens):
        d = f"{arm_name}-{i % (devices or opens)}"
        rows.append(ev("story_opened", arm_name, d))
        if i < finished:
            rows.append(ev("story_finished", arm_name, d))
    for k, n in ((3, loved), (2, liked), (1, meh)):
        rows += [ev("story_rated", arm_name, f"{arm_name}-r{k}-{i}", rating=k) for i in range(n)]
    return rows


def test_z_test_matches_a_hand_computed_case():
    t = se.two_proportion_z(60, 100, 45, 100)
    assert t.p1 == .6 and t.p2 == .45
    assert t.z == pytest.approx(2.1243, abs=1e-3)
    assert t.p_value == pytest.approx(0.0336, abs=1e-3)
    assert se.two_proportion_z(0, 0, 1, 2) is None
    assert se.two_proportion_z(5, 5, 7, 7) is None  # no variance


def test_reduce_motion_devices_are_left_out():
    rows = arm(10, 5, "static") + [ev("story_opened", "static", "rm", reduce_motion=1)] * 7
    s = se.arm_summary(rows, "static")
    assert s["opens"] == 10 and s["completion"] == .5


def test_summary_pages_ratings_and_listen_through():
    rows = [ev("story_opened"), ev("story_page_viewed", page_index=0, narration_on=1),
            ev("story_page_viewed", page_index=1, narration_on=1),
            ev("story_finished", narration_on=1), ev("story_rated", rating=3),
            ev("story_opened", device="d2"), ev("story_page_viewed", device="d2", page_index=0),
            ev("story_closed_early", device="d2", page_index=0)]
    s = se.arm_summary(rows, "motion")
    assert s["opens"] == 2 and s["finished"] == 1
    assert s["pages_per_open"] == 1.5
    assert s["ratings"] == {1: 0, 2: 0, 3: 1} and s["loved_share"] == 1
    assert s["listen_starts"] == 1 and s["listen_through"] == 1


def test_reopen_within_seven_days():
    rows = [ev("story_opened", device="a"), ev("story_opened", device="a", at=_T0 + timedelta(days=3)),
            ev("story_opened", device="b"), ev("story_opened", device="b", at=_T0 + timedelta(days=9)),
            ev("story_opened", device="c"), ev("story_opened", device="c", at=_T0 + timedelta(minutes=5))]
    rate = se.reopen_rate(rows, "motion", _T0 - timedelta(days=1), _T0 + timedelta(days=1))
    assert rate == pytest.approx(1 / 3)  # b too late, c the same sitting


def test_not_enough_data_is_said_plainly():
    v = se.verdict(arm(40, 30, "motion") + arm(40, 10, "static"))
    assert v["mode"] is None
    assert v["reasons"][0].startswith("not enough data")


def test_a_clear_completion_win():
    v = se.verdict(arm(300, 210, "motion", devices=150) + arm(300, 150, "static", devices=150))
    assert v["completion"].p_value < .05
    assert v["mode"] == "motion"
    assert any("completion" in r for r in v["reasons"])


def test_no_detectable_difference():
    v = se.verdict(arm(200, 100, "motion", loved=20, liked=15)
                   + arm(200, 104, "static", loved=19, liked=16))
    assert v["mode"] is None
    assert any("no difference" in r for r in v["reasons"])


def test_mixed_results_pick_nothing():
    v = se.verdict(arm(400, 300, "motion", loved=20, meh=40)
                   + arm(400, 200, "static", loved=55, meh=5))
    assert v["mode"] is None
    assert any(r.startswith("mixed") for r in v["reasons"])


def test_min_detectable_difference_shrinks_with_n():
    a, b = se.min_detectable_difference(.5, 100), se.min_detectable_difference(.5, 400)
    assert a == pytest.approx(.198, abs=.005) and b == pytest.approx(a / 2, abs=.005)


def _load(script: str):
    path = Path(__file__).resolve().parents[2] / "ops" / "scripts" / script
    spec = importlib.util.spec_from_file_location(script[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_weekly_section_reads_the_table(tmp_path, monkeypatch):
    from app.routers.story_events import ensure_story_events_table

    db = tmp_path / "c.db"
    con = sqlite3.connect(db)
    ensure_story_events_table(con)
    now = datetime.utcnow()
    for r in arm(4, 3, "motion", loved=1) + arm(2, 1, "static", meh=1):
        con.execute("INSERT INTO story_events (device_id, name, story_id, lang, variant, "
                    "narration_on, reduce_motion, page_index, rating, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r["device_id"], r["name"], r["story_id"], r["lang"], r["variant"],
                     0, 0, None, r["rating"], (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")))
    con.commit()
    con.close()
    wd = _load("weekly_dashboard.py")
    monkeypatch.setattr(wd, "_DB", db)
    exp = wd._story_experiment()
    assert exp["motion"]["opens"] == 4 and exp["motion"]["finished"] == 3
    assert exp["static"]["ratings"][1] == 1
    text = "\n".join(wd._story_lines(exp))
    assert "متحركة: فتح 4 · إكمال 75%" in text
    assert "ثابتة: فتح 2 · إكمال 50%" in text
    assert wd._story_lines(None) == []


def test_verdict_script_prints_not_enough_data(tmp_path, monkeypatch, capsys):
    vs = _load("story_motion_verdict.py")
    monkeypatch.setattr(vs, "_DB", tmp_path / "empty.db")
    sqlite3.connect(tmp_path / "empty.db").close()
    monkeypatch.setattr("sys.argv", ["x", "--since", "2026-11-20"])
    vs.main()
    out = capsys.readouterr().out
    assert "VERDICT: not enough data" in out
    assert "keep STORY_MOTION_MODE=ab" in out
