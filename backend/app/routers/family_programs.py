"""Family programs — Ramadan, the Prayer Journey and the proactive milestones.

All additive (schema v34); contract in MOBILE_API.md §11. Parent endpoints
need the Bearer token (AuthMiddleware: /api/programs and /api/children are
protected prefixes); the two child-mode endpoints need the Child-Bearer token
and a live screen session, like every other /api/value-tracking/child-mode/
route.

Every endpoint that depends on the day takes `tz_offset_minutes` (the
family's UTC offset, minutes, −720…840) and remembers it for the device —
the milestone push sends at the family's 20:00 and needs it. `lang=en`
returns the English content (Arabic otherwise, and as the fallback).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services import milestones as ms
from app.services import prayer_journey as pj
from app.services import programs_common as pc
from app.services import ramadan_program as rp

router = APIRouter(tags=["family-programs"])


# ── Plumbing ───────────────────────────────────────────────────────────────

def _device(request: Request) -> str:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id


def _today(tz_offset_minutes: Optional[int], as_of: Optional[str]) -> date:
    try:
        pc.validate_tz_offset(tz_offset_minutes)
        override = pc.parse_as_of(as_of)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_date_or_offset",
                                                     "message": str(exc)}) from exc
    if override is not None:
        if not pc.as_of_enabled():
            raise HTTPException(status_code=403, detail={"error": "as_of_disabled"})
        return override
    return pc.local_today(tz_offset_minutes)


def _context(request: Request, tz_offset_minutes: Optional[int], lang: Optional[str],
             as_of: Optional[str]) -> tuple[str, date]:
    device_id = _device(request)
    today = _today(tz_offset_minutes, as_of)
    pc.remember_device(device_id, tz_offset_minutes, lang)
    return device_id, today


def _child(device_id: str, child_id: int):
    try:
        return pc.owned_child(device_id, child_id)
    except pc.ChildNotFound:
        raise HTTPException(status_code=404, detail={"error": "child_not_found"}) from None


def _program(name: str, lang: Optional[str]) -> dict:
    try:
        return pc.load_program(name, lang)
    except pc.ProgramUnavailable:
        raise HTTPException(status_code=503, detail={"error": "program_unavailable",
                                                     "program": name}) from None


def _program_or_none(name: str, lang: Optional[str]) -> Optional[dict]:
    """For responses that combine programs: one unreadable file hides its own
    section, not its neighbours'."""
    try:
        return pc.load_program(name, lang)
    except pc.ProgramUnavailable:
        return None


def _refuse(exc: rp.RamadanError | pj.JourneyError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail={"error": exc.code, **exc.extra})


def _where(device_id: str, today: date, doc: dict) -> tuple[dict, dict[str, Any]]:
    settings = pc.device_settings(device_id)
    return settings, rp.locate(today, rp.family_seasons(settings, doc))


def _season_dict(where: dict[str, Any]) -> Optional[dict]:
    season = where.get("season")
    return season.as_dict() if season is not None else None


# ── The catalogue ──────────────────────────────────────────────────────────

@router.get("/programs", summary="Which family programs apply to each child today")
def programs_overview(request: Request, lang: Optional[str] = Query(None),
                      tz_offset_minutes: Optional[int] = Query(None),
                      as_of: Optional[str] = Query(None)):
    """Each program is loaded on its own: a missing file nulls that program's
    sections and names it in `unavailable`; the others are served as usual."""
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    ramadan = _program_or_none(rp.PROGRAM, lang)
    prayer = _program_or_none(pj.PROGRAM, lang)
    miles = _program_or_none(ms.PROGRAM, lang)
    settings = pc.device_settings(device_id)
    seasons = rp.family_seasons(settings, ramadan) if ramadan else []
    where = rp.locate(today, seasons) if ramadan else None
    children = []
    for child in pc.device_children(device_id):
        age = pc.child_age(child, today)
        entry: dict[str, Any] = {"child_id": child["id"], "age": age,
                                 "ramadan": None, "prayer_journey": None, "milestones": None}
        if ramadan:
            entry["ramadan"] = {"variant_band": rp.variant_band(ramadan, age["band"])}
        if prayer:
            row = pj.active(device_id, child["id"])
            adv = pj.advancement(prayer, row, today)
            entry["prayer_journey"] = {
                "eligible_track": pj.eligible_track(prayer, age),
                "enrolled": row is not None,
                "track": row["track"] if row else None,
                "stage": row["stage"] if row else None,
                "advance_suggested": bool(adv and adv["advance_suggested"]),
                "can_graduate": bool(adv and adv["can_graduate"]),
                "pending_confirmations": pj.pending_count(device_id, child["id"]),
            }
        if miles:
            found, needs = ms.evaluate(miles, child, today, seasons,
                                       pc.reached_puberty(device_id, child["id"]))
            entry["milestones"] = {
                "due": sum(1 for _, w in found if w["state"] == "due"),
                "needs_profile": sorted(needs),
            }
        children.append(entry)
    return {
        "date": today.isoformat(),
        "tz_offset_minutes": tz_offset_minutes,
        "server_features": sorted(pc.server_features(request.app)),
        "unavailable": [name for name, doc in ((rp.PROGRAM, ramadan), (pj.PROGRAM, prayer),
                                               (ms.PROGRAM, miles)) if doc is None],
        "ramadan": None if where is None else {
            "state": where["state"],
            "season": _season_dict(where),
            "day": where.get("day"),
            "days_until_start": where.get("days_until_start"),
            "after_week": where.get("week"),
            "recap_available": bool(where.get("season") is not None
                                    and today >= where["season"].eid),
        },
        "children": children,
    }


# ── Ramadan ────────────────────────────────────────────────────────────────

@router.get("/children/{child_id}/ramadan/today",
            summary="The Ramadan program for this child on the family's date")
def ramadan_today(child_id: int, request: Request, lang: Optional[str] = Query(None),
                  tz_offset_minutes: Optional[int] = Query(None),
                  features: Optional[str] = Query(None),
                  as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(rp.PROGRAM, lang)
    _, where = _where(device_id, today, doc)
    age = pc.child_age(child, today)
    band_key = rp.variant_band(doc, age["band"])
    state = where["state"]
    out: dict[str, Any] = {
        "program": rp.PROGRAM,
        "child_id": child_id,
        "date": today.isoformat(),
        "tz_offset_minutes": tz_offset_minutes,
        "state": state,
        "season": _season_dict(where),
        "title": doc.get("title"),
        "subtitle": doc.get("subtitle"),
        "age": age,
        "variant_band": band_key,
        "bands_text": (doc.get("bands") or {}).get("text"),
        "days_until_start": where.get("days_until_start"),
        "day": where.get("day"),
        "after_week": where.get("week"),
        "kickoff": None, "content": None, "eid": None, "after": None,
        "marks": None, "fasting": None,
        "recap_available": bool(where.get("season") is not None
                                and today >= where["season"].eid),
    }
    if state == "upcoming":
        out["kickoff"] = rp.kickoff_payload(doc)
    elif state == "ramadan":
        out["content"] = rp.day_payload(doc, where["day"], band_key)
        out["marks"] = rp.day_marks(doc, device_id, where["season"], where["day"])
    elif state == "eid":
        out["eid"] = rp.eid_payload(doc, band_key)
    elif state == "after":
        out["after"] = rp.after_payload(doc, where["week"],
                                        pc.features_for(request.app, features))
    if state in ("upcoming", "ramadan", "eid", "after"):
        fasting = rp.fasting_state(doc, device_id, child, age, where)
        if fasting["ladder_band"] is not None:   # prenatal-1: no ladder at all
            out["fasting"] = {k: fasting[k] for k in (
                "ladder_band", "fasts", "reached_puberty", "current_step",
                "practised_today", "practised_this_week", "rest_suggested")}
    return out


@router.get("/children/{child_id}/ramadan/days/{day}",
            summary="Any day of the month for this child: a preview, or a past day to tick")
def ramadan_day(child_id: int, day: int, request: Request, lang: Optional[str] = Query(None),
                tz_offset_minutes: Optional[int] = Query(None),
                as_of: Optional[str] = Query(None)):
    """Tomorrow's challenge may need materials bought today, and yesterday's
    «تمّ» may have been forgotten. Content is readable for every day 1–30;
    `marks` are returned (and markable) only for days up to today."""
    if not 1 <= day <= 30:
        raise HTTPException(status_code=404, detail={"error": "no_such_day"})
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(rp.PROGRAM, lang)
    _, where = _where(device_id, today, doc)
    age = pc.child_age(child, today)
    season = where.get("season")
    markable = season is not None and day <= rp.markable_days(where)
    return {"child_id": child_id, "date": today.isoformat(), "state": where["state"],
            "season": _season_dict(where), "variant_band": rp.variant_band(doc, age["band"]),
            "content": rp.day_payload(doc, day, rp.variant_band(doc, age["band"])),
            "markable": markable,
            "marks": rp.day_marks(doc, device_id, season, day) if markable else None}


@router.get("/children/{child_id}/ramadan/fasting",
            summary="The child's fasting ladder, with the safety guidance")
def ramadan_fasting(child_id: int, request: Request, lang: Optional[str] = Query(None),
                    tz_offset_minutes: Optional[int] = Query(None),
                    as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(rp.PROGRAM, lang)
    _, where = _where(device_id, today, doc)
    age = pc.child_age(child, today)
    return {"child_id": child_id, "date": today.isoformat(), "state": where["state"],
            "season": _season_dict(where), "day": where.get("day"), "age": age,
            **rp.fasting_state(doc, device_id, child, age, where),
            "guidance": rp.ladder_guidance(doc)}


class FastingIn(BaseModel):
    step_key: Optional[str] = Field(default=None, max_length=40)
    reached_puberty: Optional[bool] = None


@router.put("/children/{child_id}/ramadan/fasting",
            summary="Set the child's fasting step and/or mark puberty")
def ramadan_set_fasting(child_id: int, body: FastingIn, request: Request,
                        lang: Optional[str] = Query(None),
                        tz_offset_minutes: Optional[int] = Query(None),
                        as_of: Optional[str] = Query(None)):
    if body.step_key is None and body.reached_puberty is None:
        raise HTTPException(status_code=422, detail={"error": "nothing_to_change"})
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(rp.PROGRAM, lang)
    _, where = _where(device_id, today, doc)
    age = pc.child_age(child, today)
    try:
        result = rp.set_fasting(doc, device_id, child, age, where,
                                step_key=body.step_key, puberty=body.reached_puberty)
    except rp.RamadanError as exc:
        raise _refuse(exc) from None
    return {"child_id": child_id, "climbed": result["climbed"],
            **rp.fasting_state(doc, device_id, child, age, where)}


class PracticeIn(BaseModel):
    day: Optional[int] = Field(default=None, ge=1, le=30)
    done: bool = True


@router.post("/children/{child_id}/ramadan/fasting/practice",
             summary="The child practised their fasting step today (or on a past day)")
def ramadan_practice(child_id: int, body: PracticeIn, request: Request,
                     lang: Optional[str] = Query(None),
                     tz_offset_minutes: Optional[int] = Query(None),
                     as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(rp.PROGRAM, lang)
    _, where = _where(device_id, today, doc)
    try:
        day = rp.set_practised(device_id, child, where, day=body.day, done=body.done)
    except rp.RamadanError as exc:
        raise _refuse(exc) from None
    age = pc.child_age(child, today)
    fasting = rp.fasting_state(doc, device_id, child, age, where)
    return {"child_id": child_id, "day": day, "done": body.done,
            **{k: fasting[k] for k in ("current_step", "practised_today",
                                        "practised_this_week", "rest_suggested")}}


class MarkIn(BaseModel):
    mark: str = Field(..., max_length=32)
    day: Optional[int] = Field(default=None, ge=1, le=30)
    done: bool = True
    choice_index: Optional[int] = Field(default=None, ge=0, le=20)


@router.post("/programs/ramadan/marks", summary="Tick or untick a family «تمّ» mark")
def ramadan_mark(body: MarkIn, request: Request, lang: Optional[str] = Query(None),
                 tz_offset_minutes: Optional[int] = Query(None),
                 as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    doc = _program(rp.PROGRAM, lang)
    _, where = _where(device_id, today, doc)
    try:
        day = rp.set_family_mark(doc, device_id, where, mark=body.mark, day=body.day,
                                 done=body.done, choice_index=body.choice_index)
    except rp.RamadanError as exc:
        raise _refuse(exc) from None
    return {"hijri_year": where["season"].hijri_year, "day": day,
            "marks": rp.day_marks(doc, device_id, where["season"], day)}


class SeasonSettingsIn(BaseModel):
    start_shift_days: Optional[int] = Field(default=None, ge=-1, le=1)
    month_days: Optional[int] = Field(default=None, ge=29, le=30)


@router.put("/programs/ramadan/settings",
            summary="The family's own moon sighting for this season")
def ramadan_settings(body: SeasonSettingsIn, request: Request,
                     lang: Optional[str] = Query(None),
                     tz_offset_minutes: Optional[int] = Query(None),
                     as_of: Optional[str] = Query(None)):
    sent = body.model_fields_set
    if not sent & {"start_shift_days", "month_days"}:
        raise HTTPException(status_code=422, detail={"error": "nothing_to_change"})
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    doc = _program(rp.PROGRAM, lang)
    _, where = _where(device_id, today, doc)
    season = where.get("season")
    if season is None or where["state"] == "off_season":
        raise HTTPException(status_code=409, detail={"error": "not_in_season"})
    rp.set_family_season(
        device_id, season.hijri_year,
        shift_days=body.start_shift_days if "start_shift_days" in sent else None,
        month_days=body.month_days, set_month_days="month_days" in sent,
    )
    _, where = _where(device_id, today, doc)
    return {"state": where["state"], "season": _season_dict(where), "day": where.get("day")}


@router.get("/programs/ramadan/recap", summary="«رمضان عائلتنا» — the family's card")
def ramadan_recap(request: Request, lang: Optional[str] = Query(None),
                  tz_offset_minutes: Optional[int] = Query(None),
                  hijri_year: Optional[int] = Query(None),
                  as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    doc = _program(rp.PROGRAM, lang)
    settings = pc.device_settings(device_id)
    seasons = rp.family_seasons(settings, doc)
    if hijri_year is not None:
        season = rp.season_by_year(seasons, hijri_year)
    else:
        started = [s for s in seasons if s.start <= today]
        season = started[-1] if started else (seasons[0] if seasons else None)
    if season is None:
        raise HTTPException(status_code=404, detail={"error": "no_season"})
    return rp.recap(doc, device_id, pc.lang_code(lang), season, today)


# ── The Prayer Journey ─────────────────────────────────────────────────────

@router.get("/children/{child_id}/prayer-journey",
            summary="The Prayer Journey for this child: track, stage, tasks")
def prayer_view(child_id: int, request: Request, lang: Optional[str] = Query(None),
                tz_offset_minutes: Optional[int] = Query(None),
                as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(pj.PROGRAM, lang)
    return pj.view(doc, device_id, child, pc.child_age(child, today), today)


class EnrolIn(BaseModel):
    track: Optional[str] = Field(default=None, pattern="^(preparation|journey|ownership)$")
    start_stage: Optional[int] = Field(default=None, ge=1, le=12)
    restart: bool = False


@router.post("/children/{child_id}/prayer-journey/enrol",
             summary="Start (or restart) the child on a track")
def prayer_enrol(child_id: int, body: EnrolIn, request: Request,
                 lang: Optional[str] = Query(None),
                 tz_offset_minutes: Optional[int] = Query(None),
                 as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(pj.PROGRAM, lang)
    age = pc.child_age(child, today)
    try:
        pj.enrol(doc, device_id, child, age, today, track=body.track,
                 start_stage=body.start_stage, restart=body.restart)
    except pj.JourneyError as exc:
        raise _refuse(exc) from None
    return pj.view(doc, device_id, child, age, today)


class StageIn(BaseModel):
    stage: int = Field(..., ge=1, le=12)


@router.put("/children/{child_id}/prayer-journey/stage",
            summary="Move to the next stage, or back to an earlier one")
def prayer_stage(child_id: int, body: StageIn, request: Request,
                 lang: Optional[str] = Query(None),
                 tz_offset_minutes: Optional[int] = Query(None),
                 as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(pj.PROGRAM, lang)
    try:
        pj.set_stage(doc, device_id, child, body.stage, today)
    except pj.JourneyError as exc:
        raise _refuse(exc) from None
    return pj.view(doc, device_id, child, pc.child_age(child, today), today)


@router.post("/children/{child_id}/prayer-journey/graduate",
             summary="Graduate from the Journey to «صلاتي مسؤوليتي»")
def prayer_graduate(child_id: int, request: Request, lang: Optional[str] = Query(None),
                    tz_offset_minutes: Optional[int] = Query(None),
                    as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(pj.PROGRAM, lang)
    try:
        pj.graduate(doc, device_id, child, today)
    except pj.JourneyError as exc:
        raise _refuse(exc) from None
    return pj.view(doc, device_id, child, pc.child_age(child, today), today)


@router.delete("/children/{child_id}/prayer-journey", summary="Stop the journey")
def prayer_end(child_id: int, request: Request, lang: Optional[str] = Query(None),
               tz_offset_minutes: Optional[int] = Query(None),
               as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(pj.PROGRAM, lang)
    try:
        pj.end(device_id, child, today)
    except pj.JourneyError as exc:
        raise _refuse(exc) from None
    return pj.view(doc, device_id, child, pc.child_age(child, today), today)


# ── Milestones ─────────────────────────────────────────────────────────────

@router.get("/children/{child_id}/milestones",
            summary="Due, upcoming and library milestone cards for this child")
def milestones_list(child_id: int, request: Request, lang: Optional[str] = Query(None),
                    tz_offset_minutes: Optional[int] = Query(None),
                    as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(ms.PROGRAM, lang)
    # The Ramadan file only times the first-fast card; without it, no season.
    seasons = rp.seasons_or_empty(pc.device_settings(device_id))
    return ms.child_milestones(doc, device_id, child, today, seasons)


@router.get("/children/{child_id}/milestones/{key}",
            summary="One milestone card (the push's deep link)")
def milestone_one(child_id: int, key: str, request: Request,
                  lang: Optional[str] = Query(None),
                  tz_offset_minutes: Optional[int] = Query(None),
                  as_of: Optional[str] = Query(None)):
    device_id, today = _context(request, tz_offset_minutes, lang, as_of)
    child = _child(device_id, child_id)
    doc = _program(ms.PROGRAM, lang)
    seasons = rp.seasons_or_empty(pc.device_settings(device_id))
    card = ms.one_milestone(doc, device_id, child, key, today, seasons)
    if card is None:
        raise HTTPException(status_code=404, detail={"error": "milestone_not_found"})
    return {"child_id": child_id, "date": today.isoformat(), "milestone": card}


# ── Child mode: the child's prayer tasks ───────────────────────────────────

def _child_mode(request: Request) -> tuple[str, int]:
    child_id = getattr(request.state, "child_id", None)
    device_id = getattr(request.state, "device_id", None)
    if not isinstance(child_id, int) or not device_id:
        raise HTTPException(status_code=401, detail="وضع الطفل غير مفعل.")
    _child(device_id, child_id)
    return device_id, child_id


@router.get("/value-tracking/child-mode/prayer/today",
            summary="Child mode: today's prayer tasks")
def child_prayer_today(request: Request, lang: Optional[str] = Query(None),
                       tz_offset_minutes: Optional[int] = Query(None)):
    device_id, child_id = _child_mode(request)
    today = _today(tz_offset_minutes, None)
    pc.remember_device(device_id, tz_offset_minutes, None)
    doc = _program_or_none(pj.PROGRAM, lang)
    if doc is None:
        # The journey is hidden, not an error on the child's screen.
        return {"date": today.isoformat(), "available": False, "enrolled": False,
                "track": None, "tasks": []}
    return pj.child_today(doc, device_id, child_id, today)


@router.post("/value-tracking/child-mode/prayer/claim",
             summary="Child mode: «صلّيتها» — record a prayer task")
def child_prayer_claim(request: Request, task_id: str = Query(..., min_length=3, max_length=64),
                       lang: Optional[str] = Query(None),
                       tz_offset_minutes: Optional[int] = Query(None)):
    device_id, child_id = _child_mode(request)
    today = _today(tz_offset_minutes, None)
    pc.remember_device(device_id, tz_offset_minutes, None)
    doc = _program(pj.PROGRAM, lang)
    try:
        return pj.claim(doc, device_id, child_id, task_id, today)
    except pj.JourneyError as exc:
        raise _refuse(exc) from None
