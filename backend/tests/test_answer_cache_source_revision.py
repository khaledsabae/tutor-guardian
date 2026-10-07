"""Quarantining a source must invalidate answers before index startup/purge."""
import json
import sqlite3
from pathlib import Path

import pytest

from app.services import answer_cache as cache, knowledge_loader, retrieval

ROOT = Path(__file__).resolve().parents[2]
NONKNOWLEDGE = ("isl-23c2dd25", "isl-7349e59c")


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    units = tmp_path / "units"
    units.mkdir()
    for uid in (*NONKNOWLEDGE, "isl-1057f72f"):
        for suffix in ("", "__en"):
            name = uid + suffix + ".json"
            source = ROOT / "knowledge_base/units" / name
            if not source.exists():
                source = ROOT / "ops/data/en_unpublished" / (
                    "kb_units" if suffix else "kb_units_source"
                ) / name
            (units / name).write_bytes(source.read_bytes())
    monkeypatch.setattr(knowledge_loader, "DEFAULT_KB_DIRS", [units])
    monkeypatch.setattr(knowledge_loader, "DAILY_TIPS_DIR", tmp_path / "absent")
    monkeypatch.setattr(cache, "_DB", tmp_path / "answers.db")
    monkeypatch.setattr(cache, "ANSWER_CACHE_ENABLED", True)
    monkeypatch.setattr(cache, "_embed", lambda text: [1.0, 0.0])
    monkeypatch.setattr("app.services.ai_gateway._log_call", lambda *a, **k: None)
    return units


@pytest.mark.parametrize("uid", NONKNOWLEDGE)
@pytest.mark.parametrize("semantic", [False, True])
def test_removed_source_cannot_survive_in_exact_or_semantic_cache(corpus, uid, semantic):
    answer = (f"Historical source {uid} was used in this parenting answer. " * 4).strip()
    args = ("parent question", "4-6", "islamic_parenting", "خفيف")
    assert cache.store(*args, answer)
    assert cache.lookup(*args) == answer
    before = retrieval._fingerprint(knowledge_loader.load_default_knowledge_units())
    for suffix in ("", "__en"):
        (corpus / (uid + suffix + ".json")).unlink()
    after = retrieval._fingerprint(knowledge_loader.load_default_knowledge_units())
    assert after != before
    query = "same meaning, different question" if semantic else args[0]
    assert cache.lookup(query, *args[1:]) is None
    # No index initialization, embeddings or global purge was needed.
    fresh = ("An answer derived from the remaining real source. " * 4).strip()
    assert cache.store(*args, fresh)
    assert cache.lookup(*args) == fresh


def test_source_text_revision_also_invalidates_cached_answer(corpus):
    args = ("parent question", "4-6", "islamic_parenting", "خفيف")
    assert cache.store(*args, "Answer based on the original source. " * 4)
    path = corpus / "isl-1057f72f.json"
    data = json.loads(path.read_text())
    data["text_simplified"] += " Additional source context."
    path.write_text(json.dumps(data))
    assert cache.lookup(*args) is None


def test_legacy_cache_without_source_revision_is_not_served(corpus):
    conn = sqlite3.connect(cache._DB)
    conn.execute("""CREATE TABLE answer_cache (
        id INTEGER PRIMARY KEY, qhash TEXT UNIQUE, question_norm TEXT,
        age_group TEXT, domain TEXT, severity TEXT, answer TEXT,
        embedding TEXT, created_at TEXT DEFAULT (datetime('now')),
        hit_count INTEGER DEFAULT 0, redacted INTEGER)""")
    args = ("legacy parent question", "4-6", "islamic_parenting", "خفيف")
    conn.execute(
        "INSERT INTO answer_cache (qhash,question_norm,age_group,domain,severity,"
        "answer,embedding,redacted) VALUES (?,?,?,?,?,?,?,1)",
        (cache._key(*args), args[0], *args[1:], "Untracked source answer. " * 4, "[1,0]"),
    )
    conn.commit()
    conn.close()
    assert cache.lookup(*args) is None
    assert cache.lookup("equivalent legacy question", *args[1:]) is None


def test_quarantined_pairs_are_absent_from_default_retrieval():
    loaded = knowledge_loader.load_default_knowledge_units()
    assert loaded
    ids = {unit.id for unit in loaded}
    assert not {uid + suffix for uid in NONKNOWLEDGE for suffix in ("", "__en")} & ids
