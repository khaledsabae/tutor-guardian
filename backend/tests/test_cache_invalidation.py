"""Rebuilding the knowledge index must drop the answers derived from it.

A cached answer freezes what the units said when it was generated, «📚 المصادر»
line included. After the citation repairs on 2026-07-29 the live app still
served the pre-fix source line for an already-asked question, and would have
kept doing so for the 45-day TTL.
"""
import app.services.answer_cache as answer_cache
from app.services import retrieval


def _seed(monkeypatch, tmp_path, rows=3):
    monkeypatch.setattr(answer_cache, "ANSWER_CACHE_ENABLED", True)
    monkeypatch.setattr(answer_cache, "_DB", tmp_path / "cache.db")
    monkeypatch.setattr(answer_cache, "_embed", lambda text: [0.1, 0.2, 0.3])
    for i in range(rows):
        answer_cache.store(f"سؤال رقم {i}", "7-9", "medical", "خفيف", "إجابة " * 40)


def _count(tmp_path):
    conn = answer_cache._conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0]
    finally:
        conn.close()


def test_purge_empties_the_cache_and_reports_the_count(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    assert _count(tmp_path) == 3
    assert answer_cache.purge("test") == 3
    assert _count(tmp_path) == 0


def test_purge_is_a_no_op_when_the_cache_is_disabled(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    monkeypatch.setattr(answer_cache, "ANSWER_CACHE_ENABLED", False)
    assert answer_cache.purge() == 0
    monkeypatch.setattr(answer_cache, "ANSWER_CACHE_ENABLED", True)
    assert _count(tmp_path) == 3, "disabled must mean untouched, not emptied"


def test_a_broken_cache_never_breaks_the_caller(monkeypatch):
    monkeypatch.setattr(answer_cache, "ANSWER_CACHE_ENABLED", True)
    monkeypatch.setattr(answer_cache, "_conn", lambda: (_ for _ in ()).throw(OSError("disk gone")))
    assert answer_cache.purge() == 0


def test_rebuilding_the_index_purges_the_cache(monkeypatch):
    """The wiring, not just the helper: a rebuild must reach purge()."""
    called = {}
    monkeypatch.setattr(answer_cache, "purge",
                        lambda reason="": called.setdefault("reason", reason) or 0)

    class _Collection:
        id = "c1"
        def get(self, *a, **k): return {"ids": []}
        def add(self, **k): pass
        def count(self): return 0

    monkeypatch.setattr(retrieval, "_get_collection", lambda: _Collection())
    monkeypatch.setattr(retrieval, "with_live_collection", lambda op: op(_Collection()))
    monkeypatch.setattr(retrieval, "_hnsw_is_bloated", lambda c: False)
    monkeypatch.setattr(retrieval, "_index_matches", lambda c, u, f: False)
    monkeypatch.setattr(retrieval, "_fingerprint", lambda u: "fp")
    monkeypatch.setattr(retrieval, "_fingerprint_path",
                        lambda: type("P", (), {"write_text": lambda self, t: None})())

    retrieval.index_knowledge_units([])
    assert "reason" in called, "a rebuild must invalidate the answers derived from it"
