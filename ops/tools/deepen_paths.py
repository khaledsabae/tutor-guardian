#!/usr/bin/env python3
"""
تعميق المسارات بالطلب — دروس مكتوبة من الوحدات، وطعنٌ من عائلة نماذج أخرى
==========================================================================

الاستخدام (بالترتيب):
  python3 ops/tools/deepen_paths.py --spec ops/data/deepen_paths/prayer_religion.json --plan
      يعرض لكل درس في المواصفة الوحدات المرشّحة من قاعدة المعرفة ونصوص الحزمة المسموحة.
  … --check            بوابات حتمية على المسوّدات (عربي + إنجليزي) — بلا شبكة.
  … --review           طعنٌ آلي لكل مسوّدة تغيّر نصّها منذ آخر طعن (متتابع، نداء واحد في كل مرة).
  … --status           حالة كل درس: البوابات، آخر طعن لنصّه الحالي، وما ينقصه ليُقبل.
  … --write            يكتب المقبول فقط إلى المنهج + سجلّ الطعن بجانب المواصفة.

المسوّدات: `<work-dir>/<topic>/<path_id>.drafts.json` — مفتاح كل درس `s01`, `s02`… بترتيب
المواصفة، وفيه `ar` و`en` (الحقول: title, summary, try_this, reflection_prompts, unit_ids,
warning_flags, needs_professional_followup) و`dispositions` (قرارات على ملاحظات الطاعن).

لماذا وُجدت
-----------
المنهج «عريضٌ ضحل»: ٤١ مسارًا بنحو أربعة دروس لكلٍّ، وملخّصات من ١٣٠–٥٠٠ حرف. أمٌّ فتحت
مسارًا فأنهته في جلسة واحدة. وخريطة الطلب (١٬٢٨٤ سؤالًا حقيقيًّا) تقول أين يتعمّق: الصلاة
والدين ← الغضب والعناد ← النوم ← الدراسة ← الشاشات ← الخوف ← الغيرة. الدروس الجديدة
بالشكل اليومي — قراءة دقيقتين إلى ثلاث + فعلٌ واحد لليوم + سؤال تأمّل — داخل مخطّط
الدرس الحالي (`summary` / `try_this` / `reflection_prompts`)، فيعرضها التطبيق بلا سطر كود.

لماذا لا يكتب نموذجٌ المسوّدة (جُرِّب 2026-10-04)
------------------------------------------------
النسخة الأولى من هذه الأداة كانت تولّد المسوّدة بـ`mistral-large-3` ثم تصلحها في حلقة.
كل مسوّدة خرجت بملاحظة «عالية» في الجولة الأولى (تشبيه الله بالشمس، «اسأل طفلك: هل فكرت
من خلق الله؟» — زرعٌ للسؤال لا جواب عنه)، والمُصلِح الإنجليزي أدخل عنصرًا نائبًا لحديث
«لا تغضب» مكان «أعوذ بالله». ومفتاح Ollama مشترك مع وكلاء آخرين يردّ 429 على المراجعين
الاثنين، فصار الدرس ربع ساعة. فانقسم العمل: **المسوّدة يكتبها المؤلّف** (جلسة Claude مُسنَدة
إلى الوحدات)، و**الطعن يبقى آليًّا من عائلة أخرى** (`deepseek-v4-pro`، وبديله `glm-5.2`)،
والبوابات الحتمية قبلهما. لا يُقبل درس إلا وآخر طعنٍ على **نصّه الحالي** بلا ملاحظة عالية،
وكل ملاحظة متوسطة إمّا أُصلحت (فتغيّر النص وأُعيد الطعن) أو رُدّت بسببٍ مكتوب في
`dispositions` يظهر في السجل. الشرعي والطبي لا يُردّ بقرار — يُصلَح أو يسقط الدرس.

النصوص الشرعية: لا تُكتب في المسوّدة أبدًا
------------------------------------------
الحديث من الصحيحين فقط بكتاب ورقم مطابقَين، والقرآن لا يُترجَم، ولا تفسير مولَّد. حرّاس
pre-commit للآيات والأحاديث يفحصون حزمة الأذكار لا دروس المنهج. لذلك المسوّدة لا تحمل نصًّا
شرعيًّا إطلاقًا: تكتب `[[h_009]]` فقط، والأداة تُدخل النص والمصدر حرفيًّا من الحزمة
المتحقَّق منها (`family_adhkar.ar.json`)، بالعربية في اللغتين. وأيّ «قال تعالى» أو «رواه»
أو ﴿ أو أربع كلمات متتالية من نصّ الحزمة خارج العنصر النائب = رفضٌ حتمي.

⚠️ لا تكتب الأداة `approved_by`. سجلّ الطعن لكل درس (`<spec>.review.json`) هو الدليل لا التوقيع.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import math
import os
import re
import sys
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = ROOT / "knowledge_base" / "curriculum"
UNITS = ROOT / "knowledge_base" / "units"
BANK = ROOT / "mobile" / "assets" / "content" / "adhkar" / "family_adhkar.ar.json"
LESSON_INDEX = ROOT / "docs" / "lesson_index.json"

# نستورد أداة الترجمة بدل نسخ ثوابتها: المسرد وقيد الجذور ومراجع الطعن كلها مكوّدة من
# إخفاقات وقعت (٣٤ حقنة مصطلحات). نسخةٌ ثانية = نسختان تنحرفان.
_spec = importlib.util.spec_from_file_location(
    "translate_curriculum", Path(__file__).with_name("translate_curriculum.py"))
tc = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, [sys.argv[0]]
try:
    _spec.loader.exec_module(tc)
finally:
    sys.argv = _argv

AUTHOR = "claude-opus-5-5"                 # كاتب المسوّدة والترجمة — عائلة Anthropic
REVIEW_MODEL = tc.REVIEWER_MODEL           # deepseek-v4-pro — عائلة أخرى
# المفتاح مشترك مع وكلاء آخرين يراجعون بـdeepseek في الوقت نفسه فيردّ 429 لساعات.
# glm-5.2 عائلة ثالثة لا تشارك الكاتب افتراضاته — بديلٌ لا تخفيضٌ للمعيار.
REVIEW_FALLBACK = "glm-5.2"
GENERATED_BY = "ops/tools/deepen_paths.py"

# أنواع الملاحظات التي لا تُردّ بقرار مكتوب ولو كانت متوسطة: تُصلَح أو يسقط الدرس —
# إلا إذا أثبت القرار أن الطاعن مخطئ في الواقعة نفسها (`reviewer_wrong` بدليل).
NON_WAIVABLE = {"sharia", "medical", "religious_error", "fabricated", "safety", "script"}

# ── البوابات الحتمية ─────────────────────────────────────────────────────

AR_LETTER = r"؀-ۿ"
_B = rf"(?<![{AR_LETTER}])"           # حدّ كلمة عربي (يسار)
_E = rf"(?![{AR_LETTER}])"            # حدّ كلمة عربي (يمين)

# عامية — بحدود الكلمة لا بالاحتواء (فلتر ساذج أعطى ١٧ من ١٠٤١ والقراءة ٧٠).
# مع سابقة اختيارية و/ف. القائمة لا تدّعي الشمول؛ الطاعن يكمّلها.
DIALECT_WORDS = [
    "مش", "مافيش", "مفيش", "معلش", "عشان", "علشان", "دلوقتي", "دلوقت", "إزاي",
    "ازاي", "كده", "كدا", "كدة", "بتاع", "بتاعة", "بتاعه", "بتاعك", "اللي", "ده",
    "دي", "إيه", "ايه", "ليه", "فين", "امتى", "إمتى", "زي", "بس", "أوي",
    "اوي", "عايز", "عايزة", "عاوز", "عاوزة", "لسه", "لسة", "برضه", "برضو", "كمان",
    "ماشي", "كويس", "كويسة", "بيحب", "بيشوف", "بيقول", "بتحب", "بنحب",
    "بيعمل", "بتعمل", "هيعمل", "هتعمل", "هنعمل", "خلّيه", "خليه", "خلّيها", "خليها",
    "زعلان", "زعلانة", "يزعل", "تزعل", "إنت", "انتي", "إنتي", "احنا", "إحنا",
    "دلوقتى", "مين", "يلا", "يلّا", "ماما", "بابا",
]
# ليست في القائمة عمدًا لأنها فصيحة أيضًا: «دول» (جمع دولة)، «خالص» (لله)،
# «عيال» (الخلق عيال الله)، «حاجة» (حاجة الطفل).
DIALECT_RE = re.compile(
    _B + r"[وف]?(?:" + "|".join(map(re.escape, DIALECT_WORDS)) + r")" + _E)

# نصّ شرعي كتبه المؤلّف بنفسه. العنصر النائب وحده مسموح.
# «الحديث» وحدها ليست هنا: «الحديث مع طفلك» حوار لا رواية. ولا «سورة»/«آية»:
# «علّمه سورة الفاتحة» ذِكرٌ لا اقتباس. ما يفلت من هنا يمسكه الطاعن.
RELIGIOUS_QUOTE_RE = re.compile(
    r"﴿|﴾|قال\s+تعالى|قوله\s+تعالى|يقول\s+تعالى|قال\s+الله|يقول\s+الله|"
    r"قال\s+رسول|قال\s+النبي|يقول\s+النبي|قال\s*ﷺ|رواه|أخرجه|"
    rf"(?<![{AR_LETTER}])متفق\s+عليه(?![{AR_LETTER}])|"   # «المتفق عليها» لغةٌ عادية
    r"البخاري|صحيح\s+مسلم|الترمذي|أبو\s+داود|ابن\s+ماجه|النسائي|"
    r"حديث\s+شريف|الحديث\s+الشريف|حديث\s+نبوي|الحديث\s+النبوي|في\s+الصحيح")
PLACEHOLDER_RE = re.compile(r"\[\[([a-z]_[0-9_]+)\]\]")

# ما يُسمح به في النص العربي: حروف عربية، أرقام، ترقيم، ﷺ. لا لاتيني ولا غيره.
AR_ALLOWED = re.compile(
    rf"[{AR_LETTER}\s0-9٠-٩\.\,\:\;\!\?\(\)\[\]«»\"'\-–—/%٪…•ﷺ]")
# الإنجليزي: لاتيني وترقيم وﷺ وحروف مُعلَّمة شائعة؛ العربي فقط إن نُقل حرفيًّا من المصدر.
EN_ALLOWED = re.compile(
    r"[A-Za-z\s0-9\.\,\:\;\!\?\(\)\[\]«»\"'\-–—/%…•ﷺ’‘“”āīūḥṣḍṭẓʿʾÁáÉéÍíÓóÚú]")

# البطاقة كلها (الملخّص + فعل اليوم + سؤال التأمّل) نحو ٢٠٠–٤٠٠ كلمة: قراءة
# دقيقتين إلى ثلاث بإيقاع قارئٍ على الهاتف. وأقل من ١٥٠ للملخّص يعود بنا إلى
# الدروس القديمة (٢٠–٨٠ كلمة) التي أُنهيت في جلسة واحدة.
SUMMARY_WORDS = (150, 360)

# التطبيق لا يعرض نصّ `warning_flags` أبدًا: يقرأ منها رمزًا واحدًا
# (`needs_professional_followup`) فيُظهر بطاقة «يستحق المتابعة مع متخصص» وشارة في
# قائمة الدروس (`models.dart`). نحو ٨٠ تحذيرًا حرًّا في الدروس الحالية لا يراها أحد.
# فالدروس الجديدة تكتب علامات الخطر في الملخّص (حيث تُقرأ) والرمز وحده هنا.
WARNING_TOKENS = {"needs_professional_followup"}
TEXT_FIELDS = ("title", "summary", "try_this", "reflection_prompts", "warning_flags")


def _strip_marks(s: str) -> str:
    """حذف التشكيل والتطويل — للمقارنة بنص الحزمة."""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[ً-ٰٟـۖ-ۭ]", "", s)


def _words(s: str) -> list[str]:
    return re.findall(rf"[{AR_LETTER}A-Za-z0-9]+", s)


# كان البخاري وحده حتى نزل ترقيم عبد الباقي لصحيح مسلم في حارس الأحاديث (#27):
# رقمٌ قد يتغيّر تحت الدرس بعد نشره أسوأ من غياب الحديث. نزل، والحزمة تستشهد به،
# والاختبار يثبت أن كل رقمٍ فيها يحمل نصّه في مدوّنة الحارس نفسها.
HADITH_BOOKS_ALLOWED = {"البخاري", "مسلم"}


def load_bank() -> dict:
    data = json.loads(BANK.read_text(encoding="utf-8"))
    return {i["id"]: i for i in data["items"]
            if i.get("kind") == "verse" or (
                i.get("kind") == "hadith"
                and (i.get("provenance") or {}).get("book") in HADITH_BOOKS_ALLOWED)}


def _bank_ngrams(bank: dict, n: int = 4) -> set:
    grams = set()
    for item in bank.values():
        w = _words(_strip_marks(item["text"]))
        for i in range(len(w) - n + 1):
            grams.add(" ".join(w[i:i + n]))
    return grams


def lesson_text_fields(doc: dict) -> list[tuple[str, str]]:
    """النصوص التي يقرؤها الوالد. رموز `warning_flags` ليست نصًّا — تُفحص وحدها."""
    out = [("title", doc.get("title", "")), ("summary", doc.get("summary", "")),
           ("try_this", doc.get("try_this", ""))]
    for i, p in enumerate(doc.get("reflection_prompts") or []):
        out.append((f"reflection_prompts[{i}]", p))
    return out


def arabic_gates(doc: dict, allowed_bank: set, bank_grams: set,
                 usable_units: set) -> list[str]:
    """رفض حتمي. لا رأي هنا — كل بند يمكن التحقق منه آليًّا."""
    probs = []
    for field, text in lesson_text_fields(doc):
        bad = {c for c in PLACEHOLDER_RE.sub(" ", text) if not AR_ALLOWED.match(c)}
        if bad:
            probs.append(f"{field}: محارف غير عربية {sorted(bad)[:8]}")
        for m in DIALECT_RE.finditer(text):
            probs.append(f"{field}: كلمة عامية «{m.group(0)}»")
        body = PLACEHOLDER_RE.sub(" ", text)
        for m in RELIGIOUS_QUOTE_RE.finditer(body):
            probs.append(f"{field}: «{m.group(0)}» — نصٌّ شرعي أو مصدره خارج العنصر النائب")
        w = _words(_strip_marks(body))
        for i in range(len(w) - 3):
            if " ".join(w[i:i + 4]) in bank_grams:
                probs.append(f"{field}: كلمات منقولة من نصّ شرعي — استعمل العنصر النائب")
                break
        for pid in PLACEHOLDER_RE.findall(text):
            if pid not in allowed_bank:
                probs.append(f"{field}: العنصر [[{pid}]] غير مسموح في هذا الدرس")
    ph = PLACEHOLDER_RE.findall(json.dumps(doc, ensure_ascii=False))
    if len(ph) > 1:
        probs.append("أكثر من عنصر نائب واحد")
    if any(PLACEHOLDER_RE.search(t) for f, t in lesson_text_fields(doc) if f != "summary"):
        probs.append("العنصر النائب مكانه الملخّص فقط")

    title = doc.get("title", "")
    if not 3 <= len(title) <= 80:
        probs.append(f"title: الطول {len(title)} — بين ٣ و٨٠ حرفًا")
    summary = doc.get("summary", "")
    nw = len(_words(summary))
    if not SUMMARY_WORDS[0] <= nw <= SUMMARY_WORDS[1]:
        probs.append(f"summary: {nw} كلمة — المطلوب {SUMMARY_WORDS[0]}–{SUMMARY_WORDS[1]}")
    if len(summary) > 2400:
        probs.append(f"summary: {len(summary)} حرفًا — الحد ٢٤٠٠")
    tt = doc.get("try_this", "")
    if not tt.startswith("اليوم:"):
        probs.append("try_this: يبدأ بـ«اليوم:» — فعلٌ واحد لليوم")
    if not 20 <= len(tt) <= 600:
        probs.append(f"try_this: الطول {len(tt)} — بين ٢٠ و٦٠٠ حرف")
    rp = doc.get("reflection_prompts") or []
    if not 1 <= len(rp) <= 2:
        probs.append("reflection_prompts: سؤال واحد أو اثنان")
    for i, p in enumerate(rp):
        if not 10 <= len(p) <= 190:
            probs.append(f"reflection_prompts[{i}]: الطول {len(p)} — بين ١٠ و١٩٠")
        if not p.rstrip().endswith("؟"):
            probs.append(f"reflection_prompts[{i}]: سؤالٌ ينتهي بـ«؟»")
    uids = doc.get("unit_ids") or []
    if not 1 <= len(uids) <= 3 or len(set(uids)) != len(uids):
        probs.append("unit_ids: من وحدة إلى ثلاث، بلا تكرار")
    for u in uids:
        if u not in usable_units:
            probs.append(f"unit_ids: «{u}» ليست وحدة صالحة في قاعدة المعرفة")
    flags = doc.get("warning_flags", [])
    if not isinstance(flags, list) or not set(flags) <= WARNING_TOKENS:
        probs.append(f"warning_flags: الرموز المسموحة {sorted(WARNING_TOKENS)} فقط — "
                     "التطبيق لا يعرض نصًّا حرًّا هنا؛ علامات الخطر مكانها الملخّص")
    if doc.get("needs_professional_followup") is not (
            "needs_professional_followup" in (flags or [])):
        probs.append("needs_professional_followup يطابق وجود الرمز في warning_flags")
    return probs


def _text_only(doc: dict) -> dict:
    return {k: doc[k] for k in TEXT_FIELDS if doc.get(k)}


def english_gates(en: dict, ar: dict) -> list[str]:
    probs = []
    ar_blob = _strip_marks(json.dumps(ar, ensure_ascii=False))
    for field, text in lesson_text_fields(en):
        body = PLACEHOLDER_RE.sub(" ", text)
        # عبارة عربية تُترك كما هي (ذِكرٌ يُقال بلفظه) مسموحة إن كانت في المصدر حرفيًّا.
        for run in re.findall(rf"[{AR_LETTER}][{AR_LETTER}\s]*", body):
            if run.strip() and _strip_marks(run.strip()) not in ar_blob:
                probs.append(f"{field}: Arabic not taken verbatim from the source: {run[:40]!r}")
        body = re.sub(rf"[{AR_LETTER}]", "", body)
        bad = {c for c in body if not EN_ALLOWED.match(c)}
        if bad:
            probs.append(f"{field}: unexpected characters {sorted(bad)[:8]}")
    if sorted(PLACEHOLDER_RE.findall(json.dumps(en))) != \
            sorted(PLACEHOLDER_RE.findall(json.dumps(ar, ensure_ascii=False))):
        probs.append("placeholders differ from the Arabic")
    if not en.get("try_this", "").startswith("Today:"):
        probs.append("try_this must start with 'Today:'")
    if len(en.get("reflection_prompts") or []) != len(ar.get("reflection_prompts") or []):
        probs.append("reflection_prompts: length differs from the Arabic")
    if (en.get("warning_flags") or []) != (ar.get("warning_flags") or []):
        probs.append("warning_flags: tokens must be identical to the Arabic")
    for k in ("title", "summary", "try_this"):
        if not (en.get(k) or "").strip():
            probs.append(f"{k}: missing")
    probs += tc._validate_glossary(_text_only(ar), _text_only(en))
    return probs


# ── النصوص الشرعية: إدخال حرفي من الحزمة ──────────────────────────────

SURAH_EN = {
    "إبراهيم": "Ibrahim", "طه": "Ta-Ha", "لقمان": "Luqman", "مريم": "Maryam",
    "البقرة": "Al-Baqarah", "آل عمران": "Al Imran", "النحل": "An-Nahl",
    "الإسراء": "Al-Isra", "فصلت": "Fussilat", "الفرقان": "Al-Furqan",
    "الأحقاف": "Al-Ahqaf", "التحريم": "At-Tahrim", "الصافات": "As-Saffat",
    "الحشر": "Al-Hashr", "الشعراء": "Ash-Shu'ara", "النمل": "An-Naml",
    "العنكبوت": "Al-Ankabut", "المعارج": "Al-Ma'arij", "الروم": "Ar-Rum",
    "النساء": "An-Nisa", "يوسف": "Yusuf", "الأحزاب": "Al-Ahzab",
    "المؤمنون": "Al-Mu'minun", "القصص": "Al-Qasas", "الكهف": "Al-Kahf",
    "الرعد": "Ar-Ra'd",
}


def _en_source(item: dict) -> str:
    prov = item.get("provenance") or {}
    if prov.get("type") == "quran":
        surah = re.sub(r"^سورة\s+", "", item["source"].split("—")[0].strip())
        name = SURAH_EN.get(surah)
        if not name:
            raise KeyError(f"no English surah name for {surah!r} — add it to SURAH_EN")
        return f"Surah {name}, {prov['surah']}:{prov['ayah']}"
    book = {"البخاري": "Sahih al-Bukhari", "مسلم": "Sahih Muslim"}[prov["book"]]
    # «Sahih al-Bukhari 6927» لا «…, hadith 6927»: حارس النصوص الشرعية لا يقرأ الثانية
    # إسنادًا، فكان الحديث في النسخة الإنجليزية يظهر له بلا مصدر.
    return f"{book} {prov['number']}"


def expand(text: str, bank: dict, lang: str) -> str:
    """العنصر النائب → النص والمصدر حرفيًّا من الحزمة، بالعربية في اللغتين."""
    def rep(m):
        item = bank[m.group(1)]
        if item["kind"] == "verse":
            if lang == "ar":
                return f"قال تعالى: ﴿{item['text']}﴾ [{item['source']}]"
            return f"Allah says: ﴿{item['text']}﴾ [{_en_source(item)}]"
        if lang == "ar":
            return f"قال النبي ﷺ: «{item['text']}» ({item['source']})"
        return f"The Prophet ﷺ said: «{item['text']}» ({_en_source(item)})"
    return PLACEHOLDER_RE.sub(rep, text)


# ── الوحدات ─────────────────────────────────────────────────────────────

_UNITS: dict | None = None
_UNITS_LOCK = threading.Lock()


def units() -> dict:
    """الوحدات الصالحة للإسناد: عربية المصدر، بنصّ مبسّط ذي معنى."""
    global _UNITS
    with _UNITS_LOCK:
        if _UNITS is None:
            loaded = {}
            for f in sorted(UNITS.glob("*.json")):
                if f.name.endswith("__en.json"):
                    continue
                u = json.loads(f.read_text(encoding="utf-8"))
                ts = (u.get("text_simplified") or "").strip()
                if len(ts) < 120 or "غير واضح" in u.get("title", ""):
                    continue
                loaded[u["id"]] = u
            _UNITS = loaded
    return _UNITS


def pick_units(keywords: list, bands: list, pinned: list, k: int = 5) -> list:
    by_id = units()
    missing = [p for p in pinned if p not in by_id]
    if missing:
        raise KeyError(f"pinned units not found/usable: {missing}")
    chosen = [by_id[p] for p in pinned]
    scored = []
    for u in by_id.values():
        if u["id"] in pinned or u.get("age_group") not in bands:
            continue
        hay = " ".join([u.get("title", ""), u.get("behavior_type", ""),
                        " ".join(u.get("labels") or []),
                        " ".join(u.get("keywords") or [])])
        ts = u.get("text_simplified", "")
        s = sum(3 * len(re.findall(kw, hay)) + len(re.findall(kw, ts)) for kw in keywords)
        if s >= 3:
            if u["id"].startswith(("seed-", "gap-")):   # منسَّقة للتطبيق من مراجع موثّقة
                s += 4
            scored.append((s, u["id"], u))
    scored.sort(key=lambda x: (-x[0], x[1]))
    for _, _, u in scored:
        if len(chosen) >= k:
            break
        chosen.append(u)
    return chosen


def unit_brief(u: dict) -> dict:
    return {"id": u["id"], "title": u.get("title", ""), "age_group": u.get("age_group"),
            "reference": (u.get("reference_info") or "")[:160],
            "text": u.get("text_simplified", "")[:1400]}


# ── الطاعن ──────────────────────────────────────────────────────────────

def load_key() -> None:
    """المفتاح يُقرأ داخل بايثون — لا سطر أوامر ولا echo."""
    if os.environ.get("OLLAMA_API_KEY"):
        return
    env = Path.home() / "projects" / "email-twin" / ".env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("OLLAMA_API_KEY="):
            os.environ["OLLAMA_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
            return
    sys.exit("❌ OLLAMA_API_KEY غير موجود")


# المفتاح يردّ 429 على كل النماذج دفعةً واحدة حين تستنفده الوكلاء الآخرون (مُقاس
# 2026-10-04: ثمانية نماذج، 429 خلال ثانية). فالطاعن ينتظر بصبرٍ متصاعد — طلبٌ واحد
# كل بضع دقائق — بدل أن يسقط الدرس أو يضاعف الضغط على مفتاحٍ مشترك.
REVIEW_PATIENCE_S = int(os.environ.get("DEEPEN_REVIEW_PATIENCE_S", 4 * 3600))


def review(system: str, payload: dict) -> tuple[dict, str]:
    """طعنٌ من عائلة غير عائلة الكاتب. 429 على الأساسي → البديل؛ على الاثنين → انتظار."""
    user = json.dumps(payload, ensure_ascii=False)
    deadline = time.time() + REVIEW_PATIENCE_S
    wait = 60
    while True:
        for model in (REVIEW_MODEL, REVIEW_FALLBACK):
            try:
                raw, _ = tc._post(model, system, user)
                return tc._parse_json(raw), model
            except RuntimeError as e:
                if "غير متاح" in str(e):
                    raise
            except (json.JSONDecodeError, ValueError):
                continue
            except http.client.HTTPException:
                # IncompleteRead أسقط تشغيلةً كاملة بعد ست مراجعات: _post يعيد المحاولة
                # على أخطاء الشبكة وحدها، وانقطاع الجسم في منتصفه ليس منها.
                continue
        if time.time() + wait > deadline:
            raise RuntimeError("both reviewers unavailable (429/timeouts) — retry later")
        print(f"    … reviewers busy (429); waiting {wait}s", flush=True)
        time.sleep(wait)
        wait = min(wait * 2, 600)


SYSTEM_REVIEW_LESSON = """You are an ADVERSARIAL reviewer for «المربّي», an Islamic \
parenting app used by Muslim parents across the Arab world. Your job is to FIND \
DEFECTS in the Arabic lesson below, not to approve it. Assume it is flawed.

The lesson is one day of a daily program for parents of children in the age band \
given: a 2–3 minute read (summary), ONE concrete action for today (try_this), and a \
reflection question. Placeholders of the form [[id]] are VERIFIED Qur'an/hadith texts \
the system inserts from a checked bank — their content is listed; judge whether the \
sentence around a placeholder misattributes, misinterprets or over-reads it, but do \
not flag the placeholder itself.

Check, and quote the exact Arabic for each defect:
1. sharia — any Qur'an/hadith text, paraphrase or attribution the author wrote \
(including «في الحديث» or a saying credited to the Prophet ﷺ); a specific sira \
incident; a ruling on a disputed matter (fatwa) or an incorrect/harsh ruling; an \
aqeedah statement contrary to Ahl al-Sunnah; tafsir; frightening children with Hell \
or presenting Allah as a watcher who punishes; recommending hitting or shaming.
2. medical — factual errors; unsafe advice; numbers (hours, ages) contradicting \
mainstream pediatric guidance (AAP/WHO); a red flag that needs a doctor not mentioned.
3. grounding — claims contradicting the knowledge units; statistics, studies or \
named experts that are not in them.
4. age_fit — advice beyond or below the developmental capacity of the band.
5. register — ANY Egyptian/colloquial word or phrase — the required register is easy \
Modern Standard Arabic; also preachy, stiff or awkward phrasing; grammar errors.
6. script — any non-Arabic script or transliteration.
7. pedagogy — try_this is not ONE concrete action doable today, or it asks the parent \
to provoke a problem or plant a doubt/fear; the reflection is not a real question for \
the parent; the summary is not a coherent 2–3 minute read; it repeats another lesson \
of the path (their titles are given).

Severity: "high" = must not ship (sharia, medical safety, fabricated religious text, \
dialect, factual error). "medium" = should be fixed. "low" = polish.
Return JSON only:
{"verdict": "clean" | "defects",
 "defects": [{"type": "...", "field": "...", "quote": "...", "why": "...",
              "severity": "high"|"medium"|"low", "fix": "..."}]}
An empty list on a real lesson is more likely to mean you did not look. Look again \
before returning "clean"."""

# نداءٌ واحد للدرس بلغتيه. السقف مُقاس: «You reached your Pro 5-hour limit» (2026-10-04)
# — حصّة استعمالٍ مشتركة بين الوكلاء تنفد قبل نهاية التشغيلة. نداءان لكل درس كانا
# يضاعفان استهلاك الحصّة بلا فائدة: الطاعن يحتاج النصّين معًا ليحكم على الترجمة أصلًا.
SYSTEM_REVIEW_BOTH = SYSTEM_REVIEW_LESSON.split("Severity:")[0] + """\
ALSO review the ENGLISH translation of the same lesson against the Arabic. Report:
- meaning_change: the English says something the Arabic does not, or omits something it does
- religious_error: an attribution altered; an English rendering of a Qur'anic ayah \
presented as the Qur'an; anything attributed to the Prophet ﷺ that the Arabic does not \
attribute to him
- term_error: an Islamic term translated away instead of transliterated (tarbiyah, \
akhlaq, fitrah, rifq, aqeedah, haya, birr al-walidayn, ihsan, amanah …), or a \
transliterated term the Arabic does not contain
- register: stiff, clinical or preachy English where the Arabic is warm and direct
- structure: a field, list element, honorific or [[id]] token dropped or changed

Severity: "high" = must not ship (sharia, medical safety, fabricated religious text, \
dialect, factual error, meaning change on a religious or medical point). "medium" = \
should be fixed. "low" = polish.
Return JSON only:
{"arabic":  {"verdict": "clean" | "defects", "defects": [{"type": "...", "field": "...",
             "quote": "...", "why": "...", "severity": "high"|"medium"|"low", "fix": "..."}]},
 "english": {"verdict": "clean" | "defects", "contains_religious_text": true | false,
             "defects": [{"type": "...", "field": "...", "quote": "...", "why": "...",
             "severity": "high"|"medium"|"low", "fix": "..."}]}}
"contains_religious_text": does the ARABIC quote or paraphrase a hadith, a Qur'anic verse \
or any statement attributed to the Prophet ﷺ or a companion (placeholders count)?
An empty defect list on a real lesson is more likely to mean you did not look."""

PLACEHOLDER_NOTE = (
    "Tokens of the form [[id]] are verified Qur'an/hadith texts inserted later in "
    "Arabic in both languages; they must appear identically in both versions.")


# ── المواصفة والمسوّدات والطعون ──────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _dump(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _hash(doc: dict) -> str:
    blob = json.dumps({k: doc.get(k) for k in TEXT_FIELDS + ("unit_ids",
                                                             "needs_professional_followup")},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _generated(lid: str) -> bool:
    """درسٌ كتبته هذه الأداة — علامته في سجل ترجمته (الدرس العربي لا يقبل حقلًا زائدًا)."""
    f = CURRICULUM / "i18n" / "en" / "lessons" / f"{lid}.json"
    return f.exists() and \
        (_load(f).get("translation") or {}).get("generated_by") == GENERATED_BY


def _original_lessons(pid: str) -> list:
    """دروس المسار قبل هذه الأداة — أساسٌ ثابت لا يتغيّر بإعادة الكتابة."""
    pfile = CURRICULUM / "paths" / f"{pid}.json"
    if not pfile.exists():
        return []
    return [_load(CURRICULUM / "lessons" / f"{lid}.json")
            for lid in _load(pfile)["lesson_ids"] if not _generated(lid)]


def _asset_ids() -> set:
    """معرّفات يربطها فهرس الوسائط — درسٌ جديد بمعرّفٍ منها يرث وسائط درسٍ آخر."""
    ids = set()
    if LESSON_INDEX.exists():
        for e in _load(LESSON_INDEX).get("lessons", []):
            sid = e.get("lesson_id")
            if sid:
                ids.add(sid)
                if e.get("age_group") and e.get("topic_path"):
                    ids.add(f"lesson_{e['age_group']}_{e['topic_path']}_{sid.split('_')[-1]}")
    return ids


def expand_jobs(spec: dict) -> list:
    """كل درس في المواصفة → مهمة بمفتاح ثابت (ترتيبه في المواصفة).

    المعرّف والترتيب النهائيان يُحسبان عند الكتابة: درسٌ أُسقط لا يترك ثقبًا.
    """
    jobs = []
    for ps in spec["paths"]:
        pid = ps["path_id"]
        existing = _original_lessons(pid)
        if "create" in ps:
            new = ps["create"]
            title, age, domain = new["title"], new["age_group"], new["domain"]
        else:
            path = _load(CURRICULUM / "paths" / f"{pid}.json")
            title, age, domain = path["title"], path["age_group"], path["domain"]
        planned = [l["title"] for l in ps["lessons"]]
        for i, ls in enumerate(ps["lessons"], start=1):
            jobs.append({
                "key": f"s{i:02d}", "path_id": pid, "age_group": age, "domain": domain,
                "path_title": title, "band_notes": ps.get("band_notes", ""),
                "unit_bands": ps["unit_bands"],
                "other_lessons": [e["title"] for e in existing] +
                                 [t for j, t in enumerate(planned, 1) if j != i],
                "brief": ls["title"], "focus": ls["focus"],
                "keywords": ls["keywords"], "pin_units": ls.get("pin_units", []),
                "bank": ls.get("bank", []),
            })
    return jobs


class Work:
    """المسوّدات والطعون على القرص — كل طعن مربوط ببصمة النص الذي طُعن فيه."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / "reviews").mkdir(exist_ok=True)

    def drafts(self, pid: str) -> dict:
        f = self.root / f"{pid}.drafts.json"
        return _load(f) if f.exists() else {}

    def reviews(self, pid: str, key: str, lang: str) -> dict:
        f = self.root / "reviews" / f"{pid}__{key}.{lang}.json"
        return _load(f) if f.exists() else {}

    def add_review(self, pid: str, key: str, lang: str, h: str, rec: dict) -> None:
        f = self.root / "reviews" / f"{pid}__{key}.{lang}.json"
        allr = self.reviews(pid, key, lang)
        allr[h] = rec
        _dump(f, allr)


def _en_hash(en: dict, ar: dict) -> str:
    return _hash(en) + _hash(ar)


def lesson_state(job: dict, draft: dict, work: Work, grams: set) -> dict:
    """البوابات + آخر طعن للنص الحالي + القرارات → مقبول أم لا، ولماذا."""
    st = {"key": job["key"], "brief": job["brief"], "accepted": False, "blockers": []}
    ar, en = draft.get("ar"), draft.get("en")
    if not ar:
        st["blockers"].append("no Arabic draft")
        return st
    disp = draft.get("dispositions") or []
    st["blockers"] += [f"ar gate: {p}" for p in
                       arabic_gates(ar, set(job["bank"]), grams, set(units()))]
    if en:
        st["blockers"] += [f"en gate: {p}" for p in english_gates(en, ar)]
    else:
        st["blockers"].append("no English draft")
    for lang, doc in (("ar", ar), ("en", en)):
        if not doc:
            continue
        h = _hash(ar) if lang == "ar" else _en_hash(en, ar)
        rec = work.reviews(job["path_id"], job["key"], lang).get(h)
        st[f"{lang}_hash"] = h
        st[f"{lang}_review"] = rec
        if rec is None:
            st["blockers"].append(f"{lang}: current text not reviewed")
            continue
        for i, d in enumerate(rec.get("defects") or []):
            sev = d.get("severity")
            if sev not in ("high", "medium"):
                continue
            typ = str(d.get("type", "")).lower()
            waived = [x for x in disp if x.get("lang") == lang and x.get("hash") == h
                      and x.get("index") == i and (x.get("reason") or "").strip()]
            # الشرعي والطبي (وكل عالية) لا يُردّ إلا بإثبات أن الطاعن أخطأ الواقعة.
            strict = sev == "high" or typ in NON_WAIVABLE
            if waived and (not strict or waived[0].get("reviewer_wrong")):
                continue
            st["blockers"].append(f"{lang} review #{i} [{sev}/{typ}] {d.get('field')}: "
                                  f"«{(d.get('quote') or '')[:70]}» — "
                                  f"{(d.get('why') or '')[:220]}")
    st["accepted"] = not st["blockers"]
    return st


def _ar_payload(job: dict, ar: dict, verified: list) -> dict:
    return {"age_band": job["age_group"], "path_title": job["path_title"],
            "band_notes": job["band_notes"],
            "other_lessons_in_path": job["other_lessons"],
            "verified_texts": verified,
            "knowledge_units": [unit_brief(units()[u]) for u in ar["unit_ids"]],
            "lesson": ar}


def run_reviews(spec: dict, work: Work, bank: dict, grams: set, langs: tuple) -> None:
    load_key()
    for job in expand_jobs(spec):
        d = work.drafts(job["path_id"]).get(job["key"]) or {}
        ar, en = d.get("ar"), d.get("en")
        if not ar:
            continue
        verified = [{"id": b, "source": bank[b]["source"], "text": bank[b]["text"]}
                    for b in job["bank"]]
        # الطريق المختصر: النصّان معًا بلا طعن → نداءٌ واحد يحكم على الاثنين.
        if (langs == ("ar", "en") and en
                and not arabic_gates(ar, set(job["bank"]), grams, set(units()))
                and not english_gates(en, ar)):
            h_ar, h_en = _hash(ar), _en_hash(en, ar)
            have_ar = h_ar in work.reviews(job["path_id"], job["key"], "ar")
            have_en = h_en in work.reviews(job["path_id"], job["key"], "en")
            if not have_ar and not have_en:
                payload = _ar_payload(job, ar, verified)
                payload.update(note=PLACEHOLDER_NOTE, english=_text_only(en))
                t0 = time.time()
                verdict, model = review(SYSTEM_REVIEW_BOTH, payload)
                now = _now()
                for lang, h, part in (("ar", h_ar, verdict.get("arabic") or {}),
                                      ("en", h_en, verdict.get("english") or {})):
                    defects = part.get("defects") or []
                    work.add_review(job["path_id"], job["key"], lang, h, {
                        "reviewer": model, "at": now, "defects": defects, "combined": True,
                        "contains_religious_text": (verdict.get("english") or {})
                        .get("contains_religious_text")})
                    print(f"  {job['path_id']}/{job['key']} {lang} ← {model} "
                          f"{time.time() - t0:4.0f}s  "
                          f"high={sum(x.get('severity') == 'high' for x in defects)} "
                          f"medium={sum(x.get('severity') == 'medium' for x in defects)}",
                          flush=True)
                continue
        for lang in langs:
            if lang == "ar":
                if arabic_gates(ar, set(job["bank"]), grams, set(units())):
                    continue      # البوابة أولًا — لا يُصرف طعنٌ على نصٍّ مرفوض حتميًّا
                h = _hash(ar)
                payload = _ar_payload(job, ar, verified)
                system = SYSTEM_REVIEW_LESSON
            else:
                if not en or english_gates(en, ar):
                    continue
                h = _en_hash(en, ar)
                payload = {"note": PLACEHOLDER_NOTE,
                           "arabic": _text_only(ar), "english": _text_only(en)}
                system = tc.SYSTEM_REVIEW
            if h in work.reviews(job["path_id"], job["key"], lang):
                continue
            t0 = time.time()
            verdict, model = review(system, payload)
            defects = verdict.get("defects") or []
            work.add_review(job["path_id"], job["key"], lang, h, {
                "reviewer": model, "at": _now(), "defects": defects,
                "contains_religious_text": verdict.get("contains_religious_text")})
            hi = sum(x.get("severity") == "high" for x in defects)
            me = sum(x.get("severity") == "medium" for x in defects)
            print(f"  {job['path_id']}/{job['key']} {lang} ← {model} "
                  f"{time.time() - t0:4.0f}s  high={hi} medium={me}", flush=True)


def path_en_state(ps: dict, work: Work) -> tuple[str, dict | None]:
    """ترجمة عنوان المسار الجديد ووصفه تُطعن مثل الدروس."""
    ar = {"title": ps["create"]["title"], "description": ps["create"]["description"]}
    en = {k: ps["create"]["en"][k] for k in ("title", "description")}
    h = _hash(dict(title=en["title"], summary=en["description"])) + \
        _hash(dict(title=ar["title"], summary=ar["description"]))
    return h, work.reviews(ps["path_id"], "path", "en").get(h)


def review_paths(spec: dict, work: Work) -> None:
    load_key()
    for ps in spec["paths"]:
        if "create" not in ps:
            continue
        h, rec = path_en_state(ps, work)
        if rec is not None:
            continue
        ar = {"title": ps["create"]["title"], "description": ps["create"]["description"]}
        en = {k: ps["create"]["en"][k] for k in ("title", "description")}
        verdict, model = review(tc.SYSTEM_REVIEW, {"arabic": ar, "english": en})
        defects = verdict.get("defects") or []
        work.add_review(ps["path_id"], "path", "en", h, {
            "reviewer": model, "at": _now(), "defects": defects})
        print(f"  {ps['path_id']}/path en ← {model} high="
              f"{sum(x.get('severity') == 'high' for x in defects)} medium="
              f"{sum(x.get('severity') == 'medium' for x in defects)}", flush=True)


def minutes_for(ar: dict) -> int:
    words = len(_words(ar["summary"])) + len(_words(ar["try_this"]))
    return max(3, math.ceil(words / 130))


def write_outputs(spec: dict, spec_path: Path, work: Work, bank: dict, grams: set) -> dict:
    jobs = expand_jobs(spec)
    asset_ids = _asset_ids()
    now = _now()
    report = {"spec": str(spec_path.relative_to(ROOT)), "author": AUTHOR,
              "reviewers": [REVIEW_MODEL, REVIEW_FALLBACK], "written_at": now,
              "lessons": []}

    for ps in spec["paths"]:
        pid = ps["path_id"]
        slug = pid[len("path_"):]
        pfile = CURRICULUM / "paths" / f"{pid}.json"
        en_pfile = CURRICULUM / "i18n" / "en" / "paths" / f"{pid}.json"
        drafts = work.drafts(pid)
        accepted = []
        for job in [j for j in jobs if j["path_id"] == pid]:
            d = drafts.get(job["key"]) or {}
            st = lesson_state(job, d, work, grams)
            entry = {"key": job["key"], "brief": job["brief"], "accepted": st["accepted"],
                     "blockers": st["blockers"]}
            for lang in ("ar", "en"):
                rec = st.get(f"{lang}_review")
                if rec:
                    entry[f"{lang}_review"] = {
                        "reviewer": rec["reviewer"], "at": rec["at"],
                        "rounds": len(work.reviews(pid, job["key"], lang)),
                        "defects": [{k: x.get(k) for k in ("severity", "type", "field", "why")}
                                    for x in rec.get("defects") or []]}
            entry["dispositions"] = [x for x in d.get("dispositions") or []
                                     if x.get("hash") in (st.get("ar_hash"), st.get("en_hash"))]
            report["lessons"].append(entry)
            if st["accepted"]:
                accepted.append((job, d, st, entry))
        if not accepted:
            continue
        if "create" in ps:
            _, prec = path_en_state(ps, work)
            if prec is None or any(x.get("severity") == "high"
                                   for x in prec.get("defects") or []):
                report["lessons"].append({"key": "path", "accepted": False,
                                          "blockers": ["path EN not reviewed clean"]})
                continue
            ps["create"]["en"].update(reviewer_model=prec["reviewer"],
                                      review_verdict="clean" if not prec.get("defects")
                                      else "defects")

        # إعادة الكتابة نظيفة: احذف ما كتبته تشغيلة سابقة لهذا المسار.
        if pfile.exists():
            for lid in _load(pfile)["lesson_ids"]:
                if _generated(lid):
                    (CURRICULUM / "lessons" / f"{lid}.json").unlink()
                    (CURRICULUM / "i18n" / "en" / "lessons" / f"{lid}.json").unlink()
        base = _original_lessons(pid)
        if pfile.exists():
            path = _load(pfile)
        else:
            new = ps["create"]
            path = {"id": pid, "title": new["title"], "age_group": new["age_group"],
                    "domain": new["domain"], "description": new["description"],
                    "lesson_ids": [], "estimated_days": 1,
                    "pedagogical_framework": new["pedagogical_framework"],
                    "primary_reference": new["primary_reference"],
                    "prerequisites": [], "is_published": True, "version": "1.0.0",
                    "created_at": now, "updated_at": now, "approved_by": None}
        start = max([b.get("order", 0) for b in base] + [0]) + 1
        new_ids = []
        for i, (job, d, st, entry) in enumerate(accepted):
            order = start + i
            # المعرّف الطبيعي قد يكون محجوزًا: `lesson_13-15_islamic_parenting_steadfast_03`
            # ملفٌّ قائم نُقل إلى مسارٍ آخر، وفهرس الوسائط يربط به بودكاست — درسٌ جديد
            # بهذا المعرّف كان سيرث وسائط درسٍ آخر بصمت. فالبديل بادئة `d` (deepened).
            for lid in (f"lesson_{slug}_{order:02d}", f"lesson_{slug}_d{order:02d}"):
                if lid not in asset_ids and not (CURRICULUM / "lessons" / f"{lid}.json").exists():
                    break
            else:
                raise ValueError(f"no free lesson id for {slug} order {order}")
            ar, en = d["ar"], d["en"]
            lesson = {
                "id": lid, "path_id": pid, "title": ar["title"],
                "age_group": job["age_group"], "domain": job["domain"],
                "unit_ids": ar["unit_ids"],
                "summary": expand(ar["summary"], bank, "ar"),
                "try_this": ar["try_this"], "order": order,
                "estimated_minutes": minutes_for(ar),
                "reflection_prompts": ar["reflection_prompts"],
                "warning_flags": ar.get("warning_flags") or [],
                "needs_professional_followup": bool(ar.get("needs_professional_followup")),
                "is_published": True, "version": "1.0.0",
                "created_at": now, "updated_at": now, "approved_by": None,
            }
            _dump(CURRICULUM / "lessons" / f"{lid}.json", lesson)
            rec = st["en_review"]
            src = expand(json.dumps(_text_only(ar), ensure_ascii=False), bank, "ar")
            sig_kw = bool(tc.RELIGIOUS_MARKERS.search(src))
            sig_q = bool(tc.QUOTED_ARABIC.search(src))
            sig_model = bool(rec.get("contains_religious_text"))
            en_lesson = dict(lesson)
            en_lesson.update({
                "title": en["title"], "summary": expand(en["summary"], bank, "en"),
                "try_this": en["try_this"], "reflection_prompts": en["reflection_prompts"],
                "language": "en", "source_language": "ar",
                "translation": {
                    "translator_model": AUTHOR, "reviewer_model": rec["reviewer"],
                    "needs_scholar_review": sig_kw or sig_q or sig_model,
                    "scholar_signals": {"keyword": sig_kw, "quoted_arabic": sig_q,
                                        "reviewer_model": sig_model},
                    "review_verdict": "clean" if not rec.get("defects") else "defects",
                    "review_defects": rec.get("defects") or [],
                    "approved_by": None, "revalidated_at": rec["at"],
                    "generated_by": GENERATED_BY,
                },
            })
            _dump(CURRICULUM / "i18n" / "en" / "lessons" / f"{lid}.json", en_lesson)
            new_ids.append(lid)
            entry.update(written_as=lid, title=ar["title"])

        path["lesson_ids"] = [b["id"] for b in base] + new_ids
        path["estimated_days"] = len(path["lesson_ids"])
        path["updated_at"] = now
        for a, b in ps.get("description_replace_ar", []):
            path["description"] = path["description"].replace(a, b)
        _dump(pfile, path)

        if en_pfile.exists():
            en_path = _load(en_pfile)
            for a, b in ps.get("description_replace_en", []):
                en_path["description"] = en_path["description"].replace(a, b)
        else:
            tr = ps["create"]["en"]
            en_path = dict(path)
            en_path.update({"title": tr["title"], "description": tr["description"],
                            "language": "en", "source_language": "ar",
                            "translation": {"translator_model": AUTHOR,
                                            "reviewer_model": tr.get("reviewer_model"),
                                            "review_verdict": tr.get("review_verdict"),
                                            "approved_by": None,
                                            "generated_by": GENERATED_BY}})
        en_path["lesson_ids"] = path["lesson_ids"]
        en_path["estimated_days"] = path["estimated_days"]
        en_path["updated_at"] = now
        _dump(en_pfile, en_path)

    _dump(spec_path.with_suffix(".review.json"), report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--lang", choices=("ar", "en", "both"), default="both")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--only", help="مسار واحد")
    ap.add_argument("--work-dir", default="/tmp/deepen_paths")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = _load(spec_path)
    if args.only:
        spec = dict(spec, paths=[p for p in spec["paths"] if p["path_id"] == args.only])
    work = Work(Path(args.work_dir) / spec_path.stem)
    bank = load_bank()
    grams = _bank_ngrams(bank)
    jobs = expand_jobs(spec)

    if args.plan:
        for job in jobs:
            print(f"\n{job['path_id']}/{job['key']} · {job['brief']}")
            for u in pick_units(job["keywords"], job["unit_bands"], job["pin_units"]):
                print(f"    {u['id']:40s} {u.get('age_group'):11s} {u.get('title', '')[:60]}")
            for b in job["bank"]:
                print(f"    bank [[{b}]] {bank[b]['source']} — {bank[b].get('topic', '')}")

    if args.review:
        langs = ("ar", "en") if args.lang == "both" else (args.lang,)
        run_reviews(spec, work, bank, grams, langs)
        if "en" in langs:
            review_paths(spec, work)

    if args.check or args.status:
        n_ok = 0
        for job in jobs:
            d = work.drafts(job["path_id"]).get(job["key"])
            if d is None:
                continue
            st = lesson_state(job, d, work, grams)
            n_ok += st["accepted"]
            mark = "OK" if st["accepted"] else "--"
            print(f"{mark} {job['path_id']}/{job['key']} {d.get('ar', {}).get('title', '')}"
                  f"  ar#{st.get('ar_hash', '')} en#{st.get('en_hash', '')}")
            for b in st["blockers"]:
                if args.status or "gate" in b:
                    print(f"      · {b}")
        print(f"\n{n_ok} accepted of {len(jobs)} planned")

    if args.write:
        rep = write_outputs(spec, spec_path, work, bank, grams)
        n = sum(1 for e in rep["lessons"] if e.get("written_as"))
        print(f"\nwritten {n} of {len(rep['lessons'])} · log: "
              f"{spec_path.with_suffix('.review.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
