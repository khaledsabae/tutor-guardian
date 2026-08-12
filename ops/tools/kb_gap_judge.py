"""Judge each (question, retrieved unit) pair for topical relevance.

The judge is DeepSeek with a narrow rubric. A model judging a model's retrieval
is only as good as the spot-check that follows, so every verdict is written out
with its reasoning for manual review.
"""
import json
import os
import sys
import time

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


def main():
    pairs = json.load(open("/tmp/retrieval_pairs.json", encoding="utf-8"))
    cl = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    results = []
    n = 0
    for row in pairs:
        for u in row["units"]:
            n += 1
            prompt = (RUBRIC.replace("{q}", row["question"])
                            .replace("{age}", row["age_group"])
                            .replace("{text}", u["text"]))
            grade, why = "?", ""
            for attempt in range(3):
                try:
                    r = cl.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0, max_tokens=120)
                    raw = r.choices[0].message.content or ""
                    j = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
                    grade, why = j.get("درجة", "?"), j.get("سبب", "")
                    break
                except Exception as exc:
                    if attempt == 2:
                        why = f"judge-failed: {type(exc).__name__}"
                    time.sleep(1.5)
            results.append({
                "question": row["question"], "age": row["age_group"],
                "domains": row["domains"], "unit_domain": u["domain"],
                "reference": u["reference"], "rerank": u["rerank"],
                "grade": grade, "why": why, "text": u["text"][:200],
            })
            if n % 20 == 0:
                print(f"  حُكم {n} زوج…", flush=True)
    json.dump(results, open("/tmp/retrieval_judged.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    import collections
    c = collections.Counter(r["grade"] for r in results)
    total = len(results)
    print(f"\nالمجموع: {total} زوج")
    for g in ("صلة", "جزئية", "لا صلة", "?"):
        if c[g]:
            print(f"  {g:8s} {c[g]:4d}  ({100*c[g]/total:.1f}%)")
    # precision@4 per question: share of fully-relevant units
    per_q = collections.defaultdict(list)
    for r in results:
        per_q[r["question"]].append(r["grade"])
    clean = sum(1 for g in per_q.values() if "لا صلة" not in g)
    print(f"\nأسئلة بلا أي وحدة خارج الموضوع: {clean}/{len(per_q)}")


if __name__ == "__main__":
    main()
