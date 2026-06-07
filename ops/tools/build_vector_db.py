"""
Build / rebuild ChromaDB vector index for knowledge_base/units/*.json.
Uses the ONNX embedder built into ChromaDB (no external model download needed).
Also rebuilds units_index.json with original + normalized age_group.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend/ to path so we can import app.*
backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.knowledge_loader import load_default_knowledge_units
from app.services.retrieval import index_knowledge_units


def build_index() -> None:
    units = load_default_knowledge_units()
    print(f"Loaded {len(units)} knowledge units.")
    index_knowledge_units(units)
    print("ChromaDB index built successfully.")


def rebuild_units_index() -> None:
    """Regenerate knowledge_base/units_index.json with original + normalized age_group."""
    units_dir = Path(__file__).resolve().parents[2] / "knowledge_base" / "units"
    index_path = units_dir.parent / "units_index.json"

    from app.services.age_normalization import normalize_age_group

    units_meta: list[dict] = []
    for fp in sorted(units_dir.glob("*.json")):
        with fp.open("r", encoding="utf-8") as f:
            data = json.load(f)
        raw_age = data.get("age_group", "unspecified")
        norm_age = normalize_age_group(raw_age)
        units_meta.append({
            "id": data.get("id"),
            "domain": data.get("domain"),
            "title": data.get("title", "")[:60],
            "source_file": data.get("source_file", ""),
            "language": data.get("language", ""),
            "original_age_group": raw_age,
            "normalized_age_group": norm_age,
            "behavior_type": data.get("behavior_type", ""),
            "needs_ocr": data.get("needs_ocr", False),
            "size_chars": len(data.get("text_original", "")),
        })

    by_domain: dict[str, int] = {}
    for u in units_meta:
        by_domain[u["domain"]] = by_domain.get(u["domain"], 0) + 1

    index = {
        "total_units": len(units_meta),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "by_domain": by_domain,
        "units": units_meta,
    }

    with index_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"units_index.json rebuilt: {index_path}")


if __name__ == "__main__":
    build_index()
    rebuild_units_index()
