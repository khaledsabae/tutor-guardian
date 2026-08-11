#!/usr/bin/env python3
"""
ops/scripts/cron_push_triggers.py

Re-engagement push triggers — Phase 1.1 (schedule tuned in growth plan §4.2).
Runs as a VPS host cron, executing INSIDE the backend container (which has
firebase-admin + the DB). UTC hours: 7 (morning tip) and 17 (evening nudges):
    0 7,17 * * * docker exec -w /app tg_backend python ops/scripts/cron_push_triggers.py >> /var/log/tg-push.log 2>&1

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
    "--digest-window-days", type=int, default=14,
    help="نافذة النشاط لنصيحة الصباح — جهاز صامت أطول منها لا تصله",
)
args = parser.parse_args()
BASE_URL = args.base_url.rstrip("/")
DRY_RUN = args.dry_run
DIGEST_WINDOW_DAYS = args.digest_window_days

# Ensure project root on path for app imports.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# ruff: noqa: E402
from app.db.init_db import db_path
from app.services.push_sender import send_to_device


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


def streak_at_risk() -> set:
    """Send to parents whose last lesson/login was >36h ago.
    Returns the device_ids notified so win_back can skip them (≤1 evening
    push per device — growth plan §4.2 anti-annoyance rule)."""
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
        _send(
            device_id=r["device_id"],
            title="سلسلتك في انتظارك 🤍",
            body="درس جديد من «المربّي» ياخد دقيقتين — ادخل الحين واستمر في رحلة تربية أولادك.",
            data={"type": "streak_at_risk", "link": _deep_link_for(r["age_group"])},
        )
        sent.add(r["device_id"])
    return sent


def new_content_digest(window_days: int = DIGEST_WINDOW_DAYS):
    """Morning nudge, bounded by an activity window.

    This used to go to **every** device that ever registered a token, every
    single morning, forever, with no cap and no engagement test — which is
    most of the 29,194 notifications GA4 recorded as delivered against 810
    opens, 19,586 of them dismissed. A daily message to someone who stopped
    opening the app weeks ago is not re-engagement; it is why the next one
    gets swiped away too, and eventually why notifications get turned off for
    the app entirely. An audience that only ever grows is the bug, separately
    from wherever the threshold lands.

    On the threshold itself, honestly: the app is eleven days old, so every
    window is distorted by that and the data cannot yet pick one. Measured on
    production, 2,323 devices hold a token and only 514 (22%) did anything in
    the last seven days — but 64% have never opened a single lesson, and those
    are exactly the parents the morning tip is meant to win over, not the ones
    to drop first. So the default is deliberately loose, the window is a flag,
    and the run logs what it filtered. Tighten it in a month against numbers
    instead of a guess.

    Note `child_profiles.updated_at` alone is not an activity signal — it hits
    90% at fourteen days because it is really measuring onboarding. Real
    engagement (`lesson_progress`) is 35%. The union of both is used so a
    brand-new parent who has not reached a lesson yet still hears from us.

    Dormant devices are not abandoned: `win_back` still reaches them in the
    evening, deliberately, once.
    """
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    rows = _query(
        """
        SELECT DISTINCT device_id FROM (
            SELECT cp.device_id AS device_id FROM child_profiles cp
             WHERE cp.updated_at IS NOT NULL AND cp.updated_at >= ?
            UNION
            SELECT lp.device_id AS device_id FROM lesson_progress lp
             WHERE lp.updated_at IS NOT NULL AND lp.updated_at >= ?
        )
        WHERE device_id IN (
            SELECT device_id FROM push_tokens
             WHERE token IS NOT NULL AND token != ''
        )
        """,
        (cutoff, cutoff),
    )
    total = _query(
        "SELECT COUNT(DISTINCT device_id) AS n FROM push_tokens "
        "WHERE token IS NOT NULL AND token != ''"
    )[0]["n"]
    print(f"  new_content_digest: {len(rows)} من {total} جهاز "
          f"(نافذة {window_days} يوم، مستبعَد {total - len(rows)})")

    for r in rows:
        _send(
            device_id=r["device_id"],
            title="نصيحة اليوم 🌙",
            body="افتح المربّي واقرأ نصيحة اليوم — صدقة جارية لو شاركتها مع أحد الوالدين.",
            data={"type": "daily_tip", "link": HOME_LINK},
        )


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

    # Morning tip at 7 UTC (≈10:00 القاهرة والرياض — صباح، ليس ظهرًا)
    if 7 <= hour < 8:
        print("  -> new_content_digest")
        new_content_digest()

    # Evening re-engagement at 17 UTC (≈20:00 القاهرة والرياض — بعد المغرب،
    # وليس 23:00/منتصف الليل كما كانت 20 UTC). Max 2 pushes/device/day total.
    if 17 <= hour < 18:
        print("  -> streak_at_risk + win_back (deduped)")
        nudged = streak_at_risk()
        win_back(skip=nudged)

    print("done")
