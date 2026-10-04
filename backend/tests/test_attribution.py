"""Install-referrer contract — the link the server builds vs. what reads it.

Two readers parse the `referrer` we put on a Google Play link, and neither can
be changed from here (the app parser ships in builds that stay live for weeks):

* the app — mobile/lib/features/referral/referral_service.dart upper-cases the
  referrer and claims the first REF_([A-Z0-9]{4,16}) it finds;
* Firebase Analytics — reads utm_* from the referrer as a query string, which is
  what fills GA4's first-user source / medium / campaign.

Each test below decodes the Play URL the way Play does (once) and then asserts
what each reader would see.
"""
import re
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from app.services import attribution as at

# Verbatim from referral_service.dart (`_codeRe`), applied to the upper-cased
# referrer exactly as `captureAndClaimOnFirstRun` does.
_APP_RE = re.compile(r"REF_([A-Z0-9]{4,16})")


def _referrer(play_url: str) -> str | None:
    """The string Play hands to the app: the `referrer` param, decoded once."""
    assert play_url.startswith(at.PLAY_URL)
    values = parse_qs(urlsplit(play_url).query).get("referrer")
    return values[0] if values else None


def _app_claims(play_url: str) -> str | None:
    ref = _referrer(play_url)
    m = _APP_RE.search((ref or "").upper())
    return m.group(1) if m else None


def _firebase_utm(play_url: str) -> dict[str, str]:
    ref = _referrer(play_url) or ""
    return {k: v[0] for k, v in parse_qs(ref).items() if k.startswith("utm_")}


# ── The legacy format is untouched ─────────────────────────────────────────

def test_a_bare_link_has_no_referrer():
    assert at.play_install_url() == at.PLAY_URL


def test_a_referral_alone_keeps_the_exact_legacy_link():
    # /api/referral/me has handed this exact string to every installed app.
    assert at.play_install_url("ABC234") == f"{at.PLAY_URL}&referrer=ref_ABC234"


# ── Both readers get what they need from one link ──────────────────────────

def test_the_app_and_firebase_both_read_a_combined_referrer():
    url = at.play_install_url("DA01", {"utm_source": "facebook", "utm_medium": "paid",
                                       "utm_campaign": "ramadan_2027"})
    assert _app_claims(url) == "DA01"
    assert _firebase_utm(url) == {"utm_source": "facebook", "utm_medium": "paid",
                                  "utm_campaign": "ramadan_2027"}


def test_utm_alone_reaches_firebase_and_leaves_the_app_on_its_auto_fallback():
    url = at.play_install_url(None, {"utm_source": "facebook", "utm_campaign": "boost"})
    assert _app_claims(url) is None  # → the app tries the AUTO (IP) claim
    assert _firebase_utm(url) == {"utm_source": "facebook", "utm_campaign": "boost"}


def test_free_text_campaign_names_survive_both_encodings():
    # Meta's {{campaign.name}} expands to whatever the ad manager typed.
    name = "رمضان Boost #1 & more"
    url = at.play_install_url(None, {"utm_campaign": name})
    assert _firebase_utm(url) == {"utm_campaign": name}


@pytest.mark.parametrize("value", ["xref_ZZZZ", "pref_ABCDEF", "REF_ABC234"])
def test_a_utm_value_can_never_be_claimed_as_a_referral_code(value):
    # The app's regex is unanchored: an unescaped `ref_ZZZZ` inside a utm value
    # would be claimed, 404, and burn the install's one claim attempt.
    url = at.play_install_url(None, {"utm_content": value})
    assert _app_claims(url) is None
    assert _firebase_utm(url) == {"utm_content": value}
    url = at.play_install_url("DA01", {"utm_content": value})
    assert _app_claims(url) == "DA01"


# ── Input normalisation ─────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,code", [
    ("DA01", "DA01"), ("da01", "DA01"), (" Da-01 ", "DA01"), ("kt_001", "KT001"),
    ("ABC234", "ABC234"),
])
def test_codes_are_normalised(raw, code):
    assert at.normalize_code(raw) == code


@pytest.mark.parametrize("raw", [None, "", "AB", "A" * 17, "DA01<script>", "دعاة"])
def test_malformed_codes_are_dropped(raw):
    assert at.normalize_code(raw) is None


def test_utm_values_are_bounded_and_unknown_params_ignored():
    utm = at.clean_utm({"utm_source": "x" * 500, "utm_medium": "  ", "fbclid": "abc",
                        "utm_term": "a\x00b"})
    assert utm == {"utm_source": "x" * at.UTM_MAX_CHARS, "utm_term": "ab"}


# ── Campaign codes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["DA01", "DA10", "EN05", "WAAR", "WAEN", "KT001",
                                  "CM01", "PD01", "OT01"])
def test_the_marketing_kit_codes_are_campaign_codes(code):
    # docs/marketing/2026-10-ramadan/00_README.md hands these out.
    assert at.is_campaign_code(code)


@pytest.mark.parametrize("code", ["ABC234", "C0001", "NOPE99", "AUTO", "DA", "DA0"])
def test_other_codes_are_not_campaign_codes(code):
    assert not at.is_campaign_code(code)


@pytest.mark.parametrize("code", ["ENV9Z5", "DA2345", "WAXYZK"])
def test_a_device_code_that_starts_like_a_campaign_is_still_a_person(code):
    # ENV9Z5 is a real device code in production (read-only, 2026-10-04); a
    # prefix-only rule credited its owner's invites to "English preachers".
    assert at.is_device_shaped(code)
    assert not at.is_campaign_code(code)
    assert at.attribution_utm(code, {}) == {}


def test_no_generated_device_code_is_ever_a_campaign_code():
    from app.routers.referral import _gen_code

    assert not any(at.is_campaign_code(_gen_code()) for _ in range(5000))


def test_a_campaign_link_tells_ga4_the_campaign_without_hand_typed_utm():
    utm = at.attribution_utm("DA01", {})
    assert utm == {"utm_source": "preacher_ar", "utm_medium": "social",
                   "utm_campaign": "DA01"}
    assert _firebase_utm(at.play_install_url("DA01", utm))["utm_campaign"] == "DA01"


def test_explicit_utm_wins_over_campaign_defaults():
    utm = at.attribution_utm("PD01", {"utm_source": "facebook", "utm_campaign": "رمضان"})
    assert utm == {"utm_source": "facebook", "utm_medium": "paid",
                   "utm_campaign": "رمضان"}


def test_personal_codes_get_no_invented_utm():
    assert at.attribution_utm("ABC234", {}) == {}


def test_a_campaign_owner_can_never_be_a_real_device_id():
    # POST /api/chat/sessions only admits ^[A-Za-z0-9._:-]+$ — a client can
    # never mint a session as the campaign and read its invite count.
    from app.models.api import SessionCreate

    owner = at.campaign_owner("DA01")
    with pytest.raises(ValueError):
        SessionCreate(device_id=owner)


def test_every_campaign_code_fits_the_app_parser():
    longest = "DA" + "9" * (16 - 2)
    assert at.is_campaign_code(longest)
    assert _app_claims(at.play_install_url(longest)) == longest
    assert not at.is_campaign_code(longest + "9")
