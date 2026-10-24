"""The reranker no longer hands back an irrelevant unit just to avoid an empty list.

Before: `filtered or kept[:1]` ("never return nothing"). A question the KB cannot
answer got its single nearest unit however irrelevant: a teen-doubt unit as the
ONLY result for a router-configuration question and a TikTok follow-up
(scores -6.7 / -7.2). Now an absolute floor (RERANK_MIN_SCORE, applied to the
BEST candidate) returns an empty NoConfidentMatch, and `_off_topic` routes it
exactly as it routed the lone below-floor unit before (the off-topic pivot).
"""
import pytest

from app.routers import assistant
from app.services import reranker
from app.services.reranker import NoConfidentMatch


class _FakeModel:
    def __init__(self, scores):
        self.scores = scores

    def predict(self, pairs, show_progress_bar=False):
        return self.scores[: len(pairs)]


def _rerank(monkeypatch, scores, top_n=4):
    monkeypatch.setattr(reranker, "_get_model", lambda: _FakeModel(scores))
    monkeypatch.setattr(reranker, "RERANK_ENABLED", True)
    monkeypatch.setattr(reranker, "_disabled", False)
    cands = [{"unit_id": f"u{i}", "document": f"passage: d{i}"} for i in range(len(scores))]
    return reranker.rerank("q", cands, top_n=top_n)


def test_confident_candidates_are_returned_best_first_and_tail_trimmed(monkeypatch):
    out = _rerank(monkeypatch, [-4.0, 1.5, -7.0, -2.0])
    assert [c["unit_id"] for c in out] == ["u1", "u3", "u0"]  # u2 is under the tail floor
    assert not isinstance(out, NoConfidentMatch)


def test_nothing_clears_the_floor_returns_an_empty_marker_not_the_nearest_unit(monkeypatch):
    out = _rerank(monkeypatch, [-6.7, -9.0, -8.2])
    assert out == [] and not out
    assert isinstance(out, NoConfidentMatch)
    assert out.best_rerank_score == pytest.approx(-6.7)


def test_the_floor_is_the_tail_filter_applied_to_the_best_candidate(monkeypatch):
    monkeypatch.setattr(reranker, "RERANK_MIN_SCORE", -5.0)
    assert isinstance(_rerank(monkeypatch, [-5.1, -8.0]), NoConfidentMatch)
    out = _rerank(monkeypatch, [-5.0, -4.0, -7.0])  # best == -4.0 clears it; -5.0 is still >= floor
    assert [c["unit_id"] for c in out] == ["u1", "u0"]


def test_a_disabled_or_failing_reranker_is_not_a_no_match(monkeypatch):
    # No scores were produced, so there is nothing to call irrelevant: the
    # fusion order is returned as before and callers do not pivot.
    monkeypatch.setattr(reranker, "RERANK_ENABLED", False)
    cands = [{"unit_id": "a", "document": "x"}, {"unit_id": "b", "document": "y"}]
    assert [c["unit_id"] for c in reranker.rerank("q", cands, top_n=1)] == ["a"]
    assert reranker.rerank("q", [], top_n=4) == []
    assert not isinstance(reranker.rerank("q", [], top_n=4), NoConfidentMatch)


def test_off_topic_treats_the_marker_like_the_old_lone_low_unit():
    assert assistant._off_topic(NoConfidentMatch(-6.7)) == (True, -6.7)
    # old shape still routes the same way
    assert assistant._off_topic([{"unit_id": "x", "rerank_score": -6.7}]) == (True, -6.7)
    # a genuinely empty result is not "off-topic": it takes the "no information" reply
    assert assistant._off_topic([]) == (False, None)
    # tafsir enrichment (rerank_score 1.0) inserted into the marker list is evidence
    enriched = NoConfidentMatch(-7.0)
    enriched.insert(0, {"unit_id": "tafsir_2_255", "rerank_score": 1.0})
    assert assistant._off_topic(enriched) == (False, 1.0)


def test_hybrid_keeps_the_marker_through_the_language_branch(monkeypatch):
    from unittest.mock import patch

    from app.services import retrieval

    hit = {"unit_id": "u1", "age_group": "7-9", "text_simplified": "u1"}
    with patch.object(retrieval, "retrieve_relevant_units", return_value=[dict(hit)]), \
         patch.object(retrieval, "retrieve_domain_only", return_value=[]), \
         patch("app.services.bm25_index.get_bm25") as bm25, \
         patch("app.services.reranker.rerank",
               side_effect=lambda q, c, top_n: NoConfidentMatch(-7.2)):
        bm25.return_value.search.return_value = []
        for lang in (None, "ar"):
            out = retrieval.retrieve_hybrid("سؤال", ["fiqh"], "7-9", lang=lang)
            assert out == [] and isinstance(out, NoConfidentMatch)
            assert assistant._off_topic(out) == (True, -7.2)


# ── through the real /draft route: what the parent actually receives ────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config.guardrails_loader import load_guardrails_config
    from app.db.init_db import init_db
    from app.main import app
    from app.services import fiqh_guard

    monkeypatch.setenv("CONVERSATIONS_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(fiqh_guard, "_log_block", lambda *a, **k: None)
    init_db()
    app.state.guardrails_config = load_guardrails_config()
    return TestClient(app)


def _auth(c, device):
    r = c.post("/api/chat/sessions", json={"device_id": device})
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["session_id"]


def _ask(c, headers, **body):
    base = {"age_group": "7-9", "severity": "خفيف", "message_text": "x"}
    return c.post("/api/assistant/draft", headers=headers, json={**base, **body})


def _route(monkeypatch, units):
    seen = {"generate_reply": 0, "pivot": 0}

    async def _classify(q):
        return ["development"], ""

    async def _no_ayah(_q):
        return None

    async def _pivot(*a, **k):
        seen["pivot"] += 1
        return "جواب عام قصير ثم نشاط تربوي."

    async def _reply(*a, **k):
        seen["generate_reply"] += 1
        return "جواب مبني على الوحدات"

    monkeypatch.setattr(assistant, "_classify_and_rewrite", _classify)
    monkeypatch.setattr(assistant, "resolve_ayah_reference", _no_ayah)
    monkeypatch.setattr(assistant, "_ensure_index", lambda: None)
    monkeypatch.setattr(assistant, "retrieve_hybrid", lambda **k: units)
    monkeypatch.setattr(assistant, "log_retrieval", lambda *a, **k: None)
    monkeypatch.setattr(assistant, "generate_general_pivot", _pivot)
    monkeypatch.setattr(assistant, "generate_reply", _reply)
    monkeypatch.setattr("app.services.answer_cache.lookup", lambda *a, **k: None)
    return seen


def test_route_no_confident_match_pivots_and_never_grounds_on_a_unit(client, monkeypatch):
    seen = _route(monkeypatch, NoConfidentMatch(-6.7))
    h, _ = _auth(client, "dev-floor-1")
    body = _ask(client, h, message_text="إزاي أظبط إعدادات راوتر لحجب مواقع؟").json()
    assert body["mode"] == "general_pivot"
    assert body["metadata"]["off_topic"] is True and body["metadata"]["sources"] == []
    assert seen == {"generate_reply": 0, "pivot": 1}


def test_route_plain_empty_result_keeps_the_no_information_reply(client, monkeypatch):
    seen = _route(monkeypatch, [])
    h, _ = _auth(client, "dev-floor-2")
    body = _ask(client, h, message_text="سؤال تربوي بلا وحدات").json()
    assert body["metadata"]["off_topic"] is False
    assert "لا توجد معلومات كافية" in body["reply_text"]
    assert seen == {"generate_reply": 0, "pivot": 0}


def test_route_a_confident_unit_still_grounds_the_answer(client, monkeypatch):
    unit = {"unit_id": "u1", "document": "passage: نصيحة", "rerank_score": -2.0,
            "metadata": {"domain": "development", "title": "t", "reference_info": "r"},
            "source_domain": "development"}
    seen = _route(monkeypatch, [unit])
    h, _ = _auth(client, "dev-floor-3")
    body = _ask(client, h, message_text="ابني لا ينام مبكرا").json()
    assert body["mode"] == "llm_generated"
    assert seen["generate_reply"] == 1 and seen["pivot"] == 0
