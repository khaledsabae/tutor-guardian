#!/usr/bin/env python3
"""
إعادة تحقّق من ترجمات المنهج الإنجليزية — عدّ حقيقي بدل سجلات بائتة
====================================================================

الاستخدام:
  python3 ops/tools/revalidate_translations.py --all
  python3 ops/tools/revalidate_translations.py --kind lessons --limit 20
  python3 ops/tools/revalidate_translations.py --all --report-only

لماذا هذه الأداة موجودة
-----------------------
ملفات `i18n/en/` تخزّن ٣٦٢ سجل `review_defects` من تشغيلة المراجع الأصلية.
ثم جرت مراجعة شرعية فعلية يوم 2026-08-11 ونزلت إصلاحات في c9a5c30 و a751423
و 4e50b33 و bdfac1f و d02baf1 — **ولم يُعَد تشغيل المراجع.** فالسجلات تصف نصًّا
لم يعد موجودًا.

مقيس قبل كتابة هذه الأداة: من ٣٥٩ سجلًّا يقتبس مقتطفًا إنجليزيًّا يمكن البحث
عنه، **٧٠ (١٩٪) اختفى مقتطفها من النص** — أي أنها مُصلَحة سلفًا. مثال مؤكَّد:
`lesson_0-3_islamic_parenting_attachment_03` يخزّن عيبَي «رحمة→rifq» والنص
الحالي فيه `rahmah` ولا أثر لـ`rifq`.

اتخاذ قرار على عدّ بائت يعني إصلاح ما أُصلح وترك ما لم يُصلَح. فالخطوة الأولى
قياس، لا إصلاح.

⚠️ هذه الأداة **تقرأ وتعيد الحكم فقط**. لا تعدّل نصًّا مترجَمًا ولا ملفًا عربيًّا،
ولا تضع `approved_by` — ذاك توقيع بشري لا ناتج أداة.
"""

import argparse
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# نستورد الأداة الأصلية بدل نسخ ثوابتها. الملف يكوّد إخفاقات وقعت فعلًا
# (٣٤ حقنة مصطلحات، وحديث بلا إسناد أفلت من الكواشف) — ونسخة ثانية منها
# تعني نسختين تنحرفان.
_spec = importlib.util.spec_from_file_location(
    "translate_curriculum", Path(__file__).with_name("translate_curriculum.py"))
tc = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, [sys.argv[0]]  # الوحدة لا تفسّر argv، لكن لا نخاطر
try:
    _spec.loader.exec_module(tc)
finally:
    sys.argv = _argv

CURRICULUM = ROOT / "knowledge_base" / "curriculum"
I18N_EN = CURRICULUM / "i18n" / "en"

# نفس تقسيم الحقول المستعمل في الترجمة. مراجعة حقول لم تُترجَم تنتج ضجيجًا.
FIELDS_BY_KIND = {
    "lessons": tc.LESSON_FIELDS,
    "paths": tc.PATH_FIELDS,
    "daily_tips": tc.TIP_FIELDS,
}


def _payloads(en_path: Path, kind: str) -> tuple[dict, dict, dict]:
    """يرجّع (الوثيقة الإنجليزية، الحقول العربية، الحقول الإنجليزية)."""
    en_doc = json.loads(en_path.read_text(encoding="utf-8"))
    ar_path = CURRICULUM / kind / en_path.name
    if not ar_path.exists():
        raise FileNotFoundError(f"لا أصل عربي: {ar_path.relative_to(ROOT)}")
    ar_doc = json.loads(ar_path.read_text(encoding="utf-8"))
    fields = FIELDS_BY_KIND[kind]
    return en_doc, tc._translatable(ar_doc, fields), tc._translatable(en_doc, fields)


def revalidate(en_path: Path, kind: str, force: bool) -> dict:
    """يعيد حكم المراجع على النص الحالي ويعيد كتابة سجل المراجعة."""
    rid = en_path.stem
    try:
        en_doc, ar_payload, en_payload = _payloads(en_path, kind)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {"id": rid, "kind": kind, "status": "failed", "reason": str(e)}

    prev = en_doc.get("translation") or {}
    if prev.get("revalidated_at") and not force:
        return {"id": rid, "kind": kind, "status": "skipped",
                "reason": "مُعاد تحقّقه سلفًا"}
    if not ar_payload or not en_payload:
        return {"id": rid, "kind": kind, "status": "skipped",
                "reason": "لا حقول قابلة للمراجعة"}

    stale_before = len(prev.get("review_defects") or [])

    review_input = json.dumps(
        {"arabic": ar_payload, "english": en_payload}, ensure_ascii=False)
    try:
        raw, usage = tc._post(tc.REVIEWER_MODEL, tc.SYSTEM_REVIEW, review_input)
    except Exception as e:
        return {"id": rid, "kind": kind, "status": "failed",
                "reason": f"{type(e).__name__}: {e}"}
    try:
        review = tc._parse_json(raw)
    except json.JSONDecodeError as e:
        return {"id": rid, "kind": kind, "status": "failed",
                "reason": f"ناتج مراجع غير صالح: {e}"}

    defects = review.get("defects") or []

    # القيد البرمجي يُعاد تطبيقه على النص الحالي: حقن مصطلح إسلامي لا جذر له
    # في العربية عيب يقيني لا رأي نموذج، وقد وقع ٣٤ مرة فعلًا.
    injections = tc._validate_glossary(ar_payload, en_payload)
    for msg in injections:
        defects.append({"type": "term_error", "field": "(glossary-guard)",
                        "arabic": "", "english": "", "why": msg,
                        "severity": "high", "source": "programmatic"})

    src_json = json.dumps(ar_payload, ensure_ascii=False)
    sig_marker = bool(tc.RELIGIOUS_MARKERS.search(src_json))
    sig_quoted = bool(tc.QUOTED_ARABIC.search(src_json))
    sig_model = bool(review.get("contains_religious_text"))

    tr = dict(prev)
    tr.update({
        "reviewer_model": tc.REVIEWER_MODEL,
        "needs_scholar_review": sig_marker or sig_quoted or sig_model,
        "scholar_signals": {"keyword": sig_marker, "quoted_arabic": sig_quoted,
                            "reviewer_model": sig_model},
        "review_verdict": "defects" if defects else "clean",
        "review_defects": defects,
        "revalidated_at": datetime.now(timezone.utc).isoformat(),
        # 🚨 لا نلمس approved_by. توقيع بشري لا ناتج أداة.
        "approved_by": prev.get("approved_by"),
    })
    en_doc["translation"] = tr
    en_path.write_text(
        json.dumps(en_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "id": rid, "kind": kind, "status": "revalidated",
        "before": stale_before, "after": len(defects),
        "injections": len(injections),
        "defects": defects,
        "needs_scholar_review": tr["needs_scholar_review"],
        "tokens_out": usage.get("completion_tokens", 0),
        "tokens_in": usage.get("prompt_tokens", 0),
    }


def collect(kinds: list[str], limit: int | None) -> list[tuple[Path, str]]:
    jobs = []
    for kind in kinds:
        jobs += [(f, kind) for f in sorted((I18N_EN / kind).glob("*.json"))]
    return jobs[:limit] if limit else jobs


def report_only(kinds: list[str]) -> None:
    """قياس بلا نداء نموذج: كم سجلًّا يقتبس نصًّا لم يعد موجودًا."""
    def s(v):
        return v if isinstance(v, str) else (
            "|".join(map(str, v)) if isinstance(v, list) else str(v))

    checkable = stale = live = 0
    sev = {}
    for path, _kind in collect(kinds, None):
        d = json.loads(path.read_text(encoding="utf-8"))
        body = json.dumps({k: v for k, v in d.items() if k != "translation"},
                          ensure_ascii=False).lower()
        for x in ((d.get("translation") or {}).get("review_defects") or []):
            snippet = s(x.get("english", "")).strip().lower()
            if not 6 <= len(snippet) <= 120:
                continue
            checkable += 1
            if snippet in body:
                live += 1
                sev[s(x.get("severity"))] = sev.get(s(x.get("severity")), 0) + 1
            else:
                stale += 1
    print(f"سجلات تقتبس مقتطفًا يمكن فحصه : {checkable}")
    if checkable:
        print(f"  المقتطف اختفى (مُصلَح سلفًا) : {stale}  ({stale/checkable*100:.0f}%)")
        print(f"  المقتطف ما زال موجودًا      : {live}  ({live/checkable*100:.0f}%)")
        print(f"  الموجود بحسب الخطورة        : {sev}")
    print("\nℹ️  «المقتطف موجود» ≠ «العيب حقيقي» — المراجع مُوجَّه للطعن فينتج "
          "نقدًا صحيحًا وزائدًا.\n   شغّل بلا --report-only لحكم جديد على النص الحالي.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="الأنواع الثلاثة")
    ap.add_argument("--kind", choices=sorted(FIELDS_BY_KIND), action="append",
                    help="نوع واحد أو أكثر")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true", help="أعد التحقّق حتى المُعاد")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--report-only", action="store_true",
                    help="قياس بلا نداء نموذج")
    ap.add_argument("--json-out", type=Path, help="اكتب النتائج الخام هنا")
    args = ap.parse_args()

    kinds = sorted(FIELDS_BY_KIND) if args.all else (args.kind or [])
    if not kinds:
        sys.exit("❌ مرّر --all أو --kind")

    if args.report_only:
        report_only(kinds)
        return

    jobs = collect(kinds, args.limit)
    print(f"🔍 {len(jobs)} ملف لإعادة التحقّق · مراجع: {tc.REVIEWER_MODEL}\n")

    def run_one(job):
        # ملف يسقط لا يُسقِط الرحلة.
        path, kind = job
        try:
            return revalidate(path, kind, args.force)
        except Exception as e:
            return {"id": path.stem, "kind": kind, "status": "failed",
                    "reason": f"{type(e).__name__}: {e}"}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_one, jobs))

    ok = [r for r in results if r["status"] == "revalidated"]
    failed = [r for r in results if r["status"] == "failed"]
    skipped = [r for r in results if r["status"] == "skipped"]
    before = sum(r["before"] for r in ok)
    after = sum(r["after"] for r in ok)
    inj = sum(r["injections"] for r in ok)
    by_sev = {}
    for r in ok:
        for d in r["defects"]:
            k = d.get("severity", "?")
            by_sev[k] = by_sev.get(k, 0) + 1

    print("═" * 62)
    print(f"  مُعاد تحقّقه : {len(ok)}")
    print(f"  متخطّى      : {len(skipped)}")
    print(f"  فاشل        : {len(failed)}")
    print(f"  الملاحظات   : {before} مخزَّنة → {after} بعد إعادة الحكم")
    print(f"  بحسب الخطورة: {by_sev}")
    if inj:
        print(f"  🚨 حقن مصطلحات أمسكه القيد البرمجي: {inj}")
    print(f"  التوكن      : دخل={sum(r['tokens_in'] for r in ok):,}"
          f"  خرج={sum(r['tokens_out'] for r in ok):,}")
    print(f"  الزمن       : {time.time() - t0:.0f} ثانية")
    print("═" * 62)

    for r in failed:
        print(f"  ❌ {r['id']}: {r['reason']}")

    high = [(r["id"], d) for r in ok for d in r["defects"]
            if d.get("severity") == "high"]
    if high:
        print(f"\n🔴 {len(high)} ملاحظة عالية الخطورة — ابدأ من هنا:\n")
        for rid, d in high:
            print(f"  [{d.get('type')}] {rid} · {d.get('field')}")
            print(f"      {d.get('why')}")

    if args.json_out:
        args.json_out.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n📄 النتائج الخام: {args.json_out}")


if __name__ == "__main__":
    main()
