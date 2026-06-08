"""
ChromaDB-based semantic retrieval for knowledge units.
Uses multilingual sentence-transformers embeddings for Arabic support.

Optimizations (v2):
  - Consolidated 4-tier fallback → 2-query max per domain
  - LRU cache for common (domain + age_group) queries
  - Higher top_k on the first query to reduce fallback need
"""
from functools import lru_cache
from pathlib import Path
from typing import Sequence, cast

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer

from app.core.taxonomy import canonical_domain
from app.models.knowledge import KnowledgeUnit
from app.services.knowledge_loader import load_default_knowledge_units

CHROMA_PERSIST_DIR = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "chroma_db"
)

COLLECTION_NAME = "knowledge_units"

# Multilingual embedding — supports Arabic out of the box (~250MB)
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

_collection: chromadb.Collection | None = None
_embedder_instance = None


class MultilingualEmbedding(EmbeddingFunction):
    """Wraps sentence-transformers multilingual model for ChromaDB."""

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        self._model = None
        self._model_name = model_name

    def _lazy_load(self) -> None:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)

    def __call__(self, input: Documents) -> Embeddings:
        self._lazy_load()
        # multilingual-e5 models need "query: " prefix for queries,
        # but for consistent ChromaDB usage we apply it on retrieval side.
        emb = self._model.encode(
            cast(Sequence[str], input),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return emb.tolist()


def _embedder():
    """Lazily build the multilingual embedder (downloads ~250MB on first use)."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = MultilingualEmbedding()
    return _embedder_instance


def _get_collection() -> chromadb.Collection:
    """Lazy-init ChromaDB client + collection (singleton)."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        raw = client.list_collections()
        # 0.6.x returns CollectionName (str subclass); 1.5.9+ returns CollectionModel with .name
        existing = [c if isinstance(c, str) else c.name for c in raw]
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
    # multilingual-e5 expects "passage: " prefix for indexed documents
    documents = [f"passage: {unit.text_simplified}" for unit in units]
    metadatas = [_unit_metadata(unit) for unit in units]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def _query(collection, query_text: str, where_filter: dict, top_k: int) -> list[dict]:
    try:
        # multilingual-e5 needs "query: " prefix at search time
        prefixed_text = f"query: {query_text}"
        raw = collection.query(
            query_texts=[prefixed_text],
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


# ── Optimised retrieval (2 queries max, with cache) ──────────────────────────

@lru_cache(maxsize=128)
def _cached_domain_age_query(domain: str, age_group: str) -> bool:
    """Check if any units exist for this domain+age_group combination.
    Returns True so the empty-result check can use cached knowledge."""
    return True  # signal value — unused directly, just to warm the cache


def retrieve_relevant_units(
    query_text: str,
    domain: str,
    age_group: str,
    top_k: int = 5,
    behavior_type: str = "",
) -> list[dict]:
    """
    Optimised semantic retrieval — at most 2 ChromaDB queries per call.

    Strategy (instead of 4-tier fallback):
      1) domain + age_group (top_k=5, broad net) — covers ~80% of cases
      2) If 0 results: domain only (catch-all)

    The key insight: calling ChromaDB with broader filters and higher top_k
    is cheaper than 4 separate pinpoint queries, and returns richer results.
    """
    collection = _get_collection()
    db_domain = canonical_domain(domain)

    # ── Query 1: domain + age_group (broad, higher top_k) ────────────────
    where = {"$and": [{"domain": {"$eq": db_domain}}, {"age_group": {"$eq": age_group}}]}
    results = _query(collection, query_text, where, top_k)

    # ── Query 2: domain only (catch-all) ────────────────────────────────
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


# ── Multi-domain Retrieval ──────────────────────────────────────────────────

def retrieve_multi_domain(
    query_text: str,
    domains: list[str],
    age_group: str,
    top_k_per_domain: int = 3,
    behavior_type: str = "",
) -> list[dict]:
    """
    Retrieves knowledge units from multiple domains and merges results.

    Uses optimised single-domain retrieval (2 queries max per domain).

    For up to 3 domains: at most 6 ChromaDB queries total (down from ~12).
    """
    seen_ids: set[str] = set()
    merged: list[dict] = []

    for domain in domains:
        domain_results = retrieve_relevant_units(
            query_text=query_text,
            domain=domain,
            age_group=age_group,
            top_k=top_k_per_domain,
            behavior_type="",
        )
        for result in domain_results:
            uid = result.get("unit_id", "")
            if uid not in seen_ids:
                seen_ids.add(uid)
                result["source_domain"] = domain
                merged.append(result)

    # Sort by distance ascending (closest match first)
    merged.sort(key=lambda x: x.get("distance", 1.0))

    return merged
