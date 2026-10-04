#!/usr/bin/env python3
"""Find quoted scripture inside free text, and say whether it is sound.

The structured guards check an item that declares itself — `kind: hadith` with
a `source:`. Most of the app does not declare anything: a lesson summary, a
story's «القيمة الإسلامية», a flashcard, an onboarding string or a push-message
literal simply *quotes*. This module finds those quotes in every text that
`content_surfaces` enumerates and applies the same two rules the app lives by:

  Hadith  — only Sahih al-Bukhari and Sahih Muslim, verbatim (contiguous, one
            narration), with book and number (Muslim by Abd al-Baqi). The match
            is the guard's own: `check_hadith_citations.check_one` semantics.
  Qur'an  — the words must be the mushaf's (`mobile/assets/data/quran.json`),
            and a cited surah/ayah must be where they are.

What counts as a hadith *claim* (anything else is ordinary prose):

  1. a quote introduced as the Prophet's speech — «قال رسول الله ﷺ: «…»»,
     «النبي ﷺ يقول: …», «في الحديث: «…»», «قوله ﷺ: …»;
  2. a quote whose wording IS a hadith — found in the Sahihayn or in the five
     other books (`hadith_others_index`) — even with no marker at all. That is
     how «الراحمون يرحمهم الرحمن» opened a lesson summary unchallenged.
     Dhikr and du'a formulas («بسم الله»، «الحمد لله»، «اللهم…») taught as
     words to say are not hadith claims unless the text attributes them.

Verdicts on a claim:
  • in the Sahihayn + a citation whose number holds it            → sound
  • in the Sahihayn, citation missing / without a number / wrong  → violation,
    and the message names the right citation
  • found only in the other books, or cited to them               → violation
  • attributed to the Prophet ﷺ but not verbatim anywhere         → violation
    (a paraphrase dressed as a quote, or a saying that is not a hadith)

Matching never loosens: a quote is checked as ONE contiguous run inside ONE
narration; an ellipsis splits it into fragments that must all sit, in order,
in the same narration. A stitched pair still fails.
"""
from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from check_hadith_citations import (  # noqa: E402
    _AR_DIGITS, _load_index, _narrations, cite, locate, skeleton,
)
from check_quran_citations import ALIAS, SURAHS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OTHERS_INDEX = ROOT / "ops/data/hadith_others_index.json.gz"
QURAN = ROOT / "mobile/assets/data/quran.json"

# ── patterns ──────────────────────────────────────────────────────────────
QUOTE = re.compile(r"«([^«»]{2,600})»|“([^“”]{2,600})”|\"([^\"\n]{2,600})\"|'([^'\n]{2,400})'|﴿([^﴾]{1,1500})﴾")

_PROPHET = (r"(?:النبي|النبيّ|النبيُّ|رسول\s*الله|رسولُ\s*الله|الرسول|المصطفى|نبيّ?نا|نبيُّنا)"
            r"(?:\s*محمد)?(?:\s*(?:ﷺ|صلى\s*الله\s*عليه\s*وسلم|صلّى\s*الله\s*عليه\s*وسلّم|\(ﷺ\)|عليه\s*الصلاة\s*والسلام))?"
            r"|ﷺ")
_SPEECH = r"(?:و|ف)?(?:قال|قالَ|يقول|يقولُ|قوله|قولُه|قولِه|وقال|فقال)"
# speech marker that ends right before the quote (only spaces, ':' and «» between)
PROPHETIC_SPEECH = re.compile(
    rf"(?:{_SPEECH}\s*(?:\S+\s*){{0,3}}?(?:{_PROPHET})|(?:{_PROPHET})\s*(?:\S+\s*){{0,2}}?{_SPEECH}"
    rf"|في\s+(?:ال)?حديث(?:\s+(?:النبي|نبوي|شريف|الشريف|صحيح|الصحيح))?|(?:ال)?حديث\s+(?:النبي|نبوي|شريف|الشريف))"
    rf"\s*(?:لنا|لأصحابه|له|لها)?\s*[:：]?\s*$")

# Teaching/reporting verbs: «يعلّمنا النبي ﷺ أن 'إن الله رفيق يحب الرفق في كل شيء'»
# attributes the words as surely as «قال» does — and that exact paraphrase shipped.
# Dhikr taught this way («علّمنا ﷺ أن نقول «بسم الله»») stays exempt: these verbs
# introduce what to say, not a quotation of his speech.
_TEACH = (r"(?:و|ف)?(?:يعلّ?منا|علّ?منا|يعلّ?مُنا|أخبر(?:نا)?|يخبر(?:نا)?|أوصى|يوصي|وصّى|أرشد(?:نا)?|يرشد(?:نا)?"
          r"|حثّ?|يحثّ?|نهى|ينهى|أمر|يأمر|بيّ?ن|يبيّ?ن|ذكّ?ر|يذكّ?ر)")
PROPHETIC_TEACH = re.compile(
    rf"(?:{_TEACH}\s*(?:\S+\s*){{0,2}}?(?:{_PROPHET})|(?:{_PROPHET})\s*(?:\S+\s*){{0,1}}?{_TEACH})"
    rf"\s*(?:نا|لنا)?\s*(?:أن|أنّ|بأن|بأنّ|إن|إنّ|قائلًا|قائلا)?\s*[:：]?\s*$")

# «حديث «…»» / «بحديث: «…»» — the indefinite noun right before a quote names it a
# hadith. The definite «الحديث «…»» is left out: in prose about hadith science it
# introduces metaphors («كأن الحديث «رسالة مسجَّلة»»), not narrations.
INDEF_HADITH = re.compile(r"(?<![ء-ي])[بوف]?حديث\s*[:：]?\s*$"
                          # «يؤكد الهدي النبوي على أن '…'» — attribution by a noun phrase
                          r"|(?:الهدي|التوجيه|القول|المبدأ|الأدب|المنهج)\s+النبوي[^«»“”\"'.؛]{0,30}$")

QURAN_MARKER = re.compile(
    r"(?:قال|يقول|قوله|وقال|فقال)\s*(?:الله\s*)?(?:تعالى|سبحانه(?:\s*وتعالى)?|عزّ?\s*وجلّ?)\s*[:：]?\s*$"
    r"|(?:قال|يقول)\s+الله\s*[:：]?\s*$|(?:في|من)\s+(?:القرآن|كتاب\s+الله|الآية|سورة\s+\S+)\s*[:：]?\s*$")

# Inline citations. Lenient to read, strict to verify.
SAHIH_CITE = re.compile(
    r"(?:صحيح\s+|رواه\s+|أخرجه\s+|عند\s+)?(البخاري|مسلم)\s*[\(\[:،,—\-–]?\s*(?:حديث\s*)?(?:رقم\s*)?"
    r"\(?\s*([٠-٩0-9]{1,5})(?![٠-٩0-9])")
SAHIH_NO_NUMBER = re.compile(r"(?:رواه|أخرجه|روى|رواية|في\s+صحيح)\s+(?:الإمام\s+)?(?:البخاري|مسلم)|متفق\s+عليه|الصحيحين")
OTHER_CITE = re.compile(
    r"(?:رواه|أخرجه|أخرج|روى|عند|في\s+سنن|في\s+مسند|حسّنه|صحّحه)\s+(?:الإمام\s+)?"
    r"(الترمذي|أبو\s*داود|أبي\s*داود|النسائي|ابن\s*ماجه|أحمد|الطبراني|البيهقي|الحاكم|مالك|ابن\s*حبان|الدارمي"
    r"|البزار|ابن\s*أبي\s*شيبة|عبد\s*الرزاق|الدارقطني|أبو\s*يعلى|ابن\s*خزيمة|البخاري\s+في\s+الأدب\s+المفرد)"
    r"|الأدب\s+المفرد")

# «[الروم: ٣٠]» · «(سورة الروم — آية ٣٠)» · «(الروم ٣٠)»
AYAH_CITE = re.compile(r"^\s*[\[\(]?\s*(?:سورة\s+)?([^\d٠-٩\[\]\(\):،—\-–]{2,20}?)\s*[:：،—\-–]?\s*(?:آية|الآية)?\s*([٠-٩0-9]{1,3})")

_DHIKR_START = re.compile(
    r"^(?:(?:نقول|قل|قولي|قولوا|يقول|ردد|ردّد|رددي)\s*:?\s*)?"
    r"(?:بسم\s*الله|باسم\s*الله|الحمد\s*لله|سبحان|الله\s*أكبر|لا\s*إله\s*إلا|أستغفر|اللهم|حسبي\s*الله|حسبنا"
    r"|لا\s*حول|جزاك\s*الله|جزاكم\s*الله|بارك\s*الله|ما\s*شاء\s*الله|إن\s*شاء\s*الله|توكلت|رب\s|ربّ\s|ربنا|ربّنا"
    r"|السلام\s*عليكم|وعليكم|يرحمك\s*الله|يهديكم|آمنت|أعوذ|رضيت\s*بالله|إنا\s*لله|يا\s*حي|اللهمّ|أمسينا|أصبحنا"
    r"|باسمك|صلى\s*الله\s*عليه|اللهم\s*صل|عليه\s*الصلاة)")
_MARKS = re.compile("[\u064b-\u0652\u0670\u0640]")
_SALAWAT = re.compile(r"^(?:صلى\s*الله\s*عليه\s*(?:وآله\s*)?وسلم|عليه\s*الصلاة\s*والسلام|اللهم\s*صل\S*\s*على\s*محمد)$")

_MIN_UNMARKED_WORDS = 3     # a two-word phrase is not evidence of quoting a hadith
_MIN_SKELETON = 9


@dataclass(frozen=True)
class Finding:
    kind: str        # "hadith" | "quran"
    verdict: str     # "ok" | "violation"
    quote: str
    why: str
    fix: str = ""    # the right citation, when there is one


# ── corpora ───────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def corpora():
    idx = _load_index()
    books = idx["books"]
    with gzip.open(OTHERS_INDEX, "rt", encoding="utf-8") as f:
        others = json.load(f)["books"]
    raw = json.loads(QURAN.read_text(encoding="utf-8"))
    per_ayah = {int(c): {v["verse"]: skeleton(v["text"]) for v in vs} for c, vs in raw.items()}
    return books, others, per_ayah


@lru_cache(maxsize=1)
def _blobs() -> tuple[str, str, str]:
    """One string per corpus, for a C-speed "is it anywhere at all?" before the
    per-narration walk. Separators are newlines, which no skeleton contains."""
    books, others, per_ayah = corpora()
    sah = "\n".join(t for b in books.values() for v in b.values() for t in _narrations(v))
    oth = "\n".join(t for b in others.values() for t in b.values())
    qur = "\n".join(" ".join(a[k] for k in sorted(a)) for _, a in sorted(per_ayah.items()))
    return sah, oth, qur


def _fragments(quote: str) -> list[str]:
    parts = re.split(r"\s*(?:\.\.\.|…|\.\s\.\s\.|\*)\s*", quote)
    return [s for s in (skeleton(p) for p in parts) if s]


def _in_one(frags: list[str], text: str) -> bool:
    pos = 0
    for f in frags:
        i = text.find(f, pos)
        if i < 0:
            return False
        pos = i + len(f)
    return True


_PROCLITIC = set("فبلكس")


def _aligned(frags: list[str], text: str) -> bool:
    """Like [_in_one], but the run must start and end on word boundaries (an
    attached proclitic ف/ب/ل/ك/س may precede it). Detection only: the skeleton is
    lossy, and a short quote can otherwise "match" the middle of unrelated words
    («لا ضرب، الضرب يؤلم» did, in Bukhari 4623). Verification stays [_in_one]."""
    if not _in_one(frags, text):
        return False
    first, start = frags[0], 0
    while (i := text.find(first, start)) >= 0:
        if i == 0 or text[i - 1] == " " or (text[i - 1] in _PROCLITIC and (i == 1 or text[i - 2] == " ")):
            pos, ok = i + len(first), True
            for f in frags[1:]:
                k = text.find(f, pos)
                if k < 0:
                    ok = False
                    break
                pos = k + len(f)
            if ok and (pos == len(text) or text[pos] == " "):
                return True
        start = i + 1
    return False


def _blob_hit(frags: list[str], blob: str) -> bool:
    return all(f in blob for f in frags)


def sahihayn_locate(frags: list[str]) -> tuple[str, int] | None:
    books, _, _ = corpora()
    if not _blob_hit(frags, _blobs()[0]):
        return None
    if len(frags) == 1:
        return locate(books, frags[0])
    for b in ("البخاري", "مسلم"):
        for n in sorted(books.get(b, {}), key=float):
            if any(_in_one(frags, t) for t in _narrations(books[b][n])):
                return b, int(n)
    return None


def sahihayn_holds(book: str, number: int, frags: list[str]) -> bool:
    books, _, _ = corpora()
    return any(_in_one(frags, t) for t in _narrations(books.get(book, {}).get(str(number), [])))


def others_locate(frags: list[str], aligned: bool = False) -> tuple[str, str] | None:
    _, others, _ = corpora()
    if not _blob_hit(frags, _blobs()[1]):
        return None
    test = _aligned if aligned else _in_one
    for b, ents in others.items():
        for n, t in ents.items():
            if test(frags, t):
                return b, n
    return None


def sahihayn_aligned(frags: list[str]) -> bool:
    books, _, _ = corpora()
    if not _blob_hit(frags, _blobs()[0]):
        return False
    return any(_aligned(frags, t) for b in books.values() for v in b.values() for t in _narrations(v))


@lru_cache(maxsize=1)
def _surahs() -> list[tuple[int, str, list[tuple[int, int]]]]:
    """Each surah as one string (ayahs joined by a space, as recited) + offsets."""
    _, _, per_ayah = corpora()
    out = []
    for s, ayahs in sorted(per_ayah.items()):
        joined, starts = "", []
        for k in sorted(ayahs):
            starts.append((len(joined), k))
            joined += ayahs[k] + " "
        out.append((s, joined, starts))
    return out


def quran_locate(frags: list[str]) -> tuple[int, int] | None:
    """(surah, ayah) where the fragments sit; a quote may run across consecutive ayahs."""
    if not _blob_hit(frags, _blobs()[2]):
        return None
    for s, joined, starts in _surahs():
        if _in_one(frags, joined):
            first = joined.find(frags[0])
            return s, max(k for off, k in starts if off <= first)
    return None


# ── one text ──────────────────────────────────────────────────────────────
_NEXT = 220   # how far after a quote a citation may sit
_PREV = 90


def _citation_after(text: str, end: int, next_quote: int) -> str:
    """The window where this quote's citation may sit. It does not stop at the
    next quote: «…» وذكر منهم «…» (صحيح البخاري — حديث ٦٦٠) shares one citation,
    and the number is then verified against EACH quote it is borrowed for."""
    return text[end:min(len(text), end + _NEXT)]


def _is_dhikr(quote: str) -> bool:
    plain = _MARKS.sub("", quote).replace("ٱ", "ا").replace("إ", "ا").replace("أ", "ا")
    return bool(_DHIKR_START.search(plain.strip(" .،!؟"))
                or _DHIKR_START.search(_MARKS.sub("", quote).strip(" .،!؟")))


def scan_text(text: str) -> list[Finding]:
    """Every scripture claim in one free-text string, with its verdict."""
    if not re.search(r"[ء-ي]", text):
        return []
    out: list[Finding] = []
    quotes = list(QUOTE.finditer(text))
    for i, m in enumerate(quotes):
        q = next(g for g in m.groups() if g is not None)
        is_ayah_brackets = m.group(5) is not None
        before = text[max(0, m.start() - _PREV): m.start()]
        nxt = quotes[i + 1].start() if i + 1 < len(quotes) else len(text)
        after = _citation_after(text, m.end(), nxt)
        frags = _fragments(q)
        if not frags:
            continue
        words = sum(len(f.split()) for f in frags)
        letters = sum(len(f.replace(" ", "")) for f in frags)

        # ── Qur'an ──────────────────────────────────────────────────────
        if is_ayah_brackets or QURAN_MARKER.search(before):
            if letters < 4:
                continue      # an ayah-number ornament such as ﴿١﴾
            where = quran_locate(frags)
            if where is None:
                out.append(Finding("quran", "violation", q,
                                   "نص مقدَّم على أنه آية ولا يطابق المصحف"))
                continue
            ref = AYAH_CITE.search(after[:60])
            if ref:
                name = ALIAS.get(ref.group(1).strip(), ref.group(1).strip())
                if name in SURAHS:
                    sura, ayah = SURAHS.index(name) + 1, int(ref.group(2).translate(_AR_DIGITS))
                    span = len(frags) + max(0, len(q) // 400)
                    if sura != where[0] or not (where[1] <= ayah <= where[1] + span):
                        out.append(Finding("quran", "violation", q,
                                           f"الإحالة ({name} {ayah}) لا تطابق موضع النص "
                                           f"({SURAHS[where[0] - 1]} {where[1]})"))
                        continue
            out.append(Finding("quran", "ok", q, f"{where[0]}:{where[1]}"))
            continue

        strict = bool(PROPHETIC_SPEECH.search(before) or INDEF_HADITH.search(before))
        marked = strict or bool(PROPHETIC_TEACH.search(before))
        if words < 2:
            continue      # one word is not a quotation of anything
        if not marked and (words < _MIN_UNMARKED_WORDS or letters < _MIN_SKELETON):
            continue
        if _is_dhikr(q) and (not strict or _SALAWAT.match(_MARKS.sub("", q).strip(" .،!؟"))):
            continue      # words to say (or the salawat itself), not a claim about his speech
        if not marked and quran_locate(frags):
            continue      # an unbracketed verse, verbatim — the Qur'an check owns ayahs
        if not marked and not (sahihayn_aligned(frags) or others_locate(frags, aligned=True)):
            continue      # ordinary quoted prose
        sah = sahihayn_locate(frags)
        oth = None if sah else others_locate(frags)

        # a hadith claim — find its citation
        cited = (SAHIH_CITE.search(after) or _en_cite_as_ar(after)
                 or SAHIH_CITE.search(before[-60:]))
        other_cited = OTHER_CITE.search(after) or OTHER_CITE.search(before[-60:])
        bare = SAHIH_NO_NUMBER.search(after) or SAHIH_NO_NUMBER.search(before[-60:])
        right = f"«{cite(*sah)}»" if sah else ""
        if other_cited and not cited:
            out.append(Finding("hadith", "violation", q,
                               f"منسوب إلى {other_cited.group(1) or 'الأدب المفرد'} — التطبيق لا يقتبس إلا من الصحيحين"
                               + (f"؛ واللفظ في {right}" if sah else ""), right))
        elif sah is None:
            if oth:
                out.append(Finding("hadith", "violation", q,
                                   f"حديث خارج الصحيحين (في {oth[0]} {oth[1]}) — لا يُقتبس"))
            else:
                out.append(Finding("hadith", "violation", q,
                                   "منسوب إلى النبي ﷺ ولا يوجد بهذا اللفظ في الصحيحين — "
                                   "إما لفظ غير ثابت أو معنى صيغ كأنه نصّ"))
        elif cited:
            book, num = cited.group(1), int(cited.group(2).translate(_AR_DIGITS))
            if sahihayn_holds(book, num, frags):
                out.append(Finding("hadith", "ok", q, f"{book} {num}"))
            else:
                out.append(Finding("hadith", "violation", q,
                                   f"الرقم المذكور ({book} {num}) لا يحمل هذا اللفظ — الصحيح {right}", right))
        elif bare:
            out.append(Finding("hadith", "violation", q, f"الإسناد بلا رقم حديث — {right}", right))
        else:
            out.append(Finding("hadith", "violation", q, f"حديث بلا إسناد — {right}", right))
    return out


class _Cite:
    """An English citation («(Sahih al-Bukhari 6018)») read as the Arabic one."""

    def __init__(self, book: str, number: int):
        self._g = (book, str(number))

    def group(self, i: int) -> str:
        return self._g[i - 1]


def _en_cite_as_ar(text: str):
    m = EN_CITE.search(text or "")
    if not m:
        return None
    return _Cite({"bukhari": "البخاري", "muslim": "مسلم"}[m.group(1).lower()], int(m.group(2)))


# ── English: a citation in the translation must exist in the Arabic ────────
EN_CITE = re.compile(
    r"(?i)\b(?:sahih\s+(?:al-)?)?(bukhari|muslim)\b\s*(?:,|:|#|no\.?|number|hadith)?\s*\(?\s*(\d{1,5})\b")


def en_citations(text: str) -> set[tuple[str, int]]:
    book = {"bukhari": "البخاري", "muslim": "مسلم"}
    return {(book[m.group(1).lower()], int(m.group(2))) for m in EN_CITE.finditer(text or "")}


def ar_citations(text: str) -> set[tuple[str, int]]:
    return {(m.group(1), int(m.group(2).translate(_AR_DIGITS))) for m in SAHIH_CITE.finditer(text or "")}


# ── self-tests: what shipped must be caught, what is sound must pass ───────
MUST_FLAG = [
    # lesson_7-9_islamic_parenting_akhlaq_02 summary, as shipped (Abu Dawud / al-Tirmidhi)
    "«الراحمون يرحمهم الرحمن». علّم طفلك الرفق بإخوته والحيوان والخادم.",
    # lesson_4-6_islamic_parenting_bond_03 summary (al-Tirmidhi), single quotes
    "يستشهد الدرس بمبدأ 'خيركم خيركم لأهله' وبالرفق في السؤال.",
    # a Sahihayn hadith reworded and dressed as a quote (Bukhari 6927 says «في الأمر كله»)
    "قال النبي ﷺ: «إن الله رفيق يحب الرفق في كل شيء».",
    # right wording, sequential Muslim number
    "قال ﷺ: «إذا مات الإنسان انقطع عنه عمله إلا من ثلاثة» (صحيح مسلم — حديث ٤٢٢٣).",
    # right wording, no citation
    "وفي الحديث: «الكلمة الطيبة صدقة».",
    # cited to a book outside the Sahihayn
    "قال ﷺ: «مروا أولادكم بالصلاة وهم أبناء سبع» رواه أبو داود.",
    # a paraphrase attributed with a teaching verb (lesson 4-6 bond_01, as shipped)
    "يعلّمنا النبي ﷺ أن 'إن الله رفيق يحب الرفق في كل شيء'، والرفق ليس ضعفاً.",
    # a paraphrase attributed by a noun phrase, no speech verb (lesson 4-6 adab_01)
    "يؤكد الهدي النبوي على أن 'إن الله رفيق يحب الرفق في كل شيء'.",
    # a Qur'anic corruption (للذين for للدين — what shipped in Rum 30)
    "قال تعالى: ﴿فأقم وجهك للذين حنيفا﴾",
    # a sound verse cited to the wrong place
    "قال تعالى: ﴿فأقم وجهك للدين حنيفا﴾ [الروم: ٣٢].",
]
MUST_PASS = [
    "قال النبي ﷺ: «إن الله رفيق يحب الرفق في الأمر كله» (صحيح البخاري — حديث ٦٩٢٧).",
    "قال ﷺ: «إذا مات الإنسان انقطع عنه عمله إلا من ثلاثة» (صحيح مسلم — حديث ١٦٣١).",
    "علّمه أن يقول «بسم الله» قبل الأكل و«الحمد لله» بعده.",
    "علّمنا النبي ﷺ أن نقول «بسم الله» قبل الطعام.",
    "قل لطفلك: «أنا أحبك مهما حدث»، ثم اسأله «كيف كان يومك؟».",
    "كان النبي ﷺ رحيمًا بالأطفال، يحملهم ويلاعبهم.",
    "قال تعالى: ﴿فأقم وجهك للدين حنيفا﴾ [الروم: ٣٠].",
    "ما أجمل أن تقول له: «هذا العمل يقرّبك من الجنة».",
]


def self_test() -> str | None:
    """None when the scanner behaves; else what broke."""
    for t in MUST_FLAG:
        if not any(f.verdict == "violation" for f in scan_text(t)):
            return f"لم يُرصد: {t[:60]}"
    for t in MUST_PASS:
        bad = [f for f in scan_text(t) if f.verdict == "violation"]
        if bad:
            return f"رُفض السليم: {t[:50]} — {bad[0].why}"
    return None
