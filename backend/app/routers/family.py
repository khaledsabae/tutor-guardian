"""«قناديل الأسبوع» — the family's week of parenting acts (نور والقناديل, Phase 3).

GET /api/family/week (Bearer device auth) lights one lantern per parenting act
of the calling device in its local ISO week. What counts is decided once, in
services/family_actions.py — the same registry the weekly funnel report reads —
and worship acts never light a lantern. Contract: MOBILE_API.md §12.

No proven session is needed: the answer carries kinds, times, child ids and
curriculum titles only — never a child's name, a question, a fact or a
follow-up's text. An app on a server without this route gets a 404 and hides
the lanterns.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

from app.routers.children import _require_device_id
from app.services import family_actions

router = APIRouter()


@router.get("/family/week", summary="This week's lanterns: the family's parenting acts")
def family_week(request: Request,
                tz_offset_minutes: Optional[int] = Query(None, ge=-720, le=840),
                lang: Optional[str] = Query(None)):
    device_id = _require_device_id(request)
    lang = lang or request.headers.get("accept-language")
    return family_actions.family_week(device_id, tz_offset_minutes=tz_offset_minutes,
                                      lang=lang)
