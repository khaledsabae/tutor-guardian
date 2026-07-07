"""Pydantic models for «ميزان العادات» — age-dynamic habit/value tracker.

Tracks daily habit completion for children aged 10–18 across three
categories: worship, self_building, study. All habit names are free-text
but filtered to keep tracking strictly behavioural — no medical
diagnosis, medication, or dosage content is accepted.
"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# ── Enums as simple string constants ─────────────────────────────────────────
CATEGORIES = {"worship", "self_building", "study"}
STATUSES = {"completed", "partially", "missed"}

# Reuse the same medical-term guard as the daily_routine models to keep
# the feature inside its declared scope: habit tracking, not medical records.
_MEDICAL_TERMS_RE = re.compile(
    r"(?:\b|\s)(جرعة|دواء|دواء|أدوية|علاج|مرض|تشخيص|سكر|ضغط|حمة|حمى|إسهال|قيء|طفح|عدوى|"
    r"infection|diagnosis|medication|dosage|dose|medicine|fever|rash|vomit|diarrhea)(?:\b|\s)",
    re.IGNORECASE,
)


def _no_medical_terms(value: str) -> str:
    """Reject habit names that contain medical/diagnosis/dosage terms."""
    if _MEDICAL_TERMS_RE.search(value):
        raise ValueError(
            "اسم العادة لا يجب أن يحتوي على مصطلحات طبية أو أدوية أو جرعات. "
            "استخدم الميزة لتسجيل العادات اليومية فقط."
        )
    return value


# ── Input models ───────────────────────────────────────────────────────────


class HabitEventCreate(BaseModel):
    """Parent-submitted habit evaluation for one of the three categories."""

    category: str
    habit_name: str = Field(max_length=200)
    status: str

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in CATEGORIES:
            raise ValueError(f"التصنيف غير صالح. القيم المسموحة: {sorted(CATEGORIES)}")
        return v

    @field_validator("habit_name")
    @classmethod
    def _validate_habit_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("اسم العادة مطلوب.")
        return _no_medical_terms(v)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in STATUSES:
            raise ValueError(f"حالة التقييم غير صالحة. القيم المسموحة: {sorted(STATUSES)}")
        return v


# ── Output models ──────────────────────────────────────────────────────────


class HabitEventOut(BaseModel):
    id: int
    child_id: int
    category: str
    habit_name: str
    status: str
    created_at: str
    updated_at: str


class HabitDayOut(BaseModel):
    child_id: int
    date: str
    events: list[HabitEventOut]
    points: float = 0.0


class HabitSummaryOut(BaseModel):
    days: int
    total_completed: int
    total_partially: int
    total_missed: int
    by_category: dict[str, dict[str, int]]
    total_points: float = 0.0


class HabitDeleteOut(BaseModel):
    deleted: int