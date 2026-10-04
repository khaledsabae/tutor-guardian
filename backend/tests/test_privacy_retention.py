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


def test_retrieval_log_keeps_90_days(tmp_path, monkeypatch):
    from app.services import retrieval
    monkeypatch.setattr(retrieval, "_TELEMETRY_DB", tmp_path / "telemetry.db")
    monkeypatch.setattr(retrieval, "_last_prune", float("-inf"))
    retrieval.log_retrieval("سؤال قديم", ["tarbiyah"], "", [])
    conn = sqlite3.connect(tmp_path / "telemetry.db")
    conn.execute("UPDATE retrieval_log SET ts = datetime('now', '-91 days')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(retrieval, "_last_prune", float("-inf"))
    retrieval.log_retrieval("سؤال جديد", ["tarbiyah"], "", [])
    conn = sqlite3.connect(tmp_path / "telemetry.db")
    rows = [r[0] for r in conn.execute("SELECT question FROM retrieval_log")]
    conn.close()
    assert rows == ["سؤال جديد"]


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
