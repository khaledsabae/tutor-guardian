"""Report arithmetic/control-flow fixtures, never a real Chroma recall claim."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("probe", ROOT / "ops/tools/chroma_recall_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def golden(ident="g", units=None, domains=None):
    return {"id": ident, "question": "سؤال", "category": "in_kb", "expected_unit_ids": units or ["a", "b"],
            "expected_domains": domains or ["fiqh"]}


def row(ident="g", units=None, domains=None, status="EVALUATED"):
    return {"id": ident, "status": status, "retrieved_unit_ids": units or ["a"],
            "domains": domains or ["islamic_parenting"]}


CATALOG = {"unit_ids": ["a", "b"], "domains": ["islamic_parenting"]}


def capture(items, golden_rows, version="0.6.3"):
    return {"items": items, "metadata": {
        "chroma_version": version, "top_k": 4,
        "golden_sha256": probe.digest(golden_rows), "catalog_sha256": probe.digest(CATALOG),
        "corpus_sha256": "1" * 64, "embedding_sha256": "2" * 64,
        "query_policy_sha256": "3" * 64,
    }}


def compare(g, old, new):
    return probe.compare(g, CATALOG, old, new)


def test_supported_target_denominator_is_frozen_and_aliases_are_canonical():
    g = [golden(units=["a", "b", "withdrawn"], domains=["fiqh", "unknown"])]
    r = compare(g, capture([row()], g), capture([row(units=["b"])], g, "1.0.0"))
    assert r["status"] == "COMPARISON_COMPLETE"
    assert r["items"][0]["supported_units"] == ["a", "b"]
    assert r["items"][0]["unsupported_unit_ids"] == ["withdrawn"]
    assert r["items"][0]["unsupported_domains"] == ["unknown"]
    assert r["paired_metrics"]["unit_recall"]["old"] == .5
    assert r["paired_metrics"]["domain_recall"]["old"] == 1
    assert r["runtime_compatibility"] == "UNVERIFIED"


def test_changed_corpus_cannot_masquerade_as_an_upgrade_regression():
    g = [golden()]; old = capture([row()], g); new = capture([row()], g, "1.0.0")
    new["metadata"]["corpus_sha256"] = "4" * 64
    r = compare(g, old, new)
    assert r["status"] == "INCOMPARABLE"
    assert r["paired_metrics"] is None


def test_missing_provenance_is_not_a_comparison_pass():
    g = [golden()]
    r = compare(g, {"items": [row()]}, {"items": [row()]})
    assert r["status"] == "INCOMPARABLE"
    assert len(r["items"]) == 1


def test_missing_and_error_items_are_retained_and_excluded_from_paired_scores():
    g = [golden(), golden("missing"), golden("error")]
    r = compare(g, capture([row(), row("missing"), row("error")], g),
                capture([row(), row("error", status="ERROR")], g, "1.0.0"))
    assert r["status"] == "PARTIAL"
    assert [i["id"] for i in r["items"]] == [i["id"] for i in g]
    assert r["counts"] == {"golden": 3, "paired": 1, "unpaired": 2}
    assert r["paired_metrics"]["unit_recall"]["paired_items"] == 1


def test_no_targets_does_not_get_a_vacuous_perfect_score():
    g = [golden() | {"expected_unit_ids": [], "expected_domains": []}]
    r = compare(g, capture([row()], g), capture([row()], g, "1.0.0"))
    assert r["paired_metrics"]["unit_recall"]["old"] is None
    assert r["paired_metrics"]["unit_recall"]["paired_items"] == 0


def test_duplicate_capture_or_unknown_ids_are_rejected():
    g = [golden()]
    for rows in ([row(), row()], [row("unknown")]):
        with pytest.raises(ValueError):
            compare(g, capture(rows, g), capture([row()], g, "1.0.0"))


def test_hallucinated_catalog_id_is_an_error_not_a_recall_win():
    g = [golden()]
    r = compare(g, capture([row()], g), capture([row(units=["invented"])], g, "1.0.0"))
    assert r["status"] == "PARTIAL"
    assert r["counts"]["paired"] == 0
    assert r["items"][0]["new"]["status"] == "ERROR"


def test_actual_126_item_set_without_captures_is_explicitly_unavailable(tmp_path):
    golden_path = ROOT / "ops/eval/golden_set.jsonl"
    catalog_path = tmp_path / "catalog.json"; catalog_path.write_text(json.dumps(CATALOG))
    out = tmp_path / "report.json"
    assert probe.main(["--catalog", str(catalog_path), "--out", str(out)]) == 2
    report = json.loads(out.read_text())
    actual = [json.loads(l) for l in golden_path.read_text().splitlines() if l.strip()]
    assert len(actual) == len(report["items"]) == 126
    assert [i["id"] for i in report["items"]] == [i["id"] for i in actual]
    assert report["status"] == "UNAVAILABLE"
    assert report["paired_metrics"] is None


def test_metadata_claims_must_match_supplied_golden_and_catalog():
    g = [golden()]; new = capture([row()], g, "1.0.0")
    new["metadata"]["golden_sha256"] = hashlib.sha256(b"other set").hexdigest()
    r = compare(g, capture([row()], g), new)
    assert r["status"] == "INCOMPARABLE"


def test_capture_top_k_bound_is_enforced():
    g = [golden()]; old = capture([row(units=["a", "b"])], g)
    old["metadata"]["top_k"] = 1
    new = capture([row()], g, "1.0.0"); new["metadata"]["top_k"] = 1
    r = compare(g, old, new)
    assert r["status"] == "PARTIAL"
    assert r["counts"]["paired"] == 0


def test_baseline_only_preserves_real_report_scores_without_inventing_candidate(tmp_path):
    g = [golden(), golden("missing")]
    baseline = {"items": [{"id": "g", "status": "EVALUATED",
                            "supported_unit_recall": .5, "supported_domain_recall": 1}]}
    gp = tmp_path / "golden.jsonl"; gp.write_text("\n".join(json.dumps(x) for x in g))
    bp = tmp_path / "baseline.json"; bp.write_text(json.dumps(baseline))
    out = tmp_path / "out.json"
    assert probe.main(["--golden", str(gp), "--baseline", str(bp), "--out", str(out)]) == 2
    r = json.loads(out.read_text())
    assert r["status"] == "UNAVAILABLE"
    assert r["baseline_metrics"]["supported_unit_recall"] == {"scored_items": 1, "mean": .5}
    assert len(r["items"]) == 2
    assert r["counts"]["baseline_evaluated"] == 1
    assert r["paired_metrics"] is None


def test_report_import_does_not_load_chroma_or_ml_runtime():
    code = ("import runpy,sys; runpy.run_path(sys.argv[1],run_name='report_only'); "
            "assert not set(sys.modules).intersection({'chromadb','torch','transformers',"
            "'sentence_transformers','onnxruntime'})")
    subprocess.run([sys.executable, "-I", "-c", code,
                    str(ROOT / "ops/tools/chroma_recall_probe.py")], check=True, timeout=10)
