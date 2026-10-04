"""Regressions for the PR #32 review — each one began as a reproduction script
(/tmp/review-pr32/probe/) that showed the bug; here it asserts the fix.

1  a family on the Prayer Journey never got a milestone push (28/28 evenings)
2  a double tap recorded — and paid — a once-a-week prayer task twice
3  a retried confirm lost the coins of the rows the first attempt confirmed
4  an old prayer card could be re-claimed through the bank mission endpoint
5  the evening batch was capped at 50 cards
6  a second graduate tap was a 500
7  one missing program file took the others down; a missing prayer file
   showed blank cards and confirmed them for 0 coins
8  a refused fasting step left the puberty flag written
10 the program went off-season for good after 8 April 2027
"""
import shutil
import threading
import time
from datetime import date, datetime, timezone

import pytest

from app.db.init_db import get_conn
from app.services import child_missions as cm
from app.services import milestone_push as mp
from app.services import mission_digest
from app.services import prayer_journey as pj
from app.services import programs_common as pc
from app.services import push_sender
from app.services import ramadan_program as rp
from tests.programs_support import (DEVICE, add_child, add_child_row, child_headers, client,
                                    freeze, rows)

UTC = timezone.utc


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("RAMADAN_START_1448", "RAMADAN_DAYS_1448", "RAMADAN_START_1449",
                 "RAMADAN_DAYS_1449", "MILESTONES_MIN_BUILD", "PROGRAMS_AS_OF_ENABLED"):
        monkeypatch.delenv(name, raising=False)


def _row(cid):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM child_profiles WHERE id = ?", (cid,)).fetchone()
    finally:
        conn.close()


def _enrolled(c, monkeypatch, birth_month="2018-06", **body):
    freeze(monkeypatch, "2026-10-05T12:00:00")
    cid = add_child(c, birth_month=birth_month)
    r = c.post(f"/api/children/{cid}/prayer-journey/enrol",
               params={"tz_offset_minutes": 0}, json=body)
    assert r.status_code == 200, r.text
    return cid


# ── 1. The milestone is not starved by the Prayer Journey ──────────────────

def test_a_family_on_the_journey_still_gets_its_milestone(monkeypatch):
    """The review's probe: a child who turns 11 in March 2027 (first_phone
    alerts all February), one family with a daily prayer recorded at 15:00 and
    confirmed at 21:30, one without. Both get the reminder."""
    monkeypatch.setenv("MILESTONES_MIN_BUILD", "150")
    now = {"t": None}

    def fake(device_id, title, body, data=None, channel_id=None, visibility=None):
        conn = get_conn()
        conn.execute("INSERT INTO push_sends (device_id, kind, sent_at) VALUES (?, ?, ?)",
                     (device_id, (data or {}).get("type"), mp._sql_ts(now["t"])))
        conn.commit()
        conn.close()
        return {"ok": True, "sent": True}

    monkeypatch.setattr(push_sender, "send_to_device", fake)

    def family(with_claims: bool, device: str) -> int:
        cid = add_child_row("10-12", device=device, birth_month="2016-03", gender="male")
        conn = get_conn()
        conn.execute("INSERT OR REPLACE INTO push_tokens (device_id, token, build_number) "
                     "VALUES (?, 'tok', 200)", (device,))
        conn.execute("INSERT OR REPLACE INTO program_settings (device_id, tz_offset_minutes) "
                     "VALUES (?, 180)", (device,))
        conn.commit()
        conn.close()
        doc = pc.load_program(pj.PROGRAM)
        child = _row(cid)
        if with_claims:
            start = date(2027, 1, 25)
            pj.enrol(doc, device, child, pc.child_age(child, start), start,
                     track="journey", start_stage=2, restart=False)
        sends = 0
        for d in range(1, 29):
            day = date(2027, 2, d)
            if with_claims:
                pj.claim(doc, device, cid, "prayer_s2_pray_beside", day)
            now["t"] = datetime(2027, 2, d, 17, 5, tzinfo=UTC)          # 20:05 local
            sends += mp.run_due_milestones(now["t"]).get("sent", 0)
            pending = [p["mission_id"] for p in cm.pending_for_device(device)]
            if pending:
                cm.confirm_batch(device, [{"mission_id": i, "confirmed": True}
                                          for i in pending])
        return sends

    assert family(False, "dev-plain") == 1
    assert family(True, "dev-journey") == 1


def test_the_digest_still_goes_after_a_milestone_push(monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch)
    pj.claim(pc.load_program(pj.PROGRAM), DEVICE, cid, "prayer_s1_pray_beside",
             date(2026, 10, 5))
    sent = []
    monkeypatch.setattr(mission_digest.push_sender, "send_to_device",
                        lambda d, t, b, data=None, **k: sent.append(data) or
                        {"ok": True, "sent": True})
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("INSERT INTO push_sends (device_id, kind, sent_at) VALUES (?, ?, ?)",
                 (DEVICE, mp.KIND, stamp))
    conn.commit()
    conn.close()
    assert mission_digest.send_digest(DEVICE)["sent"] is True
    assert sent[0]["link"] == "/missions"
    # …but any other push in the window still caps it, as before.
    conn = get_conn()
    conn.execute("INSERT INTO push_sends (device_id, kind, sent_at) "
                 "VALUES (?, 'streak_at_risk', ?)", (DEVICE, stamp))
    conn.commit()
    conn.close()
    assert mission_digest.send_digest(DEVICE)["reason"] == "already_pushed_today"


def test_the_digest_exemption_is_the_milestone_kind():
    assert mission_digest._DOES_NOT_CAP == mp.KIND


# ── 2. A double tap records and pays once ──────────────────────────────────

def test_a_double_tap_records_a_once_a_week_task_once(monkeypatch):
    """Two taps at once on a per_week=1 task. The count is slowed down so the
    second tap is inside the first's check-then-insert window — which, with
    the check inside the write transaction, it can no longer enter."""
    c = client()
    cid = _enrolled(c, monkeypatch)
    doc = pc.load_program(pj.PROGRAM)
    today = date(2026, 10, 5)
    real_counts = pj._counts

    def slow_counts(*a, **k):
        out = real_counts(*a, **k)
        time.sleep(0.3)
        return out

    monkeypatch.setattr(pj, "_counts", slow_counts)
    results, errors = [], []
    barrier = threading.Barrier(2)

    def tap():
        barrier.wait()
        try:
            results.append(pj.claim(doc, DEVICE, cid, "prayer_s1_my_place", today))
        except pj.JourneyError as exc:
            errors.append(exc.code)

    threads = [threading.Thread(target=tap) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    claimed = rows("child_missions", "child_id = ? AND source = 'prayer_journey'", (cid,))
    assert len(claimed) == 1 and len(results) == 1
    assert errors == ["week_complete"]
    out = cm.confirm_batch(DEVICE, [{"mission_id": r["id"]} for r in claimed])
    assert sum(x["coins"] for x in out["coins"]) == 10


def test_the_reviews_interleaving_can_no_longer_record_twice(monkeypatch):
    """The probe's own harness: the twin claim fires from inside the first
    claim's progress read. It now runs after the first commits — and is refused."""
    c = client()
    cid = _enrolled(c, monkeypatch)
    doc = pc.load_program(pj.PROGRAM)
    today = date(2026, 10, 5)
    real = pj.task_progress
    twin = {}

    def interleaved(*a, **k):
        out = real(*a, **k)
        if not twin:
            try:
                twin["result"] = pj.claim(doc, DEVICE, cid, "prayer_s1_my_place", today)
            except pj.JourneyError as exc:
                twin["result"] = exc.code
        return out

    monkeypatch.setattr(pj, "task_progress", interleaved)
    first = pj.claim(doc, DEVICE, cid, "prayer_s1_my_place", today)
    assert first["slot"] == 1 and twin["result"] == "week_complete"
    assert len(rows("child_missions", "child_id = ?", (cid,))) == 1


# ── 3. A retried confirm is idempotent ─────────────────────────────────────

def test_a_retried_confirm_reports_the_same_coins(monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch)
    mid = pj.claim(pc.load_program(pj.PROGRAM), DEVICE, cid, "prayer_s1_pray_beside",
                   date(2026, 10, 5))["mission_id"]
    first = c.post("/api/children/missions/confirm", json={"items": [{"mission_id": mid}]})
    retry = c.post("/api/children/missions/confirm", json={"items": [{"mission_id": mid}]})
    want = [{"mission_id": mid, "child_id": cid, "task_id": "prayer_s1_pray_beside",
             "coins": 10}]
    assert (first.json()["settled"], first.json()["coins"]) == (1, want)
    assert (retry.json()["settled"], retry.json()["coins"]) == (0, want)
    # A duplicate in one request is one entry.
    twice = c.post("/api/children/missions/confirm",
                   json={"items": [{"mission_id": mid}, {"mission_id": mid}]})
    assert twice.json()["coins"] == want


def test_concurrent_confirms_name_one_mission_to_credit(monkeypatch):
    """Eight confirms at once: every response may carry the entry (idempotent),
    and they all name the same mission_id — which the app credits once."""
    c = client()
    cid = _enrolled(c, monkeypatch)
    mid = pj.claim(pc.load_program(pj.PROGRAM), DEVICE, cid, "prayer_s1_pray_beside",
                   date(2026, 10, 5))["mission_id"]
    results, errors = [], []
    barrier = threading.Barrier(8)

    def go():
        try:
            barrier.wait()
            results.append(cm.confirm_batch(DEVICE, [{"mission_id": mid, "confirmed": True}]))
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert not errors
    assert sum(r["settled"] for r in results) == 1
    assert {e["mission_id"] for r in results for e in r["coins"]} == {mid}


def test_a_not_yet_never_reports_coins_even_on_retry(monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch)
    mid = pj.claim(pc.load_program(pj.PROGRAM), DEVICE, cid, "prayer_s1_pray_beside",
                   date(2026, 10, 5))["mission_id"]
    for _ in range(2):
        out = cm.confirm_batch(DEVICE, [{"mission_id": mid, "confirmed": False}])
        assert out["coins"] == []
    assert cm.confirm_batch(DEVICE, [{"mission_id": mid, "confirmed": True}])["coins"] == []


# ── 4. The bank endpoint claims bank cards only, and not expired ones ──────

def test_a_prayer_card_cannot_be_claimed_through_the_bank_endpoint(monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch)
    mid = pj.claim(pc.load_program(pj.PROGRAM), DEVICE, cid, "prayer_s1_pray_beside",
                   date(2026, 10, 5))["mission_id"]
    conn = get_conn()
    conn.execute("UPDATE child_missions SET status = 'expired' WHERE id = ?", (mid,))
    conn.commit()
    conn.close()
    assert cm.claim(cid, mid) == {"ok": False, "reason": "mission_not_found"}
    assert rows("child_missions", "id = ?", (mid,))[0]["status"] == "expired"


def test_an_expired_bank_card_stays_expired():
    c = client()
    cid = add_child(c)
    card = cm.today_mission(DEVICE, cid, "7-9", "2026-08-16")
    conn = get_conn()
    conn.execute("UPDATE child_missions SET status = 'expired' WHERE id = ?",
                 (card["mission_id"],))
    conn.commit()
    conn.close()
    assert cm.claim(cid, card["mission_id"]) == {"ok": False, "reason": "expired"}
    assert rows("child_missions", "id = ?", (card["mission_id"],))[0]["status"] == "expired"


# ── 5. The evening batch holds a family's list ─────────────────────────────

def test_the_evening_batch_takes_200_cards_and_refuses_201():
    c = client()
    ok = c.post("/api/children/missions/confirm",
                json={"items": [{"mission_id": i} for i in range(1, 201)]})
    assert ok.status_code == 200
    assert c.post("/api/children/missions/confirm",
                  json={"items": [{"mission_id": i} for i in range(1, 202)]}).status_code == 422


# ── 6. A second graduate tap is a 409, never a 500 ─────────────────────────

def test_a_second_graduate_tap_is_refused_cleanly(monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch, track="journey", start_stage=6)
    freeze(monkeypatch, "2026-10-25T12:00:00")
    doc = pc.load_program(pj.PROGRAM)
    child = _row(cid)
    stale = pj.active(DEVICE, cid)                 # read before the first tap commits
    pj.graduate(doc, DEVICE, child, date(2026, 10, 25))
    monkeypatch.setattr(pj, "active", lambda d, ch: stale)
    with pytest.raises(pj.JourneyError) as caught:
        pj.graduate(doc, DEVICE, child, date(2026, 10, 25))
    assert caught.value.code == "already_graduated"
    assert [(r["track"], r["status"]) for r in rows("prayer_journeys", "child_id = ?", (cid,))] \
        == [("journey", "graduated"), ("ownership", "active")]


def test_two_taps_on_next_stage_move_it_once(monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch, start_stage=2)
    doc = pc.load_program(pj.PROGRAM)
    child = _row(cid)
    stale = pj.active(DEVICE, cid)
    pj.set_stage(doc, DEVICE, child, 3, date(2026, 10, 5))
    monkeypatch.setattr(pj, "active", lambda d, ch: stale)
    with pytest.raises(pj.JourneyError) as caught:
        pj.set_stage(doc, DEVICE, child, 3, date(2026, 10, 5))
    assert caught.value.code == "stage_changed"
    assert rows("prayer_journeys", "child_id = ?", (cid,))[0]["stage"] == 3


# ── 7. Each program file stands alone ──────────────────────────────────────

def _programs_without(tmp_path, monkeypatch, *missing):
    fake = tmp_path / "curriculum" / "programs"
    fake.mkdir(parents=True)
    for name in ("ramadan_family.json", "prayer_journey.json", "milestones.json"):
        if name not in missing:
            shutil.copy(pc.PROGRAMS_DIR / name, fake / name)
    monkeypatch.setattr(pc, "PROGRAMS_DIR", fake)
    return fake


def test_a_missing_milestones_file_hides_only_milestones(tmp_path, monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch)
    _programs_without(tmp_path, monkeypatch, "milestones.json")
    ov = c.get("/api/programs", params={"tz_offset_minutes": 0})
    assert ov.status_code == 200
    body = ov.json()
    assert body["unavailable"] == ["milestones"] and body["ramadan"]["state"] == "upcoming"
    child = body["children"][0]
    assert child["milestones"] is None and child["prayer_journey"]["enrolled"] is True
    assert c.get(f"/api/children/{cid}/ramadan/today").status_code == 200
    assert c.get(f"/api/children/{cid}/milestones").status_code == 503


def test_a_missing_ramadan_file_hides_only_ramadan(tmp_path, monkeypatch):
    c = client()
    cid = add_child(c, birth_month="2019-01")
    freeze(monkeypatch, "2027-01-20T12:00:00")
    _programs_without(tmp_path, monkeypatch, "ramadan_family.json")
    body = c.get("/api/programs", params={"tz_offset_minutes": 0}).json()
    assert body["unavailable"] == ["ramadan_family"] and body["ramadan"] is None
    assert body["children"][0]["ramadan"] is None
    miles = c.get(f"/api/children/{cid}/milestones", params={"tz_offset_minutes": 0})
    assert miles.status_code == 200
    assert "first_fasting" not in str(miles.json())      # no season without the file
    assert c.get(f"/api/children/{cid}/ramadan/today").status_code == 503


def test_a_missing_prayer_file_hides_the_journey_and_keeps_claims_payable(tmp_path,
                                                                          monkeypatch):
    c = client()
    cid = _enrolled(c, monkeypatch)
    mid = pj.claim(pc.load_program(pj.PROGRAM), DEVICE, cid, "prayer_s1_pray_beside",
                   date(2026, 10, 5))["mission_id"]
    fake = _programs_without(tmp_path, monkeypatch, "prayer_journey.json")
    # No blank card in the evening list, and nothing confirmed for 0 coins.
    assert c.get("/api/children/missions/pending").json()["pending"] == []
    out = c.post("/api/children/missions/confirm", json={"items": [{"mission_id": mid}]}).json()
    assert (out["settled"], out["coins"], out["deferred"]) == (0, [], [mid])
    assert rows("child_missions", "id = ?", (mid,))[0]["status"] == "claimed"
    # The journey is hidden — in the catalogue and on the child's screen.
    body = c.get("/api/programs", params={"tz_offset_minutes": 0}).json()
    assert body["unavailable"] == ["prayer_journey"]
    assert body["children"][0]["prayer_journey"] is None
    kid = c.get("/api/value-tracking/child-mode/prayer/today", headers=child_headers(cid))
    assert kid.status_code == 200 and kid.json()["available"] is False
    assert kid.json()["tasks"] == []
    claim = c.post("/api/value-tracking/child-mode/prayer/claim",
                   params={"task_id": "prayer_s1_my_place"}, headers=child_headers(cid))
    assert claim.status_code == 503
    # The file returns: the card is back and pays its coins, once.
    shutil.copy(_source("prayer_journey.json"), fake / "prayer_journey.json")
    pending = c.get("/api/children/missions/pending").json()["pending"]
    assert [p["mission_id"] for p in pending] == [mid] and pending[0]["coins"] == 10
    out = c.post("/api/children/missions/confirm", json={"items": [{"mission_id": mid}]}).json()
    assert (out["settled"], out["deferred"]) == (1, [])
    assert out["coins"][0]["coins"] == 10


def _source(name):
    from pathlib import Path
    return Path(pc.__file__).resolve().parents[3] / "knowledge_base" / "curriculum" / \
        "programs" / name


def test_the_milestone_push_runs_without_the_ramadan_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MILESTONES_MIN_BUILD", "1")
    _programs_without(tmp_path, monkeypatch, "ramadan_family.json")
    cid = add_child_row("7-9", birth_month="2020-03")
    conn = get_conn()
    conn.execute("INSERT INTO push_tokens (device_id, token, build_number) VALUES (?, 't', 5)",
                 (DEVICE,))
    conn.execute("INSERT INTO program_settings (device_id, tz_offset_minutes) VALUES (?, 180)",
                 (DEVICE,))
    conn.commit()
    conn.close()
    seen = []
    monkeypatch.setattr(push_sender, "send_to_device",
                        lambda d, t, b, data=None, **k: seen.append(data) or
                        {"ok": True, "sent": True})
    out = mp.run_due_milestones(datetime(2027, 2, 1, 17, 0, tzinfo=UTC))
    assert out["sent"] == 1 and seen[0]["child_id"] == str(cid)


# ── 8. A refused step writes nothing ───────────────────────────────────────

def test_a_refused_step_leaves_the_puberty_flag_alone(monkeypatch):
    freeze(monkeypatch, "2027-02-10T12:00:00")
    c = client()
    cid = add_child(c, birth_month="2019-06")
    r = c.put(f"/api/children/{cid}/ramadan/fasting", params={"tz_offset_minutes": 0},
              json={"reached_puberty": True, "step_key": "until_asr"})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "unknown_step"
    assert pc.reached_puberty(DEVICE, cid) is False
    assert rows("program_children", "child_id = ?", (cid,)) == []
    # Both valid together: both written, the step checked against the new ladder.
    r = c.put(f"/api/children/{cid}/ramadan/fasting", params={"tz_offset_minutes": 0},
              json={"reached_puberty": True, "step_key": "full_day_supported"})
    assert r.status_code == 200 and r.json()["ladder_band"] == "13-15"
    assert pc.reached_puberty(DEVICE, cid) is True


# ── 10. The calendar runs into 1449 ────────────────────────────────────────

def test_the_reviews_ramadan_boundaries_and_the_next_season():
    doc = pc.load_program(rp.PROGRAM)
    base = {"ramadan_year": None, "ramadan_shift_days": 0, "ramadan_days": None}
    seasons = rp.family_seasons(base, doc)
    s1448 = rp.season_by_year(seasons, 1448)
    assert (s1448.start, s1448.eid) == (date(2027, 2, 8), date(2027, 3, 10))
    assert pc.local_today(840, datetime(2027, 2, 7, 10, 0, tzinfo=UTC)) == date(2027, 2, 8)
    assert pc.local_today(-720, datetime(2027, 2, 8, 11, 59, tzinfo=UTC)) == date(2027, 2, 7)
    assert rp.locate(date(2027, 2, 7), seasons)["state"] == "upcoming"
    assert rp.locate(date(2027, 2, 8), seasons)["day"] == 1
    assert rp.locate(date(2027, 3, 9), seasons)["day"] == 30
    assert rp.locate(date(2027, 3, 10), seasons)["state"] == "eid"
    assert rp.locate(date(2027, 4, 7), seasons)["week"] == 4
    after = rp.locate(date(2027, 4, 8), seasons)
    assert (after["state"], after["season"].hijri_year) == ("upcoming", 1449)
    s1449 = rp.season_by_year(seasons, 1449)
    assert (s1449.start, s1449.start_source) == (date(2028, 1, 28), "estimate")
    fam = {"ramadan_year": 1448, "ramadan_shift_days": -1, "ramadan_days": 30}
    shifted = rp.family_seasons(fam, doc)
    assert rp.locate(date(2027, 2, 7), shifted)["day"] == 1
    assert rp.locate(date(2027, 3, 9), shifted)["state"] == "eid"
    # The family's 1448 sighting does not move 1449.
    assert rp.season_by_year(shifted, 1449).start == date(2028, 1, 28)


def test_the_validator_knows_every_years_estimate():
    import sys
    from pathlib import Path
    tools = Path(pc.__file__).resolve().parents[3] / "ops" / "tools"
    sys.path.insert(0, str(tools))
    try:
        import check_programs as cp
    finally:
        sys.path.remove(str(tools))
    assert cp.invariant("expected_start_1449") and cp.invariant("expected_start_1450")
    assert not cp.invariant("expected_start_soon")
    assert cp.season_problems({"expected_start_1448": "2027-02-08",
                               "expected_start_1449": "2028-01-28"}) == []
    assert cp.season_problems({"expected_start_1448": "2027-02-08",
                               "expected_start_1450": "2029-01-17"})   # a skipped year
