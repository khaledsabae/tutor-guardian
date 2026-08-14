"""The age filter must narrow ranking, not decide reachability.

`retrieve_relevant_units` filters the vector leg to the child's own age band
plus "unspecified". That is right when the corpus holds a unit for the child's
band and blind when it does not: a unit written for 4-6 is invisible to a 7-9
parent. The domain-only fallback inside that function does not rescue it,
because it only fires when the age-filtered query returns *nothing at all* —
and half the corpus is "unspecified", so it never does.

Measured on the 23 hand-authored gap units, before this leg existed: at the
unit's own age the target reached the delivered top-4 in 17/23 cases, at a
neighbouring age in 7/23. These tests lock the mechanism that closed that gap,
without asserting the scores themselves (which move with the corpus).
"""
from unittest.mock import patch

from app.services import retrieval


def _fake_hit(uid, age):
    return {"unit_id": uid, "age_group": age, "text_simplified": uid}


def test_hybrid_queries_the_domain_without_the_age_filter():
    """A leg that ignores age must run on every hybrid call, not only when
    the age-filtered leg comes back empty."""
    with patch.object(retrieval, "retrieve_relevant_units",
                      return_value=[_fake_hit("age-matched", "7-9")]) as vec, \
         patch.object(retrieval, "retrieve_domain_only",
                      return_value=[_fake_hit("other-band", "4-6")]) as any_age, \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=lambda q, c, top_n: c):
        bm25.return_value.search.return_value = []
        out = retrieval.retrieve_hybrid(
            query_text="ابني بيكذب", domains=["islamic_parenting"],
            age_group="7-9",
        )

    assert vec.called, "the age-filtered leg must still run"
    assert any_age.called, "the age-free leg must run unconditionally"
    ids = {u["unit_id"] for u in out}
    assert "other-band" in ids, (
        "a unit outside the child's age band has to be reachable — it is "
        "ranked below the age-matched one, not hidden from the pool"
    )


def test_age_matched_unit_outranks_the_off_band_one():
    """The age-free leg is additive. A unit in the child's own band appears in
    both vector legs and so carries twice the RRF credit — which is what keeps
    the matched case from regressing when the pool widens."""
    matched = _fake_hit("age-matched", "7-9")
    off_band = _fake_hit("other-band", "4-6")

    with patch.object(retrieval, "retrieve_relevant_units",
                      return_value=[dict(matched)]), \
         patch.object(retrieval, "retrieve_domain_only",
                      return_value=[dict(off_band), dict(matched)]), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=lambda q, c, top_n: c):
        bm25.return_value.search.return_value = []
        out = retrieval.retrieve_hybrid(
            query_text="ابني بيكذب", domains=["islamic_parenting"],
            age_group="7-9",
        )

    assert out[0]["unit_id"] == "age-matched"


def test_rerank_pool_is_capped_so_extra_legs_cannot_grow_it():
    """The cross-encoder's cost is linear in the pool it is handed. The extra
    leg is meant to change *which* candidates get scored, not how many — an
    uncapped pool cost ~875ms per answer and demoted good candidates."""
    wide = [_fake_hit(f"u{i}", "unspecified") for i in range(40)]
    seen = {}

    def capture(query, candidates, top_n):
        seen["n"] = len(candidates)
        return candidates[:top_n]

    with patch.object(retrieval, "retrieve_relevant_units", return_value=wide), \
         patch.object(retrieval, "retrieve_domain_only", return_value=wide), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=capture):
        bm25.return_value.search.return_value = []
        retrieval.retrieve_hybrid(
            query_text="ابني بيكذب", domains=["islamic_parenting"],
            age_group="7-9", rerank_pool=12,
        )

    assert seen["n"] == 12, f"reranker was handed {seen['n']} candidates, not 12"


def test_domain_only_leg_does_not_filter_by_age():
    """Guards the one line that matters: no age predicate reaches Chroma."""
    captured = {}

    def fake_query(collection, text, where, top_k):
        captured["where"] = where
        return []

    with patch.object(retrieval, "with_live_collection", lambda fn: None), \
         patch.object(retrieval, "_query", side_effect=fake_query):
        retrieval.retrieve_domain_only("ابني بيكذب", "islamic_parenting", top_k=4)

    assert "age_group" not in repr(captured["where"])
