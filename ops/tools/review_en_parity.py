#!/usr/bin/env python3
"""
بوابة المحتوى الإنجليزي — مراجعة آلية بنموذجين من عائلتين، ثم ختم موثَّق
=====================================================================

    python3 ops/tools/review_en_parity.py inventory            # عدّ بلا نداء نموذج
    python3 ops/tools/review_en_parity.py check                # البوابة (pre-commit) — بلا شبكة
    python3 ops/tools/review_en_parity.py run --kind lessons   # راجع → أصلح → أعد المراجعة → اختم
    python3 ops/tools/review_en_parity.py run --only lesson_7-9_islamic_parenting_akhlaq_01
    python3 ops/tools/review_en_parity.py run --all --rounds 3 --report /tmp/en_report.json
    python3 ops/tools/review_en_parity.py queue --only KEY --reason '…' [--category source-unverified]
    python3 ops/tools/review_en_parity.py sign --only KEY --by 'اسم من قرأ النصّين'

لماذا هذه الأداة
----------------
المخطّط يقول منذ اليوم الأول: `approved_by: null` = «غير مراجَع، لا يُنشر
للإنجليزية». وكان ٤٢٤ ملفًا منشورًا بـnull لأن الختم انتظر «مراجعًا بشريًّا» لا
وجود له — المشروع فرديّ، ولا مراجع شرعيّ ولا طابور. بندٌ مؤجَّل إلى جهة غير
موجودة ليس مؤجَّلًا؛ هو محذوف بصيغة مهذّبة، والنص الخاطئ حيّ طول «الانتظار».

فالمراجعة الآلية المتعدّدة **هي** المراجعة، وهذه الأداة تجعلها صارمة وقابلة
للتكرار وتختم بما فعلت حرفيًّا:

    approved_by: "auto-review:deepseek-v4-pro+glm-5.2:2026-10-04"

الختم **ليس إجازة شرعية** ولا يدّعيها. معناه المحدَّد: الحرّاس الحتمية مرّت،
ومراجعان من عائلتَي نماذج مختلفتين لم يجدا على **هذا النص بعينه** عيبًا متوسطًا
أو عاليًا (معنى · حذف/زيادة · قرآن مقدَّم كترجمة · حديث محرَّف أو مُسنَد بلا أصل ·
سلامة طبية · ملاءمة العمر · تسرّب عربي/صيني · وتلف في المصدر العربي نفسه).

ولماذا الختم مربوط ببصمة
------------------------
`auto_review.content_sha256` بصمة العربي والإنجليزي معًا كما رُوجعا. أي تعديل
بعدها — في الترجمة **أو في المصدر العربي** — يُبطل الختم، و`check` يرفض الـcommit
حتى تُعاد المراجعة. بلا ذلك يتكرّر ما وقع في ٢٠٢٦-٠٨: ٣٦٢ ملاحظة مخزَّنة، ١٩٪
منها تصف نصًّا لم يعد موجودًا، فصار العدّاد يصف ماضيًا.

ولماذا يُعرَض العربي على المراجع لا الإنجليزي وحده
------------------------------------------------
لأن المترجم **يغطّي تلف المصدر**: «سفينة» مكان «سكينة» في tip_16-18_016 خرجت
`companionship`، و«حق-half» خرجت `a haqq (right) for the brain`. الترجمة
الحرفية الخاطئة تفضح المصدر، والتنعيم يدفنه — فالنسختان تقرآن سليمتين والغلط
حيّ. المراجع هنا مسؤول عن الاتجاه المعاكس أيضًا: كشف المصدر عبر الترجمة.
إصلاحات العربي **لا تُكتب آليًّا** — تُجمع في التقرير وتُطبَّق بـ`--apply-arabic`
بعد فحصها، لأن العربي يقرؤه ٦٠٪ من المستخدمين ولا يعرض عليه أحدٌ بعدك.

الأدوار
-------
  · مراجع A: deepseek-v4-pro      · مراجع B: glm-5.2   (عائلتان مختلفتان عمدًا)
  · مُصلِح : mistral-large-3:675b  (عائلة ثالثة؛ رخيص وغير مفكّر — للنص بالجملة)
الملف «نظيف» فقط إذا لم يجد **أيٌّ** من المراجعَين عيبًا متوسطًا أو عاليًا
والحرّاس الحتمية سليمة. الملاحظات المنخفضة تُحفظ في سجل الختم ولا تمنعه.

نقض حكم المراجع (adjudication)
-----------------------------
عيب يكرّره مراجع بعد كل الجولات ويُثبت الدليل أنه ليس عيبًا يُسجَّل في
`ops/data/en_parity_adjudications.json` **مربوطًا ببصمة النص**: سبب مكتوب، ومن
حكم. تغيّر النص ← سقط النقض وأُعيد السؤال. لا نقض بلا سبب، ولا نقض يعبر نصًّا
جديدًا.

ما لا يمكن الوثوق به يُسحب لا يُختم
---------------------------------
`unpublish` ينقل الترجمة إلى `ops/data/en_unpublished/` مع سببها، فيعود المستخدم
الإنجليزي للنسخة العربية (السلوك الموثَّق في curriculum_loader و content_lang) بدل
نصٍّ لم يجتز البوابة.

ما يشهد به الختم — وما لا يشهد به
--------------------------------
الختم يشهد أن **الإنجليزي يطابق العربي** فقط. لا يشهد أن العربي أمينٌ لمصدره:
المراجعون لا يرون `text_original`، فوحدةٌ لخّص نموذجٌ حروفَ PDF مقلوبةً فاخترع
معناها تخرج «نظيفة» إن طابقتها ترجمتها (isl-18569b11 نسبت للنبي ﷺ قصةً مصدرها
ابن عمر — وكانت مختومة). أمانة العربي لمصدره مهمة فحصٍ آخر.

الطابور (`ops/data/en_parity_queue.json`)
----------------------------------------
`check` الكامل يجري في CI، فلا يكفي أن «نعرف» أن وحدةً تنتظر. كل إنجليزي منشور بلا
ختم يجب أن يُذكر في الطابور **مربوطًا ببصمة نصّه** مع سبب مكتوب:
  · awaiting-review   — حيٌّ كما كان، ينتظر مراجعةً من عائلةٍ غير عائلة كاتبه؛
  · source-unverified — العربي نفسه غير موثَّق أمام مصدره: لا يُختم أبدًا حتى
                        يُرفع القيد (`unqueue`) بعد إعادة الاستخراج.
تغيّر النص بعد إدراجه ← سقط الإدراج. ولا يُدرَج إنجليزيٌّ جديد: الطابور يحمل ما كان
حيًّا قبل البوابة، لا بابًا خلفيًّا لنصٍّ لم يُراجَع.

قاعدة العائلة، والتوقيع البشري
-----------------------------
`stamp-reviewed` يرفض مراجعًا من عائلة أيٍّ من كتّاب الإنجليزي (المترجم والمُصلحين،
من سجل الترجمة والطابور)، ويرفض إن جُهل الكاتب. والتوقيع البشري (`sign --by`)
يحمل بصمة النص كالختم الآلي: توقيعٌ بلا بصمة يشهد لأي نصٍّ يصيره الملف لاحقًا.

Exit (check): 0 سليم · 1 مخالفات · 2 تعطّل الفحص نفسه (self-tests)
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CURRICULUM = ROOT / "knowledge_base" / "curriculum"
I18N_EN = CURRICULUM / "i18n" / "en"
UNITS = ROOT / "knowledge_base" / "units"
STORIES_AR = ROOT / "mobile" / "assets" / "data" / "stories.json"
STORIES_EN = ROOT / "mobile" / "assets" / "data" / "stories_en.json"
# نسخة الشبكة من القصص — يجب أن تطابق المحزومة بايتًا ببايت (story_models.dart).
STORIES_EN_MIRROR = ROOT / "docs" / "stories.en.json"
ADHKAR_AR = ROOT / "mobile" / "assets" / "content" / "adhkar" / "family_adhkar.ar.json"
ADHKAR_EN = ROOT / "mobile" / "assets" / "content" / "adhkar" / "family_adhkar.en.json"
OFFSCREEN_AR = ROOT / "mobile" / "assets" / "data" / "offscreen_activities.json"
OFFSCREEN_EN = ROOT / "mobile" / "assets" / "data" / "offscreen_activities_en.json"

CACHE = ROOT / "ops" / "data" / "en_parity_cache.jsonl"          # gitignored (*.jsonl)
ADJUDICATIONS = ROOT / "ops" / "data" / "en_parity_adjudications.json"
UNPUBLISHED = ROOT / "ops" / "data" / "en_unpublished"
QUEUE = ROOT / "ops" / "data" / "en_parity_queue.json"
QUEUE_CATEGORIES = {
    "awaiting-review": "live as before; waits for a reviewer from a family other than its authors'",
    "source-unverified": "the Arabic itself is not verified against its source — never stamped "
                         "until the hold is released after re-extraction",
}

API_URL = "https://ollama.com/v1/chat/completions"
# حدّ النداء الواحد وعدد محاولاته — قابلان للضبط بـ`--request-timeout/--request-attempts`
# كي يقدر المشغّل على تحديد سقف زمني لمراجعته بدل انتظار ٦٠٠ ثانية × ٨ محاولات.
REQUEST_TIMEOUT = 600
REQUEST_ATTEMPTS = 8
REVIEWER_A = "deepseek-v4-pro"
REVIEWER_B = "glm-5.2"
FIXER = "mistral-large-3:675b"
STAMP_PREFIX = "auto-review"
TOOL_REL = "ops/tools/review_en_parity.py"

BLOCKING = ("high", "medium")
SEVERITIES = ("high", "medium", "low")

# ── Arabic / foreign-script detection ────────────────────────────────────
ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
# ﷺ ﷻ ﷽ وأخواتها علامات تبجيل تبقى في الإنجليزية عمدًا.
HONORIFICS = re.compile(r"[\ufdf0-\ufdff]")
# صيني/ياباني/كوري/سيريلي — لا مكان لها في محتوانا بأي لغة (نفس نطاق check_kb_integrity).
FOREIGN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]")
# ما يُسمح له بالبقاء عربيًّا داخل نص إنجليزي: الآية بين ﴿﴾، والمقتبَس بين «» أو "".
ALLOWED_ARABIC_SPANS = re.compile(r"﴿[^﴾]*﴾|«[^»]*»|“[^”]*”|\"[^\"]*\"|\([^)]*\)")


# ═════════════════════════════════════════════════════════════════════════
#  Leaf paths — "pages[2].text", "primary_reference.info", "keywords"
# ═════════════════════════════════════════════════════════════════════════

_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def parse_path(path: str) -> list:
    """'pages[2].text' → ['pages', 2, 'text']. يرفض المسار المشوَّه بدل تخمينه."""
    if not path or path.startswith(".") or path.endswith("."):
        raise ValueError(f"bad path: {path!r}")
    out, pos = [], 0
    while pos < len(path):
        if path[pos] == ".":
            pos += 1
            if pos >= len(path) or path[pos] in ".[":
                raise ValueError(f"bad path: {path!r}")
            continue
        m = _TOKEN.match(path, pos)
        if not m:
            raise ValueError(f"bad path: {path!r}")
        out.append(m.group(1) if m.group(1) is not None else int(m.group(2)))
        pos = m.end()
    return out


def get_leaf(doc: Any, path: str) -> Any:
    cur = doc
    for tok in parse_path(path):
        if isinstance(tok, int):
            if not isinstance(cur, list) or tok >= len(cur):
                return None
        elif not isinstance(cur, dict):
            return None
        cur = cur[tok] if isinstance(tok, int) else cur.get(tok)
    return cur


def set_leaf(doc: Any, path: str, value: Any) -> None:
    """يكتب قيمة في مسار موجود الأب. لا يخترع بنية: أبٌ مفقود = خطأ صريح."""
    toks = parse_path(path)
    cur = doc
    for tok in toks[:-1]:
        if isinstance(tok, int):
            if not isinstance(cur, list) or tok >= len(cur):
                raise KeyError(f"no parent for {path!r}")
            cur = cur[tok]
        else:
            if not isinstance(cur, dict) or tok not in cur:
                raise KeyError(f"no parent for {path!r}")
            cur = cur[tok]
    last = toks[-1]
    if isinstance(last, int):
        if not isinstance(cur, list) or last >= len(cur):
            raise KeyError(f"no slot for {path!r}")
        cur[last] = value
    else:
        if not isinstance(cur, dict):
            raise KeyError(f"no parent for {path!r}")
        cur[last] = value


# مفاتيح بنيوية: معرّفات، تعدادات، مسارات ملفات — ترجمتها تكسر الربط.
STRUCTURAL_KEYS = frozenset({
    "id", "key", "age_band", "age_group", "domain", "version", "is_published",
    "level_key", "source_unit_id", "outcome", "image", "coverImage", "videoFile",
    "themeColor", "pageNumber", "language", "source_language", "translation",
    "kind", "provenance", "unit_id", "unit_ids", "path_id", "lesson_ids", "order",
    "estimated_minutes", "estimated_days", "needs_parent", "needs_outdoors",
    "alerts_parent", "type", "approved_by", "created_at", "updated_at",
    "schema", "locale", "day_of_week", "time_of_day",
})


def walk_text_pairs(ar: Any, en: Any, path: str = "",
                    skip: frozenset = STRUCTURAL_KEYS) -> Iterator[tuple[str, str, Any]]:
    """كل ورقة نصية عربية في المصدر مع نظيرتها في الترجمة (أو None إن غابت)."""
    if isinstance(ar, dict):
        for k, v in ar.items():
            if k in skip:
                continue
            sub = en.get(k) if isinstance(en, dict) else None
            yield from walk_text_pairs(v, sub, f"{path}.{k}" if path else k, skip)
    elif isinstance(ar, list):
        for i, v in enumerate(ar):
            sub = en[i] if isinstance(en, list) and i < len(en) else None
            yield from walk_text_pairs(v, sub, f"{path}[{i}]", skip)
    elif isinstance(ar, str) and ARABIC.search(ar):
        yield path, ar, en


# ═════════════════════════════════════════════════════════════════════════
#  Items — وحدة الختم: ملف منهج، وحدة معرفة، قصة، بنك، حزمة
# ═════════════════════════════════════════════════════════════════════════

@dataclass
class Item:
    kind: str
    key: str                       # معرّف ثابت قابل للقراءة (يُستعمل في --only والتقارير)
    en_file: Path
    ar_file: Path
    fields: dict                   # path → {"ar": str|list, "en": str|list|None}
    age_band: str = ""
    published: bool = True
    selector: str | None = None    # داخل ملف متعدد العناصر (القصص): id القصة
    struct_problems: list = field(default_factory=list)

    @property
    def sha(self) -> str:
        return content_sha(self.fields)

    def rel(self) -> str:
        return str(self.en_file.relative_to(ROOT))


def content_sha(fields: dict) -> str:
    """بصمة العربي والإنجليزي معًا. مستقرة مع ترتيب المفاتيح، حسّاسة لأي حرف."""
    canon = json.dumps({p: [v.get("ar"), v.get("en")] for p, v in fields.items()},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _dump(p: Path, doc: Any) -> None:
    """يكتب بنفس شكل الملف: indent=2 بلا هروب، ويحفظ وجود السطر الأخير أو غيابه
    (حزمة الأذكار بلا سطر أخير — إضافته وحدها diff بلا معنى في ملف يلمسه غيرنا)."""
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    trailing = "\n"
    if p.exists() and not p.read_bytes().endswith(b"\n"):
        trailing = ""
    p.write_text(text + trailing, encoding="utf-8")


# الحقول المعروضة فعلًا لكل نوع منهج. `warning_flags` و`tags` عربية في الترجمة
# لكنها لا تُعرض (models.dart يقرأ warning_flags كمفاتيح فقط) — فليست تسرّبًا.
# `primary_reference.info` تُعرض في بطاقة المرجع (path_detail_screen) فهي من المحتوى.
CURRICULUM_FIELDS = {
    "lessons": ("title", "summary", "try_this", "reflection_prompts"),
    "paths": ("title", "description", "primary_reference.info"),
    "daily_tips": ("text",),
}
UNIT_FIELDS = ("title", "text_simplified", "keywords")


def _field_pairs(ar_doc: dict, en_doc: dict, paths: tuple) -> dict:
    out = {}
    for p in paths:
        a = get_leaf(ar_doc, p)
        if a in (None, "", []):
            continue
        out[p] = {"ar": a, "en": get_leaf(en_doc, p)}
    return out


def collect_curriculum(kind: str) -> list[Item]:
    items = []
    for en_f in sorted((I18N_EN / kind).glob("*.json")):
        ar_f = CURRICULUM / kind / en_f.name
        if not ar_f.exists():
            continue
        ar, en = _load(ar_f), _load(en_f)
        items.append(Item(kind=kind, key=en.get("id", en_f.stem), en_file=en_f, ar_file=ar_f,
                          fields=_field_pairs(ar, en, CURRICULUM_FIELDS[kind]),
                          age_band=str(ar.get("age_group", "")),
                          published=bool(ar.get("is_published", True))))
    return items


def collect_units() -> list[Item]:
    items = []
    for en_f in sorted(UNITS.glob("*__en.json")):
        ar_f = UNITS / en_f.name.replace("__en.json", ".json")
        if not ar_f.exists():
            continue
        ar, en = _load(ar_f), _load(en_f)
        # is_published=false على المصدر العربي = محجوزة (حجر أمانة المصدر): لا تُعرض فلا تُختم.
        items.append(Item(kind="kb_units", key=en.get("id", en_f.stem), en_file=en_f,
                          ar_file=ar_f, fields=_field_pairs(ar, en, UNIT_FIELDS),
                          age_band=str(ar.get("age_group", "")),
                          published=ar.get("is_published", True) is not False))
    return items


def collect_stories() -> list[Item]:
    if not STORIES_EN.exists():
        return []
    ar_by_id = {s["id"]: s for s in _load(STORIES_AR)}
    items = []
    for en in _load(STORIES_EN):
        ar = ar_by_id.get(en.get("id"))
        if not ar:
            continue
        fields = {p: {"ar": a, "en": e} for p, a, e in walk_text_pairs(ar, en)}
        problems = []
        if len(ar.get("pages", [])) != len(en.get("pages", [])):
            problems.append(f"pages: {len(ar.get('pages', []))} → {len(en.get('pages', []))}")
        items.append(Item(kind="stories", key=f"story:{en['id']}", en_file=STORIES_EN,
                          ar_file=STORIES_AR, fields=fields, selector=en["id"],
                          age_band=str(ar.get("ageGroup", "")), struct_problems=problems))
    return items


def _aligned_problems(ar: Any, en: Any, path: str = "") -> list[str]:
    """القوائم بنفس الطول، والعناصر ذات id/key بنفس المعرّف في نفس الموضع."""
    out = []
    if isinstance(ar, dict) and isinstance(en, dict):
        for k, v in ar.items():
            if k in en:
                out += _aligned_problems(v, en[k], f"{path}.{k}" if path else k)
    elif isinstance(ar, list) and isinstance(en, list):
        if len(ar) != len(en):
            out.append(f"{path}: {len(ar)} → {len(en)}")
        for i, (a, e) in enumerate(zip(ar, en)):
            if isinstance(a, dict) and isinstance(e, dict):
                for idk in ("id", "key"):
                    if idk in a and a.get(idk) != e.get(idk):
                        out.append(f"{path}[{i}].{idk}: {a.get(idk)} ≠ {e.get(idk)}")
            out += _aligned_problems(a, e, f"{path}[{i}]")
    return out


def collect_banks() -> list[Item]:
    items = []
    for sub in ("agreements", "missions", "license"):
        for en_f in sorted((I18N_EN / sub).glob("*.json")):
            ar_f = CURRICULUM / sub / en_f.name
            if not ar_f.exists():
                continue
            ar, en = _load(ar_f), _load(en_f)
            items.append(Item(kind="banks", key=f"{sub}/{en_f.stem}", en_file=en_f, ar_file=ar_f,
                              fields={p: {"ar": a, "en": e} for p, a, e in walk_text_pairs(ar, en)},
                              age_band=str(ar.get("age_band", "")),
                              published=bool(ar.get("is_published", True)),
                              struct_problems=_aligned_problems(ar, en)))
    return items


def collect_adhkar() -> list[Item]:
    """الحزمة كلها وحدة ختم. التلميحات تُراجَع؛ الآيات والأحاديث يجب أن تطابق العربي حرفًا."""
    if not ADHKAR_EN.exists():
        return []
    ar, en = _load(ADHKAR_AR), _load(ADHKAR_EN)
    ar_items = {i["id"]: i for i in ar.get("items", [])}
    fields, problems = {}, []
    for idx, it in enumerate(en.get("items", [])):
        src = ar_items.get(it.get("id"))
        if src is None:
            problems.append(f"items[{idx}]: id {it.get('id')} not in Arabic pack")
            continue
        if it.get("kind") in ("verse", "hadith"):
            # القرآن لا يُترجَم، والحديث لا يُعاد صوغه: يبقى كما هو في العربي.
            for k in ("text", "source"):
                if it.get(k) != src.get(k):
                    problems.append(f"items[{idx}].{k}: {it['kind']} differs from Arabic")
            continue
        for k in ("text", "source", "topic"):
            a = src.get(k)
            if isinstance(a, str) and ARABIC.search(a):
                fields[f"items[{idx}].{k}"] = {"ar": a, "en": it.get(k)}
    if len(ar.get("items", [])) != len(en.get("items", [])):
        problems.append(f"items: {len(ar.get('items', []))} → {len(en.get('items', []))}")
    return [Item(kind="adhkar", key="adhkar:family_adhkar", en_file=ADHKAR_EN, ar_file=ADHKAR_AR,
                 fields=fields, struct_problems=problems)]


def collect_offscreen() -> list[Item]:
    if not OFFSCREEN_EN.exists():
        return []
    ar, en = _load(OFFSCREEN_AR), _load(OFFSCREEN_EN)
    return [Item(kind="offscreen", key="offscreen:activities", en_file=OFFSCREEN_EN,
                 ar_file=OFFSCREEN_AR,
                 fields={p: {"ar": a, "en": e} for p, a, e in walk_text_pairs(ar, en)},
                 struct_problems=_aligned_problems(ar, en))]


COLLECTORS: dict[str, Callable[[], list[Item]]] = {
    "lessons": lambda: collect_curriculum("lessons"),
    "paths": lambda: collect_curriculum("paths"),
    "daily_tips": lambda: collect_curriculum("daily_tips"),
    "kb_units": collect_units,
    "stories": collect_stories,
    "banks": collect_banks,
    "adhkar": collect_adhkar,
    "offscreen": collect_offscreen,
}


def collect(kinds: list[str]) -> list[Item]:
    out = []
    for k in kinds:
        out += COLLECTORS[k]()
    return out


# ═════════════════════════════════════════════════════════════════════════
#  Stamp — read / write the record in the place each content type keeps it
# ═════════════════════════════════════════════════════════════════════════

_STAMP_BODY = re.compile(r"^(?P<r>\S+):(?P<d>\d{4}-\d{2}-\d{2})$")


def stamp_value(reviewers: tuple[str, ...], on: str) -> str:
    return f"{STAMP_PREFIX}:{'+'.join(reviewers)}:{on}"


def parse_stamp(value: Any) -> dict | None:
    """'auto-review:deepseek-v4-pro+glm-5.2:2026-10-04' → {reviewers, date}; غير ذلك None.

    مراجعٌ واحد مقبول أيضًا ('auto-review:claude-opus:2026-10-04') — هو ختم ما
    راجعه Claude وحده حين أغلق السقف الأسبوعي نماذج Ollama؛ اسمه في القيمة نفسها
    ليُميَّز. أسماء النماذج قد تحمل وسمًا بنقطتين (mistral-large-3:675b)، فالتاريخ
    يُقرأ من الذيل لا بالتقسيم الساذج على ':'.
    """
    if not isinstance(value, str) or not value.strip().startswith(STAMP_PREFIX + ":"):
        return None
    m = _STAMP_BODY.match(value.strip()[len(STAMP_PREFIX) + 1:])
    if not m:
        return None
    try:
        date.fromisoformat(m.group("d"))
    except ValueError:
        return None
    reviewers = m.group("r").split("+")
    if not all(reviewers):
        return None
    return {"reviewers": reviewers, "date": m.group("d")}


def _translation_block(item: Item, doc: Any) -> dict:
    """المكان الذي يعيش فيه سجل المراجعة لهذا النوع (يُنشأ إن غاب)."""
    if item.kind == "stories":
        story = next(s for s in doc if s.get("id") == item.selector)
        return story.setdefault("translation", {})
    return doc.setdefault("translation", {})


def read_translation(item: Item) -> dict:
    """سجل الترجمة كما هو في الملف (للقصص: سجل القصة بعينها)، أو {}."""
    doc = _load(item.en_file)
    if item.kind == "stories":
        story = next((s for s in doc if s.get("id") == item.selector), {})
        return story.get("translation") or {}
    return (doc.get("translation") or {}) if isinstance(doc, dict) else {}


def read_stamp(item: Item) -> tuple[Any, dict]:
    tr = read_translation(item)
    return tr.get("approved_by"), tr.get("auto_review") or {}


def _approval_problem(item: Item, tr: dict) -> str | None:
    """None إن كان في السجل اعتمادٌ يصدق على النص الحالي؛ وإلا السبب.

    ختمٌ آلي (`auto-review:…`) بصمته في `auto_review.content_sha256`. وتوقيعٌ بشريٌّ
    باسم يحمل بصمته في `approval.content_sha256` — كان يُقبل «كما كُتب» بلا بصمة،
    فيبقى صالحًا أبدًا مهما تغيّر النص بعده (ثغرةٌ أمسكتها مراجعة PR #20).
    """
    stamp = tr.get("approved_by")
    parsed = parse_stamp(stamp)
    if parsed is None:
        if str(stamp).strip().startswith(STAMP_PREFIX):
            return f"malformed stamp {stamp!r}"
        fp = (tr.get("approval") or {}).get("content_sha256")
        if not fp:
            return (f"approved_by {stamp!r} carries no content fingerprint — a signature "
                    "that never goes stale vouches for whatever the text later becomes; "
                    f"sign with `{TOOL_REL} sign --only {item.key} --by …`")
        if fp != item.sha:
            return "signature is stale — the Arabic or English changed after it was signed"
        return None
    if (tr.get("auto_review") or {}).get("content_sha256") != item.sha:
        return ("stamp is stale — the Arabic or English changed after review "
                f"(stamped {parsed['date']})")
    return None


def approval_state(item: Item) -> tuple[str, str | None]:
    """('valid' | 'none' | 'invalid', why). لا يعرف شيئًا عن الطابور."""
    tr = read_translation(item)
    if not tr.get("approved_by"):
        return "none", None
    why = _approval_problem(item, tr)
    return ("invalid", why) if why else ("valid", None)


def write_stamp(item: Item, record: dict) -> None:
    doc = _load(item.en_file)
    tr = _translation_block(item, doc)
    tr["approved_by"] = record["approved_by"]
    tr["auto_review"] = record["auto_review"]
    tr.pop("approval", None)
    # السجل القديم يصف نصًّا قبل الإصلاح؛ نستبدله بحكم الجولة الأخيرة لا نتركه بائتًا.
    tr["reviewer_model"] = "+".join(record["auto_review"]["reviewers"])
    tr["review_verdict"] = "clean" if not record["auto_review"]["residual_low"] else "low_only"
    tr["review_defects"] = record["auto_review"]["residual_low"]
    tr["revalidated_at"] = record["auto_review"]["reviewed_at"]
    _settle_queue_entry(item, tr)
    # ملفات المنهج تحمل approved_by في الجذر أيضًا (نسخة من العربي) — يتبع الختم.
    if item.kind in CURRICULUM_FIELDS and isinstance(doc, dict) and "approved_by" in doc:
        doc["approved_by"] = record["approved_by"]
    _dump(item.en_file, doc)
    if item.kind == "stories":
        shutil.copyfile(STORIES_EN, STORIES_EN_MIRROR)


def clear_stamp(item: Item) -> bool:
    """يُسقط ختمًا (أو توقيعًا) لم يعد يصدق. يرجّع True إن كان هناك ختم.

    ختمٌ بائت أسوأ من غياب الختم: الأول يقول «رُوجع» عن نصٍّ لم يُراجَع.
    """
    doc = _load(item.en_file)
    if item.kind == "stories":
        target = next((s for s in doc if s.get("id") == item.selector), None)
        if target is None:
            return False
    else:
        target = doc
    tr = target.get("translation") if isinstance(target, dict) else None
    if not tr or not tr.get("approved_by"):
        return False
    tr["approved_by"] = None
    tr.pop("auto_review", None)
    tr.pop("approval", None)
    tr["review_verdict"] = "pending"
    if item.kind in CURRICULUM_FIELDS and isinstance(doc, dict) and doc.get("approved_by"):
        doc["approved_by"] = None
    _dump(item.en_file, doc)
    if item.kind == "stories":
        shutil.copyfile(STORIES_EN, STORIES_EN_MIRROR)
    return True


# ── the queue: unstamped English that is live, named, and bound to its text ──

def load_queue() -> dict:
    """key → {category, reason, content_sha256, queued_on, english_authors?}."""
    if not QUEUE.exists():
        return {}
    return dict(_load(QUEUE).get("units") or {})


def save_queue(units: dict) -> None:
    doc = _load(QUEUE) if QUEUE.exists() else {}
    doc.setdefault("_doc", [
        "Published English that is live WITHOUT a review stamp, each bound to the exact "
        "text it was queued at (content_sha256 of the Arabic + English shown fields).",
        "review_en_parity.py check passes such a unit only while its text still matches. "
        "Edit it and the entry no longer holds: review it, or re-queue it with a reason.",
        "awaiting-review: waits for a reviewer from a family other than its English authors'. "
        "source-unverified: the Arabic is not verified against its own source — never stamped "
        "until the hold is released (unqueue) after re-extraction.",
        "Written by `review_en_parity.py queue` / `unqueue`; stamping removes the entry.",
    ])
    doc["units"] = dict(sorted(units.items()))
    _dump(QUEUE, doc)


def queue_entry_problem(key: str, entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    if entry.get("category") not in QUEUE_CATEGORIES:
        return f"category {entry.get('category')!r} — expected one of {sorted(QUEUE_CATEGORIES)}"
    if not str(entry.get("reason") or "").strip():
        return "no reason — a hold nobody can explain is a stamp by another name"
    if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("content_sha256") or "")):
        return "no content fingerprint"
    try:
        date.fromisoformat(str(entry.get("queued_on")))
    except ValueError:
        return "queued_on is not a date"
    return None


def _settle_queue_entry(item: Item, tr: dict) -> None:
    """عند الختم: يُحفظ كتّاب الإنجليزي المسجَّلون في الطابور داخل سجل الترجمة
    (لئلا تضيع معرفة «Claude كتب هذا» حين يخرج من الطابور)، ثم يُحذف الإدخال."""
    queue = load_queue()
    entry = queue.pop(item.key, None)
    if entry is None:
        return
    authors = list(tr.get("english_authors") or [])
    for a in entry.get("english_authors") or []:
        if a not in authors:
            authors.append(a)
    if authors:
        tr["english_authors"] = authors
    save_queue(queue)


# ── model families: who wrote the English, and who may vouch for it ──────

MODEL_FAMILIES = {
    "anthropic": ("claude", "anthropic", "opus", "sonnet", "haiku"),
    "mistral": ("mistral", "mixtral", "magistral", "devstral", "codestral", "ministral",
                "pixtral"),
    "deepseek": ("deepseek",),
    "zhipu": ("glm", "chatglm", "zhipu"),
    "alibaba": ("qwen", "qwq"),
    "openai": ("gpt", "chatgpt", "openai", "o1", "o3", "o4"),
    "google": ("gemini", "gemma"),
    "meta": ("llama",),
    "moonshot": ("kimi", "moonshot"),
    "cohere": ("command", "aya", "cohere"),
    "xai": ("grok",),
    "minimax": ("minimax",),
}


def model_family(name: Any) -> str | None:
    """'claude-opus-5.5' → 'anthropic'، 'mistral-large-3:675b' → 'mistral'؛ غير معروف → None."""
    if not isinstance(name, str) or not name.strip():
        return None
    for tok in re.split(r"[^a-z0-9]+", name.lower()):
        if not tok:
            continue
        for fam, prefixes in MODEL_FAMILIES.items():
            if any(tok == p or (tok.startswith(p) and len(p) > 2) for p in prefixes):
                return fam
    return None


def english_authors(item: Item, queue: dict | None = None) -> list[str]:
    """كل من كتب في هذا الإنجليزي: المترجم، والمُصلحون، وما سُجّل في الطابور.

    `manual_fix_note` بلا كاتبٍ مسمّى يُحسب على Claude: كل إصلاح يدوي في هذا
    المستودع كتبه وكيلٌ من Claude — والخطأ في هذا الاتجاه يكلّف مراجعةً إضافية
    فقط، وفي الاتجاه الآخر يكلّف ختمًا يشهد فيه الكاتب لنفسه.
    """
    tr = read_translation(item)
    names = [tr.get("translator_model"), tr.get("fixer_model"),
             (tr.get("auto_review") or {}).get("fixer"), *(tr.get("english_authors") or [])]
    entry = (load_queue() if queue is None else queue).get(item.key) or {}
    names += entry.get("english_authors") or []
    if tr.get("manual_fix_note") and not any(model_family(n) == "anthropic" for n in names):
        names.append("claude-opus")
    out: list[str] = []
    for n in names:
        if isinstance(n, str) and n.strip() and n not in out:
            out.append(n)
    return out


def family_conflict(item: Item, reviewers: tuple[str, ...] | list[str],
                    queue: dict | None = None) -> str | None:
    """None إن كان كل مراجع من عائلة غير عائلات كتّاب الإنجليزي؛ وإلا السبب."""
    authors = english_authors(item, queue)
    if not authors:
        return "its English has no recorded author, so no reviewer can be shown to be independent"
    fams = {a: model_family(a) for a in authors}
    unknown = [a for a, f in fams.items() if f is None]
    if unknown:
        return f"author family unknown ({', '.join(unknown)})"
    for r in reviewers:
        rf = model_family(r)
        if rf is None:
            return f"reviewer {r!r} is not a known model family (a person signs with `sign`)"
        same = [a for a, f in fams.items() if f == rf]
        if same:
            return f"reviewer {r} is the same family ({rf}) as an author of this English ({same[0]})"
    return None


def build_record(item: Item, reviewers: tuple[str, str], rounds: int, fixed: bool,
                 residual_low: list, adjudicated: list, on: str) -> dict:
    return {
        "approved_by": stamp_value(reviewers, on),
        "auto_review": {
            "reviewers": list(reviewers),
            "fixer": FIXER if fixed else None,
            "rounds": rounds,
            "prompt_version": PROMPT_V,
            "content_sha256": item.sha,
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "residual_low": residual_low[:8],
            "adjudicated": adjudicated,
            "tool": TOOL_REL,
            "meaning": "deterministic guards passed and two different-family model "
                       "reviewers found no medium/high defect in this exact text; "
                       "certifies that the English matches the Arabic, not that the "
                       "Arabic is faithful to its own source; not a scholar's ijazah",
        },
    }


# ═════════════════════════════════════════════════════════════════════════
#  Deterministic checks — certain defects, no model opinion
# ═════════════════════════════════════════════════════════════════════════

def _import_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = argv
    return mod


_tc = _hc = _qr = None


def _guards():
    global _tc, _hc, _qr
    if _tc is None:
        _tc = _import_tool("translate_curriculum")
        _hc = _import_tool("check_hadith_citations")
        _qr = _import_tool("check_quran_rendering")
    return _tc, _hc, _qr


def _as_text(v: Any) -> str:
    if isinstance(v, list):
        return "\n".join(_as_text(x) for x in v)
    return v if isinstance(v, str) else ("" if v is None else str(v))


# حرف عربي مفرد يُذكر بوصفه حرفًا («يتقن الطفل ب (ba) وم (meem) مبكرًا») ليس
# نصًّا لم يُترجم — هو موضوع الجملة. وحدة النطق c456b140 أُوقفت به وهي سليمة.
_LONE_LETTER = re.compile(r"(?<![\u0600-\u06ff])[\u0621-\u064a](?![\u0600-\u06ff])")


def leaked_arabic(text: str) -> str:
    """العربي المتبقّي في نص إنجليزي خارج المواضع المسموحة (آية ﴿﴾، اقتباس، تبجيل، حرف مفرد)."""
    stripped = HONORIFICS.sub("", ALLOWED_ARABIC_SPANS.sub("", text))
    return "".join(ARABIC.findall(_LONE_LETTER.sub("", stripped)))


def deterministic_defects(item: Item) -> list[dict]:
    tc, hc, qr = _guards()
    out = []

    def add(fld, typ, why, sev="high", excerpt=""):
        out.append({"field": fld, "side": "english", "type": typ, "severity": sev,
                    "why": why, "english": excerpt[:160], "source": "deterministic"})

    for p in item.struct_problems:
        add(p.split(":")[0], "structure", f"structure differs from Arabic: {p}")
    for p, v in item.fields.items():
        ar, en = v["ar"], v["en"]
        if en in (None, "", []):
            add(p, "omission", "no English for an Arabic field (field missing or empty)")
            continue
        if isinstance(ar, list) != isinstance(en, list) or (
                isinstance(ar, list) and len(ar) != len(en)):
            add(p, "structure", "list shape differs from Arabic")
        en_t, ar_t = _as_text(en), _as_text(ar)
        if FOREIGN.search(en_t):
            add(p, "leakage", "CJK/Cyrillic characters in English", excerpt=en_t)
        leak = leaked_arabic(en_t)
        # Arabic left in a field the reader sees in English. A whole untranslated
        # field is the common case (EN == AR copied over).
        if len(leak) >= 3:
            add(p, "leakage", f"untranslated Arabic in English ({len(leak)} letters)",
                sev="medium", excerpt=en_t)
        why = hc.check_translated_attribution(ar_t, en_t)
        if why:
            add(p, "hadith", why, excerpt=en_t)
        for typ, fld, ex in qr.violations_in({p: en_t}):
            add(p, "quran", typ, excerpt=ex)
    ar_all = {p: _as_text(v["ar"]) for p, v in item.fields.items()}
    en_all = {p: _as_text(v["en"]) for p, v in item.fields.items() if v["en"]}
    for msg in tc._validate_glossary(ar_all, en_all):
        add("(glossary-guard)", "term_injection", msg)
    for p, v in item.fields.items():
        if FOREIGN.search(_as_text(v["ar"])):
            out.append({"field": p, "side": "arabic", "type": "source_corruption",
                        "severity": "high", "why": "CJK/Cyrillic characters in the Arabic source",
                        "arabic": _as_text(v["ar"])[:160], "source": "deterministic"})
    return out


# ═════════════════════════════════════════════════════════════════════════
#  Model calls
# ═════════════════════════════════════════════════════════════════════════

_KEY: str | None = None
# حين يُغلق سقف الحساب الأسبوعي: احكم بما راجعه النموذجان فعلًا (مخزَّنًا ببصمة النص
# ونسخة التعليمات) ولا تطلب جديدًا. وحدةٌ ينقصها حكم أحدهما لا تُختم.
CACHE_ONLY = False


def _api_key() -> str:
    global _KEY
    if _KEY:
        return _KEY
    key = os.environ.get("OLLAMA_API_KEY")
    if key:
        _KEY = key
        return key
    env = Path.home() / "projects" / "email-twin" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("OLLAMA_API_KEY="):
                _KEY = line.split("=", 1)[1].strip().strip("'\"")
                return _KEY
    sys.exit("❌ OLLAMA_API_KEY غير مضبوط (ولا في ~/projects/email-twin/.env)")


# حصّة Ollama Cloud مشتركة مع وكلاء آخرين على نفس المفتاح. ستّة نداءات متوازية
# أعادت 429 في أول تشغيلة كاملة، فصار الحدّ سقفًا عامًّا (لا لكل مراجع) ومعه
# تبريد مشترك: أول 429 يُبطئ كل الخيوط، لا الخيط الذي أصابه وحده.
_slots = threading.BoundedSemaphore(3)
_cool_lock = threading.Lock()
_cool_until = [0.0]


def set_concurrency(n: int) -> None:
    global _slots
    _slots = threading.BoundedSemaphore(max(1, n))


def _cooldown(seconds: float) -> None:
    with _cool_lock:
        _cool_until[0] = max(_cool_until[0], time.time() + seconds)


def _wait_cooldown() -> None:
    while True:
        with _cool_lock:
            left = _cool_until[0] - time.time()
        if left <= 0:
            return
        time.sleep(min(left, 15))


class UsageCapError(Exception):
    """سقف استهلاك الحساب (Pro: نافذة ٥ ساعات) — ليس عطلًا عابرًا.

    وقع 2026-10-04 في منتصف أول تشغيلة كاملة: كل النماذج ترجع 429 بنص
    «You reached your Pro 5-hour limit». إعادة المحاولة بتراجع أُسّي كانت ستحرق
    ٨ محاولات × كل دفعة ثم تُعلِّم مئات الوحدات «غير مراجَعة» — فالأداة تتوقف
    فورًا بتقرير جزئي، والكاش يحفظ ما تمّ، والتشغيلة التالية تكمل من حيث وقفت.
    """


_capped = threading.Event()


def _is_usage_cap(body: str) -> bool:
    b = body.lower()
    return "limit" in b and any(w in b for w in ("hour", "week", "month", "usage"))


def post(model: str, system: str, user: str, timeout: int | None = None) -> tuple[str, dict]:
    """نداء واحد، بتراجع أُسّي على العابر وتبريد مشترك على 429، وسقوط فوري على 401/402/403."""
    body = json.dumps({"model": model, "temperature": 0.1,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}).encode()
    timeout = REQUEST_TIMEOUT if timeout is None else timeout
    last = None
    for attempt in range(REQUEST_ATTEMPTS):
        if _capped.is_set():
            raise UsageCapError("usage cap reached earlier in this run")
        _wait_cooldown()
        req = urllib.request.Request(API_URL, data=body, headers={
            "Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"})
        try:
            with _slots:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    out = json.load(r)
            content = out["choices"][0]["message"].get("content") or ""
            if not content.strip():
                raise ValueError("empty content")
            return content, out.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403):
                raise RuntimeError(f"{model}: HTTP {e.code} — غير متاح على هذا المفتاح") from e
            last = e
            if e.code == 429:
                try:
                    detail = e.read().decode("utf-8", "replace")
                except OSError:
                    detail = ""
                if _is_usage_cap(detail):
                    _capped.set()
                    raise UsageCapError(detail[:200]) from e
                _cooldown(min(300, 30 * 2 ** min(attempt, 3)))
                continue
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError,
                http.client.HTTPException) as e:
            # IncompleteRead (جسم مقطوع في منتصف الرد) ليس OSError — أسقط تشغيلةً
            # من ٢٢٨ وحدة بعد ساعة كاملة على 2026-10-04. عابرٌ مثل غيره: أعد المحاولة.
            last = e
        if attempt + 1 < REQUEST_ATTEMPTS:
            time.sleep(min(90, 5 * 2 ** attempt))
    raise RuntimeError(f"{model}: failed after {REQUEST_ATTEMPTS} attempts: {last}")


def parse_json(text: str) -> Any:
    """النماذج تلفّ الناتج بأسوار markdown وتسبقه بنثر أحيانًا رغم التعليمات."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


REVIEW_SYSTEM = """You audit English translations of Arabic Islamic-parenting content \
in an app used by Muslim parents. Each item gives Arabic source fields and their English \
rendering side by side, plus the child's age band. Nobody reviews this after you: what you \
miss reaches parents as published religious and medical guidance.

Check EVERY field of EVERY item for:
1. meaning — the English changes, reverses, overstates or understates the Arabic.
2. omission / addition — a substantive point dropped, or content (advice, claims, \
religious statements, attributions) added that the Arabic does not contain.
3. quran — English wording presented as the Qur'an. Correct form: the ayah stays in Arabic \
(inside ﴿﴾), any English is explicitly labelled "interpretation of the meaning". Also: an \
ayah that the Arabic attributes to Allah but the English makes read as someone else's words.
4. hadith — a hadith's wording altered, softened, shortened or "completed" in English; an \
attribution (narrated by al-Bukhari/Muslim, etc.) present in English but not in Arabic, or a \
different collection named; anything attributed to the Prophet ﷺ in English that the Arabic \
does not attribute to him; ﷺ placed on someone else (high). In the ARABIC itself (side \
"arabic"): a saying attributed to the Prophet ﷺ that is known to be fabricated or not a \
hadith at all (high); an explicit citation of a collection other than Sahih al-Bukhari or \
Sahih Muslim — the app's policy cites hadith only from those two (medium). A well-known \
hadith quoted WITHOUT any source is not a defect by itself (a missing source is safer than \
an invented one) — report it as low at most, and never invent a source in "suggestion".
5. medical — unsafe, overconfident or dosage advice; a referral to a doctor present in the \
Arabic but lost in English; clear red flags with no advice to seek care.
6. tone / age — clinical, preachy or condescending where the Arabic is warm; content unfit \
for the age band.
7. leakage — Arabic words left untranslated in English (allowed: Arabic ayah inside ﴿﴾, an \
Arabic quotation kept on purpose, ﷺ, and transliterated Islamic terms such as tarbiyah, \
akhlaq, adhkar, fitrah, rifq, aqeedah, seerah, haya, ihsan, amanah, birr al-walidayn, \
silat al-rahim, tazkiyah, salah, du'a, wudu, sunnah, halal, haram, insha'Allah); Chinese/ \
Japanese/Korean/Cyrillic characters; garbled text.
8. ARABIC SOURCE CORRUPTION — read the Arabic on its own, critically. A word that does not \
fit (e.g. «سفينة» where «سكينة» is meant), a typo that changes meaning, a stray English \
fragment inside Arabic (e.g. «حق-half»), a cut-off or garbled sentence, broken encoding, \
Egyptian colloquial where Modern Standard Arabic is expected. Translators SMOOTH OVER such \
corruption, so a fluent English line is not evidence the Arabic is sound. Report with side \
"arabic" and put the corrected Arabic field text in "suggestion".

Severity — rate honestly; a false medium/high forces a needless rewrite:
- high: religious error (items 3-4), unsafe medical advice, meaning reversed, Arabic \
corruption that changes meaning.
- medium: a substantive point changed/omitted/added; visible untranslated Arabic or foreign \
script; an Arabic typo or dialect a reader would notice; tone clearly unfit.
- low: nuance, word choice, style, transliteration preference.
Never rate as medium/high: British vs American spelling, Oxford commas, a synonym that keeps \
the meaning, or a glossary term transliterated where the Arabic has that term.

Return JSON only, with exactly one entry for EVERY item id you were given, in the given \
order — an item with no defects still gets its entry with "defects": []. An empty or partial \
"items" array is invalid output and will be discarded.
{"items": [{"id": "<id>", "defects": [{"field": "<field path as given>", \
"side": "english"|"arabic", "type": "meaning"|"omission"|"addition"|"quran"|"hadith"|\
"medical"|"tone"|"leakage"|"source_corruption"|"structure", "severity": "high"|"medium"|"low", \
"arabic": "<short excerpt>", "english": "<short excerpt>", "why": "<one sentence>", \
"suggestion": "<corrected text for that field, or empty>"}]}]}"""


FIX_SYSTEM = """You correct English translations of Arabic Islamic-parenting content. \
You get, per field, the Arabic source, the current English, and defects two independent \
reviewers reported. Produce corrected English for the affected fields.

Rules:
- Fix exactly what the defects require and nothing else. Words, glosses in parentheses, \
punctuation and sentences the defects do not mention stay verbatim.
- Fields marked "english_locked": true have only Arabic-side defects. Do NOT return English \
for them; only the corrected Arabic.
- A field with no English yet: translate it fully and faithfully.
- The English must say what the Arabic says — no added advice, claims or attributions, \
nothing dropped.
- THE QUR'AN IS NOT TRANSLATED. Keep Arabic ayah text inside ﴿﴾ exactly as in the source. \
If an English meaning is given it must be labelled "interpretation of the meaning". \
Never put English inside ﴿﴾ or present English as the words of Allah.
- Never alter, complete or paraphrase-as-quote a hadith; never add an attribution \
(narrated by …) the Arabic does not carry; keep ﷺ exactly where the Arabic has it.
- Transliterate these terms only where that exact Arabic word appears: tarbiyah (تربية), \
akhlaq (أخلاق), adhkar (أذكار), fitrah (فطرة), rifq (رفق), aqeedah (عقيدة), seerah (سيرة), \
haya (حياء), birr al-walidayn (بر الوالدين), silat al-rahim (صلة الرحم), ihsan (إحسان), \
amanah (أمانة), tazkiyah (تزكية). رحمة is mercy, not rifq; أمان is safety, not amanah.
- Warm, direct parent-to-parent register; age-appropriate.
- If a defect is wrong (the current text is already faithful), leave the field and list \
it under "rejected" with the reason.
- Defects with side "arabic" are about the SOURCE. Do not change the English to match a \
corrupted Arabic: translate what the Arabic clearly means, and put the minimally corrected \
Arabic field under "arabic" (Modern Standard Arabic, change only the corrupted words).
- Lists stay lists of the same length.

Return JSON only:
{"english": {"<field>": "<corrected full field text or list>"}, \
"arabic": {"<field>": "<corrected full Arabic field text>"}, \
"rejected": [{"field": "<field>", "why": "<reason>"}]}"""


# ── cache: (model, prompt version, chunk sha) → defects ──────────────────
# النسخة جزء من المفتاح: حكمٌ صدر بتعليمات مراجعة قديمة لا يُعاد استعماله بعد
# تغييرها. (أول تجربة سمّت «حديثًا بلا مصدر» عيبًا عاليًا، ثم تغيّرت القاعدة إلى
# «غياب المصدر أأمن من اختلاقه» — وكاد الكاش يعيد الحكم القديم كأنه جديد.)
PROMPT_V = hashlib.sha256(REVIEW_SYSTEM.encode("utf-8")).hexdigest()[:12]
# مفاتيح ما قبل الترقيم («model|sha») صدرت كلها بهذه النسخة بعينها.
_LEGACY_PROMPT_V = "dfa8a5f39718"


def _cache_key(model: str, sha: str) -> str:
    return f"{model}|{PROMPT_V}|{sha}"


def _cache_get(cache: dict, model: str, sha: str):
    hit = cache.get(_cache_key(model, sha))
    if hit is None and PROMPT_V == _LEGACY_PROMPT_V:
        hit = cache.get(f"{model}|{sha}")
    return hit

_cache_lock = threading.Lock()
_cache: dict[str, list] | None = None


def _cache_load() -> dict:
    """يُحمَّل مرة واحدة تحت القفل، ويُنشر كاملًا لا وهو يُملأ.

    النسخة الأولى كانت تُسند `{}` ثم تملؤه: الخيط الثاني (المراجع الآخر يبدأ في
    اللحظة نفسها) يرى قاموسًا غير فارغ الإسناد فارغ المحتوى، فيُخطئ الكاش. في
    التشغيل العادي يعني ذلك نداءً مكرّرًا، وفي `--cache-only` عدَّ ٦٠ وحدة «غير
    مراجَعة» وحكماها محفوظان (2026-10-04).
    """
    global _cache
    with _cache_lock:
        if _cache is None:
            loaded: dict = {}
            if CACHE.exists():
                for line in CACHE.read_text(encoding="utf-8").splitlines():
                    try:
                        rec = json.loads(line)
                        loaded[rec["k"]] = rec["v"]
                    except (json.JSONDecodeError, KeyError):
                        continue
            _cache = loaded
    return _cache


def _cache_put(k: str, v: list) -> None:
    cache = _cache_load()
    with _cache_lock:
        cache[k] = v
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"k": k, "v": v}, ensure_ascii=False) + "\n")


@dataclass
class Chunk:
    item: Item
    cid: str            # id shown to the model
    fields: dict

    @property
    def size(self) -> int:
        return sum(len(_as_text(v["ar"])) + len(_as_text(v["en"])) for v in self.fields.values())

    @property
    def sha(self) -> str:
        return content_sha(self.fields)

    def payload(self) -> dict:
        return {"id": self.cid, "kind": self.item.kind, "age_band": self.item.age_band,
                "fields": {p: {"arabic": v["ar"], "english": v["en"]}
                           for p, v in self.fields.items()}}


def chunks_of(item: Item, budget: int) -> list[Chunk]:
    """وحدة ختم كبيرة (حزمة الأذكار، قصة) تُقسَّم على الحقول؛ الصغيرة تبقى قطعة واحدة."""
    out, cur, size = [], {}, 0
    for p, v in item.fields.items():
        s = len(_as_text(v["ar"])) + len(_as_text(v["en"]))
        if cur and size + s > budget:
            out.append(cur)
            cur, size = {}, 0
        cur[p] = v
        size += s
    if cur:
        out.append(cur)
    if len(out) == 1:
        return [Chunk(item, item.key, out[0])]
    return [Chunk(item, f"{item.key}#{i}", c) for i, c in enumerate(out)]


def batches_of(chunks: list[Chunk], budget: int, max_items: int) -> list[list[Chunk]]:
    out, cur, size = [], [], 0
    for c in chunks:
        if cur and (size + c.size > budget or len(cur) >= max_items):
            out.append(cur)
            cur, size = [], 0
        cur.append(c)
        size += c.size
    if cur:
        out.append(cur)
    return out


def canon_field(fld: str, valid_fields: set) -> str:
    """glm-5.2 يكتب المسار أحيانًا «fields.text» بدل «text» — نفس الحقل، فيُعاد إليه.

    بدون هذا يبقى العيب «مانعًا» لكنه لا يصل المُصلِح (لا حقل بهذا الاسم)، فتعلق
    الوحدة بلا إصلاح ولا ختم.
    """
    fld = (fld or "").strip()
    if fld in valid_fields:
        return fld
    for prefix in ("fields.", "fields[", "english.", "arabic."):
        if fld.startswith(prefix):
            rest = fld[len(prefix):].rstrip("]").strip("'\"")
            if rest in valid_fields:
                return rest
    return fld or "?"


def normalise_defects(raw: Any, valid_fields: set) -> list[dict]:
    """ناتج المراجع كما هو لا يُوثَق: خطورة مجهولة = متوسطة (الأحوط)، والحقل يُحفظ كما ورد."""
    out = []
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict):
            continue
        sev = str(d.get("severity", "")).strip().lower()
        if sev not in SEVERITIES:
            sev = "medium"
        side = "arabic" if str(d.get("side", "")).lower().startswith("ar") else "english"
        out.append({
            "field": canon_field(str(d.get("field", "")), valid_fields),
            "side": side,
            "type": str(d.get("type", "meaning"))[:40],
            "severity": sev,
            "arabic": str(d.get("arabic", ""))[:300],
            "english": str(d.get("english", ""))[:300],
            "why": str(d.get("why", ""))[:500],
            "suggestion": d.get("suggestion") if isinstance(d.get("suggestion"), (str, list)) else "",
        })
    return out


def parse_review(raw_text: str, batch: list[Chunk]) -> dict[str, list] | None:
    """{cid: defects}. معرّف غاب عن الرد = لم يُراجَع (لا يُعدّ نظيفًا)."""
    try:
        data = parse_json(raw_text)
    except json.JSONDecodeError:
        return None
    entries = data.get("items") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return None
    by_id = {c.cid: c for c in batch}
    out = {}
    for e in entries:
        if isinstance(e, dict) and e.get("id") in by_id:
            out[e["id"]] = normalise_defects(e.get("defects"), set(by_id[e["id"]].fields))
    return out


def review_message(batch: list[Chunk]) -> str:
    ids = [c.cid for c in batch]
    return (f"Review these {len(ids)} items. Your \"items\" array must hold exactly "
            f"{len(ids)} entries, ids in this order: {json.dumps(ids, ensure_ascii=False)}\n\n"
            + json.dumps({"items": [c.payload() for c in batch]}, ensure_ascii=False))


def review_batch(model: str, batch: list[Chunk], depth: int = 0) -> dict[str, list]:
    """يرجّع {cid: defects} لكل قطعة نجحت مراجعتها. المفقود يُعاد منفردًا مرة."""
    cache = _cache_load()
    result, todo = {}, []
    for c in batch:
        hit = _cache_get(cache, model, c.sha)
        if hit is not None:
            result[c.cid] = [{**d, "field": canon_field(d.get("field", ""), set(c.fields))}
                             for d in hit]
        else:
            todo.append(c)
    if not todo or CACHE_ONLY:
        return result   # CACHE_ONLY: ما لم يُراجَع يبقى «غير مراجَع» — لا يُختم ولا يُستدعى نموذج
    user = review_message(todo)
    try:
        raw, _usage = post(model, REVIEW_SYSTEM, user)
        parsed = parse_review(raw, todo)
    except RuntimeError as e:
        print(f"   ⚠️ {model}: {e}", flush=True)
        parsed = None
    parsed = parsed or {}
    for c in todo:
        if c.cid in parsed:
            _cache_put(_cache_key(model, c.sha), parsed[c.cid])
            result[c.cid] = parsed[c.cid]
    missing = [c for c in todo if c.cid not in parsed]
    if missing and depth == 0:
        for c in missing:
            result.update(review_batch(model, [c], depth=1))
    return result


# ═════════════════════════════════════════════════════════════════════════
#  Adjudications — نقض موثَّق مربوط ببصمة النص
# ═════════════════════════════════════════════════════════════════════════

def load_adjudications() -> dict:
    if ADJUDICATIONS.exists():
        return _load(ADJUDICATIONS)
    return {}


def adjudicated_for(item: Item, adj: dict) -> list[dict]:
    """النقوض السارية على هذا النص بعينه — بصمة مختلفة = لا نقض."""
    rec = adj.get(item.key)
    if not rec or rec.get("content_sha256") != item.sha:
        return []
    return [r for r in rec.get("overrides", []) if r.get("reason")]


OVERRIDABLE_DET = frozenset({"omission", "leakage"})


def _matches_override(d: dict, overrides: list[dict]) -> bool:
    for o in overrides:
        if o.get("field") == d.get("field") and o.get("type", d.get("type")) == d.get("type"):
            return True
    return False


# ═════════════════════════════════════════════════════════════════════════
#  The loop: review → fix → re-review → stamp
# ═════════════════════════════════════════════════════════════════════════

@dataclass
class Verdict:
    item: Item
    defects: dict = field(default_factory=dict)    # model → [defects]
    det: list = field(default_factory=list)
    unreviewed: list = field(default_factory=list)  # models that returned nothing

    def blocking(self, overrides: list[dict]) -> list[dict]:
        # نقضٌ موثَّق قد يغطّي «حذفًا» أو «تسرّبًا» حتميًّا مقصودًا (حديث خارج
        # الصحيحين لا يُنقل إلى الإنجليزية) — لا يغطّي أبدًا حقنة مسرد ولا إسنادًا
        # مخترعًا ولا عرض قرآن ولا كسر بنية: تلك يقين لا رأي.
        out = [d for d in self.det
               if not (d["type"] in OVERRIDABLE_DET and _matches_override(d, overrides))]
        for model, ds in self.defects.items():
            for d in ds:
                if d["severity"] in BLOCKING and not _matches_override(d, overrides):
                    out.append({**d, "model": model})
        return out

    def low(self) -> list[dict]:
        return [{"model": m, "field": d["field"], "type": d["type"], "why": d["why"][:200]}
                for m, ds in self.defects.items() for d in ds if d["severity"] == "low"]


def replay_proof(item: Item, reviewers: tuple[str, str], proof: dict) -> Verdict:
    """Replay actual raw judgments; reuse only fields equal in both languages.

    A fragment hash authenticates its recorded input, not the current pack.
    Missing current fields remain unreviewed. No combined cache entry is made.
    """
    if (proof.get("key") != item.key or proof.get("content_sha256") != item.sha
            or proof.get("prompt_version") != PROMPT_V):
        raise ValueError("proof pack fingerprint or prompt version differs")
    responses = proof.get("responses")
    if not isinstance(responses, list):
        raise ValueError("proof responses must be a list")
    verdict = Verdict(item, det=deterministic_defects(item))
    covered = {model: set() for model in reviewers}
    for response in responses:
        model = response.get("model")
        if model not in covered:
            raise ValueError("proof contains an unexpected reviewer")
        fields = response.get("fields")
        if (not isinstance(fields, dict) or not fields
                or content_sha(fields) != response.get("content_sha256")):
            raise ValueError("fragment input fingerprint differs")
        if any(not isinstance(pair, dict) or set(pair) != {"ar", "en"}
               for pair in fields.values()):
            raise ValueError("fragment fields must contain both languages")
        cid = response.get("id")
        batch_ids = response.get("batch_ids")
        if (not isinstance(batch_ids, list) or cid not in batch_ids
                or len(set(batch_ids)) != len(batch_ids)):
            raise ValueError("invalid recorded batch identifiers")
        try:
            data = parse_json(response["raw"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("invalid actual raw review") from error
        entries = data.get("items") if isinstance(data, dict) else None
        if (not isinstance(entries, list)
                or [entry.get("id") for entry in entries if isinstance(entry, dict)] != batch_ids
                or any(not isinstance(entry, dict)
                       or not isinstance(entry.get("defects"), list) for entry in entries)):
            raise ValueError("raw review does not explicitly cover its recorded batch")
        chunk = Chunk(item, cid, fields)
        parsed = parse_review(response["raw"], [chunk])
        if parsed is None or cid not in parsed:
            raise ValueError("recorded fragment has no actual judgment")
        same = {path for path, pair in fields.items() if item.fields.get(path) == pair}
        covered[model].update(same)
        verdict.defects.setdefault(model, []).extend(
            defect for defect in parsed[cid]
            if defect["field"] in same or defect["field"] not in fields)
    verdict.unreviewed = [model for model in reviewers
                          if covered[model] != set(item.fields)]
    return verdict


def review_items(items: list[Item], reviewers: tuple[str, str], workers: int,
                 budget: int, max_items: int) -> dict[str, Verdict]:
    verdicts = {it.key: Verdict(it, det=deterministic_defects(it)) for it in items}
    chunks = [c for it in items for c in chunks_of(it, budget)]
    by_cid = {c.cid: c for c in chunks}

    def run_model(model: str) -> dict[str, list]:
        batches = batches_of(chunks, budget, max_items)
        merged: dict[str, list] = {}
        done = [0]
        lock = threading.Lock()

        def one(b):
            # دفعة تسقط بعطل غير متوقَّع تُترك «غير مراجَعة» ولا تُسقط التشغيلة كلها؛
            # سقف الحساب وحده يُوقفها (UsageCapError ليس Exception عاديًّا هنا).
            try:
                r = review_batch(model, b)
            except UsageCapError:
                raise
            except Exception as e:  # noqa: BLE001
                print(f"   ⚠️ {model}: batch dropped ({type(e).__name__}: {e})", flush=True)
                r = {}
            with lock:
                merged.update(r)
                done[0] += 1
                if done[0] % 10 == 0 or done[0] == len(batches):
                    print(f"   {model}: {done[0]}/{len(batches)} batches", flush=True)

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(one, batches))
        return merged

    with ThreadPoolExecutor(max_workers=len(reviewers)) as ex:
        results = dict(zip(reviewers, ex.map(run_model, reviewers)))

    for model, merged in results.items():
        for cid, c in by_cid.items():
            v = verdicts[c.item.key]
            if cid not in merged:
                if model not in v.unreviewed:
                    v.unreviewed.append(model)
                continue
            v.defects.setdefault(model, []).extend(merged[cid])
    return verdicts


def fix_item(item: Item, blocking: list[dict]) -> dict | None:
    """يرسل الحقول المعيبة للمُصلِح ويرجّع {english, arabic, rejected} أو None.

    حقل كل عيوبه في الجانب العربي «مقفول إنجليزيًّا»: المصدر هو المعيب، والترجمة
    السليمة لا تُعاد صياغتها لتلاحق مصدرًا تالفًا (جرّبتُ بدونه فصارت
    «cyberbullying» إلى «electronic bullying» لأن العربي فيه كلمة Electronic).
    """
    relevant = [d for d in blocking if d["field"] in item.fields]
    flds = sorted({d["field"] for d in relevant})
    if not flds:
        return None
    en_fields = {d["field"] for d in relevant if d["side"] == "english"}
    payload = {
        "age_band": item.age_band,
        "fields": {p: {"arabic": item.fields[p]["ar"], "english": item.fields[p]["en"],
                       **({} if p in en_fields else {"english_locked": True})}
                   for p in flds},
        "defects": [{k: d.get(k) for k in ("field", "side", "type", "severity", "why",
                                           "arabic", "english", "suggestion")}
                    for d in relevant],
    }
    try:
        raw, _ = post(FIXER, FIX_SYSTEM, json.dumps(payload, ensure_ascii=False))
        out = parse_json(raw)
    except (RuntimeError, json.JSONDecodeError) as e:
        print(f"   ⚠️ fix {item.key}: {e}", flush=True)
        return None
    if not isinstance(out, dict):
        return None
    eng = {p: v for p, v in (out.get("english") or {}).items() if p in en_fields}
    ara = {p: v for p, v in (out.get("arabic") or {}).items()
           if p in item.fields and type(v) is type(item.fields[p]["ar"])}
    return {"english": eng, "arabic": ara, "rejected": out.get("rejected") or []}


def candidate_ok(item: Item, new_en: dict) -> list[str]:
    """البوابات الحتمية على الإصلاح المقترح قبل كتابته: بنية، مسرد، إسناد، قرآن، تسرّب.

    يُرفض الإصلاح إذا أدخل عيبًا حتميًّا جديدًا في الحقول التي يغيّرها — أو حقنة
    مسرد لم تكن قبله. عيب قديم في حقل لم يلمسه ليس ذنبه.
    """
    trial = Item(item.kind, item.key, item.en_file, item.ar_file,
                 {p: {"ar": v["ar"], "en": new_en.get(p, v["en"])} for p, v in item.fields.items()},
                 item.age_band, item.published, item.selector, [])
    before = {d["why"] for d in deterministic_defects(item) if d["field"] == "(glossary-guard)"}
    bad = []
    for d in deterministic_defects(trial):
        if d["side"] != "english":
            continue
        if d["field"] in new_en or (d["field"] == "(glossary-guard)" and d["why"] not in before):
            bad.append(f"{d['type']}@{d['field']}: {d['why']}")
    return bad


def apply_english(item: Item, new_en: dict, author: str | None = None,
                  note: str | None = None) -> None:
    """يكتب الإنجليزي الجديد، ويسجّل كاتبه (قاعدة العائلة تقرأه)، ويُسقط ختمًا بطل."""
    doc = _load(item.en_file)
    target = doc
    if item.kind == "stories":
        target = next(s for s in doc if s.get("id") == item.selector)
    for p, v in new_en.items():
        if get_leaf(target, p) is None:
            _ensure_parent(target, p)
        set_leaf(target, p, v)
        item.fields[p]["en"] = v
    if author:
        tr = _translation_block(item, doc)
        authors = list(tr.get("english_authors") or [])
        for a in (tr.get("translator_model"), author):
            if a and a not in authors:
                authors.append(a)
        tr["english_authors"] = authors
        tr["fixer_model"] = author
        tr["fixed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if note:
            tr["manual_fix_note"] = note
    _dump(item.en_file, doc)
    if item.kind == "stories":
        shutil.copyfile(STORIES_EN, STORIES_EN_MIRROR)
    if approval_state(item)[0] == "invalid":
        clear_stamp(item)


def _ensure_parent(target: Any, path: str) -> None:
    """حقل غائب عن الترجمة (أُضيف للعربي بعدها): أنشئ أباه وخانته بشكل المسار."""
    toks = parse_path(path)
    cur = target
    for tok, nxt_tok in zip(toks, toks[1:] + [None]):
        if nxt_tok is None:
            if isinstance(tok, int) and isinstance(cur, list):
                while len(cur) <= tok:
                    cur.append(None)
            return
        blank = [] if isinstance(nxt_tok, int) else {}
        if isinstance(tok, int):
            while len(cur) <= tok:
                cur.append(None)
            if cur[tok] is None:
                cur[tok] = blank
        elif cur.get(tok) is None:
            cur[tok] = blank
        cur = cur[tok]


def _replace_literal(text: str, old: str, new: str, key: str | None = None) -> str | None:
    """يستبدل نصًّا مُرمَّزًا JSON مرة واحدة بالضبط، أو None إن لم يكن فريدًا.

    يُجرَّب أولًا مقيَّدًا باسم المفتاح (`"text_simplified": "…"`): وحدات المعرفة
    الأحدث تحمل نفس النص في text_original وtext_simplified، فالسلسلة وحدها تقع
    مرتين ولا يُعرف أيّهما المقصود — والأصل (text_original) لا يُمسّ.
    """
    enc_old = json.dumps(old, ensure_ascii=False)
    enc_new = json.dumps(new, ensure_ascii=False)
    if key:
        pat = re.compile(re.escape(json.dumps(key, ensure_ascii=False)) + r"(\s*:\s*)"
                         + re.escape(enc_old))
        hits = pat.findall(text)
        if len(hits) == 1:
            return pat.sub(lambda m: json.dumps(key, ensure_ascii=False) + m.group(1)
                           + enc_new, text, count=1)
    if text.count(enc_old) != 1:
        return None
    return text.replace(enc_old, enc_new)


def apply_arabic(item: Item, new_ar: dict) -> None:
    """يكتب إصلاح المصدر العربي **نصًّا لا إعادة تسلسل**.

    ٥١ وحدة عربية وبنكان بتنسيق لا يعيده json.dumps (مصفوفات مضغوطة، بلا سطر
    أخير) — إعادة كتابة الملف كلّه تُخرج diff بمئات الأسطر لتصحيح كلمة، في ملفات
    يعدّلها وكلاء آخرون بالتوازي. فالاستبدال حرفيّ على السلسلة المُرمَّزة، ويُرفض
    إن لم تكن فريدة في الملف.
    """
    text = item.ar_file.read_text(encoding="utf-8")
    for p, v in new_ar.items():
        old = item.fields[p]["ar"]
        pairs = list(zip(old, v)) if isinstance(old, list) else [(old, v)]
        leaf_key = None if isinstance(old, list) else parse_path(p)[-1]
        for o, n in pairs:
            if o == n:
                continue
            out = _replace_literal(text, o, n, leaf_key if isinstance(leaf_key, str) else None)
            if out is None:
                raise ValueError(f"{item.key} · {p}: Arabic string not unique in "
                                 f"{item.ar_file.name} — fix by hand")
            text = out
        item.fields[p]["ar"] = v
    json.loads(text)  # لا نكتب ملفًا مكسورًا
    item.ar_file.write_text(text, encoding="utf-8")
    if item.en_file.exists() and approval_state(item)[0] == "invalid":
        clear_stamp(item)   # المصدر تغيّر بعد المراجعة: ختم الإنجليزي لم يعد يصدق


def run(items: list[Item], args) -> dict:
    reviewers = (args.reviewer_a, args.reviewer_b)
    adj = load_adjudications()
    today = args.date or date.today().isoformat()
    report = {"stamped": [], "fixed": set(), "arabic_proposals": [], "arabic_applied": [],
              "unresolved": {}, "fix_rejected": [], "rounds": 0}
    queue = load_queue()
    pending = []
    for it in items:
        held = queue.get(it.key) or {}
        if held.get("category") == "source-unverified":
            # الختم يشهد بالتطابق، والعربي هنا غير موثَّق: لا يُشهد لنصٍّ لم يُثبت أصله.
            report["unresolved"][it.key] = [{"why": "source-unverified hold: "
                                                    + str(held.get("reason", ""))[:120]}]
            continue
        why = family_conflict(it, reviewers, queue)
        if why:
            report["unresolved"][it.key] = [{"why": why}]
            continue
        pending.append(it)
    if len(pending) != len(items):
        print(f"   ⏭️  {len(items) - len(pending)} وحدة لا تُراجَع هنا "
              "(قيد source-unverified أو تعارض عائلة)", flush=True)
    for rnd in range(1, args.rounds + 1):
        report["rounds"] = rnd
        print(f"\n━━ جولة {rnd}: {len(pending)} وحدة · {reviewers[0]} + {reviewers[1]}", flush=True)
        try:
            proof_path = getattr(args, "coverage_proof", None)
            if proof_path:
                proof = _load(proof_path)
                verdicts = {it.key: replay_proof(it, reviewers, proof) for it in pending}
            else:
                verdicts = review_items(pending, reviewers, args.workers, args.budget, args.max_items)
        except UsageCapError as e:
            print(f"\n⏸️  سقف استهلاك Ollama: {e}\n   الكاش محفوظ؛ أعد التشغيل لاحقًا.", flush=True)
            report["capped"] = True
            break
        to_fix: list[tuple[Item, list]] = []
        for key, v in verdicts.items():
            it = v.item
            overrides = adjudicated_for(it, adj)
            block = v.blocking(overrides)
            if v.unreviewed:
                report["unresolved"][key] = [{"why": f"no review from {m}"} for m in v.unreviewed]
                continue
            if not block:
                rec = build_record(it, reviewers, rnd, key in report["fixed"], v.low(),
                                   overrides, today)
                if proof_path:
                    rec["auto_review"]["coverage_proof_sha256"] = hashlib.sha256(
                        proof_path.read_bytes()).hexdigest()
                    rec["auto_review"]["coverage_mode"] = "actual raw responses; exact current field equality"
                if not args.dry_run:
                    write_stamp(it, rec)
                report["stamped"].append(key)
                report["unresolved"].pop(key, None)
                continue
            report["unresolved"][key] = block
            if rnd < args.rounds and not args.no_fix:
                to_fix.append((it, block))
        if not to_fix:
            break
        print(f"   🔧 {len(to_fix)} وحدة إلى المُصلِح ({FIXER})", flush=True)
        # النداءات متوازية، والكتابة متسلسلة: القصص الأربع عشرة ملف واحد.
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            try:
                fixes = list(ex.map(lambda job: fix_item(*job), to_fix))
            except UsageCapError as e:
                print(f"\n⏸️  سقف استهلاك Ollama أثناء الإصلاح: {e}", flush=True)
                report["capped"] = True
                break
        pending = []
        for (it, _block), fx in zip(to_fix, fixes):
            pending.append(it)
            if not fx:
                continue
            key = it.key
            seen = {(x["key"], x["field"], json.dumps(x["new"], ensure_ascii=False))
                    for x in report["arabic_proposals"]}
            for p, v_ar in fx["arabic"].items():
                sig = (key, p, json.dumps(v_ar, ensure_ascii=False))
                if v_ar != it.fields[p]["ar"] and sig not in seen:
                    report["arabic_proposals"].append({
                        "key": key, "file": str(it.ar_file.relative_to(ROOT)),
                        "selector": it.selector, "field": p,
                        "old": it.fields[p]["ar"], "new": v_ar})
            report["fix_rejected"] += [{"key": key, **r} for r in fx["rejected"]
                                       if isinstance(r, dict)]
            if args.apply_arabic and not args.dry_run:
                changed = {p: a for p, a in fx["arabic"].items()
                           if a != it.fields[p]["ar"]
                           and not arabic_change_problem(it.fields[p]["ar"], a)}
                if changed:
                    apply_arabic(it, changed)
                    report["arabic_applied"].append(key)
            new_en = {p: e for p, e in fx["english"].items() if e != it.fields[p]["en"]}
            if new_en:
                bad = candidate_ok(it, new_en)
                if bad:
                    report["fix_rejected"].append({"key": key, "field": "(gate)",
                                                   "why": "; ".join(bad)})
                elif not args.dry_run:
                    apply_english(it, new_en, author=FIXER)
                    report["fixed"].add(key)
        if args.report:   # تقرير وسيط: تشغيلة طويلة تنقطع لا تضيّع ما حُسم
            _dump_report(args.report, report)
    report["fixed"] = sorted(report["fixed"])
    return report


def _dump_report(path: Path, report: dict) -> None:
    out = {**report, "fixed": sorted(report["fixed"])}
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════
#  check — البوابة الحتمية (pre-commit)، بلا شبكة
# ═════════════════════════════════════════════════════════════════════════

def is_translation(item: Item) -> bool:
    """فيه إنجليزي فعلًا؟ ملف إنجليزي نسخةٌ من العربي حرفيًّا ليس ترجمة تحتاج ختمًا."""
    return any(v["en"] not in (None, "", []) and v["en"] != v["ar"] for v in item.fields.values())


NO_STAMP = "approved_by: null — published English that never passed the gate"


def check_item(item: Item, queue: dict | None = None) -> str | None:
    """None إن كان الإنجليزي المنشور مختومًا ختمًا يصدق على نصّه، أو مُدرَجًا في
    الطابور بنفس النص بالضبط؛ وإلا السبب."""
    if not item.published or not is_translation(item):
        return None
    state, why = approval_state(item)
    if state == "valid":
        return None
    if state == "invalid":
        return why
    held = (load_queue() if queue is None else queue).get(item.key)
    if held is None:
        return NO_STAMP
    bad = queue_entry_problem(item.key, held)
    if bad:
        return f"queue entry is invalid: {bad}"
    if held["content_sha256"] != item.sha:
        return ("queued at a different text — it changed after it was queued; review it, or "
                f"re-queue it with a reason (`{TOOL_REL} queue --only {item.key} --reason …`)")
    return None


def _self_test() -> bool:
    ok = True

    def expect(cond, msg):
        nonlocal ok
        if not cond:
            print(f"   🔴 self-test: {msg}")
            ok = False

    expect(parse_path("pages[2].text") == ["pages", 2, "text"], "parse_path nested")
    expect(parse_path("primary_reference.info") == ["primary_reference", "info"], "parse_path dotted")
    for bad in ("", ".a", "a.", "a..b", "a[x]"):
        try:
            parse_path(bad)
            expect(False, f"parse_path accepted {bad!r}")
        except ValueError:
            pass
    doc = {"pages": [{"text": "a"}, {"text": "b"}]}
    set_leaf(doc, "pages[1].text", "c")
    expect(get_leaf(doc, "pages[1].text") == "c", "set/get round-trip")
    s = stamp_value(("deepseek-v4-pro", "glm-5.2"), "2026-10-04")
    expect(parse_stamp(s) == {"reviewers": ["deepseek-v4-pro", "glm-5.2"], "date": "2026-10-04"},
           "stamp round-trip")
    expect(parse_stamp(stamp_value(("mistral-large-3:675b", "glm-5.2"), "2026-10-04")) is not None,
           "stamp with tagged model")
    expect(parse_stamp("auto-review:claude-opus:2026-10-04") ==
           {"reviewers": ["claude-opus"], "date": "2026-10-04"}, "single-reviewer stamp")
    for bad in (None, "", "Sheikh X", "auto-review:a+:2026-10-04", "auto-review::2026-10-04",
                "auto-review:a+b:2026-13-40", "auto-review:a+b"):
        expect(parse_stamp(bad) is None, f"parse_stamp accepted {bad!r}")
    f1 = {"t": {"ar": "صدق", "en": "Truth"}, "s": {"ar": "أ", "en": "A"}}
    f2 = {"s": {"ar": "أ", "en": "A"}, "t": {"ar": "صدق", "en": "Truth"}}
    f3 = {"t": {"ar": "صدق", "en": "Truth."}, "s": {"ar": "أ", "en": "A"}}
    f4 = {"t": {"ar": "سفينة", "en": "Truth"}, "s": {"ar": "أ", "en": "A"}}
    expect(content_sha(f1) == content_sha(f2), "sha must ignore key order")
    expect(content_sha(f1) != content_sha(f3), "sha must see an English change")
    expect(content_sha(f1) != content_sha(f4), "sha must see an Arabic change")
    expect(leaked_arabic("Be gentle ﷺ ﴿وَقُل رَّبِّ﴾ «خيركم»") == "", "allowed Arabic spans")
    expect(leaked_arabic("Practice الصبر daily") != "", "bare Arabic leaks")
    for name, fam in (("claude-opus", "anthropic"), ("claude-opus-5.5", "anthropic"),
                      ("mistral-large-3:675b", "mistral"), ("deepseek-v4-pro", "deepseek"),
                      ("glm-5.2", "zhipu"), ("qwen2.5:3b", "alibaba"),
                      ("command-r7b-arabic", "cohere"), ("Sheikh Ahmad", None), ("", None)):
        expect(model_family(name) == fam, f"model_family({name!r}) → {model_family(name)!r}")
    good = {"category": "awaiting-review", "reason": "r", "content_sha256": "a" * 64,
            "queued_on": "2026-10-04"}
    expect(queue_entry_problem("k", good) is None, "valid queue entry")
    for k, v in (("category", "later"), ("reason", " "), ("content_sha256", "abc"),
                 ("queued_on", "soon")):
        expect(queue_entry_problem("k", {**good, k: v}) is not None, f"queue entry with bad {k}")
    return ok


def _git_head_json(path: Path):
    import subprocess
    try:
        out = subprocess.run(["git", "show", f"HEAD:{path.relative_to(ROOT)}"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError):
        return None


def _fields_for(item: Item, ar_doc, en_doc) -> dict | None:
    """حقول الوحدة كما يبنيها مجمِّعها، من وثيقتين معطاتين (لمقارنة HEAD)."""
    if ar_doc is None or en_doc is None:
        return None
    if item.kind in CURRICULUM_FIELDS:
        return _field_pairs(ar_doc, en_doc, CURRICULUM_FIELDS[item.kind])
    if item.kind == "kb_units":
        return _field_pairs(ar_doc, en_doc, UNIT_FIELDS)
    if item.kind == "stories":
        a = next((s for s in ar_doc if s.get("id") == item.selector), None)
        e = next((s for s in en_doc if s.get("id") == item.selector), None)
        return None if a is None or e is None else {
            p: {"ar": x, "en": y} for p, x, y in walk_text_pairs(a, e)}
    if item.kind in ("banks", "offscreen"):
        return {p: {"ar": x, "en": y} for p, x, y in walk_text_pairs(ar_doc, en_doc)}
    return None   # adhkar: لا نعيد بناءه هنا — يُعامَل ختم HEAD كأنه صالح (الأحوط)


def _head_stamp_holds(item: Item, head_en) -> bool:
    """هل كان اعتماد HEAD صادقًا على نصّ HEAD؟ ما كان بائتًا أصلًا لا يُحمى،
    وتوقيعٌ بلا بصمة لم يصدق على شيءٍ قط."""
    tr = (head_en or {}).get("translation") or {}
    if parse_stamp(tr.get("approved_by")):
        fp = (tr.get("auto_review") or {}).get("content_sha256")
    else:
        fp = (tr.get("approval") or {}).get("content_sha256")
    if not fp:
        return False
    fields = _fields_for(item, _git_head_json(item.ar_file), _git_head_json(item.en_file))
    if fields is None:
        return True
    return fp == content_sha(fields)


def _head_en(item: Item) -> dict | None:
    """نسخة الترجمة في HEAD (للقصص: القصة بعينها)، أو None إن كانت جديدة."""
    import subprocess
    rel = str(item.en_file.relative_to(ROOT))
    try:
        out = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        doc = json.loads(out)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    if item.kind == "stories":
        return next((s for s in doc if s.get("id") == item.selector), None)
    return doc


def staged_check_item(item: Item, queue: dict | None = None) -> str | None:
    """البوابة على الـcommit — نفس حكم `check` في CI، وثلاثة قيود يراها HEAD وحده:

    · ترجمة جديدة (غير موجودة في HEAD) تحتاج ختمًا صالحًا؛ الطابور لا يحملها.
    · لا يُضاف إنجليزيٌّ جديد إلى وحدة غير مختومة — وإن كانت في الطابور.
    · ختمٌ كان يصدق في HEAD لا يسقط إلا بقرارٍ مسجَّل: إدراجٌ في الطابور بسبب
      (`queue --reason`)، يراه المراجع في الـdiff.
    وما عدا ذلك يجوز تصحيحه دون ختم — إصلاح تلفٍ طبي في المصدر لا ينتظر حصّة
    نموذج — لكن الوحدة تُعاد إلى الطابور ببصمة نصّها الجديد، وإلا أوقفها CI.
    """
    queue = load_queue() if queue is None else queue
    if not item.published or not is_translation(item):
        return None
    state, why = approval_state(item)
    if state == "valid":
        return None
    if state == "invalid":
        # ختمٌ موجود لا يصدق على النص: لا يدخل أبدًا، أيًّا كان HEAD. (دخل واحدٌ
        # كذلك بعد إعادة الترتيب على #27: غيّر #27 العربي، فبطل ختمٌ كُتب قبله،
        # ومرّ لأن HEAD كان «متراكمًا» — والملف يدّعي مراجعةً لنصٍّ ليس نصّه.)
        return why
    head = _head_en(item)
    if head is None:
        return (NO_STAMP + " — and it is new: new English needs a review stamp "
                "(the queue only holds English that was already live)")
    added = [p for p, v in item.fields.items()
             if get_leaf(head, p) in (None, "", []) and v["en"] not in (None, "", [])]
    if added:
        return ("adds English to a unit that has not passed review yet ("
                + ", ".join(added[:3]) + ") — run the review first")
    held = check_item(item, queue)
    if held is None:
        return None
    if (head.get("translation") or {}).get("approved_by") and _head_stamp_holds(item, head):
        return ("drops a review stamp that held — re-review it, or record the demotion with a "
                f"reason: `{TOOL_REL} queue --only {item.key} --reason …`")
    return held


def staged_paths() -> set[str] | None:
    """الملفات المرحَّلة للـcommit (نسبية للجذر)، أو None خارج git."""
    import subprocess
    try:
        out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {line.strip() for line in out.splitlines() if line.strip()}


def touched_by(item: Item, paths: set[str]) -> bool:
    """الوحدة يمسّها الـcommit إن لمس ترجمتها **أو مصدرها العربي**."""
    return any(str(f.relative_to(ROOT)) in paths for f in (item.en_file, item.ar_file))


def cmd_check(kinds: list[str], staged: bool = False) -> int:
    print("=" * 66)
    print("  EN PARITY GATE — كل إنجليزي منشور مختوم وختمه يطابق نصّه")
    print("=" * 66)
    if not _self_test():
        print("\n⛔ self-tests فشلت — الفحص لاغٍ. صلّح الفحص لا تتخطّاه.")
        return 2
    items = collect(kinds)
    queue = load_queue()
    all_keys = {it.key for it in items}
    if staged:
        # pre-commit: يُحاسَب الـcommit على ما يلمسه — ترجمةً أو مصدرًا أو إدراجًا في
        # الطابور. وحدة لم يلمسها لا تُوقفه (وإلا أوقف وكيلٌ واحد بملف بائت كلَّ من
        # بعده)؛ الصورة الكاملة في `check` بلا --staged (وهو ما يجري في CI).
        paths = staged_paths()
        if paths is not None:
            keys: set[str] = set()
            if str(QUEUE.relative_to(ROOT)) in paths:
                head_q = (_git_head_json(QUEUE) or {}).get("units") or {}
                keys = {k for k in set(head_q) | set(queue) if head_q.get(k) != queue.get(k)}
            items = [it for it in items if touched_by(it, paths) or it.key in keys]
            print(f"  (staged) وحدات يمسّها هذا الـcommit: {len(items)}")
    bad = [(it, why) for it in items
           if (why := (staged_check_item(it, queue) if staged else check_item(it, queue)))]
    for k, entry in queue.items():
        why = queue_entry_problem(k, entry)
        if why and (not staged or k in {it.key for it in items}):
            print(f"  ❌ queue entry {k}: {why}")
            bad.append((None, f"queue:{k}"))
    if STORIES_EN.exists() and STORIES_EN_MIRROR.exists() \
            and (not staged or any(it.kind == "stories" for it in items)) \
            and STORIES_EN.read_bytes() != STORIES_EN_MIRROR.read_bytes():
        print("  ❌ docs/stories.en.json ≠ mobile/assets/data/stories_en.json")
        bad.append((None, "mirror"))
    by_kind: dict[str, int] = {}
    for it in items:
        by_kind[it.kind] = by_kind.get(it.kind, 0) + 1
    print("  مفحوص: " + " · ".join(f"{k} {n}" for k, n in by_kind.items()))
    held: dict[str, int] = {}
    for it in items:
        e = queue.get(it.key)
        if e and approval_state(it)[0] == "none" and check_item(it, queue) is None \
                and it.published and is_translation(it):
            held[e["category"]] = held.get(e["category"], 0) + 1
    if held:
        print("  في الطابور (حيٌّ بلا ختم، مربوط ببصمة نصّه): "
              + " · ".join(f"{c} {n}" for c, n in sorted(held.items())))
    if not staged and set(kinds) == set(COLLECTORS):
        orphans = sorted(k for k in queue if k not in all_keys)
        if orphans:
            print(f"  ⚠️ {len(orphans)} إدراجًا في الطابور لوحداتٍ لم تعد موجودة "
                  f"(سُحبت؟): {', '.join(orphans[:6])} — `unqueue` ينظّفها")
    if bad:
        print(f"\n  ❌ {len(bad)} وحدة لم تجتز البوابة:")
        for it, why in bad[:40]:
            if it is not None:
                print(f"     {it.key}  ({it.rel()}): {why}")
        if len(bad) > 40:
            print(f"     … و{len(bad) - 40} أخرى")
        keys_s = ",".join(it.key for it, _ in bad[:20] if it is not None)
        print("\n  الإصلاح: راجِع واختم (يحتاج OLLAMA_API_KEY):")
        print(f"     python3 {TOOL_REL} run --only {keys_s}")
        print("  أو اسحب الترجمة إن تعذّر توثيقها:")
        print(f"     python3 {TOOL_REL} unpublish --only <key> --reason '…'")
        print("  أو — لإنجليزيٍّ كان حيًّا قبل هذا التعديل فقط — سجّل انتظاره بسبب:")
        print(f"     python3 {TOOL_REL} queue --only <key> --reason '…'")
        return 1
    print("  ✅ كل الإنجليزي المنشور مختوم وختمه يطابق نصّه، أو مُدرَج في الطابور بنصّه نفسه.")
    return 0


# ═════════════════════════════════════════════════════════════════════════
#  inventory / unpublish
# ═════════════════════════════════════════════════════════════════════════

def cmd_inventory(kinds: list[str]) -> None:
    items = collect(kinds)
    queue = load_queue()
    rows: dict[str, dict] = {}
    cols = ("units", "null", "queued", "src-hold", "stamped", "stale", "human")
    for it in items:
        r = rows.setdefault(it.kind, dict.fromkeys(cols, 0))
        r["units"] += 1
        stamp, rec = read_stamp(it)
        if not stamp:
            e = queue.get(it.key)
            if e and check_item(it, queue) is None:
                r["src-hold" if e.get("category") == "source-unverified" else "queued"] += 1
            else:
                r["null"] += 1
        elif parse_stamp(stamp):
            r["stamped" if rec.get("content_sha256") == it.sha else "stale"] += 1
        else:
            r["human"] += 1
    print(f"{'kind':12} " + " ".join(f"{c:>8}" for c in cols))
    for k, r in rows.items():
        print(f"{k:12} " + " ".join(f"{r[c]:>8}" for c in cols))
    # الفجوة: مصادر عربية بلا نظير إنجليزي.
    print("\nArabic sources with no English counterpart:")
    for kind in ("lessons", "paths", "daily_tips"):
        miss = [f.name for f in sorted((CURRICULUM / kind).glob("*.json"))
                if not (I18N_EN / kind / f.name).exists()]
        print(f"  {kind:12} {len(miss)}")
    for sub in ("agreements", "missions", "license"):
        miss = [f.name for f in sorted((CURRICULUM / sub).glob("*.json"))
                if not (I18N_EN / sub / f.name).exists()]
        print(f"  {sub:12} {len(miss)}  {' '.join(miss)}")
    en_ids = {s["id"] for s in _load(STORIES_EN)} if STORIES_EN.exists() else set()
    miss = [s["id"] for s in _load(STORIES_AR) if s["id"] not in en_ids]
    print(f"  {'stories':12} {len(miss)}  {' '.join(miss)}")


UNITS_INDEX = ROOT / "knowledge_base" / "units_index.json"


def _drop_from_units_index(unit_ids: list[str]) -> None:
    """يُخرج الوحدات المسحوبة من units_index.json تعديلًا لا إعادة توليد.

    check_kb_integrity يُوقف الـcommit إن خالف total_units عدد الملفات، وإعادة
    التوليد الكاملة (build_vector_db) تلمس ١٧٧٦ مدخلًا وطابعًا زمنيًّا — تعارضٌ مضمون
    مع كل فرع آخر يمسّ الوحدات.
    """
    if not UNITS_INDEX.exists() or not unit_ids:
        return
    idx = _load(UNITS_INDEX)
    gone = set(unit_ids)
    kept = []
    for u in idx.get("units", []):
        if u.get("id") in gone:
            dom = u.get("domain")
            if dom in idx.get("by_domain", {}):
                idx["by_domain"][dom] -= 1
            continue
        kept.append(u)
    idx["units"] = kept
    idx["total_units"] = len(kept)
    _dump(UNITS_INDEX, idx)


def cmd_unpublish(items: list[Item], reason: str, with_source: bool = False) -> None:
    """ينقل الترجمة خارج ما يُحمَّل؛ المستخدم الإنجليزي يرجع للعربي. لا حذف.

    `with_source` لوحدات المعرفة فقط: حين يثبت أن **المصدر العربي نفسه** مختلَق أو
    تالف بلا رجعة (ملخّص اخترع معنى لحروف PDF مقلوبة)، فبقاؤه حيًّا في الاسترجاع
    العربي هو الخيار الأقل أمانًا وإن بدا محافظًا.
    """
    if not reason:
        sys.exit("❌ --reason مطلوب: السحب بلا سبب مكتوب لا يُراجَع")
    manifest_p = UNPUBLISHED / "MANIFEST.json"
    manifest = _load(manifest_p) if manifest_p.exists() else []
    dropped_ids: list[str] = []
    for it in items:
        if it.kind not in ("lessons", "paths", "daily_tips", "kb_units"):
            sys.exit(f"❌ {it.kind}: لا سحب لملف متعدد العناصر — أصلحه أو أعد العنصر للعربي")
        moves = [(it.en_file, UNPUBLISHED / it.kind / it.en_file.name)]
        if with_source:
            if it.kind != "kb_units":
                sys.exit("❌ --with-source لوحدات المعرفة فقط")
            moves.append((it.ar_file, UNPUBLISHED / "kb_units_source" / it.ar_file.name))
        for src, dest in moves:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if it.kind == "kb_units":
                dropped_ids.append(_load(src).get("id", src.stem))
            shutil.move(str(src), dest)
            manifest.append({"key": it.key, "kind": it.kind, "from": str(src.relative_to(ROOT)),
                             "to": str(dest.relative_to(ROOT)), "reason": reason,
                             "on": date.today().isoformat()})
            print(f"  ↩︎ {src.relative_to(ROOT)} → {dest.relative_to(ROOT)}")
    _dump(manifest_p, manifest)
    _drop_from_units_index(dropped_ids)
    queue = load_queue()
    if any(it.key in queue for it in items):
        save_queue({k: v for k, v in queue.items() if k not in {it.key for it in items}})


_AYAH_SPAN = re.compile(r"﴿[^﴾]*﴾")


def arabic_change_problem(old: Any, new: Any) -> str | None:
    """إصلاح عربي مقترح لا يُكتب إن لمس آيةً أو غيّر بنية الحقل.

    الآيات تطابق المصحف بحارس (check_quran_citations) — ونموذج «يصحّح» رسمها
    هو بالضبط التحريف الذي وُضع الحارس لأجله.
    """
    if type(old) is not type(new):
        return "type changed"
    if isinstance(old, list):
        if len(old) != len(new):
            return "list length changed"
        for a, b in zip(old, new):
            why = arabic_change_problem(a, b)
            if why:
                return why
        return None
    if _AYAH_SPAN.findall(old or "") != _AYAH_SPAN.findall(new or ""):
        return "touches Qur'anic text inside ﴿﴾"
    if FOREIGN.search(new or ""):
        return "introduces CJK/Cyrillic"
    return None


def cmd_apply_arabic(path: Path) -> int:
    """يطبّق إصلاحات المصدر العربي **المفحوصة** — قائمة {key, field, old, new}.

    لا يكتب إلا إذا كان العربي الحالي يطابق `old` حرفيًّا: اقتراح قديم على نصٍّ
    تغيّر بعده لا يُطبَّق فوقه.
    """
    props = _load(path)
    by_key = {it.key: it for it in collect(sorted(COLLECTORS))}
    applied = skipped = 0
    for pr in props:
        it = by_key.get(pr["key"])
        fld = pr["field"]
        if it is None or fld not in it.fields:
            print(f"  ⚠️ {pr['key']} · {fld}: not found")
            skipped += 1
            continue
        if it.fields[fld]["ar"] != pr["old"]:
            print(f"  ⚠️ {pr['key']} · {fld}: Arabic changed since the proposal — skipped")
            skipped += 1
            continue
        why = arabic_change_problem(pr["old"], pr["new"])
        if why:
            print(f"  ⛔ {pr['key']} · {fld}: {why}")
            skipped += 1
            continue
        try:
            apply_arabic(it, {fld: pr["new"]})
        except ValueError as e:
            print(f"  ⛔ {e}")
            skipped += 1
            continue
        applied += 1
    print(f"  ✅ applied {applied} · skipped {skipped}")
    return 0 if not skipped else 1


MANUAL_REVIEWER = "claude-opus"


def cmd_stamp_reviewed(items: list[Item], reviewer: str, notes_path: Path | None) -> int:
    """يختم وحداتٍ راجعها مراجعٌ واحد بالمعيار نفسه (REVIEW_SYSTEM) — بلا نداء نموذج.

    وُضع لأسبوعٍ أغلق فيه السقف الأسبوعي Ollama Cloud (والمفتاح يخدم نظامًا حيًّا):
    الترجمات الأصلية من mistral (عائلة غير Anthropic)، فمراجعة Claude لها مراجعةٌ
    من عائلة مختلفة. ولهذا شرطان لا يُتساهل فيهما:
      · الحرّاس الحتمية تمرّ (ما لم يُنقض المسموح نقضه بسبب مكتوب)؛
      · الإنجليزي الذي كتبه Claude نفسه لا يُختم هنا — ينتظر مراجعًا من عائلة أخرى.
    والختم يحمل اسم المراجع ('auto-review:claude-opus:<date>') فيُميَّز عن ختم النموذجين.
    """
    notes = _load(notes_path) if notes_path else {}
    adj = load_adjudications()
    queue = load_queue()
    today = date.today().isoformat()
    done = refused = 0
    for it in items:
        why = _vouch_refusal(it, queue)
        if not why:
            # القاعدة كانت مكتوبة هنا ولا يفرضها شيء — فختم Claude ترجماتٍ كتبها
            # Claude ممكنًا بأمرٍ واحد (مراجعة PR #20). الآن تُفرض بسجل الكتّاب.
            why = family_conflict(it, (reviewer,), queue)
        if why:
            print(f"  ⛔ {it.key}: {why}")
            refused += 1
            continue
        overrides = adjudicated_for(it, adj)
        blocking = [d for d in deterministic_defects(it)
                    if not (d["type"] in OVERRIDABLE_DET and _matches_override(d, overrides))]
        if blocking:
            print(f"  ⛔ {it.key}: deterministic guard — {blocking[0]['type']}@{blocking[0]['field']}")
            refused += 1
            continue
        rec = build_record(it, (reviewer,), 1, False, notes.get(it.key, []), overrides, today)
        rec["auto_review"]["prompt_version"] = f"manual:{PROMPT_V}"
        rec["auto_review"]["meaning"] = (
            "deterministic guards passed and one reviewer from a model family different from "
            "every author of the English read the Arabic and English side by side against the "
            "review rubric and found no medium/high defect in this exact text; certifies that "
            "the English matches the Arabic, not that the Arabic is faithful to its own source; "
            "not a scholar's ijazah")
        write_stamp(it, rec)
        done += 1
    print(f"  ✅ stamped {done} · refused {refused}")
    return 0 if not refused else 1


def _vouch_refusal(item: Item, queue: dict) -> str | None:
    """ما يمنع أي ختمٍ أو توقيع: لا شيء يُختم بلا ترجمة، ولا عربيٌّ معلَّق التوثيق."""
    if not is_translation(item):
        return "nothing to vouch for — the English is empty or the Arabic verbatim"
    held = queue.get(item.key) or {}
    if held.get("category") == "source-unverified":
        return ("source-unverified hold — the Arabic is not verified against its source; "
                f"release it (`unqueue`) only after re-extraction: {held.get('reason', '')[:100]}")
    return None


def cmd_queue(items: list[Item], reason: str, category: str, authors: list[str]) -> int:
    """يُدرج إنجليزيًّا حيًّا بلا ختم في الطابور، مربوطًا ببصمة نصّه الحالي، بسبب مكتوب.

    ما يُدرَج لا يُشهد له: إن كان مختومًا يُسقط ختمه (الإدراج نفسه قرار «لا نشهد
    له الآن»). ولا يُدرَج إنجليزيٌّ لم يكن حيًّا في HEAD — الطابور ليس طريقًا لنصٍّ
    جديد يتخطّى المراجعة.
    """
    if not reason.strip():
        sys.exit("❌ --reason مطلوب: إدراجٌ بلا سبب ختمٌ بلا اسم")
    if category not in QUEUE_CATEGORIES:
        sys.exit(f"❌ --category: {sorted(QUEUE_CATEGORIES)}")
    queue = load_queue()
    today = date.today().isoformat()
    done = refused = 0
    for it in items:
        if not it.published or not is_translation(it):
            print(f"  · {it.key}: unpublished or not a translation — nothing to hold")
            continue
        if _head_en(it) is None:
            print(f"  ⛔ {it.key}: new English (not in HEAD) — review it; the queue holds live text only")
            refused += 1
            continue
        if clear_stamp(it):
            print(f"  ↓ {it.key}: stamp removed — the queue holds what is not vouched for")
        prev = queue.get(it.key) or {}
        names = list(prev.get("english_authors") or [])
        for a in authors:
            if a not in names:
                names.append(a)
        entry = {"category": category, "reason": reason.strip(), "content_sha256": it.sha,
                 "queued_on": today}
        if names:
            entry["english_authors"] = names
        queue[it.key] = entry
        done += 1
    save_queue(queue)
    print(f"  ✅ queued {done} · refused {refused}")
    return 0 if not refused else 1


def cmd_unqueue(keys: list[str]) -> int:
    """يرفع الإدراج (بعد مراجعةٍ أو إعادة استخراج، أو لوحدةٍ سُحبت). لا يختم شيئًا."""
    queue = load_queue()
    gone = [k for k in keys if queue.pop(k, None) is not None]
    save_queue(queue)
    print(f"  ✅ unqueued {len(gone)} of {len(keys)}")
    return 0


def cmd_sign(items: list[Item], by: str) -> int:
    """توقيع إنسانٍ قرأ النصّين — بالبصمة نفسها التي يحملها الختم الآلي.

    كان أي `approved_by` لا يبدأ بـ`auto-review:` يُقبل «توقيعًا بشريًّا» إلى الأبد،
    ولو تغيّر النص بعده كله. الآن يُكتب بهذا الأمر وحده، ويبطل بأي تعديل.
    """
    by = (by or "").strip()
    if not by or by.startswith(STAMP_PREFIX) or model_family(by):
        sys.exit("❌ --by: اسم إنسانٍ قرأ النصّين — لا نموذج (النماذج تختم بـrun أو stamp-reviewed)")
    queue = load_queue()
    done = refused = 0
    for it in items:
        why = _vouch_refusal(it, queue)
        bad = [d for d in deterministic_defects(it)]
        if why or bad:
            print(f"  ⛔ {it.key}: {why or bad[0]['type'] + '@' + bad[0]['field']}")
            refused += 1
            continue
        doc = _load(it.en_file)
        tr = _translation_block(it, doc)
        tr["approved_by"] = by
        tr["approval"] = {"by": by, "content_sha256": it.sha,
                          "signed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "meaning": "a person read this exact Arabic and English side by side"}
        tr.pop("auto_review", None)
        _settle_queue_entry(it, tr)
        if it.kind in CURRICULUM_FIELDS and isinstance(doc, dict) and "approved_by" in doc:
            doc["approved_by"] = by
        _dump(it.en_file, doc)
        if it.kind == "stories":
            shutil.copyfile(STORIES_EN, STORIES_EN_MIRROR)
        done += 1
    print(f"  ✅ signed {done} · refused {refused}")
    return 0 if not refused else 1


# ═════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    def positive_int(value: str) -> int:
        number = int(value)
        if number <= 0:
            raise argparse.ArgumentTypeError("must be a positive integer")
        return number

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("command", choices=("inventory", "check", "run", "unpublish", "apply-arabic",
                                        "stamp-reviewed", "queue", "unqueue", "sign"))
    ap.add_argument("--kind", action="append", choices=sorted(COLLECTORS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", help="مفاتيح مفصولة بفواصل، أو @ملف (سطر لكل مفتاح)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--unstamped", action="store_true", help="فقط ما لم يجتز البوابة بعد")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--request-timeout", type=positive_int, default=600,
                    help="timeout in seconds per model request")
    ap.add_argument("--request-attempts", type=positive_int, default=8,
                    help="maximum attempts per model request")
    ap.add_argument("--workers", type=int, default=2, help="خيوط لكل مراجع")
    ap.add_argument("--max-concurrent", type=int, default=3,
                    help="سقف النداءات المتزامنة كلها (الحصّة مشتركة مع وكلاء آخرين)")
    ap.add_argument("--budget", type=int, default=7000, help="حروف لكل نداء مراجعة")
    ap.add_argument("--max-items", type=int, default=12)
    ap.add_argument("--reviewer-a", default=REVIEWER_A)
    ap.add_argument("--reviewer-b", default=REVIEWER_B)
    ap.add_argument("--no-fix", action="store_true")
    ap.add_argument("--cache-only", action="store_true",
                    help="احكم بالمراجعات المخزَّنة فقط (لا نداء مراجعة جديد) — لما بعد سقف الحساب")
    ap.add_argument("--coverage-proof", type=Path,
                    help="run --cache-only: validate actual mixed-size raw judgments without synthetic cache entries")
    ap.add_argument("--apply-arabic", action="store_true",
                    help="اكتب إصلاحات المصدر العربي (بعد فحصها في تقرير سابق)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", help="تاريخ الختم (افتراضيًّا اليوم)")
    ap.add_argument("--reason", default="")
    ap.add_argument("--with-source", action="store_true",
                    help="unpublish: اسحب المصدر العربي أيضًا (وحدات المعرفة المختلَقة فقط)")
    ap.add_argument("--report", type=Path)
    ap.add_argument("--staged", action="store_true",
                    help="check: فقط الوحدات التي يمسّ الـcommit ترجمتها أو مصدرها (pre-commit)")
    ap.add_argument("--exclude", type=Path,
                    help="ملف مفاتيح (سطر لكل مفتاح) لا تُلمس — يملكها فرع آخر الآن")
    ap.add_argument("--proposals", type=Path, help="apply-arabic: قائمة الإصلاحات المفحوصة")
    ap.add_argument("--reviewer", default=MANUAL_REVIEWER, help="stamp-reviewed: اسم المراجع")
    ap.add_argument("--notes", type=Path, help="stamp-reviewed: {key: [ملاحظات منخفضة]}")
    ap.add_argument("--category", default="awaiting-review", choices=sorted(QUEUE_CATEGORIES),
                    help="queue: نوع الانتظار")
    ap.add_argument("--author", action="append", default=[],
                    help="queue: كاتبٌ للإنجليزي لم يُسجَّل في ملفه (يتكرّر)")
    ap.add_argument("--by", help="sign: اسم الإنسان الذي قرأ النصّين")
    args = ap.parse_args(argv)
    if args.coverage_proof and (args.command != "run" or not args.cache_only or args.rounds != 1):
        ap.error("--coverage-proof requires run --cache-only --rounds 1")

    kinds = sorted(COLLECTORS) if (args.all or not args.kind) else args.kind
    if args.command == "check":
        return cmd_check(kinds, args.staged)
    if args.command == "inventory":
        cmd_inventory(kinds)
        return 0
    if args.command == "apply-arabic":
        if not args.proposals:
            sys.exit("❌ --proposals مطلوب")
        return cmd_apply_arabic(args.proposals)

    wanted: set[str] = set()
    if args.only:
        raw = (Path(args.only[1:]).read_text(encoding="utf-8").splitlines()
               if args.only.startswith("@") else args.only.split(","))
        wanted = {k.strip() for k in raw if k.strip() and not k.strip().startswith("#")}
    if args.command == "unqueue":
        if not wanted:
            sys.exit("❌ --only مطلوب")
        return cmd_unqueue(sorted(wanted))
    items = collect(kinds)
    if args.only:
        items = [it for it in items if it.key in wanted]
    if args.exclude:
        skip = {ln.strip() for ln in args.exclude.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")}
        items = [it for it in items if it.key not in skip]
    if args.unstamped:
        items = [it for it in items if check_item(it) or not read_stamp(it)[0]]
    if args.limit:
        items = items[:args.limit]
    if args.command == "unpublish":
        cmd_unpublish(items, args.reason, args.with_source)
        return 0
    if args.command == "stamp-reviewed":
        if not args.only:
            sys.exit("❌ --only مطلوب: يُختم ما رُوجع فعلًا، واحدًا واحدًا")
        return cmd_stamp_reviewed(items, args.reviewer, args.notes)
    if args.command in ("queue", "sign"):
        if not args.only:
            sys.exit("❌ --only مطلوب")
        missing = wanted - {it.key for it in items}
        if missing:
            sys.exit(f"❌ not found: {', '.join(sorted(missing)[:5])}")
        if args.command == "sign":
            return cmd_sign(items, args.by)
        return cmd_queue(items, args.reason, args.category, args.author)

    set_concurrency(args.max_concurrent)
    global REQUEST_TIMEOUT, REQUEST_ATTEMPTS
    REQUEST_TIMEOUT = args.request_timeout
    REQUEST_ATTEMPTS = args.request_attempts
    global CACHE_ONLY
    CACHE_ONLY = args.cache_only
    if CACHE_ONLY:
        args.no_fix = True
    t0 = time.time()
    report = run(items, args)
    print("\n" + "═" * 62)
    print(f"  مختوم       : {len(report['stamped'])} / {len(items)}")
    print(f"  أُصلح إنجليزيه: {len(report['fixed'])}")
    print(f"  اقتراحات للعربي: {len(report['arabic_proposals'])}"
          f" (طُبّق: {len(report['arabic_applied'])})")
    print(f"  لم يُحسم    : {len(report['unresolved'])}")
    print(f"  الزمن       : {time.time() - t0:.0f} ث")
    print("═" * 62)
    for key, ds in list(report["unresolved"].items())[:30]:
        print(f"  ✗ {key}")
        for d in ds[:4]:
            print(f"      [{d.get('severity', '?')}/{d.get('type', '?')}/{d.get('side', '?')}] "
                  f"{d.get('field', '?')} ({d.get('model', d.get('source', ''))}): "
                  f"{str(d.get('why', ''))[:160]}")
    if args.report:
        _dump_report(args.report, report)
        print(f"\n📄 {args.report}")
    return 3 if report.get("capped") else 0


if __name__ == "__main__":
    sys.exit(main())
