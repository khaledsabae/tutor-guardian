#!/usr/bin/env python3
"""
Knowledge-Base Integrity Guard — حارس سلامة قاعدة المعرفة
==========================================================
The tutor-guardian analog of analytics-platform's schema-drift detector.

The same class of bug — sources of truth silently diverging — lives here
between THREE places:
    1. knowledge_base/units/*.json   (the data)
    2. knowledge_base/schema/*.json  (the contract)
    3. backend/app/core/taxonomy.py  (the code's vocabulary)
    4. ChromaDB index                (the serving layer)

This guard fails loudly when any of them drift apart.

Checks (tiered like the analytics detector — 🔴 errors block, 🟡 warnings inform):
  META   🔴 schema enums must equal taxonomy.py canonical sets
  DATA   🔴 every unit parses + validates against the JSON schema
         🔴 domain/age_group/severity/intervention_type within canonical enums
         🔴 no duplicate unit ids
         🟡 missing optional metadata (reference_type/version/updated_at)
  INDEX  🔴 (--check-index) ChromaDB ids must match units on disk

Exit: 0 = in sync · 1 = drift/errors

Usage:
    python ops/tools/check_kb_integrity.py                 # fast (no vector index)
    python ops/tools/check_kb_integrity.py --check-index   # also verify ChromaDB
    python ops/tools/check_kb_integrity.py --check-index --rebuild  # rebuild then verify
"""
import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core import taxonomy  # noqa: E402

UNITS_DIR = ROOT / "knowledge_base" / "units"
SCHEMA_PATH = ROOT / "knowledge_base" / "schema" / "knowledge_unit.schema.json"
INDEX_JSON = ROOT / "knowledge_base" / "units_index.json"

# schema-property → canonical taxonomy set (the meta-check)
ENUM_FIELDS = {
    "domain": taxonomy.CANONICAL_DOMAINS,
    "age_group": taxonomy.CANONICAL_AGE_GROUPS,
    "severity": taxonomy.CANONICAL_SEVERITIES,
    "intervention_type": taxonomy.CANONICAL_INTERVENTIONS,
    "reference_type": taxonomy.CANONICAL_REFERENCE_TYPES,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-index", action="store_true", help="verify ChromaDB ↔ disk sync")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the index before verifying")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    print("\n" + "=" * 67)
    print("  KNOWLEDGE-BASE INTEGRITY GUARD — حارس سلامة قاعدة المعرفة")
    print("=" * 67)

    # ── META: schema enums must equal taxonomy.py ──────────────────────────
    for field, canon in ENUM_FIELDS.items():
        schema_enum = set(schema.get("properties", {}).get(field, {}).get("enum", []))
        if schema_enum != canon:
            only_schema = schema_enum - canon
            only_code = canon - schema_enum
            msg = f"META: schema `{field}` enum ≠ taxonomy.py"
            if only_schema:
                msg += f" | in schema not code: {sorted(only_schema)}"
            if only_code:
                msg += f" | in code not schema: {sorted(only_code)}"
            errors.append(msg)

    # ── DATA: validate every unit ──────────────────────────────────────────
    validator = Draft202012Validator(schema)
    files = sorted(UNITS_DIR.glob("*.json"))
    if not files:
        errors.append(f"DATA: no units found in {UNITS_DIR}")

    ids: dict[str, str] = {}  # id → filename
    disk_ids: set[str] = set()
    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"DATA: {fp.name} is not valid JSON: {e}")
            continue

        # schema validation
        for err in validator.iter_errors(data):
            loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
            errors.append(f"DATA: {fp.name} [{loc}]: {err.message}")

        # duplicate id
        uid = data.get("id")
        if uid:
            disk_ids.add(uid)
            if uid in ids:
                errors.append(f"DATA: duplicate id {uid!r} in {fp.name} and {ids[uid]}")
            else:
                ids[uid] = fp.name

        # optional-metadata warnings
        for opt in ("reference_type", "version", "updated_at"):
            if opt not in data:
                warnings.append(f"DATA: {fp.name} missing optional `{opt}`")

    # ── units_index.json freshness ─────────────────────────────────────────
    if INDEX_JSON.exists():
        try:
            idx = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
            if idx.get("total_units") != len(files):
                warnings.append(
                    f"INDEX: units_index.json total_units={idx.get('total_units')} "
                    f"but {len(files)} units on disk — run build_vector_db.py"
                )
        except Exception as e:
            warnings.append(f"INDEX: could not read units_index.json: {e}")

    # ── INDEX: ChromaDB ↔ disk (optional, slower) ──────────────────────────
    if args.check_index:
        try:
            from app.services.retrieval import (
                _get_collection,
                index_knowledge_units,
            )
            from app.services.knowledge_loader import load_default_knowledge_units

            if args.rebuild:
                index_knowledge_units(load_default_knowledge_units())

            collection = _get_collection()
            indexed_ids = set(collection.get().get("ids", []))
            missing = disk_ids - indexed_ids
            orphan = indexed_ids - disk_ids
            if missing:
                errors.append(
                    f"INDEX: {len(missing)} unit(s) on disk not in ChromaDB "
                    f"(run build_vector_db.py): {sorted(missing)[:5]}..."
                )
            if orphan:
                errors.append(
                    f"INDEX: {len(orphan)} orphan vector(s) in ChromaDB with no source unit: "
                    f"{sorted(orphan)[:5]}..."
                )
            if not missing and not orphan:
                print(f"  ✓ ChromaDB in sync ({len(indexed_ids)} vectors)")
        except Exception as e:
            errors.append(f"INDEX: ChromaDB check failed: {e}")

    # ── report ─────────────────────────────────────────────────────────────
    print(f"  Units scanned : {len(files)}")
    print(f"  Schema        : {SCHEMA_PATH.name}")
    print("=" * 67)

    if warnings:
        print(f"\n🟡  WARNINGS ({len(warnings)}):")
        # collapse the noisy optional-metadata warnings into a count
        meta_warns = [w for w in warnings if "missing optional" in w]
        other = [w for w in warnings if "missing optional" not in w]
        for w in other:
            print(f"     {w}")
        if meta_warns:
            print(f"     ({len(meta_warns)} units missing optional metadata — non-blocking)")

    if errors:
        print(f"\n🔴  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"     ✗ {e}")
        print("\n" + "=" * 67)
        print("  ❌  DRIFT DETECTED — fix before committing.")
        print("  Tools: ops/tools/normalize_units.py · ops/tools/build_vector_db.py")
        print("=" * 67 + "\n")
        return 1

    print("\n" + "=" * 67)
    print(f"  ✅  KNOWLEDGE BASE IN SYNC — {len(files)} units, schema ≡ taxonomy")
    print("=" * 67 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
