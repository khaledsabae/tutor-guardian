"""
Validate that every age_group in knowledge_base/units/*.json maps to a canonical value.
Exits with code 1 if any unknown age_group is found without a clear mapping.
"""
import json
import sys
from pathlib import Path

# Add backend/ to path so we can import app.*
backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.age_normalization import list_unknown_age_groups, CANONICAL_AGE_GROUPS


def main() -> int:
    units_dir = Path(__file__).resolve().parents[2] / "knowledge_base" / "units"
    if not units_dir.exists():
        print(f"ERROR: Units dir not found: {units_dir}")
        return 1

    all_raw: list[str] = []
    for fp in sorted(units_dir.glob("*.json")):
        with fp.open("r", encoding="utf-8") as f:
            data = json.load(f)
        raw_age = data.get("age_group", "unspecified")
        all_raw.append(raw_age)

    unknown = list_unknown_age_groups(all_raw)
    if unknown:
        print(f"FAIL: {len(unknown)} unknown age_group value(s) without mapping:")
        for v in unknown:
            print(f"  - '{v}'")
        print(f"Canonical enum: {sorted(CANONICAL_AGE_GROUPS)}")
        return 1

    print(f"PASS: All {len(all_raw)} units have mapped age_group values.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
