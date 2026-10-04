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
POLICY_PATH = ROOT / "docs" / "privacy-policy.md"
# The backend image ships docs/ today (Dockerfile: COPY docs/), but a test that
# reads repo files outside backend/ skips where they are absent instead of
# failing the deploy gate (the pattern of 18da165c).
pytestmark = pytest.mark.skipif(not POLICY_PATH.exists(),
                                reason="docs/ not present (backend-only image)")
POLICY = POLICY_PATH.read_text(encoding="utf-8") if POLICY_PATH.exists() else ""
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
    # The FCM challenge behind memory, child deletion and account deletion.
    "device_proofs": "Phone verification",
    "device_proof_sessions": "Phone verification",
    "device_proof_challenges": "Phone-verification codes",
    "device_alerts": "previous phone's notification token",
    # PR #29: which old phone identifier now points at which (device twins).
    "device_aliases": "Phone identifier",
    "referral_codes": "invite code",
    "referrals": "which phone invited which",
    "referral_clicks": "browser's user agent",
    "identity_links": "Google account",
    "parent_identities": "Google account",
    "user_backups": "Backup",
    # Install attribution (PR #25): raw visits, then daily counts with no IP.
    "referral_click_days": "daily counts with no IP",
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
    # Personal (IP) though device-less; and PR #25's daily fold of the same
    # visits. Checked whenever the table exists — before #25 merges or after.
    user_tables |= {"referral_clicks", "referral_click_days"} & set(schema)
    missing = sorted(user_tables - set(TABLE_DISCLOSURE))
    assert missing == [], f"disclose in docs/privacy-policy.md and map here: {missing}"
    flat = " ".join(ENGLISH.split()).lower()      # markdown wraps lines anywhere
    for table in sorted(user_tables & set(schema)):
        assert TABLE_DISCLOSURE[table].lower() in flat, table


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
    # Support purchases (#21): the Play Developer API verifies a purchase, and
    # www.googleapis.com is that API's OAuth scope — both Google Play Billing.
    "androidpublisher.googleapis.com": "Google Play Billing",
    "www.googleapis.com": "Google Play Billing",
}
_OWN_OR_INERT = {"tg-api.alsaba.cloud", "schema.org", "www.w3.org", "json-schema.org",
                 "www.sitemaps.org",   # XML namespaces and our own domain: no call leaves
                 "support.google.com"}  # Play help-centre links in comments (#21)


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
    from app.services import answer_cache, attribution, child_memory, fiqh_guard, retention

    assert "**180 days**" in ENGLISH and "**180 يومًا**" in ARABIC
    assert "TOKEN_TTL_DAYS\", \"180\"" in (ROOT / "backend/app/db/init_db.py").read_text()
    assert child_memory.FOLLOWUP_EXPIRE_DAYS == 21
    from app.services import device_alerts, device_proof
    assert device_proof.COOLDOWN_HOURS == 72
    assert "**72 hours**" in ENGLISH and "**72 ساعة**" in ARABIC
    assert device_alerts.GIVE_UP.days == 3
    assert "**3 days** at most" in " ".join(ENGLISH.split()) and "**3 أيام**" in ARABIC
    assert "**21 days**" in ENGLISH and "**21 يومًا**" in ARABIC
    # Raw invite/campaign visits (IP + user agent): folded into daily counts
    # after a week by PR #25's compaction, run daily from cron_push_triggers.
    assert attribution.CLICK_RAW_RETENTION_DAYS == 7
    assert "**7 days**" in ENGLISH and "**7 أيام**" in ARABIC
    assert retention.DAYS["retrieval_log"] == retention.DAYS["query_rewrites"] == 90
    assert retention.DAYS["llm_calls"] == retention.DAYS["sessions"] == 90
    assert retention.DAYS["blocked_fiqh_log"] == fiqh_guard._retention_days() == 90
    assert "**90 days**" in ENGLISH and "**90 يومًا**" in ARABIC
    assert answer_cache._TTL_DAYS == retention.DAYS["answer_cache"] == 45
    assert "**45 days**" in ENGLISH and "**45 يومًا**" in ARABIC
    assert "**30 days**" in ENGLISH and "**30 يومًا**" in ARABIC
    # Database backups on the VPS (/root/tg-backups) are kept 14 days.
    assert "**14 days**" in ENGLISH and "**14 يومًا**" in ARABIC


def test_no_deletion_is_claimed_before_it_has_run():
    """F8 (PR #26 review): the first clean-up runs after the deploy, so the
    policy says what *will* happen, not that it already did."""
    en = " ".join(ENGLISH.split())
    assert not re.search(r"\b(?:have|has) been (?:deleted|purged|removed|re-redacted)", en)
    assert "حُذف أو أُعيد إخفاؤه" not in ARABIC
    assert "first daily clean-up" in en and "التنظيف اليومي الأول" in " ".join(ARABIC.split())


def test_install_attribution_is_disclosed():
    """PR #25 records visits to tagged links; the policy says what and how long."""
    en, ar = " ".join(ENGLISH.split()), " ".join(ARABIC.split())
    for phrase in ("/go", "/ui/", "/l", "/p", "/seo", "/methodology", "ref or utm",
                   "/64", "within 24 hours", "**7 days**", "daily counts with no IP",
                   "Link-preview bots and prefetches are not recorded"):
        assert phrase in en, phrase
    for phrase in ("/methodology", "64 بتًا", "خلال 24 ساعة", "**7 أيام**",
                   "أعداد يومية بلا عنوان IP", "معاينة الروابط"):
        assert phrase in ar, phrase


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
