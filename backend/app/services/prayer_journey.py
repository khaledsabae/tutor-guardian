"""«رحلة الصلاة» — enrolment, stages, the child's tasks, graduation.

Content: `knowledge_base/curriculum/programs/prayer_journey.json` (schema.md
§8.3). Three tracks, chosen by age when the birth month is known
(`entry_rules`: 4–6 preparation, 7–10 the journey, 11–15 ownership) and by
band otherwise (`band_map`); under four and over fifteen the program does not
appear.

**The loop is the existing one.** A child's prayer task is a row in
`child_missions` (`source = 'prayer_journey'`, `mission_key = '<task id>#<n>'`
for the n-th time today), so it rides the same asynchronous loop as the
off-screen mission: the child records it in child mode and does not wait;
the parent sees it in `/children/missions/pending`, confirms it in the same
evening batch, and the 21:00 digest tells them it is waiting. Confirming
returns the task's coins for the app to credit (coins are on-device).

**Never punitive** (`principles`, `reward_policy`):
* Advancing is suggested when the stage's weeks are up — never forced, and
  never conditional on the weekly counts: `per_week` is a goal, "a week below
  it is not a failure".
* Going back a stage is always allowed and silent — the content asks for it
  ("go back to two for another week, without telling him he has gone
  backwards"), so nothing records a step back and the child's view shows only
  today's tasks, never a stage number moving down.
* Coins are never withheld or taken back; they shrink stage by stage because
  the content says so. A day's slots are capped at ceil(per_week / 7) per
  task — the cap check_programs uses to keep a stage under the app's 60-coin
  day — and a "N times a week" task (per_week < 7) is complete for the week
  once done N times.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.db.init_db import get_conn
from app.services import programs_common as pc

PROGRAM = "prayer_journey"
SOURCE = "prayer_journey"
TRACKS = ("preparation", "journey", "ownership")
_UTC = timezone.utc


class JourneyError(Exception):
    def __init__(self, code: str, status: int = 409, **extra: Any):
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


def _now_iso() -> str:
    return datetime.now(_UTC).isoformat(timespec="seconds")


# ── Who sees what ──────────────────────────────────────────────────────────

def eligible_track(doc: dict, age: dict) -> Optional[str]:
    """The track a child starts on: by age if known, else by band."""
    if age.get("basis") == "birth_month" and age.get("years") is not None:
        for rule in doc.get("entry_rules", []):
            if rule["min_age_years"] <= age["years"] <= rule["max_age_years"]:
                return rule["track"]
        return None
    return (doc.get("bands") or {}).get("band_map", {}).get(age.get("band"))


def allowed_tracks(eligible: Optional[str]) -> list[str]:
    """A child on the ownership track who does not pray regularly yet may
    start the Journey instead, from the stage that suits him (bands.text).
    Nobody starts the Journey before seven."""
    if eligible == "ownership":
        return ["ownership", "journey"]
    return [eligible] if eligible else []


# ── Content ────────────────────────────────────────────────────────────────

def _stages(doc: dict) -> list[dict]:
    return list(doc.get("stages") or [])


def stage_planned_days(stage: dict) -> int:
    return (int(stage["week_to"]) - int(stage["week_from"]) + 1) * 7


def per_day(task: dict) -> int:
    """Slots a day: ceil(per_week / 7) — check_programs' coin arithmetic."""
    return max(1, -(-int(task.get("per_week") or 1) // 7))


def week_limit(task: dict) -> Optional[int]:
    """A "N times a week" task is done for the week after N; a daily task has
    no weekly ceiling beyond its daily slots."""
    n = int(task.get("per_week") or 0)
    return n if 0 < n < 7 else None


def _all_tasks(doc: dict) -> dict[str, dict]:
    out = {}
    for stage in _stages(doc):
        for task in stage.get("child_tasks") or ():
            out[task["id"]] = task
    for task in (doc.get("ownership") or {}).get("child_tasks") or ():
        out[task["id"]] = task
    return out


def task_for_key(mission_key: str, lang: Optional[str] = None) -> Optional[dict]:
    """The content task behind a child_missions key ('<task id>#<n>')."""
    task_id = (mission_key or "").split("#", 1)[0]
    try:
        doc = pc.load_program(PROGRAM, lang)
    except pc.ProgramUnavailable:
        return None
    return _all_tasks(doc).get(task_id)


def coins_for_key(mission_key: str) -> int:
    """Coins are invariant between the languages (INVARIANT_KEYS)."""
    task = task_for_key(mission_key)
    return int(task.get("coins") or 0) if task else 0


def mission_card(mission_key: str, lang: Optional[str]) -> Optional[dict[str, Any]]:
    """The fields a mission card carries, for a prayer task — so the parent's
    evening list renders it exactly like an off-screen mission. None when the
    program file (or the task) cannot be read: no blank card, no 0 coins."""
    task = task_for_key(mission_key, lang)
    if task is None:
        return None
    task_id, _, slot = (mission_key or "").partition("#")
    return {
        "title_ar": task.get("title", ""),
        "instruction_ar": task.get("instruction", ""),
        "estimated_minutes": task.get("estimated_minutes", 0),
        "needs_parent": task.get("needs_parent", False),
        "needs_outdoors": False,
        "materials": list(task.get("materials") or []),
        "skill": task.get("skill", ""),
        "program": SOURCE,
        "task_id": task_id,
        "slot": int(slot) if slot.isdigit() else None,
        "coins": int(task.get("coins") or 0),
    }


def _task_payload(task: dict) -> dict[str, Any]:
    return {
        "task_id": task["id"],
        "title": task.get("title"),
        "instruction": task.get("instruction"),
        "estimated_minutes": task.get("estimated_minutes"),
        "needs_parent": bool(task.get("needs_parent")),
        "materials": list(task.get("materials") or []),
        "skill": task.get("skill"),
        "coins": int(task.get("coins") or 0),
        "per_week": int(task.get("per_week") or 0),
        "per_day": per_day(task),
        "week_limit": week_limit(task),
    }


def stage_payload(doc: dict, stage: dict) -> dict[str, Any]:
    return {
        "stage": stage["stage"],
        "key": stage.get("key"),
        "title": stage.get("title"),
        "goal": stage.get("goal"),
        "week_from": stage.get("week_from"),
        "week_to": stage.get("week_to"),
        "parent_assignments": list(stage.get("parent_assignments") or []),
        "confirmation": stage.get("confirmation"),
        "encouragement": list(stage.get("encouragement") or []),
        "if_struggling": stage.get("if_struggling"),
        "covenant": stage.get("covenant"),
        "lesson_ids": list(stage.get("lesson_ids") or []),
        "quran": list(stage.get("quran") or []),
        "evidence": pc.evidence_for(doc, stage.get("evidence_ids")),
        "journey_milestone_key": stage.get("journey_milestone_key"),
    }


def preparation_payload(doc: dict) -> dict[str, Any]:
    prep = doc.get("preparation") or {}
    return {
        "title": prep.get("title"), "goal": prep.get("goal"), "text": prep.get("text"),
        "activities": list(prep.get("activities") or []),
        "lesson_ids": list(prep.get("lesson_ids") or []),
        "evidence": pc.evidence_for(doc, prep.get("evidence_ids")),
    }


def ownership_payload(doc: dict) -> dict[str, Any]:
    own = doc.get("ownership") or {}
    return {
        "title": own.get("title"), "goal": own.get("goal"), "text": own.get("text"),
        "parent_assignments": list(own.get("parent_assignments") or []),
        "confirmation": own.get("confirmation"),
        "encouragement": list(own.get("encouragement") or []),
        "if_struggling": own.get("if_struggling"),
        "lesson_ids": list(own.get("lesson_ids") or []),
        "path_ids": list(own.get("path_ids") or []),
        "evidence": pc.evidence_for(doc, own.get("evidence_ids")),
    }


def graduation_payload(doc: dict) -> dict[str, Any]:
    grad = doc.get("graduation") or {}
    return {
        "title": grad.get("title"), "text": grad.get("text"),
        "certificate_text": grad.get("certificate_text"),
        "covenant": grad.get("covenant"),
        "journey_milestone_keys": list(grad.get("journey_milestone_keys") or []),
        "evidence": pc.evidence_for(doc, grad.get("evidence_ids")),
    }


# ── Enrolment rows ─────────────────────────────────────────────────────────

def active(device_id: str, child_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM prayer_journeys WHERE child_id = ? AND device_id = ? "
            "AND status = 'active'", (child_id, device_id),
        ).fetchone()
    finally:
        conn.close()


def _graduated_on(device_id: str, child_id: int) -> Optional[str]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT ended_on FROM prayer_journeys WHERE child_id = ? AND device_id = ? "
            "AND status = 'graduated' ORDER BY id DESC LIMIT 1", (child_id, device_id),
        ).fetchone()
    finally:
        conn.close()
    return row["ended_on"] if row else None


def current_tasks(doc: dict, row: Optional[sqlite3.Row]) -> list[dict]:
    if row is None:
        return []
    if row["track"] == "journey":
        stage = next((s for s in _stages(doc) if s["stage"] == row["stage"]), None)
        return list((stage or {}).get("child_tasks") or [])
    if row["track"] == "ownership":
        return list((doc.get("ownership") or {}).get("child_tasks") or [])
    return []  # preparation: no daily follow-up, no coins


def _week_window(row: sqlite3.Row, today: date) -> tuple[date, int]:
    """(first day of this program week, week number) from the track's start."""
    started = date.fromisoformat(row["started_on"])
    elapsed = max(0, (today - started).days)
    week_no = elapsed // 7 + 1
    return started + timedelta(days=7 * (week_no - 1)), week_no


def _counts(device_id: str, child_id: int, task_ids: list[str], today: date,
            week_start: date, conn: Optional[sqlite3.Connection] = None
            ) -> dict[str, dict[str, int]]:
    """Per task: today's and this week's claimed / confirmed rows. A card the
    parent answered "not yet", or that expired, does not count — and does not
    count against the child either.

    `conn`: read inside the caller's transaction (the claim's write lock), so
    the count it checks is the count it writes against."""
    out = {t: {"today_claimed": 0, "today_confirmed": 0,
               "week_claimed": 0, "week_confirmed": 0} for t in task_ids}
    if not task_ids:
        return out
    own = conn is None
    conn = conn or get_conn()
    try:
        rows = conn.execute(
            "SELECT mission_key, local_date, status FROM child_missions "
            "WHERE child_id = ? AND device_id = ? AND source = ? AND local_date >= ? "
            "AND local_date <= ? AND status IN ('claimed', 'confirmed')",
            (child_id, device_id, SOURCE, week_start.isoformat(), today.isoformat()),
        ).fetchall()
    finally:
        if own:
            conn.close()
    for r in rows:
        task_id = r["mission_key"].split("#", 1)[0]
        if task_id not in out:
            continue
        state = "confirmed" if r["status"] == "confirmed" else "claimed"
        out[task_id][f"week_{state}"] += 1
        if r["local_date"] == today.isoformat():
            out[task_id][f"today_{state}"] += 1
    return out


def task_progress(doc: dict, device_id: str, child_id: int, row: Optional[sqlite3.Row],
                  today: date) -> list[dict[str, Any]]:
    tasks = current_tasks(doc, row)
    if not tasks:
        return []
    week_start, _ = _week_window(row, today)
    counts = _counts(device_id, child_id, [t["id"] for t in tasks], today, week_start)
    out = []
    for task in tasks:
        c = counts[task["id"]]
        done_today = c["today_claimed"] + c["today_confirmed"]
        done_week = c["week_claimed"] + c["week_confirmed"]
        limit = week_limit(task)
        slots = max(0, per_day(task) - done_today)
        if limit is not None:
            slots = min(slots, max(0, limit - done_week))
        out.append({
            **_task_payload(task),
            "today": {"recorded": done_today, "confirmed": c["today_confirmed"],
                      "slots_left": slots},
            "this_week": {"recorded": done_week, "confirmed": c["week_confirmed"]},
        })
    return out


def _coins_confirmed_since(device_id: str, child_id: int, since: str,
                           task_ids: set[str]) -> int:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT mission_key FROM child_missions WHERE child_id = ? AND device_id = ? "
            "AND source = ? AND status = 'confirmed' AND local_date >= ?",
            (child_id, device_id, SOURCE, since),
        ).fetchall()
    finally:
        conn.close()
    total = 0
    for r in rows:
        if r["mission_key"].split("#", 1)[0] in task_ids:
            total += coins_for_key(r["mission_key"])
    return total


def pending_count(device_id: str, child_id: int) -> int:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM child_missions WHERE child_id = ? AND device_id = ? "
            "AND source = ? AND status = 'claimed'", (child_id, device_id, SOURCE),
        ).fetchone()[0]
    finally:
        conn.close()


# ── The parent's view ──────────────────────────────────────────────────────

def advancement(doc: dict, row: Optional[sqlite3.Row], today: date) -> Optional[dict]:
    """When the content's schedule suggests moving on. A suggestion, never a
    gate on the counts, and never a demotion."""
    if row is None or row["track"] != "journey":
        return None
    stages = _stages(doc)
    stage = next((s for s in stages if s["stage"] == row["stage"]), None)
    if stage is None:
        return None
    started = date.fromisoformat(row["stage_started_on"] or row["started_on"])
    due = started + timedelta(days=stage_planned_days(stage))
    last = row["stage"] == stages[-1]["stage"]
    return {
        "days_in_stage": max(0, (today - started).days),
        "stage_planned_days": stage_planned_days(stage),
        "next_stage": None if last else row["stage"] + 1,
        "advance_suggested": (not last) and today >= due,
        "advance_suggested_on": None if last else due.isoformat(),
        "can_graduate": last and today >= due,
        "graduation_available_on": due.isoformat() if last else None,
    }


def view(doc: dict, device_id: str, child: sqlite3.Row, age: dict,
         today: date) -> dict[str, Any]:
    eligible = eligible_track(doc, age)
    row = active(device_id, child["id"])
    stages = _stages(doc)
    out: dict[str, Any] = {
        "child_id": child["id"],
        "date": today.isoformat(),
        "age": age,
        "title": doc.get("title"),
        "subtitle": doc.get("subtitle"),
        "eligible_track": eligible,
        "allowed_tracks": allowed_tracks(eligible),
        "bands_text": (doc.get("bands") or {}).get("text"),
        "enrolment": None,
        "basis": {"text": (doc.get("basis") or {}).get("text"),
                  "evidence": pc.evidence_for(doc, (doc.get("basis") or {}).get("evidence_ids"))},
        "principles": list(doc.get("principles") or []),
        "reward_policy": {"text": (doc.get("reward_policy") or {}).get("text"),
                          "daily_cap": (doc.get("reward_policy") or {}).get("daily_cap")},
        "stages": [{"stage": s["stage"], "key": s.get("key"), "title": s.get("title"),
                    "goal": s.get("goal"), "week_from": s.get("week_from"),
                    "week_to": s.get("week_to")} for s in stages],
        "graduation": graduation_payload(doc),
        "graduated_on": _graduated_on(device_id, child["id"]),
        "stage": None,
        "preparation": None,
        "ownership": None,
        "tasks": [],
        "advancement": None,
        "pending_confirmations": pending_count(device_id, child["id"]),
        "coins": None,
    }
    track = row["track"] if row else eligible
    if track == "preparation":
        out["preparation"] = preparation_payload(doc)
    elif track == "ownership":
        out["ownership"] = ownership_payload(doc)
    if row is None:
        return out

    week_start, week_no = _week_window(row, today)
    out["enrolment"] = {
        "track": row["track"], "stage": row["stage"], "status": row["status"],
        "started_on": row["started_on"], "stage_started_on": row["stage_started_on"],
        "week": week_no,
    }
    out["tasks"] = task_progress(doc, device_id, child["id"], row, today)
    if row["track"] == "journey":
        stage = next((s for s in stages if s["stage"] == row["stage"]), None)
        if stage is not None:
            out["stage"] = stage_payload(doc, stage)
            out["coins"] = {
                "confirmed_in_stage": _coins_confirmed_since(
                    device_id, child["id"], row["stage_started_on"] or row["started_on"],
                    {t["id"] for t in stage.get("child_tasks") or ()}),
                "covenant_target": (stage.get("covenant") or {}).get("coins_target"),
            }
        out["advancement"] = advancement(doc, row, today)
    return out


# ── Changes ────────────────────────────────────────────────────────────────

def enrol(doc: dict, device_id: str, child: sqlite3.Row, age: dict, today: date, *,
          track: Optional[str], start_stage: Optional[int], restart: bool) -> None:
    eligible = eligible_track(doc, age)
    allowed = allowed_tracks(eligible)
    if not allowed:
        raise JourneyError("not_eligible", eligible_track=None)
    track = track or eligible
    if track not in allowed:
        raise JourneyError("track_not_for_age", allowed_tracks=allowed)
    stages = _stages(doc)
    stage = None
    if track == "journey":
        stage = start_stage or 1
        if not 1 <= stage <= len(stages):
            raise JourneyError("unknown_stage", 422, stages=len(stages))
    elif start_stage is not None:
        raise JourneyError("stage_only_for_journey", 422)
    existing = active(device_id, child["id"])
    if existing is not None and not restart:
        raise JourneyError("already_enrolled", track=existing["track"], stage=existing["stage"])
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if existing is not None:
            conn.execute(
                "UPDATE prayer_journeys SET status = 'ended', ended_on = ?, "
                "updated_at = datetime('now') WHERE id = ? AND status = 'active'",
                (today.isoformat(), existing["id"]),
            )
        conn.execute(
            "INSERT INTO prayer_journeys (device_id, child_id, track, stage, status, "
            "started_on, stage_started_on) VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (device_id, child["id"], track, stage, today.isoformat(), today.isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise JourneyError("already_enrolled") from exc
    finally:
        conn.close()


def set_stage(doc: dict, device_id: str, child: sqlite3.Row, stage_no: int,
              today: date) -> None:
    """Forward one stage at a time; back to any earlier stage, silently."""
    row = active(device_id, child["id"])
    if row is None or row["track"] != "journey":
        raise JourneyError("not_in_journey")
    stages = _stages(doc)
    if not 1 <= stage_no <= len(stages):
        raise JourneyError("unknown_stage", 422, stages=len(stages))
    if stage_no == row["stage"]:
        return
    if stage_no > row["stage"] + 1:
        raise JourneyError("one_stage_at_a_time", next_stage=row["stage"] + 1)
    conn = get_conn()
    try:
        # The stage it was read at, too: two taps on "next stage" move it once.
        cur = conn.execute(
            "UPDATE prayer_journeys SET stage = ?, stage_started_on = ?, "
            "updated_at = datetime('now') WHERE id = ? AND status = 'active' AND stage = ?",
            (stage_no, today.isoformat(), row["id"], row["stage"]),
        )
        conn.commit()
    finally:
        conn.close()
    if cur.rowcount != 1:
        raise JourneyError("stage_changed")


def graduate(doc: dict, device_id: str, child: sqlite3.Row, today: date) -> None:
    """The last stage's weeks done → the journey closes and «صلاتي مسؤوليتي»
    opens, as graduation.text says.

    One transaction, guarded on the row still being active: a second tap that
    read the journey before the first committed finds nothing to close
    (`already_graduated`) instead of tripping the one-active-row index into a
    500 (PR #32 review)."""
    row = active(device_id, child["id"])
    if row is None or row["track"] != "journey":
        raise JourneyError("not_in_journey")
    adv = advancement(doc, row, today)
    if not adv or not adv["can_graduate"]:
        last = _stages(doc)[-1]["stage"]
        raise JourneyError("graduation_not_yet", last_stage=last,
                           available_on=(adv or {}).get("graduation_available_on"))
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE prayer_journeys SET status = 'graduated', ended_on = ?, "
            "updated_at = datetime('now') WHERE id = ? AND status = 'active'",
            (today.isoformat(), row["id"]),
        )
        if cur.rowcount != 1:
            now = conn.execute("SELECT status FROM prayer_journeys WHERE id = ?",
                               (row["id"],)).fetchone()
            raise JourneyError("already_graduated" if now and now["status"] == "graduated"
                               else "not_in_journey")
        conn.execute(
            "INSERT INTO prayer_journeys (device_id, child_id, track, stage, status, "
            "started_on, stage_started_on) VALUES (?, ?, 'ownership', NULL, 'active', ?, ?)",
            (device_id, child["id"], today.isoformat(), today.isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise JourneyError("already_enrolled") from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def end(device_id: str, child: sqlite3.Row, today: date) -> None:
    row = active(device_id, child["id"])
    if row is None:
        raise JourneyError("not_enrolled")
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE prayer_journeys SET status = 'ended', ended_on = ?, "
            "updated_at = datetime('now') WHERE id = ? AND status = 'active'",
            (today.isoformat(), row["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    if cur.rowcount != 1:
        raise JourneyError("not_enrolled")


# ── The child's half (child mode) ──────────────────────────────────────────

def child_today(doc: dict, device_id: str, child_id: int, today: date) -> dict[str, Any]:
    """What the child sees: today's tasks and how many are recorded. No
    stage number, no parent text, nothing that could read as falling behind."""
    row = active(device_id, child_id)
    tasks = task_progress(doc, device_id, child_id, row, today)
    child_fields = ("task_id", "title", "instruction", "estimated_minutes", "needs_parent",
                    "materials", "skill", "coins", "per_day", "week_limit")
    return {
        "date": today.isoformat(),
        "available": True,
        "enrolled": bool(row is not None and tasks),
        "track": row["track"] if row is not None else None,
        "tasks": [{**{k: t[k] for k in child_fields},
                   "recorded_today": t["today"]["recorded"],
                   "slots_left_today": t["today"]["slots_left"],
                   "recorded_this_week": t["this_week"]["recorded"]}
                  for t in tasks],
    }


def claim(doc: dict, device_id: str, child_id: int, task_id: str,
          today: date) -> dict[str, Any]:
    """«صلّيتها» — recorded as claimed at once; the parent confirms tonight.

    The cap check, the slot pick and the insert happen in ONE write
    transaction (BEGIN IMMEDIATE). Checked outside it, a double tap's twin
    could land between the check and the insert, and a once-a-week task was
    recorded — and paid — twice (PR #32 review). Now the second tap waits for
    the first to commit and then sees it: `day_complete` / `week_complete`.
    """
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM prayer_journeys WHERE child_id = ? AND device_id = ? "
            "AND status = 'active'", (child_id, device_id),
        ).fetchone()
        tasks = {t["id"]: t for t in current_tasks(doc, row)}
        if row is None or not tasks:
            raise JourneyError("not_enrolled")
        task = tasks.get(task_id)
        if task is None:
            raise JourneyError("task_not_current", tasks=sorted(tasks))
        week_start, _ = _week_window(row, today)
        c = _counts(device_id, child_id, [task_id], today, week_start, conn=conn)[task_id]
        done_today = c["today_claimed"] + c["today_confirmed"]
        done_week = c["week_claimed"] + c["week_confirmed"]
        limit = week_limit(task)
        if limit is not None and done_week >= limit:
            raise JourneyError("week_complete")
        if done_today >= per_day(task):
            raise JourneyError("day_complete")
        used = {
            int(r["mission_key"].split("#", 1)[1])
            for r in conn.execute(
                "SELECT mission_key FROM child_missions WHERE child_id = ? AND local_date = ? "
                "AND mission_key LIKE ?", (child_id, today.isoformat(), f"{task_id}#%"),
            ).fetchall()
            if r["mission_key"].split("#", 1)[1].isdigit()
        }
        slot = 1
        while slot in used:
            slot += 1
        now = _now_iso()
        cur = conn.execute(
            "INSERT INTO child_missions (device_id, child_id, mission_key, "
            "local_date, status, assigned_at, claimed_at, source) "
            "VALUES (?, ?, ?, ?, 'claimed', ?, ?, ?)",
            (device_id, child_id, f"{task_id}#{slot}", today.isoformat(), now, now, SOURCE),
        )
        mission_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise JourneyError("already_recorded") from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    after = next(t for t in task_progress(doc, device_id, child_id, row, today)
                 if t["task_id"] == task_id)
    return {"ok": True, "status": "claimed", "mission_id": mission_id, "task_id": task_id,
            "slot": slot, "recorded_today": after["today"]["recorded"],
            "slots_left_today": after["today"]["slots_left"]}
