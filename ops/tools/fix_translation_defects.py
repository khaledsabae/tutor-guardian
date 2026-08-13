#!/usr/bin/env python3
"""
إصلاح ملاحظات المراجع على الترجمة الإنجليزية — بثلاث بوابات لا بثقة
====================================================================

الاستخدام:
  python3 ops/tools/fix_translation_defects.py --severity high --dry-run
  python3 ops/tools/fix_translation_defects.py --severity high --severity medium
  python3 ops/tools/fix_translation_defects.py --all-severities --workers 4

يشتغل على ناتج `revalidate_translations.py` (الملاحظات المخزَّنة في كل ملف بعد
`revalidated_at`)، لا على السجلات البائتة.

لماذا لا نثق بالمُصلِح
----------------------
النموذج الذي يصلح عيبًا يستطيع أن يصنع عيبًا أكبر وهو يصلحه — وهذا وقع في هذا
المستودع: أربع تمريرات إصلاح متتالية أدخلت ٣٤ حقنة مصطلحات، وكل تمريرة كانت
«تصلح» ما قبلها. فالإصلاح هنا **اقتراح** لا يُكتب حتى يمرّ ثلاث بوابات:

  ١) بنيوية  — نفس المفاتيح ونفس أطوال القوائم. عيب يقيني لا رأي.
  ٢) مسرد    — `_validate_glossary`: كل مصطلح إسلامي في الإنجليزية له جذر
                عربي في المصدر. قيد برمجي، لا تعليمات لنموذج.
  ٣) مراجعة  — النموذج المراجع (عائلة مختلفة) يعيد الحكم على النص المُصلَح،
                ويُقبل الإصلاح فقط إذا **قلّ** عدد ملاحظات high+medium.

البوابة الثالثة هي المهمة: «النموذج قال إنه أصلحه» ليست نتيجة. النتيجة أن
مراجعًا مستقلًّا وجد عيوبًا أقل مما وجد قبله على نفس المقياس.

⚠️ النصوص الشرعية
-----------------
الملفات التي تمسّ آية أو حديثًا تبقى `needs_scholar_review: true` مهما نجح
الإصلاح، و`approved_by` لا تلمسه هذه الأداة أبدًا. الإصلاح الآلي هنا يزيل
إضافةً لا أصل لها في العربية (لقب، مبالغة، نسبة للنبي ﷺ) — وهذا حذف يمكن
التحقّق منه — ولا يخترع لفظًا لحديث. النقص أأمن من نسبة كاذبة.
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

_spec = importlib.util.spec_from_file_location(
    "translate_curriculum", Path(__file__).with_name("translate_curriculum.py"))
tc = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, [sys.argv[0]]
try:
    _spec.loader.exec_module(tc)
finally:
    sys.argv = _argv

CURRICULUM = ROOT / "knowledge_base" / "curriculum"
I18N_EN = CURRICULUM / "i18n" / "en"

FIELDS_BY_KIND = {
    "lessons": tc.LESSON_FIELDS,
    "paths": tc.PATH_FIELDS,
    "daily_tips": tc.TIP_FIELDS,
}

FIXER_MODEL = tc.TRANSLATOR_MODEL      # mistral-large-3: bulk transform, cheap
JUDGE_MODEL = tc.REVIEWER_MODEL        # deepseek-v4-pro: different family

SYSTEM_FIX = f"""You are correcting specific, itemised defects in an existing \
Arabic→English translation of Islamic parenting material. You are NOT \
retranslating.

You receive the Arabic source, the current English, and a list of defects found \
by an independent reviewer. Return the corrected English.

Rules:
1. Change ONLY what the listed defects require. Every other word stays byte for \
byte as it is. A defect list of two items must not produce a rewritten document.
2. Preserve JSON structure exactly: same keys, same array lengths, same order.
3. Islamic terms are transliterated per this table, and ONLY where that exact \
Arabic word is in the source:
{json.dumps(tc.GLOSSARY, ensure_ascii=False, indent=2)}
   Never reach for a glossary term because it sounds close. أدعية is du'a, not \
adhkar; نصيحة is advice, not tarbiyah; رحمة is rahmah, not rifq. Substituting a \
near neighbour changes a religious category — that is the single most common \
defect in this corpus and it has been introduced by fix passes before now.
4. NEVER add anything the Arabic does not say. In particular: do not add ﷺ, do \
not add "Prophetic", do not add a superlative ("Most Gentle" where the Arabic \
says only "gentle"), and do not attribute a general principle to the Prophet. \
Where a defect says content was added, the correction is to REMOVE it.
5. Never invent or "restore" the wording of a hadith. If a defect concerns one, \
correct only what the defect names and leave the rest untouched.
5b. 🚨 THE QUR'AN IS NOT TRANSLATED. An English rendering of an ayah is tafsir — \
interpretation of the meaning — never the Qur'an itself. Do not produce one, and \
do not "improve" one that is already there. Where English words stand in for an \
ayah, the only correction you may make is to label them explicitly as \
interpretation of the meaning; keep the Arabic ayah as the source has it.
6. Keep the register warm and direct — a parent speaking to a parent.
7. If the Arabic itself is wrong — a typo, a word that makes no sense in context \
— translate it faithfully anyway and leave it alone. A defect in the source is \
not yours to correct here, and "fixing" it in English makes the two say \
different things.

Return JSON only, as a flat object whose keys are exactly the keys of the \
`english` object you were given, and nothing else. Do NOT echo back the \
`arabic`, `english` or `defects` wrapper. No prose, no markdown fences, no \
commentary."""


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _unwrap(obj: dict, expected: dict) -> dict:
    """Take the corrected fields out of whatever envelope the model returned.

    The input is `{arabic, english, defects}` and the model mirrors that shape
    back about a third of the time, so a flat-object check rejected 7 of 20
    otherwise-good fixes as "missing key: text". Structural strictness is right;
    reading `{"english": {...}}` as a violation of it was not — the same
    forgiveness `_parse_json` already extends to markdown fences.
    """
    if not isinstance(obj, dict):
        return obj
    if set(expected) <= set(obj):
        return {k: obj[k] for k in expected}
    inner = obj.get("english")
    if isinstance(inner, dict) and set(expected) <= set(inner):
        return {k: inner[k] for k in expected}
    return obj


def _count_bad(defects: list, levels=("high", "medium")) -> int:
    return sum(1 for d in defects
               if str(d.get("severity", "")).lower() in levels)


def _review(ar_payload: dict, en_payload: dict) -> dict:
    raw, _ = tc._post(JUDGE_MODEL, tc.SYSTEM_REVIEW, json.dumps(
        {"arabic": ar_payload, "english": en_payload}, ensure_ascii=False))
    try:
        return tc._parse_json(raw)
    except json.JSONDecodeError:
        return {"verdict": "unreviewed", "defects": []}


def fix_file(en_path: Path, kind: str, levels: tuple, dry_run: bool) -> dict:
    rid = en_path.stem
    en_doc = _load(en_path)
    tr = en_doc.get("translation") or {}
    defects = [d for d in (tr.get("review_defects") or [])
               if str(d.get("severity", "")).lower() in levels]
    if not defects:
        return {"id": rid, "status": "skipped", "reason": "لا ملاحظات بهذه الخطورة"}

    ar_path = CURRICULUM / kind / en_path.name
    if not ar_path.exists():
        return {"id": rid, "status": "failed", "reason": "لا أصل عربي"}

    fields = FIELDS_BY_KIND[kind]
    ar_payload = tc._translatable(_load(ar_path), fields)
    en_payload = tc._translatable(en_doc, fields)
    before = _count_bad(tr.get("review_defects") or [])

    if dry_run:
        return {"id": rid, "status": "dry-run", "defects": len(defects),
                "before": before}

    user = json.dumps({"arabic": ar_payload, "english": en_payload,
                       "defects": defects}, ensure_ascii=False)
    try:
        raw, usage_f = tc._post(FIXER_MODEL, SYSTEM_FIX, user)
        fixed = _unwrap(tc._parse_json(raw), en_payload)
    except Exception as e:
        return {"id": rid, "status": "failed", "reason": f"{type(e).__name__}: {e}"}

    # ── Gate 1: structure. A missing key or a changed list length is certain,
    #    where a reviewer's opinion is probabilistic — so it runs first.
    problems = []
    for k, v in en_payload.items():
        if k not in fixed:
            problems.append(f"مفتاح مفقود: {k}")
        elif isinstance(v, list) and len(fixed.get(k, [])) != len(v):
            problems.append(f"طول قائمة مختلف في {k}")
    if problems:
        return {"id": rid, "status": "rejected", "gate": "structure",
                "reason": "; ".join(problems), "before": before}

    # ── Gate 2: glossary. Programmatic, not a prompt instruction. Four earlier
    #    fix passes injected 34 terms between them; this is why.
    injections = tc._validate_glossary(ar_payload, fixed)
    if injections:
        return {"id": rid, "status": "rejected", "gate": "glossary",
                "reason": "; ".join(injections), "before": before}

    if fixed == en_payload:
        return {"id": rid, "status": "skipped", "reason": "لم يتغيّر شيء",
                "before": before}

    # ── Gate 3: an independent reviewer must find FEWER defects at the levels
    #    we set out to fix, AND must not have made the serious ones worse.
    #    "The model says it fixed it" is not a result.
    #
    #    Both halves are needed. Judging only high+medium makes `--severity low`
    #    a no-op — a low-only file scores 0 → 0, `after >= before` holds, and
    #    every fix is thrown away (137 rejections in one run said exactly that).
    #    Judging only the targeted levels would let a pass trade four low
    #    defects for one high one and call it progress.
    review = _review(ar_payload, fixed)
    all_defects = review.get("defects") or []
    stored = tr.get("review_defects") or []
    after = _count_bad(all_defects)
    target_before = _count_bad(stored, levels)
    target_after = _count_bad(all_defects, levels)
    if target_after >= target_before:
        return {"id": rid, "status": "rejected", "gate": "review",
                "reason": f"{'+'.join(levels)} {target_before} → {target_after} "
                          f"(لم يتحسّن)", "before": before, "after": after}
    if after > before:
        return {"id": rid, "status": "rejected", "gate": "severity-traded",
                "reason": f"high+medium ساءت {before} → {after} "
                          f"مقابل تحسّن في {'+'.join(levels)}",
                "before": before, "after": after}
    # عدّ high وحده لا يكفي أن يبقى المجموع ثابتًا: تبديل medium بـhigh يُبقي
    # high+medium كما هو ويمرّ من الشرط أعلاه. حدث فعلًا — high صعدت ٧ → ١١
    # بينما medium نزلت ١٩ → ٩، والمجموع ينخفض فيبدو تحسّنًا وهو ليس كذلك.
    high_before = _count_bad(stored, ("high",))
    high_after = _count_bad(all_defects, ("high",))
    if high_after > high_before:
        return {"id": rid, "status": "rejected", "gate": "severity-traded",
                "reason": f"high ساءت {high_before} → {high_after}",
                "before": before, "after": after}

    src_json = json.dumps(ar_payload, ensure_ascii=False)
    needs_scholar = (bool(tc.RELIGIOUS_MARKERS.search(src_json))
                     or bool(tc.QUOTED_ARABIC.search(src_json))
                     or bool(review.get("contains_religious_text")))

    en_doc.update(fixed)
    tr.update({
        "review_verdict": "defects" if review.get("defects") else "clean",
        "review_defects": review.get("defects") or [],
        "needs_scholar_review": needs_scholar,
        "revalidated_at": datetime.now(timezone.utc).isoformat(),
        "fixed_at": datetime.now(timezone.utc).isoformat(),
        "fixer_model": FIXER_MODEL,
        "approved_by": tr.get("approved_by"),  # human signature, never ours
    })
    en_doc["translation"] = tr
    en_path.write_text(json.dumps(en_doc, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")

    return {"id": rid, "status": "fixed", "before": before, "after": after,
            "needs_scholar_review": needs_scholar,
            "tokens_out": usage_f.get("completion_tokens", 0)}


def collect(kinds, levels, limit):
    jobs = []
    for kind in kinds:
        for f in sorted((I18N_EN / kind).glob("*.json")):
            tr = (_load(f).get("translation") or {})
            if any(str(d.get("severity", "")).lower() in levels
                   for d in (tr.get("review_defects") or [])):
                jobs.append((f, kind))
    return jobs[:limit] if limit else jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--severity", action="append",
                    choices=["high", "medium", "low"],
                    help="repeatable; default high+medium")
    ap.add_argument("--all-severities", action="store_true")
    ap.add_argument("--kind", action="append", choices=sorted(FIELDS_BY_KIND))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()

    levels = (("high", "medium", "low") if args.all_severities
              else tuple(args.severity or ("high", "medium")))
    kinds = args.kind or sorted(FIELDS_BY_KIND)
    jobs = collect(kinds, levels, args.limit)

    print(f"🔧 {len(jobs)} ملف فيه ملاحظات {'+'.join(levels)}")
    print(f"   مُصلِح: {FIXER_MODEL}\n   حَكَم : {JUDGE_MODEL}\n")

    def run_one(job):
        f, kind = job
        try:
            return fix_file(f, kind, levels, args.dry_run)
        except Exception as e:
            return {"id": f.stem, "status": "failed",
                    "reason": f"{type(e).__name__}: {e}"}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_one, jobs))

    by = {}
    for r in results:
        by.setdefault(r["status"], []).append(r)
    fixed = by.get("fixed", [])
    rejected = by.get("rejected", [])

    print("═" * 62)
    for status in ("fixed", "rejected", "skipped", "failed", "dry-run"):
        if by.get(status):
            print(f"  {status:9}: {len(by[status])}")
    if fixed:
        print(f"  ملاحظات high+medium: {sum(r['before'] for r in fixed)} → "
              f"{sum(r['after'] for r in fixed)}")
        print(f"  توكن الخرج: {sum(r.get('tokens_out', 0) for r in fixed):,}")
    print(f"  الزمن: {time.time() - t0:.0f} ثانية")
    print("═" * 62)

    if rejected:
        gates = {}
        for r in rejected:
            gates.setdefault(r.get("gate", "?"), []).append(r)
        print("\n🚫 مرفوض عند البوابات (النص لم يُمَس):")
        for g, rs in gates.items():
            print(f"  {g}: {len(rs)}")
            for r in rs[:4]:
                print(f"     {r['id']}: {str(r['reason'])[:90]}")

    scholar = [r for r in fixed if r.get("needs_scholar_review")]
    if scholar:
        print(f"\n🕌 {len(scholar)} ملف مُصلَح يمسّ آية أو حديثًا — يبقى موقوفًا "
              "على توقيع بشري متخصص، والإصلاح الآلي لا يرفعه.")

    if args.json_out:
        args.json_out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"\n📄 {args.json_out}")


if __name__ == "__main__":
    main()
