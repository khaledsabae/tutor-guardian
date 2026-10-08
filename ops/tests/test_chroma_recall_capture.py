"""Frozen-input and failure-report tests; no model downloads or live databases."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops/tools"))
spec = importlib.util.spec_from_file_location("capture", ROOT / "ops/tools/chroma_recall_capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def bundle():
    return {
        "corpus": {"units": [{"id": "b"}, {"id": "a"}], "ids": ["b", "a"],
                   "documents": ["passage: b", "passage: a"],
                   "metadatas": [{"domain": "sleep"}, {"domain": "fiqh"}]},
        "vectors": {"documents": [[1., 0.], [0., 1.]], "queries": {"question": [1., 0.]}},
        "policy": {"top_k": 4, "model_revision": "real-snapshot-id"},
    }


def test_frozen_catalog_uses_complete_index_and_preserves_insertion_order():
    frozen = bundle()
    capture.validate_bundle(frozen, [{"question": "question"}])
    assert frozen["corpus"]["ids"] == ["b", "a"]
    assert capture.catalog(frozen) == {"unit_ids": ["a", "b"], "domains": ["fiqh", "sleep"]}


@pytest.mark.parametrize("change", [
    lambda b: b["corpus"]["ids"].__setitem__(1, "b"),
    lambda b: b["corpus"]["documents"].pop(),
    lambda b: b["vectors"]["documents"].__setitem__(1, [1.]),
    lambda b: b["vectors"]["queries"].__setitem__("question", [float("nan"), 0.]),
    lambda b: b["vectors"]["queries"].clear(),
    lambda b: b["vectors"]["queries"].__setitem__("other question", [1., 0.]),
    lambda b: b["vectors"]["documents"].__setitem__(0, [True, 0.]),
])
def test_invalid_or_drifted_frozen_inputs_fail_closed(change):
    frozen = bundle()
    change(frozen)
    with pytest.raises(ValueError):
        capture.validate_bundle(frozen, [{"question": "question"}])


def test_actual_vector_and_policy_changes_change_provenance_hashes():
    frozen = bundle()
    golden = [{"question": "question"}]
    old = capture.capture_metadata(frozen, golden, "0.6.3")
    new = capture.capture_metadata(frozen, golden, "1.99.0")
    assert old | {"chroma_version": "1.99.0"} == new
    changed = copy.deepcopy(frozen)
    changed["vectors"]["documents"][0] = [.9, .1]
    assert capture.capture_metadata(changed, golden, "1.99.0")["embedding_sha256"] != old["embedding_sha256"]
    changed = copy.deepcopy(frozen)
    changed["policy"]["model_revision"] = "different-model"
    assert capture.capture_metadata(changed, golden, "1.99.0")["query_policy_sha256"] != old["query_policy_sha256"]


def test_summary_reports_paired_metrics_without_claiming_upgrade_pass():
    report = {"status": "COMPARISON_COMPLETE", "counts": {"golden": 126, "paired": 126, "unpaired": 0},
              "declared_versions": {"old": "0.6.3", "new": "1.99.0"},
              "paired_metrics": {"unit_recall": {"old": .25, "new": .2, "delta": -.05}},
              "reasons": []}
    text = capture.summary(report)
    assert "126" in text and "1.99.0" in text and "-0.05" in text
    assert "NOT_EVALUATED" in text and "UNVERIFIED" in text


def test_summary_keeps_incomplete_comparison_visible():
    text = capture.summary({"status": "INVALID_INPUT", "reason": "FileNotFoundError"})
    assert "INVALID_INPUT" in text and "FileNotFoundError" in text


def test_fresh_index_refuses_nonempty_directory(tmp_path):
    (tmp_path / "chroma.sqlite3").write_text("old data")
    with pytest.raises(ValueError, match="non-empty"):
        capture.fresh_directory(tmp_path)
    assert (tmp_path / "chroma.sqlite3").read_text() == "old data"


def test_unknown_query_cannot_trigger_new_embedding():
    lookup = capture.FrozenQueries({"known": [1., 0.]})
    assert lookup("known") == [1., 0.]
    with pytest.raises(ValueError, match="unfrozen"):
        lookup("new")
    assert lookup.errors == ["new"]


def test_swallowed_sdk_query_failure_is_still_visible():
    class Collection:
        def query(self, **kwargs):
            raise RuntimeError("SDK mismatch")

    guarded = capture.QueryGuard(Collection())
    try:
        guarded.query(query_embeddings=[[1., 0.]])
    except RuntimeError:
        pass  # Production _query swallows this exception.
    assert guarded.errors == ["RuntimeError"]


def test_reranker_fallback_is_rejected():
    fallback = lambda query, candidates, **kwargs: candidates
    checked = capture.checked_rerank(fallback, lambda: False)
    with pytest.raises(RuntimeError, match="reranker"):
        checked("query", [{"unit_id": "a"}], top_n=4)
    working = capture.checked_rerank(lambda *a, **kw: [{"rerank_score": .5}], lambda: False)
    assert working("query", [{"unit_id": "a"}])[0]["rerank_score"] == .5
    disabled = capture.checked_rerank(lambda *a, **kw: [], lambda: True)
    with pytest.raises(RuntimeError, match="reranker"):
        disabled("query", [])


def test_cli_refuses_outputs_outside_runner_temp_before_importing_sdk(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
    with pytest.raises(SystemExit) as result:
        capture.main(["baseline", "--out", str(tmp_path / "outside.json"),
                      "--index", str(tmp_path / "runner/index"),
                      "--catalog", str(tmp_path / "runner/catalog.json"),
                      "--frozen", str(tmp_path / "runner/frozen.json")])
    assert result.value.code == 2
    assert not (tmp_path / "outside.json").exists()


def test_candidate_policy_drift_cannot_open_or_mutate_index(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    services = ModuleType("app.services")
    services.retrieval = SimpleNamespace()
    services.reranker = SimpleNamespace(RERANK_ENABLED=True)
    monkeypatch.setitem(sys.modules, "app.services", services)
    monkeypatch.setattr(capture, "policy", lambda *args: {"different": "model revision"})
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps(bundle()))
    golden = tmp_path / "golden.jsonl"
    golden.write_text(json.dumps({"id": "g", "question": "question", "age_group": "4-6",
                                  "severity": "low", "category": "in_kb",
                                  "expected_domains": ["sleep"], "expected_unit_ids": ["a"]}))
    out = tmp_path / "candidate.json"
    assert capture.main(["candidate", "--golden", str(golden), "--out", str(out),
                         "--frozen", str(frozen), "--index", str(tmp_path / "index"),
                         "--catalog", str(tmp_path / "catalog.json")]) == 2
    report = json.loads(out.read_text())
    assert report["status"] == "UNAVAILABLE"
    assert report["items"] == [{"id": "g", "status": "UNAVAILABLE"}]
    assert "policy drift" in report["reason"]
    assert not (tmp_path / "index").exists()
    assert not (tmp_path / "catalog.json").exists()


def test_summary_cli_uses_comparator_result_without_ml_imports(tmp_path):
    comparison = tmp_path / "comparison.json"
    comparison.write_text(json.dumps({"status": "PARTIAL", "counts": {"paired": 0}}))
    out = tmp_path / "summary.md"
    assert capture.main(["summary", "--summary", str(comparison), "--out", str(out)]) == 0
    assert "PARTIAL" in out.read_text() and "NOT_EVALUATED" in out.read_text()


def test_prepare_replays_ordered_frozen_corpus_and_surfaces_swallowed_errors(tmp_path, monkeypatch):
    class Unit:
        @classmethod
        def model_validate(cls, row):
            return SimpleNamespace(**row)

    knowledge = ModuleType("app.models.knowledge")
    knowledge.KnowledgeUnit = Unit
    bm25 = ModuleType("app.services.bm25_index")
    bm25._index = object()
    classifier = ModuleType("app.services.domain_classifier")
    classifier.fallback_domains = lambda question: ["tarbiyah"]
    services = ModuleType("app.services")
    services.bm25_index = bm25
    for name, module in {"app.models.knowledge": knowledge, "app.services": services,
                         "app.services.bm25_index": bm25,
                         "app.services.domain_classifier": classifier}.items():
        monkeypatch.setitem(sys.modules, name, module)

    class Collection:
        def __init__(self):
            self.rows, self.batches, self.fail = [], [], False

        def add(self, **kwargs):
            self.batches.append(kwargs["ids"])
            self.rows.extend(zip(kwargs["ids"], kwargs["documents"],
                                 kwargs["metadatas"], kwargs["embeddings"]))

        def count(self):
            return len(self.rows)

        def get(self, **kwargs):
            return {key: [row[column] for row in self.rows]
                    for column, key in enumerate(("ids", "documents", "metadatas"))}

        def query(self, **kwargs):
            if self.fail:
                raise RuntimeError("SDK mismatch")
            return [{"unit_id": "u0", "document": "passage: body 0", "rerank_score": .5}]

    ids = [f"u{i}" for i in range(130)]
    frozen = {"corpus": {"ids": ids, "units": [{"id": i, "language": "ar"} for i in ids],
                         "documents": [f"passage: body {i}" for i in range(130)],
                         "metadatas": [{"unit_id": i, "domain": "tarbiyah"} for i in ids]},
              "vectors": {"documents": [[1., 0.] for _ in ids], "queries": {"q": [1., 0.]}}}
    collection, cleared = Collection(), []
    reranker = SimpleNamespace(_disabled=False, rerank=lambda question, candidates, **kw: candidates)
    retrieval = SimpleNamespace(_get_collection=lambda: collection, unknown=False,
                                _unit_languages=SimpleNamespace(cache_clear=lambda: cleared.append(True)),
                                detect_query_language=lambda question: "ar")

    def hybrid(question, domains, age_group, **kwargs):
        try:
            vector = retrieval.embed_query("unknown" if retrieval.unknown else question)
            return reranker.rerank(question, retrieval._collection.query(query_embeddings=[vector]))
        except (RuntimeError, ValueError):
            return []  # Mirror the application's intentional degraded vector leg.

    retrieval.retrieve_hybrid = hybrid
    prepared = capture.prepare(frozen, tmp_path / "index", retrieval, reranker)
    assert [len(batch) for batch in collection.batches] == [128, 2]
    assert [i for batch in collection.batches for i in batch] == ids
    assert [row[3] for row in collection.rows] == frozen["vectors"]["documents"]
    assert [u.id for u in retrieval.load_default_knowledge_units()] == ids
    assert [u.id for u in bm25.load_default_knowledge_units()] == ids
    assert bm25._index is None and cleared == [True] and retrieval._index_built
    item = {"id": "g", "question": "q", "age_group": "4-6", "severity": "low",
            "category": "normal", "expected_domains": ["tarbiyah"], "expected_unit_ids": ["u0"]}
    report = capture.offline_report([item], tmp_path, prepare=lambda _: prepared)
    assert report["status"] == "COMPLETED"
    assert report["items"][0]["supported_unit_recall"] == 1
    for sdk_error, unknown_query in ((True, False), (False, True)):
        collection.fail, retrieval.unknown = sdk_error, unknown_query
        report = capture.offline_report([item], tmp_path, prepare=lambda _: prepared)
        assert report["status"] == "PARTIAL" and report["counts"]["errors"] == 1
        assert report["items"][0]["status"] == "ERROR"
    collection.fail, retrieval.unknown = False, False
    assert capture.offline_report([item], tmp_path, prepare=lambda _: prepared)["status"] == "COMPLETED"


def test_plain_converts_numpy_vectors_for_json():
    import json
    import numpy as np
    from ops.tools import chroma_recall_capture as cap

    vectors = cap._plain(np.array([[0.5, 0.25], [1.0, 0.0]], dtype=np.float32))
    assert vectors == [[0.5, 0.25], [1.0, 0.0]]
    assert cap._plain([np.array([1.0]), np.array([2.0])]) == [[1.0], [2.0]]
    json.dumps({"documents": vectors})

