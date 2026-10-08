"""Runtime harness contracts without model downloads or Chroma installs."""
import importlib.util
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def probe():
    path = ROOT / "ops/tools/chroma_runtime_probe.py"
    assert path.exists(), "runtime migration probe is missing"
    spec = importlib.util.spec_from_file_location("runtime_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def index(path):
    path.mkdir()
    with sqlite3.connect(path / "chroma.sqlite3") as db:
        db.execute("CREATE TABLE migrations (dir TEXT, version INTEGER)")
        db.execute("INSERT INTO migrations VALUES ('sysdb', 1)")
    (path / "_content_fingerprint").write_text("fingerprint")
    (path / "vector.bin").write_bytes(b"persisted vectors")
    return path


def test_copy_preserves_source_and_verifies_every_file(tmp_path):
    p = probe()
    source = index(tmp_path / "source")
    before = p.disk_snapshot(source)
    target = tmp_path / "copy"
    report = p.copy_index(source, target)
    assert p.disk_snapshot(source) == before == p.disk_snapshot(target)
    assert report["identical_copy"] is True
    assert report["before"]["migrations"] == [["sysdb", 1]]


@pytest.mark.parametrize("target_name", ["source", "existing", "source/nested"])
def test_copy_refuses_overwrite_or_nested_destination(tmp_path, target_name):
    p = probe()
    source = index(tmp_path / "source")
    (tmp_path / "existing").mkdir()
    with pytest.raises(ValueError):
        p.copy_index(source, tmp_path / target_name)


def test_copy_refuses_symlinks_and_incomplete_index(tmp_path):
    p = probe()
    source = index(tmp_path / "source")
    (source / "linked").symlink_to(source / "vector.bin")
    with pytest.raises(ValueError, match="symlink"):
        p.copy_index(source, tmp_path / "copy")
    (source / "linked").unlink()
    (source / "_content_fingerprint").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        p.copy_index(source, tmp_path / "copy")


def test_snapshot_does_not_modify_sqlite_and_detects_schema_migration(tmp_path):
    p = probe()
    source = index(tmp_path / "source")
    before = p.disk_snapshot(source)
    assert p.disk_snapshot(source) == before
    with sqlite3.connect(source / "chroma.sqlite3") as db:
        db.execute("ALTER TABLE migrations ADD COLUMN hash TEXT")
        db.execute("INSERT INTO migrations VALUES ('sysdb', 2, 'abc')")
    after = p.disk_snapshot(source)
    assert p.migration_behavior(before, after) == "migrated_in_place"
    assert p.migration_behavior(before, before) == "opened_in_place_no_schema_change"


def test_collection_digest_is_order_independent_and_includes_vectors():
    p = probe()
    data = {"ids": ["b", "a"], "documents": ["body b", "body a"],
            "metadatas": [{"domain": "sleep"}, {"domain": "food"}],
            "embeddings": [[1., 0.], [0., 1.]]}
    reverse = {key: list(reversed(values)) for key, values in data.items()}
    assert p.collection_digest(data) == p.collection_digest(reverse)
    reverse["embeddings"][0] = [1., 1.]
    assert p.collection_digest(data) != p.collection_digest(reverse)


@pytest.mark.parametrize("method", ["add", "upsert", "update", "delete"])
def test_guard_blocks_writes_but_runs_real_queries(method):
    p = probe()
    calls = []
    real = SimpleNamespace(query=lambda **kw: calls.append(kw) or {"ids": [["a"]]},
                           count=lambda: 1)
    guarded = p.ReadOnlyCollection(real)
    assert guarded.count() == 1
    assert guarded.query(query_texts=["question"])["ids"] == [["a"]]
    assert guarded.query_calls == 1 and calls
    with pytest.raises(RuntimeError, match="rebuild/write"):
        getattr(guarded, method)(ids=["a"])


def test_vector_log_error_is_not_hidden_by_nonempty_fallback():
    p = probe()
    with pytest.raises(RuntimeError, match="vector error"):
        p.validate_smoke([{"unit_id": "a"}], 2, ["vector error"])
    with pytest.raises(RuntimeError, match="real vector"):
        p.validate_smoke([{"unit_id": "a"}], 0, [])
    with pytest.raises(RuntimeError, match="empty"):
        p.validate_smoke([], 1, [])
    p.validate_smoke([{"unit_id": "a"}], 1, [])


def test_candidate_constraints_change_only_chromadb():
    p = probe()
    text = "# python: 3.11.17\nchromadb==0.6.3\ntorch==2.13.0+cpu\nchroma-hnswlib==0.7.6\n"
    assert p.candidate_constraints(text) == text.replace("chromadb==0.6.3\n", "")
    with pytest.raises(ValueError):
        p.candidate_constraints("torch==2.13.0+cpu\n")


def test_junit_counts_actual_cases_and_collects_source_locations(tmp_path):
    p = probe()
    xml = tmp_path / "junit.xml"
    xml.write_text('<testsuites tests="6"><testsuite tests="3">'
                   '<testcase name="ok"/><testcase name="bad"><failure>'
                   'backend/app/services/retrieval.py:151: AttributeError: API changed'
                   '</failure></testcase><testcase name="skip"><skipped/>'
                   '</testcase></testsuite></testsuites>')
    report = p.junit_report(xml)
    assert report["tests"] == 3 and report["passed"] == 1
    assert report["failures"] == 1 and report["skipped"] == 1
    assert "backend/app/services/retrieval.py:151" in report["locations"]


def test_summary_fails_closed_without_tests_or_failed_phases(tmp_path):
    p = probe()
    report, text, passed = p.make_summary(tmp_path)
    assert not passed and report["tests"]["tests"] == 0
    assert "NOT RUN" in text and "not proven" in text


def test_summary_accepts_only_complete_positive_evidence(tmp_path):
    p = probe()
    for phase in p.PHASES:
        (tmp_path / f"{phase}.exit").write_text("0")
    (tmp_path / "backend-junit.xml").write_text(
        '<testsuite><testcase name="real"/></testsuite>')
    result = {"status": "passed", "behavior": "migrated_in_place",
              "stage": "smoke", "query_calls": 2, "count": 1288}
    (tmp_path / "migration.json").write_text(json.dumps(result))
    (tmp_path / "reopen.json").write_text(json.dumps(result))
    report, text, passed = p.make_summary(tmp_path)
    assert passed and report["tests"]["passed"] == 1
    assert "migrated_in_place" in text
    (tmp_path / "tests.exit").write_text("1")
    assert p.make_summary(tmp_path)[2] is False


def test_traceback_locations_include_file_line():
    p = probe()
    assert p.source_locations('File "/repo/backend/app/services/retrieval.py", line 147, in _get_collection') == [
        "backend/app/services/retrieval.py:147"]


def test_smoke_filters_match_real_canonical_knowledge_domains():
    """A plausible topic like 'sleep' is not a knowledge-unit domain."""
    import ast

    p = probe()
    assert hasattr(p, "SMOKE_PROBES"), "smoke filters must be inspectable and validated"
    tree = ast.parse((ROOT / "backend/app/core/taxonomy.py").read_text())
    domains = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.AnnAssign) and
                   isinstance(node.target, ast.Name) and node.target.id == "CANONICAL_DOMAINS")
    for _, domain, age in p.SMOKE_PROBES:
        assert domain in domains, f"unknown probe domain: {domain}"
        units = [json.loads(path.read_text()) for path in (ROOT / "knowledge_base/units").glob("*.json")]
        assert any(unit.get("domain") == domain and unit.get("age_group") in {age, "unspecified"}
                   for unit in units), f"no real units match {domain}/{age}"


def test_junit_python_traceback_source_location_survives_xml_parsing(tmp_path):
    p = probe()
    xml = tmp_path / "junit.xml"
    xml.write_text('<testsuite><testcase name="bad"><failure>'
                   'File "/repo/backend/app/services/retrieval.py", line 147, in _get_collection'
                   '</failure></testcase></testsuite>')
    assert p.junit_report(xml)["locations"] == ["backend/app/services/retrieval.py:147"]


def test_summary_rejects_failed_reopen_even_if_exit_status_was_zero(tmp_path):
    p = probe()
    for phase in p.PHASES:
        (tmp_path / f"{phase}.exit").write_text("0")
    (tmp_path / "backend-junit.xml").write_text('<testsuite><testcase name="ok"/></testsuite>')
    (tmp_path / "migration.json").write_text(json.dumps({"status": "passed"}))
    (tmp_path / "reopen.json").write_text(json.dumps({"status": "failed", "error": "lost vectors"}))
    assert p.make_summary(tmp_path)[2] is False
