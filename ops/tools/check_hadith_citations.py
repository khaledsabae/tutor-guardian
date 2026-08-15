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

Scope: `kind: 'hadith'` entries in
mobile/assets/content/adhkar/family_adhkar.ar.json (Dart literals until
2026-08-13; the move is proven byte-for-byte by
`ops/tools/extract_app_content.py verify`). The pack stores a numeric
`provenance` — book and number — beside the Arabic citation. This check parses
the citation itself, as before, and asserts the stored pair agrees: derived
data that drifted from what it was derived from is an error, not a shortcut.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adhkar_pack import load_or_die  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "ops/data/hadith_index.json.gz"

_MARKS = re.compile("[ً-ٰۖ-ۭـࣰ-ࣿ]")
_NON_ARABIC = re.compile("[^ء-ي\\s]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
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


def _check_item(books: dict, item) -> str | None:
    """[check_one] plus: the stored provenance must equal the parsed citation."""
    m = _CITE.search(item.source)
    if m is not None:
        prov = item.provenance or {}
        parsed = (m.group(1), int(m.group(2).translate(_AR_DIGITS)))
        if (prov.get("book"), prov.get("number")) != parsed:
            return (f"provenance {prov.get('book')} {prov.get('number')} "
                    f"لا يطابق الإسناد {parsed[0]} {parsed[1]}")
    return check_one(books, item.text, item.source)


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


# ── وحدات المعرفة المترجَمة ────────────────────────────────────────────────
#
# 🚨 هذا الحارس لم يكن ينظر إلى `knowledge_base/units/` إطلاقًا. يوم 2026-08-15
# نزلت ٥٤٦ وحدة إنجليزية مترجَمة، ومرّت الفحوص الستة كلها خضراء — **لأن لا أحد
# كان ينظر هنا**، لا لأن المحتوى سليم. وفي تلك الدفعة:
#
#     العربي   : وقال النبي ﷺ: «من مات وهو يعلم أن لا إله إلا الله دخل الجنة»
#     الإنجليزي: … will enter Paradise. (Narrated by al-Bukhari)
#
# المصدر العربي **لا يحمل إسنادًا البتة** — لا «رواه» ولا «البخاري» ولا «مسلم».
# النموذج اخترع إسنادًا، والمخترَع خطأ أيضًا: الحديث عند مسلم. وهذه هي الفئة
# نفسها التي شحنت ٢٢٣ حديثًا مختلَقًا كإشعارات.
#
# ولا يُطابَق نثر مترجَم على الصحيحين: الترجمة ليست لفظًا، فالمطابقة هناك ترفض
# السليم. الفحص هنا **بنيويّ ويقيني**: إسنادٌ في الإنجليزية لا نظير له في العربية
# اختراعٌ مهما كان متنه. وهذا يمسك الحالة التي وقعت بلا احتمال إيجابية كاذبة.

_EN_ATTRIB = re.compile(
    r"\b(?:narrated|reported|related|recorded|transmitted)\s+by\s+"
    r"(?:al-?)?(bukhari|bukhaari|muslim|tirmidhi|abu\s*dawud|nasai|ibn\s*majah|ahmad)"
    r"|\b(?:sahih\s+)?(?:al-?)?(bukhari|muslim)\b\s*(?:,|\)|$)",
    re.IGNORECASE)

# أي أثر إسناد في العربية — التخريج بأي صيغة، لا الصحيحين وحدهما.
_AR_ATTRIB = re.compile(
    r"رواه|أخرجه|متفق\s*عليه|البخاري|مسلم|الترمذي|أبو\s*داود|النسائي|"
    r"ابن\s*ماجه|أحمد|صحيح\s*الجامع")

_BOOK_AR = {"bukhari": "البخاري", "bukhaari": "البخاري", "muslim": "مسلم",
            "tirmidhi": "الترمذي", "ahmad": "أحمد"}


def check_translated_attribution(arabic: str, english: str) -> str | None:
    """None when sound; else why the English attribution is not in the Arabic.

    Two rejections, both certain:
      · الإنجليزية تُسند والعربية لا تُسند إطلاقًا → إسناد مخترَع.
      · كلتاهما تُسند وتسمّيان كتابين مختلفين     → إسناد مبدَّل.

    ولا يُحكم على المتن نفسه — الترجمة تُغيّر اللفظ بالضرورة، والحكم عليها
    بمطابقة اللفظ يرفض السليم ويُعطَّل الحارس، وتعطيلُه يعيد ما وُضع لأجله.
    """
    m = _EN_ATTRIB.search(english or "")
    if not m:
        return None
    named = (m.group(1) or m.group(2) or "").lower().replace(" ", "")
    if not _AR_ATTRIB.search(arabic or ""):
        return (f"الإنجليزية تنسب الحديث إلى «{named}» والعربية لا تحمل إسنادًا "
                f"البتة — إسناد مخترَع")
    ar_book = _BOOK_AR.get(named)
    if ar_book and ar_book not in arabic:
        return (f"الإنجليزية تنسبه إلى «{named}» ولا ذكر لـ«{ar_book}» في العربية "
                f"— إسناد مبدَّل")
    return None


_UNIT_MUST_REJECT = [
    # الحالة التي وقعت فعلًا — aqe-b1e103fc، 2026-08-15.
    ("وقال النبي ﷺ: «من مات وهو يعلم أن لا إله إلا الله دخل الجنة».",
     "The Prophet said: 'Whoever dies knowing there is no god but Allah "
     "will enter Paradise.' (Narrated by al-Bukhari)"),
    # إسناد مبدَّل: العربية تخرّجه لمسلم والإنجليزية تنسبه للبخاري.
    ("قال ﷺ: «الرفق ما كان في شيء إلا زانه». رواه مسلم.",
     "He said: 'Gentleness beautifies everything.' (Narrated by al-Bukhari)"),
]
_UNIT_MUST_ACCEPT = [
    # إسناد مطابق.
    ("قال ﷺ: «الرفق ما كان في شيء إلا زانه». رواه مسلم.",
     "He said: 'Gentleness beautifies everything.' (Narrated by Muslim)"),
    # لا إسناد في أيٍّ منهما — ليس شأن هذا الفحص.
    ("الرفق بالأطفال أصل في التربية.",
     "Gentleness with children is a foundation of upbringing."),
    # نثر تربوي عادي يذكر البخاري بلا دعوى إسناد… لا شيء يُنسب هنا.
    ("يقول أهل العلم إن التربية بالقدوة أبلغ.",
     "Scholars say that teaching by example is the most effective."),
]


def scan_translated_units() -> list:
    """Every `<id>__en.json` beside its Arabic source."""
    units = ROOT / "knowledge_base" / "units"
    out = []
    for f in sorted(units.glob("*__en.json")):
        src = units / f.name.replace("__en.json", ".json")
        if not src.exists():
            continue
        try:
            en = json.loads(f.read_text(encoding="utf-8"))
            ar = json.loads(src.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        # يُفحص كل حقل نصّي مقابل نظيره: الإسناد قد يقع في المتن أو العنوان.
        for key in ("text_simplified", "text_original", "title"):
            why = check_translated_attribution(
                str(ar.get(key) or ""), str(en.get(key) or ""))
            if why:
                out.append((en.get("id", f.stem), key, why))
    return out


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
    for ar, en in _UNIT_MUST_ACCEPT:
        why = check_translated_attribution(ar, en)
        if why:
            print(f"\n🔴  SELF-TEST: رُفض إسناد سليم ({why}) — الفحص لاغٍ.\n")
            return 2
    for ar, en in _UNIT_MUST_REJECT:
        if check_translated_attribution(ar, en) is None:
            print(f"\n🔴  SELF-TEST: قُبل إسناد مخترَع «{en[:46]}» — الفحص لاغٍ.\n")
            return 2
    print(f"  self-tests: {len(_MUST_ACCEPT)} قبول · {len(_MUST_REJECT)} رفض · "
          f"وحدات {len(_UNIT_MUST_ACCEPT)}/{len(_UNIT_MUST_REJECT)} ✓")

    unit_errors = scan_translated_units()
    en_units = len(list((ROOT / "knowledge_base" / "units").glob("*__en.json")))
    print(f"  وحدات مترجَمة مفحوصة: {en_units}   ·   إسناد مخترَع: {len(unit_errors)}")
    if unit_errors:
        print(f"\n🔴  إسناد في الإنجليزية لا نظير له في العربية ({len(unit_errors)}):")
        for uid, key, why in unit_errors[:12]:
            print(f"\n     ✗ {uid} · {key}\n       → {why}")
        print("\n" + "=" * 67)
        print("  ❌  نسبة قولٍ إلى النبي ﷺ بسندٍ ليس في المصدر — لا يجوز الدفع.")
        print("=" * 67 + "\n")
        return 1

    hadiths = [i for i in load_or_die() if i.kind == "hadith"]
    errors = [(i.text, i.source, w) for i in hadiths
              if (w := _check_item(books, i)) is not None]

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
