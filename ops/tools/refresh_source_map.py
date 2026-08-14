#!/usr/bin/env python3
"""
إعادة بناء source_to_lesson.json من الحالة الحيّة للدفتر
=========================================================

    python3 ops/tools/refresh_source_map.py --dry-run
    python3 ops/tools/refresh_source_map.py --write

لماذا هذه الأداة موجودة
-----------------------
`Error: Audio generation is unavailable` ليست عطلًا في الصوت. هذه هي الرسالة
التي يرجّعها NotebookLM حين يشير `-s` إلى **مصدر لم يعد موجودًا على الدفتر**:
الخادم يقبل `CREATE_ARTIFACT`، يرجّع 200 بجسم `null`، فلا يُنشأ صفّ مهمة،
والمكتبة تترجم ذلك إلى اسم الميزة لا إلى سبب العطل.

مقيس يوم 2026-08-14 على دفتر «المربي»: **٧٤ من ١٦٩ معرّفًا في هذا الملف بائت**،
و**أول مدخل فيه واحد منها** — فكل تشخيص بدأ من أعلى الملف خرج بالنتيجة نفسها
الخاطئة: «الصوت متوقف». الإثبات في نفس الدقيقة وعلى نفس الدفتر:

    -s 3b1bc4d0 (بائت) → Audio generation is unavailable
    -s 3f7ba915 (حيّ)  → Started: 3f49cd9e…   exit 0

والفيديو كان يعمل طوال الوقت لأنه يقرأ من `path_source_mapping_new.json`
و٣٩/٣٩ فيه صالحة — لا لأن الفيديو ميزة أصحّ.

كيف تُطابَق المصادر
-------------------
المصادر تُرفع بعنوان يساوي `lesson_id` (انظر `add_new_lesson_podcasts.py`:
`source add … --title <lesson_id>`)، فالعنوان هو المفتاح الوحيد المستقر عبر
إعادة الرفع. المعرّف ليس مستقرًّا — وهذا بالضبط ما كسر الملف.

⚠️ هذه الأداة **لا ترفع مصدرًا ولا تحذف شيئًا**. تُعيد كتابة خريطة فقط، ومعها
نسخة احتياطية. الدروس التي لا مصدر حيّ لها تخرج في تقرير لتُرفع بقرار بشري —
والدفتر عند ٢٩٩/٣٠٠ مصدرًا، فرفع جديد عليه لن يتّسع أصلًا.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = str(ROOT / "notebooklm_env" / "bin" / "notebooklm")
MAP_FILE = ROOT / "source_to_lesson.json"
NOTEBOOK_ID = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"


def live_sources(notebook: str) -> dict:
    """{source_id: title} for every source currently on the notebook."""
    out = subprocess.run(
        [CLI, "source", "list", "-n", notebook, "--json"],
        capture_output=True, text=True, timeout=180,
    )
    if out.returncode != 0:
        sys.exit(f"❌ source list فشل: {out.stderr[:200]}")
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError as e:
        sys.exit(f"❌ ناتج غير صالح: {e}")
    if isinstance(payload, dict) and payload.get("error"):
        sys.exit(f"❌ {payload.get('code')}: {str(payload.get('message'))[:160]}\n"
                 f"   جرّب: {CLI} login --browser-cookies chrome")
    items = payload if isinstance(payload, list) else payload.get("sources", [])
    return {s["id"]: str(s.get("title", "")).strip() for s in items if s.get("id")}


def _candidates(lesson_id: str, by_title: dict) -> list:
    """المصادر التي يُحتمل أنها هذا الدرس، مرتّبةً بقوّة المطابقة."""
    for key in (lesson_id, f"{lesson_id}.md", f"{lesson_id}.txt"):
        if key in by_title:
            return by_title[key]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notebook", default=NOTEBOOK_ID)
    ap.add_argument("--write", action="store_true", help="اكتب الملف فعليًا")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.write and not args.dry_run:
        ap.error("مرّر --dry-run أو --write")

    live = live_sources(args.notebook)
    by_title: dict[str, list] = {}
    for sid, title in live.items():
        by_title.setdefault(title, []).append(sid)

    mapping = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    kept, remapped, orphaned = {}, {}, []

    for sid, meta in mapping.items():
        lesson_id = meta[2] if isinstance(meta, list) and len(meta) >= 3 else None
        if sid in live:
            kept[sid] = meta
            continue
        cands = _candidates(lesson_id or "", by_title)
        if cands:
            remapped[cands[0]] = meta
        else:
            orphaned.append(lesson_id or sid)

    new_map = {**kept, **remapped}

    print("═" * 62)
    print(f"  مصادر حيّة على الدفتر : {len(live)}")
    print(f"  مدخلات الخريطة        : {len(mapping)}")
    print(f"    ✅ صالحة كما هي     : {len(kept)}")
    print(f"    🔧 أُعيد ربطها بالعنوان: {len(remapped)}")
    print(f"    ❌ بلا مصدر حيّ      : {len(orphaned)}")
    print(f"  الخريطة الجديدة       : {len(new_map)} درسًا قابلًا للتوليد")
    print("═" * 62)

    if orphaned:
        print(f"\n🚫 {len(orphaned)} درسًا لا مصدر له — يحتاج رفعًا بقرار بشري:")
        for lid in sorted(orphaned)[:12]:
            print(f"     {lid}")
        if len(orphaned) > 12:
            print(f"     … و{len(orphaned) - 12} غيرها")
        print(f"\n   ⚠️ الدفتر عند {len(live)}/300 مصدرًا — لا يتّسع لرفع جديد.")

    if args.dry_run:
        print("\n(dry-run — لم يُكتب شيء)")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = MAP_FILE.with_suffix(f".json.bak-{stamp}")
    backup.write_text(MAP_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    MAP_FILE.write_text(json.dumps(new_map, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n✅ كُتبت. نسخة احتياطية: {backup.name}")


if __name__ == "__main__":
    main()
