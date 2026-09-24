"""Audit M7: one embedding per distinct query text per request.

retrieve_hybrid runs domains × queries × two vector legs, plus each leg's
domain-only fallback. Each of those used to pass Chroma the *text*, so the
e5 model encoded the same question up to 18 times for one answer. The legs
now share a per-request memo and hand Chroma the vector.
"""
from unittest.mock import patch

from app.services import retrieval


class _FakeCollection:
    def __init__(self):
        self.calls = []

    def query(self, **kw):
        self.calls.append(kw)
        # Nothing matches the banded query, so the domain-only fallback runs
        # too — the worst case for re-embedding.
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}


def test_each_query_text_is_embedded_once_per_request():
    fake = _FakeCollection()
    embedded = []

    def fake_embed(text):
        embedded.append(text)
        return [0.1, 0.2, 0.3]

    with patch.object(retrieval, "with_live_collection", side_effect=lambda op: op(fake)), \
         patch.object(retrieval, "embed_query", side_effect=fake_embed), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank", side_effect=lambda q, c, top_n: c):
        bm25.return_value.search.return_value = []
        retrieval.retrieve_hybrid(
            query_text="ابني بيزعق", rewritten_query="نوبات غضب الطفل",
            domains=["medical", "behavioral", "islamic_parenting"], age_group="4-6",
        )

    # 3 domains × 2 queries × (banded + fallback + band-free) Chroma queries…
    assert len(fake.calls) == 18
    # …and every one of them searched by vector, not by text.
    assert all("query_embeddings" in c and "query_texts" not in c for c in fake.calls)
    # …but only two encodes: one per distinct text.
    assert sorted(embedded) == sorted(["ابني بيزعق", "نوبات غضب الطفل"])


def test_the_vector_matches_the_text_path_prefix():
    # embed_query and the text path must search the same vector: both apply
    # the e5 "query: " prefix.
    seen = []
    with patch.object(retrieval, "_embedder", return_value=lambda texts: seen.extend(texts) or [[0.0]]):
        retrieval.embed_query("سؤال")
    assert seen == ["query: سؤال"]
