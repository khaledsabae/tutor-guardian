"""Several domains must read as one search over their union, not N searches.

`retrieve_hybrid` used to give every domain its own vector / band-free /
BM25 legs. Each domain's top hit then earned the same rank-0 credit however
weak it was, so on the five-domain fallback list (15 equal legs) the pool the
cross-encoder scored was "each domain's best, in turn". A unit that is the best
match in the *right* domain but has no lexical hit earns two credits against
the three of a weak neighbour, and a batch of new units in a neighbouring
domain is enough to push it out of the 12-wide pool entirely
(«الإسلام دين قديم», golden g-003: fused position 5 → 33).

Each leg *type* is now merged across the domains by its own score (vector
distance / BM25 score — comparable, one embedding and one corpus-wide index),
then cut to the depth one domain's leg has. A single domain is the identity.
"""
from unittest.mock import patch

from app.services import retrieval


def _hit(uid, dist=None, bm25=None):
    c = {"unit_id": uid, "metadata": {"age_group": "unspecified"},
         "document": uid, "text_simplified": uid}
    if dist is not None:
        c["distance"] = dist
    if bm25 is not None:
        c["bm25_score"] = bm25
    return c


def _run(vec_by_domain, domains, any_by_domain=None, lex_by_domain=None,
         fusion="global", pool=12, rewritten=""):
    """Run retrieve_hybrid over fake legs; returns the candidate list the
    cross-encoder would have been handed (i.e. the fused pool, in order)."""
    seen = {}

    def fake_vec(query_text, domain, age_group, top_k=5, behavior_type="", embed=None):
        return [dict(c) for c in vec_by_domain.get(domain, [])][:top_k]

    def fake_any(query_text, domain, top_k=5, embed=None):
        return [dict(c) for c in (any_by_domain or {}).get(domain, [])][:top_k]

    def fake_rerank(q, cands, top_n=4):
        seen["pool"] = list(cands)
        return cands[:top_n]

    with patch.object(retrieval, "_DOMAIN_FUSION", fusion), \
         patch.object(retrieval, "query_embedder", return_value=lambda t: [0.0]), \
         patch.object(retrieval, "retrieve_relevant_units", side_effect=fake_vec), \
         patch.object(retrieval, "retrieve_domain_only", side_effect=fake_any), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=fake_rerank):
        bm25.return_value.search.side_effect = (
            lambda q, domain=None, top_k=8: [dict(c) for c in (lex_by_domain or {}).get(domain, [])][:top_k])
        retrieval.retrieve_hybrid(
            query_text="سؤال", domains=domains, age_group="unspecified",
            rewritten_query=rewritten, rerank_pool=pool, top_n=100)
    return [c["unit_id"] for c in seen["pool"]]


def test_single_domain_is_unchanged():
    vec = {"medical": [_hit(f"v{i}", 0.1 + i / 100) for i in range(8)]}
    lex = {"medical": [_hit(f"l{i}", bm25=9.0 - i) for i in range(8)]}
    anyl = {"medical": [_hit(f"v{i}", 0.1 + i / 100) for i in range(4)]}
    a = _run(vec, ["medical"], anyl, lex, fusion="global", pool=30)
    b = _run(vec, ["medical"], anyl, lex, fusion="per_domain", pool=30)
    assert a == b and len(a) == 16


def test_closest_hits_win_across_domains():
    """The legacy fusion interleaves the domains' top hits; the merged legs
    order them by how close they actually are."""
    vec = {
        "medical": [_hit("m1", 0.10), _hit("m2", 0.12)],
        "cyber": [_hit("c1", 0.50), _hit("c2", 0.60)],
    }
    new = _run(vec, ["medical", "cyber"], fusion="global")
    old = _run(vec, ["medical", "cyber"], fusion="per_domain")
    assert new[:4] == ["m1", "m2", "c1", "c2"]
    assert old[:4] == ["m1", "c1", "m2", "c2"]


def test_weak_domains_do_not_crowd_the_pool():
    """Four domains with nothing close must not take pool slots from the one
    domain that has the answer."""
    strong = [_hit(f"s{i}", 0.10 + i / 100) for i in range(6)]
    vec = {"islamic_parenting": strong}
    for d in ("medical", "cyber", "development", "aqeedah"):
        vec[d] = [_hit(f"{d}-{i}", 0.55 + i / 100) for i in range(8)]
    domains = ["medical", "cyber", "islamic_parenting", "development", "aqeedah"]
    new = _run(vec, domains, fusion="global", pool=6)
    old = _run(vec, domains, fusion="per_domain", pool=6)
    assert sum(u.startswith("s") for u in new) == 6
    assert sum(u.startswith("s") for u in old) < 6


def test_each_leg_keeps_the_depth_of_a_single_domain():
    """Merging must not let the candidate list grow with the number of
    domains — the pool, and so the reranker's cost, is bounded by design."""
    vec = {d: [_hit(f"{d}-{i}", 0.2 + i / 100) for i in range(8)] for d in ("a", "b", "c")}
    pool = _run(vec, ["a", "b", "c"], fusion="global", pool=100)
    assert len(pool) == 8
    legacy = _run(vec, ["a", "b", "c"], fusion="per_domain", pool=100)
    assert len(legacy) == 24


def test_aliased_domains_do_not_earn_double_credit():
    """`fiqh` and `islamic_parenting` are one stored domain; listing both must
    not hand its units two legs' worth of credit."""
    vec = {"fiqh": [_hit("u1", 0.1), _hit("u2", 0.2)],
           "islamic_parenting": [_hit("u1", 0.1), _hit("u2", 0.2)],
           "cyber": [_hit("x1", 0.15)]}
    new = _run(vec, ["fiqh", "islamic_parenting", "cyber"], fusion="global")
    assert new == ["u1", "x1", "u2"]


def test_hits_without_a_distance_do_not_crash_and_keep_domain_order():
    vec = {"a": [_hit("a1"), _hit("a2")], "b": [_hit("b1")]}
    assert _run(vec, ["a", "b"], fusion="global") == ["a1", "a2", "b1"]


def test_bm25_leg_is_merged_by_score_highest_first():
    lex = {"a": [_hit("a1", bm25=3.0)], "b": [_hit("b1", bm25=9.0), _hit("b2", bm25=1.0)]}
    out = _run({}, ["a", "b"], lex_by_domain=lex, fusion="global")
    assert out == ["b1", "a1", "b2"]


def test_second_query_gets_its_own_merged_legs():
    vec = {"a": [_hit("a1", 0.1)], "b": [_hit("b1", 0.2)]}
    out = _run(vec, ["a", "b"], fusion="global", rewritten="صياغة أخرى")
    assert out == ["a1", "b1"]
