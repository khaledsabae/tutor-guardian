"""Child-name redaction before any text leaves for a model or an outside service.

What leaves is the parent's question, recent turns, and prompts built from them
(assistant, coach tip, insights, memory extraction, the Qur'an search, the
offline analyses). Every one goes through this module first: the names of the
family's children are replaced by a placeholder.

**Placeholders.** A family with one child: «طفلي». A family with several: each
child keeps a stable letter by profile order — «الطفل أ», «الطفل ب»… — so a
sibling question stays readable («سارة بتضرب أحمد» → «الطفل أ بتضرب الطفل ب»,
not «طفلي بتضرب طفلي»). When the question is known to be about one child, that
child is «طفلي» and the others keep their letters. Redaction with no family
(logs, offline analyses with no device) uses «طفلي» for every name.

**Matching, in both directions** (review of PR #26, 2026-10-04):
* A name is found however it was typed: hamza/alef forms, ة/ه, ى/ي, tashkeel
  and shadda, «عبدالرحمن» with or without the space, Latin case, common Latin
  transliterations (محمد ↔ Mohamed…), and each token of a multi-word name.
* A name is *not* found where it is an ordinary word: never with «ال»/«لل»
  attached (أركان الإسلام، لصلاة الفجر، سورة النور), not inside a religious
  reference (النبي محمد ﷺ، سورة يوسف — the title is anchored at a word start,
  so «جنبي يوسف» is not «نبي يوسف»), and — for names that are also common
  nouns — not in a construct or a «without»/season phrase (آية الكرسي، دعاء
  النوم، من غير نور، يصوم رمضان).

Best-effort and fail-open on a database error: returning the text unchanged is
the failure mode of an optional enrichment; every caller sits in a path that
must keep working.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional

from app.db.init_db import db_path

logger = logging.getLogger(__name__)

_REPLACEMENT = "طفلي"
# Public name for the same token: child memory (services/child_memory.py) writes
# every stored fact with this placeholder for the fact's own child, so a fact
# can go into any prompt as-is and the app can swap the child's name back in at
# render time, on the device.
CHILD_PLACEHOLDER = _REPLACEMENT
_SIBLING_LETTERS = "أبجدهوزحطيكلمن"


def sibling_placeholder(index: int) -> str:
    """«الطفل أ», «الطفل ب», … for the index-th child of a family (0-based)."""
    letter = _SIBLING_LETTERS[index] if index < len(_SIBLING_LETTERS) else str(index + 1)
    return f"الطفل {letter}"


# ── Normalisation ─────────────────────────────────────────────────────────

_AR_LETTER = r"[ء-يٮ-ۓ]"
_TASHKEEL = "[ً-ْٰـ]"          # harakat, dagger alef, tatweel
_TASHKEEL_RE = re.compile(_TASHKEEL)


def normalize_ar(text: str) -> str:
    """Spelling-insensitive form of Arabic text (for comparison only)."""
    t = _TASHKEEL_RE.sub("", text or "")
    t = re.sub("[أإآٱ]", "ا", t)
    return (t.replace("ة", "ه").replace("ى", "ي")
             .replace("ئ", "ي").replace("ؤ", "و"))


# One normalised letter → the spellings it stands for in the original text.
_LETTER_CLASS = {"ا": "[اأإآٱ]", "ه": "[هة]", "ي": "[يىئ]", "و": "[وؤ]"}


def _letters_pattern(norm: str) -> str:
    parts = []
    for ch in norm:
        if ch == " ":
            parts.append(r"\s+")
            continue
        parts.append(_LETTER_CLASS.get(ch, re.escape(ch)) + f"{_TASHKEEL}*")
    return "".join(parts)


# Attached particles: a conjunction, then a preposition. Never the article —
# «ال»/«لل» + a name is a word, not a child (الإسلام، النور، للنور).
_PREFIX_CHAIN = r"(?:[وف])?(?:[بلك])?"

# Name tokens that are not names on their own.
_STOP_TOKENS = frozenset({"بن", "ابن", "بنت", "ابو", "ام", "ال", "عبد"})

# Cheap Latin ↔ Arabic variants for the commonest names (normalised Arabic).
_LATIN_VARIANTS: dict[str, tuple[str, ...]] = {
    "محمد": ("mohamed", "mohammed", "mohammad", "muhammad", "muhammed", "mohamad"),
    "احمد": ("ahmed", "ahmad"),
    "يوسف": ("youssef", "yousef", "yusuf", "yousif", "yussef"),
    "مريم": ("mariam", "maryam", "meryem"),
    "فاطمه": ("fatima", "fatma", "fatimah"),
    "عمر": ("omar", "umar"),
    "علي": ("ali",),
    "ادم": ("adam",),
    "ساره": ("sara", "sarah"),
    "نور": ("nour", "noor"),
    "ليلي": ("laila", "layla", "leila"),
    "خالد": ("khaled", "khalid"),
    "ابراهيم": ("ibrahim",),
    "زياد": ("ziad", "ziyad"),
    "حمزه": ("hamza", "hamzah"),
    "عايشه": ("aisha", "aysha", "aicha"),
    "هدي": ("huda", "hoda"),
    "ياسين": ("yassin", "yasin", "yaseen"),
    "مصطفي": ("mostafa", "mustafa", "moustafa"),
    "محمود": ("mahmoud", "mahmud"),
    "عبدالله": ("abdullah", "abdallah"),
    "عبدالرحمن": ("abdelrahman", "abdulrahman", "abdalrahman"),
    "جني": ("jana",),
    "ملك": ("malak",),
    "حسن": ("hassan", "hasan"),
    "حسين": ("hussein", "hussain"),
    "زينب": ("zainab", "zeinab"),
    "سلمي": ("salma",),
    "تميم": ("tamim", "tameem"),
    "انس": ("anas",),
    "معاذ": ("moaz", "muadh"),
}
_ARABIC_FOR_LATIN = {v: ar for ar, vs in _LATIN_VARIANTS.items() for v in vs}

# Names that are also everyday or religious words. For these only, a
# construct («آية الكرسي»، «دعاء النوم»), a «without» phrase («من غير نور»)
# or a season phrase («يصوم رمضان») means the word, not the child.
COMMON_NOUN_NAMES = frozenset(normalize_ar(n) for n in (
    "إسلام", "إيمان", "آية", "نور", "هدى", "دعاء", "جنة", "رحمة", "أمل", "حياة",
    "تقوى", "يقين", "سلام", "فرح", "هبة", "ضحى", "بشرى", "صلاح", "وعد", "منى",
    "نصر", "عز", "فجر", "رمضان", "جمعة", "عيد", "بركة", "نعمة", "أمان", "إحسان",
    "رضا", "وفاء", "صفاء", "شروق", "سعادة", "فرحة", "هداية", "بسمة", "نسمة",
))
_SEASON_NAMES = frozenset(normalize_ar(n) for n in ("رمضان", "جمعة", "عيد", "فجر"))
_WITHOUT_BEFORE = re.compile(r"(?<![ء-ي])(?:غير|بدون|بلا|دون)\s*$")
_SEASON_BEFORE = re.compile(
    r"(?<![ء-ي])(?:[وف]?(?:شهر|صيام|صوم|يصوم|تصوم|نصوم|يصومون|يصوموا|"
    r"في|قبل|بعد|خلال|طوال|اول|اخر|نهار|ليالي|ليله|يوم|صلاه|صلاة))\s*$"
)
_CONSTRUCT_AFTER = re.compile(r"^\s+ال")


# Everyday words that a name becomes once ى/ي and ة/ه are folded: «على»
# (علي), «منه» (منة), «مني» (منى), «جني» (جنى)… They count as the child only
# when spelled exactly as the name is.
_FUNCTION_WORDS = frozenset({"علي", "مني", "الي", "حتي", "متي", "لدي", "عني",
                             "اني", "منه", "جني"})


def _strip_tashkeel(text: str) -> str:
    return _TASHKEEL_RE.sub("", text or "")


# ── Religious references ──────────────────────────────────────────────────
# A name a family gives its child is often also the name of a prophet, a surah
# or a companion — محمد ﷺ, سورة يوسف, مريم عليها السلام. A name inside such a
# reference is not the child: a title right before it (anchored at a word
# start — «جنبي يوسف» is not «نبي يوسف»), or an honorific right after it.
_TITLE_BEFORE = re.compile(
    r"(?<![ء-ي])(?:[وفبلك])?(?:النبي|نبي|سيدنا|سيدتنا|السيده|الرسول|رسول|"
    r"سوره|الصحابي|الصحابيه|ام المومنين)\s*$"
)
_HONORIFIC_AFTER = re.compile(
    r"^\s*(?:ﷺ|صلي الله عليه وسلم|عليه السلام|عليها السلام|عليهما السلام"
    r"|عليهم السلام|رضي الله عنه|رضي الله عنها|\(ص\))"
)


def _is_religious_reference(text: str, start: int, end: int) -> bool:
    before = normalize_ar(text[max(0, start - 30):start])
    after = normalize_ar(text[end:end + 40])
    return bool(_TITLE_BEFORE.search(before) or _HONORIFIC_AFTER.match(after))


def _is_common_word_use(norm_name: str, text: str, start: int, end: int) -> bool:
    if norm_name not in COMMON_NOUN_NAMES:
        return False
    before = normalize_ar(text[max(0, start - 20):start])
    if _CONSTRUCT_AFTER.match(text[end:end + 4]):
        return True
    if _WITHOUT_BEFORE.search(before):
        return True
    return norm_name in _SEASON_NAMES and bool(_SEASON_BEFORE.search(before))


# ── Patterns for one name ─────────────────────────────────────────────────


@lru_cache(maxsize=4096)
def _name_variants(name: str) -> tuple[tuple[str, Optional[str]], ...]:
    """(normalised spelling, original spelling or None) that all mean this
    child — longest first.

    The whole name, «عبد» compounds kept whole (their second word may be a
    divine name: الرحمن، الله), each other token of a multi-word name, and
    cheap Latin ↔ Arabic transliterations. The original spelling (tashkeel
    stripped) is what a function-word collision is checked against.
    """
    raw = (name or "").strip()
    if not raw:
        return ()
    out: dict[str, Optional[str]] = {}
    if re.search(r"[A-Za-z]", raw):
        low = raw.lower()
        out[low] = low
        for t in low.split():
            if len(t) >= 2:
                out.setdefault(t, t)
        ar = _ARABIC_FOR_LATIN.get(low)
        if ar:
            out.setdefault(ar, None)
        return tuple(sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True))
    plain = re.sub(r"\s+", " ", _strip_tashkeel(raw))
    plain = re.sub(r"(^|\s)عبد\s+", r"\1عبد", plain)      # عبد الرحمن ≡ عبدالرحمن
    out[normalize_ar(plain)] = plain
    tokens = plain.split()
    if len(tokens) > 1:
        for t in tokens:
            nt = normalize_ar(t)
            if len(nt) >= 2 and nt not in _STOP_TOKENS and not nt.startswith("ال") \
                    and not nt.startswith("عبد"):
                out.setdefault(nt, t)
    for v in list(out):
        for latin in _LATIN_VARIANTS.get(v, ()):
            out.setdefault(latin, latin)
    return tuple(sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True))


@lru_cache(maxsize=4096)
def _variant_pattern(variant: str) -> "re.Pattern[str]":
    if re.search(r"[a-z]", variant):
        return re.compile(rf"(?<![A-Za-z]){re.escape(variant)}(?![A-Za-z])", re.IGNORECASE)
    body = _letters_pattern(variant)
    if variant.startswith("عبد"):
        body = body.replace(_letters_pattern("عبد"), _letters_pattern("عبد") + r"\s?", 1)
    return re.compile(
        rf"(?<!{_AR_LETTER})(?P<prefix>{_PREFIX_CHAIN})(?P<name>{body})(?!{_AR_LETTER})"
    )


def _child_matches(text: str, name: str):
    """(start, end, prefix) of every place `text` names this child."""
    seen: list[tuple[int, int]] = []
    for variant, original in _name_variants(name):
        arabic = not re.search(r"[a-z]", variant)
        for m in _variant_pattern(variant).finditer(text or ""):
            s, e = m.start(), m.end()
            if any(s < pe and ps < e for ps, pe in seen):
                continue                                   # inside a longer variant
            name_start = m.start("name") if arabic else s
            if arabic and variant in _FUNCTION_WORDS and \
                    _strip_tashkeel(m.group("name")) != original:
                continue                                   # «على» is not «علي»
            if _is_religious_reference(text, name_start, e):
                continue
            if arabic and _is_common_word_use(variant, text, name_start, e):
                continue
            seen.append((s, e))
            yield s, e, (m.group("prefix") if arabic else "") or ""


def _with_prefix(prefix: str, placeholder: str) -> str:
    """Re-attach «و/ف/ب/ل/ك» to the placeholder the way Arabic spells it."""
    if not prefix:
        return placeholder
    if placeholder.startswith("ال") and prefix.endswith("ل"):
        return prefix[:-1] + "لل" + placeholder[2:]        # ل + الطفل → للطفل
    return prefix + placeholder


# ── Families ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Family:
    """A device's children in profile order: ((child_id, name), …)."""
    members: tuple[tuple[int, str], ...] = ()

    def placeholder(self, child_id: int, subject_id: Optional[int] = None) -> str:
        if len(self.members) <= 1 or child_id == subject_id:
            return CHILD_PLACEHOLDER
        for i, (cid, _) in enumerate(self.members):
            if cid == child_id:
                return sibling_placeholder(i)
        return CHILD_PLACEHOLDER

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(n for _, n in self.members)


def family_for_device(device_id: Optional[str]) -> Family:
    if not device_id:
        return Family()
    try:
        conn = sqlite3.connect(db_path())
        try:
            rows = conn.execute(
                "SELECT id, name FROM child_profiles WHERE device_id = ? ORDER BY id",
                (device_id,),
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — fail open, never break a request
        logger.debug("privacy: family unavailable: %s", exc)
        return Family()
    return Family(tuple(
        (int(r[0]), (r[1] or "").strip()) for r in rows
        if r[1] and len(r[1].strip()) >= 2
    ))


def _spans(text: str, labelled: Iterable[tuple[str, str]]) -> list[tuple[int, int, str, str]]:
    """Non-overlapping (start, end, prefix, label) for every named mention."""
    found: list[tuple[int, int, str, str]] = []
    # Longest names first so «محمد علي» wins over «محمد».
    for name, label in sorted(labelled, key=lambda x: len(x[0]), reverse=True):
        for s, e, prefix in _child_matches(text, name):
            if any(s < fe and fs < e for fs, fe, _, _ in found):
                continue
            found.append((s, e, prefix, label))
    return sorted(found)


def _replace(text: str, spans: list[tuple[int, int, str, str]]) -> str:
    out, pos = [], 0
    for s, e, prefix, label in spans:
        out.append(text[pos:s])
        out.append(_with_prefix(prefix, label))
        pos = e
    out.append(text[pos:])
    return "".join(out)


def redact_family(text: str, family: Family, subject_id: Optional[int] = None) -> str:
    """Replace each child of `family` by its placeholder (see module doc)."""
    if not text or not family.members:
        return text
    labelled = [(name, family.placeholder(cid, subject_id)) for cid, name in family.members]
    return _replace(text, _spans(text, labelled))


def family_mentions(text: str, family: Family) -> list[int]:
    """Child ids named in `text`, outside religious and common-word uses."""
    if not text:
        return []
    return sorted({cid for cid, name in family.members if next(_child_matches(text, name), None)})


# ── Generic API (kept for callers without a family) ───────────────────────


@lru_cache(maxsize=1)
def _known_names_cached(_epoch: tuple) -> tuple[str, ...]:
    try:
        conn = sqlite3.connect(db_path())
        rows = conn.execute("SELECT name FROM child_profiles").fetchall()
        conn.close()
        names = sorted(
            {(r[0] or "").strip() for r in rows if r[0] and len(r[0].strip()) >= 2},
            key=len,
            reverse=True,  # longest first so "عبد الرحمن" wins over "عبد"
        )
        return tuple(names)
    except Exception as exc:  # noqa: BLE001 — fail open, never break a request
        logger.debug("privacy: child names unavailable: %s", exc)
        return ()


def names_for_device(device_id: str | None) -> tuple[str, ...]:
    """The CALLER's children's names (longest first), or () on any error."""
    return tuple(sorted(family_for_device(device_id).names, key=len, reverse=True))


def mentions_any(text: str, names: tuple[str, ...]) -> bool:
    """True when `text` names one of `names` (same matcher as redaction)."""
    return any(next(_child_matches(text or "", n), None) for n in names)


def _store_epoch() -> tuple:
    """A key that changes whenever the store's contents may have (audit M11)."""
    key = []
    for path in (db_path(), f"{db_path()}-wal"):
        try:
            st = os.stat(path)
            key.append((st.st_mtime_ns, st.st_size))
        except OSError:
            key.append(None)
    return tuple(key)


def known_child_names() -> tuple[str, ...]:
    """Child names from the local store, re-read whenever the store changes."""
    return _known_names_cached(_store_epoch())


def redact_with_names(text: str, names: tuple[str, ...]) -> str:
    """Every one of `names` → «طفلي». For callers with no family structure
    (offline logs and analyses); a family prompt uses redact_family."""
    if not text or not names:
        return text
    return _replace(text, _spans(text, [(n, CHILD_PLACEHOLDER) for n in names]))


def redact_for_cloud(text: str, device_id: str | None = None) -> str:
    """Redact before a cloud call. With a device: that family, distinct
    placeholders; without one: every known name → «طفلي»."""
    if not text:
        return text
    if device_id:
        return redact_family(text, family_for_device(device_id))
    return redact_with_names(text, known_child_names())
