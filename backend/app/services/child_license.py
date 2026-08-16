"""The internet licence — level 1.

What this is not: a permission system. The app has no authority over the
child's browser, YouTube or WhatsApp, so nothing here unlocks anything. A
level records that a family practised a set of situations and then talked
about them. Every string that reaches a screen says "we agreed", never "you
unlocked" — see plans/sprint3-internet-licence-spec.md §1.1 for why that
distinction is load-bearing rather than pedantic.

Three rules shape the code below:

**The answer log is immutable.** `outcome` is copied onto the row at answer
time rather than read back from the bank. Re-classifying a choice next year
must not rewrite what a child did last March.

**A wrong answer is not a failure.** It is repeated after seven days with a
higher `attempt`, and the child is never told they were wrong — the response
to an answer carries no correct/incorrect signal at all. Say it back and the
exercise becomes a puzzle to brute-force until the green light appears, which
is the opposite of measuring judgement.

**Answering does not grant a level.** `practising → awaiting_talk → granted`,
and the middle step is the parent recording that the two of them actually
talked. Without it this is a certificate the app issues to itself.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.db.init_db import get_conn

_UTC = timezone.utc

BANK_DIR = Path(__file__).resolve().parents[3] / "knowledge_base" / "curriculum" / "license"

# The five levels, in order. Level 0 in the original plan ("a device with no
# internet") is the starting state, not something a family passes.
LEVELS = ("stranger", "signal", "contact", "footprint", "public")

# A scenario answered unsafely comes back, but not tomorrow. Long enough that
# the child is recalling rather than remembering the screen, short enough to
# still be the same conversation.
REPEAT_AFTER_DAYS = 7

# Statuses.
PRACTISING = "practising"
AWAITING_TALK = "awaiting_talk"
GRANTED = "granted"


def _now() -> datetime:
    return datetime.now(_UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(_UTC).isoformat(timespec="seconds")


# ── The bank ───────────────────────────────────────────────────────────────

def load_scenarios(level_key: str) -> list[dict[str, Any]]:
    """Every published scenario for a level, or [] when the bank is absent.

    An absent bank is the ordinary case: levels 2-5 have no content yet, and
    the UI renders that as "not yet", not as an error.
    """
    path = BANK_DIR / f"scenarios_{level_key}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not data.get("is_published", True):
        return []
    return [s for s in data.get("scenarios", []) if isinstance(s, dict)]


def _scenario(level_key: str, scenario_key: str) -> Optional[dict[str, Any]]:
    for s in load_scenarios(level_key):
        if s.get("key") == scenario_key:
            return s
    return None


def _outcome_of(scenario: dict[str, Any], choice_key: str) -> Optional[str]:
    for c in scenario.get("choices", []):
        if c.get("key") == choice_key:
            return c.get("outcome")
    return None


# ── Progress ───────────────────────────────────────────────────────────────

def _latest_answers(conn, child_id: int, level_key: str) -> dict[str, dict]:
    """The most recent answer per scenario for this child and level."""
    rows = conn.execute(
        "SELECT scenario_key, choice_key, outcome, attempt, answered_at "
        "FROM child_scenario_answers "
        "WHERE child_id = ? AND level_key = ? "
        "ORDER BY answered_at ASC",
        (child_id, level_key),
    ).fetchall()
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r["scenario_key"]] = dict(r)
    return latest


def next_scenario(child_id: int, level_key: str,
                  now: Optional[datetime] = None) -> Optional[dict[str, Any]]:
    """The scenario to show, or None when the level's practice is complete.

    Order is deterministic rather than random, by the same reasoning as the
    mission picker: a child who closes and reopens sees the same thing, and a
    parent looking over their shoulder sees what their child sees.

    A scenario already answered safely is done. One answered unsafely is due
    again once seven days have passed, and is skipped until then — so a child
    who got two wrong today is not made to sit through both again tonight.
    """
    moment = now or _now()
    bank = load_scenarios(level_key)
    if not bank:
        return None

    conn = get_conn()
    try:
        latest = _latest_answers(conn, child_id, level_key)
    finally:
        conn.close()

    # Deterministic rotation, seeded per child and level.
    seed = sum(ord(c) for c in f"{child_id}:{level_key}")
    ordered = bank[seed % len(bank):] + bank[:seed % len(bank)]

    for scenario in ordered:
        prev = latest.get(scenario["key"])
        if prev is None:
            return scenario
        if prev["outcome"] == "safe":
            continue
        try:
            answered = datetime.fromisoformat(prev["answered_at"])
        except (TypeError, ValueError):
            return scenario
        if answered.tzinfo is None:
            answered = answered.replace(tzinfo=_UTC)
        if moment - answered >= timedelta(days=REPEAT_AFTER_DAYS):
            return scenario
    return None


def progress(child_id: int, level_key: str) -> dict[str, Any]:
    bank = load_scenarios(level_key)
    conn = get_conn()
    try:
        latest = _latest_answers(conn, child_id, level_key)
    finally:
        conn.close()
    done = sum(1 for s in bank if latest.get(s["key"], {}).get("outcome") == "safe")
    return {"done": done, "total": len(bank)}


# ── Answering ──────────────────────────────────────────────────────────────

def answer(device_id: str, child_id: int, level_key: str, scenario_key: str,
           choice_key: str) -> dict[str, Any]:
    """Record an answer.

    The returned dict carries no correct/incorrect signal — deliberately, and
    a test reads the response body to keep it that way. `alerts_parent` is not
    a verdict on the child either: it is true for the whole scenario whenever
    the situation is one a parent should hear about, including when the child
    answered it perfectly. A child who chose well in a grooming scenario may
    be living through one.
    """
    scenario = _scenario(level_key, scenario_key)
    if scenario is None:
        return {"ok": False, "reason": "scenario_not_found"}
    outcome = _outcome_of(scenario, choice_key)
    if outcome is None:
        return {"ok": False, "reason": "choice_not_found"}

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(attempt) AS a FROM child_scenario_answers "
            "WHERE child_id = ? AND scenario_key = ?",
            (child_id, scenario_key),
        ).fetchone()
        attempt = int((row["a"] or 0)) + 1
        conn.execute(
            "INSERT INTO child_scenario_answers (device_id, child_id, "
            "scenario_key, level_key, choice_key, outcome, attempt, answered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (device_id, child_id, scenario_key, level_key, choice_key,
             outcome, attempt, _iso(_now())),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "alerts_parent": bool(scenario.get("alerts_parent")),
        "talking_point_ar": scenario.get("talking_point_ar", ""),
        "outcome": outcome,          # for the alert path only; never sent to the child
        "attempt": attempt,
    }


def mark_alerted(child_id: int, scenario_key: str, attempt: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE child_scenario_answers SET parent_alerted_at = ? "
            "WHERE child_id = ? AND scenario_key = ? AND attempt = ?",
            (_iso(_now()), child_id, scenario_key, attempt),
        )
        conn.commit()
    finally:
        conn.close()


# ── The licence itself ─────────────────────────────────────────────────────

def _row(conn, child_id: int, level_key: str):
    return conn.execute(
        "SELECT * FROM child_licences WHERE child_id = ? AND level_key = ?",
        (child_id, level_key),
    ).fetchone()


def ensure_level(device_id: str, child_id: int, level_key: str) -> dict[str, Any]:
    """Fetch the level's row, creating it as `practising` on first sight."""
    conn = get_conn()
    try:
        row = _row(conn, child_id, level_key)
        if row is None:
            conn.execute(
                "INSERT INTO child_licences (device_id, child_id, level_key, status) "
                "VALUES (?, ?, ?, ?)",
                (device_id, child_id, level_key, PRACTISING),
            )
            conn.commit()
            row = _row(conn, child_id, level_key)
        return dict(row)
    finally:
        conn.close()


def current_level(child_id: int) -> str:
    """The level a child is working on: the first not yet granted."""
    conn = get_conn()
    try:
        granted = {
            r["level_key"] for r in conn.execute(
                "SELECT level_key FROM child_licences "
                "WHERE child_id = ? AND status = ?", (child_id, GRANTED)
            ).fetchall()
        }
    finally:
        conn.close()
    for level in LEVELS:
        if level not in granted:
            return level
    return LEVELS[-1]


def refresh_status(device_id: str, child_id: int, level_key: str) -> dict[str, Any]:
    """Move `practising → awaiting_talk` once every scenario is answered safely.

    Never moves to `granted`: that transition belongs to the parent alone.
    """
    ensure_level(device_id, child_id, level_key)
    prog = progress(child_id, level_key)
    conn = get_conn()
    try:
        row = _row(conn, child_id, level_key)
        if (row["status"] == PRACTISING and prog["total"] > 0
                and prog["done"] == prog["total"]):
            conn.execute(
                "UPDATE child_licences SET status = ? WHERE id = ?",
                (AWAITING_TALK, row["id"]),
            )
            conn.commit()
            row = _row(conn, child_id, level_key)
        return dict(row)
    finally:
        conn.close()


def record_talk(device_id: str, child_id: int, level_key: str) -> dict[str, Any]:
    """The parent says they talked about it. Not verified, and not verifiable.

    The alternative would be interrogating the parent, and a parent who lies
    here is lying to themselves. The value is that the step exists in the path
    and cannot be skipped silently, not that it is proven.
    """
    ensure_level(device_id, child_id, level_key)
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE child_licences SET talked_at = ? "
            "WHERE child_id = ? AND level_key = ? AND talked_at IS NULL",
            (_iso(_now()), child_id, level_key),
        )
        conn.commit()
        return dict(_row(conn, child_id, level_key))
    finally:
        conn.close()


def grant(device_id: str, child_id: int, level_key: str) -> dict[str, Any]:
    """Grant a level. Refused unless the practice is done AND they talked."""
    ensure_level(device_id, child_id, level_key)
    prog = progress(child_id, level_key)
    conn = get_conn()
    try:
        row = _row(conn, child_id, level_key)
        if prog["total"] == 0 or prog["done"] < prog["total"]:
            return {"ok": False, "reason": "practice_incomplete"}
        if not row["talked_at"]:
            return {"ok": False, "reason": "talk_required"}
        if row["status"] == GRANTED:
            return {"ok": True, "already": True, "licence": dict(row)}
        review = _now() + timedelta(days=30)
        conn.execute(
            "UPDATE child_licences SET status = ?, granted_at = ?, "
            "next_review_date = ? WHERE id = ?",
            (GRANTED, _iso(_now()), review.strftime("%Y-%m-%d"), row["id"]),
        )
        conn.commit()
        return {"ok": True, "licence": dict(_row(conn, child_id, level_key))}
    finally:
        conn.close()


def summary(device_id: str, child_id: int) -> dict[str, Any]:
    """What the parent's screen renders."""
    level_key = current_level(child_id)
    row = refresh_status(device_id, child_id, level_key)
    prog = progress(child_id, level_key)

    conn = get_conn()
    try:
        # Talking points for what the child has actually met, newest first —
        # this is the half of the feature that teaches rather than measures.
        answered = conn.execute(
            "SELECT scenario_key, outcome, answered_at FROM child_scenario_answers "
            "WHERE child_id = ? AND level_key = ? ORDER BY answered_at DESC LIMIT 10",
            (child_id, level_key),
        ).fetchall()
        levels = {
            r["level_key"]: r["status"] for r in conn.execute(
                "SELECT level_key, status FROM child_licences WHERE child_id = ?",
                (child_id,)
            ).fetchall()
        }
    finally:
        conn.close()

    bank = {s["key"]: s for s in load_scenarios(level_key)}
    return {
        "level_key": level_key,
        "status": row["status"],
        "talked_at": row["talked_at"],
        "granted_at": row["granted_at"],
        "next_review_date": row["next_review_date"],
        "progress": prog,
        "levels": [{"level_key": k, "status": levels.get(k, "locked")} for k in LEVELS],
        "talking_points": [
            {
                "scenario_key": a["scenario_key"],
                "situation_ar": bank.get(a["scenario_key"], {}).get("situation_ar", ""),
                "talking_point_ar": bank.get(a["scenario_key"], {}).get("talking_point_ar", ""),
                "answered_at": a["answered_at"],
            }
            for a in answered if a["scenario_key"] in bank
        ],
    }
