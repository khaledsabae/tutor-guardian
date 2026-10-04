"""«رمضان العائلة» — the day, the fasting ladder, the «تمّ» marks and the card.

Content: `knowledge_base/curriculum/programs/ramadan_family.json` (schema.md
§8.2). This module decides *which* piece a family sees on a date; it never
writes program text.

**The calendar.** Ramadan's first day is announced by moon sighting, not
computed: the content's `season.expected_start_<hijri year>` (1448, 1449, …)
are planning estimates ("بداية الشهر الفعلية يحدّدها التطبيق/الخادم بإعلان الرؤية لا
هذا الحقل"). After the last year the content knows, the program is off-season
— so each year's estimate is added a season ahead.
So the start is configuration — `RAMADAN_START_<hijri year>=YYYY-MM-DD` on
the server, read per call — and the estimate is used, and labelled
`start_source: "estimate"`, only until it is set. The month's length is
`RAMADAN_DAYS_<year>` (29 or 30); until announced it is 30, and day 30 is the
content's `may_not_occur` farewell that nothing else is built on.

Sighting differs by country, so a family may move its own season by one day
(`ramadan_shift_days` −1/0/+1) and set its own month length (29/30) — both
stored for that season only (program_settings.ramadan_year).

**The night precedes its day.** In the Hijri reckoning night 21 is the evening
of day 20. The content already encodes this (`odd_night` on days 20, 22, …,
28; `night_joined` on the evenings of 20–28), so the server's day index is the
family's civil date — a mark made after midnight for last night's activity
lands on the day it belongs to because past days of the month stay markable.

**Positive marks only.** Nothing here records a missed day, a broken fast or a
step down the ladder. The card's numbers only go up, a line below its
`min_to_show` is dropped rather than shown small, and a metric marked
`shareable: false` (the children's fasting) never reaches the shared card —
it is returned separately, for the family's eyes, in `family_only`.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Optional

from app.db.init_db import get_conn
from app.services import programs_common as pc

logger = logging.getLogger(__name__)

PROGRAM = "ramadan_family"
FAMILY = 0                 # child_id of a row that belongs to the whole family
BRIDGE_WEEKS = 4           # after_ramadan.weeks
DEFAULT_MONTH_DAYS = 30

FAMILY_MARKS = ("challenge_done", "wird_done", "story_heard", "juz_read",
                "night_joined", "family_word")
STEP_UP = "fasting_step_up"
PRACTISED = "fasting_practised"

_ESTIMATE_KEY = re.compile(r"^expected_start_(\d{4})$")
_ENV_START = re.compile(r"^RAMADAN_START_(\d{4})$")


class RamadanError(Exception):
    """A request the program refuses, with a stable error code."""

    def __init__(self, code: str, status: int = 409, **extra: Any):
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


# ── The season ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Season:
    hijri_year: int
    start: date
    days: int
    start_source: str          # "configured" | "estimate"
    days_confirmed: bool
    shift_days: int = 0        # the family's own sighting, already applied to start
    days_source: str = "server"

    @property
    def eid(self) -> date:
        return self.start + timedelta(days=self.days)

    @property
    def bridge_start(self) -> date:
        return self.eid + timedelta(days=1)

    @property
    def bridge_end(self) -> date:  # exclusive
        return self.bridge_start + timedelta(days=7 * BRIDGE_WEEKS)

    def as_dict(self) -> dict[str, Any]:
        return {
            "hijri_year": self.hijri_year,
            "starts_on": self.start.isoformat(),
            "days": self.days,
            "eid_on": self.eid.isoformat(),
            "bridge_ends_on": (self.bridge_end - timedelta(days=1)).isoformat(),
            "start_source": self.start_source,
            "days_confirmed": self.days_confirmed,
            "shift_days": self.shift_days,
        }


def _env_date(name: str) -> Optional[date]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        logger.warning("%s=%r is not YYYY-MM-DD — ignored", name, raw)
        return None


def _env_days(year: int) -> Optional[int]:
    raw = os.environ.get(f"RAMADAN_DAYS_{year}", "").strip()
    if not raw:
        return None
    if raw in ("29", "30"):
        return int(raw)
    logger.warning("RAMADAN_DAYS_%s=%r is not 29 or 30 — ignored", year, raw)
    return None


def server_seasons(doc: Optional[dict] = None) -> list[Season]:
    """Every season the server knows, oldest first: configured starts from the
    environment, and the content's estimates for years not configured."""
    doc = doc or pc.load_program(PROGRAM)
    found: dict[int, Season] = {}
    for key, value in (doc.get("season") or {}).items():
        m = _ESTIMATE_KEY.match(key)
        if not m:
            continue
        try:
            start = date.fromisoformat(str(value))
        except ValueError:
            continue
        year = int(m.group(1))
        found[year] = Season(year, start, DEFAULT_MONTH_DAYS, "estimate", False)
    for name in os.environ:
        m = _ENV_START.match(name)
        if not m:
            continue
        start = _env_date(name)
        if start is None:
            continue
        year = int(m.group(1))
        found[year] = Season(year, start, DEFAULT_MONTH_DAYS, "configured", False)
    for year, season in list(found.items()):
        days = _env_days(year)
        if days is not None:
            found[year] = replace(season, days=days, days_confirmed=True)
    return sorted(found.values(), key=lambda s: s.start)


def family_seasons(settings: dict, doc: Optional[dict] = None) -> list[Season]:
    """The server's seasons with the family's own sighting applied to the one
    season it was set for."""
    out = []
    year = settings.get("ramadan_year")
    for season in server_seasons(doc):
        if year is not None and season.hijri_year == year:
            shift = int(settings.get("ramadan_shift_days") or 0)
            days = settings.get("ramadan_days")
            season = replace(
                season,
                start=season.start + timedelta(days=shift),
                shift_days=shift,
                days=int(days) if days in (29, 30) else season.days,
                days_confirmed=season.days_confirmed or days in (29, 30),
                days_source="family" if days in (29, 30) else season.days_source,
            )
        out.append(season)
    return out


def seasons_or_empty(settings: dict) -> list[Season]:
    """The family's seasons, or none when the Ramadan file cannot be read —
    for the programs that only *consult* the calendar (the first-fast
    milestone): a missing Ramadan file must not take them down with it."""
    try:
        return family_seasons(settings)
    except pc.ProgramUnavailable:
        return []


def locate(today: date, seasons: list[Season]) -> dict[str, Any]:
    """Where `today` falls: upcoming · ramadan · eid · after · off_season."""
    for season in seasons:
        if today < season.start:
            return {"state": "upcoming", "season": season,
                    "days_until_start": (season.start - today).days}
        if today < season.eid:
            return {"state": "ramadan", "season": season,
                    "day": (today - season.start).days + 1}
        if today == season.eid:
            return {"state": "eid", "season": season}
        if today < season.bridge_end:
            return {"state": "after", "season": season,
                    "week": (today - season.bridge_start).days // 7 + 1}
    return {"state": "off_season", "season": seasons[-1] if seasons else None}


def season_by_year(seasons: list[Season], hijri_year: int) -> Optional[Season]:
    return next((s for s in seasons if s.hijri_year == hijri_year), None)


def markable_days(where: dict[str, Any]) -> int:
    """How many days of the located season may carry marks today: up to today
    during the month, the whole month from Eid to the end of the bridge (a
    family that forgot day 29 can still tick it on Eid), none otherwise."""
    state = where["state"]
    if state == "ramadan":
        return where["day"]
    if state in ("eid", "after"):
        return where["season"].days
    return 0


def set_family_season(device_id: str, hijri_year: int, *, shift_days: Optional[int],
                      month_days: Optional[int], set_month_days: bool) -> None:
    """The family's own sighting for one season. Values not sent are kept for
    the same season and reset for a new one — last year's sighting is not
    carried into this year's month. `set_month_days` with `month_days=None`
    clears the family's month length (back to the server's)."""
    current = pc.device_settings(device_id)
    same_year = current.get("ramadan_year") == hijri_year
    if shift_days is None:
        shift_days = (current.get("ramadan_shift_days") or 0) if same_year else 0
    if not set_month_days:
        month_days = current.get("ramadan_days") if same_year else None
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO program_settings (device_id, ramadan_year, ramadan_shift_days,
                                          ramadan_days, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(device_id) DO UPDATE SET
                ramadan_year = excluded.ramadan_year,
                ramadan_shift_days = excluded.ramadan_shift_days,
                ramadan_days = excluded.ramadan_days,
                updated_at = excluded.updated_at
            """,
            (device_id, hijri_year, int(shift_days), month_days),
        )
        conn.commit()
    finally:
        conn.close()


# ── Content pieces ─────────────────────────────────────────────────────────

def variant_band(doc: dict, band: str) -> Optional[str]:
    """Which of the five day variants a child's band sees (bands.band_map):
    2-3 → 0-3, 16-18 → 13-15, prenatal-1 → none (the family challenge and its
    note only). An unknown label sees none rather than a guess."""
    return (doc.get("bands") or {}).get("band_map", {}).get(band)


def _note(doc: dict, note: Optional[dict]) -> Optional[dict]:
    if not note:
        return None
    return {"text": note.get("text", ""),
            "evidence": pc.evidence_for(doc, note.get("evidence_ids"))}


def _variant(item: dict, band_key: Optional[str]) -> Optional[dict]:
    if not band_key:
        return None
    v = (item.get("variants") or {}).get(band_key)
    if not v:
        return None
    return {"band": band_key, "addressed_to": v.get("addressed_to"), "text": v.get("text")}


def day_payload(doc: dict, day_no: int, band_key: Optional[str]) -> dict[str, Any]:
    day = next((d for d in doc.get("days", []) if d.get("day") == day_no), None)
    if day is None:
        raise pc.ProgramUnavailable(f"{PROGRAM}: day {day_no}")
    tracks = list(day.get("tracks") or [])
    return {
        "day": day["day"],
        "phase": day.get("phase"),
        "key": day.get("key"),
        "title": day.get("title"),
        "family_challenge": dict(day.get("family_challenge") or {}),
        "parent_note": _note(doc, day.get("parent_note")),
        "variant": _variant(day, band_key),
        "quran": day.get("quran"),
        "story_id": day.get("story_id"),
        "last_ten": bool(day.get("last_ten")),
        "odd_night": bool(day.get("odd_night")),
        "may_not_occur": bool(day.get("may_not_occur")),
        "tracks": tracks,
        # The day the family picks its word (day 28): the eight words to pick
        # from, in the reader's language; the mark stores the index.
        "family_word_choices": _family_word_choices(doc) if "family_word" in tracks else None,
    }


def eid_payload(doc: dict, band_key: Optional[str]) -> dict[str, Any]:
    eid = doc.get("eid") or {}
    return {
        "title": eid.get("title"),
        "activities": list(eid.get("activities") or []),
        "parent_note": _note(doc, eid.get("parent_note")),
        "variant": _variant(eid, band_key),
        "quran": eid.get("quran"),
        "evidence": pc.evidence_for(doc, eid.get("evidence_ids")),
    }


def _week(item: dict, features: set[str]) -> dict[str, Any]:
    needs = item.get("requires_feature")
    available = needs is None or needs in features
    out = {"week": item.get("week"), "title": item.get("title"),
           "text": item.get("text") if available else item.get("fallback_text")}
    if needs is not None:
        out["requires_feature"] = needs
        out["feature_available"] = available
    return out


def after_payload(doc: dict, week_no: Optional[int], features: set[str]) -> dict[str, Any]:
    after = doc.get("after_ramadan") or {}
    weeks = [_week(w, features) for w in after.get("weeks", [])]
    return {
        "title": after.get("title"),
        "text": after.get("text"),
        "keep_habits": list(after.get("keep_habits") or []),
        "week": next((w for w in weeks if w["week"] == week_no), None),
        "weeks": weeks,
        "links": after.get("links"),
        "evidence": pc.evidence_for(doc, after.get("evidence_ids")),
    }


def kickoff_payload(doc: dict) -> dict[str, Any]:
    kickoff = doc.get("kickoff") or {}
    return {"title": kickoff.get("title"), "text": kickoff.get("text"),
            "setup_steps": list(kickoff.get("setup_steps") or [])}


# ── The fasting ladder ─────────────────────────────────────────────────────

def ladder_band(doc: dict, band_key: Optional[str], puberty: bool) -> Optional[str]:
    """Puberty, not age, makes fasting obligatory (schema.md §8.2): a child the
    parent marked as having reached it is on the 13-15 ladder, whatever the
    band. Otherwise the ladder follows the day variants' band."""
    if puberty:
        return "13-15"
    bands = (doc.get("fasting_ladder") or {}).get("bands", {})
    return band_key if band_key in bands else None


def _steps(doc: dict, ladder: Optional[str]) -> list[dict]:
    if not ladder:
        return []
    return list(((doc.get("fasting_ladder") or {}).get("bands", {})
                 .get(ladder, {}).get("steps") or []))


def _step(doc: dict, step_key: Optional[str]) -> Optional[dict]:
    """A step by key, in any band — the hours are what a climb compares."""
    if not step_key:
        return None
    for band in ((doc.get("fasting_ladder") or {}).get("bands") or {}).values():
        for step in band.get("steps") or ():
            if step.get("key") == step_key:
                return step
    return None


def _eligible(step: dict, age: dict, puberty: bool) -> bool:
    """A step is for a child old enough for it. Unknown age: the parent
    decides, and the step's own `min_age_years` is shown with it."""
    if puberty or age.get("years") is None:
        return True
    return age["years"] >= int(step.get("min_age_years") or 0)


def current_step(device_id: str, child_id: int, hijri_year: int) -> Optional[str]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT step_key FROM ramadan_fasting WHERE child_id = ? AND device_id = ? "
            "AND hijri_year = ?", (child_id, device_id, hijri_year),
        ).fetchone()
    finally:
        conn.close()
    return row["step_key"] if row else None


def _practised_days(device_id: str, child_id: int, hijri_year: int) -> set[int]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT day FROM ramadan_marks WHERE device_id = ? AND child_id = ? "
            "AND hijri_year = ? AND mark = ?",
            (device_id, child_id, hijri_year, PRACTISED),
        ).fetchall()
    finally:
        conn.close()
    return {r["day"] for r in rows}


def fasting_state(doc: dict, device_id: str, child: sqlite3.Row, age: dict,
                  where: dict[str, Any]) -> dict[str, Any]:
    """The child's ladder: band, steps (with eligibility), current step, and —
    during the month — this week's practice against the step's weekly cap.
    `rest_suggested` is care, not a score: it says the step's own
    `max_days_per_week` has been reached, so the next day is a rest day."""
    season = where.get("season")
    puberty = pc.reached_puberty(device_id, child["id"])
    band_key = variant_band(doc, age["band"])
    ladder = ladder_band(doc, band_key, puberty)
    band = ((doc.get("fasting_ladder") or {}).get("bands") or {}).get(ladder or "", {})
    step_key = current_step(device_id, child["id"], season.hijri_year) if season else None
    step = next((s for s in _steps(doc, ladder) if s.get("key") == step_key), None)

    practised_today = False
    week_count = 0
    if season is not None and where["state"] == "ramadan":
        days = _practised_days(device_id, child["id"], season.hijri_year)
        today_no = where["day"]
        practised_today = today_no in days
        week_count = sum(1 for d in days if today_no - 6 <= d <= today_no)
    cap = step.get("max_days_per_week") if step else None
    return {
        "ladder_band": ladder,
        "fasts": band.get("fasts"),
        "summary": band.get("summary"),
        "reached_puberty": puberty,
        "current_step": None if step is None else {
            "key": step["key"], "label": step.get("label"), "until": step.get("until"),
            "approx_hours": step.get("approx_hours"),
            "max_days_per_week": cap,
        },
        "steps": [
            {**{k: s.get(k) for k in ("key", "label", "until", "approx_hours",
                                       "min_age_years", "max_days_per_week",
                                       "advance_when", "text")},
             "eligible": _eligible(s, age, puberty)}
            for s in _steps(doc, ladder)
        ],
        "practised_today": practised_today,
        "practised_this_week": week_count,
        "rest_suggested": bool(cap is not None and week_count >= cap),
    }


def ladder_guidance(doc: dict) -> dict[str, Any]:
    """The safety half of the ladder screen: who sees a doctor first, when the
    fast stops, what is urgent and what to do then (schema.md §8.2)."""
    ladder = doc.get("fasting_ladder") or {}
    return {k: ladder.get(k) for k in (
        "title", "principles", "doctor_first", "stop_signs", "stop_action",
        "urgent_signs", "urgent_action", "tips")} | {
        "evidence": pc.evidence_for(doc, ladder.get("evidence_ids"))}


def season_for_child_settings(where: dict[str, Any]) -> Season:
    """The season a ladder change belongs to: the current or coming one."""
    season = where.get("season")
    if season is None or where["state"] == "off_season":
        raise RamadanError("not_in_season")
    return season


def set_fasting(doc: dict, device_id: str, child: sqlite3.Row, age: dict,
                where: dict[str, Any], *, step_key: Optional[str],
                puberty: Optional[bool]) -> dict[str, Any]:
    """Set the child's step and/or the puberty flag.

    Everything is validated before anything is written, and both are written
    in one transaction: a step refused with a 422 used to leave the puberty
    flag sent beside it already saved (PR #32 review).

    A climb — a step with more fasting hours than the one before, during the
    month — is the card's private «درجات صيام صعدها أطفالنا». A step down is
    just a change: nothing records it, nothing counts it.
    """
    # The ladder the step must be on is the one the NEW puberty value implies.
    new_puberty = puberty if puberty is not None \
        else pc.reached_puberty(device_id, child["id"])
    season = None
    climbed = False
    if step_key is not None:
        season = season_for_child_settings(where)
        ladder = ladder_band(doc, variant_band(doc, age["band"]), new_puberty)
        step = next((s for s in _steps(doc, ladder) if s.get("key") == step_key), None)
        if step is None:
            raise RamadanError("unknown_step", 422, ladder_band=ladder)
        if not _eligible(step, age, new_puberty):
            raise RamadanError("step_not_for_age", 422,
                               min_age_years=step.get("min_age_years"))
        before = _step(doc, current_step(device_id, child["id"], season.hijri_year))
        climbed = bool(before is not None
                       and (step.get("approx_hours") or 0) > (before.get("approx_hours") or 0)
                       and where["state"] == "ramadan")
    conn = get_conn()
    try:
        if puberty is not None:
            # A fact about the child, not about this season: settable any time.
            conn.execute(
                """
                INSERT INTO program_children (child_id, device_id, reached_puberty, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(child_id) DO UPDATE SET
                    reached_puberty = excluded.reached_puberty,
                    updated_at = excluded.updated_at
                """,
                (child["id"], device_id, 1 if puberty else 0),
            )
        if step_key is not None:
            conn.execute(
                """
                INSERT INTO ramadan_fasting (device_id, child_id, hijri_year, step_key, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(child_id, hijri_year) DO UPDATE SET
                    step_key = excluded.step_key, updated_at = excluded.updated_at
                """,
                (device_id, child["id"], season.hijri_year, step_key),
            )
            if climbed:
                conn.execute(
                    "INSERT OR IGNORE INTO ramadan_marks (device_id, child_id, hijri_year, day, "
                    "mark, value) VALUES (?, ?, ?, ?, ?, ?)",
                    (device_id, child["id"], season.hijri_year, where["day"], STEP_UP,
                     step_key),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"climbed": climbed}


def set_practised(device_id: str, child: sqlite3.Row, where: dict[str, Any], *,
                  day: Optional[int], done: bool) -> int:
    """«تدرّب اليوم على درجته» — one positive mark per child per day. Undoing
    deletes it; there is no "did not manage" to record."""
    season = where.get("season")
    limit = markable_days(where)
    if season is None or limit == 0:
        raise RamadanError("not_in_season")
    if day is None:
        if where["state"] != "ramadan":
            raise RamadanError("day_required", 422)
        day = where["day"]
    if not 1 <= day <= limit:
        raise RamadanError("day_not_markable", 422, markable_up_to=limit)
    step_key = current_step(device_id, child["id"], season.hijri_year)
    if done and step_key is None:
        raise RamadanError("no_step_set")
    conn = get_conn()
    try:
        if done:
            conn.execute(
                "INSERT INTO ramadan_marks (device_id, child_id, hijri_year, day, mark, value) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(device_id, child_id, hijri_year, day, mark) "
                "DO UPDATE SET value = excluded.value",
                (device_id, child["id"], season.hijri_year, day, PRACTISED, step_key),
            )
        else:
            conn.execute(
                "DELETE FROM ramadan_marks WHERE device_id = ? AND child_id = ? "
                "AND hijri_year = ? AND day = ? AND mark = ?",
                (device_id, child["id"], season.hijri_year, day, PRACTISED),
            )
        conn.commit()
    finally:
        conn.close()
    return day


# ── Family marks ───────────────────────────────────────────────────────────

def _family_word_choices(doc: dict) -> list[str]:
    for metric in (doc.get("recap") or {}).get("metrics", []):
        if metric.get("source") == "family_word":
            return list(metric.get("choices") or [])
    return []


def day_marks(doc: dict, device_id: str, season: Season, day_no: int) -> dict[str, Any]:
    """The day card's «تمّ» toggles: one per mark in the day's `tracks`."""
    day = next((d for d in doc.get("days", []) if d.get("day") == day_no), None)
    tracks = list((day or {}).get("tracks") or [])
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT mark, value FROM ramadan_marks WHERE device_id = ? AND child_id = ? "
            "AND hijri_year = ? AND day = ?",
            (device_id, FAMILY, season.hijri_year, day_no),
        ).fetchall()
    finally:
        conn.close()
    done = {r["mark"]: r["value"] for r in rows}
    out: dict[str, Any] = {t: t in done for t in tracks}
    if "family_word" in tracks:
        idx = done.get("family_word")
        choices = _family_word_choices(doc)
        out["family_word"] = None if idx is None else {
            "choice_index": int(idx),
            "word": choices[int(idx)] if idx is not None and int(idx) < len(choices) else None,
        }
    return out


def set_family_mark(doc: dict, device_id: str, where: dict[str, Any], *, mark: str,
                    day: Optional[int], done: bool,
                    choice_index: Optional[int]) -> int:
    """Tick (or untick) a family mark on a day of the month.

    Only marks the day's card offers (`tracks`) — a story on a day with no
    story, a night outside 20–28, the family word on any day but 28 — are
    refused; so are days still to come.
    """
    if mark not in FAMILY_MARKS:
        raise RamadanError("unknown_mark", 422, allowed=list(FAMILY_MARKS))
    season = where.get("season")
    limit = markable_days(where)
    if season is None or limit == 0:
        raise RamadanError("not_in_season")
    if day is None:
        if where["state"] != "ramadan":
            raise RamadanError("day_required", 422)
        day = where["day"]
    if not 1 <= day <= limit:
        raise RamadanError("day_not_markable", 422, markable_up_to=limit)
    entry = next((d for d in doc.get("days", []) if d.get("day") == day), {})
    if mark not in (entry.get("tracks") or ()):
        raise RamadanError("mark_not_on_this_day", 422, tracks=list(entry.get("tracks") or []))
    value = None
    if mark == "family_word" and done:
        choices = _family_word_choices(doc)
        if choice_index is None or not 0 <= choice_index < len(choices):
            raise RamadanError("choice_index_required", 422, choices=len(choices))
        value = str(choice_index)
    conn = get_conn()
    try:
        if done:
            conn.execute(
                "INSERT INTO ramadan_marks (device_id, child_id, hijri_year, day, mark, value) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(device_id, child_id, hijri_year, day, mark) "
                "DO UPDATE SET value = excluded.value",
                (device_id, FAMILY, season.hijri_year, day, mark, value),
            )
        else:
            conn.execute(
                "DELETE FROM ramadan_marks WHERE device_id = ? AND child_id = ? "
                "AND hijri_year = ? AND day = ? AND mark = ?",
                (device_id, FAMILY, season.hijri_year, day, mark),
            )
        conn.commit()
    finally:
        conn.close()
    return day


# ── «رمضان عائلتنا» — the card ─────────────────────────────────────────────

def _metric_values(doc: dict, device_id: str, hijri_year: int) -> dict[str, Any]:
    """Every recap metric's value for the family's season."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT child_id, day, mark, value FROM ramadan_marks "
            "WHERE device_id = ? AND hijri_year = ?",
            (device_id, hijri_year),
        ).fetchall()
    finally:
        conn.close()
    values: dict[str, Any] = {}
    choices = _family_word_choices(doc)
    for metric in (doc.get("recap") or {}).get("metrics", []):
        source = metric.get("source")
        if source == "family_word":
            picked = [r for r in rows if r["child_id"] == FAMILY and r["mark"] == "family_word"]
            picked.sort(key=lambda r: r["day"])
            word = None
            if picked and picked[-1]["value"] is not None:
                idx = int(picked[-1]["value"])
                word = choices[idx] if 0 <= idx < len(choices) else None
            values[metric["key"]] = word
        elif source == STEP_UP:
            values[metric["key"]] = sum(1 for r in rows if r["mark"] == STEP_UP
                                        and r["child_id"] != FAMILY)
        else:
            count = len({r["day"] for r in rows
                         if r["child_id"] == FAMILY and r["mark"] == source})
            cap = metric.get("max")
            values[metric["key"]] = min(count, cap) if isinstance(cap, int) else count
    return values


def _app_link(device_id: str, hijri_year: int) -> str:
    """The Play link the shared card carries — with the family's own invite
    code, so an install it brings is credited to them («أجرك الجاري»)."""
    from app.services.attribution import PLAY_URL, play_install_url
    # Hyphens, not underscores: attribution percent-encodes '_' in a utm value
    # (so a value can never pass for a ref_ code), which reads badly in a link.
    utm = {"utm_source": "ramadan-card", "utm_medium": "share",
           "utm_campaign": f"ramadan-{hijri_year}"}
    try:
        from app.routers.referral import _code_for_device
        conn = get_conn()
        try:
            code = _code_for_device(conn, device_id)
        finally:
            conn.close()
        return play_install_url(code, utm)
    except Exception:  # noqa: BLE001 — a card without the code still shares
        logger.warning("ramadan recap: no invite code, sharing the plain link")
        return play_install_url(None, utm) or PLAY_URL


def recap(doc: dict, device_id: str, lang: str, season: Season,
          today: date) -> dict[str, Any]:
    """The family's numbers for a season, and — from Eid on — the shareable
    card. Two blocks that never mix:

    * `card` holds only `shareable` metrics whose value clears `min_to_show`
      (a line that would show a small number is dropped, not shown);
    * `family_only` holds the rest (the children's fasting), for in-app view.
    """
    rec = doc.get("recap") or {}
    metrics = rec.get("metrics", [])
    values = _metric_values(doc, device_id, season.hijri_year)
    shareable = {m["key"] for m in metrics if m.get("shareable", True)}
    minimum = rec.get("min_to_show") or {}
    labels = {m["key"]: m.get("label") for m in metrics}

    def shown(key: str) -> bool:
        value = values.get(key)
        if key not in shareable or value in (None, ""):
            return False
        if isinstance(value, int):
            return value >= int(minimum.get(key, 1))
        return True

    available = today >= season.eid
    card = None
    if available:
        templates = rec.get("templates") or {}
        lines = []
        for template in templates.get("lines", []):
            keys = re.findall(r"\{(\w+)\}", template)
            if not keys or not all(shown(k) for k in keys):
                continue
            text = template
            for k in keys:
                value = values[k]
                text = text.replace("{%s}" % k, pc.localise_number(value, lang)
                                    if isinstance(value, int) else str(value))
            lines.append({"keys": keys, "text": text})
        year = pc.localise_number(season.hijri_year, lang)
        card = {
            "title": rec.get("card_title"),
            "headline": (templates.get("headline") or "").replace("{hijri_year}", year),
            "lines": lines,
            "metrics": [{"key": k, "label": labels.get(k), "value": values[k]}
                        for k in [m["key"] for m in metrics] if shown(k)],
            "closing": templates.get("closing"),
            "share_text": (templates.get("share_text") or "").replace(
                "{app_link}", _app_link(device_id, season.hijri_year)),
        }
        # Belt and braces over check_programs: nothing private on the card.
        private = set(labels) - shareable
        card["lines"] = [ln for ln in card["lines"] if not private & set(ln["keys"])]
    return {
        "hijri_year": season.hijri_year,
        "available": available,
        "available_on": season.eid.isoformat(),
        "show_on": rec.get("show_on"),
        "card": card,
        "progress": [{"key": m["key"], "label": m.get("label"), "value": values.get(m["key"]),
                      "max": m.get("max")}
                     for m in metrics if m.get("shareable", True)],
        "family_only": [{"key": m["key"], "label": m.get("label"), "value": values.get(m["key"])}
                        for m in metrics if not m.get("shareable", True)],
        "privacy": (rec.get("privacy") or {}).get("text"),
    }
