"""The child surface's time budget, enforced on the server.

A limit that lives in the app is a limit that lasts until someone reads the
APK. Everything here runs behind the API so that exceeding it from the client
is not a matter of the client choosing not to.

Three decisions in here are not obvious and are the reason the file is longer
than a stopwatch would be:

**Time is billed from heartbeats, not from wall clock.** A child who closes
the app should not be charged for the hour it sat in the background, and an
app left open in a pocket should not bill an afternoon. But billing *only*
confirmed heartbeats leaves a hole: open a session, send nothing, get reaped
90 seconds later having paid nothing, open another. So a session closed by
timeout is charged for its grace window, and every heartbeat is charged for
the gap behind it up to twice the interval. Silence is not free.

**The local date is derived here, not accepted from the client.** The obvious
design takes `local_date` in the request and validates the clock against
server time. That check compares *instants* and a timezone change moves the
*date* without moving the instant — so flying the device clock from Cairo to
Sydney passes a 15-minute skew check and hands back a fresh daily allowance.
The client now sends only a UTC offset and the server does the arithmetic.

**And the calendar day has a rolling-24h floor under it.** Deriving the date
server-side narrows the hole but does not close it: the offset itself is still
client-supplied, and there are real offsets 26 hours apart. So every budget
question is answered by whichever ledger is *more* consumed — today's calendar
day, or the last 24 hours. A travelling family loses nothing they would have
legitimately used; a device rotating through timezones gains nothing.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.config.guardrails_loader import ChildSurfacePolicy, ResolvedBand, SurfaceSpec
from app.core.taxonomy import map_profile_age_to_band
from app.services import family_agreement
from app.db.init_db import get_conn

_UTC = timezone.utc

# Real UTC offsets run from -12:00 to +14:00. Anything outside is a client
# bug or an attempt, and either way it does not get to pick a date.
_MAX_TZ_OFFSET_MINUTES = 14 * 60
_MIN_TZ_OFFSET_MINUTES = -12 * 60

# A heartbeat is charged for the gap behind it, capped at twice the interval.
# The cap absorbs a slow network without letting a client stretch the gap and
# under-report; anything longer than the grace closes the session instead.
_HEARTBEAT_CHARGE_INTERVALS = 2

_ROLLING_WINDOW = timedelta(hours=24)


def agreement_required() -> bool:
    """Whether a signed agreement gates the child surface. **Default off.**

    The gate itself is correct and tested. What it cannot survive is arriving
    before its own exit: the signing screens live in the Flutter app, the app
    on Play is an older build without them, and a server-side gate applies to
    every client at once. Turning this on before that release reaches devices
    locks out every family with no way back in — which is exactly what shipping
    it on 2026-08-16 would have done, and did not only because the deploy was
    cancelled with four minutes to spare.

    Flip it to true once the Play build carrying the agreement screens is the
    minimum version. Not before.
    """
    return os.environ.get("AGREEMENT_REQUIRED", "").strip().lower() in {"1", "true", "yes"}


def child_surface_enabled() -> bool:
    """The kill switch. Set CHILD_SURFACE_ENABLED=false and restart.

    Turning it off does not disable child mode — it returns the app to exactly
    what it did before this sprint: a flat thirty-minute child token, no
    session, no age gate, no budget. That is a weaker product and a deliberate
    one; the alternative on a bad night is rolling back a deploy that also
    carries everything else on main.

    Read at call time so a restart is enough. Anything other than an explicit
    false leaves the surface on — a typo in the env file must not silently
    unlock the gate.
    """
    return os.environ.get("CHILD_SURFACE_ENABLED", "true").strip().lower() \
        not in {"0", "false", "no", "off"}


# ── Time helpers ───────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(_UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(_UTC).isoformat(timespec="seconds")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=_UTC)


def local_date_for(moment: datetime, tz_offset_minutes: int) -> str:
    """The child's calendar date, computed here rather than trusted."""
    return (moment + timedelta(minutes=tz_offset_minutes)).strftime("%Y-%m-%d")


# ── Reads ──────────────────────────────────────────────────────────────────

def _usage_rows(conn: sqlite3.Connection, child_id: int, local_date: str,
                since: datetime) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    today = conn.execute(
        "SELECT surface, counted_seconds FROM child_screen_sessions "
        "WHERE child_id = ? AND local_date = ?",
        (child_id, local_date),
    ).fetchall()
    rolling = conn.execute(
        "SELECT surface, counted_seconds FROM child_screen_sessions "
        "WHERE child_id = ? AND started_at >= ?",
        (child_id, _iso(since)),
    ).fetchall()
    return today, rolling


def _split(rows, policy: ChildSurfacePolicy) -> tuple[int, int]:
    """(screen seconds, audio seconds) for a set of session rows."""
    screen = audio = 0
    for row in rows:
        spec = policy.surfaces.get(row["surface"])
        if spec is None:
            # A surface that has since been removed from the policy. It was
            # real time on a real screen, so it keeps billing the screen
            # ledger — dropping it would refund a child for a config change.
            screen += row["counted_seconds"]
        elif spec.counts_toward_budget:
            screen += row["counted_seconds"]
        elif spec.counts_toward_audio_budget:
            audio += row["counted_seconds"]
    return screen, audio


def _consumed(conn: sqlite3.Connection, child_id: int, local_date: str,
              now: datetime, policy: ChildSurfacePolicy) -> tuple[int, int]:
    """Seconds already spent, taking the more consumed of the two ledgers."""
    today, rolling = _usage_rows(conn, child_id, local_date, now - _ROLLING_WINDOW)
    screen_today, audio_today = _split(today, policy)
    screen_rolling, audio_rolling = _split(rolling, policy)
    return max(screen_today, screen_rolling), max(audio_today, audio_rolling)


def _remaining(band: ResolvedBand, screen_used: int, audio_used: int) -> tuple[int, int]:
    screen = max(0, band.daily_budget_minutes * 60 - screen_used)
    audio = max(0, band.screen_off_daily_budget_minutes * 60 - audio_used)
    return screen, audio


def _allowance(spec: SurfaceSpec, band: ResolvedBand,
               screen_left: int, audio_left: int) -> int:
    """How many seconds this session may run for."""
    cap = spec.max_minutes * 60
    if spec.counts_toward_budget:
        return min(cap, band.session_max_minutes * 60, screen_left)
    if spec.counts_toward_audio_budget:
        return min(cap, audio_left)
    # Bills no daily ledger — the covenant screen is the case. Its own cap is
    # the whole limit; a child does not pay to read an agreement about them.
    return cap


def _load_child(conn: sqlite3.Connection, device_id: str,
                child_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT id, age_group FROM child_profiles WHERE id = ? AND device_id = ?",
        (child_id, device_id),
    ).fetchone()


# ── Writes ─────────────────────────────────────────────────────────────────

def _charge_and_close(conn: sqlite3.Connection, row: sqlite3.Row, reason: str,
                      now: datetime, charge: int) -> None:
    conn.execute(
        "UPDATE child_screen_sessions SET ended_at = ?, ended_reason = ?, "
        "counted_seconds = counted_seconds + ? WHERE id = ?",
        (_iso(now), reason, max(0, charge), row["id"]),
    )


def _open_session_row(conn: sqlite3.Connection, child_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM child_screen_sessions WHERE child_id = ? AND ended_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (child_id,),
    ).fetchone()


def reap_stale_sessions(policy: ChildSurfacePolicy,
                        conn: Optional[sqlite3.Connection] = None) -> int:
    """Close sessions whose heartbeat stopped, charging the grace window.

    Charging matters: a session that goes quiet and is reaped for free is a
    90-second screen refill, repeatable. The child had the surface open for at
    least that long — they are billed for it.

    Called at the top of every open_session rather than on a timer. At this
    volume a periodic job would be a second thing to operate for no gain.
    """
    owned = conn is None
    conn = conn or get_conn()
    try:
        now = _now()
        grace = policy.defaults.heartbeat_grace_seconds
        cutoff = now - timedelta(seconds=grace)
        stale = conn.execute(
            "SELECT * FROM child_screen_sessions WHERE ended_at IS NULL "
            "AND last_heartbeat_at < ?",
            (_iso(cutoff),),
        ).fetchall()
        for row in stale:
            elapsed = (now - _parse(row["last_heartbeat_at"])).total_seconds()
            _charge_and_close(conn, row, "timeout", now, int(min(elapsed, grace)))
        if owned:
            conn.commit()
        return len(stale)
    finally:
        if owned:
            conn.close()


def open_session(device_id: str, child_id: int, surface: str,
                 tz_offset_minutes: int, policy: ChildSurfacePolicy) -> dict[str, Any]:
    """Start a child session, or explain why not.

    The age gate lives here rather than in the router so that every caller
    passes it — a second entry point added later cannot forget to check.
    """
    if not (_MIN_TZ_OFFSET_MINUTES <= tz_offset_minutes <= _MAX_TZ_OFFSET_MINUTES):
        return {"ok": False, "reason": "invalid_tz_offset"}

    conn = get_conn()
    try:
        child = _load_child(conn, device_id, child_id)
        if child is None:
            return {"ok": False, "reason": "child_not_found"}

        band_name = map_profile_age_to_band(child["age_group"])
        band = policy.band(band_name)

        if not band.screen_allowed and surface not in band.allowed_surfaces:
            return {
                "ok": False,
                "reason": "age_not_allowed",
                "band": band_name,
                "parent_message_key": band.parent_message_key,
                "parent_message_ar": band.parent_message_ar,
            }
        if surface not in band.allowed_surfaces:
            return {"ok": False, "reason": "surface_not_allowed", "band": band_name}

        # The agreement is the frame everything else sits inside, so it is an
        # entry condition rather than a screen among screens: a child with no
        # signed agreement can open the agreement and nothing else.
        #
        # `agreement` is exempt for the obvious reason, and it bills no daily
        # ledger — a child does not spend screen time to read an agreement
        # written about them.
        #
        # ORDERING: this must not ship ahead of the signing UI. A gate whose
        # only exit is a screen that does not exist yet locks out every family
        # already using child mode.
        # ...for bands that can actually agree to something. A two-year-old
        # cannot read a clause, let alone sign one, and their only surface is
        # audio with the screen dark. So the gate keys on whether a clause
        # bank exists for the band: no bank, nothing to agree to, no gate —
        # and writing clauses_10-12.json later turns it on for that band with
        # no code change.
        gated = agreement_required() and bool(
            family_agreement.load_clause_bank(band_name)
        )
        if gated and surface != "agreement" and not family_agreement.has_active_agreement(
            device_id, child_id
        ):
            return {
                "ok": False,
                "reason": "agreement_required",
                "band": band_name,
                "next_surface": "agreement",
            }

        reap_stale_sessions(policy, conn)

        # One open session per child. An older one still standing means the
        # app died without closing it; it is charged for its grace and closed
        # as superseded rather than left to inflate the next reap.
        existing = _open_session_row(conn, child_id)
        if existing is not None:
            now = _now()
            elapsed = (now - _parse(existing["last_heartbeat_at"])).total_seconds()
            grace = policy.defaults.heartbeat_grace_seconds
            _charge_and_close(conn, existing, "superseded", now, int(min(elapsed, grace)))

        now = _now()
        local_date = local_date_for(now, tz_offset_minutes)
        screen_used, audio_used = _consumed(conn, child_id, local_date, now, policy)
        screen_left, audio_left = _remaining(band, screen_used, audio_used)
        spec = policy.surface(surface)
        allowed = _allowance(spec, band, screen_left, audio_left)

        if allowed <= 0:
            reason = "audio_budget_exhausted" if spec.counts_toward_audio_budget \
                else "budget_exhausted"
            return {
                "ok": False,
                "reason": reason,
                "band": band_name,
                "resets_at": f"{local_date} 00:00 (+1d)",
            }

        cur = conn.execute(
            "INSERT INTO child_screen_sessions (device_id, child_id, surface, "
            "local_date, tz_offset_minutes, started_at, last_heartbeat_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, child_id, surface, local_date, tz_offset_minutes,
             _iso(now), _iso(now)),
        )
        conn.commit()
        return {
            "ok": True,
            "session_id": cur.lastrowid,
            "band": band_name,
            "surface": surface,
            "allowed_seconds": allowed,
            "remaining_today": screen_left,
            "remaining_audio_today": audio_left,
            "requires_parent_present": band.requires_parent_present,
            "heartbeat_interval_seconds": band.heartbeat_interval_seconds,
            "exit_ritual_seconds": spec.exit_ritual_seconds,
        }
    finally:
        conn.close()


def heartbeat(session_id: int, policy: ChildSurfacePolicy) -> dict[str, Any]:
    """Bill the gap behind this heartbeat and report what is left."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM child_screen_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None or row["ended_at"] is not None:
            return {"ok": False, "reason": "session_closed"}

        now = _now()
        child = conn.execute(
            "SELECT age_group FROM child_profiles WHERE id = ?", (row["child_id"],)
        ).fetchone()
        spec = policy.surfaces.get(row["surface"])
        if child is None or spec is None:
            # The profile was deleted, or the surface was withdrawn from the
            # policy, mid-session. Either way there is nothing left to
            # authorise this session against, so it ends.
            _charge_and_close(conn, row, "timeout", now, 0)
            conn.commit()
            return {"ok": False, "reason": "session_closed"}
        band = policy.band(map_profile_age_to_band(child["age_group"]))

        interval = band.heartbeat_interval_seconds
        grace = band.heartbeat_grace_seconds
        gap = (now - _parse(row["last_heartbeat_at"])).total_seconds()

        if gap > grace:
            _charge_and_close(conn, row, "timeout", now, int(min(gap, grace)))
            conn.commit()
            return {"ok": False, "reason": "session_closed"}

        charge = int(min(gap, interval * _HEARTBEAT_CHARGE_INTERVALS))
        conn.execute(
            "UPDATE child_screen_sessions SET last_heartbeat_at = ?, "
            "counted_seconds = counted_seconds + ? WHERE id = ?",
            (_iso(now), charge, session_id),
        )

        spent_this_session = row["counted_seconds"] + charge
        screen_used, audio_used = _consumed(conn, row["child_id"], row["local_date"],
                                            now, policy)
        # Already net of this session — _consumed reads the row we just wrote.
        screen_left, audio_left = _remaining(band, screen_used, audio_used)

        session_cap = spec.max_minutes * 60
        if spec.counts_toward_budget:
            session_cap = min(session_cap, band.session_max_minutes * 60)
            daily_left = screen_left
        elif spec.counts_toward_audio_budget:
            daily_left = audio_left
        else:
            daily_left = session_cap  # bills no ledger; its own cap is the limit
        session_left = max(0, min(session_cap - spent_this_session, daily_left))

        if session_left <= 0:
            _charge_and_close(conn, row, "budget_exhausted", now, 0)
            conn.commit()
            return {"ok": False, "reason": "budget_exhausted"}

        conn.commit()
        return {
            "ok": True,
            "remaining_seconds": session_left,
            "exit_ritual": session_left <= spec.exit_ritual_seconds,
        }
    finally:
        conn.close()


def close_session(session_id: int, reason: str,
                  policy: ChildSurfacePolicy) -> None:
    """End a session, billing the tail since its last heartbeat.

    The tail is capped at one interval: the child is charged for the time we
    have reason to believe they were there, and not for the gap they spent
    disconnected.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM child_screen_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None or row["ended_at"] is not None:
            return
        now = _now()
        interval = policy.defaults.heartbeat_interval_seconds
        tail = (now - _parse(row["last_heartbeat_at"])).total_seconds()
        _charge_and_close(conn, row, reason, now, int(min(tail, interval)))
        conn.commit()
    finally:
        conn.close()


def session_for(session_id: int) -> Optional[sqlite3.Row]:
    """One session by id. Routers check `child_id` against the caller's token
    before acting on it — a session id is not an authorisation."""
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM child_screen_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    finally:
        conn.close()


def active_session(child_id: int) -> Optional[sqlite3.Row]:
    """The child's open session, if any. The middleware's gate."""
    conn = get_conn()
    try:
        return _open_session_row(conn, child_id)
    finally:
        conn.close()


def today_usage(child_id: int, local_date: str,
                policy: ChildSurfacePolicy) -> dict[str, Any]:
    """What the parent sees. Screen and audio reported separately, because
    conflating them is exactly the confusion the policy exists to undo."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT surface, counted_seconds, started_at, ended_at, ended_reason "
            "FROM child_screen_sessions WHERE child_id = ? AND local_date = ? "
            "ORDER BY id",
            (child_id, local_date),
        ).fetchall()
        screen, audio = _split(rows, policy)
        by_surface: dict[str, int] = {}
        for row in rows:
            by_surface[row["surface"]] = by_surface.get(row["surface"], 0) + row["counted_seconds"]
        return {
            "counted_seconds": screen,
            "screen_off_seconds": audio,
            "by_surface": by_surface,
            "sessions": [
                {
                    "surface": row["surface"],
                    "counted_seconds": row["counted_seconds"],
                    "started_at": row["started_at"],
                    "ended_at": row["ended_at"],
                    "ended_reason": row["ended_reason"],
                }
                for row in rows
            ],
        }
    finally:
        conn.close()
