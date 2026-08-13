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

# Source documents whose units are excluded from retrieval.
#
# These are governance material — written for governments, regulators and
# telecom operators, not for parents. Sampled text: "Obtain funding for the
# necessary equipment", "Identify specific courts where the pilot project can
# be implemented", "effective participation of governments". English, mostly
# `age_group: unspecified`, and extracted mid-sentence from PDFs.
#
# Together they are 325 of 1,168 units — 28% of the corpus — competing for the
# four slots retrieval returns. Measured 2026-08-13 on a month of real
# questions: 51% of retrieved units were judged "لا صلة" and 77 of every 100
# parent questions found nothing that served them. A parent asking why their
# six-year-old will not sleep alone was competing against 127 units of
# industry guidance on child online protection.
#
# The files stay on disk and stay in the integrity guard's scope; they are
# only kept out of the index. To reverse, delete an entry and restart the
# backend — the fingerprint changes and the index rebuilds itself on boot.
EXCLUDED_SOURCES = (
    "ITU_COP_Industry_Guidelines.pdf",
    "ITU_Child_Online_Protection.pdf",
    "WHO_Child_Adolescent_Mental_Health_Policy.pdf",
)


def _is_excluded(data: dict) -> bool:
    return (data.get("source_file") or "") in EXCLUDED_SOURCES


def load_knowledge_units_from_dir(dir_path: Path) -> list[KnowledgeUnit]:
    """Walk dir_path, load every .json file as a KnowledgeUnit."""
    if not dir_path.exists():
        return []
    units: list[KnowledgeUnit] = []
    for json_file in sorted(dir_path.glob("*.json")):
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if _is_excluded(data):
                continue
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
