"""
One-time data normalizer — تنظيف قيم enum المتسخة في وحدات المعرفة
==================================================================
Repairs whitespace, typos, and garbage values in the `severity` and
`intervention_type` fields so every unit matches the canonical taxonomy
(and therefore the JSON schema). Domains and age_groups on disk are already
canonical, so they're only whitespace-stripped defensively.

Safe to re-run (idempotent — clean values are left untouched).
Backs up originals before writing, and prints EVERY change for review.

Usage:
    python ops/tools/normalize_units.py            # apply + backup
    python ops/tools/normalize_units.py --dry-run  # report only, no writes
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.taxonomy import (  # noqa: E402
    CANONICAL_SEVERITIES,
    CANONICAL_INTERVENTIONS,
    CANONICAL_DOMAINS,
    CANONICAL_AGE_GROUPS,
)

UNITS_DIR = ROOT / "knowledge_base" / "units"

# ── explicit repair maps for known dirty values (post-strip) ────────────────
SEVERITY_REPAIR = {
    "شدى": "شديد",
    "شديد/طارئ": "شديد",          # take the lower of two highs (avoid over-escalation)
    "unspecified": "متوسط",        # neutral default (neither under- nor over-escalate)
}

INTERVENTION_REPAIR = {
    "أرشادي": "إرشادي",            # hamza typo
    "الإرشادي": "إرشادي",
    "الإرشادي والعلاجي": "علاجي",  # combined → the more intensive type
    "العلاجية": "علاجي",
    "توعوي وعلاجى": "علاجي",
    "وقائي/إرشادي": "وقائي",       # combined → take preventive
    "علاج ماركسي/إحالة طبيب": "إحالة_لطبيب",  # garbage + referral → referral
    "治적": "إرشادي",              # garbage token → default advisory
    "unspecified": "إرشادي",       # default advisory
}


def repair(value: str, repair_map: dict[str, str]) -> str:
    """Strip whitespace, then apply explicit repair map if needed."""
    if value is None:
        return value
    stripped = str(value).strip()
    return repair_map.get(stripped, stripped)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, no writes")
    args = ap.parse_args()

    files = sorted(UNITS_DIR.glob("*.json"))
    if not files:
        print(f"No units found in {UNITS_DIR}")
        return 1

    changes: list[str] = []
    unresolved: list[str] = []
    changed_files: list[Path] = []

    parsed: dict[Path, dict] = {}
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        original = json.dumps(data, ensure_ascii=False, sort_keys=True)

        # severity
        if "severity" in data:
            new = repair(data["severity"], SEVERITY_REPAIR)
            if new != data["severity"]:
                changes.append(f"{fp.name}: severity {data['severity']!r} → {new!r}")
                data["severity"] = new
            if data["severity"] not in CANONICAL_SEVERITIES:
                unresolved.append(f"{fp.name}: severity still invalid: {data['severity']!r}")

        # intervention_type
        if "intervention_type" in data:
            new = repair(data["intervention_type"], INTERVENTION_REPAIR)
            if new != data["intervention_type"]:
                changes.append(f"{fp.name}: intervention_type {data['intervention_type']!r} → {new!r}")
                data["intervention_type"] = new
            if data["intervention_type"] not in CANONICAL_INTERVENTIONS:
                unresolved.append(f"{fp.name}: intervention_type still invalid: {data['intervention_type']!r}")

        # domain / age_group — defensive strip only
        for field, canon in (("domain", CANONICAL_DOMAINS), ("age_group", CANONICAL_AGE_GROUPS)):
            if field in data and isinstance(data[field], str):
                new = data[field].strip()
                if new != data[field]:
                    changes.append(f"{fp.name}: {field} {data[field]!r} → {new!r}")
                    data[field] = new
                if data[field] not in canon:
                    unresolved.append(f"{fp.name}: {field} not canonical: {data[field]!r}")

        if json.dumps(data, ensure_ascii=False, sort_keys=True) != original:
            changed_files.append(fp)
            parsed[fp] = data

    # ── report ──────────────────────────────────────────────────────────────
    print("=" * 65)
    print("  UNIT NORMALIZER")
    print("=" * 65)
    print(f"  Scanned       : {len(files)} units")
    print(f"  Files changed : {len(changed_files)}")
    print(f"  Edits         : {len(changes)}")
    print("=" * 65)
    for c in changes:
        print(f"  ✏️  {c}")
    if unresolved:
        print("\n  ⚠️  UNRESOLVED (need manual attention):")
        for u in unresolved:
            print(f"     {u}")

    if args.dry_run:
        print("\n  (dry-run — no files written)")
        return 0

    if not changed_files:
        print("\n  ✅ Nothing to change — all units already clean.")
        return 0

    # ── backup then write ─────────────────────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "knowledge_base" / f"units_backup_normalize_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for fp in changed_files:
        shutil.copy2(fp, backup_dir / fp.name)
        fp.write_text(
            json.dumps(parsed[fp], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"\n  💾 Backed up {len(changed_files)} originals → {backup_dir.name}/")
    print(f"  ✅ Wrote {len(changed_files)} normalized units.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
