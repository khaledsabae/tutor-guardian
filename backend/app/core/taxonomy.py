"""
Canonical taxonomy — مصدر الحقيقة الوحيد لمفردات قاعدة المعرفة
================================================================
Single source of truth for the controlled vocabularies used across the
knowledge base, retrieval, and the integrity guard.

Why this exists: the schema (JSON), the data (units/*.json), the classifier
(input domains), and the retrieval layer historically drifted apart — e.g. the
schema said domain ∈ {medical, fiqh, tarbiyah, cyber} while the data actually
used {medical, cyber, islamic_parenting, development}. Centralizing the
vocabulary here, and having check_kb_integrity.py assert the JSON schema agrees
with it, prevents that class of silent drift.

Two distinct concepts:
- CANONICAL_*   : the values actually STORED in knowledge units on disk.
- DOMAIN_ALIASES: API/classifier INPUT values mapped onto canonical storage
                  domains (the schema can't express this — it's runtime).
"""

# ── Storage domains (what a unit's `domain` field may be) ───────────────────
CANONICAL_DOMAINS: set[str] = {
    "medical",
    "cyber",
    "islamic_parenting",
    "development",
}

# ── Input-domain aliases → canonical storage domain ─────────────────────────
# The domain_classifier emits `fiqh`; older code used `tarbiyah`/`digital_safety`.
# These are NOT valid stored domains — they are normalized to canonical here.
DOMAIN_ALIASES: dict[str, str] = {
    "fiqh": "islamic_parenting",
    "tarbiyah": "islamic_parenting",
    "digital_safety": "cyber",
}

# ── Age groups (kept in sync with age_normalization) ────────────────────────
CANONICAL_AGE_GROUPS: set[str] = {
    "0-3", "4-6", "7-9", "10-12", "13-15", "16-18", "unspecified",
}

# ── Severity levels ─────────────────────────────────────────────────────────
CANONICAL_SEVERITIES: set[str] = {"خفيف", "متوسط", "شديد", "طارئ"}

# ── Intervention types ──────────────────────────────────────────────────────
CANONICAL_INTERVENTIONS: set[str] = {"وقائي", "إرشادي", "علاجي", "إحالة_لطبيب"}

# ── Reference types (optional field; expanded to match real corpus) ─────────
CANONICAL_REFERENCE_TYPES: set[str] = {
    "DSM-5",
    "كتاب_فقهي",
    "حديث",
    "كتاب_تربوي",
    "تقرير_سيبراني",
    "إرشاد_مهني",
    "مقال_تنموي",
    "تقرير_طبي",
    "مقال_تربوي",
}


def canonical_domain(value: str) -> str:
    """Map an input/alias domain to its canonical storage form.

    Unknown values pass through unchanged so the caller/guard can flag them.
    """
    if not value:
        return value
    key = value.strip()
    return DOMAIN_ALIASES.get(key, key)
