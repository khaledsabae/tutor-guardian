"""In-memory BM25 index over the knowledge units (lexical leg of hybrid
retrieval).

293 units is tiny — the index builds in well under a second at first use
and lives in process memory. Documents are normalized Arabic
(text_simplified + behavior_type + labels + title-ish keywords) so
lexical matches survive hamza/teh-marbuta/diacritics variance.
"""
from __future__ import annotations

import logging
import re
import threading

from rank_bm25 import BM25Okapi

from app.services.knowledge_loader import load_default_knowledge_units

logger = logging.getLogger(__name__)

_DIACRITICS = re.compile(r"[ً-ْٰـ]")  # harakat + tatweel
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_arabic(text: str) -> str:
    """Light Arabic normalization for lexical matching."""
    text = _DIACRITICS.sub("", text or "")
    text = (
        text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    )
    text = _NON_WORD.sub(" ", text)
    return text.lower()


def _tokenize(text: str) -> list[str]:
    tokens = []
    for tok in normalize_arabic(text).split():
        # strip the definite article so «الصلاة» matches «صلاة»
        if len(tok) > 3 and tok.startswith("ال"):
            tok = tok[2:]
        if len(tok) >= 2:
            tokens.append(tok)
    return tokens


class _Bm25Index:
    def __init__(self) -> None:
        units = load_default_knowledge_units()
        self.meta: list[dict] = []
        corpus: list[list[str]] = []
        for u in units:
            blob = " ".join(
                filter(None, [u.text_simplified, u.behavior_type,
                              " ".join(u.labels or [])])
            )
            corpus.append(_tokenize(blob))
            self.meta.append({
                "unit_id": u.id,
                "document": f"passage: {u.text_simplified}",
                "metadata": {
                    "unit_id": u.id,
                    "domain": u.domain,
                    "age_group": u.age_group,
                    "behavior_type": u.behavior_type,
                    "intervention_type": u.intervention_type,
                    "severity": u.severity,
                    "labels": ", ".join(u.labels) if u.labels else "",
                    "reference_info": u.reference_info,
                },
            })
        self.bm25 = BM25Okapi(corpus)
        logger.info("BM25 index built over %d units", len(self.meta))

    def search(self, query: str, domain: str | None = None, top_k: int = 8) -> list[dict]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
        out: list[dict] = []
        for idx in ranked:
            if scores[idx] <= 0:
                break
            m = self.meta[idx]
            if domain and m["metadata"]["domain"] != domain:
                continue
            out.append({**m, "bm25_score": float(scores[idx])})
            if len(out) >= top_k:
                break
        return out


_index: _Bm25Index | None = None
_lock = threading.Lock()


def get_bm25() -> _Bm25Index:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = _Bm25Index()
    return _index
