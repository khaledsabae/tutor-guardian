"""Child memory, follow-ups and the weekly plan — «المربّي يعرف ابنك» (schema v30).

Every route is under /api/children (Bearer auth via AuthMiddleware) and is
scoped to the caller's device: a child, fact or follow-up of another device
answers 404, exactly like a missing one (same rule as routers/children.py).

The contract the app builds against is MOBILE_API.md §«Child memory». Errors
the app is expected to branch on carry a stable `code`:
    {"detail": {"code": "<code>", "message": "<Arabic message>"}}
"""
from __future__ import annotations

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
    """Off pauses everything: nothing new is learned, no follow-up is opened,
    and remembered facts stop reaching the assistant. Nothing is deleted —
    that is DELETE /api/children/{id}/memory or DELETE /api/privacy/memory.

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
    device_id = _require_device_id(request)
    # Where the follow-up push learns the family's night (quiet hours).
    cm.record_tz_offset(device_id, tz_offset_minutes)
    return {"followups": cm.due_followups(device_id, limit=limit)}


@router.get("/children/followups/{followup_id}",
            summary="One follow-up — what the /followup/{id} deep link opens",
            dependencies=[Depends(require_device_proof)])
def get_followup(followup_id: int, request: Request):
    """Any status: a push can be tapped after the follow-up was answered on
    another device or expired, and the screen should say so, not 404."""
    device_id = _require_device_id(request)
    fu = cm.get_followup(device_id, followup_id)
    if fu is None:
        raise _err(404, "followup_not_found", "متابعة غير موجودة.")
    return {"followup": fu}


@router.post("/children/followups/{followup_id}/answer",
             summary="Did the advice work? Records it as an outcome fact",
            dependencies=[Depends(require_device_proof)])
def answer_followup(followup_id: int, body: FollowupAnswerIn, request: Request):
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
    device_id = _owned_child(request, child_id)
    try:
        return cm.add_manual_fact(device_id, child_id, body.category, body.fact)
    except cm.FactValidationError as exc:
        raise _fact_error(exc) from exc


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
    """Facts, follow-ups and cached weekly plans for this child. The child
    profile itself is untouched (that is DELETE /api/children/{id})."""
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
