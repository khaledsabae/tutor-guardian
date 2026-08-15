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

# The labels above describe CONTENT. A person is a narrower question: a
# knowledge unit may be written for every age and carry "unspecified", but a
# child is never "unspecified" — accepting that label for a person would let a
# caller opt out of the age gate by omission. These are the labels an API
# caller may send when the subject is a child.
ADDRESSABLE_AGE_GROUPS: set[str] = set(ORDERED_AGE_GROUPS)
ACCEPTED_CHILD_AGE_INPUTS: set[str] = ADDRESSABLE_AGE_GROUPS | set(AGE_ALIASES)

# Habit templates only exist from school age up; younger bands have a routine,
# not a habit ledger. A subset of the vocabulary, not a competing one.
HABIT_AGE_GROUPS: set[str] = {"7-9", "10-12", "13-15", "16-18"}

# ── Child-surface bands (the age gate) ──────────────────────────────────────
# A separate axis from the bands above, and deliberately so: those answer
# "which content fits this child", this answers "may this child be shown a
# screen at all". WHO and the AAP put the first hard line before any screen
# exposure — the taxonomy's own line falls at 2 (prenatal-1 ends at 1yr, 2-3
# begins at 2), so the gate uses 2, which is the more conservative of the two
# readings and needs no birthdate the profiles do not carry.
CHILD_SURFACE_AGE_BANDS: tuple[str, ...] = (
    "under-2", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18",
)

# prenatal-1 spans pregnancy→1yr, so it maps onto the no-screen band. Every
# other canonical band keeps its label.
_PROFILE_BAND_TO_SURFACE_BAND: dict[str, str] = {"prenatal-1": "under-2"}

# The band a child falls into when we cannot tell. Failing to the strictest
# band is the only safe direction: the cost of being wrong is a parent seeing
# an explanation screen, versus an infant being handed a screen.
FALLBACK_CHILD_SURFACE_BAND = "under-2"

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


def map_profile_age_to_band(value: str | None) -> str:
    """The child-surface band a stored profile age falls into.

    Fails closed. Every input that is not a recognised developmental band —
    None, "", "unspecified", a typo, a label from a future migration — returns
    the no-screen band. Callers gate on the returned band alone and never on
    the raw column, so a profile that nobody has updated cannot open a session
    by being unreadable.

    The legacy "0-3" is the case that matters in production: four profiles
    still carry it, and it straddles infancy and toddlerhood. It aliases onto
    prenatal-1 and therefore onto "under-2" — a two-and-a-half-year-old whose
    parent never re-picked the age is refused the screen rather than an infant
    being granted one. The parent-facing message says which way to fix it.
    """
    canonical = canonical_age_group(value or "")
    if canonical not in ADDRESSABLE_AGE_GROUPS:
        return FALLBACK_CHILD_SURFACE_BAND
    return _PROFILE_BAND_TO_SURFACE_BAND.get(canonical, canonical)


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
    """How far apart two age groups are, or None when the question does not
    apply — "unspecified" content is written for every age, and an unrecognised
    label must not be silently treated as adjacent.

    Callers use this to keep obviously wrong-age material out of an answer:
    advice for a 16-18 year old is not a near miss for a 4-6 year old, it is a
    different childhood.

    The steps are not all the same size, so this is not a plain index gap.
    `prenatal-1` covers pregnancy through the first year — a pre-verbal infant —
    and the band table makes it look like 2-3's neighbour in exactly the way
    4-6 neighbours 7-9. It is not: on 2026-08-14 a parent asking about a
    two-year-old's tantrum in the street was answered with a unit titled "Your
    baby at 2 months". Crossing into or out of infancy therefore costs an extra
    step, which puts it out of reach at the default span of one band without
    forbidding it outright.
    """
    ra, rb = (a or "").strip(), (b or "").strip()
    ca, cb = canonical_age_group(ra), canonical_age_group(rb)
    if ca not in ORDERED_AGE_GROUPS or cb not in ORDERED_AGE_GROUPS:
        return None
    gap = abs(ORDERED_AGE_GROUPS.index(ca) - ORDERED_AGE_GROUPS.index(cb))
    # The surcharge keys on the literal label, not the canonical one. The
    # legacy "0-3" spans infancy AND toddlerhood, so a child still carrying it
    # may well be three years old; it aliases onto prenatal-1 for lookup, but
    # charging it for crossing a boundary it already straddles would cut those
    # children off from 2-3 material on the strength of a label nobody has
    # updated. Four production profiles still carry it.
    if (ra == "prenatal-1") != (rb == "prenatal-1"):
        gap += 1
    return gap
