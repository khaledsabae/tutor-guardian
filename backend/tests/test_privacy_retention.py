"""What the privacy policy promises about retention and redaction, enforced.

Each test pins one sentence of docs/privacy-policy.md to the code behind it:
  * the technical search log keeps questions 90 days, names replaced;
  * an invite-link visit (IP + browser) is kept 7 days;
  * a cached general answer, with its question, is gone after 45 days;
  * the weekly gap analysis, the feedback digest and the eval-set builder send
    no child name to a model;
  * an emailed deletion request runs the in-app deletion (ops/scripts).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pytest

from app.db.init_db import db_path, get_conn

NAME = "يوسف"


def _family(device: str, name: str = NAME) -> int:
    conn = get_conn()
    cid = conn.execute(
        "INSERT INTO child_profiles (device_id, name, age_group) VALUES (?, ?, '4-6')",
        (device, name)).lastrowid
    conn.commit()
    conn.close()
    return cid


def _session_with(device: str, *turns: tuple[str, str]) -> str:
    from app.services import conversation_store as store
    sid = store.create_session(device)
    for role, text in turns:
        store.add_message(sid, role, text)
    return sid


# ── Retention ─────────────────────────────────────────────────────────────


def _telemetry(tmp_path, monkeypatch):
    from app.services import ai_gateway, fiqh_guard, query_rewriter, retrieval, session_logger
    db = tmp_path / "sessions.db"
    for mod, attr in ((retrieval, "_TELEMETRY_DB"), (query_rewriter, "_CACHE_DB"),
                      (ai_gateway, "_TELEMETRY_DB"), (session_logger, "DB_PATH"),
                      (fiqh_guard, "_LOG_DB")):
        monkeypatch.setattr(mod, attr, db)
    from app.services import answer_cache
    monkeypatch.setattr(answer_cache, "_DB", db)
    monkeypatch.setattr(retrieval, "_log_schema_ready", False)
    monkeypatch.setattr(query_rewriter, "_schema_initialized", False)
    return db


def test_housekeeping_keeps_the_promised_retention(tmp_path, monkeypatch):
    """Run on a schedule (cron evening_run), not on traffic (P7)."""
    from app.services import retention, retrieval
    db = _telemetry(tmp_path, monkeypatch)
    retrieval.log_retrieval("سؤال جديد", ["tarbiyah"], "", [])
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO retrieval_log (ts, question, redacted) "
                 "VALUES (datetime('now', '-91 days'), 'قديم', 1)")
    conn.execute("INSERT INTO retrieval_log (question) VALUES ('سجّل قبل الإخفاء: يوسف')")
    conn.execute("CREATE TABLE llm_calls (id INTEGER PRIMARY KEY, ts TEXT, provider TEXT)")
    conn.execute("INSERT INTO llm_calls (ts, provider) VALUES (datetime('now','-100 days'), 'x')")
    conn.execute("INSERT INTO llm_calls (ts, provider) VALUES (datetime('now'), 'x')")
    conn.execute("CREATE TABLE sessions (id TEXT, ts TEXT)")
    conn.execute("INSERT INTO sessions VALUES ('old', '2020-01-01T10:00:00+00:00')")
    conn.execute("INSERT INTO sessions VALUES ('new', ?)", (datetime.utcnow().isoformat(),))
    conn.commit()
    conn.close()
    results = retention.run_housekeeping()
    assert not retention.has_errors(results), results
    conn = sqlite3.connect(db)
    assert [r[0] for r in conn.execute("SELECT question FROM retrieval_log")] == ["سؤال جديد"]
    assert conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 1
    assert [r[0] for r in conn.execute("SELECT id FROM sessions")] == ["new"]
    conn.close()


def test_housekeeping_reports_errors_instead_of_swallowing_them(tmp_path, monkeypatch):
    from app.services import retention, retrieval
    db = _telemetry(tmp_path, monkeypatch)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE retrieval_log (id INTEGER PRIMARY KEY, ts TEXT, question TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(retrieval, "_TELEMETRY_DB", tmp_path / "no-such-dir" / "x.db")
    results = retention.run_housekeeping()
    assert str(results["retrieval_log"]).startswith("error")
    assert retention.has_errors(results)


def test_cron_evening_run_fails_loudly_when_housekeeping_fails(monkeypatch, capsys):
    import ops.scripts.cron_push_triggers as cpt
    from app.services import retention
    monkeypatch.setattr(cpt, "DRY_RUN", False)
    monkeypatch.setattr(retention, "run_housekeeping",
                        lambda: {"retrieval_log": "error: OperationalError: disk I/O error"})
    assert cpt.privacy_housekeeping() is False
    assert "❌" in capsys.readouterr().out


def test_names_logged_before_redaction_are_purged_or_reredacted(tmp_path, monkeypatch):
    """Historical rows were written with names (P7): unmarked search-log,
    rewrite and cache rows go; the fiqh review log is re-redacted in place."""
    from app.services import answer_cache, retention
    db = _telemetry(tmp_path, monkeypatch)
    _family("dev-hist")                                   # a child named يوسف exists
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE query_rewrites (question_hash TEXT PRIMARY KEY, rewritten TEXT, "
                 "ts TEXT DEFAULT (datetime('now')))")
    conn.execute("INSERT INTO query_rewrites (question_hash, rewritten) VALUES ('h', 'نوم يوسف')")
    conn.execute("CREATE TABLE blocked_fiqh_log (id INTEGER PRIMARY KEY, question TEXT, "
                 "rule_id TEXT, created_at TEXT DEFAULT (datetime('now')))")
    conn.execute("INSERT INTO blocked_fiqh_log (question, rule_id) VALUES ('هل يجوز ليوسف', 'r1')")
    conn.commit()
    conn.close()
    with answer_cache._conn() as c:                       # creates the table, marker column
        c.execute("INSERT INTO answer_cache (qhash, question_norm, age_group, domain, severity, "
                  "answer) VALUES ('q', 'قديم', '4-6', 'tarbiyah', 'خفيف', 'مع يوسف جرّب…')")
    results = retention.run_housekeeping()
    assert not retention.has_errors(results), results
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM query_rewrites").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0] == 0
    assert conn.execute("SELECT question FROM blocked_fiqh_log").fetchone()[0] == "هل يجوز لطفلي"
    conn.close()


def test_unmarked_cached_answers_are_never_served(tmp_path, monkeypatch):
    from app.services import answer_cache
    _telemetry(tmp_path, monkeypatch)
    monkeypatch.setattr(answer_cache, "ANSWER_CACHE_ENABLED", True)
    monkeypatch.setattr(answer_cache, "_embed", lambda q: None)
    key = answer_cache._key("كيف أنظم نومه", "4-6", "tarbiyah", "خفيف")
    with answer_cache._conn() as c:
        c.execute("INSERT INTO answer_cache (qhash, question_norm, age_group, domain, severity, "
                  "answer) VALUES (?, 'q', '4-6', 'tarbiyah', 'خفيف', 'جواب قديم فيه يوسف')", (key,))
    assert answer_cache.lookup("كيف أنظم نومه", "4-6", "tarbiyah", "خفيف") is None


def test_invite_link_visits_are_kept_seven_days():
    from app.routers import web
    conn = get_conn()
    conn.execute("INSERT INTO referral_codes (device_id, code) VALUES ('dev-ref', 'ABC123')")
    conn.execute("INSERT INTO referral_clicks (ip, user_agent, code, clicked_at) "
                 "VALUES ('203.0.113.9', 'old-ua', 'ABC123', datetime('now', '-8 days'))")
    conn.execute("INSERT INTO referral_clicks (ip, user_agent, code, clicked_at) "
                 "VALUES ('203.0.113.8', 'recent-ua', 'ABC123', datetime('now', '-6 days'))")
    conn.commit()
    conn.close()
    web._record_click("198.51.100.7", "new-ua", "ABC123")
    conn = get_conn()
    uas = sorted(r[0] for r in conn.execute("SELECT user_agent FROM referral_clicks"))
    conn.close()
    assert uas == ["new-ua", "recent-ua"]


def test_expired_cached_answers_are_deleted(tmp_path, monkeypatch):
    from app.services import answer_cache
    monkeypatch.setattr(answer_cache, "ANSWER_CACHE_ENABLED", True)
    monkeypatch.setattr(answer_cache, "_DB", tmp_path / "cache.db")
    monkeypatch.setattr(answer_cache, "_embed", lambda q: None)
    long_answer = "إجابة عامة " * 20
    assert answer_cache.store("كيف أعوّد ابني على النوم", "4-6", "tarbiyah", "خفيف", long_answer)
    conn = sqlite3.connect(tmp_path / "cache.db")
    conn.execute("UPDATE answer_cache SET created_at = datetime('now', '-46 days')")
    conn.commit()
    conn.close()
    assert answer_cache.store("كيف أعلّم ابني الصدق", "4-6", "tarbiyah", "خفيف", long_answer)
    conn = sqlite3.connect(tmp_path / "cache.db")
    questions = [r[0] for r in conn.execute("SELECT question_norm FROM answer_cache")]
    conn.close()
    assert len(questions) == 1 and "الصدق" in questions[0]


# ── No child name to a model, offline paths included ──────────────────────


def test_feedback_digest_sends_no_child_name():
    from app.routers import feedback
    from app.services import feedback_analyzer
    _family("dev-fb")
    sid = _session_with("dev-fb", ("user", f"{NAME} يرفض النوم"),
                        ("assistant", f"جرّب مع {NAME} روتينًا ثابتًا"))
    conn = get_conn()
    feedback._ensure_app_feedback_table(conn)
    conn.execute("INSERT INTO user_feedback (session_id, message_id, rating, comment) "
                 "VALUES (?, 1, 'down', ?)", (sid, f"لم تفهم مشكلة {NAME}"))
    conn.execute("INSERT INTO app_feedback (id, message, device_id, created_at) "
                 "VALUES ('f1', ?, 'dev-fb', datetime('now'))", (f"{NAME} يحب التطبيق",))
    conn.commit()
    conn.close()
    items = feedback_analyzer.collect_feedback()
    rendered = feedback_analyzer._render_items(items, 0)
    assert items and NAME not in rendered
    assert "طفلي يرفض النوم" in rendered and "طفلي يحب التطبيق" in rendered


def test_weekly_gap_analysis_sends_no_child_name(tmp_path, monkeypatch):
    import ops.scripts.weekly_kb_gap_report as gap
    monkeypatch.setattr(gap, "_DB", db_path())
    arb = tmp_path / "app_ar.arb"
    arb.write_text(json.dumps({"chatQ_sleep": "كيف أنظّم نوم طفلي؟"}), encoding="utf-8")
    _family("dev-gap")
    _session_with("dev-gap", ("user", f"{NAME} يضرب أخته كل يوم ماذا أفعل"))
    questions, _ = gap.collect_questions(7, arb)
    assert questions and all(NAME not in q["content"] for q in questions)
    assert any("طفلي يضرب أخته" in q["content"] for q in questions)


def test_eval_set_builder_removes_family_names():
    import ops.tools.build_real_eval_set as builder
    _family("dev-eval")
    _session_with("dev-eval", ("user", f"كيف أتعامل مع عناد {NAME} عند النوم؟"))
    candidates = builder.collect_raw_candidates(db_path(), set())
    assert candidates and all(NAME not in c["question"] for c in candidates)


# ── An emailed request runs the in-app deletion ───────────────────────────


@pytest.fixture
def signed_in_account():
    conn = get_conn()
    conn.execute("INSERT INTO parent_identities (google_id, email) "
                 "VALUES ('g-mail', 'Parent@Example.com')")
    for dev in ("dev-mail-1", "dev-mail-2"):
        conn.execute("INSERT INTO child_profiles (device_id, name, age_group) "
                     "VALUES (?, 'سالم', '7-9')", (dev,))
        conn.execute("INSERT INTO identity_links (device_id, google_id) VALUES (?, 'g-mail')",
                     (dev,))
    conn.commit()
    conn.close()


def _children_of(*devices: str) -> int:
    conn = get_conn()
    n = conn.execute(
        f"SELECT COUNT(*) FROM child_profiles WHERE device_id IN ({','.join('?' * len(devices))})",
        devices).fetchone()[0]
    conn.close()
    return n


def test_delete_script_is_a_dry_run_unless_told(signed_in_account, capsys):
    import ops.scripts.delete_account as script
    assert script.main(["--email", "parent@example.com"]) == 0
    out = capsys.readouterr().out
    assert "2 device(s)" in out and "dry run" in out
    assert _children_of("dev-mail-1", "dev-mail-2") == 2


def test_delete_script_deletes_the_whole_google_account(signed_in_account, capsys):
    import ops.scripts.delete_account as script
    assert script.main(["--email", "parent@example.com", "--yes"]) == 0
    assert _children_of("dev-mail-1", "dev-mail-2") == 0
    conn = get_conn()
    left = conn.execute("SELECT COUNT(*) FROM parent_identities WHERE google_id = 'g-mail'"
                        ).fetchone()[0]
    conn.close()
    assert left == 0
    assert script.main(["--email", "nobody@example.com"]) == 2


def test_feedback_without_a_device_is_still_redacted():
    """P8: 5 of 26 production feedback rows have no device id — those used to
    reach the model as written. They get generic redaction (every known name)."""
    from app.routers import feedback
    from app.services import feedback_analyzer
    _family("dev-known", "ياسمين")
    conn = get_conn()
    feedback._ensure_app_feedback_table(conn)
    conn.execute("INSERT INTO app_feedback (id, message, device_id, created_at) "
                 "VALUES ('f-anon', ?, NULL, datetime('now'))", ("ياسمين بتحب التطبيق جدًا",))
    conn.commit()
    conn.close()
    rendered = feedback_analyzer._render_items(feedback_analyzer.collect_feedback(), 0)
    assert "ياسمين" not in rendered and "طفلي بتحب التطبيق" in rendered
