#!/usr/bin/env python3
"""
فحص: ملفات المنهج تطابق مخطّطاتها — عربيها وإنجليزيها
======================================================

    python3 ops/tools/check_curriculum_schema.py

لماذا لم يكن هذا الفحص موجودًا
------------------------------
المخطّطات في `knowledge_base/curriculum/schema/` كانت تُكتب ثم يتطوّر المحتوى
بعيدًا عنها، ولا شيء يقارن الاثنين. النتيجة قياسها يوم 2026-08-15: **المخطّط
يرفض بياناته هو** في ستّة مواضع دفعة واحدة —

  · `age_group` enum فيه «حتى عام» ولا فيه `0-3` ولا `2-3`، وهما ما تستعمله كل
    الملفات فعلًا
  · `domain` بلا `aqeedah` (٤١ ملفًا)
  · `needs_professional_followup` في ١٢٣ درسًا وغير معرَّف أصلًا
  · `estimated_minutes` سقفه ١٥ والبيانات تصل ٤٩
  · `unit_ids` يشترط عنصرًا واحدًا و٦٢ درسًا بلا وحدات
  · `warning_flags` enum بثلاث قيم مقابل نحو **ثمانين** تحذيرًا حرًّا في البيانات

ومخطّطٌ يرفض ما يصفه لا يصلح بوابةً أبدًا: لا يمكن تشغيله، فلا يُشغَّل، فينحرف
أكثر. أُصلح ليصف الواقع — وهذا الفحص يمنعه من الانحراف ثانيةً.

وأول تشغيلة له بعد الإصلاح أمسكت عيبًا في البيانات لا في المخطّط: ثلاث نصائح
بـ`day_of_week = 7` بينما الأيام ٠..٦. الحقل لا يقرؤه شيء اليوم، لكنه معرَّف في
موديل التطبيق بـ`0..6 (Mon..Sun)`، فأي ترشيح مستقبلي كان سيُسقط الثلاث بصمت.

Exit: 0 مطابق · 1 مخالفات
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = ROOT / "knowledge_base" / "curriculum"
SCHEMA = CURRICULUM / "schema"

# (مجلد المحتوى, اسم المخطّط)
KINDS = (("lessons", "lesson"), ("paths", "path"), ("daily_tips", "daily_tip"))


def main() -> int:
    print("=" * 66)
    print("  CURRICULUM SCHEMA CHECK — المنهج يطابق مخطّطه؟")
    print("=" * 66)

    total = 0
    problems: list[tuple[str, str, str]] = []
    for sub, name in KINDS:
        schema_path = SCHEMA / f"{name}.schema.json"
        if not schema_path.exists():
            print(f"  ⛔ مخطّط مفقود: {schema_path.relative_to(ROOT)}")
            return 1
        validator = Draft202012Validator(
            json.loads(schema_path.read_text(encoding="utf-8")))
        # الترجمات تُفحص مثل المصدر: ملف إنجليزي يخالف المخطّط يصل المستخدم
        # تمامًا كما يصل العربي.
        for tree in (CURRICULUM / sub, CURRICULUM / "i18n" / "en" / sub):
            for f in sorted(tree.glob("*.json")):
                total += 1
                try:
                    doc = json.loads(f.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    problems.append((str(f.relative_to(CURRICULUM)), "json", str(e)[:80]))
                    continue
                for err in validator.iter_errors(doc):
                    problems.append((
                        str(f.relative_to(CURRICULUM)),
                        "/".join(map(str, err.path)) or "(root)",
                        err.message[:100],
                    ))

    print(f"  ملفات مفحوصة (عربي + إنجليزي): {total}")

    if problems:
        print(f"\n  ❌ {len(problems)} مخالفة:\n")
        for path, where, msg in problems[:25]:
            print(f"     {path} · {where}")
            print(f"        {msg}")
        if len(problems) > 25:
            print(f"     … و{len(problems) - 25} غيرها")
        print("\n  إن كان المخطّط هو المتخلّف عن المحتوى فصحّح المخطّط، لا البيانات —")
        print("  لكن تحقّق أوّلًا: أول تشغيلة بعد مواءمته أمسكت عيبًا في البيانات.")
        return 1

    print("\n" + "=" * 66)
    print("  ✅ CURRICULUM SCHEMA OK — لا انحراف بين المخطّط والمحتوى")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
