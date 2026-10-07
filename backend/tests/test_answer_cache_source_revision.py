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
    assert cache.store(*args, answer, generation_revision=cache.capture_revision())
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
    assert cache.store(*args, fresh, generation_revision=cache.capture_revision())
    assert cache.lookup(*args) == fresh


def test_source_text_revision_also_invalidates_cached_answer(corpus):
    args = ("parent question", "4-6", "islamic_parenting", "خفيف")
    assert cache.store(*args, "Answer based on the original source. " * 4, generation_revision=cache.capture_revision())
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


ARGS = ("parent question", "4-6", "islamic_parenting", "خفيف")
ANSWER = ("Answer grounded in the source before removal or revision. " * 4).strip()


def _change_source(corpus, change):
    path = corpus / "isl-23c2dd25.json"
    if change == "remove":
        path.unlink()
    else:
        data = json.loads(path.read_text())
        data["text_simplified"] += " Revised source context."
        path.write_text(json.dumps(data))


@pytest.mark.parametrize("change", ["remove", "edit"])
@pytest.mark.parametrize("semantic", [False, True])
def test_source_changes_while_lookup_is_inflight(corpus, monkeypatch, change, semantic):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    assert cache.store(*ARGS, ANSWER, generation_revision=cache.capture_revision())
    ready, proceed = Event(), Event()
    original_revision = cache._kb_revision
    first = True

    def paused_revision():
        nonlocal first
        revision = original_revision()
        if first:
            first = False
            ready.set()
            assert proceed.wait(5), "lookup was not resumed"
        return revision

    monkeypatch.setattr(cache, "_kb_revision", paused_revision)
    query = "equivalent question" if semantic else ARGS[0]
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cache.lookup, query, *ARGS[1:])
        try:
            assert ready.wait(5), "lookup did not capture a revision"
            _change_source(corpus, change)
        finally:
            proceed.set()
        result = future.result(timeout=5)
    assert result is None


@pytest.mark.parametrize("change", ["remove", "edit"])
def test_old_generation_cannot_be_stamped_with_new_revision(corpus, change):
    generation_revision = cache._kb_revision()
    _change_source(corpus, change)
    assert cache._kb_revision() != generation_revision
    assert not cache.store(*ARGS, ANSWER, generation_revision=generation_revision)
    assert cache.lookup("equivalent question", *ARGS[1:]) is None


@pytest.mark.parametrize("semantic", [False, True])
@pytest.mark.parametrize("change", ["remove", "edit"])
def test_source_changes_during_hit_revalidation(corpus, monkeypatch, semantic, change):
    assert cache.store(*ARGS, ANSWER, generation_revision=cache.capture_revision())
    original_load = knowledge_loader.load_default_knowledge_units
    reads = 0

    def changing_load():
        nonlocal reads
        units = original_load()
        reads += 1
        # Initial stable snapshot uses two reads. Change the actual file after
        # the first revalidation read, while that read still describes old KB.
        if reads == 3:
            _change_source(corpus, change)
        return units

    monkeypatch.setattr(knowledge_loader, "load_default_knowledge_units", changing_load)
    query = "equivalent question" if semantic else ARGS[0]
    assert cache.lookup(query, *ARGS[1:]) is None


def test_store_without_generation_provenance_fails_closed(corpus):
    assert not cache.store(*ARGS, ANSWER)


def test_old_generation_cannot_overwrite_a_new_answer(corpus):
    old_revision = cache._kb_revision()
    _change_source(corpus, "edit")
    fresh = ("Answer generated from the revised source. " * 4).strip()
    assert cache.store(*ARGS, fresh, generation_revision=cache._kb_revision())
    assert not cache.store(*ARGS, ANSWER, generation_revision=old_revision)
    assert cache.lookup(*ARGS) == fresh


def test_capture_rejects_a_source_change_inside_the_read(corpus, monkeypatch):
    original_load = knowledge_loader.load_default_knowledge_units
    first = True

    def changing_load():
        nonlocal first
        units = original_load()
        if first:
            first = False
            _change_source(corpus, "edit")
        return units

    monkeypatch.setattr(knowledge_loader, "load_default_knowledge_units", changing_load)
    assert cache.capture_revision() is None


def test_paused_old_writer_cannot_replace_a_concurrent_fresh_answer(corpus, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    old_revision = cache.capture_revision()
    ready, proceed = Event(), Event()
    first = True

    def paused_embed(_):
        nonlocal first
        if first:
            first = False
            ready.set()
            assert proceed.wait(5), "old writer was not resumed"
        return [1.0, 0.0]

    monkeypatch.setattr(cache, "_embed", paused_embed)
    fresh = ("New answer grounded in the revised source. " * 4).strip()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cache.store, *ARGS, ANSWER, generation_revision=old_revision)
        try:
            assert ready.wait(5), "old writer did not reach embedding"
            _change_source(corpus, "edit")
            assert cache.store(*ARGS, fresh, generation_revision=cache.capture_revision())
        finally:
            proceed.set()
        assert not future.result(timeout=5)
    assert cache.lookup(*ARGS) == fresh


def test_change_after_insert_rolls_back_cache_write(corpus, monkeypatch):
    revision = cache.capture_revision()
    original_conn = cache._conn

    class ChangingConnection:
        def __init__(self):
            self.conn = original_conn()

        def execute(self, statement, parameters=()):
            result = self.conn.execute(statement, parameters)
            if statement.startswith("INSERT INTO answer_cache"):
                _change_source(corpus, "edit")
            return result

        def commit(self):
            self.conn.commit()

        def close(self):
            self.conn.close()

    monkeypatch.setattr(cache, "_conn", ChangingConnection)
    assert not cache.store(*ARGS, ANSWER, generation_revision=revision)
    with sqlite3.connect(cache._DB) as conn:
        assert conn.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0] == 0
