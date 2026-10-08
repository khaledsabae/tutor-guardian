"""Compare captured retrieval IDs. Never opens Chroma, models, or the network.

COMPARISON_COMPLETE describes supplied report coverage, never an upgrade pass.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ops/tools"))
from app.core.taxonomy import canonical_domain  # noqa: E402 — stdlib-only taxonomy
from golden_ci import score_retrieval  # noqa: E402 — the existing canonical scorer

SHA = re.compile(r"[0-9a-f]{64}\Z")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def strings(value, field):
    if not isinstance(value, list) or any(not isinstance(s, str) or not s.strip() for s in value):
        raise ValueError(f"invalid string list: {field}")
    if len(value) != len(set(value)):
        raise ValueError(f"duplicate values: {field}")
    return value


def keyed(rows, allowed=None):
    if not isinstance(rows, list):
        raise ValueError("items must be a list")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("invalid item id")
        ident = row["id"]
        if ident in out or (allowed is not None and ident not in allowed):
            raise ValueError("duplicate or unknown item id")
        out[ident] = row
    return out


def provenance(golden, catalog, old, new):
    reasons = []
    a, b = old.get("metadata", {}), new.get("metadata", {})
    for meta in (a, b):
        if not isinstance(meta, dict):
            return ["invalid capture metadata"]
        for key in ("corpus_sha256", "embedding_sha256", "query_policy_sha256",
                    "golden_sha256", "catalog_sha256"):
            if not isinstance(meta.get(key), str) or not SHA.fullmatch(meta[key]):
                reasons.append(f"missing/invalid {key}")
        if not isinstance(meta.get("chroma_version"), str) or not meta["chroma_version"]:
            reasons.append("missing Chroma version")
        if type(meta.get("top_k")) is not int or meta["top_k"] <= 0:
            reasons.append("missing/invalid top_k")
        for key, data in (("golden_sha256", golden), ("catalog_sha256", catalog)):
            if meta.get(key) != digest(data):
                reasons.append(f"{key} does not match supplied input")
    for key in ("corpus_sha256", "embedding_sha256", "query_policy_sha256", "top_k"):
        if a.get(key) != b.get(key):
            reasons.append(f"different {key}")
    return sorted(set(reasons))


def side(row, unit_ids, top_k):
    if row is None:
        return {"status": "MISSING"}
    if row.get("status") != "EVALUATED":
        return {"status": "UNAVAILABLE" if row.get("status") == "UNAVAILABLE" else "ERROR"}
    try:
        ids = strings(row.get("retrieved_unit_ids"), "retrieved_unit_ids")
        domains = strings(row.get("domains"), "domains")
        if not set(ids) <= unit_ids or len(ids) > top_k:
            raise ValueError("capture exceeds catalog or top_k")
    except ValueError:
        return {"status": "ERROR", "reason": "invalid capture IDs/domains or top_k"}
    return {"status": "EVALUATED", "unit_ids": ids,
            "domains": sorted({canonical_domain(d) for d in domains})}


def compare(golden, catalog, old, new):
    by_id = keyed(golden)
    if not by_id:
        raise ValueError("empty golden set")
    unit_ids = set(strings(catalog.get("unit_ids"), "catalog unit_ids"))
    domains = {canonical_domain(d) for d in strings(catalog.get("domains"), "catalog domains")}
    if not unit_ids:
        raise ValueError("empty index catalog")
    for g in golden:
        strings(g.get("expected_unit_ids"), "expected_unit_ids")
        strings(g.get("expected_domains"), "expected_domains")
        if not isinstance(g.get("category"), str) or not g["category"]:
            raise ValueError("missing golden category required by canonical scorer")
    report = {"status": "UNAVAILABLE", "scope": "supplied capture comparison only",
              "runtime_compatibility": "UNVERIFIED", "recall_gate": "NOT_EVALUATED",
              "provenance": "Caller-supplied metadata; consistency checks do not prove authenticity",
              "counts": {"golden": len(golden), "paired": 0, "unpaired": len(golden)},
              "paired_metrics": None, "items": []}
    if old is None or new is None:
        a, b, reasons, top_k = {}, {}, ["baseline/candidate capture absent"], 0
    else:
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise ValueError("capture must be an object")
        a, b = keyed(old.get("items"), by_id), keyed(new.get("items"), by_id)
        reasons = provenance(golden, catalog, old, new)
        top_k = old.get("metadata", {}).get("top_k")
        if type(top_k) is not int or top_k <= 0:
            top_k = 0
        report["status"] = "INCOMPARABLE" if reasons else "COMPARISON_COMPLETE"
        report["declared_versions"] = {name: cap.get("metadata", {}).get("chroma_version")
                                       for name, cap in (("old", old), ("new", new))}
    report["reasons"] = reasons
    paired = []
    for g in golden:
        # One source of denominator/alias/unsupported-label semantics: golden_ci.
        target_score = score_retrieval(g, [], [], domains, unit_ids)
        valid_ids = set(g["expected_unit_ids"]) - set(target_score["missing_expected_unit_ids"])
        valid_domains = {canonical_domain(d) for d in g["expected_domains"]} - set(target_score["unsupported_domains"])
        row = {"id": g["id"], "supported_units": sorted(valid_ids),
               "unsupported_unit_ids": target_score["missing_expected_unit_ids"],
               "supported_domains": sorted(valid_domains),
               "unsupported_domains": target_score["unsupported_domains"],
               "old": side(a.get(g["id"]), unit_ids, top_k),
               "new": side(b.get(g["id"]), unit_ids, top_k)}
        if not reasons and all(row[k]["status"] == "EVALUATED" for k in ("old", "new")):
            scores = {key: score_retrieval(
                g, row[key]["domains"], [{"unit_id": uid} for uid in row[key]["unit_ids"]],
                domains, unit_ids) for key in ("old", "new")}
            for name, expected, field in (("unit", valid_ids, "unit_ids"),
                                           ("domain", valid_domains, "domains")):
                row[f"{name}_targets"] = len(expected)
                for key in ("old", "new"):
                    hits = len(expected & set(row[key][field]))
                    row[key][f"{name}_hits"] = hits
                    row[key][f"{name}_recall"] = scores[key][f"supported_{name}_recall"]
            row["lost_supported_unit_ids"] = sorted(valid_ids & set(row["old"]["unit_ids"])
                                                     - set(row["new"]["unit_ids"]))
            paired.append(row)
        report["items"].append(row)
    report["counts"] = {"golden": len(golden), "paired": len(paired),
                        "unpaired": len(golden) - len(paired)}
    if not reasons:
        report["status"] = "COMPARISON_COMPLETE" if len(paired) == len(golden) else "PARTIAL"
        report["paired_metrics"] = {}
        for name in ("unit", "domain"):
            eligible = [r for r in paired if r[f"{name}_targets"]]
            denominator = sum(r[f"{name}_targets"] for r in eligible)
            block = {"paired_items": len(eligible), "supported_targets": denominator}
            for key in ("old", "new"):
                hits = sum(r[key][f"{name}_hits"] for r in eligible)
                block[key] = sum(r[key][f"{name}_recall"] for r in eligible) / len(eligible) if eligible else None
                block[f"{key}_hits"] = hits
                block[f"{key}_micro"] = hits / denominator if denominator else None
            block["delta"] = block["new"] - block["old"] if eligible else None
            report["paired_metrics"][f"{name}_recall"] = block
    return report


def baseline_inventory(golden, capture):
    """Inventory existing golden_ci scores; no catalog or new runtime is inferred."""
    expected = keyed(golden)
    rows = keyed(capture.get("items"), expected)
    report = {"status": "UNAVAILABLE", "reason": "1.x capture absent; paired comparison pending",
              "scope": "existing baseline artifact inventory only",
              "runtime_compatibility": "UNVERIFIED", "recall_gate": "NOT_EVALUATED",
              "paired_metrics": None, "baseline_metrics": {},
              "counts": {"golden": len(golden), "baseline_evaluated": 0,
                         "candidate_evaluated": 0, "paired": 0},
              "items": []}
    for g in golden:
        row = rows.get(g["id"], {"id": g["id"], "status": "MISSING"})
        report["items"].append({"id": g["id"], "baseline": row,
                                "candidate": {"status": "MISSING"}})
        report["counts"]["baseline_evaluated"] += row.get("status") == "EVALUATED"
    for key in ("supported_unit_recall", "supported_domain_recall"):
        values = []
        for row in rows.values():
            value = row.get(key)
            if row.get("status") == "EVALUATED" and value is not None:
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("invalid reported recall")
                values.append(value)
        report["baseline_metrics"][key] = {
            "scored_items": len(values), "mean": sum(values) / len(values) if values else None}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=ROOT / "ops/eval/golden_set.jsonl")
    parser.add_argument("--catalog", type=Path, help="frozen actual index ID/domain catalog for comparison")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    golden = []
    try:
        golden = [json.loads(l) for l in args.golden.read_text().splitlines() if l.strip()]
        old = json.loads(args.baseline.read_text()) if args.baseline else None
        new = json.loads(args.candidate.read_text()) if args.candidate else None
        if old is not None and new is None:
            report = baseline_inventory(golden, old)
        else:
            if args.catalog is None:
                raise ValueError("paired comparison requires frozen index catalog")
            catalog = json.loads(args.catalog.read_text())
            report = compare(golden, catalog, old, new)
        report["input_sha256"] = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                  for name, path in (("golden", args.golden),
                                                     ("baseline", args.baseline),
                                                     ("candidate", args.candidate)) if path is not None}
    except (ValueError, OSError, TypeError, AttributeError, KeyError) as exc:
        report = {"status": "INVALID_INPUT", "reason": type(exc).__name__,
                  "runtime_compatibility": "UNVERIFIED", "recall_gate": "NOT_EVALUATED",
                  "paired_metrics": None,
                  "items": [{"id": g.get("id"), "status": "UNAVAILABLE"}
                            for g in golden if isinstance(g, dict)]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "counts": report.get("counts"),
                      "runtime_compatibility": report["runtime_compatibility"]}))
    return 0 if report["status"] == "COMPARISON_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
