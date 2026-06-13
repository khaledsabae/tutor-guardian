"""Taxonomy + age/domain normalization tests."""
from app.core.taxonomy import (
    CANONICAL_DOMAINS, DOMAIN_ALIASES, canonical_domain,
    CANONICAL_AGE_GROUPS, CANONICAL_SEVERITIES, CANONICAL_INTERVENTIONS,
)
from app.services.age_normalization import normalize_age_group
from app.services.domain_classifier import classify_domains


def test_domain_aliases_resolve_to_canonical():
    assert canonical_domain("fiqh") == "islamic_parenting"
    assert canonical_domain("tarbiyah") == "islamic_parenting"
    assert canonical_domain("digital_safety") == "cyber"


def test_canonical_domain_passthrough():
    for d in CANONICAL_DOMAINS:
        assert canonical_domain(d) == d


def test_aliases_map_into_canonical_set():
    for target in DOMAIN_ALIASES.values():
        assert target in CANONICAL_DOMAINS


def test_age_normalization():
    # The 0-3 band was split into prenatal-1 (pregnancy→1yr) + 2-3.
    assert normalize_age_group("infant") == "prenatal-1"
    assert normalize_age_group("0-3") == "prenatal-1"  # legacy alias
    assert normalize_age_group("13-15") == "13-15"
    assert normalize_age_group(None) == "unspecified"
    assert normalize_age_group("nonsense") == "unspecified"
    assert normalize_age_group("infant") in CANONICAL_AGE_GROUPS


def test_classifier_returns_known_domain():
    domains = classify_domains("كيف أعلم ابني الصلاة والقرآن؟")
    assert "fiqh" in domains  # classifier emits input-domain; alias → islamic_parenting


def test_canonical_sets_nonempty():
    assert CANONICAL_SEVERITIES and CANONICAL_INTERVENTIONS
