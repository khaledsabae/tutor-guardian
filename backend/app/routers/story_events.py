"""«صورة حيّة» experiment — story reading events (POST /api/stories/events).

Khaled's question (2026-10-24): do children like the stories more with the
living pictures (camera following the narrator) or with the same paintings
standing still? Each device is in one arm for good (`motion` | `static`,
chosen on the device from a hash of its id while `/api/app-config` →
`story_motion_mode` is "ab"); the app reports what happened in a story here,
and the weekly report and ops/scripts/story_motion_verdict.py read it.

No PII: a device id (already the unit of every device count in the weekly
report), a bundled story id, a language code, page numbers and a 1–3 rating.
Nothing a parent or child typed. Rows that do not fit the vocabulary are
refused whole — analytics garbage costs more than a missing event.
"""
from __future__ import annotations

import re
from contextlib import closing
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.init_db import get_conn

router = APIRouter()

EVENT_NAMES = (
    "story_opened",
    "story_page_viewed",
    "story_finished",
    "story_rated",
    "story_closed_early",
)
_STORY_ID = re.compile(r"^[a-z0-9_]{1,64}$")
_LANG = re.compile(r"^[a-z]{2}$")


class StoryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal[
        "story_opened",
        "story_page_viewed",
        "story_finished",
        "story_rated",
        "story_closed_early",
    ]
    story_id: str
    lang: str
    variant: Literal["motion", "static"]
    narration_on: bool = False
    reduce_motion: bool = False
    page_index: int | None = Field(default=None, ge=0, le=50)
    rating: int | None = Field(default=None, ge=1, le=3)

    @field_validator("story_id")
    @classmethod
    def _story(cls, v: str) -> str:
        if not _STORY_ID.match(v):
            raise ValueError("story_id")
        return v

    @field_validator("lang")
    @classmethod
    def _lang(cls, v: str) -> str:
        if not _LANG.match(v):
            raise ValueError("lang")
        return v


class StoryEventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[StoryEvent] = Field(min_length=1, max_length=50)


def ensure_story_events_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS story_events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id     TEXT NOT NULL,
            name          TEXT NOT NULL,
            story_id      TEXT NOT NULL,
            lang          TEXT NOT NULL,
            variant       TEXT NOT NULL,
            narration_on  INTEGER NOT NULL DEFAULT 0,
            reduce_motion INTEGER NOT NULL DEFAULT 0,
            page_index    INTEGER,
            rating        INTEGER,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS ix_story_events_time "
        "ON story_events (created_at, variant, name)"
    )


@router.post("/stories/events", status_code=204)
async def record_story_events(batch: StoryEventBatch, request: Request) -> None:
    device_id = getattr(request.state, "device_id", None)
    if not device_id:
        raise HTTPException(status_code=401, detail="مطلوب توثيق.")
    with closing(get_conn()) as con:
        ensure_story_events_table(con)
        con.executemany(
            "INSERT INTO story_events (device_id, name, story_id, lang, variant, "
            "narration_on, reduce_motion, page_index, rating) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    device_id,
                    e.name,
                    e.story_id,
                    e.lang,
                    e.variant,
                    int(e.narration_on),
                    int(e.reduce_motion),
                    e.page_index,
                    e.rating,
                )
                for e in batch.events
            ],
        )
        con.commit()
