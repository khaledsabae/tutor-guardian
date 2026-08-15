#!/usr/bin/env python3
"""
قياس ترتيب اللغة: ماذا كسبت العربية، وماذا خسرت الإنجليزية
==========================================================

    backend/.venv/bin/python ops/tools/language_rank_probe.py
    backend/.venv/bin/python ops/tools/language_rank_probe.py --verbose

لماذا يقيس هذا الاتجاهين
------------------------
تفضيل لغة القارئ يبدو مكسبًا صافيًا، وليس كذلك. الوحدات الإنجليزية ٤٣ من ١٬١٨٧،
فأيّ تفضيل للعربية يزاحمها في مجموعةٍ محدودة السعة (`rerank_pool`)، والخسارة تقع
على **٢٧٪ من المستخدمين** لا على حالةٍ هامشية.

وسابقة الفريق مباشرة: تضييق نطاق العمر يوم 2026-08-14 حسّن «الفئة الغلط» من ٣١٪
إلى صفر، **وأسقط في الوقت نفسه وحدةً صحيحة** لسؤال أكلٍ انتقائي في ٢–٣. رقم واحد
كان سيخفي ذلك.

🚨 **وعدّاد مطابقة اللغة وحده يكذب.** الكوربوس فيه ٢٥٠+ وحدة مستوردة بالجملة من
تقارير مؤسسية (ITU للشركات، WHO لسياسات الصحة) وأغلبها عربية و`unspecified`، فهي
مؤهَّلة في كل عمر. تفضيلُ العربية سيرفعها فوق وحدةٍ تربوية إنجليزية **ويُسجَّل
مكسبًا** بينما الإجابة تسوء. لذلك يطبع هذا المسبار **عناوين ما فاز** لا أعدادًا
فقط: الرقم يقول إن شيئًا تغيّر، والعنوان يقول إن كان تغيّرًا للأفضل.

Exit: 0 دائمًا — هذا قياس لا بوابة.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.retrieval import (  # noqa: E402
    retrieve_hybrid, _ensure_index, detect_query_language, _language_matches,
    _candidate_language,
)

# أسئلة حقيقية بصياغة الأهل — نفس السؤال بالعربية والإنجليزية حيث أمكن، لأن
# الصياغة هي القياس: نسخة سابقة من مسبار العمر اخترعت عطبًا لا وجود له لأنها
# أعادت استعمال سؤال واحد عبر كل الفئات.
PROBES = [
    ("كيف أتعامل مع نوبات الغضب عند ابني؟", "4-6", ["behavior"]),
    ("How do I handle my child's tantrums?", "4-6", ["behavior"]),
    ("ابني عنده سنتين ومش بيتكلم كتير، أعمل إيه؟", "2-3", ["development"]),
    ("My two-year-old barely talks, what should I do?", "2-3", ["development"]),
    ("كم ساعة شاشة مسموحة للطفل؟", "4-6", ["cyber"]),
    ("How much screen time is okay for a young child?", "4-6", ["cyber"]),
    ("ازاي أعلّم ابني الصلاة؟", "7-9", ["islamic_parenting"]),
    ("How do I teach my child to pray?", "7-9", ["islamic_parenting"]),
    ("ابني بيتبول في السرير وعنده ٨ سنين", "7-9", ["medical"]),
    ("My 8-year-old wets the bed", "7-9", ["medical"]),
]


def run(query, age, domains, lang):
    return retrieve_hybrid(
        query_text=query, domains=domains, age_group=age,
        rewritten_query="", lang=lang,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("=" * 74)
    print("  LANGUAGE RANK PROBE — الاتجاهان معًا")
    print("=" * 74)
    _ensure_index()

    rows = []
    for query, age, domains in PROBES:
        want = detect_query_language(query)
        before = run(query, age, domains, None)
        after = run(query, age, domains, want)

        def share(units):
            if not units:
                return 0.0
            hit = sum(1 for u in units
                      if _language_matches(_candidate_language(u), want))
            return hit / len(units)

        b_ids = [u.get("unit_id") or (u.get("metadata") or {}).get("unit_id")
                 for u in before]
        a_ids = [u.get("unit_id") or (u.get("metadata") or {}).get("unit_id")
                 for u in after]
        rows.append((query, want, share(before), share(after),
                     b_ids, a_ids, before, after))

    print(f"\n  {'lang':5} {'before':>7} {'after':>7}  question")
    print("  " + "-" * 70)
    gained = lost = same = 0
    for query, want, b, a, b_ids, a_ids, bu, au in rows:
        mark = "→" if b_ids == a_ids else ("↑" if a > b else "↓" if a < b else "≈")
        if b_ids == a_ids:
            same += 1
        elif a > b:
            gained += 1
        elif a < b:
            lost += 1
        print(f"  {want or '?':5} {b:6.0%} {a:6.0%} {mark} {query[:46]}")

    print(f"\n  same result set: {same}/{len(rows)}   "
          f"more own-language: {gained}   less: {lost}")

    # 🚨 الجزء الذي يمنع «مكسبًا» زائفًا: ماذا دخل وماذا خرج فعلًا.
    print("\n  " + "=" * 70)
    print("  ما تغيّر فعلًا — العناوين، لا الأعداد")
    print("  " + "=" * 70)
    for query, want, b, a, b_ids, a_ids, bu, au in rows:
        if b_ids == a_ids:
            continue
        print(f"\n  ▸ {query[:60]}  [{want}]")
        bmap = {(u.get("unit_id") or (u.get("metadata") or {}).get("unit_id")): u
                for u in bu}
        amap = {(u.get("unit_id") or (u.get("metadata") or {}).get("unit_id")): u
                for u in au}
        for sign, uids, src in (("+", [i for i in a_ids if i not in b_ids], amap),
                                ("-", [i for i in b_ids if i not in a_ids], bmap)):
            for uid in uids:
                m = src[uid].get("metadata") or {}
                # Resolved the same way the ranking resolves it — a probe that
                # reads language differently from the code measures a different
                # change than the one being shipped.
                lg = _candidate_language(src[uid]) or "?"
                print(f"      {sign} {lg:6} {m.get('age_group','?'):12} "
                      f"{str(m.get('title',''))[:44]}")

    print("\n  اقرأ العناوين قبل تسمية هذا مكسبًا: وحدة سياسات عربية تعلو فوق"
          "\n  وحدة تربوية إنجليزية تُحسَب مكسبًا هنا والإجابة تسوء.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
