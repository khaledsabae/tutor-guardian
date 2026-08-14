#!/usr/bin/env python3
"""
فحص: الإنفوجراف الإنجليزي مكتوب بالإنجليزية فعلًا
==================================================

    python3 ops/tools/check_infographic_language.py --lang en
    python3 ops/tools/check_infographic_language.py --lang en --strict

لماذا هذا الفحص موجود
---------------------
الإنفوجراف **نصّ متحوّل إلى بكسل**. لا الفهرس ولا اسم الملف ولا كود الخروج يعرف
ما إذا كان ما رُسم داخل الصورة إنجليزيًّا أم عربيًّا — الملف اسمه `_en` ويُقدَّم
للمستخدم الإنجليزي بصرف النظر.

وللمستودع سابقة مباشرة: `generate quiz` و`generate flashcards` **لا يقبلان
`--language` أصلًا**، فكانا يرجّعان إنجليزيًّا مهما كان البرومبت عربيًّا، ولم
يُكتشف ذلك إلا بقراءة الناتج (قيد 2026-08-14 في OPERATIONS_LOG). العكس هنا
احتمال قائم بنفس المنطق.

فبدل مراجعة ١٦٠ صورة بالعين بحثًا عن اللغة، يقرأ هذا الفحص النصّ من الصورة
(tesseract) ويحكم على **نسبة الحروف** لا على وجود كلمة:

  · لاتيني ≥ ٧٠٪ من الحروف  → إنجليزي
  · عربي  ≥ ٢٠٪ من الحروف  → مخالفة في ملف `_en`

⚠️ **حدّه:** يفحص **اللغة** لا **الصحّة**. صورة إنجليزية سليمة الرسم قد تحمل
معنًى مغلوطًا أو كلمة مشوّهة — وهذا وقع فعلًا في النسخة العربية:
`64_lesson_16-18_medical_adult_transition_b04` رسم «مش» في «روتين يومي مش
مثالي» كتجمّع حروف مكسور، فبدت اللوحة مطابقة للوحة المضادّة لها. الحكم على
المعنى مراجعة بشرية، وهذا الفحص يوفّر عليها البحث عن اللغة فقط.

Exit: 0 سليم · 1 مخالفات · 2 تعطّل الفحص (tesseract غائب / self-test فشل)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INFO_DIR = ROOT / "docs" / "lesson_assets" / "infographics"

ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")

MIN_LATIN_SHARE = 0.70
MAX_ARABIC_SHARE = 0.20
# Below this many letters OCR read nothing usable — report, never pass silently.
MIN_LETTERS = 40


def ocr(path: Path, langs: str = "eng+ara") -> str:
    try:
        out = subprocess.run(
            ["tesseract", str(path), "stdout", "-l", langs],
            capture_output=True, text=True, timeout=120,
        )
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def shares(text: str) -> tuple:
    ar = len(ARABIC.findall(text))
    la = len(LATIN.findall(text))
    total = ar + la
    if total == 0:
        return 0.0, 0.0, 0
    return la / total, ar / total, total


def verdict(text: str, want: str) -> tuple:
    """('ok'|'wrong-language'|'unreadable', latin_share, arabic_share, letters)"""
    la, ar, n = shares(text)
    if n < MIN_LETTERS:
        return "unreadable", la, ar, n
    if want == "en":
        if la >= MIN_LATIN_SHARE and ar <= MAX_ARABIC_SHARE:
            return "ok", la, ar, n
        return "wrong-language", la, ar, n
    if ar >= 0.5:
        return "ok", la, ar, n
    return "wrong-language", la, ar, n


def _self_test() -> bool:
    """A checker that cannot fail is not a check."""
    cases = [
        ("Screen time for toddlers: what the evidence says about sleep", "en", "ok"),
        ("تنظيم النوم والتعامل الصحي مع الشاشات للأطفال الصغار وأسرهم", "en", "wrong-language"),
        ("تنظيم النوم والتعامل الصحي مع الشاشات للأطفال الصغار وأسرهم", "ar", "ok"),
        ("Screen time for toddlers: what the evidence says about sleep", "ar", "wrong-language"),
        ("abc", "en", "unreadable"),
    ]
    ok = True
    for text, want, expect in cases:
        got = verdict(text, want)[0]
        if got != expect:
            print(f"  ❌ self-test: {want!r} on {text[:34]!r} → {got}, expected {expect}")
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en", "ar"])
    ap.add_argument("--strict", action="store_true", help="exit 1 on any violation")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    print("=" * 66)
    print("  INFOGRAPHIC LANGUAGE CHECK — الإنفوجراف مكتوب باللغة المطلوبة؟")
    print("=" * 66)

    if not _self_test():
        print("\n  ⛔ self-tests فشلت — الفحص لاغٍ.")
        return 2
    print(f"  self-tests: 5/5 ✓")

    try:
        subprocess.run(["tesseract", "--version"], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        print("  ⛔ tesseract غير مثبَّت — لا يمكن قراءة النص من الصور.")
        return 2

    tag = "" if args.lang == "ar" else f"_{args.lang}"
    files = sorted(INFO_DIR.glob(f"*_infographic_*{tag}.png"))
    if args.lang == "ar":
        files = [f for f in files if not re.search(r"_(en|fr)\.png$", f.name)]
    if args.limit:
        files = files[:args.limit]

    print(f"  ملفات [{args.lang}]: {len(files)}\n")
    if not files:
        print("  (لا شيء لفحصه)")
        return 0

    bad, unreadable, good = [], [], 0
    for f in files:
        state, la, ar, n = verdict(ocr(f), args.lang)
        if state == "ok":
            good += 1
        elif state == "unreadable":
            unreadable.append((f.name, n))
        else:
            bad.append((f.name, la, ar))

    print(f"  ✅ باللغة الصحيحة : {good}")
    print(f"  ❌ لغة خاطئة      : {len(bad)}")
    print(f"  ⚠️  تعذّرت قراءتها : {len(unreadable)}")

    for name, la, ar in bad[:12]:
        print(f"     [wrong] {name}  latin={la:.0%} arabic={ar:.0%}")
    for name, n in unreadable[:6]:
        print(f"     [unreadable] {name}  ({n} letters read)")

    print("\n  ℹ️ يفحص اللغة لا المعنى. كلمة مشوّهة داخل صورة سليمة اللغة تمرّ من"
          "\n     هنا — تلك مراجعة بشرية.")
    return 1 if (args.strict and (bad or unreadable)) else 0


if __name__ == "__main__":
    sys.exit(main())
