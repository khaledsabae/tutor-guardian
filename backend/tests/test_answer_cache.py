"""Semantic answer cache tests (growth plan §5.1)."""
import pytest

from app.services import answer_cache as ac

ANSWER = (
    "جرب أن تجعل الصلاة لحظة مشتركة: صلِّ أمامه بسكينة، وابدأ معه بسورة "
    "قصيرة، وامدحه ولو ركع ركعة واحدة. الاستمرارية أهم من الكمال.\n"
    "📚 المصدر: وحدة تحبيب الأطفال في الصلاة"
)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "_DB", tmp_path / "cache.db")
    monkeypatch.setattr(ac, "ANSWER_CACHE_ENABLED", True)
    # Default: no embedding model in tests — exact-match path only.
    monkeypatch.setattr(ac, "_embed", lambda text: None)
    yield


def test_exact_round_trip():
    assert ac.store("ابني لا يصلي", "4-6", "islamic_parenting", "خفيف", ANSWER)
    got = ac.lookup("ابني لا يصلي", "4-6", "islamic_parenting", "خفيف")
    assert got == ANSWER


def test_normalization_bridges_orthography_and_punctuation():
    ac.store("ابني لا يصلي", "4-6", "islamic_parenting", "خفيف", ANSWER)
    assert ac.lookup("إبني  لا يصلي!؟", "4-6", "islamic_parenting", "خفيف") == ANSWER


def test_scope_isolation():
    ac.store("ابني لا يصلي", "4-6", "islamic_parenting", "خفيف", ANSWER)
    assert ac.lookup("ابني لا يصلي", "7-9", "islamic_parenting", "خفيف") is None
    assert ac.lookup("ابني لا يصلي", "4-6", "medical", "خفيف") is None
    assert ac.lookup("ابني لا يصلي", "4-6", "islamic_parenting", "شديد") is None


def test_semantic_match_via_embeddings(monkeypatch):
    vecs = {
        ac.normalize("ابني لا يصلي"): [1.0, 0.0],
        ac.normalize("طفلي يرفض الصلاه"): [0.98, 0.198997],  # cos ≈ .98
        ac.normalize("ابني يكذب كثيرا"): [0.0, 1.0],
    }
    monkeypatch.setattr(ac, "_embed", lambda text: vecs.get(ac.normalize(text)))
    ac.store("ابني لا يصلي", "4-6", "islamic_parenting", "خفيف", ANSWER)
    # Different wording, same meaning → semantic hit.
    assert ac.lookup("طفلي يرفض الصلاة", "4-6", "islamic_parenting", "خفيف") == ANSWER
    # Orthogonal question → miss.
    assert ac.lookup("ابني يكذب كثيرًا", "4-6", "islamic_parenting", "خفيف") is None


def test_disabled_flag_bypasses_everything(monkeypatch):
    ac.store("سؤال ما للتخزين المسبق", "4-6", "development", "خفيف", ANSWER)
    monkeypatch.setattr(ac, "ANSWER_CACHE_ENABLED", False)
    assert ac.lookup("سؤال ما للتخزين المسبق", "4-6", "development", "خفيف") is None
    assert not ac.store("آخر", "4-6", "development", "خفيف", ANSWER)


def test_short_answers_rejected():
    assert not ac.store("سؤال", "4-6", "development", "خفيف", "رد قصير جدًا")


def test_ttl_expiry(monkeypatch):
    ac.store("ابني لا يصلي", "4-6", "islamic_parenting", "خفيف", ANSWER)
    conn = ac._conn()
    conn.execute("UPDATE answer_cache SET created_at = datetime('now', '-90 days')")
    conn.commit()
    conn.close()
    assert ac.lookup("ابني لا يصلي", "4-6", "islamic_parenting", "خفيف") is None
