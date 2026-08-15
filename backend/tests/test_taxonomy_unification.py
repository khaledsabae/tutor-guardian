"""The age vocabulary has one home.

Three copies of the age-group list used to live in the codebase — taxonomy,
program.py, and value_tracking.py — and they had already drifted: only
program.py carried the legacy "0-3", and only taxonomy carried "unspecified".
Any age gate built on top of that would have leaked at whichever copy it
happened to read. These tests fail if a fourth copy appears, or if one of the
existing imports is quietly replaced by a literal again.

The map_profile_age_to_band tests are the security half: every one of them
asserts a *refusal*, because the gate's job is to fail closed on input nobody
has curated.
"""
from app.core.taxonomy import (
    ACCEPTED_CHILD_AGE_INPUTS,
    ADDRESSABLE_AGE_GROUPS,
    CHILD_SURFACE_AGE_BANDS,
    FALLBACK_CHILD_SURFACE_BAND,
    HABIT_AGE_GROUPS,
    ORDERED_AGE_GROUPS,
    map_profile_age_to_band,
)
from app.routers import program, value_tracking


# ── One source of truth ────────────────────────────────────────────────────

def test_routers_import_the_age_vocabulary_rather_than_redeclaring_it():
    """Identity, not equality: an equal-but-separate literal is the exact bug
    this test exists to catch, and `==` would pass on it."""
    assert program._VALID_AGE_GROUPS is ACCEPTED_CHILD_AGE_INPUTS
    assert value_tracking.HABIT_AGE_GROUPS is HABIT_AGE_GROUPS


def test_program_accepts_the_same_values_it_did_before_unification():
    """The unification must not widen or narrow a live endpoint. This is the
    pre-change literal, spelled out."""
    assert ACCEPTED_CHILD_AGE_INPUTS == {
        "prenatal-1", "0-3", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18",
    }


def test_unspecified_is_not_a_child():
    """It describes content written for every age. Accepting it for a person
    would let a caller opt out of the age gate by omission."""
    assert "unspecified" not in ADDRESSABLE_AGE_GROUPS
    assert "unspecified" not in ACCEPTED_CHILD_AGE_INPUTS


def test_habit_bands_match_the_habit_content_they_gate():
    assert HABIT_AGE_GROUPS == set(value_tracking._DEFAULT_HABITS)


# ── The gate fails closed ──────────────────────────────────────────────────

def test_every_addressable_band_maps_to_a_declared_surface_band():
    for group in ORDERED_AGE_GROUPS:
        assert map_profile_age_to_band(group) in CHILD_SURFACE_AGE_BANDS


def test_infancy_maps_to_the_no_screen_band():
    assert map_profile_age_to_band("prenatal-1") == "under-2"


def test_legacy_0_3_maps_to_the_no_screen_band():
    """Four production profiles still carry it, and it straddles infancy and
    toddlerhood. Refusing a two-and-a-half-year-old is the recoverable error;
    handing an infant a screen is not."""
    assert map_profile_age_to_band("0-3") == "under-2"


def test_school_age_bands_keep_their_label():
    for group in ("2-3", "4-6", "7-9", "10-12", "13-15", "16-18"):
        assert map_profile_age_to_band(group) == group


def test_unreadable_ages_fail_closed():
    for value in (None, "", "   ", "unspecified", "0-18m", "18m-3", "3-6",
                  "42", "adult", "prenatal", "PRENATAL-1"):
        assert map_profile_age_to_band(value) == FALLBACK_CHILD_SURFACE_BAND, value


def test_the_fallback_band_is_the_strictest_one():
    assert FALLBACK_CHILD_SURFACE_BAND == CHILD_SURFACE_AGE_BANDS[0]
