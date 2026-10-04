#!/usr/bin/env python3
"""Every quoted ayah and hadith the app ships — not just the ones in one file.

Why this guard exists (2026-10-04)
----------------------------------
`check_quran_citations.py` and `check_hadith_citations.py` look at the
notification pack. Nothing looked at the rest: lesson summaries, stories,
flashcards, quizzes, reports, KB units, ARB strings, the share card, the quiz
bank, the public SEO pages. The first full scan found 106 problems there and
**not one** free-text hadith quote carrying a valid book + number, among them:

  * «الراحمون يرحمهم الرحمن» opening a 7-9 lesson summary (Abu Dawud/al-Tirmidhi);
  * «خيركم خيركم لأهله» (al-Tirmidhi) in a lesson and its flashcard;
  * «إن الله رفيق يحب الرفق في كل شيء» — Bukhari 6927 says «في الأمر كله» —
    a paraphrase dressed as the Prophet's words, in a lesson and a daily tip;
  * «الدالُّ على الخير كفاعله» (al-Tirmidhi) on the invite share card;
  * «من كان له صبي فليتصابى معه» (no sound chain) in a lesson report.

What it checks, over `content_surfaces.iter_items()`:
  1. free text — `scripture_scan.scan_text`: a quote presented as the Prophet's
     speech, or whose wording IS a hadith, must be in the Sahihayn verbatim with
     a citation whose number holds it (Muslim by Abd al-Baqi); a verse must be
     the mushaf's, at the cited place;
  2. cards (text + its own `source`, any surface) — the structured guard's
     `_check_item`: wording, number, provenance;
  3. English twins — a book/number cited in a translation must be cited in its
     Arabic source, and an English attribution must not exist where the Arabic
     has none (`check_translated_attribution`, until now applied to KB units only);
  4. `backend/app/data/quran.json` — byte-identical to the mushaf the guards use
     (the tafsir service serves it; a drifted copy would serve unchecked verses).

Exit: 0 clean · 1 violations · 2 the guard itself is broken (self-tests, or a
surface that used to have content now yields nothing — a guard reading nothing
reports ✅, which is the worst outcome available here).
"""
from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture_scan as S  # noqa: E402
from check_hadith_citations import _check_item, check_translated_attribution  # noqa: E402
from content_surfaces import Card, arabic_twin, iter_items  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MUSHAF = ROOT / "mobile/assets/data/quran.json"
BACKEND_MUSHAF = ROOT / "backend/app/data/quran.json"

# A surface that drops under its floor means the enumerator stopped reading it
# (a moved directory, a renamed key) — not that the content got cleaner.
FLOORS = {
    "lesson": 500, "lesson.en": 500, "daily_tip": 150, "daily_tip.en": 150, "path": 100,
    "kb_unit": 1500, "kb_unit.en": 500, "story": 300, "adhkar": 500, "game": 1000,
    "arb": 1000, "asset.flashcards": 500, "asset.quizzes": 1000, "asset.reports": 1000,
    "py_literal": 300, "dart_literal": 100, "frontend": 1,
}

# Files another open PR owns and fixes. A violation there is reported as pending,
# not as a failure — but ONLY while the file is byte-for-byte the version that PR
# replaces. Any edit to it (that PR landing, or anyone else's) ends the exemption
# on its own, and a stale entry is printed so it gets deleted. It never covers a
# new violation: new text means new bytes. (seo.py's entry ended when #25 landed.)
PENDING_ELSEWHERE: dict[str, tuple[str, str]] = {}

_PARITY_MUST_FLAG = [
    # the translation keeps the old sequential number the Arabic dropped
    ("«إذا مات الإنسان انقطع عنه عمله» (صحيح مسلم — حديث ١٦٣١)",
     "«When a person dies, his deeds end» (Sahih Muslim 4223)"),
    # an attribution the Arabic never made
    ("الرفق بالأطفال أصل في التربية.", "Gentleness is a foundation (Narrated by al-Bukhari)"),
]
_PARITY_MUST_PASS = [
    ("«إن الله رفيق يحب الرفق في الأمر كله» (صحيح البخاري — حديث ٦٩٢٧)",
     "«Allah is gentle and loves gentleness in every matter» (Sahih al-Bukhari 6927)"),
]


def parity(ar: str, en: str) -> str | None:
    extra = (S.en_citations(en) | S.ar_citations(en)) - (S.ar_citations(ar) | S.en_citations(ar))
    if extra:
        b, n = sorted(extra)[0]
        return f"الترجمة تستشهد بـ{b} {n} ولا يستشهد به الأصل العربي"
    return check_translated_attribution(ar, en)


def _self_tests() -> str | None:
    why = S.self_test()
    if why:
        return why
    for ar, en in _PARITY_MUST_FLAG:
        if parity(ar, en) is None:
            return f"لم يُرصد خلل الترجمة: {en[:50]}"
    for ar, en in _PARITY_MUST_PASS:
        if (w := parity(ar, en)) is not None:
            return f"رُفضت ترجمة سليمة: {w}"
    return None


def main() -> int:
    print("\n" + "=" * 67)
    print("  SCRIPTURE COVERAGE — الآيات والأحاديث في كل ما يُعرض، لا في ملف واحد")
    print("=" * 67)

    why = _self_tests()
    if why:
        print(f"\n🔴  SELF-TEST: {why} — الفحص لاغٍ.\n")
        return 2
    print(f"  self-tests: {len(S.MUST_FLAG)} رصد · {len(S.MUST_PASS)} سليم · "
          f"ترجمة {len(_PARITY_MUST_FLAG)}/{len(_PARITY_MUST_PASS)} ✓")

    books, _, _ = S.corpora()
    items = list(iter_items())
    texts = [it for it in items if not isinstance(it, Card)]
    cards = [it for it in items if isinstance(it, Card)]

    per_surface = Counter(it.surface for it in items)
    thin = {s: (per_surface.get(s, 0), f) for s, f in FLOORS.items() if per_surface.get(s, 0) < f}
    if thin:
        for s, (n, f) in sorted(thin.items()):
            print(f"\n🔴  السطح «{s}» أعطى {n} نصًا والحد الأدنى {f} — المعدِّد لم يعد يقرؤه.")
        print("    حارسٌ لا يقرأ شيئًا يقول ✅ — أصلح content_surfaces قبل الاعتماد على النتيجة.\n")
        return 2

    errors: list[tuple[str, str, str, str]] = []
    verified = Counter()
    for it in texts:
        for f in S.scan_text(it.text):
            if f.verdict == "ok":
                verified[f.kind] += 1
            else:
                errors.append((f"{it.path} :: {it.where}", f.kind, f.quote, f.why))
    for c in cards:
        w = _check_item(books, c)
        if w:
            errors.append((f"{c.path} :: {c.where}", "card", c.text, w))
        else:
            verified["card"] += 1

    arabic = {(it.path, it.where): it.text for it in texts}
    pairs = 0
    for it in texts:
        twin = arabic_twin(it.path)
        if twin and (twin, it.where) in arabic:
            pairs += 1
            w = parity(arabic[(twin, it.where)], it.text)
            if w:
                errors.append((f"{it.path} :: {it.where}", "translation", it.text, w))

    if not BACKEND_MUSHAF.exists() or (
            hashlib.sha256(BACKEND_MUSHAF.read_bytes()).digest()
            != hashlib.sha256(MUSHAF.read_bytes()).digest()):
        errors.append((str(BACKEND_MUSHAF.relative_to(ROOT)), "quran", "—",
                       "نسخة الخادم من المصحف ليست مطابقة بايتًا ببايت لـ mobile/assets/data/quran.json"))

    pending, stale = [], []
    for rel, (digest, why_pending) in PENDING_ELSEWHERE.items():
        f = ROOT / rel
        if f.exists() and hashlib.sha256(f.read_bytes()).hexdigest() == digest:
            mine = [e for e in errors if e[0].startswith(rel + " ::")]
            errors = [e for e in errors if not e[0].startswith(rel + " ::")]
            pending += [(e, why_pending) for e in mine]
        else:
            stale.append(rel)

    print(f"  الأسطح: {len(per_surface)} · نصوص {len(texts)} · بطاقات {len(cards)} · "
          f"أزواج ترجمة {pairs}")
    print(f"  مُتحقَّق: أحاديث {verified['hadith']} · آيات {verified['quran']} · "
          f"بطاقات {verified['card']}")

    for (where, kind, quote, why), owner in pending:
        print(f"  ⏳ معلّق على فرع آخر — {where}\n     «{quote[:70]}» → {why}\n     ({owner})")
    for rel in stale:
        print(f"  🧹 استثناء قديم: {rel} تغيّر — احذف مدخله من PENDING_ELSEWHERE (صار يُفحص كاملًا).")

    if errors:
        by_kind = Counter(k for _, k, _, _ in errors)
        print(f"\n🔴  {len(errors)} مخالفة (" + " · ".join(f"{k} {n}" for k, n in by_kind.items()) + "):")
        for where, kind, quote, why in errors[:40]:
            print(f"\n     ✗ [{kind}] {where}\n       «{quote[:90]}»\n       → {why}")
        if len(errors) > 40:
            print(f"\n     … و{len(errors) - 40} أخرى")
        print("\n" + "=" * 67)
        print("  ❌  نصٌّ شرعي بلا سند صحيح أو بغير لفظه — لا يجوز الدفع.")
        print("      الحديث: من الصحيحين بلفظه + «(صحيح البخاري — حديث ٦٩٢٧)»، أو صِفْه بلا اقتباس.")
        print("=" * 67 + "\n")
        return 1

    print("\n" + "=" * 67)
    print("  ✅  SCRIPTURE COVERAGE OK — كل اقتباس في كل سطح مطابق ومُسنَد")
    print("  (مطابقة آلية على طبعة واحدة — ليست تحقيقًا ولا اختيارًا شرعيًا)")
    print("=" * 67 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
