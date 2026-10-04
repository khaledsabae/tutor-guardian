"""The proactive milestones — «ابنك هيكمّل ٧ سنين الشهر الجاي».

Content: `knowledge_base/curriculum/programs/milestones.json` (schema.md §8.4).
Each milestone is a short alert plus a 3–5 card guide, for the parent only.

**Timing needs a birth month.** An `age` milestone falls due in the month the
child reaches `age_months`; its alert opens `alert_days_before` (30) earlier —
counted in calendar months, because the content's alert text says "next month"
and a birth *month* has no day: a child born in March 2020 is alerted on
1 February 2027 that he turns seven next month. A `season_age` milestone
(first fasting) is due at the season's start for a child whose age then lies
between `min_age_months` and `max_age_months`, and opens 30 days before it.

**Without a birth month there is no push** (alert_policy): the card simply
sits in the parent's library — state `library` — for a child whose band is in
the milestone's `band_fallback`, and the response asks for the birth month.

**Gender.** A milestone for one gender is shown only when the profile says
that gender; when the gender is unknown and `if_gender_unknown` is `ask`, the
card is withheld and `needs_profile` asks for it instead (the content's rule:
"يُعرض طلب إكمال الملف بدلًا منها").

A child the parent marked as having reached puberty no longer needs the
"before puberty" reminders: those turn `past` and are never pushed.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

from app.services import programs_common as pc
from app.services import ramadan_program as rp

PROGRAM = "milestones"

# A due card stays "due" this long after its date — the guide is still the
# right read in the weeks after the birthday — then turns "past".
DUE_GRACE_DAYS = 90
# Lists stay about the near future and the recent past: a newborn's parent is
# not shown the teenage guide, nor a fifteen-year-old's the school-entry one.
UPCOMING_HORIZON_DAYS = 365
PAST_HORIZON_DAYS = 365

PUBERTY_KEYS = frozenset({"puberty_girls", "puberty_boys"})


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def alert_months(trigger: dict) -> int:
    return max(1, round(int(trigger.get("alert_days_before") or 30) / 30))


def _band_matches(child_band: str, fallback: list[str]) -> bool:
    if not fallback:
        return False
    from app.core.taxonomy import canonical_age_group
    return child_band in fallback or canonical_age_group(child_band) in fallback


def timing(milestone: dict, birth_month: Optional[str], band: str, today: date,
           seasons: list[rp.Season]) -> Optional[dict[str, Any]]:
    """{state, due_on, alert_on, push_until, season?} or None when the
    milestone is not this child's at all."""
    trigger = milestone.get("trigger") or {}
    parsed = pc.parse_birth_month(birth_month)
    if parsed is None:
        if _band_matches(band, list(trigger.get("band_fallback") or [])):
            return {"state": "library", "basis": "age_group", "due_on": None,
                    "alert_on": None, "push_until": None}
        return None

    if trigger.get("type") == "season_age":
        lo, hi = int(trigger["min_age_months"]), int(trigger["max_age_months"])
        for season in seasons:
            if today >= season.eid:
                continue                      # this season is over for this card
            months = pc.age_in_months(birth_month, season.start)
            if months is None or not lo <= months <= hi:
                continue
            alert_on = season.start - timedelta(days=int(trigger.get("alert_days_before") or 30))
            state = "upcoming" if today < alert_on else "due"
            return {"state": state, "basis": "birth_month", "due_on": season.start.isoformat(),
                    "alert_on": alert_on.isoformat(), "push_until": season.start.isoformat(),
                    "season": {"name": trigger.get("season"), "hijri_year": season.hijri_year,
                               "starts_on": season.start.isoformat(),
                               "start_source": season.start_source}}
        return None

    age_months = trigger.get("age_months")
    if age_months is None:
        return None
    due_y, due_m = _shift_month(parsed[0], parsed[1], int(age_months))
    due_on = date(due_y, due_m, 1)
    alert_on = date(*_shift_month(due_y, due_m, -alert_months(trigger)), 1)
    if today < alert_on:
        state = "upcoming"
    elif today < due_on + timedelta(days=DUE_GRACE_DAYS):
        state = "due"
    else:
        state = "past"
    return {"state": state, "basis": "birth_month", "due_on": due_on.isoformat(),
            "alert_on": alert_on.isoformat(), "push_until": due_on.isoformat()}


def audience_ok(milestone: dict, gender: Optional[str]) -> Optional[bool]:
    """True: for this child. False: not (the other gender). None: withheld
    until the profile says (if_gender_unknown = ask)."""
    audience = milestone.get("audience") or {}
    wanted = audience.get("gender", "any")
    if wanted == "any":
        return True
    if gender is None:
        return True if audience.get("if_gender_unknown") == "show" else None
    return gender == wanted


def card_payload(doc: dict, milestone: dict, when: dict[str, Any],
                 alerted: Optional[sqlite3.Row]) -> dict[str, Any]:
    return {
        "key": milestone["key"],
        "order": milestone.get("order"),
        "state": when["state"],
        "basis": when["basis"],
        "due_on": when["due_on"],
        "alert_on": when["alert_on"],
        "season": when.get("season"),
        "title": milestone.get("title"),
        "medical": bool(milestone.get("medical")),
        "alert": milestone.get("alert"),
        "cards": list(milestone.get("cards") or []),
        "red_flags": list(milestone.get("red_flags") or []),
        "quran": list(milestone.get("quran") or []),
        "evidence": pc.evidence_for(doc, milestone.get("evidence_ids")),
        "links": milestone.get("links"),
        "pushed_at": alerted["sent_at"] if alerted is not None else None,
    }


def _alerts(device_id: str, child_id: int) -> dict[str, sqlite3.Row]:
    from app.db.init_db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM milestone_alerts WHERE child_id = ? AND device_id = ? "
            "AND status = 'sent'", (child_id, device_id),
        ).fetchall()
    finally:
        conn.close()
    return {r["milestone_key"]: r for r in rows}


def in_horizon(when: dict[str, Any], today: date) -> bool:
    """Whether a card belongs in today's lists at all (see the horizons)."""
    if when["state"] == "upcoming" and when["alert_on"]:
        return (date.fromisoformat(when["alert_on"]) - today).days <= UPCOMING_HORIZON_DAYS
    if when["state"] == "past" and when["due_on"]:
        return (today - date.fromisoformat(when["due_on"])).days <= PAST_HORIZON_DAYS
    return True


def evaluate(doc: dict, child: sqlite3.Row, today: date, seasons: list[rp.Season],
             puberty: bool) -> tuple[list[tuple[dict, dict]], set[str]]:
    """[(milestone, timing)] that belong to this child, and the profile fields
    whose absence withheld a card."""
    keys = child.keys()
    birth_month = child["birth_month"] if "birth_month" in keys else None
    band = (child["age_group"] or "").strip()
    gender = pc.gender_of(child)
    out = []
    needs: set[str] = set()
    for milestone in sorted(doc.get("milestones", []), key=lambda m: m.get("order", 0)):
        ok = audience_ok(milestone, gender)
        if ok is False:
            continue
        when = timing(milestone, birth_month, band, today, seasons)
        if when is None:
            continue
        if ok is None:
            # Asked for only when the withheld card is near enough to matter.
            if in_horizon(when, today):
                needs.add("gender")
            continue
        if puberty and milestone["key"] in PUBERTY_KEYS:
            when = {**when, "state": "past"}
        out.append((milestone, when))
    if pc.parse_birth_month(birth_month) is None:
        needs.add("birth_month")
    return out, needs


def child_milestones(doc: dict, device_id: str, child: sqlite3.Row, today: date,
                     seasons: list[rp.Season]) -> dict[str, Any]:
    puberty = pc.reached_puberty(device_id, child["id"])
    found, needs = evaluate(doc, child, today, seasons, puberty)
    alerted = _alerts(device_id, child["id"])
    groups: dict[str, list] = {"due": [], "upcoming": [], "library": [], "past": []}
    for milestone, when in found:
        if not in_horizon(when, today):
            continue
        groups[when["state"]].append(
            card_payload(doc, milestone, when, alerted.get(milestone["key"])))
    groups["upcoming"].sort(key=lambda c: (c["alert_on"] or "", c["order"] or 0))
    policy = doc.get("alert_policy") or {}
    return {
        "child_id": child["id"],
        "date": today.isoformat(),
        "age": pc.child_age(child, today),
        "alert_policy": {"text": policy.get("text"),
                         "pushes": "birth_month" not in needs},
        "needs_profile": sorted(needs),
        **groups,
    }


def one_milestone(doc: dict, device_id: str, child: sqlite3.Row, key: str, today: date,
                  seasons: list[rp.Season]) -> Optional[dict[str, Any]]:
    """One card, whatever its state — for the push's deep link."""
    puberty = pc.reached_puberty(device_id, child["id"])
    found, _ = evaluate(doc, child, today, seasons, puberty)
    for milestone, when in found:
        if milestone["key"] == key:
            return card_payload(doc, milestone, when,
                                _alerts(device_id, child["id"]).get(key))
    return None
