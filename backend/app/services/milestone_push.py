"""The milestone reminder — one push, about a month ahead, at the family's 20:00.

Runs from the backend's in-process loop (main.py, beside the mission digest)
for the digest's reason: the moment is a device's local hour, which a crontab
cannot read. No cron line of its own.

Rules, each of them a test in tests/test_programs_milestones.py:
  * only children with a birth month (alert_policy: "Without a date of birth no
    notification is sent"), and only inside the alert window — from the alert
    date until the milestone's own date. A window missed is not caught up
    later: "turning seven next month" sent in the birthday month is wrong;
  * only devices whose build has the milestone screen (MILESTONES_MIN_BUILD;
    unset = nobody), with a push token, and a UTC offset the app reported —
    an unknown offset is never guessed;
  * at MILESTONE_LOCAL_HOUR on the family's clock, inside 09:00–21:00 local;
  * never to a device that had any push in the last 20 hours, whoever sent it;
  * a waiting mission does NOT hold it back: the 21:00 digest ignores this
    kind in its own once-a-day cap (mission_digest._DOES_NOT_CAP), so both go
    that evening. Holding the milestone back instead starved every family on
    the Prayer Journey — a prayer waits on the parent nearly every evening
    (PR #32 review: 28 of 28 evenings skipped);
  * at most one milestone push per device per DEVICE_EVERY_DAYS, at most one
    per child per CHILD_EVERY_DAYS (alert_policy.max_alerts_per_child_per_month),
    the most important first (the lowest `order`) — the other waits;
  * never the same milestone twice: the alert row is claimed in the database
    BEFORE the send, inside a write transaction that also re-checks the
    device's weekly cap, so two workers or a restart mid-send cannot both send
    it; it is released again if the send fails.

The text is the content's own `alert` (title ≤ 50, body ≤ 160), in the
family's language, with `visibility='private'` so it stays off a locked
screen — the parent's phone is often the one the child holds.

Deep link: /milestones/{child_id}/{milestone_key} — MOBILE_API.md §11.4.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.core.log_safety import device_tag
from app.db.init_db import get_conn
from app.services import milestones as ms
from app.services import programs_common as pc
from app.services import push_sender
from app.services import ramadan_program as rp

logger = logging.getLogger(__name__)

KIND = "milestone"
MILESTONE_LOCAL_HOUR = 20                # 20:00–20:59 where the family is
LOCAL_DAY_START, LOCAL_DAY_END = 9, 21   # the window that hour must sit inside
assert LOCAL_DAY_START <= MILESTONE_LOCAL_HOUR < LOCAL_DAY_END
DEVICE_EVERY_DAYS = 7
CHILD_EVERY_DAYS = 30
ONE_PUSH_A_DAY = timedelta(hours=20)

_UTC = timezone.utc


def min_build() -> Optional[int]:
    """MILESTONES_MIN_BUILD — the first build with the milestone screen. Unset
    (or not a number) means no milestone push at all: a tap on an older build
    lands on a link it cannot route, which is a push wasted."""
    raw = os.environ.get("MILESTONES_MIN_BUILD", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _utcnow() -> datetime:
    return datetime.now(_UTC)


def _sql_ts(moment: datetime) -> str:
    """The `datetime('now')` shape, so stored and compared stamps sort alike."""
    return moment.astimezone(_UTC).strftime("%Y-%m-%d %H:%M:%S")


def device_offset(conn: sqlite3.Connection, device_id: str) -> Optional[int]:
    """The offset the app last reported on a program call, else the one it
    sent when it last opened child mode. Never a guess."""
    row = conn.execute(
        "SELECT tz_offset_minutes FROM program_settings WHERE device_id = ?", (device_id,)
    ).fetchone()
    if row is not None and row["tz_offset_minutes"] is not None:
        return int(row["tz_offset_minutes"])
    row = conn.execute(
        "SELECT tz_offset_minutes FROM child_screen_sessions WHERE device_id = ? "
        "ORDER BY started_at DESC LIMIT 1", (device_id,),
    ).fetchone()
    return int(row["tz_offset_minutes"]) if row is not None else None


def _candidates(min_build_number: int) -> dict[str, list[sqlite3.Row]]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT c.* FROM child_profiles c
            JOIN push_tokens pt ON pt.device_id = c.device_id
            WHERE c.birth_month IS NOT NULL AND c.birth_month != ''
              AND pt.token IS NOT NULL AND pt.token != ''
              AND pt.build_number IS NOT NULL AND pt.build_number >= ?
            ORDER BY c.device_id, c.id
            """,
            (min_build_number,),
        ).fetchall()
    finally:
        conn.close()
    by_device: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        by_device[r["device_id"]].append(r)
    return by_device


def _offset(device_id: str) -> Optional[int]:
    conn = get_conn()
    try:
        return device_offset(conn, device_id)
    finally:
        conn.close()


def _device_state(device_id: str, now: datetime) -> dict[str, Any]:
    """Everything else the sweep asks about a device — read only for the
    devices whose hour it is."""
    conn = get_conn()
    try:
        weekly = conn.execute(
            "SELECT 1 FROM milestone_alerts WHERE device_id = ? AND claimed_at >= ? LIMIT 1",
            (device_id, _sql_ts(now - timedelta(days=DEVICE_EVERY_DAYS))),
        ).fetchone() is not None or conn.execute(
            "SELECT 1 FROM push_sends WHERE device_id = ? AND kind = ? AND sent_at >= ? LIMIT 1",
            (device_id, KIND, _sql_ts(now - timedelta(days=DEVICE_EVERY_DAYS))),
        ).fetchone() is not None
        settings = conn.execute(
            "SELECT * FROM program_settings WHERE device_id = ?", (device_id,)
        ).fetchone()
    finally:
        conn.close()
    return {"weekly_capped": weekly,
            "settings": dict(settings) if settings is not None else {}}


def _child_history(child_id: int) -> tuple[set[str], Optional[str]]:
    """(alert keys already claimed or sent, the latest claim time)."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT alert_key, claimed_at FROM milestone_alerts WHERE child_id = ?",
            (child_id,),
        ).fetchall()
    finally:
        conn.close()
    latest = max((r["claimed_at"] for r in rows), default=None)
    return {r["alert_key"] for r in rows}, latest


def alert_key(milestone: dict, when: dict[str, Any]) -> str:
    """Once per child per milestone — and once per season for a seasonal one."""
    season = when.get("season")
    if season:
        return f"{milestone['key']}:{season['hijri_year']}"
    return milestone["key"]


def pick(doc: dict, device_id: str, children: list[sqlite3.Row], local_today: date,
         seasons: list[rp.Season], now: datetime) -> Optional[tuple[sqlite3.Row, dict, dict]]:
    """The one reminder this device may get now: the lowest `order` among its
    children's milestones whose push window is open today, not yet sent, for a
    child not reminded in the last CHILD_EVERY_DAYS."""
    best = None
    child_cutoff = _sql_ts(now - timedelta(days=CHILD_EVERY_DAYS))
    for child in children:
        done, latest = _child_history(child["id"])
        if latest is not None and latest >= child_cutoff:
            continue
        puberty = pc.reached_puberty(device_id, child["id"])
        found, _ = ms.evaluate(doc, child, local_today, seasons, puberty)
        for milestone, when in found:
            if when["basis"] != "birth_month" or when["state"] != "due":
                continue
            if not when["alert_on"] or not when["push_until"]:
                continue
            if not (date.fromisoformat(when["alert_on"]) <= local_today
                    < date.fromisoformat(when["push_until"])):
                continue
            if alert_key(milestone, when) in done:
                continue
            rank = (int(milestone.get("order") or 0), child["id"])
            if best is None or rank < best[0]:
                best = (rank, child, milestone, when)
    return None if best is None else best[1:]


def _claim(device_id: str, child_id: int, key: str, milestone_key: str,
           now: datetime) -> Optional[int]:
    """Write the alert row before sending. One write transaction re-checks the
    device's weekly cap and inserts, so a second worker that got here at the
    same moment sees the first one's row and stops."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        recent = conn.execute(
            "SELECT 1 FROM milestone_alerts WHERE device_id = ? AND claimed_at >= ? LIMIT 1",
            (device_id, _sql_ts(now - timedelta(days=DEVICE_EVERY_DAYS))),
        ).fetchone()
        if recent is not None:
            conn.rollback()
            return None
        try:
            cur = conn.execute(
                "INSERT INTO milestone_alerts (device_id, child_id, alert_key, milestone_key, "
                "status, claimed_at) VALUES (?, ?, ?, ?, 'claimed', ?)",
                (device_id, child_id, key, milestone_key, _sql_ts(now)),
            )
        except sqlite3.IntegrityError:
            conn.rollback()
            return None
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _settle(alert_id: int, sent: bool, now: datetime) -> None:
    conn = get_conn()
    try:
        if sent:
            conn.execute("UPDATE milestone_alerts SET status = 'sent', sent_at = ? WHERE id = ?",
                         (_sql_ts(now), alert_id))
        else:
            conn.execute("DELETE FROM milestone_alerts WHERE id = ? AND status = 'claimed'",
                         (alert_id,))
        conn.commit()
    finally:
        conn.close()


def run_due_milestones(now: Optional[datetime] = None, *, dry_run: bool = False) -> dict:
    """One sweep. Returns counts; never names a device or a child."""
    floor = min_build()
    if floor is None:
        return {"sent": 0, "off": True}
    now = now or _utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_UTC)
    out = {"sent": 0, "would_send": 0, "failed": 0, "not_this_hour": 0, "capped": 0,
           "no_offset": 0, "nothing_due": 0}
    try:
        by_device = _candidates(floor)
    except sqlite3.OperationalError as exc:      # a database before v34
        logger.warning("milestone push: skipped (%s)", exc)
        return {"sent": 0, "skipped": True}
    if not by_device:
        return out
    pushed_today = push_sender.recently_pushed_since((now - ONE_PUSH_A_DAY).isoformat())
    docs: dict[str, dict] = {}

    for device_id, children in by_device.items():
        offset = _offset(device_id)
        if offset is None:
            out["no_offset"] += 1
            continue
        local = now + timedelta(minutes=offset)
        if local.hour != MILESTONE_LOCAL_HOUR:
            out["not_this_hour"] += 1
            continue
        state = _device_state(device_id, now)
        if device_id in pushed_today or state["weekly_capped"]:
            out["capped"] += 1
            continue
        lang = state["settings"].get("lang") or "ar"
        try:
            doc = docs.get(lang) or docs.setdefault(lang, pc.load_program(ms.PROGRAM, lang))
        except pc.ProgramUnavailable:
            logger.warning("milestone push: the milestones program is unavailable")
            return {**out, "unavailable": True}
        # Without the Ramadan file only the seasonal card (first fast) goes.
        seasons = rp.seasons_or_empty(state["settings"])
        chosen = pick(doc, device_id, children, local.date(), seasons, now)
        if chosen is None:
            out["nothing_due"] += 1
            continue
        child, milestone, when = chosen
        if dry_run:
            out["would_send"] += 1
            continue
        alert_id = _claim(device_id, child["id"], alert_key(milestone, when),
                          milestone["key"], now)
        if alert_id is None:
            continue                                 # another worker has it
        alert = milestone.get("alert") or {}
        result = push_sender.send_to_device(
            device_id, alert.get("title") or milestone.get("title") or "", alert.get("body") or "",
            {"type": KIND, "kind": KIND,
             "link": f"/milestones/{child['id']}/{milestone['key']}",
             "child_id": str(child["id"]), "milestone_key": milestone["key"]},
            visibility="private",
        )
        if result.get("sent"):
            _settle(alert_id, True, now)
            out["sent"] += 1
        else:
            _settle(alert_id, False, now)            # try again on a later tick
            out["failed"] += 1
            logger.info("milestone push: not sent to %s (%s)", device_tag(device_id),
                        result.get("reason") or result.get("error"))
    return out
