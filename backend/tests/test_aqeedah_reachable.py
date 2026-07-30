"""The aqeedah domain must stay reachable, and «الله» must not become a catch-all.

Ten authored units — «من هو الله؟», «ما بعد الموت؟», «أسماء الله الحسنى» — sat in
the knowledge base unreachable: `aqeedah` is a canonical storage domain and has
an Arabic label in the answer renderer, but it was missing from the classifier's
VALID_DOMAINS, so no question could ever route there. «بنتي بقت تسأل عن الموت» —
a question the app itself suggests — had an exact match it could not retrieve.

The risk on the other side is worse than the gap: «الله» is among the most common
words in everyday Arabic (الحمد لله، إن شاء الله، ماشاء الله), so a bare token
rule would route nearly every question into aqeedah — the same substring failure
that made «سم» match «يسمع» and answer ordinary parenting questions with «اتصل
بالطوارئ». Both directions are asserted here.
"""
import pytest

from app.core.taxonomy import CANONICAL_DOMAINS, canonical_domain
from app.services.domain_classifier import (
    UNCERTAIN_DOMAINS,
    VALID_DOMAINS,
    _keyword_fast_path,
)


def test_classifier_can_emit_aqeedah():
    """The gap itself: a domain the renderer knows but the classifier can't reach."""
    assert "aqeedah" in VALID_DOMAINS
    assert "aqeedah" in CANONICAL_DOMAINS
    assert canonical_domain("aqeedah") == "aqeedah"


def test_uncertain_fallback_searches_aqeedah():
    """A failed classification searches every domain — aqeedah included."""
    assert "aqeedah" in UNCERTAIN_DOMAINS


@pytest.mark.parametrize("question", [
    "بنتي بقت تسأل عن الموت وأنا مش عارفة أرد",   # the app's own suggested question
    "ابني سألني عن الموت",
    "ابني بيسأل من هو الله",
    "طفلي بيسأل أين الله",
    "ابني بيسأل ليه خلقنا ربنا",
    "بنتي بتسأل عن الجنة والنار",
    "طفلي بيسأل عن الملائكة",
    "ابني بدأ يشك في الدين",
    "ابني سمع شبهات من صحابه",
])
def test_creed_questions_route_to_aqeedah(question):
    assert "aqeedah" in (_keyword_fast_path(question) or [])


@pytest.mark.parametrize("question", [
    # Everyday «الله» — the catch-all failure mode this rule must not have
    "الحمد لله ابني بقى أحسن",
    "إن شاء الله هيتحسن",
    "ماشاء الله على ابني",
    "والله مش عارفة أعمل إيه",
    # Ordinary parenting questions
    "ابني بيرفض الصلاة",
    "بنتي مش بتسمع الكلام",
    "ابني عنده قلق",
    "طفلي مابياكلش كويس",
    # Death as grief or fear — not a question about belief
    "جدي مات وابني حزين",
    "ابني شاف حادثة موت في الشارع",
    "خايفة على ابني من الموت",
])
def test_everyday_questions_do_not_route_to_aqeedah(question):
    assert "aqeedah" not in (_keyword_fast_path(question) or [])


def test_aqeedah_has_a_guardrail_policy():
    """A reachable domain with no policy answers with no review and no escalation.

    `development` shipped in exactly that state; aqeedah must not repeat it now
    that questions can actually land here.
    """
    from app.config.guardrails_loader import load_guardrails_config

    policy = load_guardrails_config()["domains"].get("aqeedah")
    assert policy, "aqeedah is reachable but has no guardrail policy"
    assert policy["default_policy"]["require_human_review"] is True
    assert policy["severity_overrides"]["شديد"]["escalate_to"] == "scholar"
