"""The child-surface policy is a gate, so these tests are mostly refusals.

The shipped file loading correctly is one test. The other nineteen are
malformed files that must raise — because the failure this suite exists to
prevent is not "the policy is wrong", it is "the policy is wrong and the
server started anyway". A gate that silently falls back to defaults is
indistinguishable, from the outside, from a gate that works.
"""
import copy

import pytest
import yaml

from app.config.guardrails_loader import (
    ChildSurfacePolicy,
    ChildSurfacePolicyError,
    load_child_surface_policy,
)
from app.core.taxonomy import CHILD_SURFACE_AGE_BANDS


@pytest.fixture
def raw():
    """The shipped policy, as a mutable dict for the mutation tests below."""
    from app.config.guardrails_loader import DEFAULT_CHILD_SURFACE_PATH

    with DEFAULT_CHILD_SURFACE_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _write(tmp_path, data):
    target = tmp_path / "child_surface.yaml"
    target.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return target


def _expect_rejection(tmp_path, data, fragment: str):
    with pytest.raises(ChildSurfacePolicyError) as excinfo:
        load_child_surface_policy(_write(tmp_path, data))
    assert fragment in str(excinfo.value)


# ── The shipped file ───────────────────────────────────────────────────────

def test_shipped_policy_loads():
    policy = load_child_surface_policy()
    assert isinstance(policy, ChildSurfacePolicy)
    assert set(policy.age_bands) == set(CHILD_SURFACE_AGE_BANDS)


def test_shipped_policy_forbids_screens_under_two():
    band = load_child_surface_policy().band("under-2")
    assert band.screen_allowed is False
    assert band.allowed_surfaces == ()
    assert band.parent_message_key


def test_shipped_policy_gives_two_to_three_audio_only():
    band = load_child_surface_policy().band("2-3")
    assert band.screen_allowed is False
    assert band.allowed_surfaces == ("screen_off",)


def test_shipped_policy_disables_free_text_for_every_band():
    """Sprint 3 owns the topic whitelist. Until it lands, no band types."""
    policy = load_child_surface_policy()
    for name in CHILD_SURFACE_AGE_BANDS:
        assert policy.band(name).allow_free_text is False, name


def test_agreement_surface_exists_and_is_free():
    """A child does not pay screen time to read a covenant made about them —
    and without this surface the Sprint 2 entry gate cannot open at all."""
    policy = load_child_surface_policy()
    assert policy.surface("agreement").counts_toward_budget is False
    for name in ("4-6", "7-9", "10-12", "13-15", "16-18"):
        assert "agreement" in policy.band(name).allowed_surfaces, name


def test_screen_off_never_bills_screen_time():
    assert load_child_surface_policy().surface("screen_off").counts_toward_budget is False


def test_defaults_are_folded_into_every_band():
    policy = load_child_surface_policy()
    for name in CHILD_SURFACE_AGE_BANDS:
        band = policy.band(name)
        assert band.daily_budget_minutes > 0
        assert band.session_max_minutes > 0
        assert band.heartbeat_grace_seconds > band.heartbeat_interval_seconds


# ── Refusals ───────────────────────────────────────────────────────────────

def test_missing_file_raises(tmp_path):
    with pytest.raises(ChildSurfacePolicyError):
        load_child_surface_policy(tmp_path / "nope.yaml")


def test_malformed_yaml_raises(tmp_path):
    target = tmp_path / "child_surface.yaml"
    target.write_text("version: '1.0.0'\n  bad indent: [", encoding="utf-8")
    with pytest.raises(ChildSurfacePolicyError):
        load_child_surface_policy(target)


def test_non_mapping_raises(tmp_path):
    target = tmp_path / "child_surface.yaml"
    target.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ChildSurfacePolicyError):
        load_child_surface_policy(target)


def test_unknown_major_version_raises(tmp_path, raw):
    raw["version"] = "2.0.0"
    _expect_rejection(tmp_path, raw, "unsupported policy major version")


def test_misspelled_key_raises_rather_than_defaulting(tmp_path, raw):
    """The whole reason for extra='forbid'. `daily_budget_minute` silently
    ignored would mean a band running on the default budget while the file
    says otherwise — a gate that lies in review."""
    raw["age_bands"]["7-9"]["daily_budget_minute"] = 5
    _expect_rejection(tmp_path, raw, "invalid")


def test_missing_band_raises(tmp_path, raw):
    del raw["age_bands"]["10-12"]
    _expect_rejection(tmp_path, raw, "missing=['10-12']")


def test_unknown_band_raises(tmp_path, raw):
    raw["age_bands"]["19-25"] = {"screen_allowed": True, "allowed_surfaces": ["story"]}
    _expect_rejection(tmp_path, raw, "unknown=['19-25']")


def test_undeclared_surface_raises(tmp_path, raw):
    raw["age_bands"]["7-9"]["allowed_surfaces"].append("tiktok")
    _expect_rejection(tmp_path, raw, "undeclared surfaces")


def test_opening_the_under_two_band_raises(tmp_path, raw):
    """The medical line. If this ever becomes editable, the app stops being
    able to tell parents anything about screen time with a straight face."""
    raw["age_bands"]["under-2"]["screen_allowed"] = True
    raw["age_bands"]["under-2"]["allowed_surfaces"] = ["story"]
    _expect_rejection(tmp_path, raw, "must have screen_allowed=false")


def test_no_screen_band_may_not_allow_a_billing_surface(tmp_path, raw):
    """screen_allowed=false plus a surface that charges screen time is the
    gate contradicting itself one line later."""
    raw["age_bands"]["2-3"]["allowed_surfaces"] = ["screen_off", "story"]
    _expect_rejection(tmp_path, raw, "screen-billing surfaces")


def test_enabling_free_text_in_defaults_raises(tmp_path, raw):
    raw["defaults"]["allow_free_text"] = True
    _expect_rejection(tmp_path, raw, "topic whitelist")


def test_enabling_free_text_for_a_band_raises(tmp_path, raw):
    """The exact line the plan shipped for 13-15 and 16-18, two sprints ahead
    of the whitelist that makes it safe."""
    raw["age_bands"]["13-15"]["allow_free_text"] = True
    _expect_rejection(tmp_path, raw, "topic whitelist")


def test_session_longer_than_the_day_raises(tmp_path, raw):
    raw["age_bands"]["7-9"]["session_max_minutes"] = 90
    _expect_rejection(tmp_path, raw, "exceeds")


def test_exit_ritual_longer_than_a_third_of_the_surface_raises(tmp_path, raw):
    raw["surfaces"]["mission"]["exit_ritual_seconds"] = 60
    _expect_rejection(tmp_path, raw, "third or more")


def test_grace_shorter_than_the_heartbeat_interval_raises(tmp_path, raw):
    raw["defaults"]["heartbeat_grace_seconds"] = 10
    _expect_rejection(tmp_path, raw, "must exceed heartbeat_interval_seconds")


def test_zero_and_negative_budgets_raise(tmp_path, raw):
    for value in (0, -5):
        broken = copy.deepcopy(raw)
        broken["age_bands"]["7-9"]["daily_budget_minutes"] = value
        _expect_rejection(tmp_path, broken, "invalid")


def test_closed_band_without_a_parent_message_raises(tmp_path, raw):
    del raw["age_bands"]["under-2"]["parent_message_key"]
    _expect_rejection(tmp_path, raw, "parent_message_key")


def test_open_band_with_no_surfaces_raises(tmp_path, raw):
    raw["age_bands"]["7-9"]["allowed_surfaces"] = []
    _expect_rejection(tmp_path, raw, "opens onto nothing")


def test_unknown_band_lookup_raises_rather_than_guessing(raw):
    """`band()` takes a mapped band, never a raw age_group column. A caller
    that skips taxonomy.map_profile_age_to_band gets an error, not a default."""
    policy = load_child_surface_policy()
    with pytest.raises(KeyError):
        policy.band("0-3")
    with pytest.raises(KeyError):
        policy.band("unspecified")
