"""
Quranic Linguistics router — endpoints للتحليل اللغوي القرآني من Bahouth MCP.
=============================================================================
مسارات مستقلة عن الـRAG الرئيسي (توصية سالم: قاعدة لغوية دقيقة مش نصوص
معرفة للاسترجاع). بتتنادى لما:
  - الوالد يسأل عن جذر كلمة أو تكرارها في القرآن
  - الوالد يسأل عن آيات موضوع معين
  - الوالد يسأل عن قراءات آية

الـendpoints:
  POST /api/quranic-linguistics/find-root        — جذر كلمة + تكرارها (normalize تلقائي)
  POST /api/quranic-linguistics/root-verses      — آيات الجذر (pagination، سقف 50)
  GET  /api/quranic-linguistics/topics/{id}/verses — آيات موضوع (topic_id رقمي)
  GET  /api/quranic-linguistics/verses/{key}/qiraat — قراءات آية (key «2-255» بشرطة)
  GET  /api/quranic-linguistics/verses/{key}     — آية واحدة
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.quranic_linguistics_service import (
    find_root,
    list_root_verses,
    list_topic_verses,
    list_verse_qiraat,
    get_verse,
    format_root_for_display,
    format_verses_for_display,
    FALLBACK_MESSAGE,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quranic-linguistics", tags=["quranic-linguistics"])

_VERSE_KEY_RE = re.compile(r"^\d+-\d+$")  # «2-255» بشرطة — مش نقطتين


class RootRequest(BaseModel):
    root_text: str = Field(..., min_length=1, max_length=50)


class RootResponse(BaseModel):
    root_text: str
    found: bool
    root_id: int | None = None
    frequency: int | None = None
    cached: bool = False
    error: str | None = None
    formatted: str  # النص جاهز للعرض للوالد


class RootVersesRequest(BaseModel):
    root_text: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(default=10, ge=1, le=50)  # سقف السيرفر 50
    offset: int = Field(default=0, ge=0)


class VerseListResponse(BaseModel):
    query_key: str
    verses: list[dict]
    total: int | None = None
    limit: int
    offset: int
    cached: bool = False
    error: str | None = None
    formatted: str


class QiraatResponse(BaseModel):
    verse_key: str
    qiraat: list[dict]
    cached: bool = False
    error: str | None = None


class VerseResponse(BaseModel):
    verse_key: str
    verse: dict | None
    error: str | None = None


def _raise_if_unavailable(error: str | None) -> None:
    """سقوط السيرفر → 503 برسالة الـfallback الموحدة."""
    if error == "unavailable":
        raise HTTPException(status_code=503, detail=FALLBACK_MESSAGE)


@router.post("/find-root", response_model=RootResponse)
async def post_find_root(request: RootRequest):
    """جذر كلمة مع تكرارها في القرآن (normalize تلقائي للتشكيل)."""
    result = await find_root(request.root_text)
    _raise_if_unavailable(result.error)
    return RootResponse(
        root_text=result.root_text,
        found=result.found,
        root_id=result.root_id,
        frequency=result.frequency,
        cached=result.cached,
        error=result.error,
        formatted=format_root_for_display(result),
    )


@router.post("/root-verses", response_model=VerseListResponse)
async def post_root_verses(request: RootVersesRequest):
    """آيات جذر معين — pagination بالـoffset (50+43=103 لصبر ✓)."""
    result = await list_root_verses(
        request.root_text, limit=request.limit, offset=request.offset
    )
    _raise_if_unavailable(result.error)
    return VerseListResponse(
        query_key=result.query_key,
        verses=result.verses,
        total=result.total,
        limit=request.limit,
        offset=request.offset,
        cached=result.cached,
        error=result.error,
        formatted=format_verses_for_display(result),
    )


@router.get("/topics/{topic_id}/verses", response_model=VerseListResponse)
async def get_topic_verses(
    topic_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """آيات موضوع معين (topic_id رقمي — متحقق منه على السيرفر)."""
    result = await list_topic_verses(topic_id, limit=limit, offset=offset)
    _raise_if_unavailable(result.error)
    return VerseListResponse(
        query_key=result.query_key,
        verses=result.verses,
        total=result.total,
        limit=limit,
        offset=offset,
        cached=result.cached,
        error=result.error,
        formatted=format_verses_for_display(result),
    )


@router.get("/verses/{verse_key}/qiraat", response_model=QiraatResponse)
async def get_verse_qiraat(verse_key: str):
    """قراءات آية — verse_key بصيغة «2-255» بشرطة."""
    if not _VERSE_KEY_RE.match(verse_key):
        raise HTTPException(
            status_code=400,
            detail="صيغة verse_key لازم تكون «سورة-آية» بشرطة، مثال: 2-255",
        )
    result = await list_verse_qiraat(verse_key)
    _raise_if_unavailable(result.error)
    return QiraatResponse(
        verse_key=verse_key,
        qiraat=result.verses,
        cached=result.cached,
        error=result.error,
    )


@router.get("/verses/{verse_key}", response_model=VerseResponse)
async def get_single_verse(verse_key: str):
    """آية واحدة بالرسم العثماني — verse_key بصيغة «2-255» بشرطة."""
    if not _VERSE_KEY_RE.match(verse_key):
        raise HTTPException(
            status_code=400,
            detail="صيغة verse_key لازم تكون «سورة-آية» بشرطة، مثال: 2-255",
        )
    verse = await get_verse(verse_key)
    return VerseResponse(verse_key=verse_key, verse=verse)