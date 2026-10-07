"""Reporting/control-flow regressions; these are not answer-quality scores."""
import importlib.util
import json
from pathlib import Path
import socket

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("golden_ci", ROOT / "ops/tools/golden_ci.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


def item(ident="a", **extra):
    return dict(id=ident, question="كيف أساعد طفلي؟", age_group="7-9",
                severity="متوسط", category="in_kb", expected_domains=["medical"],
                expected_unit_ids=["unit-a"], **extra)


def test_actual_set_includes_original_92_and_all_distinct_items():
    rows = ci.load_set(ROOT / "ops/eval/golden_set.jsonl")
    assert len(rows) == len({r["id"] for r in rows}) >= 92
    assert {f"g-{i:03d}" for i in range(1, 93)} <= {r["id"] for r in rows}


def test_one_year_golden_case_is_eligible_for_its_existing_cdc_target_without_fake_hit():
    from app.core.taxonomy import age_bands_apart, age_equivalents

    row = next(r for r in ci.load_set(ROOT / "ops/eval/golden_set.jsonl")
               if r["id"] == "g-074")
    target_id = "d0d2dc99-520c-4ade-a1ee-9715df0c2dfd"
    target = json.loads((ROOT / "knowledge_base/units" / f"{target_id}.json").read_text())
    assert row["expected_domains"] == ["development"]
    assert row["expected_unit_ids"] == [target_id]
    assert target["title"] == "Your baby at 12 months"
    assert target["age_group"] == "prenatal-1"
    assert target["age_group"] in age_equivalents(row["age_group"])
    assert age_bands_apart(target["age_group"], row["age_group"]) == 0
    # Eligibility and catalog support do not mean that retrieval found the unit.
    scored = ci.score_retrieval(row, ["development"], [], {"development"}, {target_id})
    assert scored["missing_expected_unit_ids"] == []
    assert scored["supported_unit_recall"] == 0


@pytest.mark.parametrize("change", [{"id": ""}, {"question": ""},
                                    {"expected_domains": "medical"},
                                    {"expected_unit_ids": [3]}, {"age_group": None}])
def test_rejects_invalid_item_before_evaluation(tmp_path, change):
    path = tmp_path / "set.jsonl"
    path.write_text(json.dumps(item() | change))
    with pytest.raises(ValueError):
        ci.load_set(path)


def test_duplicate_ids_cannot_inflate_coverage(tmp_path):
    path = tmp_path / "set.jsonl"
    path.write_text("\n".join(json.dumps(item()) for _ in range(2)))
    with pytest.raises(ValueError, match="duplicate"):
        ci.load_set(path)


def test_unknown_labels_are_reported_not_counted_as_misses_or_hits():
    row = ci.score_retrieval(item() | {"expected_domains": ["medical", "invented"],
                                     "expected_unit_ids": ["unit-a", "withdrawn"]},
                             ["medical"], [{"unit_id": "unit-a"}],
                             {"medical"}, {"unit-a"})
    assert row["unsupported_domains"] == ["invented"]
    assert row["missing_expected_unit_ids"] == ["withdrawn"]
    assert row["supported_domain_recall"] == 1
    assert row["supported_unit_recall"] == 1


def test_absent_targets_have_no_vacuous_perfect_score():
    row = ci.score_retrieval(item() | {"expected_domains": [], "expected_unit_ids": []},
                             ["medical"], [], {"medical"}, {"unit-a"})
    assert row["supported_domain_recall"] is None
    assert row["supported_unit_recall"] is None


def test_retrieval_failure_retains_every_item_and_never_claims_quality(tmp_path):
    def prepare(_):
        def retrieve(row):
            if row["id"] == "bad":
                raise RuntimeError("secret-shaped error must not be published")
            return ["medical"], [{"unit_id": "unit-a"}]
        return retrieve, {"medical"}, {"unit-a"}
    report = ci.offline_report([item(), item("bad"), item("last")], tmp_path, prepare)
    assert [r["id"] for r in report["items"]] == ["a", "bad", "last"]
    assert report["counts"] == {"total": 3, "evaluated": 2, "errors": 1, "unavailable": 0}
    assert report["status"] == "PARTIAL"
    assert report["answer_quality"]["status"] == "UNAVAILABLE"
    assert "secret-shaped" not in json.dumps(report)


def test_missing_index_is_unavailable_for_entire_set(tmp_path):
    def prepare(_):
        raise FileNotFoundError("private host path")
    report = ci.offline_report([item(), item("b")], tmp_path, prepare)
    assert report["status"] == "UNAVAILABLE"
    assert report["counts"]["unavailable"] == 2
    assert len(report["items"]) == 2


@pytest.mark.backend_env
@pytest.mark.parametrize("question,language", [
    ("ar-g024", "ar"),
    ("How can I teach my child good manners and help our community?", "en"),
    ("؟", "en"),  # Insufficient script evidence retains neutral ranking.
])
def test_offline_report_keeps_production_language_preference_without_models(
        tmp_path, monkeypatch, question, language):
    """Real hybrid/language logic with synthetic candidates and rerank scores."""
    from app.services import bm25_index, retrieval, reranker

    if question == "ar-g024":
        question = next(row["question"] for row in
                        ci.load_set(ROOT / "ops/eval/golden_set.jsonl")
                        if row["id"] == "g-024")
    source = tmp_path / "source"
    seed = source / "knowledge_base/chroma_seed"
    seed.mkdir(parents=True)
    (seed / "chroma.sqlite3").write_bytes(b"synthetic seed; never opened")
    candidates = [
        {"unit_id": f"unit-{lang}-{i}", "document": "synthetic candidate",
         "metadata": {"language": lang, "age_group": "7-9",
                      "domain": "islamic_parenting"},
         "rerank_score": score}
        for lang, score in (("en", 5.01), ("ar", 5.0)) for i in range(4)
    ] + [{"unit_id": "unit-low", "document": "synthetic low score",
          "metadata": {"age_group": "7-9"}, "rerank_score": -4.0}]
    ids = {candidate["unit_id"] for candidate in candidates}

    class Collection:
        def get(self, include):
            return {"ids": sorted(ids)}

    class BM25:
        def search(self, *args, **kwargs):
            return []

    def synthetic_rerank(query, pool, top_n):
        return sorted(pool, key=lambda candidate: -candidate["rerank_score"])[:top_n]

    monkeypatch.setattr(ci, "ROOT", source)
    monkeypatch.setattr(retrieval, "CHROMA_PERSIST_DIR", retrieval.CHROMA_PERSIST_DIR)
    monkeypatch.setattr(retrieval, "_collection", retrieval._collection)
    monkeypatch.setattr(retrieval, "_TELEMETRY_DB", retrieval._TELEMETRY_DB)
    monkeypatch.setattr(retrieval, "_get_collection", lambda: Collection())
    monkeypatch.setattr(retrieval, "query_embedder", lambda: None)
    monkeypatch.setattr(retrieval, "retrieve_relevant_units",
                        lambda *args, **kwargs: candidates)
    monkeypatch.setattr(retrieval, "retrieve_domain_only", lambda *args, **kwargs: [])
    monkeypatch.setattr(bm25_index, "get_bm25", lambda: BM25())
    monkeypatch.setattr(reranker, "rerank", synthetic_rerank)
    # Resolve language from fixture metadata, without reading/loading the corpus.
    monkeypatch.setattr(retrieval, "_candidate_language",
                        lambda candidate: candidate["metadata"].get("language"))
    work = tmp_path / "private"
    work.mkdir()
    report = ci.offline_report([item() | {
        "question": question, "expected_domains": ["islamic_parenting"],
        "expected_unit_ids": [f"unit-{language}-0"],
    }], work)
    row = report["items"][0]
    assert row["retrieved_unit_ids"] == [f"unit-{language}-{i}" for i in range(4)]
    assert row["supported_unit_recall"] == 1.0
    assert report["answer_quality"]["status"] == "UNAVAILABLE"
    assert report["scope"] == "offline keyword/fallback domains + hybrid retrieval"


@pytest.mark.parametrize("env", [{}, {"DEEPSEEK_API_KEY": "test-placeholder"},
    {"GOLDEN_PROVIDER_ROUTE_VERIFIED": "true"},
    {"GOLDEN_PROVIDER_ROUTE_VERIFIED": "true", "DEEPSEEK_API_KEY": "test-placeholder",
     "LLM_PRIMARY_PROVIDER": "deepseek", "DEEPSEEK_BASE_URL": "http://private.invalid"}])
def test_full_unapproved_or_unavailable_never_imports_pipeline(tmp_path, env):
    def forbidden(_):
        pytest.fail("provider/app must not be activated")
    report = ci.full_report([item(), item("b")], tmp_path, env, forbidden)
    assert report["status"] == "UNAVAILABLE"
    assert len(report["items"]) == 2
    assert report["metrics"] is None


def test_judge_failure_keeps_raw_pipeline_rows_and_does_not_pass(tmp_path):
    env = {"GOLDEN_PROVIDER_ROUTE_VERIFIED": "true", "DEEPSEEK_API_KEY": "test-placeholder",
           "LLM_PRIMARY_PROVIDER": "deepseek"}
    class Harness:
        @staticmethod
        def run_pipeline(rows, label, db):
            assert Path(db).is_relative_to(tmp_path)
            return [r | {"mode": "llm_generated", "reply_text": "control-flow fixture"}
                    for r in rows]
        @staticmethod
        def judge_all(rows, provider):
            assert provider == "deepseek"
            assert len((tmp_path / "pipeline.jsonl").read_text().splitlines()) == 2
            raise RuntimeError("private provider error")
    report = ci.full_report([item(), item("b")], tmp_path, env, lambda _: Harness)
    assert report["status"] == "PARTIAL"
    assert len(report["items"]) == 2
    assert report["metrics"] is None
    assert "private provider error" not in json.dumps(report)


def test_offline_network_guard_blocks_even_loopback_provider(monkeypatch):
    original = socket.socket.connect
    # Restore the class method after this test; no request actually leaves.
    monkeypatch.setattr(socket.socket, "connect", original)
    ci.deny_external_network()
    with socket.socket() as sock, pytest.raises(RuntimeError, match="forbids network"):
        sock.connect(("127.0.0.1", 11434))


def test_cli_full_missing_route_preserves_entire_manifest(tmp_path, monkeypatch):
    monkeypatch.delenv("GOLDEN_PROVIDER_ROUTE_VERIFIED", raising=False)
    assert ci.main(["--mode", "full", "--out", str(tmp_path)]) == 2
    report = json.loads((tmp_path / "report.json").read_text())
    ids = [r["id"] for r in ci.load_set(ROOT / "ops/eval/golden_set.jsonl")]
    assert [r["id"] for r in report["items"]] == ids
    assert report["counts"]["unavailable"] == len(ids)
    assert report["metrics"] is None


def test_cli_failed_candidate_does_not_import_retrieval(tmp_path, monkeypatch):
    monkeypatch.setattr(ci, "prepare_offline", lambda _: pytest.fail("unexpected retrieval"))
    assert ci.main(["--out", str(tmp_path), "--unavailable", "Candidate unavailable"]) == 2
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["counts"]["total"] == report["counts"]["unavailable"]
    assert report["status"] == "UNAVAILABLE"


def test_incomplete_judge_payload_never_claims_completed_quality(tmp_path):
    class Harness:
        @staticmethod
        def run_pipeline(rows, label, db):
            return [r | {"mode": "llm_generated"} for r in rows]
        @staticmethod
        def judge_all(rows, provider):
            for row in rows:
                row["judge"] = {"judge_notes": "not a scored judgment"}
        @staticmethod
        def summarize(rows):
            return {"overall": {"n": 0}}
    env = {"GOLDEN_PROVIDER_ROUTE_VERIFIED": "true", "DEEPSEEK_API_KEY": "test-placeholder",
           "LLM_PRIMARY_PROVIDER": "deepseek"}
    report = ci.full_report([item()], tmp_path, env, lambda _: Harness)
    assert report["status"] == "PARTIAL"
    assert report["counts"]["errors"] == 1


def test_interrupted_retrieval_keeps_completed_rows_and_remaining_ids(tmp_path):
    def prepare(_):
        def retrieve(row):
            if row["id"] == "interrupted":
                raise KeyboardInterrupt
            return ["medical"], [{"unit_id": "unit-a"}]
        return retrieve, {"medical"}, {"unit-a"}
    with pytest.raises(KeyboardInterrupt):
        ci.offline_report([item(), item("interrupted"), item("last")],
                          tmp_path, prepare, checkpoint=tmp_path / "report.json")
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["status"] == "PARTIAL"
    assert report["counts"] == {"total": 3, "evaluated": 1, "errors": 0, "unavailable": 2}
    assert [r["id"] for r in report["items"]] == ["a", "interrupted", "last"]
