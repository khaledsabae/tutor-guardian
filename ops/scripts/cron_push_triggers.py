#!/usr/bin/env python3
"""
ops/scripts/cron_push_triggers.py

Re-engagement push triggers — Phase 1.1.
Runs as a cron job on the VPS (e.g. every day at 9am and 8pm local time):
    0 9,20 * * * cd /path/to/tutor-guardian && backend/.venv/bin/python ops/scripts/cron_push_triggers.py

Needs env:
    FIREBASE_CREDENTIALS  (raw JSON) or backend/secrets/firebase-adminsdk.json
    TG_ADMIN_KEY          (unused here, but kept for symmetry)

Safe to run repeatedly: all sends are best-effort and idempotent-ish.
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root on path for app imports.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db.init_db import db_path
from app.services.push_sender import send_to_device


DB_PATH = db_path()


def _query(sql: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def _device_ids_with_tokens():
    rows = _query("SELECT device_id, token FROM push_tokens WHERE token IS NOT NULL AND token != ''")
    return [r["device_id"] for r in rows]


def streak_at_risk():
    """Send to parents whose last lesson/login was >36h ago."""
    cutoff = (datetime.utcnow() - timedelta(hours=36)).isoformat()
    rows = _query(
        """
        SELECT DISTINCT cp.device_id
        FROM child_profiles cp
        LEFT JOIN lesson_progress lp
            ON lp.device_id = cp.device_id
        WHERE cp.device_id IN (
            SELECT device_id FROM push_tokens WHERE token IS NOT NULL AND token != ''
        )
        GROUP BY cp.device_id
        HAVING MAX(COALESCE(lp.last_activity_at, cp.created_at)) < ?
        """,
        (cutoff,),
    )
    for r in rows:
        send_to_device(
            device_id=r["device_id"],
            title="سلسلتك في انتظارك 🤍",
            body="درس جديد من «المربّي» ياخد دقيقتين — ادخل الحين واستمر في رحلة تربية أولادك.",
            data={"type": "streak_at_risk", "route": "/paths"},
        )


def new_content_digest():
    """Broadcast a gentle content nudge to all parents with tokens.
    In the future this can filter by child age."""
    for device_id in _device_ids_with_tokens():
        send_to_device(
            device_id=device_id,
            title="نصيحة اليوم 🌙",
            body="افتح المربّي واقرأ نصيحة اليوم — صدقة جارية لو شاركتها مع أحد الوالدين.",
            data={"type": "daily_tip", "route": "/"},
        )


def win_back():
    """Reach parents who have not opened the app for 5+ days."""
    cutoff = (datetime.utcnow() - timedelta(days=5)).isoformat()
    rows = _query(
        """
        SELECT DISTINCT device_id FROM child_profiles
        WHERE device_id IN (
            SELECT device_id FROM push_tokens WHERE token IS NOT NULL AND token != ''
        )
        AND (updated_at IS NULL OR updated_at < ?)
        """,
        (cutoff,),
    )
    for r in rows:
        send_to_device(
            device_id=r["device_id"],
            title="مشتاقين ليك 🤍",
            body="رحلة تربية أولادك مستمرة — ادخل المربّي دلوقتي واكمل من حيث وقفت.",
            data={"type": "win_back", "route": "/paths"},
        )


if __name__ == "__main__":
    hour = datetime.utcnow().hour
    print(f"[{datetime.utcnow().isoformat()}] cron_push_triggers starting (UTC hour={hour})")

    # Morning digest at 9am UTC
    if 9 <= hour < 10:
        print("  -> new_content_digest")
        new_content_digest()

    # Evening re-engagement at 8pm UTC
    if 20 <= hour < 21:
        print("  -> streak_at_risk + win_back")
        streak_at_risk()
        win_back()

    print("done")
