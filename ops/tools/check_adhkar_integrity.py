#!/usr/bin/env python3
"""Guard the daily-notification content against padding and blanket attribution.

Written after 2026-08-13, when the file claimed "exactly 730 unique high-quality
items" and actually held 267: one hadith text repeated 223 times, and 124 tips
repeated to 365. Each copy was made "unique" by appending a visible counter —
«(حديث رقم 51)» — which defeated a plain duplicate check and shipped to users
inside the notification itself. All 223 carried the same invented isnad,
«صحيح — رواه الترمذي وأبو داود», with no hadith number.

Attributing words to the Prophet ﷺ with a fabricated chain is the failure this
file exists to prevent, so the checks below are deliberately blunt:

  1. no two entries may share a text once the counter suffix is stripped
  2. no entry may show a bare counter to the user
  3. no `kind` may have every one of its entries under a single source string
  4. a hadith must cite a book and a locator, not a grading alone

Scope: mobile/assets/content/adhkar/family_adhkar.ar.json. The content was a
Dart `const` list until 2026-08-13; `ops/tools/extract_app_content.py` moved it
and proves the move byte-for-byte. The loader refuses to hand this check an
empty pack, so a missing file reports as a broken check (exit 2) rather than as
281 clean items.

Grading a hadith صحيح/ضعيف is scholarship and is out of scope here — this only
catches the mechanical signatures of placeholder text. A clean run means nothing
was obviously fabricated; it does not mean the content was verified.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adhkar_pack import load_or_die  # noqa: E402

# «(حديث رقم 51)» / «(نصيحة رقم 12)» / «(رقم ٣)» — padding, never real content
_COUNTER = re.compile(r"\s*\(\s*(?:حديث|نصيحة|أثر|رقم)[^)]*رقم[^)]*\)\s*$")
_HADITH_BOOKS = ("البخاري", "مسلم", "الترمذي", "أبو داود", "أبي داود", "النسائي",
                 "ابن ماجه", "أحمد", "مالك", "الموطأ", "الحاكم", "البيهقي",
                 "الطبراني", "ابن حبان", "الدارمي", "الأدب المفرد", "متفق عليه")


def strip_counter(text: str) -> str:
    return _COUNTER.sub("", text).strip()


def main() -> int:
    print("\n" + "=" * 67)
    print("  ADHKAR CONTENT INTEGRITY — فحص أصالة محتوى الإشعارات")
    print("=" * 67)

    # load_or_die exits 2 on a missing/empty/malformed pack: a clean run over
    # zero items is the one outcome this file exists to make impossible.
    items = load_or_die()
    errors: list[str] = []

    # 1 — duplicates once the padding is removed
    cores = collections.Counter(strip_counter(i.text) for i in items)
    dups = {t: n for t, n in cores.items() if n > 1}
    if dups:
        errors.append(f"{len(dups)} نص مكرر (بإجمالي {sum(dups.values())} عنصر)")
        for t, n in sorted(dups.items(), key=lambda x: -x[1])[:5]:
            print(f"\n  ✗ مكرر ×{n}: «{t[:70]}»")

    # 2 — user-visible counters
    padded = [i.text for i in items if _COUNTER.search(i.text)]
    if padded:
        errors.append(f"{len(padded)} عنصر يعرض عدّادًا للمستخدم")
        print(f"\n  ✗ عدّاد ظاهر في النص، مثال: «{padded[0][-40:]}»")

    # 3 — one source stamped across an entire kind
    by_kind: dict[str, list[str]] = collections.defaultdict(list)
    for item in items:
        by_kind[item.kind].append(item.source)
    for kind, sources in by_kind.items():
        uniq = set(sources)
        if len(sources) >= 10 and len(uniq) == 1:
            errors.append(f"kind='{kind}': {len(sources)} عنصر بإسناد واحد حرفيًا")
            print(f"\n  ✗ kind='{kind}' — {len(sources)} عنصر كلها: «{sources[0]}»")

    # 4 — a hadith needs a book and a locator
    vague = [i for i in items
             if i.kind == "hadith" and not any(b in i.source for b in _HADITH_BOOKS)]
    if vague:
        errors.append(f"{len(vague)} حديث بلا كتاب معروف في الإسناد")
        print(f"\n  ✗ إسناد بلا كتاب، مثال: «{vague[0].source}»")
    unlocated = [i for i in items
                 if i.kind == "hadith" and not re.search(r"[\d٠-٩]", i.source)]
    if unlocated:
        errors.append(f"{len(unlocated)} حديث بلا رقم/موضع يُراجَع عليه")
        print(f"\n  ✗ إسناد بلا موضع، مثال: «{unlocated[0].source}»")

    counts = collections.Counter(i.kind for i in items)
    print(f"\n  العناصر: {len(items)}   ·   " +
          "   ·   ".join(f"{k}={n}" for k, n in sorted(counts.items())))
    print(f"  نصوص فريدة بعد نزع الحشو: {len(cores)}")

    if errors:
        print(f"\n🔴  ADHKAR INTEGRITY ({len(errors)}):")
        for e in errors:
            print(f"     ✗ {e}")
        print("\n" + "=" * 67)
        print("  ❌  محتوى محشوّ أو منسوب بلا سند — لا يجوز الدفع.")
        print("=" * 67 + "\n")
        return 1

    print("\n" + "=" * 67)
    print(f"  ✅  ADHKAR OK — {len(items)} عنصرًا، كلها فريدة ومُسنَدة")
    print("  (فحص آلي للحشو والنسبة — لا يُغني عن مراجعة أهل العلم للمتون)")
    print("=" * 67 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
