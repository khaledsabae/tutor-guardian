#!/usr/bin/env python3
"""Verify every Qur'an citation in the app against the mushaf text.

Scope: `kind: 'verse'` entries in
mobile/assets/content/adhkar/family_adhkar.ar.json (they were Dart literals
until 2026-08-13; the move is proven byte-for-byte by
`ops/tools/extract_app_content.py verify`). Those go out as daily
notifications, so a corrupted word is scripture misquoted to every user — the
one class of defect in this repo that has no acceptable rate.

The pack now carries a numeric `provenance` — surah and ayah — alongside the
Arabic `source:` string. This check does **not** take it on trust: it parses
the citation itself, exactly as before, and then asserts the stored numbers
agree. A provenance field that drifted from the citation it was derived from is
an error here, not a shortcut.

Matching is on the **consonantal skeleton**. The mushaf and modern typing
disagree about where long vowels are written (لقمٰن/لقمان، ٱلصلوٰة/الصلاة،
ءَانَآيِٕ/آناء), so comparing the rendered spelling produces a flood of false
alarms. Dropping the marks and the matres lectionis (ا و ي) leaves the
consonants, which the two orthographies do agree on — and a swapped consonant,
which is what an actual corruption looks like, still fails.

The normaliser is guarded by self-tests: if it ever mangles text, the script
aborts instead of reporting a clean run over garbage.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adhkar_pack import load_or_die  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
QURAN = ROOT / "mobile/assets/data/quran.json"

SURAHS = ["الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال",
"التوبة","يونس","هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم",
"طه","الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت",
"الروم","لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر","فصلت",
"الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق","الذاريات",
"الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة","الصف",
"الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج","نوح",
"الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس","التكوير",
"الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد",
"الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات",
"القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر",
"المسد","الإخلاص","الفلق","الناس"]
ALIAS = {"بني إسرائيل": "الإسراء", "الانشراح": "الشرح", "المؤمن": "غافر",
         "الدهر": "الإنسان", "اللهب": "المسد", "حم السجدة": "فصلت"}

_MARKS = re.compile("[ً-ٰۖ-ۭـࣰ-ࣿ]")
_NON_ARABIC = re.compile("[^ء-ي\\s]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_CITATION = re.compile(r"سورة\s+(.+?)\s*[—\-–]\s*(?:آية|الآية)\s*([٠-٩0-9]+)")


def skeleton(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = _MARKS.sub("", s)
    s = s.replace("ٱ", "ا")
    s = re.sub("[أإآ]", "ا", s)
    s = s.replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = _NON_ARABIC.sub(" ", s)
    s = re.sub("[اوي]", "", s)
    # Gemination: the mushaf writes a doubled consonant as one letter + shadda
    # (ٱلَّيۡلِ), modern typing repeats the letter (اللَّيْلِ). The shadda is gone by
    # now, so collapse any run to a single letter and the two agree. A swapped
    # consonant — what a real corruption looks like — still differs.
    s = re.sub(r"(\S)\1+", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _load_mushaf() -> tuple[dict, dict]:
    raw = json.loads(QURAN.read_text(encoding="utf-8"))
    per_ayah = {int(c): {v["verse"]: skeleton(v["text"]) for v in vs}
                for c, vs in raw.items()}
    per_surah = {c: " ".join(d[k] for k in sorted(d)) for c, d in per_ayah.items()}
    return per_ayah, per_surah


# Verbatim citations that must always match. If one of these fails the
# normaliser is broken and every "pass" below would be meaningless.
_SELF_TESTS = [
    (13, 28, "ألا بذكر الله تطمئن القلوب"),
    (14, 40, "رب اجعلني مقيم الصلاة ومن ذريتي"),
    (31, 13, "وإذ قال لقمان لابنه وهو يعظه"),
    (30, 30, "فأقم وجهك للدين حنيفا"),
]


def main() -> int:
    print("\n" + "=" * 67)
    print("  QUR'AN CITATION CHECK — فحص مطابقة الآيات لنص المصحف")
    print("=" * 67)

    per_ayah, per_surah = _load_mushaf()

    for ch, ay, probe in _SELF_TESTS:
        if skeleton(probe) not in per_ayah[ch][ay]:
            print(f"\n🔴  SELF-TEST FAILED on {ch}:{ay} — the normaliser is broken.")
            print("    Refusing to report a result: a clean run here would be a lie.\n")
            return 2
    print(f"  self-tests: {len(_SELF_TESTS)}/{len(_SELF_TESTS)} ok")

    verses = [i for i in load_or_die() if i.kind == "verse"]

    exact, errors, unparsed = 0, [], []
    for item in verses:
        text, source = item.text, item.source
        m = _CITATION.search(source)
        if not m:
            unparsed.append((text, source))
            continue
        name = ALIAS.get(m.group(1).strip(), m.group(1).strip())
        if name not in SURAHS:
            unparsed.append((text, source))
            continue
        ch = SURAHS.index(name) + 1
        ayah = int(m.group(2).translate(_AR_DIGITS))
        # The stored provenance must be what the citation says, not something
        # a hand-edit put there. A wrong number here reaches users.
        prov = item.provenance or {}
        if (prov.get("surah"), prov.get("ayah")) != (ch, ayah):
            errors.append((text, source,
                           f"provenance {prov.get('surah')}:{prov.get('ayah')} "
                           f"لا يطابق الإسناد {ch}:{ayah}"))
            continue
        # a quote may join consecutive verses with '*'
        frags = [f for f in (skeleton(p) for p in re.split(r"\s*[*]\s*", text)) if f]
        span = " ".join(per_ayah[ch].get(ayah + k, "") for k in range(len(frags) + 1))
        if all(f in span for f in frags):
            exact += 1
        elif all(f in per_surah[ch] for f in frags):
            found = [v for v, vt in per_ayah[ch].items() if frags[0] in vt]
            errors.append((text, source, f"النص في سورة {name} لكن في آية {found[:3]}"))
        else:
            errors.append((text, source, f"النص غير موجود في سورة {name}"))

    print(f"  آيات مقتبسة: {len(verses)}   ·   مطابقة: {exact}")

    if unparsed:
        print(f"\n🟡  إسنادات لم تُقرأ آليًا ({len(unparsed)}):")
        for text, source in unparsed:
            print(f"     ? {source}  ←  {text[:44]}")

    if errors:
        print(f"\n🔴  QUR'AN TEXT ERRORS ({len(errors)}):")
        for text, source, why in errors:
            print(f"\n     ✗ {source}")
            print(f"       {text[:80]}")
            print(f"       → {why}")
        print("\n" + "=" * 67)
        print("  ❌  آية لا تطابق المصحف — لا يجوز الدفع قبل التصحيح.")
        print("=" * 67 + "\n")
        return 1

    print("\n" + "=" * 67)
    print(f"  ✅  QUR'AN CITATIONS OK — {exact}/{len(verses)} مطابقة لنص المصحف")
    print("=" * 67 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
