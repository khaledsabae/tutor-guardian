"""What child memory must never keep — and what a follow-up must never quote.

Two families of content, screened on every remembered fact (all categories),
every follow-up strategy and every parent note (review of PR #26, A1/P5):

* **harm** — self-harm and suicide, abuse and assault, sexual content, drugs
  and alcohol. A question containing any of it is not learned from at all.
* **medication** — names of medicines, doses, prescriptions, and statements
  that the child takes medication. Dropped wherever it appears; the rest of
  the question can still be learned from.

Matched on spelling-normalised text (privacy.normalize_ar: hamza/alef forms,
ة/ه, ى/ي, tashkeel) in Arabic — MSA and Egyptian — and English. Long,
unambiguous stems match as substrings; short words only as whole words, so
«جنسيته» (his nationality) or «مهدي» (a name) never trip the screen.

A screen like this has false positives by design: losing one fact costs a
little personalisation; keeping one of these costs the trust the product
runs on.
"""
from __future__ import annotations

import re

from app.services.privacy import normalize_ar

_LETTER = "ء-ي"

# Stems that cannot be part of an innocent longer word: substring match.
_HARM_STEMS = (
    # self-harm / suicide
    "انتحار", "ينتحر", "تنتحر", "انتحر", "يقتل نفسه", "تقتل نفسها", "اقتل نفسي",
    "نفسه يموت", "نفسها تموت", "عايز يموت", "عايزه تموت", "عاوز يموت",
    "عاوزه تموت", "يتمني الموت", "تتمني الموت", "يوذي نفسه", "توذي نفسها",
    "بيوذي نفسه", "بتوذي نفسها", "ايذاء النفس", "اذيه نفسه", "اذي نفسه",
    "يجرح نفسه", "تجرح نفسها", "بيجرح نفسه", "بتجرح نفسها", "جرح نفسه",
    "جرح نفسها", "يجرح ذراع", "تجرح ذراع", "يجرح يده", "يجرح ايده", "بيقطع ايده",
    "بيقطع يده", "يشرط", "بيشرط", "تشريط", "بالموس", "شفره حلاقه",
    # abuse / assault
    "تحرش", "اتحرش", "متحرش", "اعتداء جنسي", "اعتدي عليه", "اعتدي عليها",
    "تعرض لاعتداء", "تعرضت لاعتداء", "اغتصاب", "اغتصب", "لمس غير لائق",
    "لمسه في مكان", "لمسها في مكان", "اماكن حساسه", "مكان حساس", "تعنيف", "معنف",
    "يعنفه", "اساءه جنسيه",
    # sexual content
    "اعضاء تناسل", "عضو تناسل", "تناسلي", "اباحي", "بورن", "سكس", "صور عاريه",
    "صورا عاريه", "عاريه", "عريان", "العاده السريه", "عاده سريه", "استمناء",
    "شذوذ", "مثلي الجنس", "ميول جنسيه", "علاقه جنسيه", "محتوي جنسي",
    "افلام جنسيه", "اسئله جنسيه", "الامور الجنسيه", "مواضيع جنسيه",
    "ثقافه جنسيه",
    # drugs / alcohol
    "مخدرات", "حشيش", "بانجو", "استروكس", "هيروين", "كوكايين", "ترامادول",
    "تامول", "برشام", "كحول", "سكران",
)
_HARM_WORDS = ("عري", "خمر", "شابو", "فودو", "موس", "مخدر", "جنسي")
_HARM_EN = (
    r"suicid", r"kill (?:him|her|my)sel(?:f|ves)", r"self[- ]?harm",
    r"(?:cut|cuts|cutting|hurt|hurts|hurting) (?:him|her)self",
    r"wants? to die", r"wish(?:es)? to die", r"razor", r"sexual", r"\bsex\b",
    r"molest", r"\brape", r"porn", r"\bnude", r"naked (?:photo|picture|pic)",
    r"masturbat", r"\babus", r"\bdrugs?\b", r"cocaine", r"heroin", r"marijuana",
    r"cannabis", r"\bweed\b", r"alcohol", r"\bdrunk\b",
)

_MED_STEMS = (
    "ريتالين", "كونسيرتا", "ستراتيرا", "ميثيلفينيديت", "اديرال", "ميلاتونين",
    "ريسبريدال", "ريسبيريدون", "بروزاك", "فلوكستين", "سيرترالين", "زولوفت",
    "لوسترال", "سيبرالكس", "اسيتالوبرام", "ديباكين", "فالبروات", "تيجريتول",
    "كيبرا", "لاموتريجين", "فنتولين", "كورتيزون", "بريدنيزولون", "بنادول",
    "باراسيتامول", "بروفين", "ايبوبروفين", "اموكسيسيلين", "مضاد حيوي",
    "مضادات حيويه", "انسولين", "مهديات", "منومات", "بخاخ", "روشته", "وصفه طبيه",
    "بوصفه الطبيب", "جرعه", "جرعات", "علاج دوايي", "ادويه نفسيه",
)
_MED_WORDS = ("دواء", "دوا", "ادويه", "منوم", "حقن", "حقنه", "ملغ", "ملجم", "مجم")
_MED_EN = (
    r"ritalin", r"concerta", r"strattera", r"methylphenidate", r"adderall",
    r"melatonin", r"risperd", r"prozac", r"fluoxetine", r"sertraline", r"zoloft",
    r"lexapro", r"escitalopram", r"depakote", r"valproate", r"tegretol", r"keppra",
    r"ventolin", r"albuterol", r"inhaler", r"cortisone", r"prednisolone",
    r"panadol", r"paracetamol", r"tylenol", r"ibuprofen", r"advil", r"amoxicillin",
    r"antibiotic", r"insulin", r"sedative", r"sleeping pill", r"medication",
    r"medicine", r"\bdos(?:e|es|age)\b", r"\bpills?\b", r"\btablets?\b",
    r"prescri", r"\d+\s*(?:mg|ml)\b",
)
_DOSE_AR = r"\d+\s*(?:ملغ|ملجم|مجم|مل)(?![" + _LETTER + "])"


def _compile(stems: tuple[str, ...], words: tuple[str, ...], english: tuple[str, ...],
             extra: tuple[str, ...] = ()) -> "re.Pattern[str]":
    parts = [re.escape(normalize_ar(s)) for s in stems]
    # A short word: whole word only, with the particles Arabic attaches to it.
    parts += [rf"(?<![{_LETTER}])(?:[وف])?(?:[بلك])?(?:ال)?{re.escape(normalize_ar(w))}(?![{_LETTER}])"
              for w in words]
    parts += list(english) + list(extra)
    return re.compile("|".join(parts), re.IGNORECASE)


_HARM_RE = _compile(_HARM_STEMS, _HARM_WORDS, _HARM_EN)
_MED_RE = _compile(_MED_STEMS, _MED_WORDS, _MED_EN, (_DOSE_AR,))


def _norm(text: str) -> str:
    return normalize_ar(text or "").lower()


def is_harmful(text: str) -> bool:
    """Self-harm, abuse, sexual content, drugs — never learned, never stored."""
    return bool(_HARM_RE.search(_norm(text)))


def mentions_medication(text: str) -> bool:
    """A medicine, a dose or a prescription — never stored in memory."""
    return bool(_MED_RE.search(_norm(text)))


def must_not_remember(text: str) -> bool:
    return is_harmful(text) or mentions_medication(text)
