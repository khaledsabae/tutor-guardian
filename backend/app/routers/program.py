"""
Program router — Curriculum content layer (Phase 2) + progress (Phase 5).

Read-only endpoints (public per AuthMiddleware):

  GET /api/program/paths?age_group=&domain=
  GET /api/program/paths/{id}?include=lessons
  GET /api/program/lessons/{id}
  GET /api/program/daily-tip?age_group=&time_of_day=&id=<tip_id>

Mutating endpoint (requires Bearer auth — see AuthMiddleware):

  PATCH /api/program/lessons/{id}/progress
      Body: {status: "in_progress" | "completed"}
      Idempotent: a second PATCH with the same status is a no-op.

The children CRUD (POST /api/children, GET /api/children/{id}/progress)
lives in `routers/children.py` to keep `/api/program/*` focused on
curriculum content.
"""
import datetime as dt
import hashlib
import logging
import re
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import curriculum_loader as cl
from app.db.init_db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/program", tags=["program"])

# ── Constants ────────────────────────────────────────────────────────────
# Accept every canonical band + the legacy "0-3" alias (pre-split children).
_VALID_AGE_GROUPS = {
    "prenatal-1", "0-3", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18",
}
_VALID_DOMAINS = {"medical", "cyber", "islamic_parenting", "development", "aqeedah"}
_VALID_TIME_OF_DAY = {"morning", "evening", "bedtime", "anytime"}
_VALID_PROGRESS_STATUS = {"not_started", "in_progress", "completed"}


# ── Helpers ──────────────────────────────────────────────────────────────

def _validate_age_group(age_group: Optional[str]) -> Optional[str]:
    if age_group is None:
        return None
    if age_group not in _VALID_AGE_GROUPS:
        raise HTTPException(
            status_code=422,
            detail=f"age_group غير صالح. القيم المتاحة: {sorted(_VALID_AGE_GROUPS)}",
        )
    # Pass through unchanged — content lookups use age_equivalents() so the
    # legacy "0-3" and canonical "prenatal-1" resolve to each other.
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


@router.get("/lesson-assets/{lesson_id}")
async def get_lesson_assets(
    lesson_id: str,
    request: Request,
    lang: Optional[str] = Query(None, description="Preferred language for media (ar/en)")
):
    """استرجاع أصول الدرس التفاعلية (البودكاست، الفلاش كاردز، الاختبارات، إلخ)."""
    assets = cl.get_lesson_assets(lesson_id)
    if assets is None:
        raise HTTPException(status_code=404, detail=f"لا توجد أصول للدرس '{lesson_id}'")
    
    # Determine user language preference:
    # 1. Query parameter
    # 2. Accept-Language header
    # 3. Default to "ar" (Arabic-first application)
    preferred_lang = lang
    if not preferred_lang:
        accept_lang = request.headers.get("accept-language", "")
        if "en" in accept_lang.lower() and not accept_lang.lower().startswith("ar"):
            preferred_lang = "en"
        else:
            preferred_lang = "ar"

    # Resolve podcast MP3
    podcasts = assets.get("podcasts", [])
    podcast_mp3 = None
    if podcasts:
        for p in podcasts:
            if p.get("language") == preferred_lang:
                podcast_mp3 = p.get("file")
                break
        if not podcast_mp3:
            # Fallback to Arabic secondary, then to first available
            for p in podcasts:
                if p.get("language") == "ar":
                    podcast_mp3 = p.get("file")
                    break
            if not podcast_mp3:
                podcast_mp3 = podcasts[0].get("file")

    # Resolve video MP4
    videos = assets.get("videos", [])
    video_mp4 = None
    if videos:
        for v in videos:
            if v.get("language") == preferred_lang:
                video_mp4 = v.get("file")
                break
        if not video_mp4:
            # Fallback to Arabic secondary, then to first available
            for v in videos:
                if v.get("language") == "ar":
                    video_mp4 = v.get("file")
                    break
            if not video_mp4:
                video_mp4 = videos[0].get("file")

    # Single-file visual assets (one per lesson): infographic image, report
    # markdown, data-table CSV. Each is served statically from /docs/.
    def _first_file(items):
        return items[0].get("file") if items else None

    return {
        "podcast_mp3": podcast_mp3,
        "video_mp4": video_mp4,
        "infographic": _first_file(assets.get("infographics", [])),
        "report": _first_file(assets.get("reports", [])),
        "data_table": _first_file(assets.get("data_tables", [])),
        "flashcards": assets.get("flashcards", []),
        "quizzes": assets.get("quizzes", [])
    }


@router.get("/asset-content/{asset_id}")
async def get_asset_content(asset_id: str):
    """محتوى أصل تفاعلي (فلاش كاردز / اختبار) بالكامل — additive v1 endpoint."""
    content = cl.get_asset_content(asset_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"الأصل '{asset_id}' غير موجود")
    return content


@router.get("/search")
async def search_curriculum(
    q: str = Query(..., min_length=2, description="نص البحث (حرفان على الأقل)"),
    limit: int = Query(20, ge=1, le=50),
):
    """بحث نصّي في الدروس والمسارات والنصائح — additive v1 endpoint."""
    results = cl.search(q, limit=limit)
    return {"query": q, "count": len(results), "results": results}


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


# ── Proactive parenting coach (Phase 8) ────────────────────────────────

from app.services import coach_service


class CoachTipResponse(BaseModel):
    id: int
    text: str
    domain: str
    child_id: int
    date: str


@router.get("/coach-tip", response_model=CoachTipResponse)
async def get_coach_tip(
    request: Request,
    child_id: int = Query(..., description="معرّف الطفل النشط"),
):
    """نصيحة تربوية استباقية مخصّصة للطفل اليوم.

    تعوّض DailyTipCard في الهوم: إذا كان هناك سؤال حديث للأب في موضوع واضح
    وعدّت بوابة الجودة، تُولّد نصيحة محددة («لاحظت إنك سألت عن…»). وإلا
    تعود لنصيحة اليومية العادية بنفس الشكل.
    """
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    try:
        tip = await coach_service.get_proactive_tip(device_id, child_id)
        return CoachTipResponse(**tip)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/coach-tip/{tip_id}/tap")
async def tap_coach_tip(
    request: Request,
    tip_id: int,
):
    """تسجيل تفاعل خفيف: الأب ضغط على النصيحة."""
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    try:
        coach_service.record_tap(device_id, tip_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Progress tracking (Phase 5) ──────────────────────────────────────────

class ProgressPatch(BaseModel):
    status: Literal["not_started", "in_progress", "completed"]


class ProgressResponse(BaseModel):
    lesson_id: str
    path_id: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    updated_at: str


@router.patch(
    "/lessons/{lesson_id}/progress",
    response_model=ProgressResponse,
    summary="Upsert the (device_id, lesson_id) progress row. Idempotent.",
)
def patch_lesson_progress(
    lesson_id: str,
    payload: ProgressPatch,
    request: Request,
) -> ProgressResponse:
    """Mark a lesson as `in_progress` (the user opened it) or `completed`.

    The auth middleware guarantees we have a valid `device_id`; we
    never trust client-supplied identity for progress rows. `path_id`
    is resolved from the curriculum loader so the client cannot
    attribute progress to a different path.
    """
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")

    lesson = cl.get_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail=f"الدرس '{lesson_id}' غير موجود")
    path_id = lesson["path_id"]
    # Prefer child_id from a currently active child for this device. If no
    # child exists, we still allow the PATCH (legacy behaviour) and store
    # child_id = 0, which keeps the UNIQUE constraint happy without leaking
    # a real child id.
    conn = get_conn()
    try:
        child_row = conn.execute(
            "SELECT id FROM child_profiles WHERE device_id = ? ORDER BY created_at ASC LIMIT 1",
            (device_id,),
        ).fetchone()
        child_id = child_row["id"] if child_row else 0

        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Idempotent upsert. We re-read the existing row to preserve
        # `started_at` when the client transitions to `completed`.
        existing = conn.execute(
            "SELECT * FROM lesson_progress WHERE device_id = ? AND child_id = ? AND lesson_id = ?",
            (device_id, child_id, lesson_id),
        ).fetchone()

        if existing is None:
            started_at = now if payload.status != "not_started" else None
            completed_at = now if payload.status == "completed" else None
            conn.execute(
                """
                INSERT INTO lesson_progress
                    (device_id, child_id, lesson_id, path_id, status, started_at, completed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    child_id,
                    lesson_id,
                    path_id,
                    payload.status,
                    started_at,
                    completed_at,
                    now,
                ),
            )
        else:
            started_at = existing["started_at"]
            if payload.status != "not_started" and not started_at:
                started_at = now
            completed_at = existing["completed_at"]
            if payload.status == "completed":
                completed_at = now
            # `not_started` is a "reset" — wipe timestamps so the UI
            # can re-enable the lesson.
            if payload.status == "not_started":
                started_at = None
                completed_at = None
            conn.execute(
                """
                UPDATE lesson_progress
                   SET path_id = ?, status = ?, started_at = ?, completed_at = ?, updated_at = ?
                 WHERE device_id = ? AND child_id = ? AND lesson_id = ?
                """,
                (
                    path_id,
                    payload.status,
                    started_at,
                    completed_at,
                    now,
                    device_id,
                    child_id,
                    lesson_id,
                ),
            )
        conn.commit()
        return ProgressResponse(
            lesson_id=lesson_id,
            path_id=path_id,
            status=payload.status,
            started_at=started_at,
            completed_at=completed_at,
            updated_at=now,
        )
    finally:
        conn.close()


# ── Quiz ───────────────────────────────────────────────────────────────

@router.get("/quiz")
def get_quiz(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    count: int = Query(10, ge=1, le=30, description="Number of questions"),
):
    """Return random quiz questions, optionally filtered by domain."""
    from app.quiz_data import get_quiz_questions

    questions = get_quiz_questions(domain=domain, count=count)
    return {"count": len(questions), "questions": questions}


# ── Personalized story generation (a coins redeemable) ──────────────────────

# Fixed catalogue of values a story can teach — keeps generation on-rails
# and safe (no free-text theme that could be abused).
STORY_THEMES: dict[str, str] = {
    "honesty": "الصدق والأمانة",
    "courage": "الشجاعة ومواجهة الخوف",
    "mercy": "الرحمة والرفق بالآخرين",
    "parents": "بر الوالدين وطاعتهما",
    "sharing": "مشاركة الألعاب والكرم",
    "patience": "الصبر عند الغضب",
    "cleanliness": "النظافة والاهتمام بالنفس",
    "gratitude": "الشكر والقناعة",
    "prayer": "حب الصلاة والعبادة",
}


class StoryRequest(BaseModel):
    child_name: str = Field(min_length=1, max_length=40)
    age_group: str
    theme: str  # key from STORY_THEMES


@router.post("/story")
async def generate_story(req: StoryRequest):
    """Generate a short, safe, value-teaching Arabic children's story
    starring the child. Runs entirely on the local model (no cloud)."""
    from app.services.ai_gateway import get_gateway

    if req.theme not in STORY_THEMES:
        raise HTTPException(
            status_code=422,
            detail=f"قيمة غير صالحة. المتاح: {sorted(STORY_THEMES)}",
        )
    if req.age_group not in _VALID_AGE_GROUPS:
        raise HTTPException(status_code=422, detail="age_group غير صالح.")

    # Sanitize the name to letters/spaces only (defense-in-depth — the name
    # is interpolated into the prompt).
    safe_name = re.sub(r"[^\w؀-ۿ ]", "", req.child_name).strip()[:40]
    if not safe_name:
        safe_name = "بطلنا الصغير"
    value = STORY_THEMES[req.theme]

    prompt = (
        "أنت كاتب قصص أطفال عربي. اكتب قصة قصيرة (٣ إلى ٥ فقرات) بالعربية "
        "الفصحى الميسرة، آمنة تماماً ومناسبة للأطفال، خالية من العنف أو الخوف "
        "المبالغ فيه، ومنسجمة مع القيم الإسلامية.\n"
        f"بطل القصة طفل اسمه «{safe_name}». القصة تعلّم قيمة: {value}.\n"
        "اجعل لها عنواناً جذاباً في أول سطر، ثم القصة، واختمها بدرس مستفاد "
        "في جملة واحدة تبدأ بـ «الدرس المستفاد:». لا تكتب أي شيء خارج القصة."
    )
    try:
        result = await get_gateway().generate(prompt, options={"temperature": 0.8})
        story = (result.text or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("story generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="تعذّر توليد القصة حالياً، حاول مرة أخرى.",
        )
    if not story:
        raise HTTPException(status_code=503, detail="تعذّر توليد القصة حالياً.")
    return {"theme": req.theme, "value": value, "story": story}


@router.get("/story-themes")
def story_themes():
    """The catalogue of story values (key → Arabic label) for the UI."""
    return {"themes": [{"key": k, "label": v} for k, v in STORY_THEMES.items()]}
