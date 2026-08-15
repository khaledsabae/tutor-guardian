#!/usr/bin/env python3
"""
فحص: تغطية فيديو المسارات تُقاس على المنهج لا على الخريطة
=========================================================

    python3 ops/tools/check_path_video_coverage.py
    python3 ops/tools/check_path_video_coverage.py --lang en --strict

لماذا هذا الفحص موجود
---------------------
يوم 2026-08-15 كان كل عدّاد في المستودع يقول **«الفيديو الإنجليزي ٣٩/٣٩ مكتمل»**،
وكان الرقم صحيحًا ومضلّلًا في آن: المنهج فيه **٤٠ مسارًا** والخريطة
`scratch/path_source_mapping_new.json` فيها **٣٩**. المسار
`path_2-3_aqeedah_first_name` لم يكن في الخريطة إطلاقًا — فلا يُولَّد له فيديو، ولا
يُحسب ناقصًا، لأن كل عدّاد كان يبدأ من الخريطة.

والقارئ الإنجليزي كان يرى فيديو `ar_eg` بلا أن يظهر ذلك في أي رقم.

**البسط والمقام من مصدرين مختلفين، وهذا هو الفحص كلّه**: المقام من
`knowledge_base/curriculum/paths/` — أي ما يراه المستخدم فعلًا — والبسط من القرص.
الخريطة تصير مُدخَلًا يُفحَص لا مرجعًا يُوثَق به.

وهو نفس نمط الـ٤٥ مدخلًا «الميتة» في `lesson_index.json`: عدّاد يقيس ما بين يديه
بدل ما وُعد به، فتختفي الفجوة في الفرق بينهما.

Exit: 0 مغطّى · 1 فجوات (مع --strict)
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATHS_DIR = ROOT / "knowledge_base" / "curriculum" / "paths"
MAPPING = ROOT / "scratch" / "path_source_mapping_new.json"

sys.path.insert(0, str(ROOT / "backend"))
from app.media_naming import path_video_rel, MIN_VIDEO_BYTES  # noqa: E402


def curriculum_paths() -> dict:
    """Every path the app can show — the denominator, from the curriculum."""
    out = {}
    for f in sorted(PATHS_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["id"]] = d.get("title", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en", "ar"])
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("  PATH VIDEO COVERAGE — يُقاس على المنهج لا على الخريطة")
    print("=" * 66)

    paths = curriculum_paths()
    mapped = {r["path_id"] for r in json.loads(MAPPING.read_text(encoding="utf-8"))}

    unmapped = sorted(set(paths) - mapped)
    orphan = sorted(mapped - set(paths))

    on_disk, missing = [], []
    for pid in sorted(paths):
        rel = path_video_rel(pid, args.lang)
        f = ROOT / rel
        (on_disk if f.is_file() and f.stat().st_size > MIN_VIDEO_BYTES
         else missing).append(pid)

    print(f"  مسارات المنهج            : {len(paths)}")
    print(f"  منها في خريطة المصادر    : {len(paths) - len(unmapped)}")
    print(f"  فيديو [{args.lang}] على القرص     : {len(on_disk)}/{len(paths)}")

    if unmapped:
        print(f"\n  🚨 {len(unmapped)} مسارًا خارج الخريطة — لا يُولَّد ولا يُحسب ناقصًا:")
        for pid in unmapped:
            print(f"     {pid}  ({paths[pid][:44]})")
    if orphan:
        print(f"\n  ⚠️ {len(orphan)} مدخلًا في الخريطة بلا مسار في المنهج:")
        for pid in orphan:
            print(f"     {pid}")
    if missing and not unmapped:
        print(f"\n  باقٍ للتوليد: {len(missing)}")
        for pid in missing[:10]:
            print(f"     {pid}")

    if unmapped or orphan:
        print("\n  الخريطة مُدخَل يُفحَص لا مرجع يُوثَق به: المقام من المنهج.")
        return 1 if args.strict else 0

    print("\n" + "=" * 66)
    print("  ✅ كل مسار في المنهج له مدخل في الخريطة")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
