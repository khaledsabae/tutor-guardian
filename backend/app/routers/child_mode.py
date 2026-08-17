"""Child-mode endpoints for self-reported habit tracking.

These routes accept `Authorization: Child-Bearer <token>` issued by the
parent-facing session creation endpoint. They are intentionally narrow:
* view today's merged habit list for the linked child
* submit a single status for one habit today (no edit/delete)
"""
import sqlite3
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.config.guardrails_loader import ChildSurfacePolicy, load_child_surface_policy
from app.db.init_db import get_conn
from app.models.value_tracking import (
    ChildHabitDayOut,
    ChildHabitEventCreate,
    HabitEventCreate,
    HabitEventOut,
    TodayHabitItem,
)
from app.routers.value_tracking import (
    _build_today_habits,
    _event_row_to_model,
    _load_active_templates,
    _load_today_events,
    _persist_event,
    _verify_child_ownership,
)
from app.core.taxonomy import map_profile_age_to_band
from app.services import child_license, license_alert
from app.services import child_budget, child_missions, family_agreement
from app.services import child_token as child_token_service

router = APIRouter(tags=["child-mode"])

# Maximum acceptable drift between device_timestamp and server UTC time.
_MAX_CLOCK_SKEW = timedelta(minutes=15)


def _get_child_id(request: Request) -> int:
    child_id = getattr(request.state, "child_id", None)
    if not isinstance(child_id, int):
        raise HTTPException(status_code=401, detail="وضع الطفل غير مفعل.")
    return child_id


def _require_device_id(request: Request) -> str:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    return device_id


def _validate_device_timestamp(device_timestamp: str | None) -> str:
    """Validate that the device timestamp is within acceptable server drift.

    Prevents clock-skew cheating (e.g. a child manually advancing device time
    to log future habits). Falls back to server UTC time when not provided.
    """
    if device_timestamp is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        # FastAPI/Pydantic already ensured an ISO-formatted string, but
        # re-parsing defensively guards against malformed manual input.
        parsed = datetime.fromisoformat(device_timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="صيغة الطابع الزمني للجهاز غير صالحة.",
        )
    server_now = datetime.now(timezone.utc)
    if abs(parsed - server_now) > _MAX_CLOCK_SKEW:
        raise HTTPException(
            status_code=422,
            detail="وقت الجهاز منحرف عن الخادم. تأكد من ضبط الساعة التلقائي.",
        )
    return device_timestamp


@router.post("/value-tracking/child-web-claims", response_model=dict)
def create_child_web_claim(request: Request, child_id: int = Query(..., ge=1)):
    """Parent endpoint: create a one-time QR claim code for web teen access.

    Returns a short URL-safe claim code and the full teen-facing URL. The
    browser must open that URL and redeem the code via POST within 2 minutes.
    The actual HMAC token is never exposed in the URL.
    """
    device_id = _require_device_id(request)
    _verify_child_ownership(device_id, child_id)
    ttl = child_token_service.web_ttl_seconds()
    code = child_token_service.create_claim_code(device_id, child_id, ttl_seconds=ttl)
    # Build the public claim URL.  Use a configurable host if available.
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.hostname)
    port = request.headers.get("x-forwarded-port") or (
        str(request.url.port) if request.url.port and request.url.port not in {80, 443} else ""
    )
    base = f"{scheme}://{host}" + (f":{port}" if port else "")
    claim_url = f"{base}/child-mode/web/?claim={code}"
    return {
        "claim_code": code,
        "claim_url": claim_url,
        "expires_in_seconds": 120,
        "child_id": child_id,
    }


def _policy(request: Request) -> ChildSurfacePolicy:
    """The child-surface policy, from app state or loaded on the spot.

    The fallback is not a default: load_child_surface_policy raises on a bad
    file, so a router without startup state either gets a valid policy or an
    error. It exists so tests can mount this router without a lifespan.
    """
    policy = getattr(request.app.state, "child_surface_policy", None)
    return policy or load_child_surface_policy()


def _refusal(result: dict) -> HTTPException:
    """Turn a budget refusal into a 403 the parent app can render.

    The message ships as a key plus an Arabic fallback: the key is what a
    localized client should render (27% of users are not reading Arabic), the
    fallback is what an older build will show rather than a blank dialog.
    """
    reason = result.get("reason", "denied")
    body = {
        "error": reason,
        "band": result.get("band"),
        "message_key": result.get("parent_message_key") or f"child_gate.{reason}",
    }
    if result.get("parent_message_ar"):
        body["message_ar"] = result["parent_message_ar"]
    elif reason in ("budget_exhausted", "audio_budget_exhausted"):
        body["message_ar"] = "خلصت مدة النهارده. نكمل بكرة إن شاء الله 🌙"
        body["resets_at"] = result.get("resets_at")
    return HTTPException(status_code=403, detail=body)


@router.post("/value-tracking/child-sessions", response_model=dict)
def create_child_session(
    request: Request,
    child_id: int = Query(..., ge=1),
    # Both default for backward compatibility: builds already on Play call
    # this with only child_id, and the shipped child mode is the habit
    # checklist. Defaulting the offset to UTC shifts an old client's day
    # boundary by its real offset; the rolling-24h floor in child_budget keeps
    # that from being worth anything.
    surface: str = Query("habit"),
    tz_offset_minutes: int = Query(0),
):
    """Parent endpoint: issue a short-lived child-mode token for a child.

    Requires normal parent Bearer auth. The token is now bound to a screen
    session: the age gate decides whether one may exist at all, and the TTL is
    clamped to what is left of the budget. A token that outlives its budget is
    a bypass waiting to be found, so it does not.
    """
    device_id = _require_device_id(request)
    _verify_child_ownership(device_id, child_id)

    # Kill switch: hand back the pre-sprint token and open no session. The
    # middleware skips its session check under the same flag, so the two stay
    # consistent — a half-disabled gate would lock every child out.
    if not child_budget.child_surface_enabled():
        token = child_token_service.issue_child_token(device_id, child_id, ttl_seconds=1800)
        return {
            "token": token,
            "expires_at": child_token_service.child_token_expiry_iso(token),
            "child_id": child_id,
            "child_surface_enabled": False,
        }

    policy = _policy(request)
    session = child_budget.open_session(device_id, child_id, surface,
                                        tz_offset_minutes, policy)
    if not session["ok"]:
        raise _refusal(session)

    ttl = min(1800, session["allowed_seconds"])
    token = child_token_service.issue_child_token(device_id, child_id, ttl_seconds=ttl)
    expires_at = child_token_service.child_token_expiry_iso(token)
    return {
        "token": token,
        "expires_at": expires_at,
        "child_id": child_id,
        # Travels with the session so the app needs no second round trip to
        # know whether to open the agreement instead of the habit screen.
        "agreement_awaits_child": family_agreement.awaits_child_signature(
            device_id, child_id),
        "session_id": session["session_id"],
        "surface": session["surface"],
        "allowed_seconds": session["allowed_seconds"],
        "remaining_today": session["remaining_today"],
        "remaining_audio_today": session["remaining_audio_today"],
        "requires_parent_present": session["requires_parent_present"],
        "heartbeat_interval_seconds": session["heartbeat_interval_seconds"],
        "exit_ritual_seconds": session["exit_ritual_seconds"],
    }


@router.post("/value-tracking/child-mode/heartbeat", response_model=dict)
def child_heartbeat(request: Request, session_id: int = Query(..., ge=1)):
    """Bill the time since the last beat and report what is left.

    A 403 here is the budget ending, which the child's app renders as a quiet
    closing screen — not an error.
    """
    child_id = _get_child_id(request)
    policy = _policy(request)

    session = child_budget.session_for(session_id)
    if session is None or session["child_id"] != child_id:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"})

    result = child_budget.heartbeat(session_id, policy)
    if not result["ok"]:
        raise _refusal(result)
    return result


@router.post("/value-tracking/child-mode/session-end", response_model=dict)
def child_session_end(
    request: Request,
    session_id: int = Query(..., ge=1),
    reason: str = Query("completed"),
):
    """Close a session from the child's side, after the exit ritual."""
    child_id = _get_child_id(request)
    session = child_budget.session_for(session_id)
    if session is None or session["child_id"] != child_id:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"})

    allowed = {"completed", "parent_exit", "timeout"}
    child_budget.close_session(session_id, reason if reason in allowed else "completed",
                               _policy(request))
    return {"ok": True}


@router.get("/value-tracking/child-mode/today", response_model=ChildHabitDayOut)
def child_get_today(request: Request):
    """Child endpoint: fetch today's merged habit list (read-only)."""
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)

    conn = get_conn()
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        events = _load_today_events(conn, device_id, child_id, today)
        templates = _load_active_templates(conn, device_id, child_id)
        age_group = conn.execute(
            "SELECT age_group FROM child_profiles WHERE id = ?", (child_id,)
        ).fetchone()["age_group"]
        habits = _build_today_habits(age_group, templates, events)
        return {
            "child_id": child_id,
            "date": today,
            "habits": habits,
            "events": [_event_row_to_model(r) for r in events],
        }
    finally:
        conn.close()


@router.post("/value-tracking/child-mode/events", response_model=HabitEventOut)
def child_record_event(request: Request, body: ChildHabitEventCreate):
    """Child endpoint: submit today's status for one habit (submit-only)."""
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)

    # Validate that this is one of the habits available to the child today.
    today_data = child_get_today(request)
    available_names = {h.habit_name for h in today_data["habits"]}
    if body.habit_name not in available_names:
        raise HTTPException(
            status_code=400,
            detail="العادة غير متاحة لهذا الطفل اليوم.",
        )

    # Submit-only: if an event already exists today, reject the second attempt.
    today = datetime.now(timezone.utc).date().isoformat()
    conn = get_conn()
    try:
        existing = _load_today_events(conn, device_id, child_id, today)
        already = [e for e in existing if e["habit_name"] == body.habit_name]
        if already:
            raise HTTPException(
                status_code=409,
                detail="تم تسجيل هذه العادة اليوم بالفعل. لا يمكن تعديلها من وضع الطفل.",
            )
        return _persist_event(
            conn,
            device_id,
            child_id,
            today,
            body,
            submitted_by="child",
            device_timestamp=_validate_device_timestamp(body.device_timestamp),
        )
    finally:
        conn.close()


# ── The agreement, from the child's side ───────────────────────────────────

@router.get("/value-tracking/child-mode/agreement", response_model=dict)
def child_read_agreement(request: Request):
    """What the child is being asked to agree to.

    A separate endpoint under the child prefix rather than opening
    /api/children to a child token: the parent routes read and write a
    family's whole profile set, and a child surface has no business there.
    """
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)
    agreement = family_agreement.get_current(device_id, child_id)
    if agreement is None:
        return {"agreement": None}
    return {"agreement": agreement}


@router.post("/value-tracking/child-mode/agreement/acknowledge", response_model=dict)
def child_acknowledge_clause(request: Request, clause_id: int = Query(..., ge=1)):
    """The child says they understood one clause. One at a time, on purpose."""
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)
    result = family_agreement.acknowledge_clause(device_id, child_id, clause_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail={"error": result["reason"]})
    return result


@router.post("/value-tracking/child-mode/agreement/sign", response_model=dict)
def child_sign_agreement(request: Request):
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)
    result = family_agreement.sign(device_id, child_id, "child")
    if not result["ok"]:
        raise HTTPException(status_code=409, detail={
            "error": result["reason"],
            "remaining": result.get("remaining"),
            "message_key": f"agreement.{result['reason']}",
        })
    return result


# ── The daily mission ──────────────────────────────────────────────────────

@router.get("/value-tracking/child-mode/mission/today", response_model=dict)
def child_mission_today(request: Request, tz_offset_minutes: int = Query(0)):
    """One card. The same card all day, however often it is opened."""
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT age_group FROM child_profiles WHERE id = ? AND device_id = ?",
            (child_id, device_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "child_not_found"})

    band = map_profile_age_to_band(row["age_group"])
    local_date = child_budget.local_date_for(
        datetime.now(timezone.utc), tz_offset_minutes
    )
    card = child_missions.today_mission(device_id, child_id, band, local_date)
    return {"mission": card}


@router.post("/value-tracking/child-mode/mission/claim", response_model=dict)
def child_mission_claim(request: Request, mission_id: int = Query(..., ge=1)):
    """«خلّصتها» — recorded and done. The child does not wait for a parent.

    Deliberately not a request for approval: a child standing at a screen
    waiting to be confirmed has been given a reason to stay at the screen.
    """
    child_id = _get_child_id(request)
    result = child_missions.claim(child_id, mission_id)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail={"error": result["reason"]})
    return result


def _band_for(device_id: str, child_id: int) -> str:
    """The child's policy band, or the default when the profile is gone.

    Every licence endpoint needs this: the scenario bank is written per band,
    and serving a fourteen-year-old situations pitched at a ten-year-old
    teaches them the feature is for children. Kept as one helper so a new
    endpoint cannot quietly fall back to the default.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT age_group FROM child_profiles WHERE id = ? AND device_id = ?",
            (child_id, device_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        # Not a default. A token whose child no longer belongs to this device
        # is not a ten-year-old — it is a token that should not be serving
        # content at all. Falling back quietly meant a fourteen-year-old whose
        # profile had been deleted got the ten-year-old's bank and had answers
        # recorded against it.
        raise HTTPException(status_code=404, detail={"error": "child_not_found"})
    return map_profile_age_to_band(row["age_group"])


# ── Internet licence (Sprint 3, level 1) ───────────────────────────────────
#
# The child half is two endpoints and neither of them tells the child whether
# they were right. That is the whole design: say it back and the exercise
# becomes a puzzle to brute-force until the green light appears, which
# measures persistence rather than judgement.


@router.get("/value-tracking/child-mode/license/today", response_model=dict)
def child_license_today(request: Request):
    """The next situation to think about, or None when this level is done."""
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)
    band = _band_for(device_id, child_id)

    level_key = child_license.current_level(child_id)
    child_license.ensure_level(device_id, child_id, level_key)
    scenario = child_license.next_scenario(child_id, level_key, age_band=band)

    # The child sees the situation and the choices. `outcome`, `alerts_parent`
    # and `talking_point_ar` are the parent's half and are stripped here — a
    # payload that carries the answer is an answer key.
    public = None
    if scenario is not None:
        public = {
            "key": scenario["key"],
            "situation_ar": scenario["situation_ar"],
            "choices": [
                {"key": c["key"], "text_ar": c["text_ar"]}
                for c in scenario.get("choices", [])
            ],
        }

    return {
        "level_key": level_key,
        "scenario": public,
        # `child_progress`, not `progress`: the latter counts *safe* answers,
        # so reading it before and after an answer tells the child whether
        # they were right — a verdict delivered in two requests, on a surface
        # built to withhold exactly that.
        "progress": child_license.child_progress(child_id, level_key, band),
    }


@router.post("/value-tracking/child-mode/license/answer", response_model=dict)
def child_license_answer(request: Request,
                         scenario_key: str = Query(..., min_length=2),
                         choice_key: str = Query(..., min_length=2)):
    """Record the child's choice, and alert the parent when the situation
    warrants it — including when the child answered it well.

    A child who chose correctly in a grooming scenario may be living through
    one. The plan is explicit that the alert is about meeting the situation,
    not about failing it.
    """
    child_id = _get_child_id(request)
    device_id = _require_device_id(request)
    band = _band_for(device_id, child_id)
    level_key = child_license.current_level(child_id)

    result = child_license.answer(
        device_id, child_id, level_key, scenario_key, choice_key, age_band=band
    )
    if not result["ok"]:
        raise HTTPException(status_code=404, detail={"error": result["reason"]})

    if result["alerts_parent"]:
        # Fire and forget: a failed push must never block a child's screen,
        # and the answer is already recorded either way.
        try:
            sent = license_alert.send_alert(
                device_id,
                talking_point=result["talking_point_ar"],
                critical=result["outcome"] == "critical",
            )
            if sent.get("sent"):
                child_license.mark_alerted(
                    child_id, scenario_key, result["attempt"], level_key)
        except Exception:  # noqa: BLE001 — never surface a push failure here
            pass

    child_license.refresh_status(device_id, child_id, level_key, band)

    # Nothing about right or wrong. A test reads this body to keep it so.
    return {"ok": True, "next": True}
