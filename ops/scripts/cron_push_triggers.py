#!/usr/bin/env python3
"""
ops/scripts/cron_push_triggers.py

Re-engagement push triggers — Phase 1.1 (schedule tuned in growth plan §4.2).
Runs as a VPS host cron, executing INSIDE the backend container (which has
firebase-admin + the DB). One run a day, UTC hour 17:
    0 17 * * * docker exec -w /app tg_backend python ops/scripts/cron_push_triggers.py >> /var/log/tg-push.log 2>&1

The 07 UTC run was dropped on 2026-08-13 with new_content_digest — see the
note at its deletion site. docs/OPS_RUNBOOK.md carries the authoritative
crontab table; both it and this line have to move together.

Needs env:
    FIREBASE_CREDENTIALS  (raw JSON) or backend/secrets/firebase-adminsdk.json
    TG_ADMIN_KEY          (unused here, but kept for symmetry)

Safe to run repeatedly: all sends are best-effort and idempotent-ish.
"""
import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:8000")
parser.add_argument("--dry-run", action="store_true")
parser.add_argument(
    "--force", action="store_true",
    help="تجاهل بوابة الساعة — للتجربة خارج نافذة الستين دقيقة اليومية",
)
parser.add_argument(
    "--cap-days", type=int, default=3,
    help="لا تُرسل لجهاز وصلته دفعة خلال هذا العدد من الأيام",
)
args = parser.parse_args()
BASE_URL = args.base_url.rstrip("/")
DRY_RUN = args.dry_run
FORCE = args.force
CAP_DAYS = args.cap_days

# Ensure project root on path for app imports.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# ruff: noqa: E402
from app.db.init_db import db_path
from app.services.push_sender import recently_pushed_since, send_to_device


DB_PATH = db_path()


def _send(device_id: str, title: str, body: str, data: dict):
    if DRY_RUN:
        print(f"  [dry-run] would send to {device_id}: {title}  data={data}")
        return {"ok": True, "dry_run": True}
    return send_to_device(device_id, title, body, data)


def _query(sql: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


# _device_ids_with_tokens() removed 2026-08-11 along with its only caller.
# "every device that ever registered a token" is not an audience, and having
# the helper sitting there made it the path of least resistance for the next
# broadcast someone adds.


# ── Deep links ───────────────────────────────────────────────────────────
#
# The installed client reads `data['link']` (push_service.dart) and only
# understands four shapes: /go, /inbox, /l/{id}, /p/{id}. Sending anything
# else — as this file did with "route": "/paths" — makes the tap a no-op AND
# skips Analytics.pushTapped, which is why push_tapped has never once fired.
#
# We link to /p/{path_id} rather than /l/{lesson_id} on purpose:
# PathDetailScreen resolves the real active child (path_detail_screen.dart:78)
# and passes it on to the lesson (:129), so the completion button appears and
# lesson_opened fires. A bare /l/ link does neither until the client fix for
# the null childId ships and is widely adopted.

# One curated entry path per age band. Deliberately hand-picked: the generic
# listing sorts by (age_group, domain, id), i.e. alphabetical domain, which is
# not a content decision and would greet a returning parent with whatever
# domain happens to sort first.
STARTER_PATHS = {
    "prenatal-1": "path_0-3_islamic_parenting_attachment",
    "0-3": "path_0-3_islamic_parenting_attachment",
    "2-3": "path_2-3_islamic_attachment",
    "4-6": "path_4-6_islamic_parenting_bond",
    "7-9": "path_7-9_islamic_parenting_akhlaq",
    "10-12": "path_10-12_islamic_parenting_identity",
    "13-15": "path_13-15_islamic_parenting_teen_identity",
    "16-18": "path_16-18_islamic_parenting_adult_faith",
}

# Unwinds to the home tab, where the daily tip already lives.
HOME_LINK = "/go"


def _deep_link_for(age_group: str | None) -> str:
    """A tappable destination for this device, falling back to home."""
    path_id = STARTER_PATHS.get((age_group or "").strip())
    return f"/p/{path_id}" if path_id else HOME_LINK


# Newest child on the device decides the destination; a device with several
# children gets the most recently touched one.
_LATEST_AGE_GROUP = """
    (SELECT c2.age_group FROM child_profiles c2
      WHERE c2.device_id = cp.device_id
      ORDER BY c2.updated_at DESC LIMIT 1)
"""


def _recently_pushed() -> set:
    """Devices already pushed within CAP_DAYS — the frequency cap.

    Without this, "one push a day" still means a permanently-lapsed device is
    nudged every single evening forever: streak_at_risk fires on >36h idle and
    win_back on >5 days idle, and neither condition ever stops being true for
    someone who has stopped using the app. Halving the volume does not change
    that; remembering what we already sent does.

    Three days is a starting value, not a measured one — CAP_DAYS is a flag and
    the run logs how many devices it filtered, so it can be tightened against
    numbers in a month rather than guessed at twice.
    """
    cutoff = (datetime.utcnow() - timedelta(days=CAP_DAYS)).isoformat()
    return recently_pushed_since(cutoff)


def streak_at_risk(skip: set | None = None) -> set:
    """Send to parents whose last lesson/login was >36h ago.
    Returns the device_ids notified so win_back can skip them (≤1 evening
    push per device — growth plan §4.2 anti-annoyance rule).
    `skip` carries the frequency cap; see [_recently_pushed]."""
    skip = skip or set()
    cutoff = (datetime.utcnow() - timedelta(hours=36)).isoformat()
    rows = _query(
        f"""
        SELECT cp.device_id, {_LATEST_AGE_GROUP} AS age_group
        FROM child_profiles cp
        LEFT JOIN lesson_progress lp
            ON lp.device_id = cp.device_id
        WHERE cp.device_id IN (
            SELECT device_id FROM push_tokens WHERE token IS NOT NULL AND token != ''
        )
        GROUP BY cp.device_id
        HAVING MAX(COALESCE(lp.updated_at, cp.created_at)) < ?
        """,
        (cutoff,),
    )
    sent: set = set()
    for r in rows:
        if r["device_id"] in skip:
            continue
        _send(
            device_id=r["device_id"],
            title="سلسلتك في انتظارك 🤍",
            body="درس جديد من «المربّي» ياخد دقيقتين — ادخل الحين واستمر في رحلة تربية أولادك.",
            data={"type": "streak_at_risk", "link": _deep_link_for(r["age_group"])},
        )
        sent.add(r["device_id"])
    return sent


# new_content_digest() removed 2026-08-13.
#
# It was the broad one: every device active within a 14-day window, every
# morning, with a body that carried no information («افتح المربّي واقرأ نصيحة
# اليوم») and a generic destination (/go). Measured 2026-07-31 → 2026-08-12:
# 37,393 FCM notifications to 1,567 users, 922 opened (2.5%), 25,327 dismissed
# (68%). An aggregate like that is dominated by whichever message goes to the
# most devices most often, which was this one.
#
# Those figures are FCM-only — GA4's notification_* events come from the FCM
# SDK, so the three on-device notifications the app also scheduled were never
# counted in them. That half was cut in the same release (v1.0.39+84).
#
# The evening run survives because it fires on a per-device reason rather than
# on the calendar, is deduped to at most one push per device, and links to
# /p/{path_id} — the only push whose effect is observable downstream as
# lesson_opened.
#
# Deleted rather than left disabled, for the reason recorded above about
# _device_ids_with_tokens: a broadcast helper sitting in the file is the path
# of least resistance for the next broadcast someone adds.


def win_back(skip: set | None = None):
    """Reach parents who have not opened the app for 5+ days — skipping any
    device already nudged by streak_at_risk in this run (max 1 evening push)."""
    skip = skip or set()
    cutoff = (datetime.utcnow() - timedelta(days=5)).isoformat()
    rows = _query(
        f"""
        SELECT DISTINCT cp.device_id, {_LATEST_AGE_GROUP} AS age_group
        FROM child_profiles cp
        WHERE cp.device_id IN (
            SELECT device_id FROM push_tokens WHERE token IS NOT NULL AND token != ''
        )
        AND (cp.updated_at IS NULL OR cp.updated_at < ?)
        """,
        (cutoff,),
    )
    for r in rows:
        if r["device_id"] in skip:
            continue
        _send(
            device_id=r["device_id"],
            title="مشتاقين ليك 🤍",
            body="رحلة تربية أولادك مستمرة — ادخل المربّي دلوقتي واكمل من حيث وقفت.",
            data={"type": "win_back", "link": _deep_link_for(r["age_group"])},
        )


if __name__ == "__main__":
    hour = datetime.utcnow().hour
    print(f"[{datetime.utcnow().isoformat()}] cron_push_triggers starting (UTC hour={hour})")

    # Evening re-engagement at 17 UTC (≈20:00 القاهرة والرياض — بعد المغرب،
    # وليس 23:00/منتصف الليل كما كانت 20 UTC). One push per device per day, and
    # at most one per CAP_DAYS days.
    #
    # --force exists because without it this is only testable inside a
    # sixty-minute window once a day: --dry-run printed nothing at any other
    # hour, which made "did the change work?" unanswerable until tomorrow.
    if FORCE or 17 <= hour < 18:
        skip = _recently_pushed()
        print(f"  -> streak_at_risk + win_back (deduped, {len(skip)} capped)")
        nudged = streak_at_risk(skip=skip)
        win_back(skip=nudged | skip)
    else:
        print("  -> outside the 17 UTC window; nothing to do (use --force to test)")

    print("done")
