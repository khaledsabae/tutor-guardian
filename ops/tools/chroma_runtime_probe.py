#!/usr/bin/env python3
"""Hosted, copied-index runtime proof. Never run against a production volume.

Build uses the application's index_seed entry point. Candidate uses real
startup and query embeddings, with guards that turn rebuilds into failures.
The copy/summary/constraints commands need only the Python standard library.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
from importlib.metadata import version
import json
import logging
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import traceback
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PHASES = ("baseline-install", "harness-tests", "build", "copy", "candidate-install",
          "migration", "reopen", "tests")
SMOKE_PROBES = (("طفلي لا ينام جيدًا ويستيقظ كثيرًا", "medical", "2-3"),
                ("My child wakes up at night", "medical", "2-3"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def candidate_constraints(text):
    lines = text.splitlines(keepends=True)
    chroma = [line for line in lines if re.match(r"^chromadb==", line)]
    if len(chroma) != 1:
        raise ValueError("expected exactly one production chromadb pin")
    return "".join(line for line in lines if line not in chroma)


def disk_snapshot(path):
    """Hash every persisted file and read SQLite schema/migrations read-only."""
    files = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"symlink in index: {item}")
        if item.is_file():
            digest = hashlib.sha256()
            with item.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            files[item.relative_to(path).as_posix()] = digest.hexdigest()
    database = path / "chroma.sqlite3"
    if not database.is_file() or "_content_fingerprint" not in files:
        raise ValueError("incomplete persisted index")
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        schema = [list(row) for row in db.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name")]
        has_migrations = any(row[1] == "migrations" for row in schema)
        migrations = sorted([list(row) for row in db.execute("SELECT * FROM migrations")],
                            key=lambda row: json.dumps(row)) if has_migrations else []
    return {"files": files, "schema": schema, "migrations": migrations,
            "fingerprint": (path / "_content_fingerprint").read_text()}


def copy_index(source, target):
    source, target = source.resolve(), target.resolve()
    if target.exists() or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("refusing existing or overlapping index destination")
    before = disk_snapshot(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    copied = disk_snapshot(target)
    if before != copied or before != disk_snapshot(source):
        raise RuntimeError("source changed or persisted copy is not identical")
    return {"source": str(source), "target": str(target), "identical_copy": True,
            "before": before}


def migration_behavior(before, after):
    if before["schema"] != after["schema"] or before["migrations"] != after["migrations"]:
        return "migrated_in_place"
    return "opened_in_place_no_schema_change"


def collection_digest(data):
    vectors = data["embeddings"]
    if hasattr(vectors, "tolist"):
        vectors = vectors.tolist()
    rows = sorted(zip(data["ids"], data["documents"], data["metadatas"], vectors),
                  key=lambda row: row[0])
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def collection_state(collection, retrieval):
    data = collection.get(include=["documents", "metadatas", "embeddings"])
    return {"count": collection.count(), "digest": collection_digest(data),
            "collection_id": str(collection.id),
            "fingerprint": retrieval._read_fingerprint(retrieval.CHROMA_PERSIST_DIR)}


def forbidden(*args, **kwargs):
    raise RuntimeError("rebuild/write attempted against copied index")


class ReadOnlyCollection:
    def __init__(self, collection):
        self.real = collection
        self.query_calls = 0

    def __getattr__(self, name):
        if name in {"add", "upsert", "update", "delete", "modify"}:
            return forbidden
        return getattr(self.real, name)

    def query(self, **kwargs):
        result = self.real.query(**kwargs)
        self.query_calls += 1  # Only successful real Chroma calls count.
        return result


class ReadOnlyClient:
    def __init__(self, client, collections):
        self.real = client
        self.collections = collections

    def __getattr__(self, name):
        if name in {"create_collection", "get_or_create_collection", "delete_collection",
                    "reset"}:
            return forbidden
        return getattr(self.real, name)

    def get_collection(self, *args, **kwargs):
        result = ReadOnlyCollection(self.real.get_collection(*args, **kwargs))
        self.collections.append(result)
        return result


class VectorErrors(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.errors = []

    def emit(self, record):
        self.errors.append(record.getMessage())


def validate_smoke(results, calls, errors):
    if errors:
        raise RuntimeError("; ".join(errors))
    if calls < 1:
        raise RuntimeError("smoke did not execute a real vector query")
    if not results:
        raise RuntimeError("real vector smoke returned empty results")


def load_runtime(index):
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services import retrieval

    retrieval.CHROMA_PERSIST_DIR = index.resolve()
    retrieval.SEED_DIR = index.parent / "absent-seed"
    retrieval._collection = None
    retrieval._index_built = False
    retrieval._TELEMETRY_DB = index.parent / "retrieval-telemetry.db"
    return retrieval


def build(index):
    if version("chromadb") != "0.6.3":
        raise RuntimeError("baseline must use production chromadb 0.6.3")
    retrieval = load_runtime(index)
    from app.services import index_seed, reranker

    if index_seed.main() != 0:
        raise RuntimeError("production index_seed failed")
    # Same cached model warmup as backend-env; backend tests forbid HF network.
    reranker._get_model()
    state = collection_state(retrieval._get_collection(), retrieval)
    if state["count"] < 1:
        raise RuntimeError("empty baseline knowledge index")
    return {"chromadb": version("chromadb"), "status": "passed", **state}


def candidate(index, baseline, copied):
    report = {"status": "failed", "stage": "import", "behavior": "not_proven"}
    errors = VectorErrors()
    log = logging.getLogger("app.services.retrieval")
    log.addHandler(errors)
    try:
        if version("chromadb") != "1.5.9":
            raise RuntimeError("candidate must use chromadb 1.5.9")
        if baseline.get("chromadb") != "0.6.3" or not copied.get("identical_copy"):
            raise RuntimeError("missing verified 0.6.3 baseline copy provenance")
        report["before"] = disk_snapshot(index)
        if report["before"]["fingerprint"] != baseline["fingerprint"]:
            raise RuntimeError("copied fingerprint differs from baseline")
        # The original database must remain byte-for-byte unchanged.
        if disk_snapshot(Path(copied["source"])) != copied["before"]:
            raise RuntimeError("original 0.6.3 index changed")
        retrieval = load_runtime(index)
        import chromadb

        report["stage"] = "open"
        client = chromadb.PersistentClient(path=str(index.resolve()))
        collections = []
        readonly = ReadOnlyClient(client, collections)
        embedder = retrieval._embedder()
        original_embed = type(embedder).__call__

        def query_embeddings_only(self, input):
            if any(not text.startswith("query: ") for text in input):
                forbidden()
            return original_embed(self, input)

        with ExitStack() as stack:
            stack.enter_context(patch.object(chromadb, "PersistentClient", return_value=readonly))
            stack.enter_context(patch.object(retrieval, "_purge_persist_dir", forbidden))
            stack.enter_context(patch.object(type(embedder), "__call__", query_embeddings_only))
            report["stage"] = "startup"
            retrieval._ensure_index()  # Actual production startup, never mark built early.
            state = collection_state(retrieval._get_collection(), retrieval)
            for key in ("count", "digest", "collection_id", "fingerprint"):
                if state[key] != baseline[key]:
                    raise RuntimeError(f"copied collection changed: {key}")
            report.update(state)
            report["stage"] = "smoke"
            results = []
            for question, domain, age in SMOKE_PROBES:
                before_calls = sum(c.query_calls for c in collections)
                # No frozen embeddings: real application embedding function and query API.
                rows = retrieval.retrieve_relevant_units(question, domain, age, top_k=4)
                calls = sum(c.query_calls for c in collections) - before_calls
                validate_smoke(rows, calls, errors.errors)
                results.append({"question": question, "ids": [r["unit_id"] for r in rows],
                                "query_calls": calls})
            if collection_state(retrieval._get_collection(), retrieval) != state:
                raise RuntimeError("query altered persisted collection content")
            report["smoke"] = results
            report["query_calls"] = sum(c.query_calls for c in collections)
        report["after"] = disk_snapshot(index)
        report["behavior"] = migration_behavior(report["before"], report["after"])
        report["changed_files"] = sorted(name for name in set(report["before"]["files"]) |
                                         set(report["after"]["files"])
                                         if report["before"]["files"].get(name) !=
                                         report["after"]["files"].get(name))
        if disk_snapshot(Path(copied["source"])) != copied["before"]:
            raise RuntimeError("original baseline changed during migration")
        report["status"] = "passed"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        report["locations"] = source_locations(report["traceback"])
        if report["stage"] == "open":
            report["behavior"] = "refused_copied_index"
        elif report["stage"] in {"startup", "smoke"}:
            report["behavior"] = "opened_but_runtime_incompatible"
        # Opening may already have migrated SQLite, even if later runtime failed.
        try:
            report["after"] = disk_snapshot(index)
            report["schema_changed"] = migration_behavior(
                report["before"], report["after"]) == "migrated_in_place"
        except Exception:
            pass  # Keep the original failure and traceback as the primary evidence.
    finally:
        log.removeHandler(errors)
    return report


def source_locations(text):
    direct = re.findall(r"((?:backend|ops)/[\w/.-]+\.py):([0-9]+)", text)
    traces = re.findall(r'File "[^"\n]*?((?:backend|ops)/[^"\n]+\.py)", line ([0-9]+)', text)
    return sorted({f"{path}:{line}" for path, line in direct + traces})


def junit_report(path):
    result = {"tests": 0, "passed": 0, "failures": 0, "errors": 0,
              "skipped": 0, "locations": [], "details": []}
    if not path.exists():
        result["missing"] = True
        return result
    try:
        root = ET.parse(path).getroot()
        cases = list(root.iter("testcase"))
        result["tests"] = len(cases)
        for case in cases:
            bad = False
            for tag, key in (("failure", "failures"), ("error", "errors"), ("skipped", "skipped")):
                nodes = case.findall(tag)
                if nodes:
                    result[key] += 1
                    bad = True
                    if tag != "skipped":
                        result["details"].append({"test": case.get("name"),
                                                  "text": "\n".join(n.text or n.get("message", "") for n in nodes)})
            if not bad:
                result["passed"] += 1
        result["locations"] = source_locations("\n".join(item["text"] for item in result["details"]))
    except (ET.ParseError, OSError) as exc:
        result["invalid"] = str(exc)
    return result


def make_summary(evidence):
    phases = {}
    for phase in PHASES:
        path = evidence / f"{phase}.exit"
        phases[phase] = path.read_text().strip() if path.exists() else "NOT RUN"
    migration_path = evidence / "migration.json"
    migration = json.loads(migration_path.read_text()) if migration_path.exists() else {}
    reopen_path = evidence / "reopen.json"
    reopen = json.loads(reopen_path.read_text()) if reopen_path.exists() else {}
    tests = junit_report(evidence / "backend-junit.xml")
    locations = set(tests["locations"]) | set(migration.get("locations", [])) | set(reopen.get("locations", []))
    for path in evidence.glob("*.log"):
        locations.update(source_locations(path.read_text(errors="replace")))
    passed = (all(exit_code == "0" for exit_code in phases.values()) and
              migration.get("status") == "passed" and reopen.get("status") == "passed" and tests["tests"] > 0 and
              tests["passed"] > 0 and not tests["failures"] and not tests["errors"] and
              not tests.get("invalid"))
    report = {"status": "passed" if passed else "failed_or_incomplete", "phases": phases,
              "migration": migration, "reopen": reopen, "tests": tests, "locations": sorted(locations)}
    text = ("# Chroma 0.6.3 → 1.5.9 runtime experiment\n\n"
            f"Result: **{report['status']}**\n\n"
            f"Copied index: **{migration.get('behavior', 'not proven')}**, "
            f"stage: {migration.get('stage', 'NOT RUN')}\n\n"
            f"Fresh-process reopen: **{reopen.get('status', 'NOT RUN')}**\n\n"
            "Schema and migrations before/after, all file hashes, collection UUID, "
            "fingerprint, IDs/documents/metadata/vector digest and real Arabic/English "
            "query results are in migration.json and reopen.json. The second process "
            "checks persistence after the first process exits.\n\n"
            "Rebuild/export-import is not attempted; if opening is refused, whether "
            "either is necessary remains unproven. Never point 0.6.3 back at the "
            "candidate copy: in-place schema migration is potentially irreversible.\n\n"
            f"Backend JUnit: {tests['tests']} tests; {tests['passed']} passed; "
            f"{tests['failures']} failures; {tests['errors']} errors; {tests['skipped']} skipped.\n\n"
            "| Phase | Exit code |\n|---|---|\n" +
            "".join(f"| {phase} | {code} |\n" for phase, code in phases.items()) +
            "\n## Failures and possible API breakages\n\n" +
            (migration.get("error", "No migration exception recorded.") + "\n\n") +
            (reopen.get("error", "No reopen exception recorded.") + "\n\n") +
            ("\n".join(f"- `{location}`" for location in sorted(locations)) or
             "No file:line failure locations recorded.") +
            "\n\nLocations identify failures; test/environment failures are not automatically "
            "Chroma API breakages. See full JUnit tracebacks and phase logs. "
            "Package freezes, resolver report and pip-check logs are uploaded even on failure.\n")
    return report, text, passed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "candidate"):
        sub = subs.add_parser(command)
        sub.add_argument("--index", type=Path, required=True)
        sub.add_argument("--out", type=Path, required=True)
        if command == "candidate":
            sub.add_argument("--baseline", type=Path, required=True)
            sub.add_argument("--copy-report", type=Path, required=True)
    sub = subs.add_parser("copy")
    sub.add_argument("--source", type=Path, required=True)
    sub.add_argument("--target", type=Path, required=True)
    sub.add_argument("--out", type=Path, required=True)
    sub = subs.add_parser("constraints")
    sub.add_argument("--source", type=Path, required=True)
    sub.add_argument("--out", type=Path, required=True)
    sub = subs.add_parser("summary")
    sub.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "constraints":
        args.out.write_text(candidate_constraints(args.source.read_text()))
        return 0
    if args.command == "summary":
        report, text, passed = make_summary(args.evidence)
        write_json(args.evidence / "summary.json", report)
        (args.evidence / "summary.md").write_text(text)
        return 0 if passed else 1
    if args.command == "build":
        report = build(args.index)
    elif args.command == "copy":
        report = copy_index(args.source, args.target)
    else:
        report = candidate(args.index, json.loads(args.baseline.read_text()),
                           json.loads(args.copy_report.read_text()))
    write_json(args.out, report)
    print(json.dumps({k: v for k, v in report.items() if k in
                      {"status", "behavior", "stage", "count", "error"}}, ensure_ascii=False))
    return 1 if report.get("status") == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
