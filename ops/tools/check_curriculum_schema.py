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

الوعود الصادقة (أُضيف 2026-10-04)
----------------------------------
مخطّطٌ سليم لا يمنع مسارًا من أن يَعِد بما لا يملك. أمٌّ فتحت مسارًا مكتوبًا عليه
«٢٨ يومًا» فوجدت أربعة دروس وأنهتها في جلسة واحدة. الرقم لم يكن مشتقًّا من شيء:
شاشة الترحيب تقول «مسارات من ٢٨ يومًا»، وأوصاف المسارات «لمدة ١٤ يومًا» بينما
الشارة ١٢، والدروس أربعة. لذلك يفحص `duration_problems()`:

  · `estimated_days` ≤ عدد الدروس — اليوم في المسار = بطاقة درس واحدة. لا شيء في
    التطبيق يمنع قراءة الدروس كلّها في جلسة، فأيّ رقمٍ أكبر وعدٌ بمحتوى غير موجود.
  · كل `lesson_id` في المسار له ملف درس منشور يشير إلى المسار نفسه.
  · المسار الإنجليزي يطابق العربي في `lesson_ids` و`estimated_days`: الترجمة
    تُطبَّق فوق العربي، فرقمٌ قديم في الإنجليزي كان يغطّي الرقم الصحيح.
  · العنوان والوصف (عربي وإنجليزي): «N يوم/أسبوع» لا يتجاوز ما تدعمه الدروس،
    و«N دروس» يساوي عددها.
  · نصوص التطبيق ومتجر Play التي تَعِد بـ«مسارات من N يومًا» لا تتجاوز أطول مسار.

Exit: 0 مطابق · 1 مخالفات
"""

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = ROOT / "knowledge_base" / "curriculum"
SCHEMA = CURRICULUM / "schema"

# نصوص خارج المنهج تَعِد بطول المسارات. الواجهة والمتجر هما أول ما يقرؤه الوالد.
PROMISE_SOURCES = (
    ROOT / "mobile" / "lib" / "l10n" / "app_ar.arb",
    ROOT / "mobile" / "lib" / "l10n" / "app_en.arb",
    ROOT / "docs" / "PLAY_STORE_LISTING.md",
)

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_NUM = r"([0-9٠-٩]+)"
# رقم ثم وحدة. «N-day» و«N days» و«N يومًا» و«N أيام» كلها وعد بطول.
_DAYS = re.compile(_NUM + r"\s*-?\s*(?:يوم|أيام|days?\b)", re.IGNORECASE)
_WEEKS = re.compile(_NUM + r"\s*-?\s*(?:أسبوع|أسابيع|weeks?\b)", re.IGNORECASE)
_LESSONS = re.compile(_NUM + r"\s*-?\s*(?:دروس|درس|lessons?\b)", re.IGNORECASE)
# سطر/نصّ يتكلّم عن المسارات — حتى لا تُحاسَب «سلسلة ٢٨ يومًا» في العادات بطول المسار.
_PATH_WORD = re.compile(r"مسار|\bpaths?\b|\btracks?\b", re.IGNORECASE)


def _n(s: str) -> int:
    return int(s.translate(_ARABIC_DIGITS))


def _text_promises(text: str, n_lessons: int) -> list[str]:
    """وعود الطول داخل عنوان/وصف مسار مقابل عدد دروسه."""
    out = []
    for m in _DAYS.finditer(text):
        if _n(m.group(1)) > n_lessons:
            out.append(f"«{m.group(0)}» والدروس {n_lessons}")
    for m in _WEEKS.finditer(text):
        if _n(m.group(1)) * 7 > n_lessons:
            out.append(f"«{m.group(0)}» والدروس {n_lessons}")
    for m in _LESSONS.finditer(text):
        if _n(m.group(1)) != n_lessons:
            out.append(f"«{m.group(0)}» والدروس {n_lessons}")
    return out


def duration_problems(paths_ar: dict, paths_en: dict, lessons: dict,
                      promise_texts: dict) -> list[tuple[str, str, str]]:
    """وعود الطول التي لا يملكها المحتوى. مدخلات نقيّة ليُختبَر بلا قرص.

    paths_ar/paths_en: {path_id: doc} · lessons: {lesson_id: doc} (العربي المنشور)
    promise_texts: {اسم_المصدر: نص} — ARB وقائمة المتجر.
    """
    problems = []
    for pid, p in sorted(paths_ar.items()):
        ids = p.get("lesson_ids") or []
        n = len(ids)
        days = p.get("estimated_days")
        if isinstance(days, int) and days > n:
            problems.append((f"paths/{pid}", "estimated_days",
                             f"{days} يومًا والدروس {n} — اليوم = درس واحد"))
        for lid in ids:
            lesson = lessons.get(lid)
            if lesson is None:
                problems.append((f"paths/{pid}", "lesson_ids",
                                 f"{lid} لا ملف درس منشور له"))
            elif lesson.get("path_id") != pid:
                problems.append((f"paths/{pid}", "lesson_ids",
                                 f"{lid} يشير إلى {lesson.get('path_id')}"))
        for field in ("title", "description"):
            for msg in _text_promises(p.get(field) or "", n):
                problems.append((f"paths/{pid}", field, msg))

        en = paths_en.get(pid)
        if en is None:
            continue
        for field in ("lesson_ids", "estimated_days"):
            if field in en and en[field] != p.get(field):
                problems.append((f"i18n/en/paths/{pid}", field,
                                 "يخالف العربي — الحقل بنيوي لا يُترجَم"))
        for field in ("title", "description"):
            for msg in _text_promises(en.get(field) or "", n):
                problems.append((f"i18n/en/paths/{pid}", field, msg))

    longest = max((p.get("estimated_days") or 0 for p in paths_ar.values()),
                  default=0)
    for source, text in sorted(promise_texts.items()):
        for line in text.splitlines():
            if not _PATH_WORD.search(line):
                continue
            for m in _DAYS.finditer(line):
                if _n(m.group(1)) > longest:
                    problems.append((source, "promise",
                                     f"«{m.group(0)}» وأطول مسار {longest} يومًا"))
    return problems


def _load_dir(tree: Path) -> dict:
    out = {}
    for f in sorted(tree.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # يُبلَّغ عنه في فحص المخطّط
        if d.get("id"):
            out[d["id"]] = d
    return out


def check_durations() -> list[tuple[str, str, str]]:
    paths_ar = {k: v for k, v in _load_dir(CURRICULUM / "paths").items()
                if v.get("is_published", True)}
    paths_en = _load_dir(CURRICULUM / "i18n" / "en" / "paths")
    lessons = {k: v for k, v in _load_dir(CURRICULUM / "lessons").items()
               if v.get("is_published", True)}
    texts = {}
    for src in PROMISE_SOURCES:
        if not src.exists():
            continue
        raw = src.read_text(encoding="utf-8")
        if src.suffix == ".arb":
            # القيم وحدها: المفاتيح والوصف (@key) ليست نصًّا يراه المستخدم.
            data = json.loads(raw)
            raw = "\n".join(v for k, v in data.items()
                            if not k.startswith("@") and isinstance(v, str))
        texts[str(src.relative_to(ROOT))] = raw
    return duration_problems(paths_ar, paths_en, lessons, texts)

# (مجلد المحتوى, اسم المخطّط)
#
# `agreements` و`missions` شُحنا في سبرنت ٢ خارج هذه القائمة — أي أن البنك
# الذي يقرّر ما يوقّعه طفل، والبنك الذي يقرّر ما يُطلب منه أن يفعله، كانا
# الوحيدَين بلا فحص مخطّط. أُدرجا مع `license` لا بعده.
KINDS = (
    ("lessons", "lesson"),
    ("paths", "path"),
    ("daily_tips", "daily_tip"),
    ("agreements", "agreement_clauses"),
    ("missions", "mission_bank"),
    ("license", "license_scenario"),
)

# برامج الأسرة: مجلد واحد وثلاثة مخطّطات، والمخطّط يُختار بحقل `program_type` لا
# باسم المجلد. ملفٌّ بنوعٍ لا مخطّط له يُرفض — لا يمرّ ملف برنامج بلا فحص لأن
# أحدًا نسي أن يسجّله هنا.
PROGRAM_SCHEMAS = {
    "ramadan_family": "program_ramadan_family",
    "prayer_journey": "program_prayer_journey",
    "milestones": "program_milestones",
}


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

    validators = {}
    for ptype, name in PROGRAM_SCHEMAS.items():
        schema_path = SCHEMA / f"{name}.schema.json"
        if not schema_path.exists():
            print(f"  ⛔ مخطّط مفقود: {schema_path.relative_to(ROOT)}")
            return 1
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators[ptype] = Draft202012Validator(schema)
    for tree in (CURRICULUM / "programs", CURRICULUM / "i18n" / "en" / "programs"):
        for f in sorted(tree.glob("*.json")):
            total += 1
            rel = str(f.relative_to(CURRICULUM))
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                problems.append((rel, "json", str(e)[:80]))
                continue
            ptype = doc.get("program_type") if isinstance(doc, dict) else None
            if ptype not in validators:
                problems.append((rel, "program_type", f"نوع برنامج بلا مخطّط: {ptype!r}"))
                continue
            for err in validators[ptype].iter_errors(doc):
                problems.append((rel, "/".join(map(str, err.path)) or "(root)", err.message[:100]))

    print(f"  ملفات مفحوصة (عربي + إنجليزي): {total}")

    durations = check_durations()
    print(f"  وعود الطول (مسار/متجر/واجهة) المخالفة للمحتوى: {len(durations)}")
    problems += durations

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
