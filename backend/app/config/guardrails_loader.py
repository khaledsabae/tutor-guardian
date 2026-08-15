"""
Load guardrails policy YAML configuration.

Two policies live here and they are validated differently on purpose.

`policies.v1.yaml` drives the assistant's escalation and tone. A malformed
entry there degrades an answer, and the loader stays permissive: parse it,
check it is a mapping, hand it over.

`child_surface.v1.yaml` is an age gate and a time budget. A malformed entry
there is a toddler being handed a screen, or a fourteen-year-old typing free
text into a model that has no whitelist behind it yet. So it is parsed into a
strict schema with `extra="forbid"` — a misspelled key must be an error, never
a silently-applied default — and every cross-field invariant that the surface
depends on is asserted at load time. `main.py` calls it during startup with no
try/except: if the file is wrong the process does not boot. Serving with a
half-understood gate is the one outcome worse than being down.
"""
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.taxonomy import CHILD_SURFACE_AGE_BANDS

DEFAULT_POLICIES_PATH = (
    Path(__file__).resolve().parents[2] / "guardrails" / "policies.v1.yaml"
)

DEFAULT_CHILD_SURFACE_PATH = (
    Path(__file__).resolve().parents[2] / "guardrails" / "child_surface.v1.yaml"
)

# This loader understands major version 1. A file that bumps the major has
# changed shape, and the code that reads it has to change with it.
SUPPORTED_CHILD_SURFACE_MAJOR = 1

PositiveMinutes = Annotated[int, Field(gt=0, le=24 * 60)]
PositiveSeconds = Annotated[int, Field(gt=0, le=24 * 60 * 60)]


def load_guardrails_config(path: Path | None = None) -> dict:
    """Load and return the guardrails YAML configuration as a dict."""
    target = path or DEFAULT_POLICIES_PATH

    if not target.exists():
        raise FileNotFoundError(f"Guardrails policy file not found: {target}")

    try:
        with target.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"Guardrails config must be a mapping, got: {type(config)}")

        return config

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in guardrails config: {target}\n{e}") from e


# ── Child-surface policy schema ────────────────────────────────────────────


class ChildSurfacePolicyError(ValueError):
    """The child-surface policy is unusable. Never caught into a default."""


class SurfaceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counts_toward_budget: bool
    # Audio with the screen dark is not screen time by the medical definition,
    # so it does not bill the screen budget — but it still displaces sleep and
    # real play, so it bills its own. Naming the ledger here keeps the budget
    # service from hardcoding the string "screen_off".
    counts_toward_audio_budget: bool = False
    max_minutes: PositiveMinutes
    exit_ritual_seconds: PositiveSeconds

    @model_validator(mode="after")
    def _bills_at_most_one_ledger(self) -> "SurfaceSpec":
        if self.counts_toward_budget and self.counts_toward_audio_budget:
            raise ValueError("a surface cannot bill both the screen and audio budgets")
        return self

    @model_validator(mode="after")
    def _ritual_fits_inside_the_surface(self) -> "SurfaceSpec":
        # A one-minute goodbye on a three-minute mission card is a third of the
        # session spent saying goodbye. The ritual has to be a tail, not a leg.
        if self.exit_ritual_seconds * 3 >= self.max_minutes * 60:
            raise ValueError(
                f"exit_ritual_seconds={self.exit_ritual_seconds} is a third or more "
                f"of max_minutes={self.max_minutes}"
            )
        return self


class PolicyDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_budget_minutes: PositiveMinutes
    session_max_minutes: PositiveMinutes
    heartbeat_interval_seconds: PositiveSeconds
    heartbeat_grace_seconds: PositiveSeconds
    exit_ritual_seconds: PositiveSeconds
    allow_free_text: bool
    screen_off_daily_budget_minutes: PositiveMinutes

    @model_validator(mode="after")
    def _grace_outlives_an_interval(self) -> "PolicyDefaults":
        if self.heartbeat_grace_seconds <= self.heartbeat_interval_seconds:
            raise ValueError(
                "heartbeat_grace_seconds must exceed heartbeat_interval_seconds, "
                "or one dropped packet ends the session"
            )
        return self


class AgeBandSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    screen_allowed: bool
    allowed_surfaces: list[str]
    requires_parent_present: bool = False
    daily_budget_minutes: PositiveMinutes | None = None
    session_max_minutes: PositiveMinutes | None = None
    allow_free_text: bool | None = None
    parent_message_key: str | None = None
    parent_message_ar: str | None = None

    @model_validator(mode="after")
    def _a_closed_band_explains_itself(self) -> "AgeBandSpec":
        # A 403 with no explanation reads as a bug. The parent has to be told
        # what happened and what, if anything, they can do about it.
        if not self.screen_allowed and not self.parent_message_key:
            raise ValueError(
                "a band with screen_allowed=false needs a parent_message_key"
            )
        if self.screen_allowed and not self.allowed_surfaces:
            raise ValueError(
                "screen_allowed=true with no allowed_surfaces is a gate that "
                "opens onto nothing"
            )
        return self


class ResolvedBand(BaseModel):
    """A band with the defaults already folded in.

    Callers read this and never the raw mapping. Re-deriving "band value or
    else default" at each call site is how the age vocabulary drifted into
    three copies; the budget service will not repeat it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    band: str
    screen_allowed: bool
    requires_parent_present: bool
    allowed_surfaces: tuple[str, ...]
    daily_budget_minutes: int
    session_max_minutes: int
    screen_off_daily_budget_minutes: int
    heartbeat_interval_seconds: int
    heartbeat_grace_seconds: int
    allow_free_text: bool
    parent_message_key: str | None
    parent_message_ar: str | None


class ChildSurfacePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    defaults: PolicyDefaults
    age_bands: dict[str, AgeBandSpec]
    surfaces: dict[str, SurfaceSpec]

    @model_validator(mode="after")
    def _validate_policy(self) -> "ChildSurfacePolicy":
        major = self.version.split(".")[0]
        if not major.isdigit() or int(major) != SUPPORTED_CHILD_SURFACE_MAJOR:
            raise ValueError(
                f"unsupported policy major version {self.version!r}; this build "
                f"reads {SUPPORTED_CHILD_SURFACE_MAJOR}.x"
            )

        declared = set(self.age_bands)
        expected = set(CHILD_SURFACE_AGE_BANDS)
        if declared != expected:
            raise ValueError(
                f"age_bands must cover exactly the taxonomy bands; "
                f"missing={sorted(expected - declared)} unknown={sorted(declared - expected)}"
            )

        for name, band in self.age_bands.items():
            unknown = set(band.allowed_surfaces) - set(self.surfaces)
            if unknown:
                raise ValueError(f"band {name!r} allows undeclared surfaces {sorted(unknown)}")

            # A band that may not see a screen may still listen. What it may
            # not do is open a surface that bills screen time — that would be
            # the gate contradicting itself one line later.
            if not band.screen_allowed:
                billing = [s for s in band.allowed_surfaces
                           if self.surfaces[s].counts_toward_budget]
                if billing:
                    raise ValueError(
                        f"band {name!r} has screen_allowed=false but allows "
                        f"screen-billing surfaces {sorted(billing)}"
                    )

            session = band.session_max_minutes or self.defaults.session_max_minutes
            daily = band.daily_budget_minutes or self.defaults.daily_budget_minutes
            if session > daily:
                raise ValueError(
                    f"band {name!r}: session_max_minutes={session} exceeds "
                    f"daily_budget_minutes={daily}"
                )

        # The youngest band is the medical line, not a tunable. WHO and the
        # AAP both put a hard no before it, and the whole credibility of an app
        # that tells parents to limit screens rests on it refusing here first.
        if self.age_bands[CHILD_SURFACE_AGE_BANDS[0]].screen_allowed:
            raise ValueError(
                f"band {CHILD_SURFACE_AGE_BANDS[0]!r} must have screen_allowed=false"
            )

        # Free text for a child needs a topic whitelist in front of the model.
        # `intent_guard` is a blacklist and the whitelist is Sprint 3 work, so
        # this cannot be turned on by editing YAML alone — flipping it has to
        # mean deleting this check, which is a code review, which is the point.
        if self.defaults.allow_free_text:
            raise ValueError(
                "allow_free_text must be false until the topic whitelist exists "
                "(Sprint 3); a blacklist is not a child-safe default"
            )
        enabled = [n for n, b in self.age_bands.items() if b.allow_free_text]
        if enabled:
            raise ValueError(
                f"bands {sorted(enabled)} enable allow_free_text before the topic "
                f"whitelist exists (Sprint 3)"
            )

        return self

    def band(self, name: str) -> ResolvedBand:
        """The band with defaults folded in.

        Raises KeyError for an unknown band — callers must map a profile
        through `taxonomy.map_profile_age_to_band`, which fails closed, rather
        than passing a raw `age_group` column through to here.
        """
        spec = self.age_bands[name]
        d = self.defaults
        return ResolvedBand(
            band=name,
            screen_allowed=spec.screen_allowed,
            requires_parent_present=spec.requires_parent_present,
            allowed_surfaces=tuple(spec.allowed_surfaces),
            daily_budget_minutes=spec.daily_budget_minutes or d.daily_budget_minutes,
            session_max_minutes=spec.session_max_minutes or d.session_max_minutes,
            screen_off_daily_budget_minutes=d.screen_off_daily_budget_minutes,
            heartbeat_interval_seconds=d.heartbeat_interval_seconds,
            heartbeat_grace_seconds=d.heartbeat_grace_seconds,
            allow_free_text=(
                d.allow_free_text if spec.allow_free_text is None else spec.allow_free_text
            ),
            parent_message_key=spec.parent_message_key,
            parent_message_ar=spec.parent_message_ar,
        )

    def surface(self, name: str) -> SurfaceSpec:
        return self.surfaces[name]


def load_child_surface_policy(path: Path | None = None) -> ChildSurfacePolicy:
    """Parse and validate the child-surface policy, or raise.

    There is no default-on-failure branch by design. Every caller of this is
    an age gate or a time budget; a policy we could not read is a policy we
    cannot enforce, and enforcing nothing while looking like we enforce
    something is the failure mode this whole file exists to prevent.
    """
    target = path or DEFAULT_CHILD_SURFACE_PATH

    if not target.exists():
        raise ChildSurfacePolicyError(f"Child surface policy not found: {target}")

    try:
        with target.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ChildSurfacePolicyError(f"Invalid YAML in {target}:\n{e}") from e

    if not isinstance(raw, dict):
        raise ChildSurfacePolicyError(
            f"Child surface policy must be a mapping, got: {type(raw)}"
        )

    try:
        return ChildSurfacePolicy.model_validate(raw)
    except ValidationError as e:
        raise ChildSurfacePolicyError(f"Child surface policy is invalid: {target}\n{e}") from e
