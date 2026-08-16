"""The evening nudge — one push, to the parent, once.

Rule 4 of the constitution is absolute: **zero notifications aimed at the
child.** The only channel here is `send_to_device`, which addresses the
parent's device token, and the body deliberately carries no content a child
would find interesting. In many of these families the parent's phone *is* the
phone the child uses, so "sent to the parent" is a claim about the token, not
about who reads the screen — the text has to survive being seen by the child
and still be for the parent.

One push per device per day, and only when something is actually waiting. A
digest that fires on an empty list teaches people to swipe it away, and the
next one they swipe away is the one that mattered.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.db.init_db import get_conn
from app.services import child_missions, push_sender

_UTC = timezone.utc

# The kind recorded in push_sends, so the frequency cap can see it.
DIGEST_KIND = "mission_digest"

# Only one of these a day. push_sender.recently_pushed_since gives us the
# devices already contacted, and this is the window we ask about.
_ONE_DAY = timedelta(hours=20)

# 9pm where the child lives — late enough that the day's missions are done,
# early enough that the parent is awake to answer.
DIGEST_LOCAL_HOUR = 21

# How often the scheduler wakes. Shorter than the one-hour match window on
# purpose: a device must not be able to fall between two ticks.
DIGEST_TICK_SECONDS = 15 * 60


def _now() -> datetime:
    return datetime.now(_UTC)


def _body_for(pending: list[dict[str, Any]]) -> tuple[str, str]:
    """The text. Written so a child reading over a shoulder learns nothing
    they could act on, and a parent learns exactly what is being asked."""
    names = []
    for card in pending:
        name = card.get("child_name") or ""
        if name and name not in names:
            names.append(name)

    if len(pending) == 1:
        title = "مهمة مستنية تأكيدك"
        who = names[0] if names else "ابنك"
        return title, f"{who} بيقول إنه خلّص مهمة النهارده. تحب تأكّدها؟"

    title = "مهام مستنية تأكيدك"
    if len(names) == 1:
        return title, f"{names[0]} بيقول إنه خلّص {len(pending)} مهام. تأكّدهم في ضغطة."
    return title, f"{len(pending)} مهام مستنية منك — من {'، '.join(names[:3])}."


def send_digest(device_id: str, *, force: bool = False) -> dict[str, Any]:
    """Send one device its evening digest, or explain why not."""
    pending = child_missions.pending_for_device(device_id)
    if not pending:
        # Nothing waiting. Silence is the correct notification.
        return {"ok": True, "sent": False, "reason": "nothing_pending"}

    if not force:
        already = push_sender.recently_pushed_since(_iso(_now() - _ONE_DAY))
        if device_id in already:
            return {"ok": True, "sent": False, "reason": "already_pushed_today"}

    title, body = _body_for(pending)
    # `link` is what the client routes on, and `type` is what it reports to
    # analytics. Without both, the tap opens the app at the home screen and the
    # parent has to go looking for the list — which is most of the way back to
    # not having been told.
    result = push_sender.send_to_device(
        device_id, title, body,
        data={
            "kind": DIGEST_KIND,
            "type": DIGEST_KIND,
            "link": "/missions",
            "pending": str(len(pending)),
        },
    )
    return {"ok": result.get("ok", False), "sent": result.get("sent", False),
            "pending": len(pending), "detail": result}


def _iso(moment: datetime) -> str:
    return moment.astimezone(_UTC).isoformat()


def devices_with_pending() -> list[str]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT device_id FROM child_missions WHERE status = 'claimed'"
        ).fetchall()
        return [r["device_id"] for r in rows]
    finally:
        conn.close()


def devices_with_pending_and_offset() -> list[tuple[str, int]]:
    """Every device waiting on a confirmation, with the UTC offset it last
    reported.

    The offset is not stored anywhere of its own — `child_screen_sessions`
    already records the one the client sent when it opened each session, and a
    device that has a claimed mission necessarily opened a session to get it.
    The most recent one wins, so a family that travels is followed rather than
    pinned to wherever they first opened the app.

    A device with a mission but somehow no session falls back to UTC. That is
    the wrong hour for most of the world, but it is a hour, and the alternative
    is never notifying them at all.
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT m.device_id AS device_id,
                   (SELECT s.tz_offset_minutes
                      FROM child_screen_sessions s
                     WHERE s.device_id = m.device_id
                     ORDER BY s.started_at DESC
                     LIMIT 1) AS tz_offset_minutes
              FROM child_missions m
             WHERE m.status = 'claimed'
             GROUP BY m.device_id
            """
        ).fetchall()
        return [(r["device_id"], int(r["tz_offset_minutes"] or 0)) for r in rows]
    finally:
        conn.close()


def run_evening_digest(now: Optional[datetime] = None) -> dict[str, Any]:
    """The whole sweep: expire what went stale, then notify who is waited on.

    Expiry runs first on purpose — a card the parent never answered for two
    days should not generate a third night's push.
    """
    expired = child_missions.expire_stale(now)
    sent = 0
    skipped = 0
    for device_id in devices_with_pending():
        result = send_digest(device_id)
        if result.get("sent"):
            sent += 1
        else:
            skipped += 1
    return {"expired": expired, "sent": sent, "skipped": skipped}


def run_due_digests(now: Optional[datetime] = None) -> dict[str, Any]:
    """The scheduled sweep: notify only the devices for which it is evening.

    `run_evening_digest` above pushes to everyone waiting, whatever the hour
    where they are — correct for a manual run, wrong for a timer. The spec says
    9pm *on the device*, and 27% of this user base is not in the server's
    timezone, so a single UTC cron would wake part of them at 1am.

    Called every few minutes, so the window has to be wider than the tick or a
    device is skipped on the night its tick lands badly; the 20-hour cap in
    `send_digest` is what makes repeated matches harmless, and it is the reason
    the window can be a whole hour rather than a precise instant.
    """
    moment = now or _now()
    expired = child_missions.expire_stale(moment)
    sent = 0
    skipped = 0
    waiting = 0
    for device_id, offset in devices_with_pending_and_offset():
        local_hour = (moment + timedelta(minutes=offset)).hour
        if local_hour != DIGEST_LOCAL_HOUR:
            waiting += 1
            continue
        result = send_digest(device_id)
        if result.get("sent"):
            sent += 1
        else:
            skipped += 1
    return {"expired": expired, "sent": sent, "skipped": skipped, "waiting": waiting}
