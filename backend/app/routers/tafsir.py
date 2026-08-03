"""
Tafsir router — endpoints لجلب التفسير الموثّق من Tafsir MCP.
==============================================================
مسارات مستقلة عن الـRAG الرئيسي. بتتنادى لما:
  - الوالد يسأل عن تفسير آية معينة
  - الورد القرآني يحتاج تفسير
  - درس قرآني يحتاج مصدر موثوق

الـendpoints:
  GET  /api/tafsir/{surah}/{ayah}           — تفسير آية (مصادر متعددة)
  GET  /api/tafsir/{surah}/{ayah}/ayah-text — نص الآية فقط
  GET  /api/tafsir/{surah}/{ayah}/nuzool    — سبب النزول
  GET  /api/tafsir/sources                   — فهرس المصادر
  POST /api/tafsir/search                   — بحث في الآيات
  POST /api/tafsir/search-tafsir            — بحث في التفسير
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.tafsir_service import (
    fetch_tafsir,
    fetch_ayah_text,
    fetch_nuzool_reason,
    list_tafsir_sources,
    search_quran,
    search_in_tafsir,
    format_tafsir_for_display,
    FALLBACK_MESSAGE,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tafsir", tags=["tafsir"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    source: str = Field(default="saadi")


class TafsirEntryResponse(BaseModel):
    surah: int
    ayah: int
    source: str
    attribution: str
    text: str
    cached: bool = False
    error: str | None = None


class TafsirResponse(BaseModel):
    surah: int
    ayah: int
    results: list[TafsirEntryResponse]
    formatted: str  # النص جاهز للعرض للوالد


class AyahTextResponse(BaseModel):
    surah: int
    ayah: int
    text: str | None


class NuzoolResponse(BaseModel):
    surah: int
    ayah: int
    attribution: str
    text: str
    formatted: str


class SourceListResponse(BaseModel):
    sources: list[dict]


class SearchResponse(BaseModel):
    results: list[dict]


@router.get("/{surah}/{ayah}", response_model=TafsirResponse)
async def get_tafsir(
    surah: int,
    ayah: int,
    sources: list[str] | None = Query(default=None),
):
    """جلب تفسير آية من مصدر أو أكثر."""
    if not (1 <= surah <= 114):
        raise HTTPException(status_code=400, detail="رقم السورة يجب أن يكون 1-114")
    if ayah < 1:
        raise HTTPException(status_code=400, detail="رقم الآية يجب أن يكون ≥ 1")

    results = await fetch_tafsir(surah, ayah, sources)

    entry_responses = [
        TafsirEntryResponse(
            surah=r.surah, ayah=r.ayah, source=r.source,
            attribution=r.attribution, text=r.text,
            cached=r.cached, error=r.error,
        )
        for r in results
    ]

    # Build formatted display from first successful result
    formatted = FALLBACK_MESSAGE
    for r in results:
        if r.ok:
            formatted = format_tafsir_for_display(r)
            break

    return TafsirResponse(
        surah=surah, ayah=ayah,
        results=entry_responses, formatted=formatted,
    )


@router.get("/{surah}/{ayah}/ayah-text", response_model=AyahTextResponse)
async def get_ayah_text(surah: int, ayah: int):
    """جلب نص آية قرآنية بالرسم العثماني فقط."""
    if not (1 <= surah <= 114):
        raise HTTPException(status_code=400, detail="رقم السورة يجب أن يكون 1-114")
    if ayah < 1:
        raise HTTPException(status_code=400, detail="رقم الآية يجب أن يكون ≥ 1")

    text = await fetch_ayah_text(surah, ayah)
    return AyahTextResponse(surah=surah, ayah=ayah, text=text)


@router.get("/{surah}/{ayah}/nuzool", response_model=NuzoolResponse)
async def get_nuzool_reason(surah: int, ayah: int):
    """جلب سبب نزول آية."""
    if not (1 <= surah <= 114):
        raise HTTPException(status_code=400, detail="رقم السورة يجب أن يكون 1-114")
    if ayah < 1:
        raise HTTPException(status_code=400, detail="رقم الآية يجب أن يكون ≥ 1")

    result = await fetch_nuzool_reason(surah, ayah)
    if result is None or not result.ok:
        raise HTTPException(
            status_code=404,
            detail="لا يتوفر سبب نزول موثّق لهذه الآية",
        )

    return NuzoolResponse(
        surah=surah, ayah=ayah,
        attribution=result.attribution,
        text=result.text,
        formatted=format_tafsir_for_display(result),
    )


@router.get("/sources", response_model=SourceListResponse)
async def get_sources():
    """فهرس مصادر التفسير المتاحة."""
    sources = await list_tafsir_sources()
    return SourceListResponse(sources=sources)


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """بحث نصي في آيات القرآن."""
    results = await search_quran(request.query, request.limit)
    return SearchResponse(results=results)


@router.post("/search-tafsir", response_model=SearchResponse)
async def search_tafsir(request: SearchRequest):
    """بحث LIKE داخل تفسير معين."""
    results = await search_in_tafsir(
        request.query, source=request.source, limit=request.limit
    )
    return SearchResponse(results=results)