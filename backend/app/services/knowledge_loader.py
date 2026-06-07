"""
Load knowledge units from JSON files on disk.
Normalizes age_group metadata before instantiating KnowledgeUnit.
"""
import json
from pathlib import Path

from app.models.knowledge import KnowledgeUnit
from app.services.age_normalization import normalize_age_group


BASE_DIR = Path(__file__).resolve().parents[3] / "knowledge_base"

DEFAULT_KB_DIRS = [
    BASE_DIR / "units",
]


def load_knowledge_units_from_dir(dir_path: Path) -> list[KnowledgeUnit]:
    """Walk dir_path, load every .json file as a KnowledgeUnit."""
    if not dir_path.exists():
        return []
    units: list[KnowledgeUnit] = []
    for json_file in sorted(dir_path.glob("*.json")):
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # ── metadata normalization ──
            raw_age = data.get("age_group", "unspecified")
            data["age_group"] = normalize_age_group(raw_age)
            unit = KnowledgeUnit(**data)
            units.append(unit)
        except Exception as e:
            print(f"[WARNING] Skipping {json_file}: {e}")
    return units


def load_default_knowledge_units() -> list[KnowledgeUnit]:
    """Load units from all default knowledge base directories."""
    all_units: list[KnowledgeUnit] = []
    seen_ids: set[str] = set()
    for d in DEFAULT_KB_DIRS:
        for unit in load_knowledge_units_from_dir(d):
            if unit.id not in seen_ids:
                all_units.append(unit)
                seen_ids.add(unit.id)
    return all_units
