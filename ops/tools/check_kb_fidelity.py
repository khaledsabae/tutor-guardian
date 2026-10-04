#!/usr/bin/env python3
"""
check_kb_fidelity.py — هل ملخّص وحدة المعرفة أمينٌ لمصدرها؟ وهل الحجر صامد؟
================================================================================

المساعد يسترجع `text_simplified` (مع العنوان والوسوم) ويستشهد به «بالدليل».
مراجعو الترجمة يرون العربي والإنجليزي فقط — لا `text_original` — فختمٌ نظيف
يعني أن الإنجليزي يطابق العربي، **لا أن العربي أمينٌ لمصدره**. في ٢٠٢٦-١٠-٠٤
ظهر أن مئات الوحدات بُنيت على نصّ PDF مستخرج **مقلوب الحروف** (وبعضه بخطٍّ
مبدَّل الحروف فوق القلب)، فكتب النموذج «ملخّصًا» لنصٍّ لم يقرأه: قصةٌ للنبي ﷺ
مع الحسن ومصدرها ابن عمر يعلّم أبناءه، و«ناطقشلا» تُفسَّر سلوكًا وهي «الشيطان»
مقلوبة.

الكاشف (scan) — ثلاث عائلات، لكل وحدة أساسية حيّة (غير `__en`):

  (أ) المصدر غير مقروء آليًّا
      reversed            حروف الكلمات وترتيبها مقلوبان (استخراج بالترتيب البصري)
      partially_reversed  مقاطع مقلوبة وسط نصٍّ سليم
      glyph_substituted   حروف بديلة يستحيل وجودها في العربية (خطّ mylotus المكسور:
                          ؿ مكان م، ؾ مكان ل، ػ ؼ ؽ …) — النص لا يُقرأ ولو عُكس
      missing_glyphs      «(cid:NNN)» — حروف لم يُعرف ما هي أصلًا
  (ب) ملاحظات النموذج بدل المحتوى
      meta_unreadable     «لا يمكن استخراج…»، «النص غير واضح/مفهوم»، «الحروف مشوهة»
      meta_framing        «النص يتحدث عن…» — يصف نصًّا بدل أن ينقل مضمونه
  (ج) الملخّص يُدخل ما ليس في المصدر (المصدر يُقرأ بالاتجاهين: كما هو ومعكوسًا)
      introduces_prophet / introduces_companion / introduces_scripture /
      introduces_number / introduces_medical

  الحكم الآلي **علامة للقراءة لا حكم**: ملخّصٌ أمين فوق مصدرٍ قبيح الاستخراج يبقى
  (ويُسجَّل في سجل «فُحص وأُبقي» مربوطًا ببصمة نصّه)؛ والملفّق يُحجر.

الحارس (check) — pre-commit و CI:
  1. self-tests أولًا؛ تعطّل التطبيع أو انقلاب حالة مرجعية ← exit 2.
     نجاحٌ كاذب على نصٍّ يُنسب للنبي ﷺ أسوأ من غياب الفحص.
  2. المسحوب لا يرجع صامتًا (انحدار b1100ae2: ٣٩ وحدة محجوزة أعادتها تشغيلة ترجمة
     إلى `knowledge_base/units/` فعاشت سبعة أسابيع على الإنتاج). لكل وحدة في
     `ops/data/kb_fidelity/quarantined.json`، ولكل مصدرٍ عربيّ مسحوب في أرشيف
     `ops/data/en_unpublished/` (ما ذهب إلى `kb_units_source/`):
       - لا ملف في مساره القديم، ولا معرّفه في وحدة حيّة تحت أي اسم ملف،
       - ولا ترجمةٌ (`<id>__en`) له، ولا ذكرٌ له في units_index.json،
       - ونسخته في الأرشيف موجودة (السجل لا يفقد دليله).
     سحبُ الإنجليزي وحده شأنُ بوابة الإنجليزي: يُراقَب مساره القديم فقط، لتعود
     ترجمةٌ مراجَعة من بابها.
     إعادة النشر ممكنة — لكن **بقرار ظاهر**: يُصحَّح العربي أمام مصدره، ويُعاد
     الملف، ويُحذف سجلّه من quarantined.json ومن MANIFEST الأرشيف في الكوميت نفسه.
  3. لا وحدة حيّة تحمل علامة من الكاشف إلا وهي في `judged_faithful.json` **ببصمة
     نصّها الحالي**. تغيّر النص ← سقط الحكم وأُعيد السؤال. وحدةٌ جديدة من PDF
     مقلوب بمعرّفٍ جديد تُمسَك هنا لا في قائمة المعرّفات.
  4. `is_published: false` على وحدة معرفة لا يخفيها: المحمِّل لا يقرأ إلا
     EXCLUDED_SOURCES، فالوحدة «المحجوبة» تُسترجَع ويُستشهَد بها. السحب نقلٌ لا علَم.

Exit (check): 0 سليم · 1 مخالفات · 2 الفحص نفسه معطّل

Usage:
    python3 ops/tools/check_kb_fidelity.py scan [--json OUT] [--flagged-only]
    python3 ops/tools/check_kb_fidelity.py show ID [ID ...]
    python3 ops/tools/check_kb_fidelity.py check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNITS_DIR = ROOT / "knowledge_base" / "units"
UNITS_INDEX = ROOT / "knowledge_base" / "units_index.json"
# The verdicts of a read, one record per unit: why it was withdrawn, or the
# exact text that was judged faithful.
FIDELITY_DIR = ROOT / "ops" / "data" / "kb_fidelity"
QUARANTINE_RECORD = FIDELITY_DIR / "quarantined.json"
KEEP_LEDGER = FIDELITY_DIR / "judged_faithful.json"
# Where withdrawn units physically live (shared with review_en_parity.py
# `unpublish --with-source`, which also cleans the English queue). Every
# knowledge-unit entry there gets the same "never silently back" protection.
EN_UNPUBLISHED_MANIFEST = ROOT / "ops" / "data" / "en_unpublished" / "MANIFEST.json"

# ── text folding ────────────────────────────────────────────────────────────

# Harakat, Qur'anic marks, superscript alef and tatweel. U+0653..0655 are in this
# range too, so the glyph metric below is computed *before* folding.
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_AR_WORD = re.compile(r"[ء-يٱ-ۓ]+")
_LATIN_WORD = re.compile(r"[A-Za-z]+")
_PRESENTATION = re.compile(r"[ﭐ-﷿ﹰ-﻿]")
# Letters that do not exist in Arabic prose. A PDF font whose ToUnicode map is
# broken (the «mylotus» face in Shamela exports) emits them in place of م ل ن ق
# ف ك, so «على» arrives as «طؾك». U+0653..0655 left over after NFC composition
# are the same font's lam-alef ligatures (ٓ = لا, ٕ = لأ, ٔ = لآ).
_ODD_GLYPHS = re.compile(r"[ػ-ؿ]")
_ORPHAN_HAMZA_MADDA = re.compile(r"(?<![اويى])[ٓ-ٕ]")
_CID = re.compile(r"\(cid:\d+\)")


def fold(text: str) -> str:
    """NFKC (presentation forms → letters, ﻻ → لا), no harakat, no tatweel,
    hamza-carrier alefs unified, ى/ي kept apart (they carry the orientation signal)."""
    t = unicodedata.normalize("NFKC", text or "")
    t = _DIACRITICS.sub("", t)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
    return t


def dereverse(text: str) -> str:
    """Undo visual-order extraction: reverse the folded string, then put digit
    runs back the right way round (they were left-to-right inside the RTL line)."""
    rev = fold(text)[::-1]
    return re.sub(r"\d+", lambda m: m.group(0)[::-1], rev)


# ── (أ) orientation and glyph integrity ────────────────────────────────────

# High-frequency words whose reversal is not itself a word. Palindromes (هذه،
# لل…) carry no signal and are left out. Folded spelling (no hamza on alef).
_FWD_WORDS = frozenset("""
في من على الى الله ان التي الذي هذا عن مع كان اذا ذلك بين عند الطفل الاطفال قال
ولا وهو هو هي لم لن كما حتى او ثم قد كل بعد قبل لان عليه وسلم صلى النبي الاولاد
الوالدين الابناء الام الاب يجب لهم له لها منه فيه عليها تعالى رسول
""".split())
_REV_WORDS = frozenset(w[::-1] for w in _FWD_WORDS) - _FWD_WORDS


@dataclass
class Orientation:
    tokens: int = 0
    forward: int = 0
    reverse: int = 0
    odd_glyphs: int = 0
    letters: int = 0
    cid: int = 0
    presentation: int = 0

    @property
    def score(self) -> float:
        """Share of orientation evidence that says «reversed» (0 = forward, 1 = reversed)."""
        n = self.forward + self.reverse
        return self.reverse / n if n else 0.0

    @property
    def glyph_ratio(self) -> float:
        return self.odd_glyphs / self.letters if self.letters else 0.0


def orientation(text: str) -> Orientation:
    """Count evidence for the reading direction of Arabic text.

    Forward Arabic: words begin with «ال», end in «ة»/«ى», and the common words
    are common. Visual-order extraction flips all three: «ال» becomes a word
    *ending* «لا», «ة»/«ى» start words (impossible in Arabic), and «في» reads «يف».
    Each token votes; the score is the reversed share of the votes.
    """
    o = Orientation()
    raw = unicodedata.normalize("NFC", text or "")
    o.cid = len(_CID.findall(raw))
    o.presentation = len(_PRESENTATION.findall(raw))
    o.odd_glyphs = len(_ODD_GLYPHS.findall(raw)) + len(_ORPHAN_HAMZA_MADDA.findall(raw))
    t = fold(raw)
    o.letters = len(re.findall(r"[ء-يػ-ؿ]", t)) + o.odd_glyphs
    for w in _AR_WORD.findall(t):
        o.tokens += 1
        if len(w) >= 4 and w.startswith("ال"):
            o.forward += 1
        if len(w) >= 4 and w.endswith("لا"):
            o.reverse += 1
        if len(w) >= 2 and w[-1] in "ةى":
            o.forward += 1
        if len(w) >= 2 and w[0] in "ةى":
            o.reverse += 1
        if w in _FWD_WORDS:
            o.forward += 1
        elif w in _REV_WORDS:
            o.reverse += 1
    return o


# Thresholds, calibrated on the 2026-10-04 corpus (1,226 base units):
#   clean Arabic sources      score 0.01–0.08   glyph 0.000
#   visual-order sources      score 0.80–0.97   glyph 0.000
#   Alukah (mylotus + visual) score ≈ 0.85      glyph ≈ 0.046
REVERSED_SCORE = 0.5
PARTIAL_SCORE = 0.15
MIN_VOTES = 8
GLYPH_RATIO = 0.005
MIN_ODD = 5
MIN_CID = 3


def source_flags(text_original: str) -> tuple[list[str], Orientation]:
    o = orientation(text_original)
    flags: list[str] = []
    votes = o.forward + o.reverse
    if votes >= MIN_VOTES and o.score >= REVERSED_SCORE:
        flags.append("reversed")
    elif votes >= MIN_VOTES and o.score >= PARTIAL_SCORE and o.reverse >= MIN_VOTES:
        flags.append("partially_reversed")
    if o.odd_glyphs >= MIN_ODD and o.glyph_ratio >= GLYPH_RATIO:
        flags.append("glyph_substituted")
    if o.cid >= MIN_CID:
        flags.append("missing_glyphs")
    return flags, o


# ── (ب) model meta-notes ───────────────────────────────────────────────────

# The subject is always the *text* — «كلام الطفل غير مفهوم» is a speech-delay
# summary, not a model admitting it could not read its source.
_META_UNREADABLE = re.compile(
    r"لا\s+يمكن(?:ني|نا)?\s+(?:استخراج|فهم|تحليل|تلخيص|قراءة|تحديد|استنتاج)"
    r"|(?:النص|الفقرة|المقطع|المحتوى)\s+(?:\S+\s+){0,2}?غير\s+(?:واضح|مفهوم|مقروء|مترابط|منظم|مرتب|مكتمل|متسق)"
    r"|(?:الحروف|الكلمات|الأحرف|النصوص)\s+(?:\S+\s+){0,2}?(?:مشوهة|مقلوبة|مبعثرة|متداخلة|معكوسة|غير\s+مرتبة)"
    r"|(?:النص|المحتوى)\s+(?:\S+\s+){0,2}?(?:مشوه|مقلوب|معكوس|مبعثر|تالف)"
    r"|بطريقة\s+(?:مشوهة|مقلوبة|معكوسة|غير\s+مفهومة|غير\s+واضحة)"
    r"|ترتيب\s+(?:الحروف|الكلمات)"
    r"|يبدو\s+أن\s+(?:النص|هذا\s+النص|المحتوى)"
    r"|(?:^|[.\n]\s*)عذر[اً]{1,2}[،,]?\s+(?:لا|لم|النص|هذا)"
    r"|\b(?:I\s+cannot|I'm\s+unable|unable\s+to\s+(?:extract|read|understand)|the\s+text\s+(?:is|appears)\s+(?:garbled|unclear|corrupted))",
    re.IGNORECASE,
)
_META_FRAMING = re.compile(
    r"(?:^|[.،\s])(?:هذا\s+)?(?:النص|المقطع|الكتاب|المقال)\s+"
    r"(?:يتحدث|يتناول|يشرح|يذكر|يوضح|يحتوي|يتضمن|يناقش|يقدم|يتعلق|يعرض|يشير|يركز|يهدف|يصف|يبين|يسلط|يدور|يروي)"
    r"|(?:يتحدث|يتناول|يشرح|يذكر|يوضح|يناقش|يعرض|يصف|يبين)\s+(?:هذا\s+)?(?:النص|المقطع|الكتاب)"
)


def meta_flags(text_simplified: str, title: str = "") -> list[str]:
    flags = []
    if any(_META_UNREADABLE.search(t) for t in (text_simplified or "", fold(text_simplified or ""), title or "")):
        flags.append("meta_unreadable")
    if _META_FRAMING.search(fold(text_simplified or "")) or _META_FRAMING.search(text_simplified or ""):
        flags.append("meta_framing")
    return flags


# ── (ج) claims the summary adds ────────────────────────────────────────────


@dataclass(frozen=True)
class Claim:
    name: str
    summary_patterns: tuple[str, ...]     # regex over the folded summary
    source_patterns: tuple[str, ...]      # regex over folded source (either direction) + its English


def _alts(*words: str) -> str:
    return "|".join(words)


# Folded spellings (no hamza on alef, no harakat). Word boundaries are spelled
# out because \b does not treat Arabic letters reliably across Python builds.
_B = r"(?<![ء-ي])"
_E = r"(?![ء-ي])"

# A source that *is* a narration («… رواه البخاري (1423)») carries the Prophet ﷺ
# even when it never spells his name — the hadith text starts at the matn.
_NARRATION = r"(?:رواه|اخرجه|متفق\s+عليه|صحيح\s+البخاري|صحيح\s+مسلم)"

CLAIMS: tuple[Claim, ...] = (
    Claim(
        "introduces_prophet",
        (_B + r"(?:[وفب]?النبي|[وفب]?الرسول|رسول\s+الله|نبينا|المصطفى)" + _E, r"صلى\s+الله\s+عليه\s+وسلم", "ﷺ"),
        (_B + r"(?:[وفلب]?النبي|[وفلب]?الرسول|[وفلب]?لنبي|رسول|نبينا|النبوي|النبوية|المصطفى|محمد)" + _E,
         r"صلى\s*الله\s*عليه", "ﷺ", r"عليه\s+الصلاة", _B + _NARRATION + _E,
         r"(?i)\b(?:prophet|messenger|muhammad|pbuh)\b"),
    ),
    Claim(
        "introduces_scripture",
        # Bare «الحديث» is also «modern» (العلم الحديث) and «talk» (آداب الحديث):
        # only the forms that can only mean a narration count.
        (_B + r"(?:حديث\s+(?:نبوي|شريف|صحيح|رقم)|الحديث\s+(?:النبوي|الشريف|الصحيح|القدسي)|في\s+الحديث|"
         r"حديث\s+قدسي|احاديث|الاحاديث|رواه|اخرجه|البخاري|الترمذي|ابو\s+داود|النسائي|ابن\s+ماجه|صحيح\s+مسلم|"
         r"رواه\s+مسلم|قال\s+تعالى|قوله\s+تعالى|يقول\s+تعالى|الاية|اية|سورة|القران)" + _E, "﴿"),
        (_B + r"(?:حديث|الحديث|احاديث|رواه|اخرجه|البخاري|مسلم|الترمذي|داود|النسائي|ماجه|احمد|تعالى|الاية|اية|"
         r"ايات|سورة|القران|قال|يقول)" + _E, "﴿", "»", "«", r"\(\d+\)",
         r"(?i)\b(?:hadith|narrated|bukhari|muslim|quran|qur'an|verse|surah|allah)\b"),
    ),
    Claim(
        "introduces_medical",
        (_B + r"(?:[وب]?دواء|[وب]?الدواء|ادوية|الادوية|جرعة|جرعات|ملغ|مجم|ملغم|مضاد\s+حيوي|مضادات|"
         r"فيتامين|مكملات|مكمل|حقنة|ميلاتونين|ريتالين|ميثيلفينيديت|باراسيتامول|ايبوبروفين|مسكن|مهدئ|"
         r"هرمون|جراحة|جراحية)" + _E,),
        (_B + r"(?:دواء|الدواء|ادوية|الادوية|علاج|العلاج|جرعة|ملغ|مجم|مضاد|مضادات|فيتامين|مكمل|مكملات|حقنة|"
         r"ميلاتونين|ريتالين|منبهات|مسكن|مهدئ|هرمون|جراحة|طبيب|الطبيب)" + _E,
         r"(?i)\b(?:medic\w*|drug\w*|dose\w*|dosage|mg|antibiotic\w*|vitamin\w*|supplement\w*|injection\w*|"
         r"melatonin|ritalin|methylphenidate|stimulant\w*|paracetamol|acetaminophen|ibuprofen|hormone\w*|surg\w*|"
         r"treatment\w*|pharmac\w*)\b"),
    ),
)

# Companions and early figures, one pair per name: (as the summary names them,
# evidence the source names them too). Several names are also common words —
# «الحسن» (good), «عمر» (age), «سعيد» (happy), «معاذ الله», «انس» — so both sides
# are spelled as the name, never the bare word.
COMPANIONS: tuple[tuple[str, str], ...] = (
    (r"ابن\s+عباس", r"عباس"),
    (r"(?:ابن|عبد\s*الله\s+بن)\s+عمر" + _E, r"(?:ابن|بن)\s+عمر" + _E),
    (r"عمر\s+(?:بن\s+الخطاب|رضي)|الفاروق", r"الخطاب|الفاروق|عمر\s+(?:بن|رضي)"),
    (r"ابن\s+مسعود", r"مسعود"),
    (r"اب[وي]\s+هريرة", r"هريرة"),
    (r"اب[وي]\s+بكر" + _E, r"بكر" + _E + r"|الصديق"),
    (r"علي\s+(?:بن\s+ابي\s+طالب|رضي)", r"طالب|علي\s+(?:بن|رضي)"),
    (_B + r"عثمان" + _E, r"عثمان"),
    (_B + r"عائشة" + _E, r"عائشة|عايشة"),
    (_B + r"فاطمة" + _E, r"فاطمة"),
    (r"الحسن\s+(?:بن\s+علي|والحسين|رضي)|(?<![ء-ي])الحسين" + _E,
     r"الحسين|حسين|الحسن\s+(?:بن|والحسين|رضي)|حسن\s+(?:بن|او)|الحسنين|سبط"),
    (r"انس\s+(?:بن\s+مالك|رضي)|عن\s+انس" + _E, r"انس\s+(?:بن|رضي)|عن\s+انس|مالك"),
    (r"معاذ\s+(?:بن\s+جبل|رضي)", r"جبل|معاذ\s+(?:بن|رضي)"),
    (_B + r"خديجة" + _E, r"خديجة"),
    (_B + r"اسامة" + _E, r"اسامة"),
    (_B + r"بلال" + _E, r"بلال"),
    (r"جابر\s+(?:بن|رضي)", r"جابر"),
    (r"اب[وي]\s+ذر" + _E, r"ذر" + _E),
    (r"ام\s+سلمة", r"سلمة"),
    (r"اب[وي]\s+سعيد", r"اب[وي]\s+سعيد|الخدري"),
    (_B + r"لقمان" + _E, r"لقمان"),
)
# «رضي الله عنه» with no listed name: the source must name *someone* with a
# kunya/nasab or carry the formula itself.
_RADI = (r"رضي\s+الله\s+عن", r"رضي\s*الله|رضى\s*الله|(?:ابن|بن|ابو|ابي|ام)\s+[ء-ي]{3,}")

_AR_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NUMBER_WORDS = {
    # cardinal / ordinal stems → value (folded spelling)
    "واحد": 1, "الاول": 1, "اثنان": 2, "اثنين": 2, "الثاني": 2, "ثلاث": 3, "ثلاثة": 3, "الثالث": 3,
    "الثالثة": 3, "اربع": 4, "اربعة": 4, "الرابع": 4, "الرابعة": 4, "خمس": 5, "خمسة": 5, "الخامس": 5,
    "الخامسة": 5, "ست": 6, "ستة": 6, "السادس": 6, "السادسة": 6, "سبع": 7, "سبعة": 7, "السابع": 7,
    "السابعة": 7, "ثمان": 8, "ثماني": 8, "ثمانية": 8, "الثامن": 8, "الثامنة": 8, "تسع": 9, "تسعة": 9,
    "التاسع": 9, "التاسعة": 9, "عشر": 10, "عشرة": 10, "العاشر": 10, "العاشرة": 10, "عشرون": 20,
    "عشرين": 20, "ثلاثون": 30, "ثلاثين": 30, "اربعون": 40, "اربعين": 40, "خمسون": 50, "خمسين": 50,
    "ستون": 60, "ستين": 60, "سبعون": 70, "سبعين": 70, "مئة": 100, "مائة": 100, "سنتين": 2, "سنتان": 2,
    "شهرين": 2, "اسبوعين": 2, "يومين": 2, "ساعتين": 2,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "hundred": 100,
}
# Prefixes that glue onto a number word in Arabic («وسبع», «بالسابعة», «للعاشرة»).
_NUM_PREFIX = re.compile(r"^(?:و|ف|ب|ل|ك)?(?:ال)?")


def numbers_in(text: str) -> set[int]:
    t = fold(text).translate(_AR_INDIC)
    out: set[int] = set()
    for m in re.findall(r"\d+(?:[.,]\d+)?", t):
        try:
            out.add(int(float(m.replace(",", "."))))
        except ValueError:
            continue
    for w in _AR_WORD.findall(t) + [x.lower() for x in _LATIN_WORD.findall(t)]:
        if w in _NUMBER_WORDS:
            out.add(_NUMBER_WORDS[w])
            continue
        stem = _NUM_PREFIX.sub("", w, count=1)
        for cand in (stem, "ال" + stem):
            if cand in _NUMBER_WORDS:
                out.add(_NUMBER_WORDS[cand])
                break
    return out


# Reference numbers are not claims: «(صحيح البخاري — حديث ٦٦٠)», «رواه مسلم (2699)»,
# «[الأحزاب: 21]». check_scripture / the hadith guards verify those against the
# corpus; here they would only flag a correct citation whose source quotes
# another narration of the same hadith.
# Only a number *glued* to a collection, «حديث رقم» or a bracketed sura name is
# a reference — «حديث الأم مع طفلها 10 دقائق» and «الطفل المسلم … 10 ساعات» keep
# their figures.
_N = r"[\d٠-٩]+(?:\s*[-–]\s*[\d٠-٩]+)?"
_CITATION_NUM = re.compile(
    _B + r"(?:صحيح\s+البخاري|البخاري|صحيح\s+مسلم|رواه\s+مسلم|اخرجه\s+مسلم|مسلم|ابي\s+داود|ابو\s+داود|"
    r"الترمذي|النسائي|ابن\s+ماجه|الالباني)"
    r"\s*[—–:-]?\s*(?:حديث\s*)?(?:رقم\s*)?[(\[]?\s*" + _N
    + r"|" + _B + r"حديث\s*(?:رقم\s*)?[(\[]?\s*" + _N
    + r"|" + _B + r"(?:سورة\s+[ء-ي]+|الاية|اية)\s*[:-]?\s*" + _N
    + r"|[(\[]\s*(?:سورة\s+)?[ء-ي]{3,}(?:\s+[ء-ي]{3,})?\s*:?\s*" + _N + r"\s*[)\]]"
)


def _age_numbers(age_group: str) -> set[int]:
    """«7-9» → {7, 8, 9}: a summary may restate its own age band («(٧-٩ سنوات)»)."""
    nums = sorted(numbers_in(age_group or ""))
    if len(nums) == 2 and 0 <= nums[0] <= nums[1] <= 25:
        return set(range(nums[0], nums[1] + 1))
    return set(nums)


def claim_flags(text_simplified: str, text_original: str, age_group: str = "") -> list[str]:
    """Names and claims the summary carries that the source does not.

    The source is searched in both reading directions, because a reversed
    extraction still *contains* «ملسو هيلع للها ىلص» — it is the summary that is
    unfaithful, not the extraction that hides the evidence. A source that is
    empty (authored content, no PDF behind it) has nothing to be faithful to and
    is not judged here.
    """
    src_raw = text_original or ""
    if len(_AR_WORD.findall(fold(src_raw))) + len(_LATIN_WORD.findall(src_raw)) < 20:
        return []
    summ = fold(text_simplified or "")
    src = fold(src_raw) + "\n" + dereverse(src_raw)
    flags: list[str] = []
    for c in CLAIMS:
        if any(re.search(p, summ) for p in c.summary_patterns) and not any(
            re.search(p, src) for p in c.source_patterns
        ):
            flags.append(c.name)
    named = [(s, e) for s, e in COMPANIONS if re.search(s, summ)]
    if any(not re.search(e, src) for s, e in named) or (
        not named and re.search(_RADI[0], summ) and not re.search(_RADI[1], src)
    ):
        flags.append("introduces_companion")
    # Numbers: a figure in the summary (age, dose, percentage, count) the source
    # never states. 1 and 2 are left out — «طفل واحد», «الوالدين» read as numbers.
    figures = _CITATION_NUM.sub(" ", fold(text_simplified or ""))
    extra = {n for n in numbers_in(figures) if n > 2} - numbers_in(src) - _age_numbers(age_group)
    if extra:
        flags.append("introduces_number")
    return flags


# ── unit-level verdict ─────────────────────────────────────────────────────

SOURCE_FLAGS = ("reversed", "partially_reversed", "glyph_substituted", "missing_glyphs")
META_FLAGS = ("meta_unreadable", "meta_framing")
CLAIM_FLAGS = tuple(c.name for c in CLAIMS) + ("introduces_companion", "introduces_number")


@dataclass
class Verdict:
    id: str
    file: str
    source_file: str
    flags: list[str] = field(default_factory=list)
    score: float = 0.0
    glyph_ratio: float = 0.0

    @property
    def flagged(self) -> bool:
        return bool(self.flags)


def unit_fingerprint(unit: dict) -> str:
    """Binds a «judged faithful» record to the exact text that was judged."""
    h = hashlib.sha256()
    for key in ("title", "text_simplified", "text_original"):
        h.update((unit.get(key) or "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def judge_unit(unit: dict, file: str = "") -> Verdict:
    src_flags, o = source_flags(unit.get("text_original") or "")
    flags = src_flags + meta_flags(unit.get("text_simplified") or "", unit.get("title") or "")
    flags += claim_flags(unit.get("text_simplified") or "", unit.get("text_original") or "",
                         str(unit.get("age_group") or ""))
    return Verdict(
        id=unit.get("id") or Path(file).stem,
        file=file,
        source_file=unit.get("source_file") or "",
        flags=flags,
        score=round(o.score, 3),
        glyph_ratio=round(o.glyph_ratio, 4),
    )


def is_translation(path: Path, unit: dict) -> bool:
    return path.stem.endswith("__en") or bool(unit.get("translated_from"))


KNOWLEDGE_LOADER = ROOT / "backend" / "app" / "services" / "knowledge_loader.py"


def excluded_sources(loader: Path = KNOWLEDGE_LOADER) -> frozenset[str]:
    """`EXCLUDED_SOURCES` as the backend reads it — those units never reach retrieval.

    Parsed, not imported: the CI job that runs this guard has no pydantic. If the
    assignment cannot be found the guard must not quietly widen or narrow its
    scope, so the caller treats `None` as a broken check.
    """
    import ast

    tree = ast.parse(loader.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "EXCLUDED_SOURCES" for t in node.targets
        ):
            return frozenset(ast.literal_eval(node.value))
    raise LookupError(f"EXCLUDED_SOURCES not found in {loader}")


def is_served(unit: dict, excluded: frozenset[str]) -> bool:
    return (unit.get("source_file") or "") not in excluded


def load_live_units(units_dir: Path = UNITS_DIR) -> dict[Path, dict]:
    out: dict[Path, dict] = {}
    for fp in sorted(units_dir.glob("*.json")):
        try:
            out[fp] = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out[fp] = {}
    return out


# ── the guard ──────────────────────────────────────────────────────────────


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def quarantine_violations(
    root: Path,
    live: dict[Path, dict],
    records: list[dict],
    en_unpublished: list[dict],
    index_ids: set[str],
) -> list[str]:
    """A withdrawn unit must not be live again — by path, by id, or by translation.

    `records` are this tool's verdicts (`quarantined.json`); `en_unpublished` is
    the shared archive manifest. An Arabic source withdrawn there (`to` under
    `kb_units_source/`) is held to the same id-level rule. An English-only
    withdrawal is the English gate's business: only its old path is watched, so
    a reviewed re-translation can come back through that gate.
    """
    out: list[str] = []
    live_ids = {u.get("id") for u in live.values() if u.get("id")}
    live_paths = {p.resolve() for p in live}

    def gone(uid: str, why: str) -> None:
        for live_id in (uid, f"{uid}__en"):
            if live_id in live_ids:
                out.append(f"QUARANTINE: unit id {live_id} is live again ({why})")
            if live_id in index_ids:
                out.append(f"QUARANTINE: units_index.json still lists {live_id}")

    for e in records:
        uid = e.get("id", "")
        for mv in e.get("files", []):
            frm = (root / mv["from"]).resolve()
            if frm in live_paths or frm.exists():
                out.append(f"QUARANTINE: {mv['from']} is back at its live path ({uid}: {e.get('category')})")
            if not (root / mv["to"]).exists():
                out.append(f"QUARANTINE: archive copy {mv['to']} is missing — the record lost its evidence")
        gone(uid, f"{e.get('category')}: quarantined {e.get('on')}")
    for e in en_unpublished:
        if e.get("kind") != "kb_units":
            continue
        frm = (root / e.get("from", "")).resolve()
        if frm in live_paths or frm.exists():
            out.append(f"EN_UNPUBLISHED: {e.get('from')} is back at its live path ({e.get('key')})")
        if "/kb_units_source/" in e.get("to", ""):
            gone(Path(e["to"]).stem, f"source withdrawn {e.get('on')}")
    return out


def unpublished_flag_violations(live: dict[Path, dict]) -> list[str]:
    """`is_published: false` on a knowledge unit hides nothing: the loader reads only
    EXCLUDED_SOURCES, so such a unit is still retrieved and cited. A unit that must
    not be served is moved out of knowledge_base/units/, with its reason."""
    return [f"UNPUBLISHED-BUT-SERVED: {fp.name} says is_published=false, but the KB loader ignores that flag — "
            f"it is retrieved and cited. Withdraw it (review_en_parity.py unpublish --with-source) instead"
            for fp, u in live.items() if u and u.get("is_published") is False]


def ledger_violations(
    live: dict[Path, dict], ledger: dict[str, dict], excluded: frozenset[str] = frozenset()
) -> tuple[list[str], list[str], int]:
    """Every flagged *served* base unit must carry a «judged faithful» record for its current text.

    Units of an excluded source are on disk but never retrieved; the day a source
    leaves EXCLUDED_SOURCES its units come into scope here and must be read.
    """
    out: list[str] = []
    stale: list[str] = []
    flagged = 0
    live_base_ids = set()
    for fp, unit in live.items():
        if not unit or is_translation(fp, unit) or not is_served(unit, excluded):
            continue
        live_base_ids.add(unit.get("id"))
        v = judge_unit(unit, fp.name)
        if not v.flagged:
            continue
        flagged += 1
        rec = ledger.get(v.id)
        if rec is None:
            out.append(f"FIDELITY: {v.id} ({v.source_file or '—'}) flagged {v.flags} and never judged — "
                       f"read it (`check_kb_fidelity.py show {v.id}`), then quarantine it or record it as kept")
        elif rec.get("fingerprint") != unit_fingerprint(unit):
            out.append(f"FIDELITY: {v.id} changed since it was judged faithful on {rec.get('judged_on')} — "
                       f"re-read it and re-record the verdict")
    for uid in sorted(set(ledger) - live_base_ids):
        stale.append(uid)
    return out, stale, flagged


# ── self-tests ─────────────────────────────────────────────────────────────

_FWD_SAMPLE = (
    "من أهمل تعليم ولده ما ينفعه وتركه سدى فقد أساء إليه غاية الإساءة، وأكثر الأولاد إنما جاء "
    "فسادهم من قبل الآباء وإهمالهم لهم وترك تعليمهم فرائض الدين وسننه، فأضاعوهم صغارا فلم "
    "ينتفعوا بأنفسهم ولم ينفعوا آباءهم كبارا. وقال النبي صلى الله عليه وسلم: كلكم راع وكلكم "
    "مسئول عن رعيته. والتربية في الطفولة هي الأساس الذي يبنى عليه ما بعده."
)


def _visual_order(text: str) -> str:
    """What a visual-order PDF extraction produces: the logical string reversed,
    with digit runs still left-to-right (as «2024 ربنون» in Manhaj_Nabawi_Khulayfi)."""
    return re.sub(r"\d+", lambda m: m.group(0)[::-1], text[::-1])


def _mylotus(text: str) -> str:
    """Approximate the broken-font substitution seen in Alukah_Rights_of_Children.pdf."""
    return text.translate(str.maketrans({"م": "ؿ", "ل": "ؾ", "ن": "ـ", "ف": "ػ", "ق": "ؼ", "ك": "ؽ"}))


def self_test() -> list[str]:
    fails: list[str] = []

    def expect(cond: bool, what: str) -> None:
        if not cond:
            fails.append(what)

    fwd, _ = source_flags(_FWD_SAMPLE)
    expect(fwd == [], f"clean forward Arabic must carry no source flag (got {fwd})")
    rev, o = source_flags(_visual_order(_FWD_SAMPLE))
    expect("reversed" in rev, f"visual-order text must read as reversed (score {o.score:.2f})")
    pres = unicodedata.normalize("NFKC", _visual_order(_FWD_SAMPLE))
    # Presentation forms fold to the same letters, so the verdict cannot change.
    expect("reversed" in source_flags(pres)[0], "folding must not change the reversed verdict")
    glyph, og = source_flags(_visual_order(_mylotus(_FWD_SAMPLE)))
    expect("glyph_substituted" in glyph, f"broken-font text must be glyph_substituted (ratio {og.glyph_ratio:.3f})")
    half = _FWD_SAMPLE + " " + _visual_order(_FWD_SAMPLE) + " " + _FWD_SAMPLE + " " + _FWD_SAMPLE
    part, op = source_flags(half)
    expect("partially_reversed" in part and "reversed" not in part,
           f"a reversed passage inside clean text must be partially_reversed (score {op.score:.2f}, got {part})")
    expect(source_flags("Children need sleep. " * 20)[0] == [], "English prose carries no Arabic source flag")
    expect("missing_glyphs" in source_flags(_FWD_SAMPLE + " (cid:276) (cid:3) (cid:12)")[0], "(cid:N) must be seen")

    expect(dereverse(_visual_order("قال في سنة 2024 كذلك")) == fold("قال في سنة 2024 كذلك"),
           "dereverse must restore word order and keep digit runs readable")

    for s in ("النص غير واضح ولا يمكن استخراج معلومات مفيدة منه.",
              "يبدو أن النص مكتوب بطريقة مقلوبة.", "الحروف في هذا النص مشوهة.",
              "لا يمكن تحليل هذا المقطع لأن الكلمات مبعثرة."):
        expect("meta_unreadable" in meta_flags(s), f"meta-note not caught: {s}")
    expect("meta_framing" in meta_flags("النص يتحدث عن أهمية تعليم الطفل الصلاة."), "«النص يتحدث عن» not caught")
    expect("meta_framing" in meta_flags("هذا النص يتناول آداب الطعام."), "«هذا النص يتناول» not caught")
    for s in ("يجب على الأهل تعليم أطفالهم الصلاة منذ الصغر.", "شجّع طفلك على الحوار واستمع له باهتمام."):
        expect(meta_flags(s) == [], f"plain advice flagged as meta: {s}")

    src_no_prophet = "ينبغي للوالدين أن يعلما الطفل الصدق بالقدوة والحوار، وأن يكافئا السلوك الحسن. " * 3
    expect("introduces_prophet" in claim_flags("كان النبي ﷺ يعلم الأطفال الصدق.", src_no_prophet),
           "a Prophet ﷺ attribution absent from the source must be flagged")
    src_reversed_prophet = _visual_order("وكان النبي صلى الله عليه وسلم يمازح الصغار ويعلمهم الصدق. " * 3)
    expect("introduces_prophet" not in claim_flags("كان النبي ﷺ يمازح الصغار.", src_reversed_prophet),
           "a Prophet mention present in a REVERSED source must count as present")
    expect("introduces_companion" in claim_flags("روى الحسن بن علي رضي الله عنهما قصة.", src_no_prophet),
           "an invented Companion story must be flagged")
    expect("introduces_companion" not in claim_flags("الخلق الحسن أساس التربية.", src_no_prophet),
           "«الحسن» as an adjective is not a Companion")
    expect("introduces_scripture" in claim_flags("وفي الحديث: رواه البخاري.", src_no_prophet),
           "a hadith attribution absent from the source must be flagged")
    expect("introduces_number" not in claim_flags("يبدأ ذلك في سن السابعة.", "يؤمر الطفل بالصلاة لسبع سنين " * 6),
           "«السابعة» and «سبع» are the same number")
    expect("introduces_number" in claim_flags("ينام الطفل 14 ساعة يوميًا.", src_no_prophet),
           "a figure absent from the source must be flagged")
    expect("introduces_medical" in claim_flags("يعطى الطفل ميلاتونين قبل النوم.", src_no_prophet),
           "a medication absent from the source must be flagged")
    expect(claim_flags("كان النبي ﷺ رحيمًا.", "") == [], "authored units (no source) are not judged for fidelity")

    # False positives found while reading the 2026-10-04 flags — each one must
    # stay quiet, and its near-miss must still be caught.
    for s in ("كلام الطفل في هذا العمر غير مفهوم أحيانًا، وهذا طبيعي.", "علّم طفلك أن يقول عذرًا عندما يخطئ."):
        expect(meta_flags(s) == [], f"advice read as a model meta-note: {s}")
    expect("meta_unreadable" in meta_flags("عذرًا، لا يمكنني فهم هذا النص."), "an apology meta-note must be caught")
    expect("introduces_scripture" not in claim_flags("العلم الحديث يؤكد أهمية آداب الحديث مع الطفل.", src_no_prophet),
           "«الحديث» meaning modern / talk is not a hadith")
    narration = ("سبعة يظلهم الله في ظله يوم لا ظل الا ظله: الامام العادل، وشاب نشا في عبادة الله، "
                 "ورجل قلبه معلق في المساجد، ورجلان تحابا في الله. رواه البخاري (1423) عن ابي هريرة.")
    cited = "ذكّره بقول النبي ﷺ: «وشاب نشأ في عبادة ربه» (صحيح البخاري — حديث ٦٦٠)."
    got = claim_flags(cited, narration)
    expect("introduces_prophet" not in got, f"a source that is itself a narration carries the Prophet ﷺ (got {got})")
    expect("introduces_number" not in got, f"a hadith reference number is not a claimed figure (got {got})")
    expect("introduces_number" in claim_flags("حديث الأم مع طفلها 15 دقيقة يوميًا يكفي.", src_no_prophet),
           "a figure after «حديث» meaning talk is still a figure")
    expect("introduces_number" in claim_flags("الطفل المسلم يحتاج 11 ساعة نوم.", src_no_prophet),
           "«المسلم» is not «صحيح مسلم» — its figure is still a figure")
    expect("introduces_number" not in claim_flags("ابنك (١٣-١٥ سنة) يحتاج حوارًا هادئًا.", src_no_prophet, "13-15"),
           "a summary restating its own age band introduces nothing")
    expect("introduces_number" in claim_flags("ابنك (١٣-١٥ سنة) يحتاج حوارًا هادئًا.", src_no_prophet, "4-6"),
           "an age band that is neither the unit's nor the source's is still a claim")

    # Guard plumbing on a scratch tree: a quarantined id back in units/ must fail.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        arch = root / "ops" / "data" / "en_unpublished"
        (root / "knowledge_base" / "units").mkdir(parents=True)
        (arch / "kb_units_source").mkdir(parents=True)
        (arch / "kb_units").mkdir(parents=True)
        (arch / "kb_units_source" / "isl-x.json").write_text("{}", encoding="utf-8")
        records = [{"id": "isl-x", "category": "unfaithful", "on": "2026-10-04",
                    "files": [{"from": "knowledge_base/units/isl-x.json",
                               "to": "ops/data/en_unpublished/kb_units_source/isl-x.json"}]}]
        expect(quarantine_violations(root, {}, records, [], set()) == [], "clean quarantine must pass")
        back = root / "knowledge_base" / "units" / "isl-x__en.json"
        back.write_text(json.dumps({"id": "isl-x__en"}), encoding="utf-8")
        live = {back: {"id": "isl-x__en"}}
        expect(any("isl-x__en" in v for v in quarantine_violations(root, live, records, [], set())),
               "a re-created translation of a quarantined unit must fail (the b1100ae2 shape)")
        back.unlink()
        expect(any("units_index" in v for v in quarantine_violations(root, {}, records, [], {"isl-x"})),
               "a quarantined id left in units_index.json must fail")
        renamed = root / "knowledge_base" / "units" / "isl-x-restored.json"
        expect(any("isl-x" in v for v in quarantine_violations(root, {renamed: {"id": "isl-x"}}, records, [], set())),
               "a quarantined id restored under another file name must fail")
        (root / "ops" / "data" / "en_unpublished" / "kb_units_source" / "isl-x.json").unlink()
        expect(any("evidence" in v for v in quarantine_violations(root, {}, records, [], set())),
               "a record whose archived copy vanished must fail")

        # The shared archive: a withdrawn *source* is held by id; an English-only
        # withdrawal leaves its Arabic live and must not trip the guard.
        src_out = [{"key": "isl-z__en", "kind": "kb_units", "from": "knowledge_base/units/isl-z.json",
                    "to": "ops/data/en_unpublished/kb_units_source/isl-z.json"}]
        en_out = [{"key": "isl-w__en", "kind": "kb_units", "from": "knowledge_base/units/isl-w__en.json",
                   "to": "ops/data/en_unpublished/kb_units/isl-w__en.json"}]
        z = root / "knowledge_base" / "units" / "isl-z-v2.json"
        expect(any("isl-z" in v for v in quarantine_violations(root, {z: {"id": "isl-z"}}, [], src_out, set())),
               "a source withdrawn in en_unpublished must not come back under a new file name")
        w = root / "knowledge_base" / "units" / "isl-w.json"
        expect(quarantine_violations(root, {w: {"id": "isl-w"}}, [], en_out, set()) == [],
               "an English-only withdrawal leaves its Arabic unit legitimately live")
        expect(unpublished_flag_violations({w: {"id": "isl-w", "is_published": False}}) != [],
               "is_published=false on a knowledge unit hides nothing — it must be reported")
        expect(unpublished_flag_violations({w: {"id": "isl-w"}}) == [], "a plain unit is not a violation")

        loader = root / "loader.py"
        loader.write_text('X = 1\nEXCLUDED_SOURCES = (\n    "a.pdf",\n    "b.pdf",\n)\n', encoding="utf-8")
        expect(excluded_sources(loader) == frozenset({"a.pdf", "b.pdf"}), "EXCLUDED_SOURCES must parse")

    bad = {"id": "isl-y", "title": "t", "text_simplified": "النص غير مفهوم.", "text_original": _FWD_SAMPLE}
    fp = Path("isl-y.json")
    v, _, _ = ledger_violations({fp: bad}, {})
    expect(len(v) == 1, "a flagged unit with no verdict must fail")
    v, _, _ = ledger_violations({fp: bad}, {"isl-y": {"fingerprint": unit_fingerprint(bad)}})
    expect(v == [], "a flagged unit judged on its current text must pass")
    v, _, _ = ledger_violations({fp: {**bad, "text_simplified": "النص غير مفهوم أبدًا."}},
                                {"isl-y": {"fingerprint": unit_fingerprint(bad)}})
    expect(len(v) == 1, "editing a judged unit must drop the verdict")
    v, _, _ = ledger_violations({fp: {**bad, "source_file": "gov.pdf"}}, {}, frozenset({"gov.pdf"}))
    expect(v == [], "a unit of an excluded (never retrieved) source is out of scope")
    return fails


# ── commands ───────────────────────────────────────────────────────────────


def cmd_scan(json_out: str | None, flagged_only: bool) -> int:
    live = load_live_units()
    excluded = excluded_sources()
    rows = []
    for fp, unit in live.items():
        if not unit or is_translation(fp, unit):
            continue
        v = judge_unit(unit, fp.name)
        if flagged_only and not v.flagged:
            continue
        rows.append({"id": v.id, "file": v.file, "source_file": v.source_file, "flags": v.flags,
                     "served": is_served(unit, excluded),
                     "reversed_score": v.score, "glyph_ratio": v.glyph_ratio,
                     "fingerprint": unit_fingerprint(unit)})
    flagged = [r for r in rows if r["flags"] and r["served"]]
    counts: dict[str, int] = {}
    for r in flagged:
        for f in r["flags"]:
            counts[f] = counts.get(f, 0) + 1
    base = [u for p, u in live.items() if u and not is_translation(p, u)]
    print(f"scanned base units: {len(base)} ({sum(1 for u in base if is_served(u, excluded))} served)")
    print(f"flagged (served): {len(flagged)}")
    for k in SOURCE_FLAGS + META_FLAGS + CLAIM_FLAGS:
        if counts.get(k):
            print(f"  {k:22s} {counts[k]}")
    if json_out:
        Path(json_out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"→ {json_out}")
    return 0


def cmd_show(ids: list[str]) -> int:
    live = {u.get("id"): (fp, u) for fp, u in load_live_units().items() if u}
    for uid in ids:
        if uid not in live:
            print(f"## {uid}: not live")
            continue
        fp, unit = live[uid]
        v = judge_unit(unit, fp.name)
        src = unit.get("text_original") or ""
        readable = dereverse(src) if {"reversed", "partially_reversed"} & set(v.flags) else fold(src)
        print(f"## {uid}  [{v.source_file}]  flags={v.flags}  score={v.score}  glyph={v.glyph_ratio}")
        print(f"TITLE: {unit.get('title')}")
        print(f"SUMMARY: {unit.get('text_simplified')}")
        print(f"SOURCE ({'de-reversed' if readable is not src and 'reversed' in ' '.join(v.flags) else 'folded'}):")
        print(readable)
        print()
    return 0


def cmd_check(root: Path = ROOT) -> int:
    """The guard. `root` is the repository (a scratch tree in the tests)."""
    units_dir = root / UNITS_DIR.relative_to(ROOT)
    record_p = root / QUARANTINE_RECORD.relative_to(ROOT)
    ledger_p = root / KEEP_LEDGER.relative_to(ROOT)
    fails = self_test()
    if fails:
        print("⛔ check_kb_fidelity self-tests failed — the guard cannot be trusted:")
        for f in fails:
            print(f"   ✗ {f}")
        return 2
    try:
        records_doc = _load_json(record_p, None)
        ledger_doc = _load_json(ledger_p, None)
        en_unpub = _load_json(root / EN_UNPUBLISHED_MANIFEST.relative_to(ROOT), [])
        index = _load_json(root / UNITS_INDEX.relative_to(ROOT), {})
    except json.JSONDecodeError as e:
        print(f"⛔ a fidelity record is not valid JSON: {e}")
        return 2
    if (not isinstance(records_doc, dict) or not isinstance(records_doc.get("units"), list)
            or not isinstance(ledger_doc, dict) or not isinstance(ledger_doc.get("units"), dict)):
        print(f"⛔ {record_p.relative_to(root)} or {ledger_p.relative_to(root)} is missing or malformed — "
              "the guard has nothing to enforce, which is not the same as clean")
        return 2
    records, ledger = records_doc["units"], ledger_doc["units"]
    live = load_live_units(units_dir)
    if not live:
        print(f"⛔ no units under {units_dir.relative_to(root)} — refusing to report a clean empty corpus")
        return 2
    try:
        excluded = excluded_sources(root / KNOWLEDGE_LOADER.relative_to(ROOT))
    except (OSError, SyntaxError, ValueError, LookupError) as e:
        print(f"⛔ cannot read EXCLUDED_SOURCES from the backend ({e}) — the guard's scope is unknown")
        return 2
    index_ids = {u.get("id") for u in index.get("units", [])}
    errors = quarantine_violations(root, live, records, en_unpub, index_ids)
    errors += unpublished_flag_violations(live)
    lv, stale, flagged = ledger_violations(live, ledger, excluded)
    errors += lv
    n_live = sum(1 for p, u in live.items() if u and not is_translation(p, u) and is_served(u, excluded))
    withdrawn = sum(1 for e in en_unpub if e.get("kind") == "kb_units" and "/kb_units_source/" in e.get("to", ""))
    print(f"🔍 KB fidelity: {n_live} served base units · {flagged} carry a detector flag · "
          f"{len(ledger)} judged faithful · {len(records)} quarantined by this review · "
          f"{withdrawn} withdrawn sources held")
    if stale:
        print(f"🟡 {len(stale)} judged-faithful record(s) for units no longer live (harmless): {stale[:5]}")
    if errors:
        print(f"❌ {len(errors)} fidelity/quarantine violation(s):")
        for e in errors[:60]:
            print(f"   ✗ {e}")
        if len(errors) > 60:
            print(f"   … and {len(errors) - 60} more")
        return 1
    print("✅ quarantine holds; every flagged live unit was read and judged on its current text")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--json")
    s.add_argument("--flagged-only", action="store_true")
    sh = sub.add_parser("show")
    sh.add_argument("ids", nargs="+")
    sub.add_parser("check")
    sub.add_parser("self-test")
    a = ap.parse_args()
    if a.cmd == "scan":
        return cmd_scan(a.json, a.flagged_only)
    if a.cmd == "show":
        return cmd_show(a.ids)
    if a.cmd == "self-test":
        fails = self_test()
        for f in fails:
            print(f"✗ {f}")
        print("self-tests:", "FAILED" if fails else "ok")
        return 2 if fails else 0
    return cmd_check()


if __name__ == "__main__":
    sys.exit(main())
