"""Age-group normalization mapping.

Maps free-text age groups found in raw PDF metadata to the canonical enum
used by the KnowledgeUnit schema.
"""

# mapping: raw -> canonical
_AGE_MAP: dict[str, str] = {
    "adolescent":      "13-15",
    "all":             "unspecified",
    "infant":          "0-3",
    "toddler":         "4-6",
    "preschool":       "4-6",
    "school_age":      "7-9",
    "middle_childhood":"7-9",
    "late_childhood":  "10-12",
    # canonical values pass through unchanged
    "0-3":             "0-3",
    "4-6":             "4-6",
    "7-9":             "7-9",
    "10-12":           "10-12",
    "13-15":           "13-15",
    "16-18":           "16-18",
    "unspecified":     "unspecified",
    "":                "unspecified",
}

# The canonical enum values we accept after normalisation
CANONICAL_AGE_GROUPS: set[str] = {
    "0-3", "4-6", "7-9", "10-12", "13-15", "16-18", "unspecified",
}


def normalize_age_group(raw: str | None) -> str:
    """Return canonical age group or 'unspecified' if unknown."""
    if raw is None:
        return "unspecified"
    key = str(raw).strip().lower()
    return _AGE_MAP.get(key, "unspecified")


def is_valid_age_group(value: str) -> bool:
    """True if the value is already a canonical enum member."""
    return value in CANONICAL_AGE_GROUPS


def list_unknown_age_groups(raw_values: list[str]) -> list[str]:
    """Return distinct raw strings that have no explicit mapping."""
    out: set[str] = set()
    for v in raw_values:
        key = str(v).strip().lower()
        if key not in _AGE_MAP:
            out.add(v)
    return sorted(out)
