#!/usr/bin/env python3
"""
ترجمة قاعدة المعرفة إلى الإنجليزية — وحدات جديدة، لا استبدال
=============================================================

    export OLLAMA_API_KEY=…                       # من ~/projects/email-twin/.env
    python3 ops/tools/translate_knowledge_base.py --limit 5      # جرّب أولًا
    python3 ops/tools/translate_knowledge_base.py --all

لماذا هذه الأداة
----------------
الاسترجاع فيه **٤١ وحدة إنجليزية من ٨٦٤** (٤٫٧٪). مقيس على مسبار من عشرة أسئلة:
السؤال العربي يرجع بـ٥٠–١٠٠٪ محتوى بلغته، والإنجليزي بـ**٠–٢٥٪**. وترتيب اللغة
الذي نزل في `49b14e9` لا يصلح ذلك ولا يمكنه: **لا إشارة ترتيب تخلق محتوًى غير
موجود.** ٢٧٪ من المستخدمين على أجهزة إنجليزية، وهذا هو الشغل الذي يخدمهم فعلًا.

**كل شيء هنا مستورَد من `translate_curriculum.py`، ولا سطر منه مُعاد كتابته.**
ذلك الملف يكوّد إخفاقات وقعت: `GLOSSARY_ROOTS` أُضيف بعد ٣٤ حقنة مصطلح حقيقية،
وبوابة الشرع تجمع ثلاث إشارات باتحاد لا بتقاطع، والمراجع من **عائلة نموذج مختلفة**
لأن النموذج يوافق على نفسه. إعادة كتابة أيٍّ من ذلك هنا تعني إعادة اكتشافه بالثمن.

قراران يخصّان قاعدة المعرفة تحديدًا
-----------------------------------
**١. الوحدة المترجمة وحدة جديدة، لا نسخة تحلّ محلّ الأصل.** معرّفها `<id>__en`
وملفها منفصل، فالعربية تبقى كما هي في الفهرس. الاستبدال كان سيخسر القارئَ العربي
مصدرَه لخدمة الإنجليزي — وهو نفس الخطأ الذي عولج في `_pick` هذا اليوم.

**٢. النصوص المؤسسية لا تُترجَم افتراضيًا.** من ٨٣٥ وحدة عربية، **٢٢٠ مستوردة
بالجملة** من `ITU_COP_Industry_Guidelines` و`WHO_Child_Adolescent_Mental_Health_
Policy` وأخواتها: إرشادات امتثال موجَّهة لشركات الاتصالات، ونصّ سياسات صحية عن
التنسيق بين القطاعات. هي اليوم تزاحم سؤال الأم لأنها `unspecified` فمؤهَّلة في كل
عمر — وسؤال «كيف أتعامل مع نوبات الغضب؟» يعود بوحدات عن اكتئاب الكبار من
`NIMH_Depression.pdf` لأنها تذكر الغضب.

فترجمتها **إنفاق على جعل الاسترجاع الإنجليزي أسوأ**: تضاعف الزحام بلغةٍ لا يملك
قارئها بديلًا. `--include-institutional` يشغّلها لمن أراد، والقرار مسجَّل هنا لا
مخبوء في مرشّح.

Exit: 0 تمّ · 1 فشل مانع
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops" / "tools"))

from translate_curriculum import (  # noqa: E402
    _post, _parse_json, _validate_glossary, SYSTEM_TRANSLATE, SYSTEM_REVIEW,
    RELIGIOUS_MARKERS, QUOTED_ARABIC, TRANSLATOR_MODEL, REVIEWER_MODEL,
)

UNITS = ROOT / "knowledge_base" / "units"
STATE = ROOT / "ops" / "data" / "kb_translation_state.json"

# ما يُترجَم. `text_original` مُستثنى عمدًا: هو النصّ المصدري كما ورد، وقيمته أنه
# غير محرَّر — ترجمته تنتج "أصلًا" ليس أصلًا. و`source_file`/`source_url` إسناد.
FIELDS = ("title", "text_simplified", "keywords")

# بصمات الاستيراد بالجملة — انظر القرار ٢ أعلاه.
INSTITUTIONAL = ("ITU_", "WHO_", "UNICEF_", "OECD_", "_Policy", "_Guidelines",
                 "_Industry", "NIMH_")


def is_institutional(unit: dict) -> bool:
    src = str(unit.get("source_file") or "")
    return any(m in src for m in INSTITUTIONAL)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")


def arabic_units(include_institutional: bool) -> list:
    """Arabic units with no English sibling yet."""
    out = []
    for f in sorted(UNITS.glob("*.json")):
        if f.stem.endswith("__en"):
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(doc, dict) or doc.get("language") != "ar":
            continue
        if not include_institutional and is_institutional(doc):
            continue
        if (UNITS / f"{f.stem}__en.json").exists():
            continue
        out.append((f, doc))
    return out


def translate_unit(src: Path, doc: dict) -> dict:
    uid = doc.get("id", src.stem)
    payload = {k: doc[k] for k in FIELDS if doc.get(k)}
    if not payload:
        return {"id": uid, "status": "skipped", "reason": "no translatable fields"}

    src_json = json.dumps(payload, ensure_ascii=False)
    raw, usage_t = _post(TRANSLATOR_MODEL, SYSTEM_TRANSLATE, src_json)
    try:
        translated = _parse_json(raw)
    except json.JSONDecodeError as e:
        return {"id": uid, "status": "failed", "reason": f"bad JSON: {e}"}

    # Structural check before any judgement of quality: a missing key or a
    # changed list length is a certain defect, while a reviewer's opinion is
    # probabilistic. Same order as translate_curriculum, for the same reason.
    for k, v in payload.items():
        if k not in translated:
            return {"id": uid, "status": "failed", "reason": f"missing key: {k}"}
        if isinstance(v, list) and len(translated.get(k, [])) != len(v):
            return {"id": uid, "status": "failed",
                    "reason": f"list length changed in {k}"}

    issues = _validate_glossary(payload, translated)
    if issues:
        return {"id": uid, "status": "failed",
                "reason": "term injection: " + "; ".join(issues)}

    review_input = json.dumps({"arabic": payload, "english": translated},
                              ensure_ascii=False)
    raw_r, usage_r = _post(REVIEWER_MODEL, SYSTEM_REVIEW, review_input)
    try:
        review = _parse_json(raw_r)
    except json.JSONDecodeError:
        review = {"verdict": "unreviewed", "defects": []}

    needs_scholar = bool(
        RELIGIOUS_MARKERS.search(src_json) or QUOTED_ARABIC.search(src_json)
        or review.get("contains_religious_text"))

    out = dict(doc)
    out.update(translated)
    out["id"] = f"{uid}__en"
    out["language"] = "en"
    out["source_language"] = "ar"
    out["translated_from"] = uid
    out["translation"] = {
        "translator_model": TRANSLATOR_MODEL,
        "reviewer_model": REVIEWER_MODEL,
        "needs_scholar_review": needs_scholar,
        "review_verdict": review.get("verdict", "unreviewed"),
        "review_defects": review.get("defects", []),
        "approved_by": None,
    }
    (UNITS / f"{src.stem}__en.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "id": uid, "status": "translated",
        "needs_scholar_review": needs_scholar,
        "verdict": review.get("verdict", "unreviewed"),
        "defects": len(review.get("defects", [])),
        "tokens": (usage_t.get("completion_tokens", 0)
                   + usage_r.get("completion_tokens", 0)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--include-institutional", action="store_true",
                    help="also translate ITU/WHO bulk imports — read the "
                         "module docstring before using this")
    args = ap.parse_args()

    if not os.environ.get("OLLAMA_API_KEY"):
        print("❌ OLLAMA_API_KEY not set")
        return 1

    pending = arabic_units(args.include_institutional)
    print("=" * 66)
    print("  KNOWLEDGE BASE TRANSLATION — ar → en")
    print("=" * 66)
    print(f"  pending: {len(pending)}"
          f"{'' if args.include_institutional else '  (institutional excluded)'}")
    if not (args.all or args.limit):
        print("  pass --limit N or --all")
        return 0

    todo = pending[: args.limit] if args.limit else pending
    state = load_state()
    done = failed = flagged = 0

    for i, (f, doc) in enumerate(todo, 1):
        r = translate_unit(f, doc)
        state[r["id"]] = r
        if r["status"] == "translated":
            done += 1
            flagged += bool(r.get("needs_scholar_review"))
        elif r["status"] == "failed":
            failed += 1
            print(f"  ❌ {r['id'][:36]}  {r['reason'][:60]}")
        if i % 10 == 0:
            save_state(state)
            print(f"  … {i}/{len(todo)}  ok={done} failed={failed}")

    save_state(state)
    print(f"\n  translated: {done}   failed: {failed}   "
          f"needs scholar review: {flagged}")
    print("\n  🚨 الوحدات الجديدة تدخل الفهرس عند الإقلاع القادم — و`_fingerprint`"
          "\n     يتغيّر فيُعاد التضمين مرة واحدة. تكلفة إقلاع لا تكلفة طلب.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
