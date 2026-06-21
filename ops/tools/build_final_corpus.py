#!/usr/bin/env python3
"""
build_final_corpus — تنظيف + دمج + تقرير جودة للكوربوس النهائي.

يدمج الـpremium (DeepSeek، 25k) مع qa_dataset_clean (الأقدم) بعد تنظيف صارم
ثم إزالة التكرار، ويطبع تقرير جودة شامل.

التشغيل:
    python ops/tools/build_final_corpus.py \
        --premium ops/data/qa_dataset_premium_25k.jsonl \
        --clean   ops/data/qa_dataset_clean.jsonl \
        --out     ops/data/qa_dataset_final.jsonl
"""
import argparse
import collections
import json
import re
from pathlib import Path

# نطاقات CJK/اليابانية/الكورية — أي تلوّث = إسقاط السطر.
_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯　-〿]")
_MIN_OUTPUT = 50  # أقل طول مقبول للإجابة (حروف)


def _load(path: str) -> list[dict]:
    rows: list[dict] = []
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            rows.append({"__bad__": True})
    return rows


def _instr(r: dict) -> str:
    return (r.get("instruction") or r.get("question") or "").strip()


def _output(r: dict) -> str:
    return (r.get("output") or r.get("answer") or "").strip()


def _clean_rows(rows: list[dict], origin: str) -> tuple[list[dict], dict]:
    """صفِّ السطور حسب قواعد الجودة وأعِد (المقبولة، عدّاد الأسباب)."""
    kept: list[dict] = []
    drop = collections.Counter()
    for r in rows:
        if r.get("__bad__"):
            drop["malformed"] += 1
            continue
        instr, out = _instr(r), _output(r)
        if not instr or not out:
            drop["empty"] += 1
            continue
        if _CJK.search(instr) or _CJK.search(out):
            drop["cjk"] += 1
            continue
        if len(out) < _MIN_OUTPUT:
            drop["too_short"] += 1
            continue
        # سطر مُطبَّع بمصدر الأصل للتتبّع
        kept.append({
            "instruction": instr,
            "output": out,
            "domain": r.get("domain", ""),
            "age_group": r.get("age_group", ""),
            "behavior_type": r.get("behavior_type", ""),
            "reference": r.get("reference", ""),
            "unit_id": r.get("unit_id", ""),
            "kind": r.get("kind", ""),
            "_origin": origin,
        })
    return kept, dict(drop)


def _merge_dedup(*groups: list[dict]) -> tuple[list[dict], int, int]:
    """ادمج المجموعات (الأولوية للأولى) وأزل التكرار التام (instruction+output)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    exact_dups = 0
    for group in groups:
        for r in group:
            key = (r["instruction"], r["output"])
            if key in seen:
                exact_dups += 1
                continue
            seen.add(key)
            out.append(r)
    instr_overlap = len(out) - len({r["instruction"] for r in out})
    return out, exact_dups, instr_overlap


def _dist(rows: list[dict], field: str) -> dict:
    return dict(collections.Counter(r.get(field) or "?" for r in rows))


def _report(final: list[dict], stats: dict) -> None:
    lens = [len(r["output"]) for r in final]
    avg = sum(lens) // len(lens) if lens else 0
    print("\n" + "=" * 62)
    print("📊  تقرير الكوربوس النهائي — المربّي")
    print("=" * 62)
    for src, s in stats["sources"].items():
        print(f"\n• {src}: {s['raw']} خام → {s['kept']} مقبول")
        if s["drop"]:
            print(f"  أُسقط: {s['drop']}")
    print(f"\n🔗 الدمج: {stats['merged_in']} مقبول → "
          f"أُزيل {stats['exact_dups']} تكرار تام → "
          f"**{len(final)} نهائي**")
    print(f"   (تداخل أسئلة بإجابات مختلفة محفوظ: {stats['instr_overlap']})")
    print(f"\n✅ نقاء CJK: 0  |  متوسط طول الإجابة: {avg} حرف  |  "
          f"المدى: {min(lens)}–{max(lens)}")
    print(f"\nبالأصل:   {_dist(final, '_origin')}")
    print(f"بالمجال:  {_dist(final, 'domain')}")
    print(f"بالنوع:   {_dist(final, 'kind')}")
    print(f"بالعمر:   {_dist(final, 'age_group')}")
    print("=" * 62)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--premium", default="ops/data/qa_dataset_premium_25k.jsonl")
    ap.add_argument("--clean", default="ops/data/qa_dataset_clean.jsonl")
    ap.add_argument("--out", default="ops/data/qa_dataset_final.jsonl")
    args = ap.parse_args()

    prem_raw, clean_raw = _load(args.premium), _load(args.clean)
    prem, prem_drop = _clean_rows(prem_raw, "premium_deepseek")
    clean, clean_drop = _clean_rows(clean_raw, "clean_legacy")
    # الأولوية للـpremium (DeepSeek أحدث وأجود) عند التكرار التام
    final, exact_dups, instr_overlap = _merge_dedup(prem, clean)

    Path(args.out).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in final) + "\n",
        encoding="utf-8",
    )
    _report(final, {
        "sources": {
            "premium (DeepSeek)": {"raw": len(prem_raw), "kept": len(prem), "drop": prem_drop},
            "clean (legacy)": {"raw": len(clean_raw), "kept": len(clean), "drop": clean_drop},
        },
        "merged_in": len(prem) + len(clean),
        "exact_dups": exact_dups,
        "instr_overlap": instr_overlap,
    })
    print(f"\n💾 كُتب: {args.out}  ({len(final)} سطر)")


if __name__ == "__main__":
    main()
