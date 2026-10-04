#!/usr/bin/env python3
"""Build the two hadith indexes the content guards match against.

    ops/data/hadith_index.json.gz         — Sahih al-Bukhari + Sahih Muslim.
                                            The citation authority: book + number + wording.
    ops/data/hadith_others_index.json.gz  — Abu Dawud, al-Tirmidhi, al-Nasa'i, Ibn Majah,
                                            the Muwatta. Detection only: "this quote IS a
                                            hadith, and it is NOT in the Sahihayn".

Usage:
    python ops/tools/build_hadith_index.py            # download (pinned) and rebuild both
    python ops/tools/build_hadith_index.py --cache /tmp/hadith-src --offline

Why this script exists (2026-10-04)
-----------------------------------
The first index keyed Sahih Muslim by the **sequential** number of the
fawazahmed0 edition (Darussalam-style: «إذا مات الإنسان انقطع عنه عمله» was
«مسلم ٤٢٢٣», «ستًّا من شوال» was 2758). Arabic readers and every scholar cite
Muslim by **Muhammad Fu'ad Abd al-Baqi's** numbering — 1631 and 1164. A preacher
seeing «مسلم ٤٢٢٣» concludes the app fabricates. The index was a hand-made
artefact with no build script, so nobody could see which numbering it used.

Where the Abd al-Baqi number comes from — and how we know it is right
--------------------------------------------------------------------
* The same pinned fawazahmed0 edition carries an ``arabicnumber`` per narration:
  Abd al-Baqi's number with the narration index as a decimal (1164.01 = the first
  chain of 1164). The integer part is the number scholars cite.
* Verified independently against sunnah.com's canonical references
  (``muslim:1631``, ``muslim:1164a``), taken from the MIT-licensed dataset
  meeAtif/hadith_datasets, which was scraped from sunnah.com — a different
  pipeline from fawazahmed0. Narrations are aligned by sunnah.com's in-book
  reference and confirmed by text. Result at build time on the pinned inputs:
  7,195 agree, 17 disagree, 156 unaligned (mostly the Introduction's 148
  narrations, which neither numbers). Run this script to see the current figures.
* The 17 disagreements are of two kinds, each listed in the index with its
  ``kind``:
  - 13 **boundary** placements (|Δ| ≤ 4): where one hadith ends and the next
    begins — one edition says 902, the other 901.
  - 4 **cross-references** (|Δ| in the hundreds or thousands): a narration that
    repeats a hadith from another book. Abd al-Baqi labels it with the number
    of the first occurrence — «عليكم بهذا العود الهندي» in Kitab al-Salam is
    287.05, «دخلت امرأة النار في هرة» in Kitab al-Tawba is 2619.02, a Fitan
    narration is 169.04 — while sunnah.com numbers it where it stands (2214,
    2756, 2930); once it is the other way round (a 2214 narration that
    sunnah.com files as 287).
  Both kinds are registered under **both** numbers: each is what one of the
  two references prints for that exact narration, so rejecting either rejects
  a citation a reader can verify there. Limiting the second number to small
  gaps was considered and rejected: in three of the four cross-references it
  would keep Abd al-Baqi's back-reference and drop sunnah.com's own number —
  «عليكم بهذا العود الهندي» would fail as Muslim 2214, the number a reader
  finds it under on sunnah.com, and pass only as 287, whose own chapter does
  not contain those words. Wording is still checked exactly (one contiguous
  run in one narration); an unrelated number still fails.
* Anchors, asserted at build time AND as self-tests in the guard (exit 2):
  Muslim 1631, 1164, 1893, 2699, 55, 2564 · Bukhari 1, 13, 5027, 6018.

Bukhari: fawazahmed0's ``hadithnumber`` equals its ``arabicnumber`` for every
narration and matches the common (Fath al-Bari / sunnah.com) numbering on the
anchors. Its 26 sub-entries (402.2 …) belong to the integer number and are
filed under it.

Numbers the fawazahmed0 edition does not carry at all (e.g. 2700, «لا يقعد قوم
يذكرون الله») are filled from sunnah.com's text, so a correct citation is not
rejected; they are listed under ``filled_from_sunnah_com``.

Muslim's Introduction (المقدمة) has no Abd al-Baqi number in either source. It is
kept out of the numbered table and stored unnumbered, so a citation to it fails
with a precise message instead of silently matching a number.

The old sequential number is kept only as an internal alias (``aliases``) so the
guard can say «this is the sequential number; Abd al-Baqi's is N» — it never
makes a citation pass.

Indexes hold consonantal skeletons for matching only — never display text, and
not a certificate of tahqiq.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_hadith_citations import ANCHORS, skeleton  # noqa: E402  (one normaliser, one anchor table)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ops/data/hadith_index.json.gz"
OUT_OTHERS = ROOT / "ops/data/hadith_others_index.json.gz"

FAWAZ_SHA = "df57907be35291c91ad6a6691180e22ca9920784"   # fawazahmed0/hadith-api, 2026-06-03
FAWAZ = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@{sha}/editions/ara-{book}.json"
SUNNAH_SHA = "cd62605e4fef3c46968a5f9fdcccbbbffdf631b5"  # meeAtif/hadith_datasets (MIT)
SUNNAH = "https://huggingface.co/datasets/meeAtif/hadith_datasets/resolve/{sha}/Sahih%20Muslim.json"

OTHERS = {"abudawud": "أبو داود", "tirmidhi": "الترمذي", "nasai": "النسائي",
          "ibnmajah": "ابن ماجه", "malik": "الموطأ"}

# A disagreement this small is a boundary placement; anything larger is a
# cross-reference label (see the docstring). Classification only — both kinds
# are accepted, and the build refuses to write if the split ever changes.
_BOUNDARY = 5
_EXPECTED_SPLIT = {"boundary": 13, "cross_reference": 4}



def _fetch(url: str, dest: Path, offline: bool) -> dict:
    if not dest.exists():
        if offline:
            sys.exit(f"🔴 --offline and missing {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "tutor-guardian-index-builder"})
        with urllib.request.urlopen(req, timeout=180) as r:
            dest.write_bytes(r.read())
    return json.loads(dest.read_text(encoding="utf-8"))


def _int_key(n) -> str:
    return str(int(float(n)))


def build(cache: Path, offline: bool) -> tuple[dict, dict]:
    ed = {b: _fetch(FAWAZ.format(sha=FAWAZ_SHA, book=b), cache / f"ara-{b}.json", offline)
          for b in ("bukhari", "muslim")}

    # ── Bukhari: hadithnumber == arabicnumber; sub-entries (402.2) file under 402
    bukhari: dict[str, list[str]] = {}
    for h in ed["bukhari"]["hadiths"]:
        sk = skeleton(h["text"])
        if not sk:
            continue
        if h.get("arabicnumber") is not None and float(h["arabicnumber"]) != float(h["hadithnumber"]):
            sys.exit(f"🔴 Bukhari {h['hadithnumber']}: arabicnumber {h['arabicnumber']} differs — "
                     "the numbering assumption no longer holds")
        bukhari.setdefault(_int_key(h["hadithnumber"]), []).append(sk)

    # ── Muslim: Abd al-Baqi from arabicnumber; sequential kept as alias
    muslim: dict[str, list[str]] = {}
    aliases: dict[str, int] = {}
    intro: list[str] = []
    by_ref: dict[tuple, dict] = {}
    for h in ed["muslim"]["hadiths"]:
        sk = skeleton(h["text"])
        if not sk:
            continue
        an = h.get("arabicnumber")
        if an is None:
            if h["reference"]["book"] != 0:
                sys.exit(f"🔴 Muslim seq {h['hadithnumber']} outside the Introduction has no arabicnumber")
            intro.append(sk)
            continue
        abq = _int_key(an)
        muslim.setdefault(abq, []).append(sk)
        aliases[str(h["hadithnumber"])] = int(abq)
        by_ref[(h["reference"]["book"], h["reference"]["hadith"])] = {"abq": int(abq), "sk": sk,
                                                                     "seq": h["hadithnumber"]}

    # ── Independent cross-check against sunnah.com's canonical references
    sun = _fetch(SUNNAH.format(sha=SUNNAH_SHA), cache / "sunnah-com-muslim.json", offline)
    agree, disputed, unaligned = 0, [], 0
    for s in sun:
        m = re.match(r"Book (\d+), Hadith (\d+)", s.get("In-book reference") or "")
        r = re.search(r"muslim:(\d+)", s.get("Reference") or "")
        if not (m and r):
            unaligned += 1
            continue
        mine = by_ref.get((int(m.group(1)), int(m.group(2))))
        if mine is None:
            unaligned += 1
            continue
        words = mine["sk"].split()
        probe = " ".join(words[len(words) // 2: len(words) // 2 + 5]) if len(words) > 8 else mine["sk"]
        if probe not in skeleton(s.get("Arabic_Text") or ""):
            unaligned += 1          # same slot, different text: not evidence either way
            continue
        theirs = int(r.group(1))
        if theirs == mine["abq"]:
            agree += 1
        else:
            kind = "boundary" if abs(theirs - mine["abq"]) <= _BOUNDARY else "cross_reference"
            disputed.append({"seq": mine["seq"], "fawazahmed0": mine["abq"], "sunnah_com": theirs,
                             "kind": kind})
            muslim.setdefault(str(theirs), []).append(mine["sk"])   # accept both numbers (docstring)
    if agree < 7000 or len(disputed) > 60:
        sys.exit(f"🔴 cross-check too weak (agree={agree}, disputed={len(disputed)}) — refusing to write")
    split = {k: sum(d["kind"] == k for d in disputed) for k in _EXPECTED_SPLIT}
    if split != _EXPECTED_SPLIT:
        sys.exit(f"🔴 disagreements split {split}, expected {_EXPECTED_SPLIT} — new inputs: read each "
                 "new cross-reference against both editions before accepting it under two numbers")

    # ── Gaps: Abd al-Baqi numbers the fawazahmed0 edition does not carry at all
    # (e.g. 2700, «لا يقعد قوم يذكرون الله»). Without this a correct citation is
    # rejected and the author is pushed to a wrong neighbour. sunnah.com's text
    # fills them; a combined reference ("1697/1698a") is filed under each number.
    fawaz_numbers = set(muslim)
    filled: set[int] = set()
    for s in sun:
        ref = re.search(r"muslim:(\S+)", s.get("Reference") or "")
        sk = skeleton(s.get("Arabic_Text") or "")
        if not ref or not sk:
            continue
        for n in {int(x) for x in re.findall(r"\d+", ref.group(1))}:
            if str(n) not in fawaz_numbers:
                muslim.setdefault(str(n), []).append(sk)
                filled.add(n)

    index = {
        "schema": "tg.hadith_index/2",
        "source": (f"fawazahmed0/hadith-api@{FAWAZ_SHA} — editions ara-bukhari, ara-muslim; "
                   f"Muslim numbers cross-checked against sunnah.com references "
                   f"(meeAtif/hadith_datasets@{SUNNAH_SHA}, MIT)"),
        "numbering": {
            "البخاري": "الترقيم الشائع (فتح الباري / sunnah.com) — hadithnumber = arabicnumber",
            "مسلم": "ترقيم محمد فؤاد عبد الباقي — الجزء الصحيح من arabicnumber",
        },
        "note": "مشتق آليًا: الهيكل الصامت فقط للمطابقة. ليس نصًا للعرض ولا شهادةَ تحقيق.",
        "books": {"البخاري": bukhari, "مسلم": muslim},
        "aliases": {"مسلم": aliases},
        "unnumbered": {"مسلم": {"المقدمة": intro}},
        "cross_check": {"مسلم": {"agree": agree, "disputed": disputed, "unaligned": unaligned,
                                  "filled_from_sunnah_com": sorted(filled)}},
    }

    # ── anchors must hold before anything is written
    for book, num, phrase, old in ANCHORS:
        sk = skeleton(phrase)
        if not any(sk in t for t in index["books"][book].get(str(num), [])):
            sys.exit(f"🔴 anchor {book} {num} «{phrase}» not found under {num}")
        if old is not None and any(sk in t for t in index["books"][book].get(str(old), [])):
            sys.exit(f"🔴 anchor {book}: «{phrase}» still answers to the old number {old}")

    others: dict[str, dict[str, str]] = {}
    for slug, name in OTHERS.items():
        data = _fetch(FAWAZ.format(sha=FAWAZ_SHA, book=slug), cache / f"ara-{slug}.json", offline)
        ents: dict[str, str] = {}
        for h in data["hadiths"]:
            sk = skeleton(h["text"])
            if sk:
                ents[str(h["hadithnumber"])] = sk
        others[name] = ents
    others_index = {
        "schema": "tg.hadith_others_index/1",
        "source": f"fawazahmed0/hadith-api@{FAWAZ_SHA} — " + ", ".join(f"ara-{s}" for s in OTHERS),
        "note": ("للكشف فقط: يثبت أن النص المقتبس حديثٌ خارج الصحيحين. أرقامه أرقام تلك الطبعة، "
                 "ولا يُستشهد بها في التطبيق — التطبيق يقتبس من الصحيحين وحدهما."),
        "books": others,
    }
    return index, others_index


def _write(path: Path, obj: dict) -> None:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    # mtime=0: the file is byte-identical on every rebuild of the same inputs.
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path("/tmp/tg-hadith-sources"))
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    index, others = build(args.cache, args.offline)
    _write(OUT, index)
    _write(OUT_OTHERS, others)
    cc = index["cross_check"]["مسلم"]
    print(f"✅ {OUT.relative_to(ROOT)}: البخاري {len(index['books']['البخاري'])} رقمًا · "
          f"مسلم {len(index['books']['مسلم'])} رقمًا (عبد الباقي) · مقدمة غير مرقّمة "
          f"{len(index['unnumbered']['مسلم']['المقدمة'])}")
    kinds = {k: sum(d["kind"] == k for d in cc["disputed"]) for k in _EXPECTED_SPLIT}
    print(f"   sunnah.com: يتفق {cc['agree']} · يختلف {len(cc['disputed'])} "
          f"({kinds['boundary']} حدود + {kinds['cross_reference']} إحالة — مقبول بالرقمين) · "
          f"غير مقابَل {cc['unaligned']} · أرقام غائبة عن fawazahmed0 أُكملت منه "
          f"{len(cc['filled_from_sunnah_com'])}")
    print(f"✅ {OUT_OTHERS.relative_to(ROOT)}: " +
          " · ".join(f"{b} {len(e)}" for b, e in others["books"].items()))
    print(f"   المراسي: {len(ANCHORS)}/{len(ANCHORS)} ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
