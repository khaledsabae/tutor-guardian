"""
Program router — Curriculum content layer (Phase 2).

Endpoints (read-only; no auth required for now — same model as
/api/chat/sessions which is public per the existing auth middleware):

  GET /api/program/paths?age_group=&domain=
      → list of published paths, optionally filtered.

  GET /api/program/paths/{id}
      → single path detail. If `?include=lessons` is set, the response
        also includes the ordered list of lessons for the path.

  GET /api/program/lessons/{id}
      → single lesson detail.

  GET /api/program/daily-tip?age_group=&time_of_day=
      → one tip, chosen deterministically from the age_group pool using
        a day-of-week seed so the same client sees the same tip on the
        same day. ?id=<tip_id> is also supported to fetch a specific tip.

Progress-tracking endpoints (POST /api/program/progress,
POST /api/program/children) are NOT yet implemented — see Phase 5+ plan.
"""
import datetime as dt
import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import curriculum_loader as cl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/program", tags=["program"])

# ── Constants ────────────────────────────────────────────────────────────
_VALID_AGE_GROUPS = {"0-3", "4-6", "7-9", "10-12", "13-15", "16-18"}
_VALID_DOMAINS = {"medical", "cyber", "islamic_parenting", "development"}
_VALID_TIME_OF_DAY = {"morning", "evening", "bedtime", "anytime"}


# ── Helpers ──────────────────────────────────────────────────────────────

def _validate_age_group(age_group: Optional[str]) -> Optional[str]:
    if age_group is None:
        return None
    if age_group not in _VALID_AGE_GROUPS:
        raise HTTPException(
            status_code=422,
            detail=f"age_group غير صالح. القيم المتاحة: {sorted(_VALID_AGE_GROUPS)}",
        )
    return age_group


def _validate_domain(domain: Optional[str]) -> Optional[str]:
    if domain is None:
        return None
    if domain not in _VALID_DOMAINS:
        raise HTTPException(
            status_code=422,
            detail=f"domain غير صالح. القيم المتاحة: {sorted(_VALID_DOMAINS)}",
        )
    return domain

def _pick_tip_for_today(age_group: str, time_of_day: Optional[str]) -> dict:
    """Deterministic per-day tip selection so the same client sees the
    same tip on the same day. Hash of (date + age_group) → index in pool."""
    pool = cl.get_daily_tips(age_group, time_of_day=time_of_day)
    if not pool:
        raise HTTPException(
            status_code=404,
            detail=f"لا توجد نصائح متاحة للعمر {age_group}"
                   + (f" والوقت {time_of_day}" if time_of_day else ""),
        )
    # Day seed: ISO date string (UTC). Stable for a calendar day.
    day_seed = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    seed_input = f"{day_seed}:{age_group}:{time_of_day or 'any'}"
    h = hashlib.sha256(seed_input.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(pool)
    return pool[idx]


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/paths")
async def list_paths(
    age_group: Optional[str] = Query(None, description="فلترة بالعمر: 0-3, 4-6, 7-9, 10-12, 13-15, 16-18"),
    domain: Optional[str] = Query(None, description="فلترة بالمجال: medical, cyber, islamic_parenting, development"),
):
    """قائمة المسارات المنشورة، قابلة للفلترة."""
    age_group = _validate_age_group(age_group)
    domain = _validate_domain(domain)
    paths = cl.get_paths(age_group=age_group, domain=domain)
    return {
        "count": len(paths),
        "paths": paths,
    }


@router.get("/paths/{path_id}")
async def get_path_detail(
    path_id: str,
    include: Optional[str] = Query(None, description="?include=lessons لإرجاع الدروس مع المسار"),
):
    """تفاصيل مسار واحد. لو include=lessons، يرجع الدروس بالترتيب."""
    path = cl.get_path(path_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"المسار '{path_id}' غير موجود")

    body: dict = dict(path)
    if include == "lessons":
        lessons = cl.get_lessons_for_path(path_id)
        body["lessons"] = lessons
        body["lessons_count"] = len(lessons)
    return body


@router.get("/lessons/{lesson_id}")
async def get_lesson_detail(lesson_id: str):
    """تفاصيل درس واحد. يرجع الـ unit_ids لكن لا يحمّل الـ units الكاملة —
    الـ app يستخدم /api/assistant/stream لجلب السياق عند الحاجة."""
    lesson = cl.get_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail=f"الدرس '{lesson_id}' غير موجود")
    return lesson


@router.get("/daily-tip")
async def get_daily_tip(
    age_group: str = Query(..., description="إلزامي: العمر لتحديد الـ pool"),
    time_of_day: Optional[str] = Query(None, description="اختياري: morning | evening | bedtime | anytime"),
    tip_id: Optional[str] = Query(None, description="اختياري: لو محتاج نصيحة محددة بالـ id"),
):
    """نصيحة يومية واحدة. الافتراضي: deterministic per-day selection من pool.
    لو tip_id موجود، يرجع النصيحة المحددة (للـ debugging أو favorites)."""
    age_group = _validate_age_group(age_group)
    if time_of_day is not None and time_of_day not in _VALID_TIME_OF_DAY:
        raise HTTPException(
            status_code=422,
            detail=f"time_of_day غير صالح. القيم المتاحة: {sorted(_VALID_TIME_OF_DAY)}",
        )

    if tip_id is not None:
        tip = cl.get_daily_tip_by_id(tip_id)
        if tip is None or tip.get("age_group") != age_group:
            raise HTTPException(
                status_code=404,
                detail=f"النصيحة '{tip_id}' غير موجودة أو لا تناسب العمر {age_group}",
            )
        return tip

    return _pick_tip_for_today(age_group, time_of_day)
