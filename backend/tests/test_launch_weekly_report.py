"""ops/scripts/launch_weekly_report.py — numbers checked by hand.

The database is built from production's own DDL (fixtures/
prod_launch_report_tables_2026-10-16.sql, copied read-only from tg_backend),
not from init_db. The GA4 and Play vitals parsers read real API responses
saved unedited on the same day.
"""
import json
import subprocess
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import ops.scripts.launch_weekly_report as lwr  # noqa: E402

_FIX = Path(__file__).parent / "fixtures"
SCHEMA = _FIX / "prod_launch_report_tables_2026-10-16.sql"
# Sunday 2026-10-18, 09:00 in Cairo (UTC+3 until the end of October).
NOW = datetime(2026, 10, 18, 6, 0, 0)


def _session(conn, device, at):
    conn.execute("INSERT INTO chat_sessions (id, device_id, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?)", (f"s-{device}", device, at, at))


def _ask(conn, device, at, text="كيف أعلّم ابني الصدق؟"):
    conn.execute("INSERT INTO chat_messages (session_id, role, content, created_at) "
                 "VALUES (?, 'user', ?, ?)", (f"s-{device}", text, at))


def _child(conn, device, at, name="سارة"):
    return conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at, "
                        "updated_at) VALUES (?, ?, '4-6', ?, ?)",
                        (device, name, at, at)).lastrowid


def _claim(conn, device, code, at, via="code"):
    conn.execute("INSERT INTO referrals (referrer_device, referred_device, code, created_at, via) "
                 "VALUES (?, ?, ?, ?, ?)", (f"campaign#{code}", device, code, at, via))


@pytest.fixture
def prod_db(tmp_path):
    path = tmp_path / "conversations.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    # ── North Star: this week = 10-11..10-17, last week = 10-04..10-10 ──
    _session(conn, "fam1", "2026-09-01 10:00:00")
    _ask(conn, "fam1", "2026-10-12 10:00:00")                     # this week
    _session(conn, "fam2", "2026-09-01 10:00:00")
    conn.execute("INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, "
                 "started_at, updated_at) VALUES ('fam2', 0, 'p', 'l1', 'in_progress', ?, ?)",
                 ("2026-10-05T09:00:00Z", "2026-10-05T09:00:00Z"))  # last week, 'T…Z'
    _session(conn, "fam3", "2026-09-01 10:00:00")
    conn.execute("INSERT INTO habits_value_events (device_id, child_id, category, habit_name, "
                 "status, created_at, updated_at) VALUES ('fam3', 0, 'manners', 'h', 'done', ?, ?)",
                 ("2026-10-13T08:00:00+00:00", "2026-10-13T08:00:00+00:00"))  # '+00:00'
    # Opened the app (a tip) but did nothing: not an action.
    _session(conn, "opener", "2026-09-01 10:00:00")
    conn.execute("INSERT INTO coach_tips (device_id, child_id, date, text) "
                 "VALUES ('opener', 0, '2026-10-14', 't')")
    # Test traffic: the E2E gate's device and an eval-harness device.
    _session(conn, "e2e1", "2026-10-12 09:00:00")
    _child(conn, "e2e1", "2026-10-12 09:00:00", name="E2E-Maestro")
    _ask(conn, "e2e1", "2026-10-12 09:01:00", text="E2E test how can I teach")
    _session(conn, "eval-harness-real-1", "2026-10-12 09:00:00")
    _ask(conn, "eval-harness-real-1", "2026-10-12 09:01:00")

    # ── DA01 ──
    for i in range(2):
        conn.execute("INSERT INTO referral_clicks (ip, user_agent, code, clicked_at) VALUES "
                     "(?, 'Mozilla/5.0 (Linux; Android 11)', 'DA01', '2026-10-12 08:00:00')",
                     (f"203.0.113.{i}",))
    conn.execute("INSERT INTO referral_clicks (ip, user_agent, code, clicked_at) VALUES "
                 "('198.51.100.9', 'WhatsApp/2.23.20.0 A', 'DA01', '2026-10-12 08:00:00')")
    # c1: back on day 1 (a tip), acts on day 9 → D1 and D7 both.
    _session(conn, "c1", "2026-09-20 10:00:00")
    kid1 = _child(conn, "c1", "2026-09-20 10:05:00")
    _claim(conn, "c1", "DA01", "2026-09-20 10:00:00")
    conn.execute("INSERT INTO coach_tips (device_id, child_id, date, text) "
                 "VALUES ('c1', ?, '2026-09-21', 't')", (kid1,))
    conn.execute("INSERT INTO child_missions (device_id, child_id, mission_key, local_date, "
                 "status, assigned_at, confirmed_at) VALUES ('c1', ?, 'm', '2026-09-29', "
                 "'confirmed', ?, ?)", (kid1, "2026-09-29T08:00:00+00:00",
                                         "2026-09-29T18:00:00+00:00"))
    # c2: matched by IP, never came back.
    _session(conn, "c2", "2026-09-22 10:00:00")
    _child(conn, "c2", "2026-09-22 10:05:00")
    _claim(conn, "c2", "DA01", "2026-09-22 10:00:00", via="auto")
    # c3: 4 days old — D1 measurable (a daily login), D7 not yet.
    _session(conn, "c3", "2026-10-14 10:00:00")
    _claim(conn, "c3", "DA01", "2026-10-14 10:00:00")
    conn.execute("INSERT INTO daily_login_streaks (device_id, child_id, date) "
                 "VALUES ('c3', 0, '2026-10-15')")
    # c4: claimed yesterday — its day 1 is today, not over.
    _session(conn, "c4", "2026-10-17 10:00:00")
    _claim(conn, "c4", "DA01", "2026-10-17 10:00:00")
    # c5: asked a question on day 3 only — active, but not in days 7–13.
    _session(conn, "c5", "2026-09-24 10:00:00")
    _claim(conn, "c5", "DA01", "2026-09-24 10:00:00")
    _ask(conn, "c5", "2026-09-27 10:00:00")
    # The E2E device claiming the code is not an install.
    _claim(conn, "e2e1", "DA01", "2026-10-12 09:00:30")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def db_numbers(prod_db):
    return lwr.collect_db(prod_db, NOW, 120)


def test_fixture_is_production_schema():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(referrals)")}
    assert "via" in cols  # added by a later migration, as in production
    assert {r[1] for r in conn.execute("PRAGMA table_info(lesson_progress)")} >= {
        "path_id", "score", "updated_at"}


def test_north_star_counts_real_families_with_an_action(db_numbers):
    weeks = db_numbers["north_star"]
    assert weeks[0] == {"start": "2026-10-11", "end": "2026-10-17", "families": 2}
    assert weeks[1] == {"start": "2026-10-04", "end": "2026-10-10", "families": 1}
    assert len(weeks) == 6


def test_campaign_code_installs_and_retention(db_numbers):
    da = db_numbers["campaigns"]["DA01"]
    assert da["clicks"] == 2            # the WhatsApp preview fetch is not a visit
    assert da["new"] == 5               # the E2E device's claim is left out
    assert (da["exact"], da["auto"]) == (4, 1)
    assert (da["d1_retained"], da["d1_eligible"]) == (2, 4)
    assert (da["d7_active"], da["d7_eligible"]) == (1, 3)


def test_second_wave_gate_reads_family_cohorts(db_numbers):
    gate = db_numbers["gate"]
    assert (gate["active"], gate["eligible"]) == (1, 2)


def test_db_numbers_carry_no_device_ids(db_numbers):
    text = json.dumps(db_numbers)
    for device in ("fam1", "c1", "c2", "e2e1", "opener"):
        assert f'"{device}"' not in text


def test_parse_cohorts_on_the_real_response():
    raw = json.loads((_FIX / "ga4_cohort_by_campaign_2026-10-16.json").read_text())["response"]
    out = lwr.parse_cohorts(raw)
    # fb4a: old cohort 271 users (54 on day 1, 16 on day 7) + 1 recent user.
    assert out["fb4a"] == {"d1": [54, 272], "d7": [16, 271]}
    assert out["fb_aug15"] == {"d1": [2, 5], "d7": [1, 5]}


def test_parse_vitals_on_the_real_response():
    raw = json.loads((_FIX / "play_vitals_crash_rate_2026-10-16.json").read_text())["response"]
    out = lwr.parse_vitals(raw)
    assert out == {"crash_rate": 0.0, "user_days": 340, "days": 5, "last_day": "2026-10-13"}


@pytest.mark.parametrize("db, ga4, expected", [
    ({"d1_retained": 2, "d1_eligible": 25}, None, "PD01: D1 8% (قاعدة، n=25) < 10% ⇒ أوقف"),
    ({"d1_retained": 4, "d1_eligible": 25}, None, "راقب"),
    ({"d1_retained": 6, "d1_eligible": 25}, None, "كمّل — ويجوز رفع الميزانية"),
    ({"d1_retained": 1, "d1_eligible": 5}, None, "أقل من 20"),
    # The larger sample decides: GA4 saw 40 installs, the claims only 5.
    ({"d1_retained": 5, "d1_eligible": 5}, [2, 40], "D1 5% (GA4، n=40) < 10% ⇒ أوقف"),
    (None, None, "لا قرار"),
])
def test_decide_code(db, ga4, expected):
    assert expected in lwr.decide_code("PD01", db, ga4)


def test_decide_code_budget_note_only_for_paid():
    line = lwr.decide_code("DA01", {"d1_retained": 6, "d1_eligible": 25}, None)
    assert line.endswith("⇒ كمّل")


def _ga4_bundle():
    return {
        "cohort_start": "2026-07-31",
        "new_users_by_source": [["(direct)", "(direct)", 40], ["google-play", "(not set)", 20],
                                ["google-play", "DA01", 40]],
        "campaign_new_users": {"DA01": 40, "(direct)": 40},
        "campaign_cohorts": {"DA01": {"d1": [2, 30], "d7": [1, 20]}},
        "events": {"horizon_strip_shown": [50, 40], "horizon_strip_tapped": [12, 10],
                   "horizon_to_action_48h": [4, 4], "lantern_lit": [90, 30]},
        "versions": [["1.0.73", 60, 0], ["1.0.71", 40, 2]],
        "active_users": 100,
        "crash": {"crash_affected_users": 2, "crash_free_users_rate": 0.98},
        "vitals": {"crash_rate": 0.0, "user_days": 340, "days": 5, "last_day": "2026-10-13"},
        "errors": [],
    }


def test_compose_writes_every_section_and_the_decisions(db_numbers):
    text = lwr.compose(db_numbers, _ga4_bundle(), [["DA01", "2026-10-01", 10.0]], "csv")
    for section in ("①", "②", "③", "④", "⑤", "⑥"):
        assert section in text
    assert "هذا الأسبوع 2 · الماضي 1" in text
    # D1 from GA4 (n=30) beats the 3 measurable claims.
    # The holder's name, from docs/marketing/campaign_codes.md, on both lines.
    assert "DA01 (د. هيثم طلعت): D1 7% (GA4، n=30) < 10% ⇒ أوقف" in text
    assert "DA01 (د. هيثم طلعت): نقرات" in text
    # spend 10 ÷ 1 family with a D7 action
    assert "صرف 10$ · 10 للأسرة الباقية (D7) · 2 للتثبيت" in text
    assert "(direct) 40% ≥ 30% ⇒ فيه لينكات من غير كود" in text
    assert "نُقر 10 (25%" in text and "فعل خلال 48 س 4 (40%)" in text
    assert "90 إضاءة على 30 مستخدم = 1.50 لكل نشط" in text
    assert "1.0.71: 2" in text
    assert "بلا أعطال 98.00% < 99.5%" in text
    # Sessions are not measurable here, and the report says so every week.
    assert "crash-free sessions): غير مقيسة" in text
    assert "D7 فعل تربوي 50.0% ≥ 12% ⇒ بوابة الموجة الثانية مفتوحة" in text


def test_compose_shows_a_bare_code_when_the_registry_has_no_name(db_numbers):
    text = lwr.compose(db_numbers, _ga4_bundle(), None, None, names={})
    assert "DA01: نقرات" in text and "DA01: D1 7%" in text
    assert lwr.decide_code("PD01", {"d1_retained": 9, "d1_eligible": 30}, None,
                           "PD01 (x)").endswith("كمّل — ويجوز رفع الميزانية")


def test_compose_without_ga4_says_so(db_numbers):
    text = lwr.compose(db_numbers, None, None, None)
    assert "لم تصل بيانات GA4" in text
    assert "GA4 غير متاح — لا رقم." in text
    assert "crash-free sessions): غير مقيسة" in text


def test_spend_csv_template_parses_empty():
    assert lwr.read_spend_csv(_ROOT / "docs" / "marketing" / "campaign_spend.csv") == []


def test_spend_csv_rows_and_errors(tmp_path):
    good = tmp_path / "s.csv"
    good.write_text("# note\ncode,date,amount\npd01,2026-10-25,3.5\nPD01,2026-10-26,3\n")
    assert lwr.read_spend_csv(good) == [["PD01", "2026-10-25", 3.5], ["PD01", "2026-10-26", 3.0]]
    bad = tmp_path / "b.csv"
    bad.write_text("PD01,2026-10-25\n")
    with pytest.raises(ValueError):
        lwr.read_spend_csv(bad)
    bad.write_text("PD01,25/10/2026,3\n")
    with pytest.raises(ValueError):
        lwr.read_spend_csv(bad)


class _Resp:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_send_telegram_plain_text_returns_message_ids(monkeypatch):
    sent = []

    def fake(req, timeout):
        sent.append(req.data.decode())
        return _Resp({"ok": True, "result": {"message_id": 41 + len(sent)}})
    monkeypatch.setattr(lwr.urllib.request, "urlopen", fake)
    ids = lwr.send_telegram("t", "c", "D1 8% < 10% ⇒ أوقف")
    assert ids == [42]
    assert "parse_mode" not in sent[0]   # «<» would break HTML mode


def test_send_telegram_raises_when_rejected(monkeypatch):
    monkeypatch.setattr(lwr.urllib.request, "urlopen",
                        lambda req, timeout: _Resp({"ok": False, "description": "bad"}))
    with pytest.raises(RuntimeError):
        lwr.send_telegram("t", "c", "x")


def test_cairo_hour_guard_skips(monkeypatch, capsys):
    monkeypatch.setattr(lwr, "_cairo_hour", lambda now: 10)
    monkeypatch.setattr(lwr, "fetch_ga4", lambda *a: pytest.fail("must not fetch"))
    assert lwr.main(["--via-ssh", "vps", "--only-at-cairo-hour", "9"]) == 0
    assert "skip" in capsys.readouterr().out


def test_cairo_hour_follows_dst():
    from datetime import timezone
    # 06:00 UTC is 09:00 in Cairo on 18 Oct (UTC+3) and 08:00 on 1 Nov (UTC+2).
    assert lwr._cairo_hour(datetime(2026, 10, 18, 6, tzinfo=timezone.utc)) == 9
    assert lwr._cairo_hour(datetime(2026, 11, 1, 6, tzinfo=timezone.utc)) == 8


def test_via_ssh_pipes_the_bundle_and_keeps_the_exit_code(monkeypatch, tmp_path):
    monkeypatch.setattr(lwr, "fetch_ga4", lambda key, today, days: {"errors": [], "x": 1})
    spend = tmp_path / "s.csv"
    spend.write_text("PD01,2026-10-25,3\n")
    seen = {}

    def fake_run(cmd, input, text, capture_output, timeout):
        seen["cmd"], seen["input"] = cmd, json.loads(input)
        return subprocess.CompletedProcess(cmd, 1, "", "boom\n")
    monkeypatch.setattr(lwr.subprocess, "run", fake_run)
    rc = lwr.main(["--via-ssh", "root@vps", "--spend-csv", str(spend), "--dry-run"])
    assert rc == 1                      # the container half's failure is not hidden
    assert seen["cmd"][-2] == "root@vps"
    assert seen["cmd"][-1].endswith("launch_weekly_report.py --ga4-json - --cohort-days 120 --dry-run")
    assert seen["input"]["spend"] == [["PD01", "2026-10-25", 3.0]]


def test_main_without_telegram_env_fails_loudly(prod_db, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert lwr.main(["--db", str(prod_db)]) == 1
    assert "nothing sent" in capsys.readouterr().err


def test_version_tuple():
    assert lwr.version_tuple("1.0.73") >= lwr.FEATURE_VERSION
    assert lwr.version_tuple("1.0.9") < lwr.FEATURE_VERSION
    assert lwr.version_tuple("(not set)") == ()


def test_week_windows():
    w = lwr.week_windows(date(2026, 10, 18))
    assert w["this"] == (date(2026, 10, 11), date(2026, 10, 17))
    assert w["last"] == (date(2026, 10, 4), date(2026, 10, 10))
