#!/usr/bin/env python3
"""Link the 25 new hand-authored lessons (unit_ids == []) to the most relevant
knowledge-base units, so the lesson screen stops showing "مرتبط بـ 0 وحدة" and
the lessons gain grounded references.

For each new lesson we query the (improved) hybrid retrieval with the lesson's
title+summary, restricted to the lesson's own domain + age band, and keep the
top units whose rerank score clears the relevance floor. Prints a report so we
can see which lessons still lack a good KB match (→ candidates for new units).
"""
import json
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from app.services.retrieval import _ensure_index, retrieve_hybrid  # noqa: E402
from app.services.reranker import RERANK_MIN_SCORE  # noqa: E402

LESSONS_DIR = (pathlib.Path(__file__).resolve().parent.parent
               / "knowledge_base" / "curriculum" / "lessons")

TOP_N = 3


def main():
    _ensure_index()
    new = [f for f in sorted(LESSONS_DIR.glob("*.json"))
           if f.stem.rsplit("_", 1)[-1].startswith("b")]
    print(f"Linking {len(new)} new lessons…\n")
    weak = []
    for f in new:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("unit_ids"):
            continue
        query = f"{d['title']} {d.get('summary', '')[:200]}"
        units = retrieve_hybrid(
            query_text=query, domains=[d["domain"]],
            age_group=d["age_group"], top_n=TOP_N,
        )
        kept = [(u["unit_id"], round(u.get("rerank_score", -99), 2))
                for u in units
                if u.get("rerank_score", -99) >= RERANK_MIN_SCORE]
        d["unit_ids"] = [uid for uid, _ in kept]
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        top = kept[0][1] if kept else None
        flag = "" if (top is not None and top > -4) else "  ⚠ weak/none"
        print(f"{d['id']:<46} → {len(kept)} units  top={top}{flag}")
        if not kept or top is None or top <= -4:
            weak.append(d["id"])

    print(f"\nLessons still weak/unlinked ({len(weak)}): "
          f"{weak if weak else 'none — all grounded ✅'}")


if __name__ == "__main__":
    main()
