#!/usr/bin/env python3
"""
feedback_digest — تقرير قرارات قابل للقراءة من تحليل الفيدباك الذكي.

التشغيل (من جذر المشروع، مع DEEPSEEK_API_KEY مضبوط):
    python ops/tools/feedback_digest.py [--limit 200]

يعرض: التوزيع حسب التصنيف + العناصر الحقيقية القابلة للتنفيذ مرتّبة بالخطورة.
يُفضّل تشغيله على السيرفر حيث قاعدة الفيدباك الحقيقية.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

_SEV = {5: "🔴 حرج", 4: "🟠 عالٍ", 3: "🟡 متوسط", 2: "🔵 منخفض", 1: "⚪ تافه"}
_CAT_AR = {
    "wrong_answer": "إجابة خاطئة", "kb_gap": "ثغرة معرفة", "bug": "عُطل تقني",
    "content_error": "خطأ محتوى", "feature_request": "طلب ميزة",
    "praise": "مدح", "noise": "ضجيج",
}


def _print_report(digest: dict) -> None:
    print("\n" + "=" * 60)
    print("📊  ملخّص قرارات الفيدباك — المربّي")
    print("=" * 60)
    print(f"إجمالي العناصر: {digest['total']}  |  "
          f"حقيقية قابلة للتنفيذ: {digest['actionable_count']}  |  "
          f"نوتات صوتية للمراجعة: {digest['voice_notes_pending']}")
    print("\nالتوزيع حسب التصنيف:")
    for cat, n in sorted(digest["by_category"].items(), key=lambda x: -x[1]):
        print(f"  • {_CAT_AR.get(cat, cat):<14} {n}")
    if not digest["actionable"]:
        print("\n✅ لا توجد عناصر حقيقية تستحق قرارًا الآن.")
        return
    print("\n🎯 العناصر الحقيقية (مرتّبة بالخطورة):")
    for i, it in enumerate(digest["actionable"], 1):
        sev = _SEV.get(it.get("severity", 0), str(it.get("severity")))
        print(f"\n{i}. [{sev}] {_CAT_AR.get(it['category'], it['category'])}")
        print(f"   المشكلة: {it['issue']}")
        print(f"   الإجراء: {it['recommended_action']}")
        print(f"   المصدر: {it['raw']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()
    from app.services.feedback_analyzer import analyze

    digest = asyncio.run(analyze(args.limit))
    _print_report(digest)


if __name__ == "__main__":
    main()
