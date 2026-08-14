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
    "aqeedah",
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
    "prenatal-1", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18", "unspecified",
}

# The same bands in developmental order, which the set above cannot express.
# Retrieval needs "how far apart are these two ages" to keep a 16-18 unit out
# of a 4-6 parent's answer — see `age_bands_apart`.
ORDERED_AGE_GROUPS: tuple[str, ...] = (
    "prenatal-1", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18",
)

# The 0-3 band was split into "prenatal-1" (pregnancy→1yr) + "2-3". Existing
# children/units created before the split still carry "0-3" — alias it onto
# the new canonical band so they keep resolving instead of being orphaned.
AGE_ALIASES: dict[str, str] = {
    "0-3": "prenatal-1",
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


def canonical_age_group(value: str) -> str:
    """Map a legacy/alias age group (e.g. "0-3") to its canonical band.

    Unknown values pass through unchanged.
    """
    if not value:
        return value
    key = value.strip()
    return AGE_ALIASES.get(key, key)


# Reverse alias map (canonical → legacy labels) so equivalence is bidirectional.
_REVERSE_AGE_ALIASES: dict[str, list[str]] = {}
for _legacy, _canon in AGE_ALIASES.items():
    _REVERSE_AGE_ALIASES.setdefault(_canon, []).append(_legacy)


def age_equivalents(value: str) -> list[str]:
    """All age-group labels equivalent to `value` (itself + its alias both
    ways). Lets content stored under the legacy "0-3" label keep matching
    after the split to "prenatal-1" without renaming every curriculum file.
    """
    if not value:
        return [value]
    key = value.strip()
    out = {key, canonical_age_group(key)}
    out.update(_REVERSE_AGE_ALIASES.get(canonical_age_group(key), []))
    return list(out)


def age_bands_apart(a: str, b: str) -> int | None:
    """How many bands separate two age groups, or None when the question does
    not apply — "unspecified" content is written for every age, and an
    unrecognised label must not be silently treated as adjacent.

    Callers use this to keep obviously wrong-age material out of an answer:
    advice for a 16-18 year old is not a near miss for a 4-6 year old, it is a
    different childhood.
    """
    ca, cb = canonical_age_group(a or ""), canonical_age_group(b or "")
    if ca not in ORDERED_AGE_GROUPS or cb not in ORDERED_AGE_GROUPS:
        return None
    return abs(ORDERED_AGE_GROUPS.index(ca) - ORDERED_AGE_GROUPS.index(cb))
