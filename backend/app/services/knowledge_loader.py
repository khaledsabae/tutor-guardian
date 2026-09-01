"""
Load knowledge units from JSON files on disk.
Normalizes age_group metadata before instantiating KnowledgeUnit.
"""
import json
from pathlib import Path

from app.models.knowledge import KnowledgeUnit
from app.services.age_normalization import normalize_age_group


BASE_DIR = Path(__file__).resolve().parents[3] / "knowledge_base"

# knowledge_base/units holds the authored corpus. knowledge_base/curriculum/
# daily_tips is listed separately because its files are NOT KnowledgeUnit
# shaped — they need a field mapping (see _load_daily_tip_units). Adding the
# dir to DEFAULT_KB_DIRS without that mapping would make every tip fail
# KnowledgeUnit(**data) validation and get skipped with a warning.
DAILY_TIPS_DIR = BASE_DIR / "curriculum" / "daily_tips"

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


def _load_daily_tip_units() -> list[KnowledgeUnit]:
    """Read every daily-tip JSON (``tip_*.json``) as a retrieval unit.

    The daily tip is what a parent actually saw; when they ask a follow-up
    ("بخصوص نصيحة اليوم: ... إزاي أطبقها؟") retrieval must be able to find
    that exact text. These files are not ``KnowledgeUnit`` shaped (they have
    ``text`` not ``text_simplified``, and no ``behavior_type``), so they are
    mapped here instead of going through ``load_knowledge_units_from_dir``.

    Only ``is_published`` tips are indexed. ``source = "daily_tip"`` keeps
    them distinguishable in metadata / telemetry (and lets the fiqh guard or
    dashboards treat them separately). The parent unit the tip was authored
    from is kept in ``reference_info`` (``unit_id``), so a follow-up can reach
    both the tip surface text and its backing unit.
    """
    if not DAILY_TIPS_DIR.exists():
        return []
    units: list[KnowledgeUnit] = []
    for json_file in sorted(DAILY_TIPS_DIR.glob("*.json")):
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # Matches curriculum_loader._is_published: a MISSING key means
            # published (the API serves all 210 tips; only an explicit
            # False is a draft). Indexing only the 90 that spell it out
            # would leave 120 live tips irretrievable — the exact gap this
            # change exists to close, on the majority of the pool.
            if not data.get("is_published", True):
                continue
            text = (data.get("text") or "").strip()
            tip_id = (data.get("id") or "").strip()
            if not text or not tip_id:
                continue
            unit = KnowledgeUnit(
                id=tip_id,
                domain=data.get("domain") or "tarbiyah",
                age_group=normalize_age_group(data.get("age_group", "unspecified")),
                # Not in the source files; the corpus is authored in Arabic and
                # the field defaults to "ar" upstream for the same reason.
                language="ar",
                behavior_type="نصيحة يومية",
                title=f"نصيحة اليوم — {data.get('age_group', '')}".strip(" —"),
                intervention_type="وقائي",
                severity="خفيف",
                reference_type="daily_tip_backing",
                reference_info=str(data.get("unit_id") or ""),
                text_simplified=text,
                labels=list(data.get("tags") or []),
                version=str(data.get("version") or "1.0"),
                source_meta={
                    "source": "daily_tip",
                    "source_file": json_file.name,
                    "day_of_week": data.get("day_of_week"),
                    "time_of_day": data.get("time_of_day"),
                    "backing_unit_id": data.get("unit_id"),
                },
            )
            units.append(unit)
        except Exception as e:  # noqa: BLE001 — one bad tip must not break the build
            print(f"[WARNING] Skipping daily tip {json_file}: {e}")
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
    for unit in _load_daily_tip_units():
        if unit.id not in seen_ids:
            all_units.append(unit)
            seen_ids.add(unit.id)
    return all_units
