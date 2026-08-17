"""One thing to go and do, away from the screen.

The mission card is the smallest complete expression of what this product
claims: sixty seconds of screen buys fifteen minutes of something else. So the
bank enforces the ratio rather than hoping for it — a mission whose estimate
is under five times the card's own three minutes is refused at load, because a
"leverage" number computed from content nobody constrained is decoration.

Two rules shape the selection:

**No repeats inside three weeks.** A child who gets «صيّاد الأخضر» every
Tuesday learns that the app has four ideas. The window is per child and looks
at what was actually assigned, not what was completed.

**One card a day, and the same card all day.** Re-opening the app must not
reroll the mission — a child who does not like today's task should not be able
to shop for a different one, and a parent confirming in the evening needs the
card to be the one the child was actually given.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.db.init_db import get_conn
from app.services import content_lang

_UTC = timezone.utc

MISSIONS_DIR = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "curriculum" / "missions"
)

# The mission surface's own cap, from child_surface.v1.yaml. Kept here as the
# ratio's denominator rather than read from the policy, because the policy can
# be tightened and this floor should not follow it down.
_CARD_MINUTES = 3

# The leverage the product claims. A mission that does not clear it is not a
# mission, it is a screen with an instruction on it.
MIN_LEVERAGE = 5

NO_REPEAT_DAYS = 21

# After this the card stops waiting for an answer. Quietly: an expired mission
# is not a failure anyone needs to be told about, least of all the child.
EXPIRE_AFTER_HOURS = 48


def _now() -> datetime:
    return datetime.now(_UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(_UTC).isoformat(timespec="seconds")


# ── The bank ───────────────────────────────────────────────────────────────

def load_missions(age_band: str, lang: Optional[str] = None) -> list[dict[str, Any]]:
    """Published missions for a band that clear the leverage floor."""
    path = content_lang.localised(
        MISSIONS_DIR, f"missions_{age_band}.json", lang)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not data.get("is_published", True):
        return []
    return [
        m for m in data.get("missions", [])
        if m.get("is_published", True)
        and m.get("estimated_minutes", 0) >= _CARD_MINUTES * MIN_LEVERAGE
    ]


def _recently_assigned(conn: sqlite3.Connection, child_id: int,
                       since: str) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT mission_key FROM child_missions "
        "WHERE child_id = ? AND local_date >= ?",
        (child_id, since),
    ).fetchall()
    return {r["mission_key"] for r in rows}


def _pick(candidates: list[dict[str, Any]], child_id: int,
          local_date: str) -> dict[str, Any]:
    """Deterministic choice, so re-opening the app cannot reroll the card.

    Not random: the same child on the same day must get the same mission
    whether they open the app once or nine times.
    """
    seed = sum(ord(c) for c in f"{child_id}:{local_date}")
    return candidates[seed % len(candidates)]


# ── Assignment and claiming ────────────────────────────────────────────────

def today_mission(device_id: str, child_id: int, age_band: str,
                  local_date: str, lang: Optional[str] = None) -> Optional[dict[str, Any]]:
    """The child's card for today, assigning one on first ask."""
    missions = load_missions(age_band, lang)
    if not missions:
        return None

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT * FROM child_missions WHERE child_id = ? AND local_date = ? "
            "ORDER BY id DESC LIMIT 1",
            (child_id, local_date),
        ).fetchone()
        if existing is not None:
            return _row_to_card(existing, missions)

        cutoff = (date.fromisoformat(local_date)
                  - timedelta(days=NO_REPEAT_DAYS)).isoformat()
        seen = _recently_assigned(conn, child_id, cutoff)
        fresh = [m for m in missions if m["id"] not in seen]
        # Everything used inside the window: fall back to the whole bank
        # rather than handing the child nothing. A repeat beats a blank.
        chosen = _pick(fresh or missions, child_id, local_date)

        conn.execute(
            "INSERT OR IGNORE INTO child_missions (device_id, child_id, "
            "mission_key, local_date, status, assigned_at) "
            "VALUES (?, ?, ?, ?, 'assigned', ?)",
            (device_id, child_id, chosen["id"], local_date, _iso(_now())),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM child_missions WHERE child_id = ? AND local_date = ? "
            "ORDER BY id DESC LIMIT 1", (child_id, local_date),
        ).fetchone()
        return _row_to_card(row, missions)
    finally:
        conn.close()


def _row_to_card(row: sqlite3.Row, missions: list[dict[str, Any]]) -> dict[str, Any]:
    detail = next((m for m in missions if m["id"] == row["mission_key"]), None)
    return {
        "mission_id": row["id"],
        "mission_key": row["mission_key"],
        "status": row["status"],
        "local_date": row["local_date"],
        "claimed_at": row["claimed_at"],
        "confirmed_at": row["confirmed_at"],
        "title_ar": (detail or {}).get("title_ar", ""),
        "instruction_ar": (detail or {}).get("instruction_ar", ""),
        "estimated_minutes": (detail or {}).get("estimated_minutes", 0),
        "needs_parent": (detail or {}).get("needs_parent", False),
        "needs_outdoors": (detail or {}).get("needs_outdoors", False),
        "materials": (detail or {}).get("materials", []),
        "skill": (detail or {}).get("skill", ""),
    }


def claim(child_id: int, mission_id: int) -> dict[str, Any]:
    """The child says they did it — and does not wait for anyone.

    Asynchronous on purpose. A child standing in front of a screen waiting for
    a parent to press a button has been handed a reason to stay at the screen.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM child_missions WHERE id = ? AND child_id = ?",
            (mission_id, child_id),
        ).fetchone()
        if row is None:
            return {"ok": False, "reason": "mission_not_found"}
        if row["status"] in ("confirmed", "not_done"):
            return {"ok": False, "reason": "already_settled"}
        conn.execute(
            "UPDATE child_missions SET status = 'claimed', claimed_at = ? "
            "WHERE id = ?", (_iso(_now()), mission_id),
        )
        conn.commit()
        return {"ok": True, "status": "claimed"}
    finally:
        conn.close()


# ── The parent's evening ───────────────────────────────────────────────────

def pending_for_device(device_id: str, lang: Optional[str] = None) -> list[dict[str, Any]]:
    """Everything waiting on the parent, across all their children."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT m.*, c.name AS child_name, c.age_group "
            "FROM child_missions m JOIN child_profiles c ON c.id = m.child_id "
            "WHERE m.device_id = ? AND m.status = 'claimed' "
            "ORDER BY m.claimed_at",
            (device_id,),
        ).fetchall()
        out = []
        for row in rows:
            from app.core.taxonomy import map_profile_age_to_band
            missions = load_missions(
                map_profile_age_to_band(row["age_group"]), lang)
            card = _row_to_card(row, missions)
            card["child_id"] = row["child_id"]
            card["child_name"] = row["child_name"]
            out.append(card)
        return out
    finally:
        conn.close()


def confirm_batch(device_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Settle several missions in one go — the whole point of the evening card.

    A parent with three children should press one button, not six.
    """
    settled = 0
    conn = get_conn()
    try:
        for item in items:
            mission_id = item.get("mission_id")
            if not isinstance(mission_id, int):
                continue
            confirmed = bool(item.get("confirmed", True))
            note = (item.get("note") or "")[:280] or None
            cur = conn.execute(
                "UPDATE child_missions SET status = ?, confirmed_at = ?, "
                "parent_note = ? WHERE id = ? AND device_id = ? "
                "AND status = 'claimed'",
                ("confirmed" if confirmed else "not_done", _iso(_now()),
                 note, mission_id, device_id),
            )
            settled += cur.rowcount
        conn.commit()
        return {"ok": True, "settled": settled}
    finally:
        conn.close()


def expire_stale(now: Optional[datetime] = None) -> int:
    """Let unanswered cards go quietly.

    Not 'failed' and not surfaced: a child whose parent was travelling did not
    do anything wrong, and neither did the parent.
    """
    cutoff = _iso((now or _now()) - timedelta(hours=EXPIRE_AFTER_HOURS))
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE child_missions SET status = 'expired' "
            "WHERE status IN ('assigned', 'claimed') AND assigned_at < ?",
            (cutoff,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ── What the parent is shown at the end of a month ─────────────────────────

def leverage(child_id: int, since_date: str, screen_seconds: int) -> dict[str, Any]:
    """Confirmed off-screen minutes against screen minutes.

    Reported, never optimised. The numerator is a number we write in a JSON
    file, so a target of ×10 is met by editing `estimated_minutes` — which is
    why this returns a sentence's worth of numbers and no goal.
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT mission_key, local_date FROM child_missions "
            "WHERE child_id = ? AND local_date >= ? AND status = 'confirmed'",
            (child_id, since_date),
        ).fetchall()
    finally:
        conn.close()

    # One lookup across every published band: a child's mission may have been
    # assigned under a band they have since grown out of, and the minutes they
    # actually spent do not stop counting because of a birthday.
    # No `lang`: this sums estimated_minutes, which is identical in every
    # translation. Passing a language here would imply the leverage figure
    # changes per locale.
    lookup: dict[str, int] = {}
    for band in ("4-6", "7-9", "10-12", "13-15", "16-18"):
        for m in load_missions(band):
            lookup.setdefault(m["id"], m.get("estimated_minutes", 0))
    minutes = sum(lookup.get(row["mission_key"], 0) for row in rows)

    screen_minutes = round(screen_seconds / 60)
    return {
        "confirmed_missions": len(rows),
        "off_screen_minutes": minutes,
        "screen_minutes": screen_minutes,
        "ratio": round(minutes / screen_minutes, 1) if screen_minutes else None,
    }
