"""Measure retrieval precision locally — never against the production index.

Runs the real pipeline (classify → rewrite → retrieve_hybrid) over realistic
parent questions and dumps every (question, retrieved unit) pair to JSON for
judging. Deliberately local: probing the live Chroma index from a second
process is what stranded the collection handle and 500'd production.

Two ways in:
  * no args — the built-in QUESTIONS list below (a fixed yardstick).
  * --questions-file — JSONL of {"question": ..., "age_group": ...}, which is
    how the weekly loop feeds it real parent questions from chat_messages.

    python ops/tools/retrieval_probe.py \
        --questions-file /tmp/week.jsonl --out /tmp/retrieval_pairs.json
"""
import argparse
import json
import sys
import time

sys.path.insert(0, "/app")

from app.services.domain_classifier import classify_domains, matched_fast_path
from app.services.query_rewriter import rewrite_query
from app.services.retrieval import retrieve_hybrid

# Realistic parent phrasing, Egyptian colloquial, spread across domains and ages.
# Deliberately NOT the app's suggested questions — those all hit the keyword
# fast path and would measure the easiest case.
QUESTIONS = [
    ("ابني بيتكسف يسلم على الناس ويختبي ورايا", "4-6"),
    ("طفلي بيخاف من الحمام ومش عايز يدخل لوحده", "2-3"),
    ("ابني بيعض أخوه الصغير لما يزعل", "2-3"),
    ("بنتي بتعيط لما أسيبها في الحضانة", "4-6"),
    ("ابني مش بيحب يشارك ألعابه مع أولاد عمه", "4-6"),
    ("طفلي بيرفض يغسل سنانه كل يوم", "4-6"),
    ("ابني بيقول كلمات وحشة سمعها من الشارع", "7-9"),
    ("بنتي بتقارن نفسها بصحابها في اللبس", "10-12"),
    ("ابني بينسى واجباته في المدرسة باستمرار", "7-9"),
    ("طفلي بيخاف ينام لوحده في أوضته", "7-9"),
    ("ابني بيتخانق مع أخته على التلفزيون", "7-9"),
    ("بنتي بقت تسأل عن الموت وأنا مش عارفة أرد", "7-9"),
    ("ابني بيقعد على التابلت ساعات ومش بيسمع كلامي", "10-12"),
    ("بنتي دخلت على موقع مش مناسب من غير قصد", "10-12"),
    ("ابني حد كلمه على لعبة أونلاين وطلب صوره", "10-12"),
    ("ابني بيسيب صلاة الفجر وبيقول أنا تعبان", "10-12"),
    ("بنتي بتسأل ليه لازم نلبس الحجاب", "10-12"),
    ("ابني بيقول إن صحابه بيسخروا منه إنه بيصلي", "10-12"),
    ("بنتي المراهقة بقت تقفل باب أوضتها وماتكلمنيش", "13-15"),
    ("ابني بقى عصبي جدًا وبيرد عليا بحدة", "13-15"),
    ("بنتي بتقضي وقت طويل على التيك توك", "13-15"),
    ("ابني بيقارن نفسه بأصحابه في الفلوس", "13-15"),
    ("ابني المراهق صحابه بيدخنوا وأنا خايفة", "13-15"),
    ("بنتي بتقول إنها مش حاسة بحاجة وزهقانة من كل حاجة", "13-15"),
    ("ابني في الجامعة مش عارف يختار تخصصه", "16-18"),
    ("بنتي عايزة تشتغل وأنا مش موافق", "16-18"),
    ("ابني بيسهر برة البيت لوقت متأخر", "16-18"),
    ("طفلي عنده سنة ونص ولسه مش بيتكلم", "0-3"),
    ("ابني بيضرب راسه في الحيطة لما يتعصب", "2-3"),
    ("بنتي بترفض الأكل غير الشيبسي والحاجة الحلوة", "4-6"),
]


def _load_questions(path: str | None, limit: int | None) -> list[tuple[str, str]]:
    """Built-in list, or JSONL of {"question", "age_group"}."""
    if not path:
        items = list(QUESTIONS)
    else:
        items = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                q = (row.get("question") or "").strip()
                if q:
                    items.append((q, row.get("age_group") or "unspecified"))
    return items[:limit] if limit else items


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--questions-file", help="JSONL: {question, age_group} per line")
    ap.add_argument("--out", default="/tmp/retrieval_pairs.json")
    ap.add_argument("--limit", type=int, help="probe at most N questions")
    ap.add_argument("--quiet", action="store_true", help="suppress the per-question line")
    args = ap.parse_args(argv)

    questions = _load_questions(args.questions_file, args.limit)
    if not questions:
        print("لا أسئلة للفحص.")
        json.dump([], open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
        return 0

    # NO _ensure_index(): that is the rebuild path that deleted the collection
    # out from under the live handle and 500'd production. Reads only.
    out = []
    for q, age in questions:
        t0 = time.time()
        domains = classify_domains(q)
        rewritten = rewrite_query(q, classifier_fast_path=matched_fast_path(q))
        units = retrieve_hybrid(query_text=q, domains=domains, age_group=age,
                                rewritten_query=rewritten)
        out.append({
            "question": q,
            "age_group": age,
            "domains": domains,
            "fast_path": matched_fast_path(q),
            "elapsed": round(time.time() - t0, 2),
            "units": [{
                "title": (u.get("metadata", {}) or {}).get("behavior_type", ""),
                "domain": u.get("source_domain") or (u.get("metadata", {}) or {}).get("domain", ""),
                "reference": (u.get("metadata", {}) or {}).get("reference_info", ""),
                "rerank": u.get("rerank_score"),
                "text": (u.get("document", "") or "").removeprefix("passage: ")[:340],
            } for u in units],
        })
        if not args.quiet:
            print(f"  {q[:44]:46s} → {len(units)} وحدة  ({','.join(domains)})", flush=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    pairs = sum(len(r["units"]) for r in out)
    print(f"\nالأسئلة: {len(out)} | أزواج (سؤال، وحدة): {pairs} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
