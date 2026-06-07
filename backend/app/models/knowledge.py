"""
Pydantic model for a single knowledge unit matching the JSON Schema.
"""
from datetime import datetime
from pydantic import BaseModel, Field


class KnowledgeUnit(BaseModel):
    """وحدة معرفة واحدة – طبي / شرعي / تربوي / سيبراني."""

    id: str
    domain: str  # "medical", "fiqh", "tarbiyah", "cyber"
    age_group: str  # "0-3", "4-6", "7-9", "10-12", "13-15", "16-18"
    behavior_type: str
    intervention_type: str = "إرشادي"  # "وقائي", "إرشادي", "علاجي", "إحالة_لطبيب"
    severity: str = "خفيف"  # "خفيف", "متوسط", "شديد", "طارئ"
    reference_type: str = ""
    reference_info: str = ""
    jurisdiction: str | None = None
    text_original: str = ""
    text_simplified: str = ""
    labels: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0"
    source_meta: dict | None = None
