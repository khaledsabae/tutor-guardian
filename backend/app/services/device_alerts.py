"""The notice owed to the phone that just lost the account's push token.

PR #26 review, round 3. When a device's push token is replaced by a session
that had not proven the old one — a new phone, a reinstall, or someone who
learned the device id (services/device_proof.py) — the previous token gets one
generic notification: the account was opened on a new device; if it wasn't
you, open the app. Opening the app re-registers that phone's own token, which
voids the newcomer's proof (and the owner's clean proof vouches for it at once).

Rules:
  * generic, in Arabic and English: no name, nothing from the account;
  * at most one per device per day — a later one waits for the day to end
    (it is delayed, never dropped);
  * between 09:00 and 21:00 on the family's clock (the offset the app last
    sent; when it never sent one, UTC+3 — where most of the families are);
  * on the safety channel, so a parent who muted reminders still gets it;
  * sent from the backend's in-process loop (main.py), no cron line;
  * the previous token is kept only until the notice goes out — or GIVE_UP if
    it cannot — then forgotten. Claimed before sending, so two workers cannot
    both send it.
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

KIND = "account_alert"
LOCAL_DAY_START, LOCAL_DAY_END = 9, 21
DEFAULT_OFFSET_MINUTES = 180          # UTC+3 when the family's offset is unknown
GIVE_UP = timedelta(days=3)
ONE_A_DAY = timedelta(hours=24)

TITLE = "تنبيه أمان · Security notice"
BODY = ("فُتح حسابك في المربّي على جهاز جديد. إن لم تكن أنت فافتح التطبيق الآن. · "
        "Your Almorabbi account was opened on a new device. If it wasn't you, open the app now.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def queue(conn: sqlite3.Connection, device_id: str, old_token: str) -> bool:
    """Owe the previous token a notice — unless one is already waiting. One
    sent in the last day does not cancel it: it waits until the day is over
    (run_due_alerts; PR #26 final review — a second takeover is told, later).
    Runs inside the caller's transaction."""
    row = conn.execute(
        "SELECT old_token FROM device_alerts WHERE device_id = ?", (device_id,),
    ).fetchone()
    if row is not None and row["old_token"]:
        return False
    conn.execute(
        "INSERT INTO device_alerts (device_id, old_token, queued_at) "
        "VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(device_id) DO UPDATE SET old_token = excluded.old_token, "
        "queued_at = excluded.queued_at",
        (device_id, old_token),
    )
    return True


def _local_hour(now: datetime, offset: Optional[int]) -> int:
    off = DEFAULT_OFFSET_MINUTES if offset is None else int(offset)
    return (now + timedelta(minutes=off)).hour


def run_due_alerts(now: Optional[datetime] = None) -> dict:
    """One sweep. Returns counts; never names a device or a token."""
    now = now or _utcnow()
    now_s = now.isoformat(sep=" ", timespec="seconds")      # the sweep's clock, as SQLite writes it
    out = {"sent": 0, "dead": 0, "failed": 0, "night": 0, "expired": 0, "waiting": 0}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT a.device_id, a.old_token, a.sent_at, "
            "       a.queued_at < datetime('now', ?) AS stale, "
            "       a.sent_at IS NOT NULL AND a.sent_at > datetime(?) AS recent, "
            "       s.tz_offset_minutes "
            "FROM device_alerts a "
            "LEFT JOIN child_memory_settings s ON s.device_id = a.device_id "
            "WHERE a.old_token IS NOT NULL",
            (f"-{int(GIVE_UP.total_seconds())} seconds",
             (now - ONE_A_DAY).isoformat(sep=" ", timespec="seconds")),
        ).fetchall()
    except sqlite3.OperationalError as exc:          # a database before v30
        logger.warning("account alert: skipped (%s)", exc)
        return out
    finally:
        conn.close()
    for r in rows:
        device, token = r["device_id"], r["old_token"]
        if r["stale"]:
            _settle(device, token, sent=False)       # forget the token, no notice
            out["expired"] += 1
            continue
        if r["recent"]:
            out["waiting"] += 1                      # one a day: this one goes tomorrow
            continue
        if not (LOCAL_DAY_START <= _local_hour(now, r["tz_offset_minutes"]) < LOCAL_DAY_END):
            out["night"] += 1
            continue
        if not _claim(device, token, now_s):
            continue                                 # another worker has it
        result = push_sender.send_notification_to_token(
            token, TITLE, BODY, {"type": KIND},
            channel_id=_safety_channel(),
        )
        if result.get("sent"):
            out["sent"] += 1
        elif result.get("reason") == "unregistered":
            out["dead"] += 1                         # the old phone is gone: nothing to warn
        else:
            _release(device, token)
            out["failed"] += 1
            logger.info("account alert: not sent for %s (%s)", device_tag(device),
                        result.get("error"))
    return out


def _safety_channel() -> str:
    from app.services.license_alert import SAFETY_CHANNEL
    return SAFETY_CHANNEL


def _claim(device_id: str, token: str, now_s: str) -> bool:
    """Take the notice and forget the token in one step."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE device_alerts SET old_token = NULL, sent_at = ? "
            "WHERE device_id = ? AND old_token = ?", (now_s, device_id, token))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def _release(device_id: str, token: str) -> None:
    """The send failed: owe it again (a later tick retries, GIVE_UP bounds it)."""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE device_alerts SET old_token = ?, sent_at = NULL "
            "WHERE device_id = ? AND old_token IS NULL", (token, device_id))
        conn.commit()
    finally:
        conn.close()


def _settle(device_id: str, token: str, *, sent: bool) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE device_alerts SET old_token = NULL"
            + (", sent_at = datetime('now')" if sent else "")
            + " WHERE device_id = ? AND old_token = ?", (device_id, token))
        conn.commit()
    finally:
        conn.close()
