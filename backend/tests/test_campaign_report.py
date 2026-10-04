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


def _claim(conn, device, code, at):
    conn.execute("INSERT INTO referrals (referrer_device, referred_device, code, created_at) "
                 "VALUES (?, ?, ?, ?)", (f"campaign#{code}", device, code, at))


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
    _claim(conn, "a2", "DA01", "2026-09-02 10:00:00")
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
    _claim(conn, "a5", "DA01", "2026-09-01 10:00:00")
    conn.execute("INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, "
                 "started_at, updated_at) VALUES ('a5', ?, 'p', 'l2', 'in_progress', ?, ?)",
                 (kid5, "2026-09-01T11:00:00Z", "2026-09-08T09:59:00Z"))

    # WAAR: clicked, never installed.
    conn.execute("INSERT INTO referral_clicks (ip, code, clicked_at) VALUES "
                 "('198.51.100.1', 'WAAR', '2026-09-20 10:00:00')")
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
    assert (da.child, da.lesson) == (3, 2)                # a1 a2 a5 · a1 a5
    assert (da.d7_eligible, da.d7_active) == (3, 1)       # a1 a2 a5 eligible; a1 active
    assert da.first_seen == "2026-09-01 09:00:00"


def test_clicks_without_installs_still_show(report_db):
    wa = _data(report_db)["campaigns"]["WAAR"]
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
    assert "<b>DA01</b> · preacher_ar" in out and "WAAR" in out
    # No device ids, IPs or owners — and a person's own code never gets a line.
    for private in ("a1", "a2", "p1", "p2", "o1", "203.0.113", "inviter", "campaign#",
                    "ABC234", "ENV9Z5"):
        assert private not in out


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
    assert cr.DEVICE_CODE_ALPHABET == attribution.DEVICE_CODE_ALPHABET
    assert cr.DEVICE_CODE_LEN == attribution.DEVICE_CODE_LEN
    assert cr.PREVIEW_FETCHER_RE.pattern == attribution.PREVIEW_FETCHER_RE.pattern
    for code in ("DA01", "WAAR", "KT001", "ABC234", "C0001", "ENV9Z5", "DA0001",
                 "DA" + "9" * 14, "DA" + "9" * 15):
        assert cr.is_campaign_code(code) == attribution.is_campaign_code(code), code
