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
    'صحيح البخاري — حديث ٥٠٢٧'   ·   'صحيح مسلم — حديث ١٦٣١'

**Numbering.** Bukhari by the common (Fath al-Bari / sunnah.com) number. Muslim by
**Muhammad Fu'ad Abd al-Baqi's** number — the one Arabic readers and scholars
cite. Until 2026-10-04 Muslim was keyed by the fawazahmed0 edition's sequential
(Darussalam-style) number, so the app showed «مسلم ٤٢٢٣» for «إذا مات الإنسان»,
whose number is 1631. A preacher reading that concludes the app fabricates. The
sequential number survives only as an internal alias that names the right number
in the error — it never makes a citation pass. Anchors (exit 2 on regression):
Muslim 1631, 1164, 1893, 2699, 55, 2564 · Bukhari 1, 13, 5027, 6018.

Free text everywhere else (lessons, stories, assets, ARB, push and SEO literals…)
is `check_scripture_coverage.py`, which reuses [check_one]'s matching.

Scope: `kind: 'hadith'` entries in
mobile/assets/content/adhkar/family_adhkar.ar.json (Dart literals until
2026-08-13; the move is proven byte-for-byte by
`ops/tools/extract_app_content.py verify`). The pack stores a numeric
`provenance` — book and number — beside the Arabic citation. This check parses
the citation itself, as before, and asserts the stored pair agrees: derived
data that drifted from what it was derived from is an error, not a shortcut.

Corpus: `ops/data/hadith_index.json.gz`, built by `ops/tools/build_hadith_index.py`
from the ara-bukhari and ara-muslim editions of fawazahmed0/hadith-api (pinned
commit), Muslim numbers cross-checked against sunnah.com. It stores consonantal skeletons
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


INDEX_SCHEMA = "tg.hadith_index/2"

# Filled by [_load_index]: the old sequential Muslim numbers (diagnosis only) and
# the Introduction narrations, which Abd al-Baqi did not number.
_ALIASES: dict[str, dict[str, int]] = {}
_UNNUMBERED: dict[str, dict[str, list[str]]] = {}


def _load_index() -> dict:
    if not INDEX.exists():
        print(f"\n🔴  الفهرس غير موجود: {INDEX}")
        print("    أعِد بناءه: python ops/tools/build_hadith_index.py\n")
        sys.exit(2)
    with gzip.open(INDEX, "rt", encoding="utf-8") as f:
        idx = json.load(f)
    if idx.get("schema") != INDEX_SCHEMA:
        # A v1 index keys Muslim by the sequential number: every check against
        # it would "pass" the wrong numbers. Refuse rather than report.
        print(f"\n🔴  مخطط الفهرس {idx.get('schema')!r} — المنتظر {INDEX_SCHEMA!r} "
              "(ترقيم عبد الباقي لصحيح مسلم).")
        print("    أعِد بناءه: python ops/tools/build_hadith_index.py\n")
        sys.exit(2)
    _ALIASES.clear()
    _ALIASES.update(idx.get("aliases", {}))
    _UNNUMBERED.clear()
    _UNNUMBERED.update(idx.get("unnumbered", {}))
    return idx


def _narrations(value) -> list[str]:
    """One number → its narrations. Each stays a separate string, so a match can
    never run across the boundary between two chains filed under one number."""
    return value if isinstance(value, list) else [value]


def locate(books: dict, frag: str) -> tuple[str, int] | None:
    """(book, number) of the first narration holding `frag` — Bukhari first,
    lowest number first, so the answer is stable from run to run."""
    for b in ("البخاري", "مسلم"):
        for n in sorted(books.get(b, {}), key=float):
            if any(frag in t for t in _narrations(books[b][n])):
                return b, int(n)
    return None


def check_one(books: dict, text: str, source: str) -> str | None:
    """Return None when sound, else why it is rejected."""
    m = _CITE.search(source)
    if not m:
        return "الإسناد لا يذكر «صحيح البخاري» أو «صحيح مسلم» برقم حديث"
    book, num = m.group(1), str(int(m.group(2).translate(_AR_DIGITS)))
    entries = books.get(book)
    if entries is None:
        return f"كتاب غير مدعوم: {book}"
    frag = skeleton(text)
    if not frag:
        return "النص فارغ بعد التطبيع"
    target = entries.get(num)
    if target is not None and any(frag in t for t in _narrations(target)):
        return None
    # The pre-2026-10-04 sequential number: name the right one, never pass.
    alias = _ALIASES.get(book, {}).get(num)
    if alias is not None and any(frag in t for t in _narrations(entries.get(str(alias), []))):
        return (f"{num} رقمٌ تسلسلي (طبعة دار السلام/fawazahmed0) لا رقم عبد الباقي — "
                f"الإسناد الصحيح: «{cite(book, alias)}»")
    found = locate(books, frag)
    if found:
        where = f"صحيح {found[0]} حديث {found[1]}"
        if target is None:
            return f"لا يوجد حديث برقم {num} في صحيح {book} — والنص في {where}"
        return f"النص موجود في {where}، لا {book} {num}"
    for b, pools in _UNNUMBERED.items():
        for part, texts in pools.items():
            if any(frag in t for t in texts):
                return f"النص في {part} صحيح {b} — غير مرقّمة عند عبد الباقي فلا يُستشهد بها برقم"
    if target is None:
        return f"لا يوجد حديث برقم {num} في صحيح {book}"
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

# Numbering anchors — (book, the number scholars cite, a phrase that lives there,
# the sequential number the v1 index used for it). Shared with the index builder,
# which refuses to write an index that breaks one. A Muslim anchor accepted under
# its old number, or rejected under Abd al-Baqi's, means the numbering regressed.
ANCHORS = [
    ("مسلم", 1631, "إذا مات الإنسان انقطع عنه عمله", 4223),
    ("مسلم", 1164, "من صام رمضان ثم أتبعه ستا من شوال", 2758),
    ("مسلم", 1893, "من دل على خير فله مثل أجر فاعله", 4899),
    ("مسلم", 2699, "من نفس عن مؤمن كربة من كرب الدنيا", 6853),
    ("مسلم", 55, "الدين النصيحة", 196),
    ("مسلم", 2564, "لا تحاسدوا ولا تناجشوا ولا تباغضوا ولا تدابروا", 6541),
    ("البخاري", 1, "إنما الأعمال بالنيات", None),
    ("البخاري", 13, "لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه", None),
    ("البخاري", 5027, "خيركم من تعلم القرآن وعلمه", None),
    ("البخاري", 6018, "من كان يؤمن بالله واليوم الآخر فلا يؤذ جاره", None),
]
_AR_NUM = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def cite(book: str, number: int) -> str:
    """The one citation format the guards accept: «صحيح مسلم — حديث ١٦٣١»."""
    return f"صحيح {book} — حديث {str(number).translate(_AR_NUM)}"


_MUST_ACCEPT += [(phrase, cite(b, n)) for b, n, phrase, _ in ANCHORS]
_MUST_REJECT += [(phrase, cite(b, old)) for b, _, phrase, old in ANCHORS if old]
# A cross-reference narration (build_hadith_index.py docstring): Abd al-Baqi
# labels it 287.05, sunnah.com files it as 2214 — both editions' number pass,
# a neighbour of either does not.
_MUST_ACCEPT += [("عليكم بهذا العود الهندي", cite("مسلم", 287)),
                 ("عليكم بهذا العود الهندي", cite("مسلم", 2214))]
_MUST_REJECT += [("عليكم بهذا العود الهندي", cite("مسلم", 2215))]


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


# ── برامج الأسرة ───────────────────────────────────────────────────────────
#
# برامج رمضان ورحلة الصلاة والمراحل (knowledge_base/curriculum/programs/) تحمل
# أحاديثها في مصفوفة `evidence` بعناصر `kind: hadith` — النص العربي متصلًا،
# والإسناد بالصيغة نفسها، و`provenance` رقمية. الحارس كان لا ينظر إلا في حزمة
# الأذكار والوحدات المترجمة، فبطاقة حديث في برنامج كانت ستمرّ بلا مطابقة. الملف
# الإنجليزي يحمل `text_ar` نفسه ويُفحص كذلك: انحراف نصّ الحديث في الترجمة وحدها
# يصل المستخدم الإنجليزي تمامًا كما يصل العربي.

PROGRAM_DIRS = (
    ROOT / "knowledge_base" / "curriculum" / "programs",
    ROOT / "knowledge_base" / "curriculum" / "i18n" / "en" / "programs",
)


class _Card:
    """Adapter so a program evidence card goes through the same `_check_item`."""

    def __init__(self, card: dict):
        self.text = card.get("text_ar") or ""
        self.source = card.get("source") or ""
        self.provenance = card.get("provenance") or {}


def check_program_card(books: dict, card: dict) -> str | None:
    return _check_item(books, _Card(card))


_PROGRAM_MUST_REJECT = [
    # رقم في provenance لا يطابق الإسناد المكتوب.
    {"text_ar": "خيركم من تعلم القرآن وعلمه", "source": "صحيح البخاري — حديث ٥٠٢٧",
     "provenance": {"book": "البخاري", "number": 5028}},
    # اللفظ الذي شُحن فعلًا ثم بلّغ عنه المستخدمان.
    {"text_ar": "خيركم من تعلم العلم وعلمه", "source": "صحيح البخاري — حديث ٥٠٢٧",
     "provenance": {"book": "البخاري", "number": 5027}},
]
_PROGRAM_MUST_ACCEPT = [
    {"text_ar": "خيركم من تعلم القرآن وعلمه", "source": "صحيح البخاري — حديث ٥٠٢٧",
     "provenance": {"book": "البخاري", "number": 5027}},
]


def scan_programs(books: dict) -> tuple[int, list]:
    cards, errors = 0, []
    for d in PROGRAM_DIRS:
        for f in sorted(d.glob("*.json")) if d.exists() else []:
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append((str(f.relative_to(ROOT)), "json", str(e)[:60]))
                continue
            for card in (doc.get("evidence") or []) if isinstance(doc, dict) else []:
                if card.get("kind") != "hadith":
                    continue
                cards += 1
                why = check_program_card(books, card)
                if why:
                    errors.append((str(f.relative_to(ROOT)), card.get("id", "?"), why))
    return cards, errors


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
    for card in _PROGRAM_MUST_ACCEPT:
        why = check_program_card(books, card)
        if why:
            print(f"\n🔴  SELF-TEST: رُفضت بطاقة برنامج سليمة ({why}) — الفحص لاغٍ.\n")
            return 2
    for card in _PROGRAM_MUST_REJECT:
        if check_program_card(books, card) is None:
            print(f"\n🔴  SELF-TEST: قُبلت بطاقة برنامج مرفوضة «{card['text_ar'][:40]}» — الفحص لاغٍ.\n")
            return 2
    print(f"  self-tests: {len(_MUST_ACCEPT)} قبول · {len(_MUST_REJECT)} رفض · "
          f"وحدات {len(_UNIT_MUST_ACCEPT)}/{len(_UNIT_MUST_REJECT)} · "
          f"برامج {len(_PROGRAM_MUST_ACCEPT)}/{len(_PROGRAM_MUST_REJECT)} ✓")

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

    n_cards, program_errors = scan_programs(books)
    print(f"  بطاقات أحاديث في البرامج (عربي + إنجليزي): {n_cards}   ·   مخالفة: {len(program_errors)}")
    if program_errors:
        print(f"\n🔴  بطاقات أحاديث في البرامج لا تطابق الصحيحين ({len(program_errors)}):")
        for rel, cid, why in program_errors[:12]:
            print(f"\n     ✗ {rel} · {cid}\n       → {why}")
        print("\n" + "=" * 67)
        print("  ❌  حديث في برنامج لا يطابق الصحيحين لفظًا ورقمًا — لا يجوز الدفع.")
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
