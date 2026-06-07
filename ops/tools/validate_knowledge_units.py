import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


def load_schema(schema_path: Path):
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_file(schema, file_path: Path) -> bool:
    validator = Draft202012Validator(schema)
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        validator.validate(data)
        print(f"[OK] {file_path}")
        return True
    except ValidationError as e:
        print(f"[ERROR] {file_path}")
        print(f"   -> {e.message}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Validate knowledge base JSON files against knowledge_unit.schema.json"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="knowledge_base/examples",
        help="Directory containing JSON files to validate.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    schema_path = project_root / "knowledge_base" / "schema" / "knowledge_unit.schema.json"
    target_dir = project_root / args.dir

    if not schema_path.exists():
        print(f"Schema file not found: {schema_path}")
        sys.exit(1)

    if not target_dir.exists():
        print(f"Target directory not found: {target_dir}")
        sys.exit(1)

    schema = load_schema(schema_path)
    json_files = list(target_dir.rglob("*.json"))
    if not json_files:
        print(f"No JSON files found in {target_dir}")
        sys.exit(0)

    all_ok = True
    for file_path in json_files:
        if not validate_file(schema, file_path):
            all_ok = False

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
