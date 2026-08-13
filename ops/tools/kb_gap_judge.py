"""Judge each (question, retrieved unit) pair for topical relevance.

The judge is DeepSeek with a narrow rubric. A model judging a model's retrieval
is only as good as the spot-check that follows, so every verdict is written out
with its reasoning for manual review.

    python ops/tools/kb_gap_judge.py --in /tmp/retrieval_pairs.json \
        --out /tmp/retrieval_judged.json --max-pairs 400 --concurrency 5

Scale matters here: one call per (question, unit) pair means the default probe
is ~120 calls, but the 1,616 stored production questions would be ~6,500. That
is why --max-pairs is a hard stop rather than advice, and why the weekly loop
samples the tail instead of re-judging everything.
"""
import argparse
import collections
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

RUBRIC = """أنت محكّم لجودة استرجاع في تطبيق تربية أطفال.
أمامك سؤال من أب/أم، ونص وحدة معرفية استرجعها النظام كمرجع للإجابة.

قيّم صلة الوحدة بالسؤال بدرجة واحدة فقط:
- "صلة" : الوحدة تعالج نفس الموضوع وتفيد في الإجابة مباشرة.
- "جزئية" : الوحدة في نفس المجال العام لكنها لا تعالج السؤال تحديدًا (مثال: سؤال عن الخجل ووحدة عن التربية العامة).
- "لا صلة" : الوحدة عن موضوع مختلف تمامًا (مثال: سؤال عن الخجل ووحدة عن التغذية).

أجب بـ JSON فقط: {"درجة": "...", "سبب": "جملة قصيرة"}

السؤال: {q}
عمر الطفل: {age}

نص الوحدة:
{text}
"""

_progress_lock = threading.Lock()
_done = 0


def _judge_one(cl, model, row, unit, quiet):
    """One verdict. Never raises: a dead judge degrades to grade '?'."""
    global _done
    prompt = (RUBRIC.replace("{q}", row["question"])
                    .replace("{age}", row.get("age_group") or "unspecified")
                    .replace("{text}", unit["text"]))
    grade, why = "?", ""
    for attempt in range(3):
        try:
            r = cl.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0, max_tokens=120)
            raw = r.choices[0].message.content or ""
            j = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
            grade, why = j.get("درجة", "?"), j.get("سبب", "")
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                why = f"judge-failed: {type(exc).__name__}"
            else:
                time.sleep(1.5)
    with _progress_lock:
        _done += 1
        if not quiet and _done % 20 == 0:
            print(f"  حُكم {_done} زوج…", flush=True)
    return {
        "question": row["question"], "age": row.get("age_group") or "",
        "domains": row.get("domains") or [], "unit_domain": unit["domain"],
        "reference": unit["reference"], "rerank": unit["rerank"],
        "grade": grade, "why": why, "text": unit["text"][:200],
    }


def summarize(results: list[dict]) -> dict:
    """Grade distribution + per-question cleanliness, as data not print()."""
    total = len(results)
    counts = collections.Counter(r["grade"] for r in results)
    per_q = collections.defaultdict(list)
    for r in results:
        per_q[r["question"]].append(r["grade"])
    # A question is "unserved" when retrieval found nothing that addresses it —
    # this is the signal the weekly report is actually built on.
    unserved = [q for q, gs in per_q.items() if "صلة" not in gs]
    clean = sum(1 for gs in per_q.values() if "لا صلة" not in gs)
    return {
        "pairs": total,
        "questions": len(per_q),
        "counts": dict(counts),
        "clean_questions": clean,
        "unserved_questions": unserved,
    }


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Judge retrieval pairs with DeepSeek.")
    ap.add_argument("--in", dest="inp", default="/tmp/retrieval_pairs.json")
    ap.add_argument("--out", default="/tmp/retrieval_judged.json")
    ap.add_argument("--max-pairs", type=int, default=600,
                    help="hard ceiling on judge calls (cost guard)")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    with open(args.inp, encoding="utf-8") as fh:
        rows = json.load(fh)

    jobs = [(row, u) for row in rows for u in row.get("units", [])]
    if len(jobs) > args.max_pairs:
        # Never silently truncate: a capped run that reads as a full one is how
        # "we covered everything" becomes false.
        print(f"⚠️  {len(jobs)} زوجًا يتجاوز السقف {args.max_pairs} — "
              f"سيُحكم على {args.max_pairs} فقط، والباقي غير مفحوص.")
        jobs = jobs[:args.max_pairs]

    if not jobs:
        print("لا أزواج للحكم.")
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump([], fh, ensure_ascii=False)
        return 0

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("DEEPSEEK_API_KEY غير مضبوط — لا يمكن الحكم.", file=sys.stderr)
        return 2
    cl = OpenAI(api_key=key,
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(
            lambda j: _judge_one(cl, args.model, j[0], j[1], args.quiet), jobs
        ))

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)

    s = summarize(results)
    print(f"\nالمجموع: {s['pairs']} زوج · {s['questions']} سؤال")
    for g in ("صلة", "جزئية", "لا صلة", "?"):
        if s["counts"].get(g):
            print(f"  {g:8s} {s['counts'][g]:4d}  ({100*s['counts'][g]/s['pairs']:.1f}%)")
    print(f"\nأسئلة بلا أي وحدة خارج الموضوع: {s['clean_questions']}/{s['questions']}")
    print(f"أسئلة لم يخدمها الاسترجاع إطلاقًا: {len(s['unserved_questions'])}/{s['questions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
