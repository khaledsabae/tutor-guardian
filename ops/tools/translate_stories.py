#!/usr/bin/env python3
"""
ترجمة قصص الأطفال إلى الإنجليزية — نفس خط الإنتاج بمراجعة عدائية
=================================================================

الاستخدام:
  python3 ops/tools/translate_stories.py                 # الأربع عشرة قصة
  python3 ops/tools/translate_stories.py --only hamza_truth --dry-run
  python3 ops/tools/translate_stories.py --force

يقرأ `docs/stories.json` ويكتب:
  · `docs/stories.en.json`               (النسخة التي يجلبها التطبيق من الشبكة)
  · `mobile/assets/data/stories_en.json` (النسخة المحزومة داخل التطبيق)

**نسختان لا نسخة واحدة، ومتطابقتان بايتًا ببايت** — لأن `storiesProvider`
يجلب من الشبكة بمهلة ٤ ثوانٍ ثم **يسقط صامتًا** إلى الأصل المحزوم. مستخدمٌ
إنجليزي بنسخة شبكية بلا نسخة محزومة يقع على العربية عند أول انقطاع، بلا خطأ
واحد يظهر له. (نفس السبب الذي جعل العربية تعيش في ملفين متطابقين.)

لا نعيد اشتقاق شيء: المترجم والمراجع والمسرد وحرّاسه مستوردة من
`translate_curriculum.py`. نموذجان من عائلتين مختلفتين عمدًا — نموذج يراجع
لنفسه يوافق على نفسه.

⚠️ هذه الأداة تنتج **مسودة للمراجعة الشرعية، لا محتوى جاهزًا للنشر.**
خمس قصص من الأربع عشرة تحمل آيات، وكل قصة تمسّ آية أو حديثًا تخرج بعلامة
`needs_scholar_review`.

🚨 والقرآن لا يُترجَم. الآية تبقى عربية كما هي في المصدر، وما يُكتب
بالإنجليزية مقابلها تفسيرٌ لمعناها يُعلَن أنه تفسير. هذا مفروض ببوابة
برمجية هنا (`_ayah_gate`) لا بتعليمات لنموذج، ومفروض ثانيةً على pre-commit
بـ`check_quran_rendering.py`.

المتطلبات:
  OLLAMA_API_KEY  — مفتاح Ollama Cloud
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# لا نعيد اشتقاق المسرد ولا حرّاسه ولا اختيار النماذج — نستوردها.
from translate_curriculum import (  # noqa: E402
    GLOSSARY,
    QUOTED_ARABIC,
    RELIGIOUS_MARKERS,
    REVIEWER_MODEL,
    SYSTEM_REVIEW,
    TRANSLATOR_MODEL,
    _parse_json,
    _post,
    _validate_glossary,
)
from check_quran_rendering import violations_in  # noqa: E402

SRC = ROOT / "docs" / "stories.json"
OUT_DOCS = ROOT / "docs" / "stories.en.json"
OUT_ASSET = ROOT / "mobile" / "assets" / "data" / "stories_en.json"

# الحقول القابلة للترجمة. ما عداها هوية أو مسار ملف أو لون أو ترتيب —
# ترجمتها تكسر الربط بالصور والفيديو وبأي حالة قراءة محفوظة بالـid.
STORY_FIELDS = ("title", "description")
PAGE_FIELDS = ("text",)

AYAH_SPAN = re.compile(r"﴿[^﴾]*﴾")
LATIN_RUN = re.compile(r"[A-Za-z]{3,}")

# نسبة الآية إلى قائلها. المصدر ينسب صراحةً («قوله تعالى»، «الآية الكريمة»،
# «وصف القرآن»)، والإنجليزية يجب أن تنسب كذلك. هذا ليس تدقيقًا أسلوبيًا:
# التمريرة الأولى أخرجت «Aisha remembered her father's words when they
# memorized together ﴿آية﴾» — فبقيت الآية معلّقة بعد «كلام أبيها» بلا ذكرٍ
# لله ولا للقرآن، أي آية منسوبة ظاهرًا إلى أبٍ.
# وفحص `check_quran_rendering` يمرّ على هذا لأنه يفحص **الشكل**: الآية عربية
# كما هي بين ﴿﴾، ولا إنجليزيةَ مقدَّمةً على أنها قرآن. الخلل في **النسبة** لا
# في الرسم، فيلزمه حارس آخر — هذا.
AYAH_ATTRIBUTION_AR = re.compile(
    r"قوله تعالى|قول الله|قال تعالى|قوله سبحانه|كتاب الله|القرآن|الآية|الآيات")
AYAH_ATTRIBUTION_EN = re.compile(
    r"\ballah\b|\bgod\b|qur['’ʼ]?an|\bayah\b|\bayat\b|\bverse", re.IGNORECASE)

# ملاحظات المراجع تُخزَّن للمراجع البشري ولا تُسقِط الترجمة — إلا هذه.
# خطأ شرعي بدرجة `high` ليس ملاحظة تُؤجَّل: أول تمريرة أنتجت نسبةَ آيةٍ إلى
# كلام أبٍ في `aisha_permission` (سقط «قوله تعالى» فبقيت الآية معلّقة بعد
# «حفظا معًا»). الشكل سليم — الآية عربية كما هي، وفحص القرآن يمرّ — والنسبة
# خاطئة. فحصٌ شكلي لا يمسك هذا، والمراجع العدائي أمسكه، فيُعامَل كرفض.
REJECT_ON = {("high", "religious_error")}

SYSTEM_TRANSLATE = f"""You translate Islamic bedtime stories for children from \
Arabic into English. The reader is a Muslim parent reading aloud to a child \
aged roughly 4 to 10, in English, sharing the same religious frame of reference.

Rules:
1. Register first. This is a story read aloud at bedtime, not a lesson and not \
a report. Short sentences, concrete images, a warm narrating voice. Keep the \
Arabic story's affection — do not flatten it into instructional English, and do \
not add a moral the Arabic does not state.
2. Transliterate these terms rather than translating them; a short gloss in \
parentheses on first use is fine, then use the term alone:
{json.dumps(GLOSSARY, ensure_ascii=False, indent=2)}
   This table is a substitution rule, not a vocabulary to reach for. Apply an \
entry ONLY where that exact Arabic word appears in the source. Never use a \
glossary term for a different Arabic word that seems close: أدعية is du'a, not \
adhkar; نصيحة is advice, not tarbiyah. Substituting a near-neighbour changes a \
religious category, which is a defect, not a stylistic choice.
3. NEVER paraphrase, shorten or soften a hadith. Translate it faithfully and \
keep any attribution exactly as given. If you are unsure of the established \
English rendering of a hadith, translate it literally rather than reaching for a \
familiar-sounding phrase.
4. 🚨 THE QUR'AN IS NOT TRANSLATED. An English rendering of an ayah is *tafsir* \
— interpretation of the meaning — not the Qur'an, and presenting it as the \
Qur'an is a religious error, not a stylistic one. Therefore, wherever the Arabic \
contains Qur'anic text inside ﴿ ﴾:
   · Reproduce the Arabic ayah EXACTLY as it appears, character for character, \
still inside ﴿ ﴾. Do not translate it, do not transliterate it, do not \
re-spell it, do not drop its diacritics.
   · Then, in the surrounding English narration, give the meaning and label it \
explicitly, in this form: interpretation of the meaning: ... — the label is \
mandatory, not optional.
   · Never place English words inside ﴿ ﴾, and never introduce quotation marks \
around English words in a way that presents them as the words of Allah.
   · A sentence that merely NAMES a surah or mentions the Qur'an without quoting \
it is translated normally. This rule is about rendering ayah text.
5. Keep ﷺ and similar honorifics exactly where they appear.
6. Personal names are transliterated, not replaced: يوسف is Yusuf, عائشة is \
Aisha, ياسين is Yaseen, حمزة is Hamza.
7. Preserve the JSON structure exactly: same keys, same number of pages, same \
order, same pageNumber values. Translate only `title`, `description` and each \
page's `text`.

Return JSON only. No prose, no markdown fences, no commentary."""


# ── البوابات البرمجية ────────────────────────────────────────────────────
# رأي النموذج المراجع احتمالي؛ هذه البوابات يقينية، فتسبقه.

def _payload(story: dict) -> dict:
    """ما يُرسَل للترجمة: الحقول النصية فقط، بلا مسارات ولا ألوان ولا id."""
    return {
        **{k: story[k] for k in STORY_FIELDS if story.get(k)},
        "pages": [
            {"pageNumber": p["pageNumber"],
             **{k: p[k] for k in PAGE_FIELDS if p.get(k)}}
            for p in story["pages"]
        ],
    }


def _structural_gate(src: dict, en: dict) -> list[str]:
    """عدد الصفحات وترتيبها وأرقامها — قبل أي حكم على الجودة."""
    problems = []
    for k in STORY_FIELDS:
        if src.get(k) and not str(en.get(k, "")).strip():
            problems.append(f"حقل مفقود أو فارغ: {k}")
    pages = en.get("pages")
    if not isinstance(pages, list):
        problems.append("pages ليست قائمة")
        return problems
    if len(pages) != len(src["pages"]):
        problems.append(
            f"عدد الصفحات مختلف: {len(src['pages'])} → {len(pages)}")
        return problems
    for i, (sp, ep) in enumerate(zip(src["pages"], pages)):
        if not isinstance(ep, dict):
            problems.append(f"الصفحة {i + 1} ليست كائنًا")
            continue
        if ep.get("pageNumber") != sp["pageNumber"]:
            problems.append(
                f"ترتيب مختلف في الموضع {i + 1}: "
                f"{sp['pageNumber']} → {ep.get('pageNumber')}")
        if not str(ep.get("text", "")).strip():
            problems.append(f"نص الصفحة {sp['pageNumber']} فارغ")
        elif not LATIN_RUN.search(str(ep["text"])):
            # نص بلا حرف لاتيني واحد = العربية رجعت كما هي، لا ترجمة.
            problems.append(f"الصفحة {sp['pageNumber']} لم تُترجَم (بلا إنجليزية)")
    return problems


def _ayah_gate(src: dict, merged: dict) -> list[str]:
    """🚨 القرآن لا يُترجَم — بوابة برمجية لا تعليمات لنموذج.

    شرطان:
      ١) كل آية بين ﴿﴾ في العربية موجودة **حرفًا بحرف** في الناتج الإنجليزي.
         نموذج «ترجم كل شيء» يُخرج الآية إنجليزية أو يعيد رسمها بلا تشكيل،
         والحالتان تسقطان هنا لا في المراجعة.
      ٢) ما يمسكه `check_quran_rendering` من أشكال تقديم الإنجليزية على أنها
         قرآن — نفس الفحص الذي يعمل على pre-commit، مُطبَّقًا هنا قبل الكتابة
         حتى لا يصل الملف إلى الكوميت أصلًا.
    """
    problems = []
    src_blob = json.dumps(src, ensure_ascii=False)
    en_blob = json.dumps(merged, ensure_ascii=False)
    for ayah in AYAH_SPAN.findall(src_blob):
        if ayah not in en_blob:
            problems.append(
                f"آية لم تُنقل كما هي (تُرجمت أو أُعيد رسمها): {ayah[:60]}…")
    for kind, field, snippet in violations_in(merged):
        problems.append(f"[{kind}] {field}: {snippet}")

    # ٣) النسبة تُنقل مع الآية. حقلًا بحقل، لا على الوثيقة كلها: «الله» في
    #    صفحة أخرى لا ينسب آيةَ هذه الصفحة إلى أحد.
    pairs = [(src.get(k, ""), merged.get(k, "")) for k in STORY_FIELDS]
    pairs += [(sp.get("text", ""), ep.get("text", ""))
              for sp, ep in zip(src["pages"], merged["pages"])]
    for ar_text, en_text in pairs:
        if (AYAH_SPAN.search(ar_text)
                and AYAH_ATTRIBUTION_AR.search(ar_text)
                and not AYAH_ATTRIBUTION_EN.search(en_text)):
            problems.append(
                "الآية فقدت نسبتها: العربية تنسبها صراحةً ولا ذكر لله ولا "
                f"للقرآن في الإنجليزية — «{en_text[:90]}…»")
    return problems


def _merge(story: dict, en: dict) -> dict:
    """يبني القصة الإنجليزية من الأصل: الترجمة تحلّ محلّ النص فقط.

    نبني من الأصل لا من ناتج النموذج، فلا يستطيع النموذج أن يغيّر id ولا
    coverImage ولا image ولا videoFile ولا themeColor ولا pageNumber حتى لو
    أرجعها مختلفة.
    """
    out = dict(story)
    for k in STORY_FIELDS:
        if en.get(k):
            out[k] = en[k]
    out["pages"] = []
    for sp, ep in zip(story["pages"], en["pages"]):
        page = dict(sp)
        page["text"] = ep["text"]
        out["pages"].append(page)
    return out


def translate_story(story: dict, retries: int = 2) -> dict:
    """يترجم قصة ويراجعها. يرجّع تقريرًا؛ القصة في `story` عند النجاح."""
    sid = story["id"]
    payload = _payload(story)
    src_json = json.dumps(payload, ensure_ascii=False)
    feedback = ""
    last_reason = "لم تُحاوَل"

    for attempt in range(retries + 1):
        user = src_json if not feedback else (
            f"{src_json}\n\nYour previous attempt was REJECTED by an automated "
            f"gate for these reasons. Fix them and return the JSON again:\n"
            f"{feedback}")
        try:
            raw, usage_t = _post(TRANSLATOR_MODEL, SYSTEM_TRANSLATE, user)
            translated = _parse_json(raw)
        except json.JSONDecodeError as e:
            last_reason = f"ناتج غير صالح: {e}"
            feedback = "Return valid JSON only — no prose, no markdown fences."
            continue
        except RuntimeError as e:
            return {"id": sid, "status": "failed", "reason": str(e)}

        problems = _structural_gate(story, translated)
        if problems:
            last_reason = "بنية: " + "; ".join(problems)
            feedback = "; ".join(problems)
            continue

        merged = _merge(story, translated)

        # حقن المصطلحات: مصطلح إنجليزي من المسرد بلا جذر عربي في المصدر.
        glossary_issues = _validate_glossary(payload, translated)
        if glossary_issues:
            last_reason = "حقن مصطلحات: " + "; ".join(glossary_issues)
            feedback = "; ".join(glossary_issues)
            continue

        ayah_issues = _ayah_gate(story, merged)
        if ayah_issues:
            last_reason = "القرآن: " + "; ".join(ayah_issues)
            feedback = (
                "THE QUR'AN IS NOT TRANSLATED. " + "; ".join(ayah_issues)
                + " — reproduce every ﴿…﴾ ayah in Arabic exactly as in the "
                  "source, and label any English meaning as "
                  "'interpretation of the meaning: …'.")
            continue

        # مراجعة عدائية بنموذج من عائلة أخرى، مخزَّنة مع القصة.
        review_input = json.dumps(
            {"arabic": payload, "english": translated}, ensure_ascii=False)
        try:
            raw_r, usage_r = _post(REVIEWER_MODEL, SYSTEM_REVIEW, review_input)
            review = _parse_json(raw_r)
        except (json.JSONDecodeError, RuntimeError):
            review, usage_r = {"verdict": "unreviewed", "defects": []}, {}

        # ونفاد المحاولات هنا يعني **سقوط القصة** لا قبولها بملاحظة: قصة ناقصة
        # من الرف أهون من آية منسوبة إلى غير قائلها في يد طفل.
        blocking = [d for d in review.get("defects", [])
                    if (d.get("severity"), d.get("type")) in REJECT_ON]
        if blocking:
            last_reason = "خطأ شرعي جسيم: " + "; ".join(
                str(d.get("why")) for d in blocking)
            feedback = "; ".join(
                f"{d.get('field')}: {d.get('why')}" for d in blocking)
            continue

        sig_marker = bool(RELIGIOUS_MARKERS.search(src_json))
        sig_quoted = bool(QUOTED_ARABIC.search(src_json))
        sig_ayah = bool(AYAH_SPAN.search(src_json))
        sig_model = bool(review.get("contains_religious_text"))
        needs_scholar = sig_marker or sig_quoted or sig_ayah or sig_model

        merged["language"] = "en"
        merged["source_language"] = "ar"
        merged["translation"] = {
            "translator_model": TRANSLATOR_MODEL,
            "reviewer_model": REVIEWER_MODEL,
            "attempts": attempt + 1,
            "needs_scholar_review": needs_scholar,
            "scholar_signals": {
                "keyword": sig_marker,
                "quoted_arabic": sig_quoted,
                "quran_ayah": sig_ayah,
                "reviewer_model": sig_model,
            },
            "review_verdict": review.get("verdict", "unreviewed"),
            "review_defects": review.get("defects", []),
            "approved_by": None,  # يملؤه مراجع بشري، لا هذه الأداة
        }

        return {
            "id": sid,
            "status": "translated",
            "story": merged,
            "attempts": attempt + 1,
            "needs_scholar_review": needs_scholar,
            "verdict": review.get("verdict", "unreviewed"),
            "defects": review.get("defects", []),
            "tokens_out": (usage_t.get("completion_tokens", 0)
                           + usage_r.get("completion_tokens", 0)),
            "tokens_in": (usage_t.get("prompt_tokens", 0)
                          + usage_r.get("prompt_tokens", 0)),
        }

    return {"id": sid, "status": "failed", "reason": last_reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", help="معرّف قصة (يتكرر)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--force", action="store_true",
                    help="أعد ترجمة القصص الموجودة في الناتج")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    stories = json.loads(SRC.read_text(encoding="utf-8"))
    # الموجود يُقرأ دائمًا، و`--force` يعني «أعد ترجمة المختار» لا «امحُ
    # الباقي». بدون هذا التمييز كان `--only x --force` يكتب ملفًا فيه قصة
    # واحدة ويحذف الثلاث عشرة الأخرى بلا تحذير.
    existing = {}
    if OUT_DOCS.exists():
        existing = {s["id"]: s
                    for s in json.loads(OUT_DOCS.read_text(encoding="utf-8"))}

    selected = [s for s in stories if not args.only or s["id"] in args.only]
    todo = [s for s in selected if args.force or s["id"] not in existing]

    print(f"📖 {len(stories)} قصة · {len(todo)} للترجمة · "
          f"{len(existing)} موجودة")
    print(f"   مترجم : {TRANSLATOR_MODEL}")
    print(f"   مراجع : {REVIEWER_MODEL}\n")

    if args.dry_run:
        for s in todo:
            print(f"  [dry-run] {s['id']}  صفحات={len(s['pages'])}")
        return 0

    def run_one(s):
        """قصة تسقط لا تُسقِط الباقي."""
        try:
            return translate_story(s, args.retries)
        except Exception as e:
            return {"id": s["id"], "status": "failed",
                    "reason": f"{type(e).__name__}: {e}"}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_one, todo))

    ok = [r for r in results if r["status"] == "translated"]
    failed = [r for r in results if r["status"] == "failed"]

    # نكتب بترتيب المصدر لا بترتيب الانتهاء — الترتيب هو ترتيب الرف.
    done = {**existing, **{r["id"]: r["story"] for r in ok}}
    out = [done[s["id"]] for s in stories if s["id"] in done]

    if out:
        blob = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
        OUT_DOCS.write_text(blob, encoding="utf-8")
        OUT_ASSET.parent.mkdir(parents=True, exist_ok=True)
        OUT_ASSET.write_text(blob, encoding="utf-8")

    scholar = [r for r in ok if r.get("needs_scholar_review")]
    defects = [(r["id"], d) for r in ok for d in r.get("defects", [])]
    retried = [r for r in ok if r.get("attempts", 1) > 1]

    print("═" * 62)
    print(f"  مترجَم   : {len(ok)}")
    print(f"  فاشل     : {len(failed)}")
    print(f"  في الملف : {len(out)} من {len(stories)}")
    print(f"  أُعيدت المحاولة عليها: {len(retried)}")
    print(f"  🕌 يحتاج مراجعة شرعية: {len(scholar)} من {len(ok)}")
    print(f"  التوكن   : دخل={sum(r.get('tokens_in', 0) for r in ok):,}"
          f"  خرج={sum(r.get('tokens_out', 0) for r in ok):,}")
    print(f"  الزمن    : {time.time() - t0:.0f} ثانية")
    print("═" * 62)

    for r in failed:
        print(f"  ❌ {r['id']}: {r['reason']}")
    for r in retried:
        print(f"  ↻ {r['id']}: نجحت بعد {r['attempts']} محاولات")

    if defects:
        print(f"\n🔍 المراجع العدائي وجد {len(defects)} ملاحظة:\n")
        for sid, d in defects:
            sev = {"high": "🔴", "medium": "🟡"}.get(d.get("severity"), "⚪")
            print(f"  {sev} [{d.get('type')}] {sid} · {d.get('field')}")
            print(f"      {d.get('why')}")
    else:
        print("\n🔍 المراجع العدائي: صفر ملاحظات — تعامل معها بريبة، "
              "لا كشهادة جودة.")

    if scholar:
        print(f"\n🕌 {len(scholar)} قصة تمسّ آية أو حديثًا ولا تُنشر بلا توقيع "
              "بشري متخصص:")
        for r in scholar:
            print(f"      {r['id']}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
