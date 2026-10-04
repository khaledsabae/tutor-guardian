"""The privacy policy must say what the code does — and keep saying it.

Until 2026-10-04 docs/privacy-policy.md said child profiles and progress stayed
on the device and named Google as the only third party, while production kept
both server-side and sent every question to DeepSeek and to tafsir.net. Google
Play's User Data policy treats a false policy as a violation in itself.

These tests tie the text to the code, so a change on either side that makes it
false again fails the build:
  * no "on-device only" claim, in either language;
  * every table that holds a user's data maps to a sentence the policy contains;
  * every external host the backend calls is a processor the policy names;
  * every retention period the policy states is the constant the code uses;
  * /privacy-policy (the URL the app and Play link to) and /delete-account are
    served.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.routers import privacy as pv

ROOT = Path(__file__).resolve().parents[2]
POLICY = (ROOT / "docs" / "privacy-policy.md").read_text(encoding="utf-8")
ARABIC, _, ENGLISH = POLICY.partition("## English")


def test_both_languages_are_present():
    assert "## عربي" in ARABIC and ENGLISH.strip()
    for part in (ARABIC, ENGLISH):
        assert "support@alsaba.cloud" in part
        assert "https://tg-api.alsaba.cloud/delete-account" in part
        for name in ("DeepSeek", "Firebase", "Telegram", "Cloudflare", "Hostinger",
                     "tafsir.net", "Google Play Billing"):
            assert name in part, name


# Phrasings of the old, false claim. Matched loosely (case, hyphens, diacritics).
_ON_DEVICE_ONLY = (
    r"on[- ]device only", r"on your (?:device|phone) only", r"only on your (?:device|phone)",
    r"stored (?:only )?locally only", r"never leaves? your (?:device|phone)",
    r"stays? on your (?:device|phone) only", r"local[- ]only",
    r"على جهازك فقط", r"على هاتفك فقط", r"محلي[اًّ]* فقط", r"تُخزَّن على جهازك فقط",
    r"تخزن على جهازك فقط", r"لا تغادر (?:جهازك|هاتفك)", r"على الجهاز فقط",
)


def _strip_diacritics(text: str) -> str:
    return re.sub(r"[ً-ْ]", "", text)


@pytest.mark.parametrize("pattern", _ON_DEVICE_ONLY)
def test_policy_never_claims_on_device_only(pattern):
    text = _strip_diacritics(POLICY).lower()
    assert not re.search(_strip_diacritics(pattern).lower(), text), pattern


def test_profiles_progress_and_chat_are_declared_server_side():
    section = ENGLISH.split("### What we store on our servers", 1)[1].split("###", 1)[0]
    for item in ("Child profiles", "Lesson progress", "questions you ask", "Child memory"):
        assert item in section, item
    section_ar = ARABIC.split("### ما نحفظه على خوادمنا", 1)[1].split("###", 1)[0]
    for item in ("ملفات الأطفال", "التقدّم في الدروس", "الأسئلة التي تطرحها", "ذاكرة الطفل"):
        assert item in section_ar, item


# ── Every stored table is disclosed ───────────────────────────────────────

# table → a phrase the English policy must contain. A new table holding a
# user's data cannot ship without a line here — and so without a line there.
TABLE_DISCLOSURE = {
    "api_tokens": "session tokens",
    "chat_sessions": "questions you ask",
    "chat_messages": "questions you ask",
    "user_feedback": "ratings",
    "app_feedback": "App feedback you send",
    "feedback_replies": "our replies",
    "child_profiles": "Child profiles",
    "lesson_progress": "Lesson progress",
    "daily_login_streaks": "daily streaks",
    "coach_tips": "daily tip",
    "child_challenges": "current challenge",
    "child_facts": "Child memory",
    "followups": "follow-ups",
    "weekly_plans": "weekly plan",
    "child_memory_settings": "memory switch",
    "child_daily_routines": "baby routine",
    "routine_events": "baby routine",
    "habits_value_events": "habit tracker",
    "habit_templates": "habits you add",
    "child_screen_sessions": "screen time",
    "child_missions": "daily missions",
    "family_agreements": "family agreement",
    "agreement_clauses": "family agreement",
    "child_licences": "internet licence",
    "child_scenario_answers": "internet licence",
    "child_web_claims": "QR codes",
    "push_tokens": "notification token",
    "push_sends": "log of the notifications we sent",
    "referral_codes": "invite code",
    "referrals": "which phone invited which",
    "referral_clicks": "IP address, browser type",
    "identity_links": "Google account",
    "parent_identities": "Google account",
    "user_backups": "Backup",
}


def _schema() -> dict[str, set[str]]:
    from app.routers import feedback
    from app.services import coach_service, story_service
    conn = get_conn()
    feedback._ensure_app_feedback_table(conn)
    story_service._ensure_schema(conn)
    conn.commit()
    conn.close()
    coach_service._ensure_coach_tips_table()
    conn = get_conn()
    try:
        return pv._table_columns(conn)
    finally:
        conn.close()


def test_every_table_holding_user_data_is_disclosed():
    schema = _schema()
    user_tables = {t for t, cols in schema.items() if "device_id" in cols}
    user_tables |= {t for t, *_ in pv.DEPENDENT_TABLES}
    user_tables |= {t for t, _ in pv.OTHER_DEVICE_COLUMNS}
    user_tables |= {t for t, _ in pv.IDENTITY_TABLES}
    user_tables.add("referral_clicks")          # personal (IP) though device-less
    missing = sorted(user_tables - set(TABLE_DISCLOSURE))
    assert missing == [], f"disclose in docs/privacy-policy.md and map here: {missing}"
    for table in sorted(user_tables & set(schema)):
        assert TABLE_DISCLOSURE[table].lower() in ENGLISH.lower(), table


# ── Every external host is a named processor ──────────────────────────────

HOST_DISCLOSURE = {
    "api.deepseek.com": "DeepSeek",
    "mcp.tafsir.net": "tafsir.net",
    "bahouth.tafsir.net": "Bahouth",
    "oauth2.googleapis.com": "Sign-In",
    "accounts.google.com": "Sign-In",
    "api.telegram.org": "Telegram",
    "fonts.googleapis.com": "Google Fonts",
    "play.google.com": "Google Play",
    "www.cloudflare.com": "Cloudflare",
}
_OWN_OR_INERT = {"tg-api.alsaba.cloud", "schema.org", "www.w3.org", "json-schema.org",
                 "www.sitemaps.org"}  # XML namespaces and our own domain: no call leaves


def test_every_external_host_in_the_backend_is_disclosed():
    hosts: set[str] = set()
    for f in (ROOT / "backend" / "app").rglob("*.py"):
        for m in re.finditer(r"https?://([a-zA-Z0-9.-]+\.[a-z]{2,})", f.read_text(encoding="utf-8")):
            hosts.add(m.group(1).lower())
    hosts = {h for h in hosts if h not in _OWN_OR_INERT and not h.endswith(".local")
             and h not in ("localhost",) and "example" not in h}
    unknown = sorted(hosts - set(HOST_DISCLOSURE))
    assert unknown == [], f"name these processors in the policy and map them here: {unknown}"
    for host in hosts:
        assert HOST_DISCLOSURE[host] in ENGLISH, host


# ── Retention periods are the code's ──────────────────────────────────────


def test_retention_periods_match_the_code():
    from app.routers import web
    from app.services import answer_cache, child_memory, fiqh_guard, retrieval

    assert "**180 days**" in ENGLISH and "**180 يومًا**" in ARABIC
    assert "TOKEN_TTL_DAYS\", \"180\"" in (ROOT / "backend/app/db/init_db.py").read_text()
    assert child_memory.FOLLOWUP_EXPIRE_DAYS == 21
    assert "**21 days**" in ENGLISH and "**21 يومًا**" in ARABIC
    assert web._CLICK_RETENTION == "-7 days"
    assert "**7 days**" in ENGLISH and "**7 أيام**" in ARABIC
    assert retrieval.RETRIEVAL_LOG_RETENTION_DAYS == 90
    assert fiqh_guard._retention_days() == 90
    assert ENGLISH.count("**90 days**") == 2 and ARABIC.count("**90 يومًا**") == 2
    assert answer_cache._TTL_DAYS == 45
    assert "**45 days**" in ENGLISH and "**45 يومًا**" in ARABIC
    assert "**30 days**" in ENGLISH and "**30 يومًا**" in ARABIC


# ── Served where the app and Play already link ────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_policy_url_serves_the_new_text(client):
    resp = client.get("/privacy-policy")
    assert resp.status_code == 200
    assert "markdown" in resp.headers["content-type"]
    assert "DeepSeek" in resp.text and "/delete-account" in resp.text


def test_delete_account_page(client):
    resp = client.get("/delete-account")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    html = resp.text
    assert html.count(pv.SUPPORT_EMAIL) >= 4               # visible + mailto, both languages
    assert "الإعدادات" in html and "Settings" in html       # the in-app path
    assert "30" in html and 'href="/privacy-policy"' in html
    # Nothing loads from a third party while someone reads how to leave.
    assert not re.search(r"<(?:link|script|img|iframe)[^>]+(?:src|href)=\"https?://", html)
    assert "fonts.googleapis" not in html
    # Public: no token needed.
    assert TestClient(client.app).get("/delete-account").status_code == 200
