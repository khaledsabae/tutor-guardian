"""The follow-up push — «جرّبت النصيحة؟ نفعت؟» — at the family's own evening.

It used to ride the 17 UTC cron, and one fixed UTC hour is night somewhere:
17 UTC is 21:00 in Dubai, 22:00 in Karachi and 01:00 in Kuala Lumpur, so a
family from UTC+4 to UTC+8 could never be asked (PR #26 review F7). It now
runs from the backend's in-process loop (main.py, beside the mission digest,
for the same reason: the moment depends on each device's local hour, which a
crontab cannot read) and sends when it is FOLLOWUP_LOCAL_HOUR where the family
is — inside 09:00–21:00 local, never at night, in every time zone. No cron
line of its own.

Rules:
  * only devices whose build has the follow-up screen (CHILD_MEMORY_MIN_BUILD;
    unset = nobody);
  * a device's oldest due follow-up; at most one follow-up push per device per
    FOLLOWUP_PUSH_EVERY_DAYS; never the same follow-up twice — it is claimed in
    the database before it is sent, so two workers cannot both send it, and
    released again if the send fails;
  * nothing more than FOLLOWUP_EXPIRE_DAYS past due (it has expired);
  * only with a UTC offset the app reported (child_memory_settings) — an
    unknown offset is never guessed, and nothing is sent;
  * never to a device that had any push in the last ONE_PUSH_A_DAY, whoever
    sent it — one push a day stays one push a day;
  * never to a device whose parent switched memory off;
  * a GENERIC text, private on the lock screen: the strategy can be about
    something the family keeps to itself (A8/P5). The app shows it on open.

Deep link: /followup/{id} — MOBILE_API.md §9.4.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.log_safety import device_tag
from app.db.init_db import get_conn
from app.services import push_sender

logger = logging.getLogger(__name__)

FOLLOWUP_LOCAL_HOUR = 19                 # 19:00–19:59 where the family is
LOCAL_DAY_START, LOCAL_DAY_END = 9, 21   # the window that hour must sit inside
assert LOCAL_DAY_START <= FOLLOWUP_LOCAL_HOUR < LOCAL_DAY_END
FOLLOWUP_PUSH_EVERY_DAYS = 7
FOLLOWUP_EXPIRE_DAYS = 21
ONE_PUSH_A_DAY = timedelta(hours=20)
KIND = "followup_due"

TEXT = {
    "ar": ("متابعة من المربّي 🤍",
           "هل جرّبت النصيحة التي اقترحناها؟ أخبرنا بالنتيجة لنكيّف نصائحنا لطفلك."),
    "en": ("A follow-up from Almorabbi 🤍",
           "Did you try the advice we suggested? Tell us how it went, so we can adapt it to your child."),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_hour(now: datetime, tz_offset_minutes: Optional[int]) -> Optional[int]:
    """The hour on the family's clock, or None when their offset is unknown."""
    if tz_offset_minutes is None:
        return None
    return (now + timedelta(minutes=int(tz_offset_minutes))).hour


def _due_rows(now: datetime, min_build: int) -> list[sqlite3.Row]:
    weekly_cutoff = (now - timedelta(days=FOLLOWUP_PUSH_EVERY_DAYS)).isoformat()
    expired_before = (now - timedelta(days=FOLLOWUP_EXPIRE_DAYS)).isoformat()
    conn = get_conn()
    try:
        return conn.execute(
            """
            SELECT f.id, f.device_id, f.child_id, f.lang, s.tz_offset_minutes
            FROM followups f
            JOIN push_tokens pt ON pt.device_id = f.device_id
            JOIN child_memory_settings s ON s.device_id = f.device_id
            WHERE f.status = 'pending'
              AND f.due_at <= datetime(?)
              AND f.due_at >= datetime(?)
              AND f.pushed_at IS NULL
              AND pt.token IS NOT NULL AND pt.token != ''
              AND pt.build_number IS NOT NULL AND pt.build_number >= ?
              AND s.enabled = 1
              AND s.tz_offset_minutes IS NOT NULL
              AND f.device_id NOT IN (
                  SELECT device_id FROM push_sends
                  WHERE kind = ? AND sent_at >= datetime(?))
            ORDER BY f.due_at ASC, f.id ASC
            """,
            (now.isoformat(), expired_before, min_build, KIND, weekly_cutoff),
        ).fetchall()
    finally:
        conn.close()


def _claim(followup_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("UPDATE followups SET pushed_at = datetime('now') "
                           "WHERE id = ? AND pushed_at IS NULL", (followup_id,))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def _release(followup_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE followups SET pushed_at = NULL WHERE id = ?", (followup_id,))
        conn.commit()
    finally:
        conn.close()


def run_due_followups(now: Optional[datetime] = None, *, dry_run: bool = False) -> dict:
    """One sweep: push every follow-up whose family's clock reads
    FOLLOWUP_LOCAL_HOUR now. Returns counts; never names a device."""
    from app.services.child_memory import memory_min_build

    min_build = memory_min_build()
    if min_build is None:
        return {"sent": 0, "off": True}
    now = now or _utcnow()
    try:
        rows = _due_rows(now, min_build)
    except sqlite3.OperationalError as exc:      # a database before v30
        logger.warning("follow-up push: skipped (%s)", exc)
        return {"sent": 0, "skipped": True}
    pushed_today = push_sender.recently_pushed_since((now - ONE_PUSH_A_DAY).isoformat())
    out = {"sent": 0, "would_send": 0, "failed": 0, "not_this_hour": 0, "capped": 0}
    seen: set[str] = set()
    for r in rows:
        device = r["device_id"]
        if device in seen:
            continue
        seen.add(device)
        if local_hour(now, r["tz_offset_minutes"]) != FOLLOWUP_LOCAL_HOUR:
            out["not_this_hour"] += 1
            continue
        if device in pushed_today:
            out["capped"] += 1
            continue
        if dry_run:
            out["would_send"] += 1
            continue
        if not _claim(r["id"]):
            continue                                 # another worker has it
        title, body = TEXT.get(r["lang"] or "ar", TEXT["ar"])
        result = push_sender.send_to_device(
            device, title, body,
            {"type": KIND, "link": f"/followup/{r['id']}",
             "followup_id": str(r["id"]), "child_id": str(r["child_id"])},
            visibility="private",
        )
        if result.get("sent"):
            out["sent"] += 1
        else:
            _release(r["id"])                        # try again on a later tick
            out["failed"] += 1
            logger.info("follow-up push: not sent to %s (%s)", device_tag(device),
                        result.get("reason") or result.get("error"))
    return out
