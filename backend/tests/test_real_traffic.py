"""app/core/real_traffic.py — which devices are test traffic, and the metric
scripts that leave them out (weekly dashboard, gap report, campaign report;
the funnel report has its own test in test_weekly_funnel_report.py).

The database is the app's schema (conftest runs init_db on a temp file), which
has push_tokens and — from schema v33 — device_aliases.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from app.core.real_traffic import (
    E2E_CHILD_NAME_LIKE,
    E2E_QUESTION_LIKE,
    e2e_devices,
    e2e_devices_sql,
    real_device_sql,
    real_session_sql,
    table_names,
)
from app.db.init_db import db_path, get_conn

E2E_QUESTION = "E2E test how can I teach my child to be honest"   # e2e/run.sh


def _child(conn, device, name="سارة", created="datetime('now', '-1 day')"):
    return conn.execute(
        f"INSERT INTO child_profiles (device_id, name, age_group, created_at) "
        f"VALUES (?, ?, '4-6', {created})", (device, name)).lastrowid


def _ask(conn, device, text, sid=None):
    sid = sid or f"s-{device}"
    conn.execute("INSERT OR IGNORE INTO chat_sessions (id, device_id) VALUES (?, ?)", (sid, device))
    conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', ?)",
                 (sid, text))
    conn.execute("INSERT INTO chat_messages (session_id, role, content, mode) "
                 "VALUES (?, 'assistant', 'رد', 'error')", (sid,))


def _token(conn, device, token):
    conn.execute("INSERT INTO push_tokens (device_id, token) VALUES (?, ?)", (device, token))


def _seed() -> None:
    """Real families, one E2E install of every shape, and an eval device."""
    conn = get_conn()
    # Real: a child whose name merely contains the marker's words, a parent
    # writing «E2E» mid-question, a session without a device.
    _child(conn, "real-1", name="Maestro")
    _ask(conn, "real-1", "My son loves E2E testing, how do I limit his screen time?")
    _token(conn, "real-1", "fcm-real")
    _child(conn, "real-2")
    _ask(conn, "real-2", "ابني يرفض النوم كل ليلة، ماذا أفعل؟")
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s-null', NULL)")
    conn.execute("INSERT INTO chat_messages (session_id, role, content) "
                 "VALUES ('s-null', 'user', 'سؤال قديم بلا جهاز')")
    # E2E: the marked install, its token twin, a flawed rename, a question-only
    # twin, and a twin folded away by the device-twin repair (v33 alias).
    _child(conn, "e2e-1", name="E2E-Maestro")
    _ask(conn, "e2e-1", E2E_QUESTION)
    _token(conn, "e2e-1", "fcm-e2e-1")
    _token(conn, "e2e-1-twin", "fcm-e2e-1")
    _ask(conn, "e2e-1-twin", "سؤال من التوأم بلا طفل")
    _child(conn, "e2e-2", name="E2E-Maestroي")
    _token(conn, "e2e-3-twin", "fcm-e2e-3")
    _ask(conn, "e2e-3-twin", E2E_QUESTION)
    conn.execute("INSERT INTO device_aliases (device_id, canonical_device) "
                 "VALUES ('e2e-2-alias', 'e2e-2')")
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s-alias', 'e2e-2-alias')")
    # Eval harness.
    _ask(conn, "eval-harness-real-12", "كيف أعلّم ابني الصدق دون عقاب؟")
    conn.commit()
    conn.close()


E2E = {"e2e-1", "e2e-1-twin", "e2e-2", "e2e-3-twin", "e2e-2-alias"}


def test_the_rule_finds_every_e2e_device_and_nothing_else():
    _seed()
    conn = get_conn()
    try:
        e2e = e2e_devices(conn)
        assert e2e == E2E
        kept = {r[0] for r in conn.execute(
            f"SELECT device_id FROM chat_sessions WHERE {real_device_sql('device_id', e2e)}")}
        asked = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE role = 'user' AND "
            f"{real_session_sql('session_id', e2e, table_names(conn))}").fetchone()[0]
    finally:
        conn.close()
    assert kept == {"real-1", "real-2", None}       # a session without a device stays
    assert asked == 3                                # real-1, real-2 and the device-less one


def test_a_device_less_e2e_question_never_hides_the_real_rows():
    """`x NOT IN (… NULL …)` is NULL for every x: one NULL in the E2E set would
    drop every real row from every metric."""
    _seed()
    conn = get_conn()
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s-null-e2e', NULL)")
    conn.execute("INSERT INTO chat_messages (session_id, role, content) "
                 "VALUES ('s-null-e2e', 'user', ?)", (E2E_QUESTION,))
    conn.commit()
    try:
        assert None not in {r[0] for r in conn.execute(e2e_devices_sql(table_names(conn)))}
        n = conn.execute(f"SELECT COUNT(*) FROM child_profiles WHERE "
                         f"{real_device_sql('device_id', e2e_devices(conn))}").fetchone()[0]
        # Even a None handed in by hand never reaches the SQL.
        assert conn.execute(f"SELECT COUNT(*) FROM child_profiles WHERE "
                            f"{real_device_sql('device_id', {None})}").fetchone()[0] == 4
    finally:
        conn.close()
    assert n == 2


def test_a_database_without_tokens_or_aliases(tmp_path):
    """Production today (schema 32): no device_aliases; and a bare database."""
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE child_profiles (id INTEGER PRIMARY KEY, device_id TEXT, name TEXT);"
        "CREATE TABLE chat_sessions (id TEXT PRIMARY KEY, device_id TEXT);"
        "CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT,"
        " content TEXT);"
        "INSERT INTO child_profiles (device_id, name) VALUES ('e', 'E2E-Maestro'), ('r', 'Ali');")
    assert e2e_devices(conn) == {"e"}
    bare = sqlite3.connect(":memory:")
    bare.execute("CREATE TABLE coach_tips (device_id TEXT)")
    bare.execute("INSERT INTO coach_tips VALUES ('a'), ('eval-harness-x')")
    assert e2e_devices(bare) == set()
    assert bare.execute(f"SELECT device_id FROM coach_tips WHERE "
                        f"{real_device_sql('device_id', set())}").fetchall() == [("a",)]
    assert real_session_sql("session_id", set(), set()) == "1"


def test_any_device_id_round_trips_through_the_literal():
    """The E2E set is one JSON literal in the SQL: a quote, non-ASCII or a NUL
    in an id must neither break the statement nor miss the device."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (device_id TEXT)")
    odd = ["e2e-'quote", "e2e-\u00e9\u0644", "e2e-\x00nul", 'e2e-"dq', "e2e-\\back"]
    conn.executemany("INSERT INTO t VALUES (?)", [(d,) for d in odd + ["real-'x", "real"]])
    kept = [r[0] for r in conn.execute(
        f"SELECT device_id FROM t WHERE {real_device_sql('device_id', odd)} ORDER BY 1")]
    assert kept == ["real", "real-'x"]


def test_markers_match_what_the_e2e_gate_writes():
    """The two markers are e2e/run.sh's defaults; drift there would silently
    let a whole E2E run back into the numbers."""
    from pathlib import Path
    run_sh = Path(__file__).resolve().parents[2] / "e2e" / "run.sh"
    if not run_sh.exists():
        pytest.skip("e2e/ not present (backend-only image)")
    src = run_sh.read_text(encoding="utf-8")
    assert 'CHILD_NAME="${E2E_CHILD_NAME:-E2E-Maestro}"' in src
    assert 'QUESTION="${E2E_QUESTION:-E2E test ' in src
    assert E2E_CHILD_NAME_LIKE == "E2E-Maestro%" and E2E_QUESTION_LIKE == "E2E test%"


# ── The metric scripts ─────────────────────────────────────────────────────


def test_campaign_report_mirror_matches_the_rule():
    """campaign_report.py copies the rule to run on a host whose backend
    predates it; the copy must be the rule."""
    cr = pytest.importorskip("ops.scripts.campaign_report")
    full = {"child_profiles", "chat_messages", "chat_sessions", "push_tokens", "device_aliases"}
    for tables in (full, full - {"device_aliases"}, {"child_profiles"},
                   {"chat_messages", "chat_sessions"}, set()):
        assert cr.e2e_devices_sql(tables) == e2e_devices_sql(tables)
    for e2e in (set(), {"e2e-1", "e2e-'q", "e2e-\u00e9"}, {None, "x"}):
        for column in ("device_id", "cs.device_id", "referred_device"):
            assert cr.real_device_sql(column, e2e) == real_device_sql(column, e2e)


def test_weekly_dashboard_counts_real_devices_only(monkeypatch):
    wd = pytest.importorskip("ops.scripts.weekly_dashboard")
    monkeypatch.setattr(wd, "_DB", db_path())
    _seed()
    today = datetime.utcnow().date()
    conn = get_conn()
    for device in ("real-2", "e2e-1", "e2e-1-twin", "eval-harness-real-12"):
        for day in (today, today - timedelta(days=1), today - timedelta(days=2)):
            conn.execute("INSERT INTO daily_login_streaks (device_id, child_id, date) "
                         "VALUES (?, 1, ?)", (device, day.isoformat()))
        conn.execute("INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, "
                     "status, updated_at) VALUES (?, 1, 'p', 'l', 'completed', ?)",
                     (device, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    stats = wd._db_stats()
    assert stats["total_sessions"] == 3              # real-1, real-2, the device-less one
    assert stats["total_children"] == 2
    assert stats["active_children_7d"] == stats["lessons_completed_7d"] == 1
    assert stats["logins_today"] == 1
    retention = wd._compute_retention()
    assert retention["total_active_7d"] == 1 and retention["d1_users"] == 1


def test_weekly_gap_report_reads_real_questions_only(tmp_path, monkeypatch):
    gap = pytest.importorskip("ops.scripts.weekly_kb_gap_report")
    monkeypatch.setattr(gap, "_DB", db_path())
    arb = tmp_path / "app_ar.arb"
    arb.write_text(json.dumps({"chatQ_sleep": "كيف أنظّم نوم طفلي؟"}), encoding="utf-8")
    _seed()
    questions, filt = gap.collect_questions(7, arb)
    assert filt["total"] == 3
    assert {q["device_id"] for q in questions} == {"real-1", "real-2", None}
    unanswered = gap.unanswered_stats(7)
    assert unanswered["total"] == 3
    assert unanswered["modes"] == {"error": 2}       # real-1's and real-2's answers only
