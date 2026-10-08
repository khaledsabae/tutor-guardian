"""Build disposable indexes from frozen real vectors; never migrate a database.

Only the CLI's experiment modes import ML/Chroma. The comparator remains the
authority for recall arithmetic. This is offline hybrid recall, not an upgrade gate.
"""
import argparse
import hashlib
from importlib.metadata import version
import inspect
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ops/tools"))
from chroma_recall_probe import digest  # noqa: E402
from golden_ci import base_report, deny_external_network, load_set, offline_report  # noqa: E402

ML_PACKAGES = ("torch", "numpy", "sentence-transformers", "transformers",
               "huggingface_hub", "tokenizers", "scikit-learn", "scipy", "rank-bm25")
POLICY_FILES = ("retrieval.py", "reranker.py", "bm25_index.py", "domain_classifier.py",
                "knowledge_loader.py")


def catalog(bundle):
    return {"unit_ids": sorted(bundle["corpus"]["ids"]),
            "domains": sorted({m["domain"] for m in bundle["corpus"]["metadatas"]})}


def validate_bundle(bundle, golden):
    corpus, vectors = bundle["corpus"], bundle["vectors"]
    ids = corpus["ids"]
    if not ids or len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("empty or duplicate corpus IDs")
    if any(len(corpus[key]) != len(ids) for key in ("units", "documents", "metadatas")):
        raise ValueError("corpus columns differ in length")
    if [u["id"] for u in corpus["units"]] != ids:
        raise ValueError("unit insertion order differs")
    if len(vectors["documents"]) != len(ids):
        raise ValueError("document vectors differ in length")
    if set(vectors["queries"]) != {g["question"] for g in golden}:
        raise ValueError("query vectors differ from golden questions")
    rows = vectors["documents"] + list(vectors["queries"].values())
    dimension = len(rows[0])
    if not dimension or any(len(v) != dimension or any(
        type(n) not in (float, int) or not math.isfinite(n) for n in v
    ) for v in rows):
        raise ValueError("non-finite or inconsistent vectors")


def capture_metadata(bundle, golden, chroma_version):
    return {"chroma_version": chroma_version, "top_k": bundle["policy"]["top_k"],
            "golden_sha256": digest(golden), "catalog_sha256": digest(catalog(bundle)),
            "corpus_sha256": digest(bundle["corpus"]),
            "embedding_sha256": digest(bundle["vectors"]),
            "query_policy_sha256": digest(bundle["policy"])}


def fresh_directory(path):
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"refusing non-empty index: {path}")
    path.mkdir(parents=True, exist_ok=True)


class FrozenQueries:
    def __init__(self, vectors):
        self.vectors = vectors
        self.errors = []

    def __call__(self, text):
        if text not in self.vectors:
            self.errors.append(text)
            raise ValueError("unfrozen query requested")
        return self.vectors[text]


class QueryGuard:
    """Retain SDK failures even when production _query degrades to empty results."""
    def __init__(self, collection):
        self.collection = collection
        self.errors = []

    def __getattr__(self, name):
        return getattr(self.collection, name)

    def query(self, **kwargs):
        try:
            return self.collection.query(**kwargs)
        except Exception as exc:
            self.errors.append(type(exc).__name__)
            raise


def checked_rerank(rerank, disabled):
    def checked(*args, **kwargs):
        result = rerank(*args, **kwargs)
        if disabled() or any("rerank_score" not in r for r in result):
            raise RuntimeError("reranker degraded during capture")
        return result
    return checked


def policy(retrieval, reranker):
    from huggingface_hub import snapshot_download

    return {
        "top_k": inspect.signature(retrieval.retrieve_hybrid).parameters["top_n"].default,
        "ml_packages": {name: version(name) for name in ML_PACKAGES},
        "models": {name: Path(snapshot_download(name, local_files_only=True)).name
                   for name in (retrieval.EMBEDDING_MODEL, reranker.RERANKER_MODEL)},
        "sources": {name: hashlib.sha256((ROOT / "backend/app/services" / name).read_bytes()).hexdigest()
                    for name in POLICY_FILES},
        "reranker": {name: getattr(reranker, name) for name in (
            "RERANK_ENABLED", "RERANK_MIN_SCORE", "RERANK_BUDGET_S", "RERANK_MAX_STRIKES")},
        "embedding": {"normalized": True, "query_prefix": "query: ",
                      "passage_input": "KnowledgeUnit.embedding_text", "metric": "cosine"},
        "scope": "golden_ci offline fallback domains + production hybrid; no LLM/rewrite/answers",
    }


def freeze(golden, retrieval, reranker):
    from app.services.knowledge_loader import load_default_knowledge_units

    units = load_default_knowledge_units()
    # Preserve insertion order for HNSW and BM25 ties; never sort the corpus.
    corpus = {"units": [u.model_dump(mode="json") for u in units],
              "ids": [u.id for u in units],
              "documents": [f"passage: {u.text_simplified}" for u in units],
              "metadatas": [retrieval._unit_metadata(u) for u in units]}
    vectors = {"documents": retrieval._embedder()([u.embedding_text for u in units]),
               "queries": {q: retrieval.embed_query(q) for q in dict.fromkeys(g["question"] for g in golden)}}
    reranker._get_model()  # Download/warm once; candidate uses this same offline snapshot.
    return {"corpus": corpus, "vectors": vectors, "policy": policy(retrieval, reranker)}


def prepare(bundle, index, retrieval, reranker):
    from app.core.taxonomy import CANONICAL_DOMAINS
    from app.models.knowledge import KnowledgeUnit
    from app.services import bm25_index
    from app.services.domain_classifier import fallback_domains

    fresh_directory(index)
    retrieval.CHROMA_PERSIST_DIR = index
    retrieval._TELEMETRY_DB = index.parent / "retrieval.db"
    retrieval._collection = None
    # Exercise the application's explicit custom EF and cosine collection API.
    collection = retrieval._get_collection()
    corpus = bundle["corpus"]
    # Chroma's per-call limit varies between engines. Identical ordered batches.
    for start in range(0, len(corpus["ids"]), 128):
        stop = start + 128
        collection.add(**{k: corpus[k][start:stop] for k in ("ids", "documents", "metadatas")},
                       embeddings=bundle["vectors"]["documents"][start:stop])
    actual = collection.get(include=["metadatas", "documents"])
    expected = {i: (d, m) for i, d, m in zip(corpus["ids"], corpus["documents"], corpus["metadatas"])}
    restored = {i: (d, m) for i, d, m in zip(actual["ids"], actual["documents"], actual["metadatas"])}
    if collection.count() != len(expected) or restored != expected:
        raise ValueError("index content differs from frozen corpus")
    guarded = QueryGuard(collection)
    retrieval._collection = guarded
    retrieval._index_built = True  # Never enter seed-copy/purge/re-embedding paths.
    units = [KnowledgeUnit.model_validate(u) for u in corpus["units"]]
    retrieval.load_default_knowledge_units = lambda: units
    bm25_index.load_default_knowledge_units = lambda: units
    bm25_index._index = None
    retrieval._unit_languages.cache_clear()
    queries = FrozenQueries(bundle["vectors"]["queries"])
    retrieval.embed_query = queries
    reranker.rerank = checked_rerank(reranker.rerank, lambda: reranker._disabled)

    def retrieve(item):
        guarded.errors.clear()
        queries.errors.clear()
        domains = fallback_domains(item["question"])
        result = retrieval.retrieve_hybrid(item["question"], domains, item["age_group"],
                                           lang=retrieval.detect_query_language(item["question"]))
        if guarded.errors or queries.errors:
            raise RuntimeError("vector query or frozen lookup failed during capture")
        return domains, result

    return retrieve, CANONICAL_DOMAINS, set(actual["ids"])


def summary(report):
    return "\n".join([
        "# Chroma 1.x offline recall comparison", "",
        f"Status: **{report['status']}**", "",
        "```json", json.dumps({k: report.get(k) for k in (
            "declared_versions", "counts", "paired_metrics", "reasons", "reason")}, indent=2), "```", "",
        "Runtime compatibility: UNVERIFIED. Recall gate: NOT_EVALUATED.",
        "Complete coverage is not an upgrade approval. No answer quality, migration,",
        "production resource fit, deployment, or production data was evaluated.", "",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "candidate", "summary"))
    parser.add_argument("--golden", type=Path, default=ROOT / "ops/eval/golden_set.jsonl")
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--summary", type=Path, help="comparison JSON for summary mode")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "summary":
        args.out.write_text(summary(json.loads(args.summary.read_text())), encoding="utf-8")
        return 0
    # The CLI intentionally requires a hosted/scratch temp boundary before imports.
    private = Path(os.environ["RUNNER_TEMP"]).resolve()
    for path in (args.out, args.frozen, args.index, args.catalog):
        if path is None or not path.resolve().is_relative_to(private) or path.resolve() == private:
            parser.error("all experiment outputs/indexes must be below RUNNER_TEMP")
    golden = load_set(args.golden)
    report = base_report(golden, "frozen-input offline hybrid recall", "No answer generation or judging")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from app.services import retrieval, reranker

        if not reranker.RERANK_ENABLED:
            raise ValueError("reranker must be enabled for this experiment")
        if args.mode == "baseline":
            bundle = freeze(golden, retrieval, reranker)
            args.frozen.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        else:
            bundle = json.loads(args.frozen.read_text())
            if bundle["policy"] != policy(retrieval, reranker):
                raise ValueError("model/library/query policy drift")
            reranker._get_model()
        validate_bundle(bundle, golden)
        args.catalog.write_text(json.dumps(catalog(bundle), indent=2), encoding="utf-8")
        report["metadata"] = capture_metadata(bundle, golden, version("chromadb"))
        report["policy"] = bundle["policy"]
        prepared = prepare(bundle, args.index, retrieval, reranker)
        # Both captures run offline after baseline weights are warmed.
        deny_external_network()
        evaluated = offline_report(golden, args.index.parent, prepare=lambda _: prepared,
                                   checkpoint=args.out)
        report.update(evaluated)
    except Exception as exc:
        report["reason"] = f"capture failed: {type(exc).__name__}: {exc}"
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"], "reason": report.get("reason")}))
    return 0 if report["status"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
