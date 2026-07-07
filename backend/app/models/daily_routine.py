"""Pydantic models for the «حِساب اليوم» daily routine tracker.

All datetimes are ISO8601 strings. Notes are free-text but filtered to keep
routine tracking strictly behavioral — no medical diagnosis, medication, or
dosage content is accepted.
"""
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ── Enums as simple string constants ─────────────────────────────────────────
EVENT_TYPES = {"sleep", "feed", "diaper"}
FEED_TYPES = {"breast", "bottle", "solid"}
SIDES = {"left", "right", "both"}
DIAPER_TYPES = {"wet", "dirty", "both"}
SOURCES = {"manual", "reminder", "recurring"}

# Terms we never accept in parent-supplied notes (Arabic + English). This is a
# lightweight guard, not a clinical safety system; it keeps the feature inside
# its declared scope: routine tracking, not medical records.
_MEDICAL_TERMS_RE = re.compile(
    r"(?:\b|\s)(جرعة|دواء|دواء|أدوية|علاج|مرض|تشخيص|سكر|ضغط|حمة|حمى|إسهال|قيء|طفح|عدوى|"
    r"infection|diagnosis|medication|dosage|dose|medicine|fever|rash|vomit|diarrhea)(?:\b|\s)",
    re.IGNORECASE,
)


def _parse_iso(value: str | None) -> str | None:
    """Validate and normalise an ISO8601 timestamp."""
    if value is None:
        return value
    # Accept Python datetime ISO; reject ambiguous strings.
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("التوقيت يجب أن يكون بتنسيق ISO8601") from exc
    return dt.isoformat()


def _no_medical_notes(value: str | None) -> str | None:
    """Reject notes that contain medical/diagnosis/dosage terms."""
    if value is None:
        return value
    if _MEDICAL_TERMS_RE.search(value):
        raise ValueError(
            "الملاحظات لا يجب أن تحتوي على مصطلحات طبية أو أدوية أو جرعات. "
            "استخدم الميزة لتسجيل الروتين اليومي فقط."
        )
    return value


# ── Input models ───────────────────────────────────────────────────────────

class RoutineEventCreate(BaseModel):
    """Parent-submitted event for one of the three supported routine types."""

    event_type: str
    started_at: str
    ended_at: str | None = None
    feed_type: str | None = None
    amount_ml: int | None = Field(default=None, ge=0, le=1000)
    side: str | None = None
    diaper_type: str | None = None
    notes: str | None = Field(default=None, max_length=500)
    source: str = "manual"

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in EVENT_TYPES:
            raise ValueError(f"نوع الحدث غير صالح. القيم المسموحة: {sorted(EVENT_TYPES)}")
        return v

    @field_validator("started_at", "ended_at")
    @classmethod
    def _validate_iso(cls, v: str | None) -> str | None:
        return _parse_iso(v)

    @field_validator("feed_type")
    @classmethod
    def _validate_feed_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in FEED_TYPES:
            raise ValueError(f"نوع الرضاعة غير صالح. القيم المسموحة: {sorted(FEED_TYPES)}")
        return v

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in SIDES:
            raise ValueError(f"الجانب غير صالح. القيم المسموحة: {sorted(SIDES)}")
        return v

    @field_validator("diaper_type")
    @classmethod
    def _validate_diaper_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in DIAPER_TYPES:
            raise ValueError(f"نوع الحفاظ غير صالح. القيم المسموحة: {sorted(DIAPER_TYPES)}")
        return v

    @field_validator("source")
    @classmethod
    def _validate_source(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in SOURCES:
            raise ValueError(f"المصدر غير صالح. القيم المسموحة: {sorted(SOURCES)}")
        return v

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, v: str | None) -> str | None:
        return _no_medical_notes(v)


# ── Output models ──────────────────────────────────────────────────────────

class RoutineEventOut(BaseModel):
    id: int
    routine_id: int
    event_type: str
    started_at: str
    ended_at: str | None
    feed_type: str | None
    amount_ml: int | None
    side: str | None
    diaper_type: str | None
    notes: str | None
    source: str
    created_at: str
    updated_at: str


class RoutineDayOut(BaseModel):
    routine_id: int
    child_id: int
    routine_date: str
    events: list[RoutineEventOut]


class RoutineSummaryOut(BaseModel):
    days: int
    total_sleep_minutes: int
    total_feed_count: int
    total_feed_amount_ml: int
    diaper_count: int


class RoutineDeleteOut(BaseModel):
    deleted: int
