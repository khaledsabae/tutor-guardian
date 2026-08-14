"""Wrong-childhood material must not reach a parent's answer.

The vector leg has always been filtered to the child's band, but BM25 never
was, and the band-free vector leg added later reached anywhere too. Measured
across the probe set, 31% of everything delivered sat two or more bands away
from the child: a question about a four-year-old's tantrums answered with
material written for a 16-18 year old, and one about an eight-year-old wetting
the bed answered with ADHD and bereavement.

Bounding the two unbanded legs to the neighbouring band improved every axis at
once — target reachability at the child's own band 14/23 → 16/23, the gap case
4/11 → 5/11, and wrong-band material 31% → 0%. These tests hold the bound and
the two things it must not break: "unspecified" content, which is written for
every age, and the neighbouring band the gap case depends on.
"""
from unittest.mock import patch

import pytest

from app.core.taxonomy import age_bands_apart
from app.services import retrieval


def _hit(uid, age):
    return {"unit_id": uid, "metadata": {"age_group": age},
            "document": uid, "text_simplified": uid}


def _run(vec, any_age, lex, age_group="4-6", **kw):
    with patch.object(retrieval, "retrieve_relevant_units", return_value=vec), \
         patch.object(retrieval, "retrieve_domain_only", return_value=any_age), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=lambda q, c, top_n: c):
        bm25.return_value.search.return_value = lex
        out = retrieval.retrieve_hybrid(
            query_text="ابني بيزعق ويرمي حاجات", domains=["medical"],
            age_group=age_group, **kw)
    return {u["unit_id"] for u in out}


# ── The distance function ────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b,expected", [
    ("4-6", "4-6", 0),
    ("4-6", "7-9", 1),
    ("2-3", "4-6", 1),
    ("4-6", "16-18", 4),
    ("0-3", "2-3", 1),          # legacy label straddles the infancy boundary
])
def test_distance_between_bands(a, b, expected):
    assert age_bands_apart(a, b) == expected


@pytest.mark.parametrize("a,b", [
    ("unspecified", "4-6"),
    ("4-6", "unspecified"),
    ("", "4-6"),
    ("nonsense", "4-6"),
])
def test_distance_is_undefined_rather_than_zero(a, b):
    """Undefined must not collapse to 0 — that would silently make every
    unlabelled unit count as a perfect age match."""
    assert age_bands_apart(a, b) is None


# ── Infancy is not the band next door ────────────────────────────────────────

def test_infancy_costs_an_extra_step():
    """`prenatal-1` runs from pregnancy to the first birthday. The band table
    makes it look like 2-3's neighbour the way 4-6 neighbours 7-9, and on
    2026-08-14 that let a unit titled "Your baby at 2 months" answer a parent
    asking about a two-year-old's tantrum in the street."""
    assert age_bands_apart("prenatal-1", "2-3") == 2
    assert age_bands_apart("2-3", "prenatal-1") == 2
    assert age_bands_apart("prenatal-1", "4-6") == 3


def test_infancy_is_still_reachable_from_itself():
    assert age_bands_apart("prenatal-1", "prenatal-1") == 0


def test_the_legacy_label_is_not_charged_for_a_boundary_it_straddles():
    """"0-3" predates the split into prenatal-1 + 2-3, so a child still
    carrying it may well be three years old. It aliases onto prenatal-1 for
    lookup, but charging it the infancy step would cut those children off from
    2-3 material on the strength of a label nobody has updated — four
    production profiles still carry it."""
    assert age_bands_apart("0-3", "2-3") == 1
    assert age_bands_apart("0-3", "prenatal-1") == 1


def test_infant_material_does_not_reach_a_toddler_question():
    delivered = _run(
        vec=[],
        any_age=[_hit("two-month-old", "prenatal-1")],
        lex=[_hit("two-month-old-lex", "prenatal-1")],
        age_group="2-3",
    )
    assert delivered == set()


def test_a_widened_span_still_lets_infancy_through():
    """The surcharge must be a cost, not a ban — a parent of a one-year-old
    asking something the corpus only answers for toddlers still needs it."""
    delivered = _run(
        vec=[],
        any_age=[_hit("toddler-unit", "2-3")],
        lex=[],
        age_group="prenatal-1",
        age_span=2,
    )
    assert "toddler-unit" in delivered


# ── The bound ────────────────────────────────────────────────────────────────

def test_material_four_bands_away_is_dropped():
    delivered = _run(
        vec=[_hit("own-band", "4-6")],
        any_age=[_hit("teenager", "16-18")],
        lex=[_hit("teenager-lex", "13-15")],
        age_group="4-6",
    )
    assert "own-band" in delivered
    assert "teenager" not in delivered
    assert "teenager-lex" not in delivered


def test_the_neighbouring_band_still_gets_through():
    """The whole point of the band-free leg is reaching the nearest unit when
    the corpus has nothing for this child's age. A bound that kills that would
    undo the change it is bounding."""
    delivered = _run(
        vec=[],
        any_age=[_hit("next-door", "7-9")],
        lex=[],
        age_group="4-6",
    )
    assert "next-door" in delivered


def test_unspecified_is_never_filtered():
    """Half the corpus is 'unspecified' and it is written to apply at every
    age — filtering it would empty most answers."""
    delivered = _run(
        vec=[],
        any_age=[_hit("general", "unspecified")],
        lex=[_hit("general-lex", "unspecified")],
        age_group="4-6",
    )
    assert {"general", "general-lex"} <= delivered


def test_an_unreadable_band_is_kept_not_guessed():
    """A missing or malformed label is a data gap. Dropping it loses real
    content; treating it as adjacent would be inventing a fact."""
    delivered = _run(
        vec=[],
        any_age=[{"unit_id": "no-meta", "document": "x"}],
        lex=[_hit("weird-band", "toddler")],
        age_group="4-6",
    )
    assert {"no-meta", "weird-band"} <= delivered


def test_the_bound_can_be_widened_and_switched_off():
    far = lambda: (  # noqa: E731
        [], [_hit("teenager", "16-18")], [])

    assert "teenager" not in _run(*far(), age_group="4-6")
    assert "teenager" in _run(*far(), age_group="4-6", age_span=None)
    assert "teenager" in _run(*far(), age_group="4-6", age_span=4)


def test_the_child_own_band_leg_is_never_bounded():
    """The age-filtered leg is already correct by construction; running it
    through the bound as well would be a second chance to get it wrong."""
    with patch.object(retrieval, "retrieve_relevant_units",
                      return_value=[_hit("odd", "16-18")]) as vec, \
         patch.object(retrieval, "retrieve_domain_only", return_value=[]), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=lambda q, c, top_n: c):
        bm25.return_value.search.return_value = []
        out = retrieval.retrieve_hybrid(
            query_text="س", domains=["medical"], age_group="4-6")

    assert vec.called
    assert {u["unit_id"] for u in out} == {"odd"}


def test_bm25_over_fetches_so_the_bound_does_not_shorten_the_leg():
    """Filtering after a top-8 search would hand fusion fewer than 8 lexical
    candidates whenever wrong-band hits occupied the slots — the bound has to
    cost accuracy from the wrong-band units, not depth from the right ones."""
    asked = {}

    def search(q, domain=None, top_k=8):
        asked["top_k"] = top_k
        return [_hit(f"far{i}", "16-18") for i in range(top_k - 8)] + \
               [_hit(f"near{i}", "4-6") for i in range(8)]

    with patch.object(retrieval, "retrieve_relevant_units", return_value=[]), \
         patch.object(retrieval, "retrieve_domain_only", return_value=[]), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=lambda q, c, top_n: c):
        bm25.return_value.search.side_effect = search
        out = retrieval.retrieve_hybrid(
            query_text="س", domains=["medical"], age_group="4-6",
            candidates_per_leg=8)

    assert asked["top_k"] > 8, "BM25 must over-fetch before the bound trims it"
    assert len([u for u in out if u["unit_id"].startswith("near")]) == 8
