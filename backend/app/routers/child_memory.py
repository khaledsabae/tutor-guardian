"""Child memory, follow-ups and the weekly plan — «المربّي يعرف ابنك» (schema v30).

Every route is under /api/children (Bearer auth via AuthMiddleware) and is
scoped to the caller's device: a child, fact or follow-up of another device
answers 404, exactly like a missing one (same rule as routers/children.py).

The contract the app builds against is MOBILE_API.md §«Child memory». Errors
the app is expected to branch on carry a stable `code`:
    {"detail": {"code": "<code>", "message": "<Arabic message>"}}
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.proof import request_access, require_device_proof
from app.core.times import iso_z
from app.db.init_db import get_conn
from app.routers.children import _load_owned_child, _require_device_id
from app.services import child_memory as cm
from app.services import weekly_plan

router = APIRouter()


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


_FACT_ERRORS = {
    "category": "التصنيف غير صالح.",
    "fact": "النص فارغ أو يحتوي على رابط أو رقم تواصل.",
    "fact_too_long": f"النص أطول من {cm.MAX_FACT_CHARS} حرفًا.",
    "status": "الحالة المسموحة: active أو rejected.",
    "sensitive": "هذه المعلومة مما لا يحفظه المربّي (أدوية أو أمور حساسة).",
    "outcome": "النتيجة المسموحة: worked أو partly أو didnt_work أو didnt_try.",
}


def _fact_error(exc: cm.FactValidationError) -> HTTPException:
    code = str(exc) or "fact"
    return _err(422, code, _FACT_ERRORS.get(code, "قيمة غير صالحة."))


def _memory_off() -> HTTPException:
    return _err(409, "memory_off",
                "ذاكرة المربّي متوقفة، فلا يُضاف إليها شيء. فعّلها أولًا ثم أضف المعلومة.")


def _owned_child(request: Request, child_id: int) -> str:
    device_id = _require_device_id(request)
    conn = get_conn()
    try:
        _load_owned_child(conn, child_id, device_id)
    finally:
        conn.close()
    return device_id


# ── Settings (device-level; registered before /children/{child_id}/…) ────


class MemorySettingsIn(BaseModel):
    enabled: bool


def _settings(request: Request, device_id: str) -> dict:
    acc = request_access(request)
    return {
        "enabled": cm.memory_enabled(device_id),
        # Whether the server learns from THIS session's questions: the parent's
        # switch, a build with the memory screen (CHILD_MEMORY_MIN_BUILD), and a
        # session proven to hold the phone (§9.0).
        "collecting": cm.collection_allowed(device_id, proven=acc.ok),
        # Whether this session may read, change or erase memory right now. When
        # false: if `cooldown_until` is set, say when it opens (§9.0.1);
        # otherwise run the device-proof challenge first.
        "proven": acc.ok,
        "cooldown_until": iso_z(acc.available_at) if acc.reason == "cooldown" else None,
    }


@router.get("/children/memory/settings",
            summary="Is child memory on for this device? (no proof needed)")
def get_memory_settings(request: Request):
    """Two booleans and the proof state — nothing remembered is in it, so it
    answers without a proof: the app needs it to know whether to ask for one."""
    return _settings(request, _require_device_id(request))


@router.put("/children/memory/settings",
            summary="Turn child memory on or off for this device")
def put_memory_settings(body: MemorySettingsIn, request: Request):
    """Off pauses everything: nothing new is learned, no follow-up is opened
    or asked (due → []), an answer to one is not kept, a parent cannot add a
    fact, and remembered facts stop reaching the assistant. Nothing is
    deleted — that is DELETE /api/children/{id}/memory or DELETE
    /api/privacy/memory.

    Switching OFF never needs a proof: stopping must always be possible.
    Switching ON does (§9.0)."""
    device_id = _require_device_id(request)
    if body.enabled:
        require_device_proof(request)
    cm.set_memory_enabled(device_id, body.enabled)
    return _settings(request, device_id)


# ── Follow-ups (device-level routes first) ────────────────────────────────


class FollowupAnswerIn(BaseModel):
    outcome: Literal["worked", "partly", "didnt_work", "didnt_try"]
    note: Optional[str] = Field(default=None, max_length=cm.MAX_NOTE_CHARS)


@router.get("/children/followups/due",
            summary="Follow-ups whose time has come, across all children",
            dependencies=[Depends(require_device_proof)])
def followups_due(request: Request, limit: int = Query(10, ge=1, le=20),
                  tz_offset_minutes: Optional[int] = Query(None)):
    """While the parent's memory switch is off the follow-up loop is paused:
    no items, and `memory_enabled: false` says why (PR #36 review). Nothing is
    closed or deleted — switched back on, what is still due comes back."""
    device_id = _require_device_id(request)
    # Where the follow-up push learns the family's night (quiet hours).
    cm.record_tz_offset(device_id, tz_offset_minutes)
    enabled = cm.memory_enabled(device_id)
    return {"followups": cm.due_followups(device_id, limit=limit) if enabled else [],
            "memory_enabled": enabled}


@router.get("/children/followups/{followup_id}",
            summary="One follow-up — what the /followup/{id} deep link opens",
            dependencies=[Depends(require_device_proof)])
def get_followup(followup_id: int, request: Request):
    """Any status: a push can be tapped after the follow-up was answered on
    another device or expired, and the screen should say so, not 404.
    `memory_enabled: false` — memory is off, so an answer would not be kept:
    show that instead of the four answer buttons."""
    device_id = _require_device_id(request)
    fu = cm.get_followup(device_id, followup_id)
    if fu is None:
        raise _err(404, "followup_not_found", "متابعة غير موجودة.")
    return {"followup": fu, "memory_enabled": cm.memory_enabled(device_id)}


@router.post("/children/followups/{followup_id}/answer",
             summary="Did the advice work? Records it as an outcome fact",
            dependencies=[Depends(require_device_proof)])
def answer_followup(followup_id: int, body: FollowupAnswerIn, request: Request):
    """While memory is off nothing is kept: 200 with `remembered: false`,
    `fact: null`, and the follow-up unchanged (still pending)."""
    device_id = _require_device_id(request)
    try:
        result = cm.answer_followup(device_id, followup_id, body.outcome, body.note)
    except cm.FollowupStateError as exc:
        raise _err(409, "followup_closed",
                   f"هذه المتابعة مغلقة ({exc}).") from exc
    except cm.FactValidationError as exc:
        raise _fact_error(exc) from exc
    if result is None:
        raise _err(404, "followup_not_found", "متابعة غير موجودة.")
    return result


@router.post("/children/followups/{followup_id}/dismiss",
             summary="Stop asking about this follow-up",
            dependencies=[Depends(require_device_proof)])
def dismiss_followup(followup_id: int, request: Request):
    device_id = _require_device_id(request)
    try:
        result = cm.dismiss_followup(device_id, followup_id)
    except cm.FollowupStateError as exc:
        raise _err(409, "followup_closed", f"هذه المتابعة مغلقة ({exc}).") from exc
    if result is None:
        raise _err(404, "followup_not_found", "متابعة غير موجودة.")
    return {"followup": result}


@router.get("/children/{child_id}/followups",
            summary="A child's follow-ups (pending by default)",
            dependencies=[Depends(require_device_proof)])
def child_followups(
    child_id: int, request: Request,
    status: Literal["pending", "answered", "dismissed", "expired", "all"] = "pending",
):
    device_id = _owned_child(request, child_id)
    return {"child_id": child_id,
            "followups": cm.list_followups(device_id, child_id, status)}


class PromiseIn(BaseModel):
    """«متى ستجرّبها مع …؟» — the lesson's one step and the slot picked."""
    strategy: str = Field(min_length=1, max_length=400)
    when: Literal["tonight", "tomorrow", "week"]
    topic: Literal["prayer", "anger", "sleep", "study", "screens", "fear",
                   "siblings", "eating", "lying", "other"] = "other"


_PROMISE_REFUSED = {
    "followup_exists": "هناك سؤال متابعة مفتوح عن هذا الأمر بالفعل.",
    "followups_full": "لديك ثلاث متابعات مفتوحة لهذا الطفل؛ أجب عن إحداها أولًا.",
}


@router.post("/children/{child_id}/followups", status_code=201,
             summary="A lesson promise becomes a follow-up (source='lesson')",
             dependencies=[Depends(require_device_proof)])
def open_promise(child_id: int, body: PromiseIn, request: Request):
    """Same queue, limits and memory switch as the chat follow-ups.
    `409 followup_exists` / `409 followups_full` are not errors for the app:
    the promise is still kept on the device and the parent is not told off."""
    device_id = _owned_child(request, child_id)
    lang = "en" if (request.headers.get("accept-language") or "")[:2] == "en" else "ar"
    try:
        fu = cm.open_promise_followup(device_id, child_id, body.strategy,
                                      when=body.when, topic=body.topic, lang=lang)
    except cm.FactValidationError as exc:
        raise _err(422, "strategy",
                   "الخطوة فارغة أو طويلة أو مما لا يحفظه المربّي.") from exc
    except cm.MemoryOffError as exc:
        raise _memory_off() from exc
    except cm.FollowupRefused as exc:
        code = str(exc)
        raise _err(409, code, _PROMISE_REFUSED.get(code, "لم تُفتح المتابعة.")) from exc
    return {"followup": fu}


# ── Facts ─────────────────────────────────────────────────────────────────


class FactIn(BaseModel):
    category: Literal[
        "temperament", "challenge", "goal", "tried_strategy", "outcome",
        "health_note", "school", "worship", "other",
    ]
    fact: str = Field(min_length=1, max_length=400)


class FactPatch(BaseModel):
    category: Optional[Literal[
        "temperament", "challenge", "goal", "tried_strategy", "outcome",
        "health_note", "school", "worship", "other",
    ]] = None
    fact: Optional[str] = Field(default=None, min_length=1, max_length=400)
    status: Optional[Literal["active", "rejected"]] = None


@router.get("/children/{child_id}/memory",
            summary="What the assistant remembers about this child",
            dependencies=[Depends(require_device_proof)])
def list_memory(
    child_id: int, request: Request,
    status: Literal["active", "pending", "rejected", "all"] = "all",
):
    device_id = _owned_child(request, child_id)
    return {
        "child_id": child_id,
        "facts": cm.list_facts(device_id, child_id, status),
        "settings": _settings(request, device_id),
        "limits": {"max_fact_chars": cm.MAX_FACT_CHARS,
                   "max_facts": cm.MAX_FACTS_PER_CHILD},
    }


@router.post("/children/{child_id}/memory", status_code=201,
             summary="Add a fact the parent typed",
            dependencies=[Depends(require_device_proof)])
def add_memory(child_id: int, body: FactIn, request: Request):
    """`409 memory_off` while the parent's switch is off: nothing new goes in
    (PR #36 review). Edit, confirm, reject and delete still work while off."""
    device_id = _owned_child(request, child_id)
    try:
        return cm.add_manual_fact(device_id, child_id, body.category, body.fact)
    except cm.FactValidationError as exc:
        raise _fact_error(exc) from exc
    except cm.MemoryOffError as exc:
        raise _memory_off() from exc


@router.patch("/children/{child_id}/memory/{fact_id}",
              summary="Edit, confirm (active) or reject a fact",
              dependencies=[Depends(require_device_proof)])
def patch_memory(child_id: int, fact_id: int, body: FactPatch, request: Request):
    device_id = _owned_child(request, child_id)
    if body.fact is None and body.category is None and body.status is None:
        raise _err(422, "empty_patch", "لا يوجد ما يُعدَّل.")
    try:
        fact = cm.update_fact(device_id, child_id, fact_id, fact=body.fact,
                              category=body.category, status=body.status)
    except cm.FactValidationError as exc:
        raise _fact_error(exc) from exc
    if fact is None:
        raise _err(404, "fact_not_found", "معلومة غير موجودة.")
    return fact


@router.delete("/children/{child_id}/memory/{fact_id}",
               summary="Forget one fact",
            dependencies=[Depends(require_device_proof)])
def delete_memory_fact(child_id: int, fact_id: int, request: Request):
    device_id = _owned_child(request, child_id)
    if not cm.delete_fact(device_id, child_id, fact_id):
        raise _err(404, "fact_not_found", "معلومة غير موجودة.")
    return {"deleted": True, "fact_id": fact_id}


@router.delete("/children/{child_id}/memory",
               summary="Forget everything about this child",
            dependencies=[Depends(require_device_proof)])
def delete_child_memory(child_id: int, request: Request):
    """Facts, follow-ups, cached weekly plans and their marks for this child.
    The child profile itself is untouched (that is DELETE /api/children/{id})."""
    device_id = _owned_child(request, child_id)
    counts = cm.delete_child_memory(device_id, child_id)
    return {"child_id": child_id, "deleted": counts}


# ── Weekly plan ───────────────────────────────────────────────────────────


@router.get("/children/{child_id}/weekly-plan",
            summary="This week's plan for the child (built once per ISO week)")
def get_weekly_plan(child_id: int, request: Request,
                    lang: Optional[str] = Query(None),
                    tz_offset_minutes: Optional[int] = Query(None)):
    device_id = _owned_child(request, child_id)
    lang = lang or request.headers.get("accept-language")
    confirmed = request_access(request).ok
    # Recorded only when sent (a call without it must not reset the family's
    # clock to UTC — PR #26 review F7), and only from a session confirmed to
    # hold the phone: the follow-up push and the security notice read it
    # (PR #26 final review).
    if confirmed:
        cm.record_tz_offset(device_id, tz_offset_minutes)
    return weekly_plan.get_weekly_plan(
        device_id, child_id, lang=lang, tz_offset_minutes=tz_offset_minutes,
        personal=cm.memory_in_use(device_id, proven=confirmed),
    )


# ── Weekly plan marks (نور والقناديل, Phase 3) ─────────────────────────────


class PlanMarkIn(BaseModel):
    week_start: str      # the plan's week_start (a Monday), YYYY-MM-DD
    item_key: str        # an `actions[].key` or the `worship.key` of the plan


def _plan_mark(request: Request, child_id: int, body: PlanMarkIn) -> tuple[str, date, str]:
    """Owner first (another device's child is a 404, like every child route),
    then the body: a recent Monday, and a step that exists in the banks."""
    device_id = _owned_child(request, child_id)
    try:
        week_start = date.fromisoformat(body.week_start.strip())
    except ValueError:
        week_start = None
    if week_start is None or not weekly_plan.valid_mark_week(week_start):
        raise _err(422, "week_start",
                   "أرسل تاريخ الاثنين لأسبوع الخطة الحالي أو الأسبوع الذي قبله.")
    item_key = body.item_key.strip()
    if item_key not in weekly_plan.plan_item_keys():
        raise _err(422, "item_key", "هذه الخطوة ليست من خطة الأسبوع.")
    return device_id, week_start, item_key


@router.put("/children/{child_id}/weekly-plan/marks",
            summary="Tick one step of the week's plan (idempotent)")
def put_weekly_plan_mark(child_id: int, body: PlanMarkIn, request: Request):
    device_id, week_start, item_key = _plan_mark(request, child_id, body)
    marks = weekly_plan.mark_item(device_id, child_id, week_start, item_key)
    return {"child_id": child_id, "week_start": week_start.isoformat(),
            "item_key": item_key, "marked": True, "marks": marks}


@router.delete("/children/{child_id}/weekly-plan/marks",
               summary="Un-tick one step of the week's plan (idempotent)")
def delete_weekly_plan_mark(child_id: int, body: PlanMarkIn, request: Request):
    device_id, week_start, item_key = _plan_mark(request, child_id, body)
    marks = weekly_plan.unmark_item(device_id, child_id, week_start, item_key)
    return {"child_id": child_id, "week_start": week_start.isoformat(),
            "item_key": item_key, "marked": False, "marks": marks}
