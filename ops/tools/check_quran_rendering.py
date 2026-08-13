#!/usr/bin/env python3
"""
فحص: القرآن لا يُترجَم — وأي معنًى بالإنجليزية يُعلَن أنه تفسير
================================================================

القاعدة الشرعية التي يفرضها هذا الفحص:

  **القرآن لا يُترجَم.** ما يُكتب بالإنجليزية مقابلَ آيةٍ هو *تفسير لمعناها*
  لا القرآن، وتقديمه على أنه القرآن خطأ شرعي لا خيار أسلوبي. فإن أردنا
  الإنجليزية جاء **التفسير** مع **التصريح بأنه تفسير**.

فما الذي يفحصه هذا الملف فعليًا
-------------------------------
لا يستطيع فحصٌ آليٌّ أن يحكم على أمانة تفسير. يستطيع — وهذا كل ما يدّعيه —
أن يمسك الشكل الذي **يُقدِّم إنجليزيةً على أنها قرآن**:

  ١) نصٌّ إنجليزي بين علامتَي اقتباس يسبقه ما يَنسبه إلى الله تعالى
     («Allah says: "…"» و«Allah Almighty said: "…"» ونحوهما)، بلا لفظ يدل
     على أنه تفسير.
  ٢) نصٌّ إنجليزي داخل قوسَي الآية ﴿﴾ — القوسان علامة الرسم القرآني، ولا
     يصحّ أن يقعا حول إنجليزية أصلًا.
  ٣) عنصر بيانات نوعه `verse` وفيه نصّ إنجليزي بلا حقل `provenance` يسمّي
     ترجمةً منشورة معتمدة ولا وسمٍ يقول إنه تفسير.

والمخرج الصحيح المقبول:

    "interpretation of the meaning: ..."   ·   "(interpretation of the meaning)"
    "meaning of the verse: ..."            ·   provenance: saheeh_international

⚠️ **حدّ هذا الفحص:** يمسك الشكل لا الأمانة. تفسيرٌ مُعلَنٌ لكنه محرَّف يمرّ من
هنا — تلك مسؤولية مراجعٍ مؤهَّل، وهذا الفحص لا يدّعي أنه يغني عنها.

Exit: 0 سليم · 1 مخالفات · 2 تعطّل الفحص نفسه (self-tests)
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# مواضع المحتوى الإنجليزي التي يسري عليها الفحص. تُوسَّع مع كل طبقة تُترجَم.
EN_CONTENT_GLOBS = (
    "knowledge_base/curriculum/i18n/en/**/*.json",
    "mobile/assets/content/**/*.en.json",   # طبقة الألعاب/الأذكار (المرحلة ٤)
)

# ما يجعل نصًّا إنجليزيًّا «معلَنًا أنه تفسير».
DISCLOSED = re.compile(
    r"interpretation of the meaning|meaning of the verse|approximate meaning|"
    r"tafsir|tafseer|interpretation of meaning",
    re.IGNORECASE,
)

# نسبةُ قولٍ إلى الله تعالى يتبعها اقتباس إنجليزي.
ATTRIBUTED = re.compile(
    r"(?:Allah|God)(?:\s+(?:the\s+)?(?:Almighty|Most\s+High|Exalted|ta'ala|Ta'ala))?"
    r"\s+(?:says?|said|tells?|told|declares?|stated)\s*[:،,]?\s*[\"“«]([^\"”»]{15,})",
    re.IGNORECASE,
)

# قوسا الآية حول حروف لاتينية.
IN_AYAH_BRACES = re.compile(r"﴿[^﴾]*[A-Za-z]{4,}[^﴾]*﴾")

LATIN_RUN = re.compile(r"[A-Za-z]{3,}")


def _texts(obj, path="") -> list:
    """كل نصّ في الوثيقة مع مساره، ما عدا سجل الترجمة (ليس محتوى معروضًا)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "translation":
                continue
            out += _texts(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _texts(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        out.append((path, obj))
    return out


def violations_in(doc: dict) -> list:
    """يرجّع [(نوع, مسار الحقل, مقتطف)] لكل مخالفة شكلية."""
    found = []
    for field, text in _texts(doc):
        for m in ATTRIBUTED.finditer(text):
            quoted = m.group(1)
            if LATIN_RUN.search(quoted) and not DISCLOSED.search(text):
                found.append(("english_presented_as_quran", field, m.group(0)[:120]))
        for m in IN_AYAH_BRACES.finditer(text):
            found.append(("latin_inside_ayah_braces", field, m.group(0)[:120]))

    # عنصر بيانات نوعه verse: يحتاج مصدرًا مسمّى أو إعلانًا أنه تفسير.
    if isinstance(doc, dict) and str(doc.get("kind", "")).lower() == "verse":
        blob = json.dumps(doc, ensure_ascii=False)
        if LATIN_RUN.search(str(doc.get("text", ""))) \
                and not doc.get("provenance") and not DISCLOSED.search(blob):
            found.append(("verse_without_provenance", "text",
                          str(doc.get("text", ""))[:120]))
    return found


# ── self-tests ───────────────────────────────────────────────────────────
# نجاحٌ كاذب على نصٍّ شرعي أسوأ من غياب الفحص، فالفحص يتوقّف إذا انقلبت حالة
# مرجعية بدل أن يمرّ صامتًا.
_MUST_FLAG = [
    {"summary": 'Allah says: "And your Lord has decreed that you worship none but Him."'},
    {"text": 'Allah Almighty said: "Indeed, We have sent it down as an Arabic Qur\'an."'},
    {"note": "﴿ And hold firmly to the rope of Allah ﴾"},
    {"kind": "verse", "text": "And do good to parents.", "source": "Al-Isra 23"},
]
_MUST_PASS = [
    # معلَن أنه تفسير
    {"summary": 'Allah says (interpretation of the meaning): "And your Lord has decreed…"'},
    # الآية بالعربية كما هي — وهذا هو الصواب
    {"summary": "﴿وَقَضَىٰ رَبُّكَ أَلَّا تَعْبُدُوا إِلَّا إِيَّاهُ﴾"},
    # ذكرٌ للقرآن بلا اقتباس
    {"text": "Choose a short surah together and live by one of its verses for a week."},
    # حديث منسوب للنبي ﷺ — ليس من شأن هذا الفحص
    {"text": 'The Prophet ﷺ said: "Allah is Gentle and loves gentleness."'},
    # عنصر آية بمصدر مسمّى
    {"kind": "verse", "text": "And do good to parents.",
     "provenance": "saheeh_international", "surah": 17, "ayah": 23},
]


def _self_test() -> bool:
    ok = True
    for case in _MUST_FLAG:
        if not violations_in(case):
            print(f"  ❌ self-test: لم يُمسَك ما يجب مسكه → {case}")
            ok = False
    for case in _MUST_PASS:
        got = violations_in(case)
        if got:
            print(f"  ❌ self-test: إنذار كاذب على نصّ سليم → {case}\n     {got}")
            ok = False
    return ok


def main() -> int:
    print("=" * 67)
    print("  QUR'AN RENDERING CHECK — القرآن لا يُترجَم، والمعنى يُعلَن أنه تفسير")
    print("=" * 67)

    if not _self_test():
        print("\n  ⛔ self-tests فشلت — الفحص لاغٍ، ولا يُعتدّ بنتيجته.")
        return 2
    print(f"  self-tests: {len(_MUST_FLAG)} مسك · {len(_MUST_PASS)} تمرير ✓")

    checked = 0
    problems = []
    for pattern in EN_CONTENT_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                problems.append((path, "unreadable", str(path), str(e)[:80]))
                continue
            checked += 1
            for kind, field, snippet in violations_in(doc):
                problems.append((path, kind, field, snippet))

    print(f"  ملفات إنجليزية مفحوصة: {checked}")

    if problems:
        print(f"\n  ❌ {len(problems)} مخالفة — إنجليزية مقدَّمة على أنها قرآن:\n")
        for path, kind, field, snippet in problems:
            print(f"     [{kind}] {path.relative_to(ROOT)} · {field}")
            print(f"        {snippet}")
        print("\n  الصواب: تُترك الآية بالعربية، ويُكتب المعنى مُعلَنًا:")
        print('     "interpretation of the meaning: …"  أو  provenance: <ترجمة معتمدة>')
        return 1

    print("\n" + "=" * 67)
    print("  ✅ QUR'AN RENDERING OK — لا إنجليزية مقدَّمة على أنها قرآن")
    print("  (فحص شكلي — لا يُغني عن مراجعة أهل العلم لأمانة التفسير)")
    print("=" * 67)
    return 0


if __name__ == "__main__":
    sys.exit(main())
