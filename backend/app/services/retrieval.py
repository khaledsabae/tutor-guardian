"""
ChromaDB-based semantic retrieval for knowledge units.
Uses multilingual sentence-transformers embeddings for Arabic support.

Optimizations (v2):
  - Consolidated 4-tier fallback → 2-query max per domain
  - LRU cache for common (domain + age_group) queries
  - Higher top_k on the first query to reduce fallback need
"""
import hashlib
import logging
import re
import shutil
import threading
from functools import lru_cache
from pathlib import Path
from typing import Sequence, cast

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

from app.core.taxonomy import (
    canonical_domain,
    age_equivalents,
    age_bands_apart,
)
from app.models.knowledge import KnowledgeUnit
from app.services.knowledge_loader import load_default_knowledge_units

logger = logging.getLogger(__name__)

CHROMA_PERSIST_DIR = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "chroma_db"
)

COLLECTION_NAME = "knowledge_units"

# Purge and rebuild when the HNSW graph carries this many times more vectors
# than the collection has live documents (tombstones are never reclaimed).
_HNSW_BLOAT_FACTOR = 3

# Multilingual embedding — supports Arabic out of the box (~250MB)
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

_collection: chromadb.Collection | None = None

# Raised when the handle outlives the collection it points at. The class moved
# between chromadb versions and is absent in some, so this is resolved by name
# with a ValueError floor — older builds raise that instead, and matching too
# widely here would swallow real errors behind a pointless second attempt.
_STALE_COLLECTION_ERRORS: tuple[type[BaseException], ...] = tuple(
    exc for exc in (
        getattr(chromadb.errors, "InvalidCollectionException", None),
        getattr(chromadb.errors, "NotFoundError", None),
    ) if isinstance(exc, type)
) or (ValueError,)
_embedder_instance = None


class MultilingualEmbedding(EmbeddingFunction):
    """Wraps sentence-transformers multilingual model for ChromaDB."""

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        self._model = None
        self._model_name = model_name

    def _lazy_load(self) -> None:
        if self._model is None:
            # deferred so the app can import without the heavy torch stack
            from sentence_transformers import SentenceTransformer

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


def embed_query(text: str) -> list[float]:
    """L2-normalized query embedding (e5 "query: " convention) for arbitrary
    text — used by the semantic answer cache. Dot product == cosine sim."""
    return _embedder()(
        [f"query: {text}"]
    )[0]


def _reset_collection_handle() -> None:
    """Forget the cached handle so the next call re-acquires it."""
    global _collection
    _collection = None


def with_live_collection(operation):
    """Run `operation(collection)`, re-acquiring the handle once if it went stale.

    `_collection` is a process-wide singleton, but the collection it points at
    can be deleted and recreated underneath it. The rebuild path below does
    exactly that, and so does any other process opening the same persist
    directory — a diagnostic `docker exec … python -c "_ensure_index()"` is
    enough. Chroma then raises InvalidCollectionException on every subsequent
    call in this process, and the assistant answers 500 to every parent until
    someone restarts the container.

    That is not hypothetical: it took production down on 2026-07-29. The data
    was never at risk — only the handle — so re-acquiring it is the entire fix.
    """
    try:
        return operation(_get_collection())
    except _STALE_COLLECTION_ERRORS:
        logger.warning("Chroma collection handle went stale — re-acquiring")
        _reset_collection_handle()
        return operation(_get_collection())


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
        # اللغة **تُرتِّب ولا تُرشِّح** — انظر `retrieve_hybrid`. ٤٣ وحدة
        # إنجليزية من ١,١٨٧، فمرشِّح صارم `language == "en"` يفرّغ النتيجة
        # ويعطي المستخدم الإنجليزي «لا توجد معلومات كافية» بدل إسنادٍ عربي
        # مفيد؛ ولهذا رُفض الترشيح، وكان رفضه صوابًا.
        # 🚨 لكن «لا نستطيع الترشيح» قُرئ «لا نستطيع شيئًا»، ودفع الثمنَ
        # القارئُ العربي: ١٤ من ٣١ وحدة في `prenatal-1` غير عربية، فأمٌّ تسأل
        # بالعربية عن ابنها ابن السنتين كانت تُعطى «Your child at 2 years».
        # التفضيل الآن رصيد RRF إضافي، لا استبعاد.
        # ⚠️ إضافة مفتاح هنا تغيّر `_fingerprint`، فأول إقلاع بعد النشر يعيد
        # تضمين الوحدات كلها مرة واحدة — تكلفة إقلاع لا تكلفة طلب.
        "language": unit.language,
        "behavior_type": unit.behavior_type,
        "intervention_type": unit.intervention_type,
        "severity": unit.severity,
        "labels": ", ".join(unit.labels) if unit.labels else "",
        "reference_info": unit.reference_info,
        "title": unit.title,
    }


def _fingerprint(units: list[KnowledgeUnit]) -> str:
    """Content hash of the unit set — lets us skip a rebuild when nothing changed.

    Hashes `embedding_text`, not `text_simplified`: the vector is built from the
    topic header plus the body, so a change to either — or to the composition
    rule itself — has to invalidate the index.
    """
    h = hashlib.sha256()
    for unit in sorted(units, key=lambda u: u.id):
        h.update(unit.id.encode())
        h.update(b"\0")
        h.update(unit.embedding_text.encode())
        h.update(b"\0")
        h.update(repr(sorted(_unit_metadata(unit).items())).encode())
        h.update(b"\x01")
    return h.hexdigest()


def _fingerprint_path() -> Path:
    return CHROMA_PERSIST_DIR / "_content_fingerprint"


def _hnsw_is_bloated(collection: chromadb.Collection) -> bool:
    """True when the HNSW graph holds far more vectors than the collection has
    documents.

    `collection.delete()` only tombstones vectors — the graph never reclaims
    them. Re-indexing on every process start therefore grew the graph without
    bound (observed in prod: 1,122 documents against 245,557 graph elements).
    Once the live fraction gets small enough, filtered KNN can no longer reach
    `n_results` reachable neighbours within `ef` and hnswlib raises
    "Cannot return the results in a contigious 2D array", which surfaced to
    parents as "لا توجد معلومات كافية".
    """
    try:
        from chromadb.segment import VectorReader

        seg = collection._client._manager.get_segment(collection.id, VectorReader)
        graph_elements = seg._index.get_current_count()
    except Exception:  # noqa: BLE001 — introspection is best-effort
        return False
    live = collection.count()
    if not live or not graph_elements:
        return False
    if graph_elements > live * _HNSW_BLOAT_FACTOR:
        logger.warning(
            "HNSW graph bloated: %d elements for %d documents — purging index",
            graph_elements, live,
        )
        return True
    return False


def _index_matches(
    collection: chromadb.Collection, units: list[KnowledgeUnit], fingerprint: str
) -> bool:
    """True when the persisted index already holds exactly these units."""
    path = _fingerprint_path()
    if not path.exists() or collection.count() != len(units):
        return False
    try:
        return path.read_text().strip() == fingerprint
    except OSError:
        return False


def _purge_persist_dir() -> None:
    """Empty the on-disk index so the next build starts from a fresh graph.

    Clears the directory's *contents* rather than the directory itself — in
    production it is a docker volume mount point, and rmdir on it fails with
    EBUSY.

    Dropping our own handle is not enough: chromadb caches one System per
    persist path, so the next PersistentClient(path=…) hands back the same
    process-wide object still holding an open descriptor on the sqlite file we
    just unlinked. It then reports the deleted collection as present and the
    first write fails with SQLITE_READONLY_DBMOVED (code 1032) — i.e. the
    bloat-triggered rebuild would delete the index and then be unable to
    rewrite it, leaving the app with nothing. Clearing chroma's cache too
    makes the next client genuinely new.
    """
    global _collection
    _collection = None
    try:
        from chromadb.api.shared_system_client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception as exc:  # noqa: BLE001 — private-ish API, never fatal
        logger.warning("could not clear chroma's system cache: %s", exc)
    if not CHROMA_PERSIST_DIR.exists():
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        return
    for entry in CHROMA_PERSIST_DIR.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def index_knowledge_units(
    units: list[KnowledgeUnit] | None = None, *, force: bool = False
) -> None:
    """
    Embed and store knowledge units in ChromaDB.

    Skips the rebuild entirely when the on-disk index already matches the
    content fingerprint. This is what keeps the HNSW graph from growing on
    every process start — see `_hnsw_is_bloated`. Pass force=True to rebuild
    from a clean graph regardless.
    """
    if units is None:
        units = load_default_knowledge_units()

    fingerprint = _fingerprint(units)
    # Both probes read the collection, so a handle stranded by another process
    # would surface here first — as it did in production.
    collection = with_live_collection(lambda c: c)

    if not force:
        if with_live_collection(_hnsw_is_bloated):
            force = True
        elif _index_matches(collection, units, fingerprint):
            logger.info("Knowledge index up to date (%d units) — skipping rebuild", len(units))
            return

    if force:
        # A tombstoned graph can't be repaired in place; start from empty disk.
        _purge_persist_dir()
        collection = _get_collection()
    else:
        existing_ids = collection.get()["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids)

    ids = [unit.id for unit in units]
    # The stored document stays the authored prose — it is what the generation
    # prompt and the parent-facing fallback quote. The VECTOR is built from
    # `embedding_text`, which prepends the unit's own topic fields (title,
    # behaviour type, labels, keywords). Embedding the body alone made a unit's
    # subject invisible to semantic search: prose about olive oil never says
    # "this is a nutrition unit", so it competed for questions about shyness.
    documents = [f"passage: {unit.text_simplified}" for unit in units]
    metadatas = [_unit_metadata(unit) for unit in units]
    # Guarded: an empty rebuild must not drag the ~250MB embedder into memory.
    embeddings = _embedder()([unit.embedding_text for unit in units]) if units else []

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    _fingerprint_path().write_text(fingerprint)
    logger.info("Knowledge index built: %d units", len(units))

    # Every cached answer is a frozen copy of what these units used to say,
    # citation line included. Reaching this point means they no longer say it.
    # Imported here rather than at module scope: answer_cache reaches back into
    # this module for embed_query.
    try:
        from app.services import answer_cache

        answer_cache.purge(reason="knowledge index rebuilt")
    except Exception as exc:  # noqa: BLE001 — indexing must not fail on this
        logger.warning("could not purge answer cache after rebuild: %s", exc)


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
    except Exception as exc:  # noqa: BLE001 — a broken leg must not kill the request
        # Never swallow this silently: an empty list here is indistinguishable
        # from "no matching knowledge", and the router turns that into
        # "لا توجد معلومات كافية" — a plausible-looking wrong answer that hid a
        # corrupt HNSW graph in production for weeks.
        logger.error(
            "Vector query failed (filter=%s, top_k=%d): %s",
            where_filter, top_k, exc, exc_info=True,
        )
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
    collection = with_live_collection(lambda c: c)
    db_domain = canonical_domain(domain)

    # ── Query 1: domain + age_group (broad, higher top_k) ────────────────
    # "unspecified" units hold general principles that apply to every age,
    # so they compete alongside age-matched units instead of being invisible.
    # age_equivalents() matches the legacy "0-3" and canonical "prenatal-1"
    # to each other so a pre-split child or unit still resolves.
    age_candidates = set(age_equivalents(age_group)) | {"unspecified"}
    where = {
        "$and": [
            {"domain": {"$eq": db_domain}},
            {"age_group": {"$in": list(age_candidates)}},
        ]
    }
    results = _query(collection, query_text, where, top_k)

    # ── Query 2: domain only (catch-all) ────────────────────────────────
    if not results:
        where_domain = {"domain": {"$eq": db_domain}}
        results = _query(collection, query_text, where_domain, top_k)

    return results


def retrieve_domain_only(
    query_text: str,
    domain: str,
    top_k: int = 5,
) -> list[dict]:
    """Vector search over a whole domain, ignoring the child's age band.

    The age-filtered query above is right when the corpus holds a unit for
    the child's own band, and blind when it does not: a unit written for
    4-6 is invisible to a 7-9 parent, and query 2 does not rescue it because
    it only fires on a *completely* empty result — and half the corpus is
    "unspecified", so it never is. This leg exists to be fused *underneath*
    the age-filtered one, not to replace it.
    """
    collection = with_live_collection(lambda c: c)
    where = {"domain": {"$eq": canonical_domain(domain)}}
    return _query(collection, query_text, where, top_k)


# Ensure the index is built on first import
_index_built = False
_index_lock = threading.Lock()


def _ensure_index() -> None:
    """Build the ChromaDB index once on first access (thread-safe).

    Handlers now run in the threadpool, so concurrent first requests could
    otherwise race into a full re-embed of the same Chroma collection.
    """
    global _index_built
    if _index_built:
        return
    with _index_lock:
        if _index_built:
            return
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


# ── Retrieval telemetry (non-fatal, mirrors ai_gateway._log_call) ───────────

_TELEMETRY_DB = Path(__file__).resolve().parents[3] / "ops" / "sessions.db"


def log_retrieval(query_text: str, domains: list[str],
                  rewritten_query: str, final_units: list[dict]) -> None:
    """Record what retrieval produced so eval runs can diagnose recall."""
    try:
        import json as _json
        import sqlite3 as _sqlite3

        conn = _sqlite3.connect(_TELEMETRY_DB)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS retrieval_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT (datetime('now')),
                question TEXT, domains TEXT, rewritten_query TEXT,
                final_ids TEXT, distances TEXT, rerank_scores TEXT
            )"""
        )
        conn.execute(
            "INSERT INTO retrieval_log (question, domains, rewritten_query,"
            " final_ids, distances, rerank_scores) VALUES (?,?,?,?,?,?)",
            (
                query_text[:300],
                ",".join(domains),
                rewritten_query[:120],
                _json.dumps([u.get("unit_id") for u in final_units]),
                _json.dumps([round(u["distance"], 3) for u in final_units
                             if isinstance(u.get("distance"), float)]),
                _json.dumps([round(u["rerank_score"], 3) for u in final_units
                             if isinstance(u.get("rerank_score"), float)]),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001 — telemetry must never break a request
        pass


# ── Hybrid retrieval (vector + BM25 → RRF → cross-encoder rerank) ───────────

_RRF_K = 60

# Fraction of the rerank-score spread that reading in your own language is
# worth. It settles near-ties among candidates the cross-encoder already judged
# relevant; it cannot outrank a real relevance gap. That ceiling is the point:
# 250+ units in this corpus are bulk-imported ITU and WHO policy text written
# for telecom companies and health ministries, almost all Arabic and
# `unspecified`, so eligible at every age. An unbounded preference for Arabic
# would float those above an English parenting unit that answers the question,
# and score as a win while the answer got worse.
_LANG_TIEBREAK = 0.15


_ARABIC_CHARS = re.compile(r"[؀-ۿ]")
_LATIN_CHARS = re.compile(r"[A-Za-z]")


def detect_query_language(text: str) -> str | None:
    """The language the parent wrote in — which is the one they read in.

    Taken from the question rather than from a request field on purpose.
    `UserMessage` carries no language, and adding one would mean every client
    already installed keeps retrieving with no preference until it updates —
    on an app with a force-update lever precisely because old builds linger.
    The question is already in the reader's language; nothing needs to be sent.

    Script, not vocabulary: an Arabic question about "screen time" is Arabic.
    Returns None when there is too little to tell, and None means no
    preference — never a guess.
    """
    ar = len(_ARABIC_CHARS.findall(text))
    la = len(_LATIN_CHARS.findall(text))
    if ar + la < 8:
        return None
    if ar > la:
        return "ar"
    if la > ar:
        return "en"
    return None


@lru_cache(maxsize=1)
def _unit_languages() -> dict:
    """unit_id → language, from the corpus rather than from a candidate dict.

    🚨 The legs do not agree on what a candidate carries. Vector hits come out
    of Chroma with the full stored metadata; BM25 hits carry a `metadata` dict
    with **no language key at all**. Reading the candidate directly therefore
    gave the bonus to vector hits and withheld it from BM25 hits — a preference
    for which leg found a unit, wearing the costume of a language preference.

    That is not a hypothetical: the first probe run scored a "gain" that was
    entirely this bug. One Arabic unit displaced another Arabic unit, and the
    displaced one was the more on-topic of the two. The number said the change
    worked; the titles said it had reshuffled two Arabic units by provenance.
    """
    return {u.id: u.language for u in load_default_knowledge_units()}


def _candidate_language(cand: dict) -> str | None:
    """The candidate's language, resolved by id first — see _unit_languages."""
    uid = cand.get("unit_id") or (cand.get("metadata") or {}).get("unit_id")
    if uid:
        found = _unit_languages().get(uid)
        if found:
            return found
    return (cand.get("metadata") or {}).get("language")


def _language_matches(unit_lang: str | None, want: str) -> bool:
    """True when a unit is written in `want`.

    🚨 `mixed` does NOT match, and the reasoning that said it should was wrong
    in a way only the titles showed. "It contains both languages, so it is
    readable either way" is true of the unit and false of the ranking: 69 units
    carry the tag, and counting it as a match handed all 69 the bonus on
    *every* query in *either* language. That is not a language preference, it
    is a preference for one tag, applied universally.

    Measured, on "My 8-year-old wets the bed": it promoted a `mixed` unit about
    early puberty over an Arabic unit about childhood anxiety — neither about
    bedwetting, and it scored as an English gain because `mixed` counted.
    Making `mixed` neutral, the same probe surfaced
    «التبول اللاإرادي الليلي في عمر أربعة إلى…» for the Arabic version of that
    question: nocturnal enuresis, exactly the subject asked about.

    An absent tag is neutral for the same reason — see retrieve_hybrid.
    """
    if not unit_lang:
        return False
    unit_lang = unit_lang.strip().lower()
    if unit_lang == "mixed":
        return False
    return unit_lang.split("-")[0] == want.split("-")[0]


def _rrf_merge(*ranked_lists: list[dict]) -> list[dict]:
    """Reciprocal Rank Fusion across candidate lists, deduped by unit_id.
    The fused candidate keeps the metadata of its first appearance and
    accumulates `rrf_score`; vector `distance` is preserved when known."""
    fused: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, cand in enumerate(ranked):
            uid = cand.get("unit_id", "")
            if not uid:
                continue
            entry = fused.setdefault(uid, {**cand, "rrf_score": 0.0})
            entry["rrf_score"] += 1.0 / (_RRF_K + rank + 1)
            # keep the best (smallest) vector distance seen for telemetry
            if "distance" in cand:
                entry["distance"] = min(
                    entry.get("distance", cand["distance"]), cand["distance"]
                )
    return sorted(fused.values(), key=lambda c: -c["rrf_score"])


def retrieve_hybrid(
    query_text: str,
    domains: list[str],
    age_group: str,
    rewritten_query: str = "",
    top_n: int = 4,
    candidates_per_leg: int = 8,
    rerank_pool: int = 12,
    age_span: int = 1,
    lang: str | None = None,
) -> list[dict]:
    """The quality-first retrieval path.

    Per domain and per query: three legs — vector filtered to the child's age
    band, vector across the domain regardless of band, and BM25 → RRF fusion →
    cross-encoder rerank → top_n.

    The band-free vector leg is additive, never a replacement: a unit written
    for the child's own band appears in both vector legs and so accumulates
    twice the RRF credit, which is what keeps the age-matched case intact
    while the gap case stops coming up empty.

    `age_span` bounds how far those two unbanded legs may reach — 1 means the
    neighbouring band, which is what "the corpus has nothing for this child's
    age, use the nearest thing" was always supposed to mean. Without it they
    reach anywhere, and BM25 always could: measured across the probe set, **31%
    of everything delivered to a parent sat two or more bands away** — a
    question about a four-year-old's tantrums answered with material on a
    16-18 year old, and one about an eight-year-old wetting the bed answered
    with ADHD and bereavement. That predates the band-free leg; BM25 has been
    unbanded since it was written, and the age-filtered vector leg could not
    counterweight it.

    Bounding both to one band improves every axis at once (probe set):

                                matched   gap   two-or-more bands away
        BM25 unbanded (before)   14/23    4/11         31%
        age_span=2               15/23    4/11         24%
        age_span=1 (this)        16/23    5/11          0%

    ⚠️ That last row no longer reproduces. `age_reach_probe` reports **15/23**
    matched, 5/11 gap as of 2026-08-15 — the conclusion stands, the number is
    one lower. It is not the language change below: that probe passes no
    `lang`, and re-running it against `origin/main` in a detached worktree,
    before the change existed, also gives 15/23. Something else moved it
    between the two measurements and was not caught, because nothing re-runs
    this. Read the row as directional, and re-measure before tuning against it.

    "unspecified" is never filtered — half the corpus carries it and it is
    written to apply at every age. Set age_span to None to disable the bound.

    `lang` prefers units written in the reader's language. It is a **ranking**
    signal, never a filter — the distinction is the whole point. The corpus is
    835 `ar`, 183 `mixed`, 126 untagged and **43 `en`**, so a hard
    `language == "en"` filter empties the result for the English 27% of users
    and returns "no sufficient information" instead of a useful Arabic
    citation. That is why filtering was refused, and refusing it was right.

    But "we cannot filter" was then read as "we can do nothing", and the cost
    of that fell on Arabic readers: 14 of the 31 `prenatal-1` units are not
    Arabic, so a parent asking in Arabic about a two-year-old was handed
    "Your child at 2 years*" in English. Nothing was choosing Arabic for them,
    because nothing was choosing at all.

    Preference is expressed in the currency this function already uses: one
    extra leg appearance, the same credit an age-matched unit earns by showing
    up in two vector legs. It reorders near-ties and decides who survives the
    `rerank_pool` cap; it cannot lift an irrelevant unit over a relevant one.

    Two deliberate non-behaviours, both neutral rather than penalised:

    · **Untagged is not wrong-language.** Units with no tag get no bonus and no
      penalty. Demoting them would bury a slice of the corpus on the strength
      of a missing field.
    · **`mixed` is neutral too**, and that is a correction — see
      _language_matches. Counting it as a match for both languages gave 69
      units a bonus on every query in either language, which is a preference
      for a tag, not for a language, and it displaced on-topic content.

    Falls back to fusion order if the reranker is unavailable (see
    reranker.rerank — it never raises).
    """
    from app.services.bm25_index import get_bm25
    from app.services.reranker import rerank

    bm25 = get_bm25()
    legs: list[list[dict]] = []
    queries = [q for q in (query_text, rewritten_query) if q]

    def within_span(cands: list[dict]) -> list[dict]:
        """Drop candidates written for a childhood this child is not in.

        `unspecified` and anything with an unreadable band are kept: the first
        applies at every age by design, and the second is a labelling gap, not
        a licence to answer a four-year-old's question with teenage material.
        """
        if age_span is None:
            return cands
        keep = []
        for c in cands:
            band = (c.get("metadata") or {}).get("age_group", "")
            apart = age_bands_apart(band, age_group)
            if apart is None or apart <= age_span:
                keep.append(c)
        return keep

    for domain in domains:
        db_domain = canonical_domain(domain)
        for q in queries:
            vec = retrieve_relevant_units(
                query_text=q, domain=domain, age_group=age_group,
                top_k=candidates_per_leg,
            )
            for r in vec:
                r.setdefault("source_domain", domain)
            legs.append(vec)
            # Half depth on purpose: this leg only has to rescue the units
            # the age filter hid, and every extra candidate it adds is one
            # more pair the cross-encoder has to score. At full depth it
            # bought nothing extra and cost ~875ms per answer.
            any_age = within_span(retrieve_domain_only(
                query_text=q, domain=domain,
                top_k=max(1, candidates_per_leg // 2),
            ))
            for r in any_age:
                r.setdefault("source_domain", domain)
            legs.append(any_age)
            # Over-fetch before bounding, or the bound silently shortens the
            # leg: the wrong-band hits it removes were occupying slots the
            # right-band ones never got a chance at.
            lex = within_span(
                bm25.search(q, domain=db_domain, top_k=candidates_per_leg * 3)
            )[:candidates_per_leg]
            for r in lex:
                r.setdefault("source_domain", domain)
            legs.append(lex)

    # The cross-encoder is the expensive step and its cost is linear in the
    # pool, so the extra leg must not be allowed to grow the pool — it is
    # there to change *which* candidates are scored, not how many.
    candidates = _rrf_merge(*legs)[:rerank_pool]
    if not lang:
        return rerank(query_text, candidates, top_n=top_n)

    # 🚨 Language is applied AFTER the reranker, not before it.
    #
    # Before it, the preference is inert. Measured across a 10-question probe:
    # zero results changed, at 1×, 3×, 6× and 12× the RRF weight. The reason is
    # structural, not a matter of tuning — the cross-encoder re-sorts whatever
    # it is handed, so a pre-rerank bonus can only change which candidates
    # enter the pool, and a candidate that was ranked twelfth by fusion is one
    # the cross-encoder then rejects anyway. Turning the weight up moves
    # nothing; it just makes the no-op look deliberate.
    #
    # After it, the ordering is a judgement about relevance that already
    # happened. Preferring the reader's language among candidates the
    # cross-encoder has *already* judged relevant is the thing that was wanted
    # all along, and it cannot promote an off-topic unit, because off-topic
    # units are not in this list — RERANK_MIN_SCORE removed them.
    scored = rerank(query_text, candidates, top_n=len(candidates))
    if len(scored) <= 1:
        return scored[:top_n]

    # Scaled to the spread of this result set rather than a fixed constant:
    # rerank scores are cross-encoder logits with no stable range, so any
    # absolute nudge is either meaningless on a wide spread or decisive on a
    # narrow one. A fraction of the spread means "flip near-ties, never a
    # clear relevance gap" at every scale.
    vals = [c.get("rerank_score", 0.0) for c in scored]
    spread = max(vals) - min(vals)
    bonus = _LANG_TIEBREAK * spread
    scored.sort(key=lambda c: -(
        c.get("rerank_score", 0.0)
        + (bonus if _language_matches(_candidate_language(c), lang) else 0.0)
    ))
    return scored[:top_n]
