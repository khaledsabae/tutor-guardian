"""ops/scripts/campaign_report.py — numbers checked by hand on a built database.

The database is the app's real schema (conftest runs init_db on a temp file),
filled with timestamps in the three formats production stores.
"""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import ops.scripts.campaign_report as cr  # noqa: E402
from app.db.init_db import db_path, get_conn  # noqa: E402
from app.services import attribution  # noqa: E402

NOW = datetime(2026, 10, 4, 12, 0, 0)


def _device(conn, device, first_session, *, child=False):
    conn.execute("INSERT INTO chat_sessions (id, device_id, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?)", (f"s-{device}", device, first_session, first_session))
    if child:
        cur = conn.execute("INSERT INTO child_profiles (device_id, name, age_group) "
                           "VALUES (?, 'x', '4-6')", (device,))
        return cur.lastrowid
    return None


def _claim(conn, device, code, at, via="code"):
    conn.execute("INSERT INTO referrals (referrer_device, referred_device, code, created_at, via) "
                 "VALUES (?, ?, ?, ?, ?)", (f"campaign#{code}", device, code, at, via))


@pytest.fixture
def report_db():
    conn = get_conn()
    # DA01: four new installs, one already-installed device, three clicks —
    # plus the preview fetch WhatsApp made when the link was shared.
    for i in range(3):
        conn.execute("INSERT INTO referral_clicks (ip, code, clicked_at) VALUES (?, 'DA01', ?)",
                     (f"203.0.113.{i}", "2026-09-01 09:00:00"))
    conn.execute("INSERT INTO referral_clicks (ip, user_agent, code, clicked_at) VALUES "
                 "('198.51.100.9', 'WhatsApp/2.23.20.0 A', 'DA01', '2026-08-31 09:00:00')")
    kid = _device(conn, "a1", "2026-09-01 09:59:00", child=True)
    _claim(conn, "a1", "DA01", "2026-09-01 10:00:00")
    conn.execute("INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, "
                 "started_at, updated_at) VALUES ('a1', ?, 'p', 'l1', 'in_progress', ?, ?)",
                 (kid, "2026-09-01T10:30:00Z", "2026-09-01T10:30:00Z"))
    # Day 7.9 — inside the D7 window.
    conn.execute("INSERT INTO habits_value_events (device_id, child_id, category, habit_name, "
                 "status, created_at, updated_at) VALUES ('a1', ?, 'c', 'h', 'done', ?, ?)",
                 (kid, "2026-09-09 08:00:00", "2026-09-09 08:00:00"))

    kid2 = _device(conn, "a2", "2026-09-02 10:00:00", child=True)
    _claim(conn, "a2", "DA01", "2026-09-02 10:00:00", via="auto")  # matched by IP
    conn.execute("INSERT INTO chat_messages (session_id, role, content, created_at) "
                 "VALUES ('s-a2', 'user', 'q', '2026-09-03 10:00:00')")
    # Day 15, '+00:00' format — after the window.
    conn.execute("INSERT INTO child_missions (device_id, child_id, mission_key, local_date, "
                 "status, assigned_at) VALUES ('a2', ?, 'm', '2026-09-17', 'expired', ?)",
                 (kid2, "2026-09-17T11:00:00+00:00"))

    _device(conn, "a3", "2026-05-01 10:00:00", child=True)   # installed in May
    _claim(conn, "a3", "DA01", "2026-09-03 10:00:00")         # tapped the link in Sept

    _device(conn, "a4", "2026-09-28 10:00:00")
    _claim(conn, "a4", "DA01", "2026-09-28 10:00:00")         # too recent for D7

    # A one-minute-early 'T…Z' stamp: compared as raw text it would sort
    # after '2026-09-08 10:00:00' and count as a day-7 action.
    kid5 = _device(conn, "a5", "2026-09-01 10:00:00", child=True)
    _claim(conn, "a5", "DA01", "2026-09-01 10:00:00", via=None)    # before via existed
    conn.execute("INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, "
                 "started_at, updated_at) VALUES ('a5', ?, 'p', 'l2', 'in_progress', ?, ?)",
                 (kid5, "2026-09-01T11:00:00Z", "2026-09-08T09:59:00Z"))

    # WA01: clicked, never installed.
    conn.execute("INSERT INTO referral_clicks (ip, code, clicked_at) VALUES "
                 "('198.51.100.1', 'WA01', '2026-09-20 10:00:00')")
    # Two personal invites — one from a parent whose code merely starts like a
    # campaign (ENV9Z5 is a real production device code) — and an organic install.
    _device(conn, "p1", "2026-09-10 10:00:00")
    conn.execute("INSERT INTO referrals (referrer_device, referred_device, code, created_at) "
                 "VALUES ('inviter', 'p1', 'ABC234', '2026-09-10 10:00:00')")
    _device(conn, "p2", "2026-09-11 10:00:00")
    conn.execute("INSERT INTO referrals (referrer_device, referred_device, code, created_at) "
                 "VALUES ('inviter2', 'p2', 'ENV9Z5', '2026-09-11 10:00:00')")
    _device(conn, "o1", "2026-09-05 10:00:00", child=True)
    # Outside the 60-day window.
    _device(conn, "old", "2026-06-01 10:00:00", child=True)
    _claim(conn, "old", "DA01", "2026-06-01 10:00:00")
    conn.commit()
    conn.close()
    return db_path()


def _data(db, days=60):
    conn = cr._connect_ro(db)
    try:
        return cr.build_report_data(cr.load_facts(conn, days, NOW))
    finally:
        conn.close()


def test_campaign_funnel_counts(report_db):
    da = _data(report_db)["campaigns"]["DA01"]
    assert (da.clicks, da.new, da.already) == (3, 4, 1)   # a1 a2 a4 a5 new; a3 already
    assert (da.exact, da.auto, da.unknown) == (2, 1, 1)   # a1 a4 · a2 · a5
    assert (da.child, da.lesson) == (3, 2)                # a1 a2 a5 · a1 a5
    assert (da.d7_eligible, da.d7_active) == (3, 1)       # a1 a2 a5 eligible; a1 active
    assert da.first_seen == "2026-09-01 09:00:00"


def test_clicks_without_installs_still_show(report_db):
    wa = _data(report_db)["campaigns"]["WA01"]
    assert (wa.clicks, wa.new, wa.already) == (1, 0, 0)


def test_channels_and_yardsticks(report_db):
    data = _data(report_db)
    assert data["channels"]["preacher_ar"].new == 4
    assert data["channels"]["whatsapp"].clicks == 1
    assert (data["invites"].new, data["invites"].child) == (2, 0)   # p1, p2
    assert "ENV9Z5" not in data["campaigns"]
    assert "preacher_en" not in data["channels"]
    # Every device whose first session is inside the window.
    assert data["everyone"].new == 7                      # a1 a2 a4 a5 p1 p2 o1


def test_the_window_bounds_claims(report_db):
    assert _data(report_db, days=60)["campaigns"]["DA01"].new == 4
    assert _data(report_db, days=200)["campaigns"]["DA01"].new == 5   # + "old"


def test_the_database_is_opened_read_only(report_db):
    conn = cr._connect_ro(report_db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM referrals")
    finally:
        conn.close()


def test_dry_run_prints_aggregates_only(report_db, capsys, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "must-not-be-used")
    monkeypatch.setattr(cr, "send_telegram", lambda *a: pytest.fail("sent in dry run"))
    assert cr.main(["--db", str(report_db), "--dry-run", "--days", "365"]) == 0
    out = capsys.readouterr().out
    assert "<b>DA01</b> · preacher_ar" in out and "WA01" in out
    assert "تثبيت 5 [بالكود 3 · بمطابقة IP 1 · قبل التتبّع 1]" in out  # + the June claim
    # D7 here counts five kinds of action; say so, or it gets compared with
    # weekly_funnel_report's chat + lesson figure.
    for action in ("رسالة للمساعد", "تقدّم في درس", "عادة", "مهمة طفل", "تحدٍّ"):
        assert action in out, action
    # No device ids, IPs or owners — and a person's own code never gets a line.
    for private in ("a1", "a2", "p1", "p2", "o1", "203.0.113", "inviter", "campaign#",
                    "ABC234", "ENV9Z5"):
        assert private not in out


def test_without_dry_run_the_report_goes_to_telegram(report_db, monkeypatch):
    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr(cr, "send_telegram",
                        lambda token, chat, text: sent.append((token, chat, text)) or True)
    assert cr.main(["--db", str(report_db), "--days", "365"]) == 0
    assert len(sent) == 1 and sent[0][:2] == ("t", "c")
    assert "<b>DA01</b>" in sent[0][2]
    monkeypatch.setattr(cr, "send_telegram", lambda *a: False)
    assert cr.main(["--db", str(report_db)]) == 1   # a failed send is not a success


def test_without_telegram_credentials_it_prints_instead(report_db, capsys, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(cr, "send_telegram", lambda *a: pytest.fail("no credentials"))
    assert cr.main(["--db", str(report_db)]) == 0
    assert "تقرير الحملات" in capsys.readouterr().out


def test_end_to_end_a_preacher_link_lands_in_the_report():
    """Link → page → Play → app parser → claim → report, every hop for real."""
    import html as _html
    import re
    from urllib.parse import parse_qs, urlsplit

    from fastapi.testclient import TestClient

    from app.main import app

    phone = {"cf-connecting-ip": "203.0.113.120",
             "user-agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"}
    with TestClient(app, client=("172.18.0.5", 50000)) as client:
        page = client.get("/go?ref=DA07", headers=phone).text
        play = _html.unescape(re.search(r'href="(https://play\.google\.com[^"]*)"', page)[1])
        # Play hands the app its `referrer` parameter, decoded once …
        referrer = parse_qs(urlsplit(play).query)["referrer"][0]
        # … and referral_service.dart claims the first REF_<code> in it.
        code = re.search(r"REF_([A-Z0-9]{4,16})", referrer.upper())[1]
        assert parse_qs(referrer)["utm_campaign"] == ["DA07"]   # what GA4 reads
        token = client.post("/api/chat/sessions",
                            json={"device_id": "e2e-phone"}).json()["token"]
        r = client.post("/api/referral/claim", json={"code": code},
                        headers={"Authorization": f"Bearer {token}", **phone})
        assert r.json()["ok"] is True

    conn = cr._connect_ro(db_path())
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        data = cr.build_report_data(cr.load_facts(conn, 30, now))
    finally:
        conn.close()
    da07 = data["campaigns"]["DA07"]
    assert (da07.clicks, da07.new, da07.already) == (1, 1, 0)
    assert data["channels"]["preacher_ar"].new == 1


def test_the_script_and_the_backend_agree_on_campaign_codes():
    assert cr.CAMPAIGN_CHANNELS == attribution.CAMPAIGN_CHANNELS
    assert cr.CAMPAIGN_RE.pattern == attribution.CAMPAIGN_RE.pattern
    assert cr.PREVIEW_FETCHER_RE.pattern == attribution.PREVIEW_FETCHER_RE.pattern
    for code in ("DA01", "WA02", "KT17", "WAAR", "KT001", "ENV9Z", "ENV9Z5", "ABC234",
                 "DA0001", "DA٠١"):
        assert cr.is_campaign_code(code) == attribution.is_campaign_code(code), code


def test_folded_daily_clicks_are_counted(report_db):
    conn = get_conn()
    conn.execute("INSERT INTO referral_click_days (day, code, clicks) VALUES "
                 "('2026-08-20', 'DA01', 4), ('2026-05-01', 'DA01', 50)")
    conn.commit()
    conn.close()
    da = _data(report_db)["campaigns"]["DA01"]
    assert da.clicks == 3 + 4                    # May is outside the 60-day window
    assert da.first_seen == "2026-08-20 00:00:00"


def test_a_database_from_before_v32_still_reports(tmp_path):
    # Production until this deploys: no referrals.via, no referral_click_days.
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE referrals (id INTEGER PRIMARY KEY, referrer_device TEXT,"
        " referred_device TEXT, code TEXT, created_at TEXT);"
        "CREATE TABLE chat_sessions (id TEXT, device_id TEXT, created_at TEXT);"
        "INSERT INTO referrals VALUES (1, 'campaign#DA01', 'd1', 'DA01', '2026-09-20 10:00:00');"
        "INSERT INTO chat_sessions VALUES ('s', 'd1', '2026-09-20 10:00:00');")
    conn.commit()
    conn.close()
    da = _data(db)["campaigns"]["DA01"]
    assert (da.new, da.exact, da.auto, da.unknown) == (1, 0, 0, 1)


def _raw_click(conn, ip, ua, code, age):
    conn.execute("INSERT INTO referral_clicks (ip, user_agent, code, clicked_at) "
                 "VALUES (?, ?, ?, datetime('now', ?))", (ip, ua, code, age))


def test_old_clicks_fold_into_daily_counts_and_leave_no_ip_behind():
    from app.services.attribution import compact_referral_clicks

    conn = get_conn()
    _raw_click(conn, "203.0.113.1", "Mozilla", "DA01", "-10 days")
    _raw_click(conn, "203.0.113.2", "Mozilla", "DA01", "-10 days")
    _raw_click(conn, "203.0.113.3", "facebookexternalhit/1.1", "DA01", "-10 days")
    _raw_click(conn, "203.0.113.4", "Mozilla", "WA01", "-9 days")
    _raw_click(conn, "203.0.113.5", "Mozilla", "DA01", "-1 days")    # recent: stays raw
    conn.commit()
    conn.close()
    assert compact_referral_clicks(dry_run=True) == 4                 # counts, writes nothing
    assert compact_referral_clicks() == 4
    conn = get_conn()
    raw = [(r["ip"], r["code"]) for r in conn.execute("SELECT ip, code FROM referral_clicks")]
    days = {(r["code"], r["clicks"]) for r in
            conn.execute("SELECT code, clicks FROM referral_click_days")}
    conn.close()
    assert raw == [("203.0.113.5", "DA01")]         # only the recent click keeps an IP
    assert days == {("DA01", 2), ("WA01", 1)}        # the preview fetch is not counted
    assert compact_referral_clicks() == 0            # nothing left to fold


def test_the_daily_push_cron_folds_old_clicks():
    import ops.scripts.cron_push_triggers as cpt

    conn = get_conn()
    _raw_click(conn, "203.0.113.9", "Mozilla", "DA01", "-30 days")
    conn.commit()
    conn.close()
    assert cpt.fold_referral_clicks(dry_run=True) == 1
    assert cpt.fold_referral_clicks() == 1
    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) FROM referral_clicks").fetchone()[0] == 0
    conn.close()


def _quiet_pushes(monkeypatch, cpt, *, failing=False):
    def boom(skip=None):
        raise RuntimeError("FCM unavailable")

    monkeypatch.setattr(cpt, "_recently_pushed", lambda: set())
    monkeypatch.setattr(cpt, "first_lesson_activation",
                        boom if failing else (lambda skip=None: set()))
    monkeypatch.setattr(cpt, "streak_at_risk", lambda skip=None: set())
    monkeypatch.setattr(cpt, "win_back", lambda skip=None: set())


def test_a_failing_push_step_does_not_skip_the_fold(monkeypatch):
    # The fold is the only thing that expires raw IPs and user agents; it used
    # to run after the pushes, so any push exception skipped it.
    import ops.scripts.cron_push_triggers as cpt

    conn = get_conn()
    _raw_click(conn, "203.0.113.10", "Mozilla", "DA01", "-30 days")
    conn.commit()
    conn.close()
    _quiet_pushes(monkeypatch, cpt, failing=True)
    with pytest.raises(RuntimeError):
        cpt.main(["--force"])
    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) FROM referral_clicks").fetchone()[0] == 0
    conn.close()


def test_a_fold_that_cannot_run_is_loud_and_fails_the_run(monkeypatch, capsys):
    import ops.scripts.cron_push_triggers as cpt

    def no_compactor():
        raise ImportError("cannot import name 'compact_referral_clicks'")

    _quiet_pushes(monkeypatch, cpt)
    monkeypatch.setattr(cpt, "_load_compactor", no_compactor)
    assert cpt.main([]) == 2
    assert cpt.RETENTION_ALERT in capsys.readouterr().err
    _quiet_pushes(monkeypatch, cpt)
    monkeypatch.setattr(cpt, "_load_compactor",
                        lambda: (lambda dry_run=False: 0))
    assert cpt.main([]) == 0


def test_test_devices_are_not_installs(report_db, monkeypatch):
    """Eval-harness and remote-E2E devices (with the E2E install's twin) are
    neither a campaign's installs nor part of the every-new-device yardstick."""
    before = _data(report_db)
    conn = get_conn()
    _device(conn, "e2e-1", "2026-09-20 10:00:00")
    conn.execute("INSERT INTO child_profiles (device_id, name, age_group) "
                 "VALUES ('e2e-1', 'E2E-Maestro', '4-6')")
    _claim(conn, "e2e-1", "DA01", "2026-09-20 10:00:00")
    _device(conn, "e2e-1-twin", "2026-09-20 10:00:00")
    _claim(conn, "e2e-1-twin", "WA01", "2026-09-20 10:00:01")
    conn.execute("INSERT INTO push_tokens (device_id, token) VALUES ('e2e-1', 'fcm-e2e'), "
                 "('e2e-1-twin', 'fcm-e2e')")
    _device(conn, "eval-harness-real-5", "2026-09-21 10:00:00")
    conn.commit()
    conn.close()
    assert _data(report_db) == before

    monkeypatch.setattr(cr, "real_device_sql", lambda *a: "1")
    unfiltered = _data(report_db)
    assert unfiltered["campaigns"]["DA01"].new == before["campaigns"]["DA01"].new + 1
    assert unfiltered["everyone"].new == before["everyone"].new + 3


def test_the_test_devices_are_found_once_per_report(report_db, monkeypatch):
    calls = []
    sql = cr.e2e_devices_sql
    monkeypatch.setattr(cr, "e2e_devices_sql", lambda tables: calls.append(1) or sql(tables))
    _data(report_db)
    assert len(calls) == 1
