"""The knowledge index baked into the image replaces re-embedding at startup.

backend/Dockerfile builds the index with the container's own startup call and
parks it at retrieval.SEED_DIR, beside the persist dir the production volume
covers. At startup, when the volume's index was built for other units and the
seed for exactly these, the seed is copied in — no embedding on the production
host (where, CPU-throttled, re-embedding outran the deploy's health window).
"""
import shutil

import pytest

from app.services import answer_cache, retrieval
from app.services.knowledge_loader import load_default_knowledge_units


class _FakeEmbedder(retrieval.MultilingualEmbedding):
    """Small deterministic vectors; no model."""

    def __call__(self, input):
        return [[1.0, float(len(text) % 7), float(i % 5), 0.5] for i, text in enumerate(input)]


class _MustNotEmbed(retrieval.MultilingualEmbedding):
    def __call__(self, input):
        raise AssertionError("re-embedded although a current index was baked into the image")


def _drop_clients():
    retrieval._collection = None
    from chromadb.api.shared_system_client import SharedSystemClient

    SharedSystemClient.clear_system_cache()


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    persist, seed = tmp_path / "chroma_db", tmp_path / "chroma_seed"
    persist.mkdir()
    monkeypatch.setattr(retrieval, "CHROMA_PERSIST_DIR", persist)
    monkeypatch.setattr(retrieval, "SEED_DIR", seed)
    saved = retrieval._collection
    _drop_clients()
    yield persist, seed
    _drop_clients()
    retrieval._collection = saved


@pytest.fixture(scope="module")
def units():
    return load_default_knowledge_units()[:6]


def _bake(units, persist, seed, monkeypatch):
    """What the image build does: index into the persist dir, park it as the seed."""
    monkeypatch.setattr(retrieval, "_embedder", lambda: _FakeEmbedder())
    retrieval.index_knowledge_units(units)
    _drop_clients()
    shutil.move(str(persist), str(seed))
    persist.mkdir()


def test_startup_installs_the_baked_index_instead_of_re_embedding(dirs, units, monkeypatch):
    persist, seed = dirs
    _bake(units, persist, seed, monkeypatch)
    # The production volume, after the previous deploy: an index for older units.
    (persist / "_content_fingerprint").write_text("an-index-for-older-units")
    monkeypatch.setattr(retrieval, "_embedder", lambda: _MustNotEmbed())
    purged = []
    monkeypatch.setattr(answer_cache, "purge", lambda reason="": purged.append(reason) or 0)

    retrieval.index_knowledge_units(units)

    assert retrieval._read_fingerprint(persist) == retrieval._fingerprint(units)
    assert retrieval.with_live_collection(lambda c: c.count()) == len(units)
    # New unit texts mean stale cached citations — same rule as a rebuild.
    assert purged == ["baked knowledge index installed"]


def test_an_index_that_is_already_current_is_left_alone(dirs, monkeypatch):
    persist, seed = dirs
    seed.mkdir()
    (seed / "_content_fingerprint").write_text("fp-now")
    (persist / "_content_fingerprint").write_text("fp-now")
    (persist / "live.bin").write_text("the volume's own files")
    monkeypatch.setattr(answer_cache, "purge", lambda reason="": pytest.fail("purged"))

    assert retrieval._install_seed_if_current("fp-now") is False
    assert (persist / "live.bin").read_text() == "the volume's own files"


def test_a_seed_built_for_other_units_is_ignored(dirs):
    persist, seed = dirs
    seed.mkdir()
    (seed / "_content_fingerprint").write_text("fp-of-other-units")
    (persist / "live.bin").write_text("untouched")

    assert retrieval._install_seed_if_current("fp-now") is False
    assert (persist / "live.bin").read_text() == "untouched"


def test_an_interrupted_copy_never_looks_current(dirs, monkeypatch):
    persist, seed = dirs
    seed.mkdir()
    (seed / "chroma.sqlite3").write_text("index")
    (seed / "_content_fingerprint").write_text("fp-now")

    def _disk_full(src, dst, *a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(retrieval.shutil, "copy2", _disk_full)

    assert retrieval._install_seed_if_current("fp-now") is False
    assert retrieval._read_fingerprint(persist) is None  # the next start tries again


def test_without_a_matching_seed_the_slow_path_is_said_loudly(dirs, units, monkeypatch, caplog):
    persist, _ = dirs
    monkeypatch.setattr(retrieval, "_embedder", lambda: _FakeEmbedder())

    with caplog.at_level("WARNING", logger=retrieval.logger.name):
        retrieval.index_knowledge_units(units)

    assert any("Re-embedding all" in r.getMessage() and r.levelname == "WARNING"
               for r in caplog.records)
    assert retrieval._read_fingerprint(persist) == retrieval._fingerprint(units)
