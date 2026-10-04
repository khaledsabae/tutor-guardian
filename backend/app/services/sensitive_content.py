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
unambiguous stems match as substrings; short words only as whole words, with
the endings each may take (منوم → منومة، منومات), so «جنسيته» (his
nationality) or «مهدي» (a name) never trip the screen. Egyptian euphemisms are
matched in their context, not alone (PR #26 review F6): «قلة أدب» is rudeness
until it is «فيديوهات قلة أدب»; «حاجة وحشة» is a misdeed until someone «عمل
فيه حاجة وحشة»; «جرعة» is a dose next to a number or a medicine, not in
«جرعة حنان»; «علاج» is a medicine when the child takes it.

The extraction model also labels what it returns (child_memory.EXTRACT_PROMPT:
"sensitive": true), and a labelled fact or follow-up is dropped — a second
reader for the phrasings no list will ever finish.

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
# Whole words (normalised), each with the endings it may take.
_HARM_WORDS = (
    "عري", "خمر(?:ه)?", "شابو", "فودو", "موس", "مخدر(?:ه|ات)?", "جنسي",
    "بيره", "بيرا", "نبيذ", "ويسكي", "فودكا",
)
# Phrases whose meaning is in the context (normalised text; Egyptian and MSA).
_HARM_PATTERNS = (
    # hurting oneself, any person, tense or aspect: يضرب/بيضرب/ضربت نفسها…
    r"(?<![ء-ي])(?:[يتن]|ب[يتن]|[هح][يتن])?(?:ضرب|جرح|وذي|اذي|عور|حرق|خنق|عض)"
    r"(?:ت|وا|ي)?\s+(?:في\s+)?نفس(?:ه|ها|ي|هم|و)(?![ء-ي])",
    # cutting: بتشرط ايدها، يشرط، شرطت
    r"(?<![ء-ي])(?:[يت]|ب[يت]|[هح][يت])شرط(?:ت|وا|ي)?(?![ء-ي])",
    r"(?<![ء-ي])شرطت\s+(?:ايد|دراع|نفس)",
    # obscene media, by euphemism: فيديوهات قلة أدب، أفلام وحشة، صور وحشة
    r"(?:فيديو\S*|افلام|فيلم|صور|مقاطع|مقطع|مواقع|موقع|كليبات|كليب|حاجات)\s+"
    r"(?:\S+\s+)?(?:قله\s+ادب|وحشه|وحشين|خارجه|قذره|سافله|مش\s+كويسه)",
    # without clothes: من غير هدوم، بدون ملابس
    r"(?:من\s+غير|بدون|بلا|من\s+دون)\s+(?:هدوم|ملابس|لبس|هدومه|هدومها)",
    # private parts, by euphemism: حتة وحشة، مكان وحش، منطقة حساسة
    r"(?:حته|حتت|مكان|اماكن|منطقه|مناطق)\s+(?:وحشه|وحش|وحشين|حساسه|خاصه|عيب)",
    # something done TO the child: عمل فيه حاجة وحشة
    r"(?:عمل|عملت|عملوا|يعمل|بيعمل|بتعمل|تعمل)\s+(?:فيه|فيها|معاه|معاها|فيا|فينا)\s+"
    r"(?:حاجه|حاجات)\s+(?:وحشه|وحشين|عيب|غلط|مش\s+كويسه)",
    # inhalants: بيشم كلة، يشم بنزين
    r"(?<![ء-ي])(?:[يت]|ب[يت])?شم(?:م|ت|وا)?\s+(?:ال)?(?:كله|كوله|غرا|بنزين|تنر|سلسيون)(?![ء-ي])",
    # alcohol, drunk: بيشرب بيرة/خمرة
    r"(?:يشرب|بيشرب|شرب|بتشرب|تشرب)\s+(?:ال)?(?:بيره|بيرا|خمر|نبيذ|ويسكي|فودكا|كحول)",
)
_HARM_EN = (
    r"suicid", r"kill (?:him|her|my)sel(?:f|ves)", r"self[- ]?harm",
    r"(?:cut|cuts|cutting|hurt|hurts|hurting|hit|hits|hitting) (?:him|her)self",
    r"wants? to die", r"wish(?:es)? to die", r"razor", r"sexual", r"\bsex\b",
    r"molest", r"\brape", r"porn", r"\bnude", r"naked", r"masturbat", r"\babus",
    r"\bdrugs?\b", r"cocaine", r"heroin", r"marijuana", r"cannabis", r"\bweed\b",
    r"alcohol", r"\bdrunk\b", r"\bbeer\b", r"\bwine\b", r"vodka", r"whisk(?:e)?y",
    r"sniff(?:s|ing)? glue", r"inappropriate(?:ly)? touch", r"private parts",
)

_MED_STEMS = (
    "ريتالين", "ستراتيرا", "ميثيلفينيديت", "اديرال", "ميلاتونين",
    "بروزاك", "فلوكستين", "سيرترالين", "زولوفت",
    "لوسترال", "سيبرالكس", "اسيتالوبرام", "ديباكين", "فالبروات", "تيجريتول",
    "كيبرا", "لاموتريجين", "فنتولين", "كورتيزون", "بريدنيزولون", "بنادول",
    "باراسيتامول", "بروفين", "ايبوبروفين", "اموكسيسيلين", "مضاد حيوي",
    "مضادات حيويه", "انسولين", "مهديات", "منومات", "بخاخ", "روشته", "وصفه طبيه",
    "بوصفه الطبيب", "علاج دوايي", "ادويه نفسيه",
)
_MED_WORDS = (
    "دواء", "دوا(?:ه|ها|يه)?", "ادويه", "منوم(?:ه|ات)?", "مهدي(?:ه|ات)",
    "حقن(?:ه|ات)?", "ملغ", "ملجم", "مجم", "حباي(?:ه|ات)", "اقراص", "كبسول(?:ه|ات)?",
    "الجرعه", "جرعته", "جرعتها", "جرعتين",
)
_MED_PATTERNS = (
    # brand names however they are spelled: كونسرتا/كونسيرتا، ريسبريدون/ريسبيريدال
    r"كونس(?:ي)?ر[تط]ا", r"ريسب(?:ي)?ري?د(?:ون|ال)",
    # taking a treatment: بياخد علاج، يتناول دواء، اخد حبوب
    r"(?<![ء-ي])(?:[يتن]|ب[يتن]|[هح][يتن])?(?:اخد|اخذ|تناول)(?:ت|وا|ه|ها)?\s+"
    r"(?:ال)?(?:علاج|دوا|دواء|ادويه|حبوب|حبايه|حبايات|اقراص|برشام|كبسولات|حقن)",
    # pills for something: حبوب منومة، حبوب للتركيز
    r"حبوب\s+(?:ال)?(?:منوم|مهدي|للنوم|للتركيز|للصرع|للاكتئاب|للقلق|دوا|علاج)",
    # a dose — next to a number or a medicine, not «جرعة حنان»
    r"(?<![ء-ي])جرع(?:ه|ات)\s+(?:من\s+)?(?:\d|ال?دوا|ال?دواء|ال?علاج|ريتالين|ميلاتونين|كونس)",
    r"\d+\s*جرع",
)
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
    # `words` are already normalised regex fragments (they carry their endings).
    parts += [rf"(?<![{_LETTER}])(?:[وف])?(?:[بلك])?(?:ال)?(?:{w})(?![{_LETTER}])"
              for w in words]
    parts += list(english) + list(extra)
    return re.compile("|".join(parts), re.IGNORECASE)


_HARM_RE = _compile(_HARM_STEMS, _HARM_WORDS, _HARM_EN, _HARM_PATTERNS)
_MED_RE = _compile(_MED_STEMS, _MED_WORDS, _MED_EN, _MED_PATTERNS + (_DOSE_AR,))


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
