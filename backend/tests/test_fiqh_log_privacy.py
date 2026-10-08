"""Audit M4/M5 follow-up: the blocked-question log keeps the phrasing that
tripped a rule, not who asked — and not forever."""
import sqlite3

import pytest

from app.db.init_db import get_conn, init_db
from app.services import fiqh_guard


@pytest.fixture
def log_db(tmp_path, monkeypatch):
    init_db()
    conn = get_conn()
    conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES ('dev-1', 'سليم', '4-6')"
    )
    conn.commit()
    conn.close()
    path = tmp_path / "sessions.db"
    monkeypatch.setattr(fiqh_guard, "_LOG_DB", path)
    return path


def _logged(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT question FROM blocked_fiqh_log")]
    finally:
        conn.close()


def test_child_name_email_and_phone_are_masked(log_db):
    q = "ابني سليم بيسألني هل الموسيقى حرام؟ ردوا على parent.x@example.com أو 0100 123 4567"
    blocked, _ = fiqh_guard.check_fiqh_guard(q, "dev-1")
    assert blocked
    [stored] = _logged(log_db)
    assert "سليم" not in stored
    assert "example.com" not in stored and "[email]" in stored
    assert "4567" not in stored and "[phone]" in stored
    assert "الموسيقى حرام" in stored              # the part the review needs


def test_arabic_indic_phone_digits_are_masked(log_db):
    fiqh_guard.check_fiqh_guard("ما حكم الأغاني؟ رقمي ٠١٠٠١٢٣٤٥٦٧", "dev-1")
    [stored] = _logged(log_db)
    assert "٤٥٦٧" not in stored and "[phone]" in stored


def test_short_numbers_survive(log_db):
    # Ages and counts are part of the question, not contact details.
    fiqh_guard.check_fiqh_guard("هل يجوز الطلاق وأنا حامل في الشهر 7 وعندي 3 أطفال", "dev-1")
    [stored] = _logged(log_db)
    assert "7" in stored and "3" in stored


def test_rows_older_than_the_retention_are_dropped(log_db, monkeypatch):
    monkeypatch.setenv("FIQH_LOG_RETENTION_DAYS", "30")
    fiqh_guard.check_fiqh_guard("هل الرسم حرام؟", "dev-1")
    conn = sqlite3.connect(log_db)
    conn.execute("UPDATE blocked_fiqh_log SET created_at = datetime('now', '-31 days')")
    conn.commit()
    conn.close()
    fiqh_guard.check_fiqh_guard("ما حكم التصوير؟", "dev-1")
    assert _logged(log_db) == ["ما حكم التصوير؟"]


def test_a_failing_redaction_logs_only_hash_and_still_blocks(log_db, monkeypatch):
    import app.services.privacy as privacy

    def boom(*a, **k):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(privacy, "redact_for_cloud", boom)
    assert fiqh_guard.check_fiqh_guard("هل الرسم حرام؟", "dev-1")[0]
    import hashlib
    assert _logged(log_db) == ["sha256:" + hashlib.sha256("هل الرسم حرام؟".encode()).hexdigest()]
    with sqlite3.connect(log_db) as db:
        assert db.execute("SELECT redacted FROM blocked_fiqh_log").fetchone()[0] == 0
