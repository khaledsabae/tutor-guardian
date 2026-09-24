import json
import sqlite3
from pathlib import Path

import pytest

from ops.scripts.weekly_funnel_report import (
    format_report,
    get_coach_tips_metrics,
    get_feedback_metrics,
    get_funnel_metrics,
    get_questions_and_quality,
    get_retention_metrics,
    load_suggested_questions,
)


@pytest.fixture
def mock_db(tmp_path: Path):
    db_file = tmp_path / "test_conversations.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE child_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            age_group TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE lesson_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            child_id INTEGER NOT NULL,
            lesson_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started',
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE chat_sessions (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            domain TEXT,
            mode TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE daily_login_streaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            child_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE coach_tips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            child_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            shown_at TEXT,
            tapped_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            rating TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE app_feedback (
            id TEXT PRIMARY KEY,
            message TEXT,
            audio_file TEXT,
            audio_b64 TEXT,
            device_id TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return db_file


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
        "INSERT INTO lesson_progress (device_id, child_id, lesson_id, status, started_at, completed_at) "
        "VALUES ('dev_A', 1, 'l1', 'completed', datetime('now', '-2 days'), datetime('now', '-2 days'))"
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
        "INSERT INTO lesson_progress (device_id, child_id, lesson_id, status, started_at) "
        "VALUES ('dev_B', 2, 'l1', 'in_progress', datetime('now', '-3 days'))"
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

    # Device D: From previous cohort (9 days ago), returned at Day 8 with streak
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group, created_at) "
        "VALUES ('dev_D', 'مريم', '7-9', datetime('now', '-9 days'))"
    )
    conn.execute(
        "INSERT INTO daily_login_streaks (device_id, child_id, date, created_at) "
        "VALUES ('dev_D', 4, date('now', '-1 days'), datetime('now', '-1 days'))"
    )

    # Coach tips & Feedback
    conn.execute(
        "INSERT INTO coach_tips (device_id, child_id, date, shown_at, tapped_at, created_at) "
        "VALUES ('dev_A', 1, date('now'), datetime('now'), datetime('now'), datetime('now'))"
    )
    conn.execute(
        "INSERT INTO coach_tips (device_id, child_id, date, shown_at, tapped_at, created_at) "
        "VALUES ('dev_B', 2, date('now'), datetime('now'), NULL, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO user_feedback (session_id, message_id, rating, created_at) "
        "VALUES ('sess_A', 2, 'helpful', datetime('now'))"
    )
    conn.commit()
    conn.close()

    # 1. Funnel
    funnel = get_funnel_metrics(mock_db, days=7, suggested=suggested)
    assert funnel["cohort_size"] == 3  # dev_A, dev_B, dev_C (dev_D is 9 days old)
    assert funnel["started_lesson"] == 2  # dev_A, dev_B
    assert funnel["completed_lesson"] == 1  # dev_A
    assert funnel["asked_question"] == 1  # dev_A only! (dev_B asked canned chatQ_prayer)

    # 2. Retention
    ret = get_retention_metrics(mock_db)
    assert ret["prev_cohort_size"] == 1  # dev_D
    assert ret["returned_d7"] == 1
    assert ret["d7_retention_pct"] == 100.0

    # 3. Quality & Questions
    qm = get_questions_and_quality(mock_db, days=7, suggested=suggested)
    assert qm["total_user_messages"] == 2
    assert qm["suggested_dropped"] == 1  # dev_B's message
    assert qm["genuine_questions"] == 1  # dev_A's message
    assert qm["unanswered_rate"] == 0.0

    # 4. Coach Tips
    tips = get_coach_tips_metrics(mock_db, days=7)
    assert tips["tips_shown"] == 2
    assert tips["tips_tapped"] == 1
    assert tips["tips_ctr"] == 50.0

    # 5. Feedback
    fb = get_feedback_metrics(mock_db, days=7)
    assert fb["ratings"] == {"helpful": 1}

    # 6. Report format
    report = format_report(7, funnel, ret, qm, tips, fb)
    assert "مسار التفعيل" in report
    assert "سارة" not in report  # Privacy: zero child names or question texts
    assert "طفلتي تعاني" not in report
    assert "تسريب التهيئة ← أول درس" in report
