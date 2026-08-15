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

def _base_lang(code: Optional[str]) -> Optional[str]:
    """'ar_eg' → 'ar', 'en-US' → 'en'.

    Media entries declare the NotebookLM locale that produced them, so the same
    language arrives as `ar` on a podcast and `ar_eg` on a video. Anything that
    compares those strings raw treats one language as two.
    """
    if not code:
        return None
    return code.strip().lower().replace("-", "_").split("_")[0]


def _pick_tip_for_today(age_group: str, time_of_day: Optional[str],
                        lang: Optional[str] = None) -> dict:
    """Deterministic per-day tip selection so the same client sees the
    same tip on the same day. Hash of (date + age_group) → index in pool.

    `lang` translates the pool item-by-item without changing pool length or
    order, so the index below still lands on the same tip in every language —
    two parents in one household get the same tip on the same day.
    """
    pool = cl.get_daily_tips(age_group, time_of_day=time_of_day, lang=lang)
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
    request: Request,
    age_group: Optional[str] = Query(None, description="فلترة بالعمر: 0-3, 4-6, 7-9, 10-12, 13-15, 16-18"),
    domain: Optional[str] = Query(None, description="فلترة بالمجال: medical, cyber, islamic_parenting, development"),
    lang: Optional[str] = Query(None, description="لغة المحتوى: ar/en"),
):
    """قائمة المسارات المنشورة، قابلة للفلترة."""
    age_group = _validate_age_group(age_group)
    domain = _validate_domain(domain)
    paths = cl.get_paths(age_group=age_group, domain=domain,
                         lang=_resolve_lang(lang, request))
    return {
        "count": len(paths),
        "paths": paths,
    }


@router.get("/paths/{path_id}")
async def get_path_detail(
    path_id: str,
    request: Request,
    include: Optional[str] = Query(None, description="?include=lessons لإرجاع الدروس مع المسار"),
    lang: Optional[str] = Query(None, description="لغة المحتوى: ar/en"),
):
    """تفاصيل مسار واحد. لو include=lessons، يرجع الدروس بالترتيب."""
    resolved = _resolve_lang(lang, request)
    path = cl.get_path(path_id, lang=resolved)
    if path is None:
        raise HTTPException(status_code=404, detail=f"المسار '{path_id}' غير موجود")

    body: dict = dict(path)
    if include == "lessons":
        lessons = cl.get_lessons_for_path(path_id, lang=resolved)
        body["lessons"] = lessons
        body["lessons_count"] = len(lessons)
    return body


# One curated entry path per age band.
#
# `get_paths` sorts by (age_group, domain, id) — alphabetical domain, which is
# a stable order, not a content decision. Left to it, a new parent's very first
# impression of the curriculum is whichever domain happens to sort first
# ('aqeedah' or 'cyber'), rather than the relationship material that actually
# earns the second visit.
#
# Mirrored in ops/scripts/cron_push_triggers.py (STARTER_PATHS) — the
# re-engagement push aims at the same door. Keep the two in step.
_STARTER_PATHS = {
    "prenatal-1": "path_0-3_islamic_parenting_attachment",
    "0-3": "path_0-3_islamic_parenting_attachment",
    "2-3": "path_2-3_islamic_attachment",
    "4-6": "path_4-6_islamic_parenting_bond",
    "7-9": "path_7-9_islamic_parenting_akhlaq",
    "10-12": "path_10-12_islamic_parenting_identity",
    "13-15": "path_13-15_islamic_parenting_teen_identity",
    "16-18": "path_16-18_islamic_parenting_adult_faith",
}


class NextLessonResponse(BaseModel):
    lesson_id: str
    path_id: str
    path_title: str
    title: str
    order: int
    # False on a parent's very first lesson — lets the client say "ابدأ" rather
    # than "أكمل", which is a different promise.
    resumed: bool


@router.get("/next-lesson", response_model=NextLessonResponse)
async def get_next_lesson(
    request: Request,
    age_group: str = Query(..., description="الفئة العمرية للطفل"),
    child_id: Optional[int] = Query(None, description="لتخطّي ما أُنجز"),
):
    """The single lesson to put in front of this parent right now.

    Exists because the home screen's primary call to action used to hand a
    newly-onboarded parent a filterable list of 39 paths: four taps between
    finishing onboarding and reading a single line of the curriculum. 86% of
    installs add a child; 31% ever open a lesson. This endpoint is what lets
    that CTA open one.

    Deliberately server-side: which lesson greets a new parent becomes a
    tunable we can change without shipping an app release.
    """
    age = _validate_age_group(age_group)
    if age is None:
        raise HTTPException(status_code=422, detail="age_group مطلوب.")

    path_id = _STARTER_PATHS.get(age)
    if path_id is None or cl.get_path(path_id) is None:
        # An age band we have not curated, or a curated id that no longer
        # resolves after a curriculum edit. Falling back beats a 404.
        candidates = cl.get_paths(age_group=age)
        if not candidates:
            raise HTTPException(
                status_code=404, detail=f"لا توجد مسارات للفئة '{age}'."
            )
        path_id = candidates[0]["id"]

    lessons = cl.get_lessons_for_path(path_id)
    if not lessons:
        raise HTTPException(
            status_code=404, detail=f"المسار '{path_id}' بلا دروس منشورة."
        )

    # Scoped by device as well as child, so an id that is not the caller's
    # simply matches nothing and they get lesson one — no ownership check
    # needed, and no way to probe another family's progress.
    done: set[str] = set()
    device_id = getattr(request.state, "device_id", None)
    if child_id is not None and device_id:
        conn = get_conn()
        try:
            done = {
                r["lesson_id"]
                for r in conn.execute(
                    "SELECT lesson_id FROM lesson_progress "
                    "WHERE device_id = ? AND child_id = ? AND status = 'completed'",
                    (device_id, child_id),
                )
            }
        finally:
            conn.close()

    nxt = next((le for le in lessons if le.get("id") not in done), None)
    # Every lesson done: send them back to the last one rather than nowhere.
    resumed = bool(done)
    if nxt is None:
        nxt = lessons[-1]

    path = cl.get_path(path_id) or {}
    return NextLessonResponse(
        lesson_id=nxt["id"],
        path_id=path_id,
        path_title=path.get("title", ""),
        title=nxt.get("title", ""),
        order=int(nxt.get("order", 1)),
        resumed=resumed,
    )


def _resolve_lang(lang: Optional[str], request: Request) -> Optional[str]:
    """Query parameter first, then Accept-Language, then Arabic.

    The lesson endpoint took no language at all until 2026-08-13, so English
    users read Arabic lessons while a complete English translation sat unused
    on disk. Two of them reported it through the in-app form.
    """
    return lang or request.headers.get("accept-language", "") or None


@router.get("/lessons/{lesson_id}")
async def get_lesson_detail(
    lesson_id: str,
    request: Request,
    lang: Optional[str] = Query(None, description="لغة المحتوى: ar/en"),
):
    """تفاصيل درس واحد. يرجع الـ unit_ids لكن لا يحمّل الـ units الكاملة —
    الـ app يستخدم /api/assistant/stream لجلب السياق عند الحاجة."""
    lesson = cl.get_lesson(lesson_id, lang=_resolve_lang(lang, request))
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

    def _pick(items, kind):
        """Best file for `preferred_lang`, Arabic as fallback, then whatever exists.

        One helper for every medium, because the two hand-written copies it
        replaces had drifted: the video branch compared `language == "ar"` while
        every video entry declares `ar_eg`, so its Arabic fallback could never
        match and the result came from the `videos[0]` catch-all instead. It was
        right only because Arabic happened to be first.

        Comparison is on the base language: entries carry `ar`, `ar_eg` and
        `en_us` for what are two languages.

        **Existence is part of the choice, not a filter applied after it.**
        Media is gitignored and arrives by rsync, so the index routinely names a
        file this host does not have. Picking first and dropping the path
        afterwards was wrong twice over: the response still reported a language
        for a medium it had not served, and a lesson whose English podcast was
        indexed but not yet synced lost its Arabic one too — a working fallback,
        sitting on disk, skipped because a better-matching entry was chosen
        before anyone asked whether it was there.
        """
        usable = []
        for entry in items or ():
            path = entry.get("file")
            if not path:
                continue
            if not cl.media_exists(path):
                # The gap is worth a line in the log: an indexed file that never
                # arrived is invisible in every count that reads the index.
                logger.warning(
                    "lesson %s: %s references missing file %s", lesson_id, kind, path
                )
                continue
            usable.append(entry)
        if not usable:
            return None, None
        want = _base_lang(preferred_lang)
        for candidate in (want, "ar"):
            for entry in usable:
                if _base_lang(entry.get("language")) == candidate:
                    return entry["file"], _base_lang(entry.get("language"))
        first = usable[0]
        # No declared language anywhere: infographics, reports and data tables
        # carry none at all, and Arabic is the source language for every asset
        # produced before English generation existed.
        return first["file"], _base_lang(first.get("language")) or "ar"

    podcast_mp3, podcast_lang = _pick(assets.get("podcasts", []), "podcast")
    video_mp4, video_lang = _pick(assets.get("videos", []), "video")
    # Single-file visual assets (one per lesson): infographic image, report
    # markdown, data-table CSV. Each is served statically from /docs/.
    #
    # These are language-bearing too, and more starkly than audio: an
    # infographic is Arabic *pixels*, so an English reader gets no partial
    # understanding and no fallback is possible — the text is the image.
    infographic, infographic_lang = _pick(assets.get("infographics", []), "infographic")
    report, report_lang = _pick(assets.get("reports", []), "report")
    data_table, data_table_lang = _pick(assets.get("data_tables", []), "data_table")

    return {
        # No post-filter here: `_pick` already refused anything not on this
        # host, so a path present below is a file that exists and a language
        # beside it describes that same file.
        "podcast_mp3": podcast_mp3,
        "video_mp4": video_mp4,
        "infographic": infographic,
        "report": report,
        "data_table": data_table,
        "flashcards": assets.get("flashcards", []),
        "quizzes": assets.get("quizzes", []),
        # What the app actually got, per medium. Asking for English and being
        # handed Arabic is normal while English media is still being generated;
        # the app can only say so if the response admits it.
        "languages": {
            "requested": _base_lang(preferred_lang),
            "podcast": podcast_lang,
            "video": video_lang,
            "infographic": infographic_lang,
            "report": report_lang,
            "data_table": data_table_lang,
        },
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
    request: Request,
    q: str = Query(..., min_length=2, description="نص البحث (حرفان على الأقل)"),
    limit: int = Query(20, ge=1, le=50),
    lang: Optional[str] = Query(None, description="لغة المحتوى: ar/en"),
):
    """بحث نصّي في الدروس والمسارات والنصائح — additive v1 endpoint."""
    results = cl.search(q, limit=limit, lang=_resolve_lang(lang, request))
    return {"query": q, "count": len(results), "results": results}


@router.get("/daily-tip")
async def get_daily_tip(
    request: Request,
    age_group: str = Query(..., description="إلزامي: العمر لتحديد الـ pool"),
    time_of_day: Optional[str] = Query(None, description="اختياري: morning | evening | bedtime | anytime"),
    tip_id: Optional[str] = Query(None, description="اختياري: لو محتاج نصيحة محددة بالـ id"),
    lang: Optional[str] = Query(None, description="لغة المحتوى: ar/en"),
):
    """نصيحة يومية واحدة. الافتراضي: deterministic per-day selection من pool.
    لو tip_id موجود، يرجع النصيحة المحددة (للـ debugging أو favorites)."""
    age_group = _validate_age_group(age_group)
    if time_of_day is not None and time_of_day not in _VALID_TIME_OF_DAY:
        raise HTTPException(
            status_code=422,
            detail=f"time_of_day غير صالح. القيم المتاحة: {sorted(_VALID_TIME_OF_DAY)}",
        )

    resolved = _resolve_lang(lang, request)

    if tip_id is not None:
        tip = cl.get_daily_tip_by_id(tip_id, lang=resolved)
        if tip is None or tip.get("age_group") != age_group:
            raise HTTPException(
                status_code=404,
                detail=f"النصيحة '{tip_id}' غير موجودة أو لا تناسب العمر {age_group}",
            )
        return tip

    return _pick_tip_for_today(age_group, time_of_day, lang=resolved)


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
    """تسجيل تفاعل خفيف: الأب ضغط على النصيحة.

    Best-effort: 200 even if the tip does not exist or belongs to another
    device, because the mobile client should never crash over a missed
    analytics tap. The device_id check is preserved in logs for audit.
    """
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    try:
        coach_service.record_tap(device_id, tip_id)
    except ValueError:
        # Tip missing or owned by another device — ignore silently. This is a
        # non-critical interaction event and the client must not crash.
        pass
    return {"ok": True}


# ── Progress tracking (Phase 5) ──────────────────────────────────────────

class ProgressPatch(BaseModel):
    status: Literal["not_started", "in_progress", "completed"]
    # Which child this progress belongs to. Optional for backward compat:
    # older mobile clients don't send it and fall back to the legacy
    # first-created-child attribution.
    child_id: Optional[int] = None


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
    # Attribute progress to the child the client names (ownership-checked).
    # Legacy fallback when child_id is absent: first-created child, or 0 if
    # the device has no children (keeps the UNIQUE constraint happy).
    conn = get_conn()
    try:
        if payload.child_id is not None:
            owned = conn.execute(
                "SELECT id FROM child_profiles WHERE id = ? AND device_id = ?",
                (payload.child_id, device_id),
            ).fetchone()
            if owned is None:
                raise HTTPException(status_code=404, detail="الطفل غير موجود لهذا الجهاز.")
            child_id = payload.child_id
        else:
            child_row = conn.execute(
                "SELECT id FROM child_profiles WHERE device_id = ? ORDER BY created_at ASC LIMIT 1",
                (device_id,),
            ).fetchone()
            child_id = child_row["id"] if child_row else 0

        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Idempotent upsert. We re-read the existing row to preserve
        # `started_at` when the client transitions to `completed`.
        #
        # Matched on (device_id, lesson_id) — the table's ACTUAL unique key.
        # `child_id` was added later and left out of it, so the table can hold
        # only one row per device per lesson no matter how many children the
        # device has. Selecting on child_id too meant a row owned by a sibling
        # was invisible here: the handler concluded nothing existed, inserted,
        # and sqlite rejected it with `UNIQUE constraint failed:
        # lesson_progress.device_id, lesson_progress.lesson_id` — an
        # unhandled 500 for a parent doing nothing more exotic than finishing
        # a lesson. Eight of them on 2026-08-13, right after a migration moved
        # rows onto the correct sibling while clients still sent no child_id.
        #
        # Matching the real key makes the upsert total: the row is found
        # whoever it belongs to, and `child_id` below re-points it at the
        # child the client names.
        existing = conn.execute(
            "SELECT * FROM lesson_progress WHERE device_id = ? AND lesson_id = ?",
            (device_id, lesson_id),
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
            # Same key as the SELECT, and `child_id` is written rather than
            # matched on: a client that names its child re-points the row,
            # while an older client that names none leaves it where it is.
            # Keying the UPDATE on child_id too meant the statement matched
            # nothing whenever the row belonged to a sibling — no row changed,
            # no error raised, and the parent's completion vanished in
            # silence. That is the same failure the user reported, wearing a
            # 200 instead of a 500.
            conn.execute(
                """
                UPDATE lesson_progress
                   SET path_id = ?, status = ?, started_at = ?, completed_at = ?,
                       updated_at = ?, child_id = COALESCE(?, child_id)
                 WHERE device_id = ? AND lesson_id = ?
                """,
                (
                    path_id,
                    payload.status,
                    started_at,
                    completed_at,
                    now,
                    payload.child_id and child_id,
                    device_id,
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
    "neighbor_rights": "حقوق الجار والإحسان إليه",
    "table_manners": "آداب الطعام والتسمية والأكل باليمين",
    "speech_guard": "حفظ اللسان والنهي عن السخرية",
    "quran_love": "تعظيم القرآن وتدبره",
    "permission_adab": "أدب الاستئذان وحفظ الخصوصية",
    "creation_contemplation": "التأمل في خلق الله وعظمته",
    "parents_respect": "بر الوالدين وإدخال السرور عليهما",
    "forgiveness_morals": "العفو والتسامح والقدوة الحسنة",
}


class StoryRequest(BaseModel):
    child_name: str = Field(min_length=1, max_length=40)
    age_group: str
    theme: str  # key from STORY_THEMES
    # Optional: lets the backend resolve the child's gender so a correctly
    # conjugated pre-generated story can be served from cache (§5.1).
    child_id: Optional[int] = None


@router.post("/story")
async def generate_story(req: StoryRequest, request: Request):
    """Generate a short, safe, value-teaching Arabic children's story
    starring the child. Served from the pre-generated cache when a gendered
    variant exists; otherwise generated live on the local model (no cloud)."""
    from app.services import story_service
    from app.services.ai_gateway import _log_call, get_gateway

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

    # Cache tier: only when the child's gender is known (Arabic conjugation).
    device_id = getattr(request.state, "device_id", None)
    gender = story_service.resolve_child_gender(device_id, req.child_id)
    cached = story_service.get_cached_story(req.theme, req.age_group, gender)
    if cached:
        _log_call("story_cache", "pregen", 0, None, None,
                  streamed=False, ok=True, tier="local_fast",
                  route_reason="story_cache_hit")
        return {
            "theme": req.theme,
            "value": value,
            "story": story_service.personalize(
                cached["story"], cached["hero_name"], safe_name
            ),
        }

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


# ── Monthly Report (Phase 4.1) ──────────────────────────────────────────

@router.get("/monthly-report/{child_id}")
def monthly_report(child_id: int, request: Request):
    """Generate a monthly progress report for a child (auth-required).

    Returns structured data the client renders as a shareable report/PDF.
    The child must belong to the caller's device — a child's name and
    progress are private family data, never publicly enumerable.
    """
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")

    now = dt.datetime.now(dt.timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start_str = month_start.isoformat()

    conn = get_conn()
    try:
        child = conn.execute(
            "SELECT name, age_group, avatar_emoji, device_id "
            "FROM child_profiles WHERE id = ?",
            (child_id,),
        ).fetchone()
        if child is None or child["device_id"] != device_id:
            raise HTTPException(status_code=404, detail="طفل غير موجود.")

        # Lessons completed this month
        lessons = conn.execute(
            """SELECT lesson_id, status, updated_at
               FROM lesson_progress
               WHERE device_id = ? AND child_id = ?
               AND status = 'completed' AND updated_at >= ?
               ORDER BY updated_at""",
            (device_id, child_id, month_start_str),
        ).fetchall()

        # Habit/value check-ins this month («ميزان العادات» — the real habits
        # table, not the baby routine tracker).
        habit_counts = {
            r["status"]: int(r["cnt"])
            for r in conn.execute(
                """SELECT status, COUNT(*) AS cnt FROM habits_value_events
                   WHERE device_id = ? AND child_id = ? AND created_at >= ?
                   GROUP BY status""",
                (device_id, child_id, month_start_str),
            )
        }

        chats = conn.execute(
            """SELECT COUNT(*) AS cnt FROM chat_sessions
               WHERE device_id = ? AND created_at >= ?""",
            (device_id, month_start_str),
        ).fetchone()

        streak_rows = conn.execute(
            """SELECT date FROM daily_login_streaks
               WHERE device_id = ? ORDER BY date DESC LIMIT 30""",
            (device_id,),
        ).fetchall()
    finally:
        conn.close()

    # Current streak: consecutive days ending today (or yesterday — an
    # unfinished today shouldn't zero the streak).
    streak = 0
    if streak_rows:
        dates = [dt.date.fromisoformat(r["date"]) for r in streak_rows]
        expected = now.date()
        if dates[0] == expected - dt.timedelta(days=1):
            expected = dates[0]
        for d in dates:
            if d == expected:
                streak += 1
                expected -= dt.timedelta(days=1)
            else:
                break

    completed_habits = habit_counts.get("completed", 0)
    partial_habits = habit_counts.get("partial", 0)

    return {
        "child": {
            "name": child["name"],
            "age_group": child["age_group"],
            "avatar": child["avatar_emoji"] or "👶",
        },
        "period": {
            "month": now.strftime("%Y-%m"),
            "month_name_ar": _month_name_ar(now.month),
        },
        "stats": {
            "lessons_completed": len(lessons),
            "lessons_by_domain": _count_by_domain(lessons),
            "habit_completions": completed_habits,
            "habit_partials": partial_habits,
            "chat_sessions": chats["cnt"] if chats else 0,
            "current_streak": streak,
            "badges_earned": 0,  # client-side badges — not tracked server-side
        },
        "highlights": _generate_highlights(
            len(lessons), completed_habits, streak
        ),
        "generated_at": now.isoformat(),
    }


def _month_name_ar(month: int) -> str:
    """Arabic month name."""
    names = {
        1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
        5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
        9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
    }
    return names.get(month, "")


def _count_by_domain(lessons: list) -> dict:
    """Count completed lessons per domain via the curriculum index."""
    counts: dict[str, int] = {}
    for row in lessons:
        lesson = cl.get_lesson(row["lesson_id"])
        domain = (lesson or {}).get("domain") or "other"
        counts[domain] = counts.get(domain, 0) + 1
    return counts


def _generate_highlights(lessons_done: int, habits_done: int, streak: int) -> list[str]:
    """Generate personalized highlights for the report."""
    highlights = []
    if lessons_done > 0:
        highlights.append(f"أكملت {lessons_done} دروس هذا الشهر! 📚")
    if streak > 7:
        highlights.append(f"سلسلة {streak} أيام متتالية! استمر يا بطل 🔥")
    elif streak > 3:
        highlights.append(f"{streak} أيام متتالية — في الطريق الصحيح! 💪")
    if habits_done > 0:
        highlights.append(f"سجّلت {habits_done} عادة بنجاح ⭐")
    if not highlights:
        highlights.append("ابدأ هذا الشهر بخطوة صغيرة — كل رحلة تبدأ بخطوة! 🌟")
    return highlights
