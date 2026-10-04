import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ops.scripts.weekly_funnel_report import (
    count_orphans,
    format_report,
    get_action_events,
    get_coach_tips_metrics,
    get_cohort_retention,
    get_feedback_metrics,
    get_funnel_metrics,
    get_north_star,
    get_openers,
    get_questions_and_quality,
    get_stream_outcomes,
    load_suggested_questions,
)

# Copied from production (`SELECT sql FROM sqlite_master`, tg_backend,
# 2026-10-04) — not from init_db: the live schema differs (user_feedback has
# no message_id, chat_messages carries needs_human_review, lesson_progress has
# path_id/score, coach_tips has lang). A fixture written from the code's idea
# of the schema tests that idea, not production.
_PROD_SCHEMA = """
CREATE TABLE chat_sessions (
    id          TEXT PRIMARY KEY,
    device_id   TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    metadata    TEXT
);
CREATE TABLE chat_messages (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id         TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role               TEXT NOT NULL,
    content            TEXT NOT NULL,
    domain             TEXT,
    severity           TEXT,
    mode               TEXT,
    needs_human_review INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE "lesson_progress" (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id      TEXT NOT NULL,
    child_id       INTEGER NOT NULL DEFAULT 0,
    path_id        TEXT NOT NULL,
    lesson_id      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'not_started',
    started_at     TEXT,
    completed_at   TEXT,
    score          INTEGER,
    updated_at     TEXT,
    UNIQUE (device_id, child_id, lesson_id)
);
CREATE TABLE habits_value_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    child_id    INTEGER NOT NULL,
    category    TEXT NOT NULL,
    habit_name  TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_by TEXT NOT NULL DEFAULT 'parent',
    device_timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE child_missions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     TEXT NOT NULL,
    child_id      INTEGER NOT NULL,
    mission_key   TEXT NOT NULL,
    local_date    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'assigned',
    assigned_at   TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at    TEXT,
    confirmed_at  TEXT,
    parent_note   TEXT,
    UNIQUE (child_id, local_date, mission_key)
);
CREATE TABLE child_challenges (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     TEXT NOT NULL,
    child_id      INTEGER NOT NULL,
    challenge_key TEXT NOT NULL,
    topic         TEXT NOT NULL,
    domain        TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    note          TEXT,
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at   TEXT
);
CREATE TABLE coach_tips (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL,
    child_id     INTEGER NOT NULL,
    date         TEXT NOT NULL,
    domain       TEXT,
    text         TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'fallback',
    shown_at     TEXT,
    tapped_at    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    lang TEXT,
    UNIQUE (device_id, child_id, date)
);
CREATE TABLE child_profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    age_group   TEXT NOT NULL,
    gender      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    avatar_emoji TEXT
);
CREATE TABLE daily_login_streaks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    child_id    INTEGER NOT NULL,
    date        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(device_id, child_id, date)
);
CREATE TABLE user_feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    rating     TEXT NOT NULL,
    comment    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE app_feedback (
    id TEXT PRIMARY KEY,
    message TEXT,
    contact TEXT,
    audio_file TEXT,
    device_id TEXT,
    app_version TEXT,
    created_at TEXT,
    audio_b64 TEXT,
    tg_message_id INTEGER
);
"""


@pytest.fixture
def mock_db(tmp_path: Path):
    db_file = tmp_path / "test_conversations.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(_PROD_SCHEMA)
    conn.commit()
    conn.close()
    return db_file


def _iso(dt: datetime) -> str:
    """The ISO-with-offset shape missions and feedback are written in."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")


def _sql(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_funnel_and_filtering(mock_db: Path, tmp_path: Path):
    # Setup mock ARB
    arb_file = tmp_path / "app_ar.arb"
    arb_file.write_text(
        json.dumps({
            "chatQ_prayer": "كيف أحبب طفلي في الصلاة؟",
            "chatQ_sleep": "كيف أنظم نوم طفلي؟",
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    suggested = load_suggested_questions(arb_file)
    assert len(suggested) == 2

    conn = sqlite3.connect(mock_db)

    # Device A: Created child, started lesson, completed lesson, asked real question
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group, created_at) "
        "VALUES ('dev_A', 'سارة', '4-6', datetime('now', '-2 days'))"
    )
    conn.execute(
        "INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, started_at, completed_at) "
        "VALUES ('dev_A', 1, 'p1', 'l1', 'completed', datetime('now', '-2 days'), datetime('now', '-2 days'))"
    )
    conn.execute(
        "INSERT INTO chat_sessions (id, device_id, created_at) "
        "VALUES ('sess_A', 'dev_A', datetime('now', '-2 days'))"
    )
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, domain, created_at) "
        "VALUES ('sess_A', 'user', 'طفلتي تعاني من الخوف الشديد ليلاً ماذا أفعل؟', 'تربية', datetime('now', '-2 days'))"
    )
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, domain, mode, created_at) "
        "VALUES ('sess_A', 'assistant', 'طمئن طفلتك واقرأ معها الأذكار...', 'تربية', 'normal', datetime('now', '-2 days'))"
    )

    # Device B: Created child, started lesson (not completed), asked ONLY suggested question
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group, created_at) "
        "VALUES ('dev_B', 'أحمد', '4-6', datetime('now', '-3 days'))"
    )
    conn.execute(
        "INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, started_at) "
        "VALUES ('dev_B', 2, 'p1', 'l1', 'in_progress', datetime('now', '-3 days'))"
    )
    conn.execute(
        "INSERT INTO chat_sessions (id, device_id, created_at) "
        "VALUES ('sess_B', 'dev_B', datetime('now', '-3 days'))"
    )
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) "
        "VALUES ('sess_B', 'user', 'كيف أحبب طفلي في الصلاة؟', datetime('now', '-3 days'))"
    )
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, mode, created_at) "
        "VALUES ('sess_B', 'assistant', 'ابدأ بالقدوة الحسنة...', 'normal', datetime('now', '-3 days'))"
    )

    # Device C: Created child, dropped off immediately (no lesson, no question)
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group, created_at) "
        "VALUES ('dev_C', 'عمر', '2-3', datetime('now', '-1 days'))"
    )

    # Coach tips & Feedback (feedback is written ISO-with-offset in production)
    conn.execute(
        "INSERT INTO coach_tips (device_id, child_id, date, text, shown_at, tapped_at, created_at) "
        "VALUES ('dev_A', 1, date('now'), 'نص', datetime('now'), datetime('now'), datetime('now'))"
    )
    conn.execute(
        "INSERT INTO coach_tips (device_id, child_id, date, text, shown_at, tapped_at, created_at) "
        "VALUES ('dev_B', 2, date('now'), 'نص', datetime('now'), NULL, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO user_feedback (session_id, rating, created_at) VALUES ('sess_A', 'up', ?)",
        (_iso(datetime.utcnow()),),
    )
    conn.commit()
    conn.close()

    # 1. Funnel
    funnel = get_funnel_metrics(mock_db, days=7, suggested=suggested)
    assert funnel["cohort_size"] == 3  # dev_A, dev_B, dev_C
    assert funnel["started_lesson"] == 2  # dev_A, dev_B
    assert funnel["completed_lesson"] == 1  # dev_A
    assert funnel["asked_question"] == 1  # dev_A only! (dev_B asked canned chatQ_prayer)

    # 2. Quality & Questions
    qm = get_questions_and_quality(mock_db, days=7, suggested=suggested)
    assert qm["total_user_messages"] == 2
    assert qm["suggested_dropped"] == 1  # dev_B's message
    assert qm["genuine_questions"] == 1  # dev_A's message
    assert qm["unanswered_rate"] == 0.0

    # 3. Coach Tips
    tips = get_coach_tips_metrics(mock_db, days=7)
    assert tips["tips_shown"] == 2
    assert tips["tips_tapped"] == 1
    assert tips["tips_ctr"] == 50.0

    # 4. Feedback
    fb = get_feedback_metrics(mock_db, days=7)
    assert fb["ratings"] == {"up": 1}

    # 5. Report format
    north = get_north_star(mock_db)
    openers = get_openers(mock_db)
    cohorts = get_cohort_retention(mock_db)
    report = format_report(7, north, openers, cohorts, funnel, qm, tips, fb)
    assert "مسار التفعيل" in report
    assert "النجم الشمالي" in report
    assert "تقريبي" in report  # openers are labelled a proxy
    assert "سارة" not in report  # Privacy: zero child names or question texts
    assert "طفلتي تعاني" not in report
    assert "تسريب التهيئة ← أول درس" in report
    assert "daily_login_streaks" not in report


# ── North Star ─────────────────────────────────────────────────────────

def _seed_actions(conn, now: datetime) -> None:
    """One device per action source, all inside the latest week, plus noise."""
    d = now - timedelta(days=1)
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s1', 'q')")
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES ('s1','user','سؤال حقيقي عن ابني', ?)",
        (_sql(d),),
    )
    # The assistant's own row is not a family action.
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s2', 'asst_only')")
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES ('s2','assistant','رد', ?)",
        (_sql(d),),
    )
    conn.execute(
        "INSERT INTO lesson_progress (device_id, child_id, path_id, lesson_id, status, updated_at) "
        "VALUES ('lesson', 1, 'p', 'l', 'in_progress', ?)", (_sql(d),),
    )
    conn.execute(
        "INSERT INTO habits_value_events (device_id, child_id, category, habit_name, status, created_at) "
        "VALUES ('habit', 1, 'c', 'h', 'completed', ?)", (_sql(d),),
    )
    conn.execute(
        "INSERT INTO child_missions (device_id, child_id, mission_key, local_date, assigned_at, confirmed_at) "
        "VALUES ('mission', 1, 'm', '2026-01-01', ?, ?)",
        (_iso(now - timedelta(days=40)), _iso(d)),  # assigned long ago, confirmed this week
    )
    conn.execute(
        "INSERT INTO child_challenges (device_id, child_id, challenge_key, topic, started_at) "
        "VALUES ('challenge', 1, 'k', 't', ?)", (_sql(d),),
    )
    # Opening the app (a coach tip fetch) is not an action.
    conn.execute(
        "INSERT INTO coach_tips (device_id, child_id, date, text) VALUES ('opener', 1, ?, 'نص')",
        (d.date().isoformat(),),
    )


def test_north_star_counts_each_action_source_once_per_device(mock_db: Path):
    now = datetime(2026, 10, 4, 12, 0, 0)
    conn = sqlite3.connect(mock_db)
    _seed_actions(conn, now)
    # Same device acting twice in a week is still one family.
    conn.execute(
        "INSERT INTO habits_value_events (device_id, child_id, category, habit_name, status, created_at) "
        "VALUES ('habit', 1, 'c', 'h2', 'completed', ?)", (_sql(now - timedelta(days=2)),),
    )
    # Previous week: one family.
    conn.execute(
        "INSERT INTO habits_value_events (device_id, child_id, category, habit_name, status, created_at) "
        "VALUES ('old', 1, 'c', 'h', 'completed', ?)", (_sql(now - timedelta(days=10)),),
    )
    conn.commit()
    conn.close()

    weeks = get_north_star(mock_db, weeks=3, now=now)
    assert [w["families"] for w in weeks] == [5, 1, 0]


def test_action_events_normalise_iso_timestamps(mock_db: Path):
    """Missions are stored ISO-with-'T'; compared raw against 'YYYY-MM-DD HH:MM'
    they sort after every same-day timestamp and leak across the cut-off."""
    now = datetime(2026, 10, 4, 12, 0, 0)
    conn = sqlite3.connect(mock_db)
    conn.execute(
        "INSERT INTO child_missions (device_id, child_id, mission_key, local_date, assigned_at) "
        "VALUES ('early', 1, 'm', '2026-09-27', ?)", (_iso(datetime(2026, 9, 27, 6, 0, 0)),),
    )
    conn.commit()
    conn.close()
    events = get_action_events(mock_db, since=datetime(2026, 9, 27, 11, 0, 0))
    assert events == []


def test_openers_is_distinct_devices_with_a_tip_per_week(mock_db: Path):
    now = datetime(2026, 10, 4, 12, 0, 0)
    conn = sqlite3.connect(mock_db)
    for dev, child, day in [("a", 1, "2026-10-04"), ("a", 2, "2026-10-04"),
                            ("a", 1, "2026-10-01"), ("b", 3, "2026-09-28"),
                            ("c", 4, "2026-09-27")]:
        conn.execute(
            "INSERT INTO coach_tips (device_id, child_id, date, text) VALUES (?, ?, ?, 'نص')",
            (dev, child, day),
        )
    conn.commit()
    conn.close()
    weeks = get_openers(mock_db, weeks=2, now=now)
    assert weeks[0] == {"start": "2026-09-28", "end": "2026-10-04", "devices": 2}
    assert weeks[1]["devices"] == 1  # c on 09-27


# ── Cohort retention ───────────────────────────────────────────────────

def test_cohort_retention_counts_only_measurable_devices(mock_db: Path):
    now = datetime(2026, 10, 4, 12, 0, 0)  # a Sunday
    conn = sqlite3.connect(mock_db)
    # Cohort week of Monday 2026-08-24: two devices, both old enough for D30.
    conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at) "
                 "VALUES ('ret', 'x', '4-6', '2026-08-25 10:00:00')")
    conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at) "
                 "VALUES ('gone', 'y', '4-6', '2026-08-26 10:00:00')")
    # A second child later does not move the device's cohort.
    conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at) "
                 "VALUES ('ret', 'z', '7-9', '2026-09-20 10:00:00')")
    # ret: opened on day 1 (tip), acted on day 8, opened on day 31.
    conn.execute("INSERT INTO coach_tips (device_id, child_id, date, text) VALUES ('ret', 1, '2026-08-26', 'ن')")
    conn.execute("INSERT INTO habits_value_events (device_id, child_id, category, habit_name, status, created_at) "
                 "VALUES ('ret', 1, 'c', 'h', 'completed', '2026-09-02 09:00:00')")
    conn.execute("INSERT INTO coach_tips (device_id, child_id, date, text) VALUES ('ret', 1, '2026-09-25', 'ن')")
    # Cohort week of Monday 2026-09-28 is the current week → excluded.
    conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at) "
                 "VALUES ('new', 'w', '4-6', '2026-10-01 10:00:00')")
    # Cohort week of 2026-09-21: a device from 09-26 is too young for D7.
    conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at) "
                 "VALUES ('young', 'v', '4-6', '2026-09-26 10:00:00')")
    conn.commit()
    conn.close()

    rows = {r["week"]: r for r in get_cohort_retention(mock_db, cohorts=6, now=now)}
    assert "2026-09-28" not in rows
    aug = rows["2026-08-24"]
    assert aug["size"] == 2
    assert aug["d1_open"] == (1, 2)
    assert aug["d7_open"] == (1, 2)   # the day-8 action is also an open
    assert aug["d7_action"] == (1, 2)
    assert aug["d30_open"] == (1, 2)
    young = rows["2026-09-21"]
    assert young["size"] == 1
    assert young["d1_open"] == (0, 1)
    assert young["d7_open"] == (0, 0)  # window not over → not measurable
    assert young["d30_open"] == (0, 0)


def test_cohort_report_shows_dash_for_unmeasurable(mock_db: Path):
    now = datetime(2026, 10, 4, 12, 0, 0)
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO child_profiles (device_id, name, age_group, created_at) "
                 "VALUES ('young', 'v', '4-6', '2026-09-26 10:00:00')")
    conn.commit()
    conn.close()
    cohorts = get_cohort_retention(mock_db, cohorts=2, now=now)
    report = format_report(
        7, [], [], cohorts,
        {"cohort_size": 0, "started_lesson": 0, "completed_lesson": 0, "asked_question": 0,
         "started_pct": 0.0, "completed_pct": 0.0, "asked_pct": 0.0},
        {"total_user_messages": 0, "suggested_dropped": 0, "short_dropped": 0,
         "genuine_questions": 0, "tip_initiated_count": 0, "orphans": 0, "interrupted": 0,
         "errors": 0, "degraded": 0, "unanswered_rate": 0.0, "top_domains": []},
        {"tips_shown": 0, "tips_tapped": 0, "tips_ctr": 0.0},
        {"ratings": {}, "total_app_feedback": 0, "voice_notes": 0},
    )
    assert "2026-09-21 (n=1): D1 فتح 0% · D7 فتح — · D7 فعل — · D30 فتح —" in report
    # `interrupted` no longer means "the parent left": since the server
    # finishes a cut answer, it means the answer could not be completed.
    assert "لم يكتمل وحُفظ ما ظهر منه" in report
    assert "خروج من التطبيق/إيقاف" not in report


# ── Unanswered questions, by cause ─────────────────────────────────────

def test_unanswered_is_split_by_cause(mock_db: Path, tmp_path: Path):
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s', 'd')")
    rows = [
        ("user", "سؤال أول طويل بما يكفي", None),
        ("assistant", "رد كامل", "llm_generated"),
        ("user", "سؤال ثانٍ طويل بما يكفي", None),
        ("assistant", "جزء", "interrupted"),
        ("user", "سؤال ثالث طويل بما يكفي", None),
        ("assistant", "تعذّر توليد الرد", "error"),
        ("user", "سؤال رابع بلا أي رد", None),
    ]
    for role, content, mode in rows:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, mode) VALUES ('s', ?, ?, ?)",
            (role, content, mode),
        )
    conn.commit()
    conn.close()

    sessions_db = tmp_path / "sessions.db"
    s = sqlite3.connect(sessions_db)
    s.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, ts TEXT, domain TEXT, behavior_type TEXT, "
              "age_group TEXT, severity TEXT, mode TEXT, needs_human_review INTEGER, "
              "reply_length INTEGER, retrieved_count INTEGER, flag TEXT)")
    now_iso = _iso(datetime.utcnow())
    for i, flag in enumerate(["client_left_before_first_token", "client_left_before_first_token",
                              "first_token_timeout", "pipeline_error:RuntimeError", "no_results", "",
                              "stream_error:RuntimeError", "completed_after_disconnect",
                              "superseded", "stopped_by_parent", "stopped_by_parent"]):
        s.execute("INSERT INTO sessions (id, ts, mode, flag) VALUES (?, ?, 'x', ?)", (str(i), now_iso, flag))
    s.execute("INSERT INTO sessions (id, ts, mode, flag) VALUES ('old', ?, 'x', 'first_token_timeout')",
              (_iso(datetime.utcnow() - timedelta(days=30)),))
    s.commit()
    s.close()

    qm = get_questions_and_quality(mock_db, 7, set(), sessions_db)
    assert qm["total_user_messages"] == 4
    assert qm["orphans"] == 1
    assert qm["interrupted"] == 1
    assert qm["errors"] == 1
    assert qm["degraded"] == 2
    assert qm["unanswered_rate"] == 75.0
    assert qm["stream_outcomes"] == {
        "client_left_before_first_token": 2, "first_token_timeout": 1,
        "stream_stalled": 0, "stream_error": 1, "pipeline_error": 1,
        "superseded": 1, "stopped_by_parent": 2, "completed_after_disconnect": 1,
    }
    assert get_stream_outcomes(tmp_path / "missing.db", 7) == {}


def test_a_pending_answer_left_behind_counts_as_unfinished(mock_db: Path):
    """T5 — a 'pending' row is finished in place within minutes; one still
    pending long after was cut by a server restart and is not an answer."""
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s', 'd')")
    for role, content, mode, age in [
        ("user", "سؤال أول طويل بما يكفي", None, "-30 minutes"),
        ("assistant", "جزء بقي معلقًا", "pending", "-30 minutes"),
        ("user", "سؤال ثانٍ طويل بما يكفي", None, "-1 minutes"),
        ("assistant", "يُكتب الآن", "pending", "-1 minutes"),
    ]:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, mode, created_at) "
            "VALUES ('s', ?, ?, ?, datetime('now', ?))",
            (role, content, mode, age),
        )
    conn.commit()
    conn.close()

    qm = get_questions_and_quality(mock_db, 7, set())
    assert qm["orphans"] == 0
    assert qm["interrupted"] == 1  # the stale one; the fresh one is being written
    assert qm["degraded"] == 1


def test_question_asked_again_before_the_answer_was_saved_is_not_an_orphan(mock_db: Path):
    """Q1, Q2, A1, A2 — the parent re-asked while the first answer was still
    being written (now routine: answers are finished after the app leaves).
    The old rule, "the next row is not a reply", called Q1 unanswered."""
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('s', 'd')")
    conn.execute("INSERT INTO chat_sessions (id, device_id) VALUES ('t', 'e')")
    for sid, role, content, mode in [
        ("s", "user", "سؤال أول طويل بما يكفي", None),
        ("t", "user", "سؤال في جلسة أخرى بلا رد", None),
        ("s", "user", "سؤال ثانٍ قبل حفظ الرد الأول", None),
        ("s", "assistant", "رد الأول", "llm_generated"),
        ("s", "assistant", "رد الثاني", "llm_generated"),
    ]:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, mode) VALUES (?, ?, ?, ?)",
            (sid, role, content, mode),
        )
    conn.commit()
    conn.close()

    qm = get_questions_and_quality(mock_db, 7, set())
    assert qm["total_user_messages"] == 3
    assert qm["orphans"] == 1  # only session t's question


def test_count_orphans_pairs_replies_in_order():
    rows = [("a", "user"), ("a", "user"), ("a", "assistant"),   # one left
            ("b", "assistant"), ("b", "user"),                  # reply to an older window
            ("c", "user"), ("c", "assistant"), ("c", "assistant")]
    assert count_orphans(rows) == 2
    assert count_orphans([{"session_id": "x", "role": "user"}]) == 1
