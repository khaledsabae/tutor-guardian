#!/usr/bin/env python3
"""
ترجمة المنهج إلى الإنجليزية — خط إنتاج بمراجعة عدائية
======================================================

الاستخدام:
  python3 ops/tools/translate_curriculum.py --path path_4-6_islamic_parenting_bond
  python3 ops/tools/translate_curriculum.py --path <id> --dry-run
  python3 ops/tools/translate_curriculum.py --all --limit 20

يكتب في `knowledge_base/curriculum/i18n/en/` — **لا يعدّل ملفًا عربيًا أبدًا**.

المتطلبات:
  OLLAMA_API_KEY  — مفتاح Ollama Cloud

لماذا نموذجان لا نموذج واحد
---------------------------
المترجم يراجَع بنموذج **مختلف** مُوجَّه للطعن لا للموافقة. نموذج يصحّح
لنفسه يوافق على نفسه؛ وهذا وقع فعلًا في هذا المستودع من قبل (سجل العمليات
2026-08-11: وكيل قال «١٠٨/١٠٨ نضيفة» وفحص مستقل وجد ١٣ عيبًا).

ولماذا mistral-large-3 للترجمة
------------------------------
قياس فعلي على درس واحد: mistral-large-3 أنهاه في ١٨٠ توكن خرج، و
qwen3.5:397b أنهاه بنفس الجودة في ٥,٨٦٩ — لأنه نموذج تفكير يحرق التوكن في
التأمل قبل الإجابة. الفرق ٣٢ ضعفًا على ناتج واحد؛ على ١,٦٣٦ ملفًا هو الفرق
بين مشروع ممكن ومشروع بلا داعٍ.

⚠️ هذه الأداة تنتج **مسودة للمراجعة الشرعية، لا محتوى جاهزًا للنشر.**
كل ملف يلمس حديثًا أو آية يخرج بعلامة `needs_scholar_review`، ولا يُنشر
قبل توقيع بشري متخصص. «بدت صحيحة» ليست معيارًا في محتوى شرعي.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM = ROOT / "knowledge_base" / "curriculum"

# 🚨 الترجمات تعيش في شجرة منفصلة، لا بجانب الأصل.
# curriculum_loader يحمّل بـ`LESSONS_DIR.glob("*.json")` ويفهرس بـ`id`،
# والترجمة تحمل نفس الـid. فملف `<id>.en.json` بجانب `<id>.json` يدخل
# نفس الحلقة ويتنازع على نفس المفتاح. جرّبتُه: العربي نجا — **لأن
# `.en.json` يسبق `.json` أبجديًا فيُكتب فوقه**، لا لأن أحدًا صمّم ذلك.
# صحّة بالمصادفة: يكفي أن يسمّي أحدهم ملفًا `.ar.json` أو يتغيّر الترتيب
# ليحلّ الإنجليزي محلّ العربي في الإنتاج بلا خطأ واحد.
I18N = CURRICULUM / "i18n"

API_URL = "https://ollama.com/v1/chat/completions"
TRANSLATOR_MODEL = "mistral-large-3:675b"
# عائلة مختلفة عن المترجم عمدًا. مراجع من نفس العائلة يشارك المترجم
# افتراضاته، فيوافق على الخطأ الذي كان سيرتكبه هو.
# (kimi-k3 يرجّع 402 على هذا المفتاح، وkimi-k2.6 يرجّع 503 — مُتحقَّق 2026-08-11.)
REVIEWER_MODEL = "deepseek-v4-pro"

# الحقول القابلة للترجمة فقط. المعرّفات والفئات العمرية والنطاقات وأرقام
# الترتيب تبقى كما هي — ترجمتها تكسر الربط بالقاعدة والتطبيق.
LESSON_FIELDS = ("title", "summary", "try_this", "reflection_prompts")
PATH_FIELDS = ("title", "description")
TIP_FIELDS = ("text",)

# مصطلحات تُنقل صوتيًا لا تُترجم. الترجمة الحرفية تُفقدها معناها الشرعي:
# «tarbiyah» ليست parenting، و«fitrah» ليست instinct.
GLOSSARY = {
    "تربية": "tarbiyah",
    "أخلاق": "akhlaq",
    "أذكار": "adhkar",
    "فطرة": "fitrah",
    "رفق": "rifq",
    "عقيدة": "aqeedah",
    "سيرة": "seerah",
    "حياء": "haya",
    "بر الوالدين": "birr al-walidayn",
    "صلة الرحم": "silat al-rahim",
    "إحسان": "ihsan",
    "أمانة": "amanah",
    "تزكية": "tazkiyah",
}

# 🚨 قيد برمجي لا تعليمات لنموذج. كل مصطلح إنجليزي من المسرد يجب أن يكون
# له جذر عربي في المصدر. هذا يمنع حقن «rifq» بدل «رحمة» و«amanah» بدل
# «أمان» — أخطاء وقعت فعلًا ٣٤ مرة قبل إضافة هذا القيد (2026-08-11).
# الجذور موسّعة عمدًا: «يربّي» و«تربوي» كلاهما يسمحان بـ tarbiyah،
# و«يستحي» يسمح بـ haya. لكن «رحمة» لا تسمح بـ rifq ولا «أمان» تسمح
# بـ amanah — لأن الكلمتين مختلفتان جذرًا.
GLOSSARY_ROOTS = {
    "tarbiyah": ["ربو", "ربّي", "يرب", "ترب", "تربية", "تربوي"],
    "akhlaq": ["خلق", "أخلاق", "خُلق", "خلقاً", "أخلاقه", "خلقي"],
    "adhkar": ["ذكر", "أذكار", "اذكر"],
    "fitrah": ["فطر", "فطرة", "فطري"],
    "rifq": ["رفق", "رفيقاً", "يرفق", "ارفق", "برفق", "رقيق"],
    "aqeedah": ["عقد", "عقيدة", "عقائدي"],
    "seerah": ["سير", "سيرة", "سيرته"],
    "haya": ["حيي", "حياء", "يستحي", "استحياء", "حيائي"],
    "birr al-walidayn": ["برّ", "بر", "يبرّ", "يبر", "بر الوالد"],
    "silat al-rahim": ["صلة", "رحم", "الأقارب", "أقارب"],
    "ihsan": ["أحسن", "إحسان", "محسن", "المحسنين", "إحساني"],
    "amanah": ["أمن", "أمانة", "أمين", "أمناء", "ثقة", "الأمانة"],
    "tazkiyah": ["زكى", "تزكية", "زكوي"],
}

# ما يجعل ملفًا يستوجب مراجعة شرعية. متعمَّد أنه واسع: خطأ من نوع
# «مرّت آية بلا مراجعة» أفدح بكثير من «راجعنا ملفًا لم يكن يحتاج».
RELIGIOUS_MARKERS = re.compile(
    r"ﷺ|صلى الله عليه|رضي الله عن|قال النبي|قال رسول|عن النبي|حديث|"
    r"قال تعالى|قوله تعالى|في القرآن|سورة|آية|رواه|أخرجه|البخاري|مسلم|"
    r"الترمذي|أبو داود|النسائي|ابن ماجه|أحمد"
)

# 🚨 الكلمات المفتاحية وحدها لا تكفي، وهذا مُتحقَّق لا مُفترض.
# lesson_4-6_islamic_parenting_bond_03 يقتبس «خيركم خيركم لأهله» داخل
# علامتَي اقتباس **بلا ﷺ وبلا «قال النبي» وبلا تخريج** — فلم تلتقطه أي
# علامة أعلاه، بينما وجد المراجع في ترجمته تحريفًا فعليًا للحديث. والحالة
# التي يفلت فيها النص من الكاشف هي الحالة التي تلزم فيها المراجعة أكثر:
# اقتباس بلا إسناد لا يوجد ما يُقابَل به.
# لذلك ثلاث إشارات، والاتحاد لا التقاطع:
#   ١) الكلمات المفتاحية (رخيصة، تمسك المُسنَد)
#   ٢) أي عبارة عربية بين علامات اقتباس (تمسك المقتبس بلا إسناد)
#   ٣) حكم النموذج المراجع صراحةً (يمسك ما تفوته الصياغة)
QUOTED_ARABIC = re.compile(r"['\"«»“”]\s*[؀-ۿ][^'\"«»“”]{8,}['\"«»“”]")

SYSTEM_TRANSLATE = f"""You translate an Islamic parenting curriculum from Arabic \
into English, for Muslim parents who read English but share the same religious \
frame of reference. This is not general localisation — the reader expects Islamic \
vocabulary, not its secular approximations.

Rules:
1. Transliterate these terms rather than translating them; give a short gloss in \
parentheses on first use in a field, then use the term alone:
{json.dumps(GLOSSARY, ensure_ascii=False, indent=2)}
   This table is a substitution rule, not a vocabulary to reach for. Apply an entry \
ONLY where that exact Arabic word appears in the source. Never use a glossary term \
for a different Arabic word that seems close: أدعية is du'a, not adhkar; نصيحة is \
advice, not tarbiyah. Substituting a near-neighbour changes a religious category, \
which is a defect, not a stylistic choice.
2. NEVER paraphrase, shorten or soften a hadith. Translate it faithfully and keep \
any attribution (رواه البخاري, etc.) exactly as given. If you are unsure of the \
established English rendering of a hadith, translate it literally rather than \
reaching for a familiar-sounding phrase.
2b. 🚨 THE QUR'AN IS NOT TRANSLATED. An English rendering of an ayah is *tafsir* \
— interpretation of the meaning — not the Qur'an, and presenting it as the \
Qur'an is a religious error, not a stylistic one. So: do NOT produce an English \
rendering of Qur'anic text. Keep the Arabic ayah exactly as it is in the source, \
and if the source gives an interpretation alongside it, render that and label it \
explicitly — "interpretation of the meaning: …". Never introduce quotation marks \
around English words in a way that presents them as the words of Allah. If the \
Arabic only *names* a surah or refers to the Qur'an without quoting it, translate \
that reference normally — this rule is about rendering ayah text, not about \
mentioning the Qur'an.
3. Keep ﷺ and similar honorifics exactly where they appear.
4. Keep the register warm and direct — a parent speaking to a parent, not an \
academic. Arabic parenting prose is often more affectionate than English; do not \
flatten it into instructional English.
5. Preserve JSON structure exactly: same keys, same array lengths, same order. \
Translate only the values.

Return JSON only. No prose, no markdown fences, no commentary."""

SYSTEM_REVIEW = """You are reviewing an Arabic-to-English translation of Islamic \
parenting material. Your job is to FIND DEFECTS, not to approve. Assume the \
translation is flawed and look for where.

Report, specifically:
- meaning_change: the English says something the Arabic does not, or omits something it does
- religious_error: a hadith or attribution altered, softened, shortened, or given a \
familiar-sounding English phrasing that is not what the Arabic says; an English \
rendering of a Qur'anic ayah presented as the Qur'an rather than as clearly \
labelled interpretation of the meaning (tafsir); or anything attributed to the \
Prophet ﷺ — an honorific, the word "Prophetic", a superlative — that the Arabic \
does not attribute to him
- term_error: an Islamic term translated away instead of transliterated, or transliterated \
inconsistently within the same document
- register: the English is stiff, clinical or preachy where the Arabic is warm and direct
- structure: a key, array element or honorific dropped

Also decide, independently of the defect list: does the ARABIC source quote or \
paraphrase a hadith, a Qur'anic verse, or any statement attributed to the Prophet ﷺ \
or to a companion? Answer yes even when there is no honorific, no "قال النبي" and no \
attribution — a bare quoted phrase such as 'خيركم خيركم لأهله' is still a hadith, and \
that unattributed case is the one that most needs a scholar, because there is no \
citation to check it against. When in doubt, answer yes.

Return JSON only:
{"verdict": "clean" | "defects", "contains_religious_text": true | false, \
"defects": [{"type": "...", "field": "...", "arabic": "...", "english": "...", \
"why": "...", "severity": "high"|"medium"|"low"}]}

An empty defect list on a real translation is more likely to mean you did not look \
than that the translation is perfect. Look again before returning "clean"."""


def _post(model: str, system: str, user: str, timeout: int = 300) -> tuple[str, dict]:
    """نداء واحد مع إعادة محاولة على الأخطاء العابرة."""
    key = os.environ.get("OLLAMA_API_KEY")
    if not key:
        sys.exit("❌ OLLAMA_API_KEY غير مضبوط")
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }).encode()

    last = None
    for attempt in range(3):
        req = urllib.request.Request(
            API_URL, data=body,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.load(r)
            return out["choices"][0]["message"]["content"], out.get("usage", {})
        except urllib.error.HTTPError as e:
            # 401/402/403 حالة حساب لا عطل عابر: إعادة المحاولة تكرّر
            # نفس الرفض وتخفيه خلف تأخير. اسقط فورًا وقل السبب.
            if e.code in (401, 402, 403):
                raise RuntimeError(
                    f"{model}: HTTP {e.code} {e.reason} — النموذج غير متاح "
                    f"على هذا المفتاح، لا تعده."
                ) from e
            last = e
            time.sleep(2 ** attempt * 3)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(2 ** attempt * 3)
    raise RuntimeError(f"{model}: فشل بعد ٣ محاولات: {last}")


def _parse_json(text: str) -> dict:
    """النماذج تلفّ الناتج بأسوار markdown أحيانًا رغم التعليمات."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


def _translatable(doc: dict, fields: tuple) -> dict:
    return {k: doc[k] for k in fields if doc.get(k)}


def _validate_glossary(arabic: dict, english: dict) -> list[str]:
    """قيد برمجي: كل مصطلح إنجليزي من المسرد يجب أن يكون له جذر عربي في المصدر.

    يمنع حقن «rifq» بدل «رحمة» و«amanah» بدل «أمان» — أخطاء وقعت ٣٤ مرة
    قبل إضافة هذا القيد. يرجّع قائمة بالحقن المرفوضة، أو قائمة فارغة إذا سلم.

    🚨 المطابقة بحدود الكلمة لا بالاحتواء. المطابقة النصية الساذجة كانت تجد
    «haya» داخل «al-Hayah» — وهي من «الحياة» لا من «حياء» — فترفض ترجمة سليمة
    مرتين متتاليتين في `lesson_10-12_islamic_parenting_identity_02`. وحارس
    يرفض السليم يُعطَّل، وتعطيله يعيد الأخطاء الأربعة والثلاثين التي وُضع
    لأجلها. (نفس الدرس المستفاد من الهيكل الصامت في `check_quran_citations`:
    المطابقة الفضفاضة تنتج إنذارات كاذبة تُسقِط الحارس نفسه.)
    """
    ar_text = json.dumps(arabic, ensure_ascii=False)
    en_text = json.dumps(english, ensure_ascii=False).lower()
    injections = []
    for en_term, roots in GLOSSARY_ROOTS.items():
        # An English plural or possessive is the same injection wearing a
        # suffix — «seerahs» must not walk past a check that stops «seerah».
        # The suffix list is deliberately short: extending it to any trailing
        # letter re-opens the al-Hayah false positive this replaced.
        if not re.search(rf"\b{re.escape(en_term)}(?:s|es|'s)?\b", en_text):
            continue
        if any(root in ar_text for root in roots):
            continue
        injections.append(
            f"حقن مصطلح: '{en_term}' في الإنجليزية ولا جذر له في العربية "
            f"(الجذور المسموحة: {', '.join(roots[:3])}...)")
    return injections


def translate_file(src: Path, fields: tuple, force: bool = False) -> dict:
    """يترجم ملفًا ويراجعه. يرجّع تقريرًا عن الملف."""
    doc = json.loads(src.read_text(encoding="utf-8"))
    out_path = I18N / "en" / src.parent.name / src.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rid = doc.get("id", src.stem)

    if out_path.exists() and not force:
        return {"id": rid, "status": "skipped", "reason": "مترجم بالفعل"}

    payload = _translatable(doc, fields)
    if not payload:
        return {"id": rid, "status": "skipped", "reason": "لا حقول قابلة للترجمة"}

    src_json = json.dumps(payload, ensure_ascii=False)
    raw, usage_t = _post(TRANSLATOR_MODEL, SYSTEM_TRANSLATE, src_json)
    try:
        translated = _parse_json(raw)
    except json.JSONDecodeError as e:
        return {"id": rid, "status": "failed", "reason": f"ناتج غير صالح: {e}"}

    # تحقّق بنيوي قبل أي حكم على الجودة: مفتاح ناقص أو طول قائمة مختلف
    # عيب يقيني، بينما رأي المراجع احتمالي.
    problems = []
    for k, v in payload.items():
        if k not in translated:
            problems.append(f"مفتاح مفقود: {k}")
        elif isinstance(v, list) and len(translated.get(k, [])) != len(v):
            problems.append(
                f"طول قائمة مختلف في {k}: {len(v)} → {len(translated.get(k, []))}")
    if problems:
        return {"id": rid, "status": "failed", "reason": "; ".join(problems)}

    # 🚨 قيد برمجي: ارفض أي ترجمة تحقن مصطلحًا إسلاميًا لا جذر له في المصدر.
    # هذا يمنع تكرار أخطاء 2026-08-11 (٣٤ حقنة عبر ٤ تمريرات إصلاح).
    glossary_issues = _validate_glossary(payload, translated)
    if glossary_issues:
        return {"id": rid, "status": "failed",
                "reason": "حقن مصطلحات: " + "; ".join(glossary_issues)}

    review_input = json.dumps(
        {"arabic": payload, "english": translated}, ensure_ascii=False)
    raw_r, usage_r = _post(REVIEWER_MODEL, SYSTEM_REVIEW, review_input)
    try:
        review = _parse_json(raw_r)
    except json.JSONDecodeError:
        review = {"verdict": "unreviewed", "defects": []}

    # اتحاد الإشارات الثلاث لا تقاطعها: أي واحدة تكفي للتعليم.
    sig_marker = bool(RELIGIOUS_MARKERS.search(src_json))
    sig_quoted = bool(QUOTED_ARABIC.search(src_json))
    sig_model = bool(review.get("contains_religious_text"))
    needs_scholar = sig_marker or sig_quoted or sig_model

    result = dict(doc)
    result.update(translated)
    result["language"] = "en"
    result["source_language"] = "ar"
    result["translation"] = {
        "translator_model": TRANSLATOR_MODEL,
        "reviewer_model": REVIEWER_MODEL,
        "needs_scholar_review": needs_scholar,
        "scholar_signals": {
            "keyword": sig_marker,
            "quoted_arabic": sig_quoted,
            "reviewer_model": sig_model,
        },
        "review_verdict": review.get("verdict", "unreviewed"),
        "review_defects": review.get("defects", []),
        "approved_by": None,  # يملؤه مراجع بشري، لا هذه الأداة
    }
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "id": rid,
        "status": "translated",
        "needs_scholar_review": needs_scholar,
        "verdict": review.get("verdict", "unreviewed"),
        "defects": review.get("defects", []),
        "tokens_out": (usage_t.get("completion_tokens", 0)
                       + usage_r.get("completion_tokens", 0)),
        "tokens_in": (usage_t.get("prompt_tokens", 0)
                      + usage_r.get("prompt_tokens", 0)),
        "out": str(out_path.relative_to(ROOT)),
    }


def collect(path_id: str | None, do_all: bool, limit: int | None) -> list:
    """يرجّع [(ملف, حقول)] بالترتيب: المسار أولًا ثم دروسه."""
    jobs = []
    if path_id:
        pf = CURRICULUM / "paths" / f"{path_id}.json"
        if not pf.exists():
            sys.exit(f"❌ المسار غير موجود: {pf}")
        jobs.append((pf, PATH_FIELDS))
        lessons = []
        for f in (CURRICULUM / "lessons").glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("path_id") == path_id:
                lessons.append((d.get("order", 999), f))
        jobs += [(f, LESSON_FIELDS) for _, f in sorted(lessons)]
    elif do_all:
        jobs += [(f, PATH_FIELDS)
                 for f in sorted((CURRICULUM / "paths").glob("*.json"))]
        jobs += [(f, LESSON_FIELDS)
                 for f in sorted((CURRICULUM / "lessons").glob("*.json"))]
        jobs += [(f, TIP_FIELDS)
                 for f in sorted((CURRICULUM / "daily_tips").glob("*.json"))]
    else:
        sys.exit("❌ مرّر --path أو --all")
    return jobs[:limit] if limit else jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", help="معرّف مسار واحد")
    ap.add_argument("--all", action="store_true", help="المنهج كله")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true", help="أعد ترجمة الموجود")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs = collect(args.path, args.all, args.limit)
    print(f"📚 {len(jobs)} ملف للترجمة")
    print(f"   مترجم : {TRANSLATOR_MODEL}")
    print(f"   مراجع : {REVIEWER_MODEL}\n")

    if args.dry_run:
        for f, fields in jobs:
            print(f"  [dry-run] {f.name}  حقول={','.join(fields)}")
        return

    def run_one(job):
        """ملف يسقط لا يُسقِط الرحلة — ٤٠ ملفًا ناجحًا وواحد فاشل نتيجة
        أفضل من استثناء يمحو الأربعين."""
        f, fields = job
        try:
            return translate_file(f, fields, args.force)
        except Exception as e:
            return {"id": f.stem, "status": "failed",
                    "reason": f"{type(e).__name__}: {e}"}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_one, jobs))

    ok = [r for r in results if r["status"] == "translated"]
    failed = [r for r in results if r["status"] == "failed"]
    skipped = [r for r in results if r["status"] == "skipped"]
    scholar = [r for r in ok if r.get("needs_scholar_review")]
    defects = [(r["id"], d) for r in ok for d in r.get("defects", [])]

    print("═" * 62)
    print(f"  مترجَم   : {len(ok)}")
    print(f"  متخطّى   : {len(skipped)}")
    print(f"  فاشل     : {len(failed)}")
    print(f"  🕌 يحتاج مراجعة شرعية: {len(scholar)} من {len(ok)}")
    print(f"  التوكن   : دخل={sum(r.get('tokens_in', 0) for r in ok):,}"
          f"  خرج={sum(r.get('tokens_out', 0) for r in ok):,}")
    print(f"  الزمن    : {time.time() - t0:.0f} ثانية")
    print("═" * 62)

    for r in failed:
        print(f"  ❌ {r['id']}: {r['reason']}")

    if defects:
        print(f"\n🔍 المراجع العدائي وجد {len(defects)} ملاحظة:\n")
        for lid, d in defects:
            sev = {"high": "🔴", "medium": "🟡"}.get(d.get("severity"), "⚪")
            print(f"  {sev} [{d.get('type')}] {lid} · {d.get('field')}")
            print(f"      {d.get('why')}")
    else:
        print("\n🔍 المراجع العدائي: صفر ملاحظات — تعامل معها بريبة، "
              "لا كشهادة جودة.")

    if scholar:
        print(f"\n🕌 {len(scholar)} ملف يمسّ حديثًا أو آية ولا يُنشر بلا توقيع "
              "بشري متخصص:")
        for r in scholar:
            print(f"      {r['id']}")


if __name__ == "__main__":
    main()
