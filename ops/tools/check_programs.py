#!/usr/bin/env python3
"""
فحص: برامج الأسرة (رمضان · رحلة الصلاة · المراحل) سليمة المراجع ومتطابقة اللغتين
==========================================================================

    python3 ops/tools/check_programs.py

المخطّطات في `knowledge_base/curriculum/schema/program_*.schema.json` تفرض الشكل،
ويفحصها `check_curriculum_schema.py`. هذا الفحص يسأل ما لا يستطيع المخطّط أن يسأله:

1. **هل يشير كل مرجع إلى شيء موجود؟** وحدة معرفة، قصة (بالعربية والإنجليزية معًا —
   خمس قصص من تسع عشرة لا ترجمة لها، وإحالة الإنجليزي إليها تفتح له قصة عربية)،
   درس، مسار، آية في حدود سورتها، حديث مرفق في الملف نفسه.
2. **هل الملف الإنجليزي هو الملف العربي نفسه بلغة أخرى؟** كل معرّف ورقم ومرجع
   متطابق؛ النصوص وحدها تختلف، والعربي فيه عربية والإنجليزي بلا حرف عربي. ملفّان
   يتباعدان بنية = مستخدم إنجليزي يرى يومًا بلا تحدٍّ أو سلّم صيام بدرجات مختلفة.
3. **هل النص الحرّ نظيف من النصوص المقدّسة؟** الآيات والأحاديث لها مواضع مُهيكلة
   تُفحَص (المراجع سورة:آية، وبطاقات الأحاديث يفحصها check_hadith_citations).
   أمّا النص الحرّ فلا يُقتبس فيه قرآن (يُقارَن بكل آيات المصحف بالهيكل الصامت،
   خمس كلمات متتالية)، ولا يُقتبس فيه حديث مرفق خارج بطاقته، ولا «قال النبي»
   ولا «رواه»، ولا تُذكر النبي ﷺ في عنصر لا يحمل حديثًا مرفقًا — لأن ذكره بلا
   سند هو بالضبط الطريق الذي دخلت منه ٢٢٣ رواية مختلَقة إلى الإشعارات.
4. **هل القيود التي يقوم عليها البرنامج محترمة؟** لا إمساك تحت السابعة، ولا يوم
   صيام كامل لـ7-9، وتحدٍّ لا يتجاوز ربع ساعة، ومكافآت تتناقص لا تتزايد، وحدود
   أجزاء الختمة على علامة ۞ في المصحف المتحقَّق منه، ومراحل البلوغ للجنسين معًا.
5. **العامية:** النص فصحى سهلة (قرار خالد ٢٠٢٦-٠٨-١٦). قائمة كلمات بحدود الكلمة
   لا بالـsubstring — فلتر ساذج كان يعطي «١٧ من ١٠٤١» والحقيقة ٧٠.

Exit: 0 سليم · 1 مخالفات · 2 تعطّل الفحص نفسه (self-tests)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_hadith_citations import skeleton  # noqa: E402  — تطبيع واحد للنصوص المقدّسة

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = ROOT / "knowledge_base" / "curriculum"
PROGRAMS = CURRICULUM / "programs"
PROGRAMS_EN = CURRICULUM / "i18n" / "en" / "programs"
UNITS = ROOT / "knowledge_base" / "units"
STORIES = (ROOT / "mobile/assets/data/stories.json", ROOT / "mobile/assets/data/stories_en.json")
QURAN = ROOT / "mobile/assets/data/quran.json"

PROGRAM_FILES = {
    "ramadan_family": "ramadan_family.json",
    "prayer_journey": "prayer_journey.json",
    "milestones": "milestones.json",
}

APP_BANDS = ("prenatal-1", "0-3", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18")
RAMADAN_BANDS = ("0-3", "4-6", "7-9", "10-12", "13-15")
ODD_NIGHT_EVENINGS = (20, 22, 24, 26, 28)     # ليالي ٢١، ٢٣، ٢٥، ٢٧، ٢٩
LAST_TEN_EVENINGS = range(20, 29)              # ليالي ٢١..٢٩ (ليلة ٣٠ لا تُعرف مسبقًا)
FAMILY_WORD_DAY = 28
PARENT_READ_BANDS = {"0-3", "4-6"}

# بداية كل جزء (سورة، آية) — مصحف المدينة، وهي نفسها جدول Juz في بيانات tanzil.
# لا تُصدَّق لأنها مكتوبة هنا: `_juz_table_ok` يتحقّق أن كل بداية ليست أول سورة
# تبدأ بعلامة ۞ في quran.json (المصحف الذي يعرضه التطبيق ويفحصه حارس الآيات).
JUZ_STARTS = (
    (1, 1), (2, 142), (2, 253), (3, 93), (4, 24), (4, 148), (5, 82), (6, 111),
    (7, 88), (8, 41), (9, 93), (11, 6), (12, 53), (15, 1), (17, 1), (18, 75),
    (21, 1), (23, 1), (25, 21), (27, 56), (29, 46), (33, 31), (36, 28), (39, 32),
    (41, 47), (46, 1), (51, 31), (58, 1), (67, 1), (78, 1),
)

# مفاتيح قيمها معرّفات/تعدادات لا نصّ: تتطابق حرفيًا بين العربي والإنجليزي.
# كل ما سواها نصّ يُترجَم. مفتاح تعدادي جديد لم يُضَف هنا يفشل فحص «العربي فيه
# عربية» — فلا يمرّ معرّف إنجليزي في الملف العربي على أنه ترجمة.
INVARIANT_KEYS = {
    "program_type", "id", "version", "key", "kind", "text_ar", "source", "book",
    "phase", "when", "cost", "until", "fasts", "addressed_to", "story_id", "track",
    "type", "season", "band_fallback", "gender", "if_gender_unknown", "show_on",
    "requires_feature",
    "drafter_model", "reviewer_model", "translator_model", "reviewed_at",
    "approved_by", "journey_milestone_key",
}
# مفاتيح ثابتة تُعرَف بنمطها لا باسمها: تقدير بداية رمضان لكل سنة هجرية
# (expected_start_1448، expected_start_1449، …) — تاريخ لا نصّ، فيتطابق بين اللغتين.
# بالاسم وحده كانت كل سنة جديدة تحتاج سطرًا هنا وإلا فشل «العربي فيه عربية».
INVARIANT_KEY_PATTERNS = (re.compile(r"^expected_start_\d{4}$"),)


def invariant(key) -> bool:
    return key in INVARIANT_KEYS or (
        isinstance(key, str) and any(p.match(key) for p in INVARIANT_KEY_PATTERNS))
INVARIANT_LIST_KEYS = {
    "unit_ids", "evidence_ids", "lesson_ids", "path_ids", "story_ids", "program_ids",
    "features", "tracks", "covered", "journey_milestone_keys",
}
# مفاتيح شجرتها كلها معرّفات (قيمها فئات أو مسارات لا نصوص).
INVARIANT_TREE_KEYS = {"band_map"}
EN_ONLY_KEYS = {"meaning"}          # ترجمة معنى الحديث — في الإنجليزي وحده
PLACEHOLDER = re.compile(r"\{(\w+)\}")
LANG_KEY = "language"

ARABIC = re.compile(r"[؀-ۿ]")
FOREIGN_SCRIPT = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

# اقتباس أو إسناد في النص الحرّ. النصوص المقدّسة مكانها البطاقات والمراجع.
ATTRIBUTION = re.compile(
    r"(?:قال|يقول|قوله)\s+(?:النبي|رسول\s+الله|ﷺ|تعالى|الله\s+تعالى|الله\s+عز)"
    r"|\bرواه\b|\bأخرجه\b|\bمتفق\s+عليه\b|﴿|﴾"
    r"|\b(?:narrated|reported|recorded)\s+by\b"
    r"|\bthe\s+Prophet\s*(?:ﷺ\s*)?(?:\([^)]*\)\s*)?(?:said|says)\b"
    r"|\bAllah\s+(?:says|said)\b|\bthe\s+Qur'?an\s+says\b",
    re.IGNORECASE)
PROPHET = re.compile(
    r"النبي|رسول\s+الله|ﷺ|صلى\s+الله\s+عليه\s+وسلم|\bthe\s+Prophet\b|\bMessenger\s+of\s+Allah\b",
    re.IGNORECASE)
# أقوال شائعة لا تثبت. «أوله رحمة وأوسطه مغفرة وآخره عتق من النار» ضعيف، وتعيين
# ليلة بعينها بأنها ليلة القدر قطعٌ لا دليل عليه.
WEAK = re.compile(
    r"عتق\s+من\s+النار|عتقاء|أوله\s+رحمة|عشر\s+الرحمة|عشر\s+المغفرة|عشر\s+العتق"
    r"|(?:هي|هذه)\s+ليلة\s+القدر|الليلة\s+ليلة\s+القدر"
    r"|ten\s+(?:days\s+)?of\s+(?:mercy|forgiveness)|freedom\s+from\s+the\s+fire"
    r"|tonight\s+is\s+laylat",
    re.IGNORECASE)

# العامية — بحدود الكلمة. «فيه» و«بكرة» و«خلاص» و«قوي» و«حاجة» فصيحة أيضًا فليست هنا.
DIALECT = {
    "مش", "مافيش", "مفيش", "عشان", "علشان", "دلوقتي", "دلوقت", "إزاي", "ازاي",
    "ليه", "ده", "دي", "كده", "كدا", "إيه", "ايه", "اللي", "بتاع", "بتاعة", "بتاعك",
    "عايز", "عايزة", "عاوز", "عاوزة", "النهارده", "النهاردة", "كمان", "يلا", "يالا",
    "شوية", "لسه", "لسة", "العيلة", "عيلة", "عيلتنا", "هنعمل", "هيعمل", "بيقول",
    "بتقول", "امبارح", "إمبارح", "برضه", "برضو", "أوي", "اوي", "بقى", "ماما", "بابا",
}
_WORD = re.compile(r"[ء-يٱ]+")
_PREFIXES = ("و", "ف")


def dialect_words(text: str) -> list[str]:
    found = []
    for raw in _WORD.findall(re.sub(r"[ً-ْٰ]", "", text)):
        w = raw
        if w not in DIALECT and len(w) > 2 and w[0] in _PREFIXES and w[1:] in DIALECT:
            w = w[1:]
        if w in DIALECT:
            found.append(raw)
    return found


# ── المصادر ────────────────────────────────────────────────────────────────

def _load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def load_sources() -> dict:
    unit_ids, hadith_units = set(), set()
    for f in UNITS.glob("*.json"):
        if f.name.endswith("__en.json"):
            continue
        unit_ids.add(f.stem)
        try:
            u = _load_json(f)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(u, dict):
            continue
        if u.get("id"):
            unit_ids.add(u["id"])
        if u.get("reference_type") == "حديث":
            hadith_units.update({f.stem, u.get("id")})
    stories = [{s["id"] for s in _load_json(p)} for p in STORIES]
    lessons = {_load_json(f).get("id") for f in (CURRICULUM / "lessons").glob("*.json")}
    paths = {_load_json(f).get("id") for f in (CURRICULUM / "paths").glob("*.json")}
    quran = {int(k): v for k, v in _load_json(QURAN).items()}
    return {
        "units": unit_ids,
        "hadith_units": frozenset(hadith_units - {None}),
        "stories_ar": stories[0],
        "stories_en": stories[1],
        "lessons": lessons,
        "paths": paths,
        "quran": quran,
        "ayah_counts": {s: len(v) for s, v in quran.items()},
        "quran_shingles": quran_shingles(quran),
    }


def quran_shingles(quran: dict, n: int = 5) -> set[str]:
    out = set()
    for verses in quran.values():
        for v in verses:
            words = skeleton(v["text"]).split()
            for i in range(len(words) - n + 1):
                out.add(" ".join(words[i:i + n]))
    return out


def quotes_quran(text: str, shingles: set[str], n: int = 5) -> str | None:
    words = skeleton(text).split()
    for i in range(len(words) - n + 1):
        sh = " ".join(words[i:i + n])
        if sh in shingles:
            return sh
    return None


def quotes_evidence(text: str, evidence_skeletons: list[str]) -> bool:
    """Is an attached hadith copied into free text?

    Long skeletons match as substrings. Short ones (e.g. «الحياء من الإيمان»,
    ten characters of skeleton) match only as whole words: a reviewer caught
    that very sentence in a card after a 12-character floor had let it
    through, and a bare substring at that length would also fire on ordinary
    prose.
    """
    sk = skeleton(text)
    padded = f" {sk} "
    for h in evidence_skeletons:
        if len(h) >= 12 and h in sk:
            return True
        if 8 <= len(h) < 12 and f" {h} " in padded:
            return True
    return False


def juz_table_problems(quran: dict) -> list[str]:
    out = []
    prev = (0, 0)
    for i, (s, a) in enumerate(JUZ_STARTS, 1):
        if (s, a) <= prev:
            out.append(f"juz {i}: غير متزايد")
        prev = (s, a)
        verses = {v["verse"]: v["text"] for v in quran.get(s, [])}
        if a not in verses:
            out.append(f"juz {i}: {s}:{a} ليست في المصحف")
        elif a != 1 and not verses[a].startswith("۞"):
            out.append(f"juz {i}: {s}:{a} لا تبدأ بعلامة ۞")
    return out


# ── التجوال ───────────────────────────────────────────────────────────────

def walk_text(node, path="", key=None, scoped=False, hadith_units=frozenset()):
    """(path, key, text, prophet_ok) لكل نصّ قابل للترجمة.

    prophet_ok: العنصر (أو أحد آبائه) يحمل سندًا — حديثًا مرفقًا من الصحيحين في
    evidence_ids، أو وحدة معرفة نوع مرجعها «حديث» تحمل التخريج. الثانية لما ليس في
    الصحيحين (مثل «مروهم بالصلاة لسبع»): يُوصَف ولا يُقتبس، والسند في الوحدة.
    """
    if isinstance(node, dict):
        if node.get("kind") == "hadith":
            # بطاقة الحديث نفسها: context يذكر النبي ﷺ بحقّ، والحديث مفحوص في حارسه.
            for k in ("context", "meaning"):
                if isinstance(node.get(k), str):
                    yield f"{path}/{k}", k, node[k], True
            return
        here = (scoped or bool(node.get("evidence_ids"))
                or any(u in hadith_units for u in node.get("unit_ids") or ()))
        for k, v in node.items():
            if k in INVARIANT_TREE_KEYS:
                continue
            yield from walk_text(v, f"{path}/{k}", k, here, hadith_units)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_text(v, f"{path}[{i}]", key, scoped, hadith_units)
    elif isinstance(node, str):
        if invariant(key) or key in INVARIANT_LIST_KEYS or key == LANG_KEY:
            return
        yield path, key, node, scoped


def parity(ar, en, path="", key=None) -> list[str]:
    out = []
    if isinstance(ar, dict) and isinstance(en, dict):
        extra = set(en) - set(ar) - EN_ONLY_KEYS
        missing = set(ar) - set(en)
        if extra or missing:
            out.append(f"{path}: مفاتيح مختلفة (ناقص بالإنجليزي {sorted(missing)} · زائد {sorted(extra)})")
        if ar.get("kind") == "hadith" and not en.get("meaning"):
            out.append(f"{path}: حديث بلا meaning في الإنجليزي")
        for k in set(ar) & set(en):
            if k in INVARIANT_TREE_KEYS:
                if ar[k] != en[k]:
                    out.append(f"{path}/{k}: يجب أن يتطابق حرفيًا بين اللغتين")
                continue
            out += parity(ar[k], en[k], f"{path}/{k}", k)
    elif isinstance(ar, list) and isinstance(en, list):
        if len(ar) != len(en):
            out.append(f"{path}: طول القائمة {len(ar)} بالعربي و{len(en)} بالإنجليزي")
        for i, (a, e) in enumerate(zip(ar, en)):
            out += parity(a, e, f"{path}[{i}]", key)
    elif isinstance(ar, str) and isinstance(en, str):
        if key == LANG_KEY:
            if (ar, en) != ("ar", "en"):
                out.append(f"{path}: language يجب أن يكون ar/en")
        elif invariant(key) or key in INVARIANT_LIST_KEYS:
            if ar != en:
                out.append(f"{path}: «{key}» يجب أن يتطابق ({ar!r} ≠ {en!r})")
        else:
            if not ARABIC.search(ar):
                out.append(f"{path}: نصّ عربي بلا حروف عربية: {ar[:40]!r}")
            if ARABIC.search(en):
                out.append(f"{path}: حروف عربية في الإنجليزي: {en[:60]!r}")
            if set(PLACEHOLDER.findall(ar)) != set(PLACEHOLDER.findall(en)):
                out.append(f"{path}: حقول القالب تختلف بين اللغتين")
    elif ar != en:
        out.append(f"{path}: قيمة غير نصّية تختلف ({ar!r} ≠ {en!r})")
    return out


def hygiene(doc: dict, lang: str, evidence_skeletons: list[str], src: dict) -> list[str]:
    out = []
    shingles = src["quran_shingles"]
    for path, key, text, prophet_ok in walk_text(doc, hadith_units=src["hadith_units"]):
        if key in EN_ONLY_KEYS or key == "context":
            if FOREIGN_SCRIPT.search(text):
                out.append(f"{path}: حروف أجنبية (CJK/سيريلية)")
            continue
        if FOREIGN_SCRIPT.search(text):
            out.append(f"{path}: حروف أجنبية (CJK/سيريلية)")
        if EMOJI.search(text):
            out.append(f"{path}: رمز تعبيري")
        if (m := ATTRIBUTION.search(text)):
            out.append(f"{path}: اقتباس/إسناد في نصّ حرّ «{m.group(0)}» — النصوص المقدّسة مكانها البطاقات")
        if (m := WEAK.search(text)):
            out.append(f"{path}: قول لا يثبت «{m.group(0)}»")
        if PROPHET.search(text) and not prophet_ok:
            out.append(f"{path}: ذِكر للنبي ﷺ في عنصر بلا حديث مرفق (evidence_ids)")
        if lang == "ar":
            if (d := dialect_words(text)):
                out.append(f"{path}: عامية {sorted(set(d))}")
            if (q := quotes_quran(text, shingles)):
                out.append(f"{path}: نصّ قرآني في نصّ حرّ ({q}) — الآيات مراجع فقط")
            if quotes_evidence(text, evidence_skeletons):
                out.append(f"{path}: الحديث المرفق مقتبس خارج بطاقته")
    return out


# ── المراجع ───────────────────────────────────────────────────────────────

def _collect(node, key: str):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from _collect(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from _collect(v, key)


def _quran_ranges(node, path=""):
    if isinstance(node, dict):
        if {"surah", "from", "to"} <= set(node):
            yield path, node
            return
        for k, v in node.items():
            yield from _quran_ranges(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _quran_ranges(v, f"{path}[{i}]")


def references(doc: dict, src: dict) -> list[str]:
    out = []
    ev_ids = [e["id"] for e in doc.get("evidence", [])]
    if len(ev_ids) != len(set(ev_ids)):
        out.append("evidence: معرّف مكرّر")
    used = set()
    for ids in _collect(doc, "evidence_ids"):
        for i in ids:
            used.add(i)
            if i not in ev_ids:
                out.append(f"evidence_ids: «{i}» غير موجود في evidence")
    for i in set(ev_ids) - used:
        out.append(f"evidence: «{i}» لا يشير إليه شيء — بطاقة يتيمة")
    for ids in _collect(doc, "unit_ids"):
        for u in ids:
            if u not in src["units"]:
                out.append(f"unit_ids: «{u}» ليست وحدة في knowledge_base/units")
    stories = list(_collect(doc, "story_id")) + [s for ids in _collect(doc, "story_ids") for s in ids]
    for s in stories:
        if s is None:
            continue
        if s not in src["stories_ar"]:
            out.append(f"story: «{s}» ليست في stories.json")
        elif s not in src["stories_en"]:
            out.append(f"story: «{s}» بلا ترجمة في stories_en.json — المستخدم الإنجليزي سيفتح قصة عربية")
    for ids in _collect(doc, "lesson_ids"):
        for lid in ids:
            if lid not in src["lessons"]:
                out.append(f"lesson_ids: «{lid}» غير موجود")
    for ids in _collect(doc, "path_ids"):
        for pid in ids:
            if pid not in src["paths"]:
                out.append(f"path_ids: «{pid}» غير موجود")
    for ids in _collect(doc, "program_ids"):
        for pid in ids:
            if pid not in PROGRAM_FILES:
                out.append(f"program_ids: «{pid}» غير موجود")
    for path, r in _quran_ranges(doc):
        n = src["ayah_counts"].get(r["surah"])
        if n is None:
            out.append(f"{path}: سورة {r['surah']} غير موجودة")
        elif not (1 <= r["from"] <= r["to"] <= n):
            out.append(f"{path}: {r['surah']}:{r['from']}-{r['to']} خارج حدود السورة (١..{n})")
    return out


# ── قيود كل برنامج ─────────────────────────────────────────────────────────

def _band_map(bands: dict, allowed: set, where: str) -> list[str]:
    out = []
    bm = bands.get("band_map", {})
    if set(bm) != set(APP_BANDS):
        out.append(f"{where}: band_map يجب أن يغطي الفئات الثماني بالضبط")
    for b, v in bm.items():
        if v not in allowed:
            out.append(f"{where}: band_map[{b}] = {v!r} غير مسموح")
    return out


def season_problems(season: dict) -> list[str]:
    """Each year's estimated start is one Hijri year (354–355 days) after the
    one before — a typo here would silently move a whole Ramadan."""
    out = []
    starts = []
    for k, v in season.items():
        m = re.match(r"^expected_start_(\d{4})$", k)
        if not m:
            continue
        try:
            starts.append((int(m.group(1)), date.fromisoformat(v)))
        except (TypeError, ValueError):
            out.append(f"season.{k}: ليس تاريخًا YYYY-MM-DD")
    starts.sort()
    for (y1, d1), (y2, d2) in zip(starts, starts[1:]):
        if y2 != y1 + 1 or not 352 <= (d2 - d1).days <= 357:
            out.append(f"season: expected_start_{y2} بعد expected_start_{y1} بـ{(d2 - d1).days} "
                       "يومًا — السنة الهجرية ٣٥٤–٣٥٥ يومًا، والسنوات متتالية")
    return out


def ramadan_rules(doc: dict) -> list[str]:
    out = season_problems(doc.get("season") or {})
    days = doc.get("days", [])
    if [d.get("day") for d in days] != list(range(1, 31)):
        out.append("days: يجب أن تكون ١..٣٠ مرتبة بلا تكرار")
    keys = [d.get("key") for d in days]
    if len(keys) != len(set(keys)):
        out.append("days: key مكرّر")
    metrics = {m["key"]: m for m in doc["recap"]["metrics"]}
    sources = {m["source"] for m in metrics.values()}
    for d in days:
        n = d["day"]
        w = f"day {n}"
        phase = "first_ten" if n <= 10 else ("middle_ten" if n <= 20 else "last_ten")
        if d["phase"] != phase:
            out.append(f"{w}: phase يجب أن يكون {phase}")
        if d["last_ten"] != (n > 20):
            out.append(f"{w}: last_ten خطأ")
        # الليلة في الحساب الهجري تسبق نهارها: ليلة ٢١ هي مساء اليوم ٢٠. فنشاط
        # «الليلة الوترية» يقع في أمسيات الأيام ٢٠، ٢٢، ٢٤، ٢٦، ٢٨ — وضعه في أمسية
        # اليوم ٢١ يجعله ليلة ٢٢ وهي شفع.
        if d["odd_night"] != (n in ODD_NIGHT_EVENINGS):
            out.append(f"{w}: odd_night خطأ — أمسيات الليالي الوترية هي الأيام {ODD_NIGHT_EVENINGS}")
        if d["may_not_occur"] != (n == 30):
            out.append(f"{w}: may_not_occur لليوم ٣٠ وحده")
        if d["quran"]["parent_juz"] != n:
            out.append(f"{w}: parent_juz يجب أن يساوي رقم اليوم")
        if d["quran"]["together"] is None:
            out.append(f"{w}: لا ورد عائلي")
        for b, v in d["variants"].items():
            want = "parent" if b in PARENT_READ_BANDS else "child"
            if v["addressed_to"] != want:
                out.append(f"{w}: variants[{b}] موجّه إلى {v['addressed_to']} والصواب {want}")
        tracks = set(d["tracks"])
        if not tracks <= sources:
            out.append(f"{w}: tracks {sorted(tracks - sources)} لا يقابلها مقياس في البطاقة")
        if ("story_heard" in tracks) != bool(d["story_id"]):
            out.append(f"{w}: story_heard يتبع وجود story_id")
        if "night_joined" in tracks and n not in LAST_TEN_EVENINGS:
            out.append(f"{w}: night_joined لأمسيات ليالي العشر (الأيام ٢٠–٢٨) وحدها؛ "
                       "مساء ٢٩ قد يكون ليلة العيد")
        if ("family_word" in tracks) != (n == FAMILY_WORD_DAY):
            out.append(f"{w}: family_word يُختار في اليوم {FAMILY_WORD_DAY} وحده (اليوم ٣٠ قد لا يأتي)")
    for m in metrics.values():
        if m["source"] == "family_word" and not m.get("choices"):
            out.append("recap: family_word بلا choices")
    # أماكن الحقول في القوالب. مقياس shareable=false (تقدّم الأطفال في الصيام)
    # شأن خاص بالأسرة: يُعرض داخل التطبيق، ولا يدخل البطاقة التي تخرج إلى واتساب.
    shareable = {k for k, m in metrics.items() if m.get("shareable", True)}
    allowed = shareable | {"hijri_year", "app_link"}
    tpl = doc["recap"]["templates"]
    for t in [tpl["headline"], tpl["closing"], tpl["share_text"], *tpl["lines"]]:
        for ph in re.findall(r"\{(\w+)\}", t):
            if ph not in allowed:
                out.append(f"recap: «{{{ph}}}» ليس مقياسًا معرَّفًا قابلًا للمشاركة")
    for k in doc["recap"]["min_to_show"]:
        if k not in shareable:
            out.append(f"recap.min_to_show: «{k}» ليس مقياسًا يظهر في البطاقة")
    # سلّم الصيام
    lad = doc["fasting_ladder"]["bands"]
    for b in ("0-3", "4-6"):
        if lad[b]["fasts"] != "no" or any(s["until"] != "none" or s["approx_hours"] != 0 for s in lad[b]["steps"]):
            out.append(f"fasting_ladder[{b}]: لا إمساك تحت السابعة — until=none وapprox_hours=0")
    if lad["7-9"]["fasts"] != "partial":
        out.append("fasting_ladder[7-9]: fasts يجب أن يكون partial")
    for b, floor in (("7-9", 7), ("10-12", 10), ("13-15", 13)):
        steps = lad[b]["steps"]
        hours = [s["approx_hours"] for s in steps]
        if hours != sorted(hours):
            out.append(f"fasting_ladder[{b}]: الدرجات غير متصاعدة")
        for s in steps:
            if s["min_age_years"] < floor:
                out.append(f"fasting_ladder[{b}].{s['key']}: min_age_years دون {floor}")
            if b == "7-9" and s["until"] == "maghrib":
                out.append(f"fasting_ladder[7-9].{s['key']}: لا يوم كامل في 7-9")
    out += _band_map(doc["bands"], set(RAMADAN_BANDS) | {None}, "bands")
    if set(doc["bands"]["covered"]) != set(RAMADAN_BANDS):
        out.append("bands.covered يجب أن يطابق نسخ الأيام الخمس")
    return out


def prayer_rules(doc: dict) -> list[str]:
    out = []
    stages = doc["stages"]
    if [s["stage"] for s in stages] != list(range(1, len(stages) + 1)):
        out.append("stages: الأرقام يجب أن تكون ١..ن مرتبة")
    week = 1
    for s in stages:
        if s["week_from"] != week or s["week_to"] < s["week_from"]:
            out.append(f"stage {s['stage']}: الأسابيع غير متصلة (يُتوقَّع البدء بالأسبوع {week})")
        week = s["week_to"] + 1
    if week - 1 != doc["age"]["weeks"]:
        out.append(f"stages: تنتهي في الأسبوع {week - 1} والبرنامج {doc['age']['weeks']} أسبوعًا")
    cap = doc["reward_policy"]["daily_cap"]
    prev_max = None
    task_ids = []
    for s in stages + [doc["ownership"]]:
        tasks = s["child_tasks"]
        task_ids += [t["id"] for t in tasks]
        per_day = sum(t["coins"] * -(-t["per_week"] // 7) for t in tasks)
        if per_day > cap:
            out.append(f"{s.get('key')}: عملات اليوم الأقصى {per_day} > سقف التطبيق {cap}")
        mx = max(t["coins"] for t in tasks)
        if prev_max is not None and mx > prev_max:
            out.append(f"{s.get('key')}: المكافأة تزيد ({mx} > {prev_max}) — يجب أن تتناقص حتى تبقى العبادة لا العملة")
        prev_max = mx
    if len(task_ids) != len(set(task_ids)):
        out.append("child_tasks: معرّف مهمة مكرّر")
    if not any(s["journey_milestone_key"] == "first_prayer" for s in stages):
        out.append("stages: لا مرحلة تقترح تسجيل «أول صلاة»")
    if "keeps_prayer" not in doc["graduation"]["journey_milestone_keys"]:
        out.append("graduation: لا تقترح تسجيل «يحافظ على الصلاة»")
    rules = sorted(doc["entry_rules"], key=lambda r: r["min_age_years"])
    for a, b in zip(rules, rules[1:]):
        if b["min_age_years"] != a["max_age_years"] + 1:
            out.append("entry_rules: فجوة أو تداخل بين الأعمار")
    by_age = {age: r["track"] for r in rules for age in range(r["min_age_years"], r["max_age_years"] + 1)}
    for age, want in ((6, "preparation"), (7, "journey"), (10, "journey"), (11, "ownership")):
        if by_age.get(age) != want:
            out.append(f"entry_rules: عمر {age} يجب أن يبدأ بـ{want}")
    out += _band_map(doc["bands"], {"preparation", "journey", "ownership", None}, "bands")
    bm = doc["bands"]["band_map"]
    if (bm.get("4-6"), bm.get("7-9")) != ("preparation", "journey"):
        out.append("bands.band_map: 4-6 ← preparation و7-9 ← journey")
    return out


# «بنوك المحتوى هي التي تقرّر مَن يرى الميزة» — رابط إلى ميزة لا بنك لها في فئة
# الطفل يفتح شاشة فارغة («الميثاق متاح لـ7-9 فقط»). شُحنت ثلاث ميزات وابن ١٣ سنة
# لا يرى واحدة منها؛ فالمدقّق يفرض: كل ميزة مربوطة لها بنك في كل فئة تبلغها المرحلة.
FEATURE_BANKS = {
    "agreement": ("agreements", "clauses_{band}.json"),
    "license": ("license", "scenarios_stranger_{band}.json"),
    "missions": ("missions", "missions_{band}.json"),
}


def band_of_age(years: int) -> str:
    for lo, hi, band in ((0, 3, "0-3"), (4, 6, "4-6"), (7, 9, "7-9"), (10, 12, "10-12"),
                         (13, 15, "13-15"), (16, 18, "16-18")):
        if lo <= years <= hi:
            return band
    return "16-18"


def milestone_bands(trigger: dict) -> set[str]:
    bands = set(trigger.get("band_fallback") or [])
    if trigger["type"] == "age" and trigger.get("age_months") is not None:
        at_alert = trigger["age_months"] - -(-trigger["alert_days_before"] // 30)
        bands.add(band_of_age(at_alert // 12))
    elif trigger["type"] == "season_age":
        for years in range(trigger["min_age_months"] // 12, trigger["max_age_months"] // 12 + 1):
            bands.add(band_of_age(years))
    return bands


REQUIRED_MILESTONES = {
    "school_entry", "tamyeez", "prayer_start", "first_fasting", "age_ten",
    "puberty_girls", "puberty_boys", "first_phone", "teen_identity",
}


def milestone_rules(doc: dict) -> list[str]:
    out = []
    ms = doc["milestones"]
    keys = [m["key"] for m in ms]
    if len(keys) != len(set(keys)):
        out.append("milestones: key مكرّر")
    if len({m["order"] for m in ms}) != len(ms):
        out.append("milestones: order مكرّر")
    if (missing := REQUIRED_MILESTONES - set(keys)):
        out.append(f"milestones: ناقص {sorted(missing)}")
    default = doc["alert_policy"]["default_days_before"]
    for m in ms:
        w = f"milestone {m['key']}"
        t = m["trigger"]
        if t["type"] == "age":
            if t["age_months"] is None:
                out.append(f"{w}: trigger age بلا age_months")
        else:
            if t.get("season") != "ramadan" or "min_age_months" not in t or "max_age_months" not in t:
                out.append(f"{w}: season_age يحتاج season وmin/max_age_months")
            elif t["min_age_months"] >= t["max_age_months"]:
                out.append(f"{w}: min_age_months ≥ max_age_months")
        if t["alert_days_before"] != default:
            out.append(f"{w}: alert_days_before {t['alert_days_before']} ≠ السياسة {default}")
        for feature in m["links"]["features"]:
            if feature in FEATURE_BANKS:
                sub, pattern = FEATURE_BANKS[feature]
                for band in sorted(milestone_bands(t)):
                    if not (CURRICULUM / sub / pattern.format(band=band)).exists():
                        out.append(f"{w}: الميزة «{feature}» لا بنك لها لفئة {band} — "
                                   "الرابط يفتح شاشة فارغة")
        if m["medical"] and not m.get("red_flags"):
            out.append(f"{w}: مرحلة طبية بلا red_flags")
        g = m["audience"]
        if g["gender"] != "any" and g["if_gender_unknown"] != "ask":
            out.append(f"{w}: مرحلة خاصة بجنس يجب ألا تُرسل قبل معرفته (if_gender_unknown=ask)")
    genders = {m["key"]: m["audience"]["gender"] for m in ms}
    if (genders.get("puberty_girls"), genders.get("puberty_boys")) != ("female", "male"):
        out.append("milestones: puberty_girls=female وpuberty_boys=male")
    return out


RULES = {"ramadan_family": ramadan_rules, "prayer_journey": prayer_rules, "milestones": milestone_rules}


def check_pair(name: str, ar: dict, en: dict | None, src: dict) -> list[str]:
    out = []
    ev_sk = [skeleton(e["text_ar"]) for e in ar.get("evidence", [])]
    if ar.get("language") != "ar":
        out.append("language يجب أن يكون ar في الملف العربي")
    out += references(ar, src)
    out += hygiene(ar, "ar", ev_sk, src)
    try:
        out += RULES[name](ar)
    except (KeyError, TypeError) as e:
        out.append(f"البنية لا تسمح بفحص القيود ({e!r}) — شغّل check_curriculum_schema أولًا")
    if en is None:
        out.append("لا ترجمة إنجليزية — كل نصّ يشحن بالعربية والإنجليزية")
    else:
        out += parity(ar, en)
        out += hygiene(en, "en", ev_sk, src)
    return out


# ── self-tests ────────────────────────────────────────────────────────────

def _self_test(src: dict) -> list[str]:
    fails = []
    if dialect_words("أحسنت، هيا نصنع معًا") or dialect_words("مشى الولد إلى المسجد") or dialect_words("فيه خير كثير"):
        fails.append("العامية: إنذار كاذب على فصحى")
    for s in ("مش عارف أعمل إيه", "عشان نلحق الإفطار", "والعيلة كلها"):
        if not dialect_words(s):
            fails.append(f"العامية: فاتت «{s}»")
    for s in ("قال النبي ﷺ: الصيام جنة", "رواه البخاري", "The Prophet ﷺ said that fasting", "﴿ ﴾"):
        if not ATTRIBUTION.search(s):
            fails.append(f"الإسناد: فات «{s}»")
    for s in ("اقرؤوا السورة معًا، ثم ليقل كل واحد ما فهمه", "الخطة المتفق عليها مسبقًا"):
        if ATTRIBUTION.search(s):
            fails.append(f"الإسناد: إنذار كاذب على «{s}»")
    v = src["quran"][2][182]["text"]          # البقرة ١٨٣ — آية الصيام
    if not quotes_quran("ذكّر أولادك: " + v, src["quran_shingles"]):
        fails.append("القرآن: لم يُمسك نصّ آية مُلصق")
    if quotes_quran("نقرأ معًا سورة قصيرة ثم يدعو كل واحد لأهله بالخير والبركة", src["quran_shingles"]):
        fails.append("القرآن: إنذار كاذب على نثر عادي")
    if (p := juz_table_problems(src["quran"])):
        fails.append(f"جدول الأجزاء: {p[:2]}")
    short = [skeleton("الحياء من الإيمان")]
    if not quotes_evidence("والحياء من الإيمان كما في الحديث المرفق؛ فعلّموه", short):
        fails.append("الاقتباس: فات حديث قصير منسوخ في نص حرّ")
    if quotes_evidence("علّموه الحياء باحترام، فهو من خلق المؤمن", short):
        fails.append("الاقتباس: إنذار كاذب على نثر عادي")
    if not WEAK.search("العشر الأواخر عتق من النار"):
        fails.append("الأقوال الضعيفة: فات «عتق من النار»")
    if not FOREIGN_SCRIPT.search("abc\u4e2d") or not FOREIGN_SCRIPT.search("\u041f\u0440\u0438") \
            or FOREIGN_SCRIPT.search("مرحبًا hello ﷺ"):
        fails.append("الحروف الأجنبية: الكاشف لا يمسك CJK/السيريلية أو يُنذر على عربي/لاتيني")
    if band_of_age(6) != "4-6" or band_of_age(7) != "7-9" or band_of_age(12) != "10-12":
        fails.append("حساب الفئة من العمر معطوب")
    if milestone_bands({"type": "age", "age_months": 84, "alert_days_before": 30,
                        "band_fallback": []}) != {"4-6"}:
        fails.append("فئة لحظة الإشعار معطوبة: ابن ٦ سنوات و١١ شهرًا في 4-6")
    if not invariant("expected_start_1449") or invariant("expected_start_soon") \
            or invariant("title"):
        fails.append("المفاتيح الثابتة بالنمط: expected_start_<سنة> لا يُعرَف أو يُعرَف غيره")
    if season_problems({"expected_start_1448": "2027-02-08", "expected_start_1449": "2028-01-28"}) \
            or not season_problems({"expected_start_1448": "2027-02-08",
                                    "expected_start_1449": "2029-01-28"}):
        fails.append("تتابع تقديرات بداية رمضان: الفحص لا يقبل الصحيح أو لا يرفض الخطأ")
    return fails


def main() -> int:
    print("=" * 66)
    print("  PROGRAMS CHECK — برامج الأسرة: مراجع، لغتان، نصوص مقدّسة، قيود")
    print("=" * 66)
    src = load_sources()
    fails = _self_test(src)
    if fails:
        for f in fails:
            print(f"  ⛔ SELF-TEST: {f}")
        print("\n  الفحص لاغٍ — نجاح كاذب على نصّ شرعي أسوأ من غياب الفحص.")
        return 2
    print("  self-tests ✓")

    problems: list[tuple[str, str]] = []
    seen = 0
    for d in (PROGRAMS, PROGRAMS_EN):
        for f in sorted(d.glob("*.json")) if d.exists() else []:
            if f.name not in PROGRAM_FILES.values():
                problems.append((str(f.relative_to(ROOT)), "ملف برنامج غير معروف — لا يفحصه شيء"))
    for name, fname in PROGRAM_FILES.items():
        p_ar, p_en = PROGRAMS / fname, PROGRAMS_EN / fname
        if not p_ar.exists():
            continue
        seen += 1
        try:
            ar = _load_json(p_ar)
            en = _load_json(p_en) if p_en.exists() else None
        except json.JSONDecodeError as e:
            problems.append((fname, f"json: {e}"))
            continue
        if ar.get("program_type") != name:
            problems.append((fname, f"program_type {ar.get('program_type')!r} لا يطابق اسم الملف"))
            continue
        for msg in check_pair(name, ar, en, src):
            problems.append((fname, msg))

    print(f"  برامج مفحوصة: {seen} (عربي + إنجليزي)")
    if problems:
        print(f"\n  ❌ {len(problems)} مخالفة:\n")
        for fname, msg in problems[:40]:
            print(f"     {fname} · {msg}")
        if len(problems) > 40:
            print(f"     … و{len(problems) - 40} غيرها")
        return 1
    print("\n" + "=" * 66)
    print("  ✅ PROGRAMS OK")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
