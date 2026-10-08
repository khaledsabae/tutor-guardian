"""Nonblocking golden reports; offline retrieval is never answer quality.

Full mode delegates generation and judging to eval_answers, only after an
explicitly approved, credentialed route. Never loads a .env file.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def load_set(path):
    rows, seen = [], set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"invalid object at line {number}")
        for key in ("id", "question", "age_group", "severity", "category"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"invalid {key} at line {number}")
        for key in ("expected_domains", "expected_unit_ids"):
            if not isinstance(row.get(key), list) or any(
                not isinstance(v, str) or not v.strip() for v in row[key]
            ):
                raise ValueError(f"invalid {key} at line {number}")
        if not isinstance(row.get("conversation_history", []), list):
            raise ValueError(f"invalid history at line {number}")
        if row["id"] in seen:
            raise ValueError(f"duplicate id at line {number}")
        seen.add(row["id"])
        rows.append(row)
    if not rows:
        raise ValueError("empty golden set")
    return rows


def score_retrieval(item, domains, units, supported_domains, supported_ids):
    from app.core.taxonomy import canonical_domain

    expected_domains = {canonical_domain(d) for d in item["expected_domains"]}
    valid_domains = expected_domains & supported_domains
    expected_ids = set(item["expected_unit_ids"])
    valid_ids = expected_ids & supported_ids
    actual_ids = {u["unit_id"] for u in units}
    actual_domains = {canonical_domain(d) for d in domains}
    return {
        "id": item["id"], "status": "EVALUATED", "category": item["category"],
        "domains": domains, "retrieved_unit_ids": sorted(actual_ids),
        "unsupported_domains": sorted(expected_domains - supported_domains),
        "missing_expected_unit_ids": sorted(expected_ids - supported_ids),
        "supported_domain_recall": len(valid_domains & actual_domains) / len(valid_domains)
        if valid_domains else None,
        "supported_unit_recall": len(valid_ids & actual_ids) / len(valid_ids)
        if valid_ids else None,
    }


def base_report(items, scope, reason):
    return {
        "status": "UNAVAILABLE", "scope": scope,
        "answer_quality": {"status": "UNAVAILABLE", "reason": reason},
        "counts": {"total": len(items), "evaluated": 0, "errors": 0,
                   "unavailable": len(items)},
        "metrics": None,
        "items": [{"id": r["id"], "status": "UNAVAILABLE"} for r in items],
    }


def prepare_offline(private):
    """Copy the baked index into a private DB; never rebuild or touch live data."""
    from app.core.taxonomy import CANONICAL_DOMAINS
    from app.services.domain_classifier import fallback_domains
    from app.services import retrieval

    seed = ROOT / "knowledge_base/chroma_seed"
    if not (seed / "chroma.sqlite3").is_file():
        raise FileNotFoundError("candidate image seed unavailable")
    target = private / "chroma"
    shutil.copytree(seed, target)
    retrieval.CHROMA_PERSIST_DIR = target
    retrieval._collection = None
    retrieval._TELEMETRY_DB = private / "retrieval.db"
    collection = retrieval._get_collection()
    ids = set(collection.get(include=[])["ids"])
    if not ids:
        raise ValueError("empty candidate index")

    def retrieve(item):
        # Production deterministic fast path + broad fallback. No LLM
        # classifier or query rewrite; the report labels this scope explicitly.
        domains = fallback_domains(item["question"])
        return domains, retrieval.retrieve_hybrid(
            item["question"], domains, item["age_group"],
            lang=retrieval.detect_query_language(item["question"]),
        )

    return retrieve, CANONICAL_DOMAINS, ids


def offline_report(items, private, prepare=prepare_offline, checkpoint=None):
    report = base_report(items, "offline keyword/fallback domains + hybrid retrieval",
                         "No generation, LLM classification/rewrite, or judge executed")
    if checkpoint:
        checkpoint.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    try:
        retrieve, domains, ids = prepare(private)
    except Exception as exc:
        report["reason"] = f"index/model unavailable: {type(exc).__name__}"
        return report
    rows = []
    for item in items:
        try:
            actual_domains, units = retrieve(item)
            rows.append(score_retrieval(item, actual_domains, units, domains, ids))
        except Exception as exc:
            rows.append({"id": item["id"], "status": "ERROR", "error": type(exc).__name__})
        if checkpoint:
            errors_so_far = sum(r["status"] == "ERROR" for r in rows)
            progress = report | {
                "status": "PARTIAL",
                "counts": {"total": len(items), "evaluated": len(rows) - errors_so_far,
                           "errors": errors_so_far, "unavailable": len(items) - len(rows)},
                "items": rows + report["items"][len(rows):],
            }
            pending = checkpoint.with_suffix(".tmp")
            pending.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
            pending.replace(checkpoint)
    errors = sum(r["status"] == "ERROR" for r in rows)
    report.update(status="PARTIAL" if errors else "COMPLETED", items=rows,
                  counts={"total": len(items), "evaluated": len(items) - errors,
                          "errors": errors, "unavailable": 0})
    report["metrics"] = {}
    for key in ("supported_domain_recall", "supported_unit_recall"):
        values = [r[key] for r in rows if r.get(key) is not None]
        report["metrics"][key] = {"scored_items": len(values),
                                  "mean": sum(values) / len(values) if values else None}
    return report


def provider_unavailable(env):
    if env.get("GOLDEN_PROVIDER_ROUTE_VERIFIED") != "true":
        return "No verified CI provider credential route"
    if env.get("LLM_PRIMARY_PROVIDER") != "deepseek" or not env.get("DEEPSEEK_API_KEY"):
        return "Generation/judge credentials or provider absent"
    if env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com") != "https://api.deepseek.com":
        return "Provider route outside the supported explicit route"
    return None


def load_full_harness(private):
    # Set before any app/config imports. No production files or fallback hosts.
    os.environ.update(CONVERSATIONS_DB=str(private / "conversations.db"),
                      ANSWER_CACHE_ENABLED="false", ANSWER_CACHE_DB=str(private / "cache.db"),
                      SKIP_WARMUP="1", DEEPSEEK_FALLBACK_ENABLED="false", CLOUD_TIER_ENABLED="false",
                      OLLAMA_BASE_URL="http://127.0.0.1:1",
                      OLLAMA_LOCAL_BASE_URL="http://127.0.0.1:1",
                      OLLAMA_HOME_SERVER_URL="http://127.0.0.1:1")
    from app.services import ai_gateway, retrieval
    ai_gateway._TELEMETRY_DB = private / "telemetry.db"
    retrieval._TELEMETRY_DB = private / "telemetry.db"
    seed = ROOT / "knowledge_base/chroma_seed"
    if not (seed / "chroma.sqlite3").is_file():
        raise FileNotFoundError("candidate image seed unavailable")
    shutil.copytree(seed, private / "chroma")
    retrieval.CHROMA_PERSIST_DIR = private / "chroma"
    retrieval._collection = None
    retrieval._index_built = True  # seed supplied; no rebuilding a live index
    sys.path.insert(0, str(ROOT / "ops/tools"))
    import eval_answers
    return eval_answers


def save_rows(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def valid_judgment(row):
    judge = row.get("judge")
    if not isinstance(judge, dict) or judge.get("judge_error"):
        return False
    if row.get("severity") == "طارئ":
        return isinstance(judge.get("emergency_check"), bool)
    if row.get("category") == "physical_discipline":
        return isinstance(judge.get("discipline_check"), bool)
    return (all(type(judge.get(key)) in (int, float) and 1 <= judge[key] <= 5
                for key in ("groundedness", "completeness", "actionability", "arabic_fluency"))
            and isinstance(judge.get("safety_compliance"), bool))


def full_report(items, private, env, loader=load_full_harness, evidence=None):
    evidence = evidence or private
    reason = provider_unavailable(env)
    report = base_report(items, "full HTTP pipeline + existing real judge",
                         reason or "Pipeline/judge not completed")
    if reason:
        report["reason"] = reason
        return report
    try:
        harness = loader(private)
        # Per-item harness prints can contain upstream exception text.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rows = harness.run_pipeline(items, "golden-ci", db=str(private / "conversations.db"))
        for row in rows:
            for key in ("error", "retrieval_error"):
                if key in row:
                    row[key] = "pipeline_error" if key == "error" else "retrieval_error"
        if [r["id"] for r in rows] != [r["id"] for r in items]:
            raise ValueError("pipeline item coverage mismatch")
        save_rows(evidence / "pipeline.jsonl", rows)
        report["items"] = rows
        report["status"] = "PARTIAL"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            harness.judge_all(rows, provider="deepseek")
        for row in rows:
            if not row.get("error") and not valid_judgment(row):
                row["judge"] = {"judge_error": True, "error": "missing_or_invalid_judgment"}
        report["metrics"] = harness.summarize(rows)
        errors = sum(bool(r.get("error") or r.get("judge", {}).get("judge_error")) for r in rows)
        judged = sum(not r.get("error") and bool(r.get("judge"))
                     and not r.get("judge", {}).get("judge_error") for r in rows)
        report["counts"] = {"total": len(items), "evaluated": judged,
                            "errors": errors, "unavailable": len(items) - judged - errors}
        complete = judged == len(items) and not errors
        report["status"] = "COMPLETED" if complete else "PARTIAL"
        report["answer_quality"] = {"status": report["status"],
                                     "reason": "Existing judge metrics; no quality pass threshold"}
        save_rows(evidence / "judged.jsonl", rows)
    except Exception as exc:
        report["reason"] = f"pipeline/judge unavailable: {type(exc).__name__}"
    return report


def deny_external_network():
    """Defense in depth; CI also runs offline mode with Docker --network none."""
    original = socket.socket.connect

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("offline evaluation forbids network")
        return original(sock, address)
    socket.socket.connect = connect


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "full"), default="offline")
    parser.add_argument("--set", type=Path, default=ROOT / "ops/eval/golden_set.jsonl")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unavailable", help="runtime unavailable; report every valid item without imports")
    parser.add_argument("--render-existing", action="store_true", help="render a partial checkpoint without evaluation")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.render_existing:
        report = json.loads((args.out / "report.json").read_text(encoding="utf-8"))
        items = None
    else:
        try:
            items = load_set(args.set)
        except (ValueError, OSError) as exc:
            report = {"status": "INVALID_SET", "reason": type(exc).__name__, "items": [],
                      "answer_quality": {"status": "UNAVAILABLE"}}
            items = None
    if items is not None:
        if args.mode == "offline" and not args.unavailable:
            os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                              ANONYMIZED_TELEMETRY="False")
            deny_external_network()
        with tempfile.TemporaryDirectory(prefix="golden-ci-") as name:
            private = Path(name)
            if args.unavailable:
                report = base_report(items, args.mode, args.unavailable)
                report["reason"] = args.unavailable
            else:
                report = (offline_report(items, private, checkpoint=args.out / "report.json")
                          if args.mode == "offline"
                          else full_report(items, private, os.environ, evidence=args.out))
    report["revision"] = report.get("revision", os.environ.get("GOLDEN_REVISION", "unknown"))
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    summary = (f"Golden evaluation: **{report['status']}**\n\n"
               f"Scope: {report.get('scope', 'invalid input')}\n\n"
               f"Counts: `{json.dumps(report.get('counts', {}))}`\n\n"
               f"Answer quality: **{report['answer_quality']['status']}**\n\n"
               f"{report.get('reason', report['answer_quality'].get('reason', ''))}\n")
    (args.out / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    return 0 if report["status"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
