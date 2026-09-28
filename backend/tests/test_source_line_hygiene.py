"""A reference_info that is not a source must never reach the parent.

The value is rendered as «📚 المصدر». 33 of the 1,122 units hold something that
is not a citation — a bare domain name, an empty string, leftover generation
instructions, or a placeholder — so without this filter the app answers a
question about a five-month-old and attributes it to "medical".
"""
import pytest

from app.services.llm_service import build_full_prompt, usable_reference


@pytest.mark.parametrize("ref", [
    "medical", "cyber", "fiqh", "development", "islamic_parenting",
    "MEDICAL", "  cyber  ",
    "", "   ", None,
    "أصل المصدر غير محدد",
    "العنوان المفقود للنص الأصلي",
    "شرح عربي واضح للأهل في 3-5 جمل، يذكر الأعراض والتعامل العملي",
])
def test_non_sources_are_rejected(ref):
    assert usable_reference(ref) is None


@pytest.mark.parametrize("ref", [
    "Centers for Disease Control and Prevention (CDC)",
    "المنهج النبوي في تربية الأولاد — الشيخ عدنان باحارث",
    "WHO ICD-11 Gaming Disorder (6C51)",
    "UNICEF",
    "Anxiety UK, unspecified year",
    # A real citation that merely lacks a date. A contains-check on «غير محدد»
    # would discard it — the placeholder list is matched exactly for this reason.
    "Children and Mental Health — NIMH, (غير محددة)",
])
def test_real_sources_survive(ref):
    assert usable_reference(ref) == ref.strip()


def _unit(ref, text="نص الوحدة"):
    return {"document": text, "metadata": {"reference_info": ref, "domain": "medical"}}


def test_bogus_reference_is_kept_out_of_the_source_line():
    _, source_line = build_full_prompt(
        domain="medical", behavior_type="", age_group="4-6", severity="خفيف",
        retrieved_units=[_unit("medical"), _unit("UNICEF")],
    )
    assert "medical" not in source_line
    assert "UNICEF" in source_line


def test_context_tells_the_model_not_to_attribute_an_unsourced_passage():
    prompt, _ = build_full_prompt(
        domain="medical", behavior_type="", age_group="4-6", severity="خفيف",
        retrieved_units=[_unit("medical", "فقرة بلا مصدر")],
    )
    assert "فقرة بلا مصدر" in prompt          # the knowledge is still usable
    assert "لا تنسب هذه الفقرة" in prompt     # but the attribution is withheld


def test_all_bogus_falls_back_to_the_honest_default():
    _, source_line = build_full_prompt(
        domain="medical", behavior_type="", age_group="4-6", severity="خفيف",
        retrieved_units=[_unit("medical"), _unit("")],
    )
    assert source_line == "مصدر غير مذكور"


# ── Structured sources for the app's "Sources (n)" disclosure (UX-2, C8) ──────
from app.routers.assistant import _merge_retrieved  # noqa: E402
from app.models.api import UserMessage  # noqa: E402
from app.services.llm_service import MAX_REPLY_SOURCES, reply_sources  # noqa: E402


def test_reply_sources_filters_dedupes_and_keeps_order():
    units = [_unit("UNICEF"), _unit("medical"), _unit("CDC"), _unit("UNICEF"), _unit("")]
    assert reply_sources(units) == ["UNICEF", "CDC"]


def test_reply_sources_is_capped():
    units = [_unit(f"Source {i}") for i in range(MAX_REPLY_SOURCES + 3)]
    assert len(reply_sources(units)) == MAX_REPLY_SOURCES


def test_source_line_and_structured_sources_agree():
    units = [_unit("medical"), _unit("UNICEF"), _unit("CDC")]
    _, source_line = build_full_prompt(
        domain="medical", behavior_type="", age_group="4-6", severity="خفيف",
        retrieved_units=units,
    )
    assert source_line == " · ".join(reply_sources(units))


def test_merged_fallback_does_not_cite_a_non_source():
    msg = UserMessage(age_group="4-6", severity="خفيف", message_text="سؤال")
    text = _merge_retrieved(msg, [_unit("medical", "فقرة أولى"), _unit("UNICEF", "فقرة ثانية")])
    assert "فقرة أولى" in text and "فقرة ثانية" in text
    assert "📚 المصدر: medical" not in text
    assert "📚 المصدر: UNICEF" in text
    assert "مصدر غير مذكور" not in text
