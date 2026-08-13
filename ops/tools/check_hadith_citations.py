#!/usr/bin/env python3
"""Verify every hadith in the app against Sahih al-Bukhari and Sahih Muslim.

Only the two Sahihs. That is the whole point: their authenticity is settled by
consensus, so the question «is this hadith sound?» — which is scholarship, not
string work — is taken off the table, and what remains is mechanical: is this
the text, and is this the number.

What this rejects, drawn from what actually shipped:

  * a wording that is not in either Sahih. The app sent «خيركم من تعلم **العلم**
    وعلمه»; the sound narration is «خيركم من تعلم **القرآن** وعلمه» (Bukhari
    5027). Two users reported it on 3 and 7 August 2026; nobody was listening,
    because the feedback alerts were never wired up.
  * a hadith stitched to something that is not part of it. The second reporter
    was precise: «فقط الشق الأول منه، والشق الثاني هو من صفة رسول الله». The
    matched text must be one contiguous run inside one corpus entry, so a
    stitched pair cannot pass.
  * a citation whose number points at a different hadith.

Source format expected in `source:`
    'صحيح البخاري — حديث ٥٠٢٧'   ·   'صحيح مسلم — حديث ٢٣١٨'

Corpus: `ops/data/hadith_index.json.gz`, derived from the ara-bukhari and
ara-muslim editions of fawazahmed0/hadith-api. It stores consonantal skeletons
for matching only — it is not display text, and **it is not a certificate of
tahqiq**. A pass here means the wording and the number line up with that
edition; it does not mean a scholar has reviewed the choice.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADHKAR = ROOT / "mobile/lib/features/adhkar/data/family_adhkar.dart"
INDEX = ROOT / "ops/data/hadith_index.json.gz"

_MARKS = re.compile("[ً-ٰۖ-ۭـࣰ-ࣿ]")
_NON_ARABIC = re.compile("[^ء-ي\\s]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_ITEM = re.compile(
    r"ParentingContent\(\s*text:\s*'((?:[^'\\]|\\.)*)'\s*,"
    r"\s*source:\s*'((?:[^'\\]|\\.)*)'\s*,"
    r"\s*topic:\s*'((?:[^'\\]|\\.)*)'\s*,\s*kind:\s*'(\w+)'")
_CITE = re.compile(r"صحيح\s+(البخاري|مسلم)\s*[—\-–]\s*حديث\s*([٠-٩0-9]+)")


def skeleton(s: str) -> str:
    """Same reduction as the Qur'an check — see check_quran_citations.py."""
    s = unicodedata.normalize("NFC", s)
    s = _MARKS.sub("", s)
    s = s.replace("ٱ", "ا")
    s = re.sub("[أإآ]", "ا", s)
    s = s.replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = _NON_ARABIC.sub(" ", s)
    s = re.sub("[اوي]", "", s)
    s = re.sub(r"(\S)\1+", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _load_index() -> dict:
    if not INDEX.exists():
        print(f"\n🔴  الفهرس غير موجود: {INDEX}")
        print("    أعِد بناءه من ara-bukhari/ara-muslim قبل الاعتماد على الفحص.\n")
        sys.exit(2)
    with gzip.open(INDEX, "rt", encoding="utf-8") as f:
        return json.load(f)


def check_one(books: dict, text: str, source: str) -> str | None:
    """Return None when sound, else why it is rejected."""
    m = _CITE.search(source)
    if not m:
        return "الإسناد لا يذكر «صحيح البخاري» أو «صحيح مسلم» برقم حديث"
    book, num = m.group(1), str(int(m.group(2).translate(_AR_DIGITS)))
    entries = books.get(book)
    if entries is None:
        return f"كتاب غير مدعوم: {book}"
    target = entries.get(num)
    if target is None:
        return f"لا يوجد حديث برقم {num} في صحيح {book}"
    frag = skeleton(text)
    if not frag:
        return "النص فارغ بعد التطبيع"
    if frag in target:
        return None
    # Where does it really live? Cheap enough over 15k entries.
    for b, ents in books.items():
        for n, t in ents.items():
            if frag in t:
                return f"النص موجود في صحيح {b} حديث {n}، لا {book} {num}"
    return f"النص ليس في صحيح {book} ولا في الآخر — لفظ غير ثابت أو ملزوق"


# Regression fixtures: the checker must reject what shipped and accept what is
# sound. With zero hadith in the app these are the only thing proving it works.
_MUST_REJECT = [
    ("قال النبي صلى الله عليه وسلم: خيركم من تعلم العلم وعلمه، وكان أرحم "
     "الناس بالصبيان والعيال.", "صحيح البخاري — حديث ٥٠٢٧"),
    ("خيركم من تعلم القرآن وعلمه وكان أرحم الناس بالعيال",
     "صحيح البخاري — حديث ٥٠٢٧"),
    ("خيركم من تعلم القرآن وعلمه", "صحيح البخاري — حديث ١"),
    ("خيركم من تعلم القرآن وعلمه", "صحيح — رواه الترمذي وأبو داود"),
]
_MUST_ACCEPT = [("خيركم من تعلم القرآن وعلمه", "صحيح البخاري — حديث ٥٠٢٧")]


def main() -> int:
    print("\n" + "=" * 67)
    print("  HADITH CITATION CHECK — فحص الأحاديث على الصحيحين")
    print("=" * 67)

    books = _load_index()["books"]
    print("  الفهرس: " + " · ".join(f"{b} {len(e)}" for b, e in books.items()))

    for text, source in _MUST_ACCEPT:
        why = check_one(books, text, source)
        if why:
            print(f"\n🔴  SELF-TEST: رُفض حديث ثابت ({why}) — الفحص لاغٍ.\n")
            return 2
    for text, source in _MUST_REJECT:
        if check_one(books, text, source) is None:
            print(f"\n🔴  SELF-TEST: قُبل «{text[:50]}» وهو مرفوض — الفحص لاغٍ.\n")
            return 2
    print(f"  self-tests: {len(_MUST_ACCEPT)} قبول · {len(_MUST_REJECT)} رفض ✓")

    items = _ITEM.findall(ADHKAR.read_text(encoding="utf-8"))
    hadiths = [(t, s) for t, s, _, k in items if k == "hadith"]
    errors = [(t, s, w) for t, s in hadiths
              if (w := check_one(books, t, s)) is not None]

    print(f"  أحاديث في التطبيق: {len(hadiths)}   ·   مطابقة: {len(hadiths) - len(errors)}")

    if errors:
        print(f"\n🔴  HADITH ERRORS ({len(errors)}):")
        for text, source, why in errors:
            print(f"\n     ✗ {source}\n       {text[:80]}\n       → {why}")
        print("\n" + "=" * 67)
        print("  ❌  حديث لا يطابق الصحيحين — لا يجوز الدفع.")
        print("=" * 67 + "\n")
        return 1

    print("\n" + "=" * 67)
    if not hadiths:
        print("  ✅  لا أحاديث في التطبيق حاليًا — الحارس جاهز لأول واحد يُضاف.")
    else:
        print(f"  ✅  HADITH OK — {len(hadiths)} مطابقة للصحيحين لفظًا ورقمًا")
    print("  (مطابقة آلية على طبعة واحدة — ليست تحقيقًا ولا اختيارًا شرعيًا)")
    print("=" * 67 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
