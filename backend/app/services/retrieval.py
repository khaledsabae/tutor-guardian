"""
ChromaDB-based semantic retrieval for knowledge units.
Uses ChromaDB's built-in ONNX embedding (no PyTorch/SentenceTransformer download needed).
"""
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from app.core.taxonomy import canonical_domain
from app.models.knowledge import KnowledgeUnit
from app.services.knowledge_loader import load_default_knowledge_units

CHROMA_PERSIST_DIR = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "chroma_db"
)

COLLECTION_NAME = "knowledge_units"

# ONNX embedding — lightweight (~80MB), no PyTorch, runs on CPU, supports Arabic
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_collection: chromadb.Collection | None = None
_embedder_instance = None


def _embedder():
    """Lazily build the ONNX embedder (downloads ~80MB on first real use only)."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = embedding_functions.ONNXMiniLM_L6_V2()
    return _embedder_instance


def _get_collection() -> chromadb.Collection:
    """Lazy-init ChromaDB client + collection (singleton)."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        existing = [c.name for c in client.list_collections()]
        if COLLECTION_NAME in existing:
            _collection = client.get_collection(
                COLLECTION_NAME,
                embedding_function=_embedder(),
            )
        else:
            _collection = client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=_embedder(),
                metadata={"hnsw:space": "cosine"},
            )
    return _collection


def _unit_metadata(unit: KnowledgeUnit) -> dict:
    """Convert a KnowledgeUnit to flat metadata dict for ChromaDB."""
    return {
        "unit_id": unit.id,
        "domain": unit.domain,
        "age_group": unit.age_group,
        "behavior_type": unit.behavior_type,
        "intervention_type": unit.intervention_type,
        "severity": unit.severity,
        "labels": ", ".join(unit.labels) if unit.labels else "",
        "reference_info": unit.reference_info,
    }


def index_knowledge_units(units: list[KnowledgeUnit] | None = None) -> None:
    """
    Embed and store knowledge units in ChromaDB.
    Clears and rebuilds the collection each call (idempotent).
    """
    if units is None:
        units = load_default_knowledge_units()

    collection = _get_collection()

    # Clear existing data
    existing_ids = collection.get()["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)

    # Batch insert — embedding happens automatically via the collection's EF
    ids = [unit.id for unit in units]
    documents = [unit.text_simplified for unit in units]
    metadatas = [_unit_metadata(unit) for unit in units]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def _query(collection, query_text: str, where_filter: dict, top_k: int) -> list[dict]:
    try:
        raw = collection.query(
            query_texts=[query_text],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        ids = raw.get("ids", [[]])[0]
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]
        return [
            {"unit_id": i, "document": d, "metadata": m, "distance": dist}
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]
    except Exception:
        return []


def retrieve_relevant_units(
    query_text: str,
    domain: str,
    age_group: str,
    top_k: int = 3,
    behavior_type: str = "",
) -> list[dict]:
    """
    Semantic retrieval with 4-tier fallback:
    1) domain + age_group + behavior_type
    2) domain + behavior_type
    3) domain + unspecified
    4) domain only
    """
    collection = _get_collection()

    # Map API/classifier input domain → canonical storage domain.
    # Single source of truth: app.core.taxonomy (keeps schema/code/data aligned).
    db_domain = canonical_domain(domain)

    # ── Attempt 1: exact match + behavior_type ──────────────────────
    if behavior_type:
        where = {"$and": [{"domain": {"$eq": db_domain}}, {"age_group": {"$eq": age_group}}, {"behavior_type": {"$eq": behavior_type}}]}
        results = _query(collection, query_text, where, top_k)
    else:
        results = []

    # ── Attempt 2: domain + behavior_type (no age_group) ────────────
    if not results and behavior_type:
        where = {"$and": [{"domain": {"$eq": db_domain}}, {"behavior_type": {"$eq": behavior_type}}]}
        results = _query(collection, query_text, where, top_k)

    # ── Attempt 3: domain + unspecified ────────────────────────────
    if not results:
        where_unspecified = {"$and": [{"domain": {"$eq": db_domain}}, {"age_group": {"$eq": "unspecified"}}]}
        results = _query(collection, query_text, where_unspecified, top_k)

    # ── Attempt 4: domain only ─────────────────────────────────────
    if not results:
        where_domain = {"domain": {"$eq": db_domain}}
        results = _query(collection, query_text, where_domain, top_k)

    return results


# Ensure the index is built on first import
_index_built = False


def _ensure_index() -> None:
    """Build the ChromaDB index once on first access."""
    global _index_built
    if not _index_built:
        units = load_default_knowledge_units()
        index_knowledge_units(units)
        _index_built = True


# ─────────────────────────────────────────────────────────────────────────────
# Multi-domain Retrieval — الدالة الجديدة
# تستدعي retrieve_relevant_units لكل domain في القائمة وتدمج النتائج
# ─────────────────────────────────────────────────────────────────────────────

def retrieve_multi_domain(
    query_text: str,
    domains: list[str],
    age_group: str,
    top_k_per_domain: int = 2,
    behavior_type: str = "",
) -> list[dict]:
    """
    يسترجع وحدات معرفة من مجالات متعددة ويدمجها.

    المنطق:
    - لكل domain في القائمة: يستدعي retrieve_relevant_units
    - يضيف حقل 'source_domain' لكل نتيجة (للـ prompt)
    - يزيل التكرار بناءً على unit_id
    - يرتب حسب distance (الأقل = الأدق)
    - يعيد بحد أقصى top_k_per_domain * len(domains) نتيجة

    Args:
        query_text: نص السؤال
        domains: قائمة المجالات ['fiqh', 'medical', 'cyber']
        age_group: الفئة العمرية
        top_k_per_domain: عدد النتائج لكل مجال (افتراضي 2)
        behavior_type: نوع السلوك (اختياري)

    Returns:
        قائمة مدمجة من الوحدات مع حقل source_domain إضافي
    """
    seen_ids: set[str] = set()
    merged: list[dict] = []

    for domain in domains:
        domain_results = retrieve_relevant_units(
            query_text=query_text,
            domain=domain,
            age_group=age_group,
            top_k=top_k_per_domain,
            behavior_type=behavior_type,
        )
        for result in domain_results:
            uid = result.get("unit_id", "")
            if uid not in seen_ids:
                seen_ids.add(uid)
                # أضف source_domain للـ prompt يعرف من أين جاءت الوحدة
                result["source_domain"] = domain
                merged.append(result)

    # رتّب حسب distance تصاعدياً (الأقرب معنىً أولاً)
    merged.sort(key=lambda x: x.get("distance", 1.0))

    return merged

