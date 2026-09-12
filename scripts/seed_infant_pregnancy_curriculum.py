#!/usr/bin/env python3
"""
Seed script for Infant & Pregnancy (الحمل والرضع) Curriculum Content
====================================================================
Generates:
1. path_0-3_infant_pregnancy_foundations.json
2. 5 Lessons (lesson_0-3_infant_pregnancy_01 to 05)
3. 7 Daily Tips (tip_0-3_031 to 037)
4. NotebookLM source markdown files in notebooklm_sources/prenatal-1/
5. Prompt package in docs/prenatal_notebooklm_prompts.md
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / "knowledge_base" / "curriculum"
PATHS_DIR = CURRICULUM / "paths"
LESSONS_DIR = CURRICULUM / "lessons"
TIPS_DIR = CURRICULUM / "daily_tips"
NLM_DIR = ROOT / "notebooklm_sources" / "prenatal-1"
DOCS_DIR = ROOT / "docs"

CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]")

def assert_clean(text: str, label: str):
    match = CJK_RE.search(text)
    if match:
        raise ValueError(f"CJK/Cyrillic character '{match.group()}' found in {label}")

# ── 1. Path Data ─────────────────────────────────────────────────────────────
PATH_DATA = {
    "id": "path_0-3_infant_pregnancy_foundations",
    "title": "الحمل والمولود الجديد: رحلة الرعاية والسكينة",
    "age_group": "0-3",
    "domain": "infant_pregnancy",
    "description": "مسار شامل لمدة 14 يوماً يرافق الأمهات والآباء الجدد من أواخر الحمل وحتى الأشهر الأولى للمولود: الدعم النفسي والارتباط المبكر بالجنين وسماعه للقرآن، سنن الاستقبال النبوية، إتقان الرضاعة الطبيعية، فك شفرة البكاء والنوم الآمن، وحظر الشاشات وصحة الوالدين النفسية.",
    "lesson_ids": [
        "lesson_0-3_infant_pregnancy_01",
        "lesson_0-3_infant_pregnancy_02",
        "lesson_0-3_infant_pregnancy_03",
        "lesson_0-3_infant_pregnancy_04",
        "lesson_0-3_infant_pregnancy_05"
    ],
    "estimated_days": 14,
    "pedagogical_framework": "attachment_rahma",
    "primary_reference": {
        "type": "دليل_طبي",
        "info": "AAP Safe Sleep & Infant Care Guidelines + تحفة المودود بأحكام المولود لابن القيم"
    },
    "prerequisites": [],
    "is_published": True,
    "version": "1.0.0",
    "created_at": "2026-09-12T19:00:00",
    "updated_at": "2026-09-12T19:00:00",
    "approved_by": None
}

# ── 2. Lessons Data ──────────────────────────────────────────────────────────
LESSONS_DATA = [
    {
        "id": "lesson_0-3_infant_pregnancy_01",
        "path_id": "path_0-3_infant_pregnancy_foundations",
        "title": "سيكولوجية الحمل والرابطة المبكرة مع الجنين",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "unit_ids": ["70ef8432-d97f-490a-acab-8df9e57f8652"],
        "summary": "تبدأ التربية وبناء الارتباط العاطفي قبل الولادة بأشهر. من الأسبوع الثامن عشر يكتمل جهاز السمع لدى الجنين فيبدأ بتمييز نبضات قلب أمه وأصوات والديه. تلاوة القرآن والحديث الهادئ مع الجنين يمنحانه طمأنينة وراحة فطرية. كما تتطلب هذه المرحلة دعماً نفسياً استثنائياً من الزوج للأم الحامل لمواجهة تقلبات الهرمونات والمخاوف الطبيعية، فالأمان النفسي للأم ينعكس مباشرة على استقرار الجنين العصبي ونموه الصحي.",
        "try_this": "هذا الأسبوع: خصصا 10 دقائق يومياً في وقت هادئ قبل النوم — يضع الأب يده برفق على بطن الأم، ويقرأ آيات من القرآن الكريم بصوت دافئ أو يتحدث بكلمات محبة موجهة للجنين باسمه المختار. استشعرا حركة الجنين واستجابته للصوت.",
        "order": 1,
        "estimated_minutes": 12,
        "reflection_prompts": [
            "ما المشاعر التي تراودك عندما تتخيل طفلك يستمع لصوتك من داخل الرحم؟",
            "كيف يمكن للزوج تقديم مساندة ملموسة لتقليل التوتر النفسي للأم هذا الأسبوع؟"
        ],
        "warning_flags": ["pregnancy_anxiety_support"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "updated_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "lesson_0-3_infant_pregnancy_02",
        "path_id": "path_0-3_infant_pregnancy_foundations",
        "title": "سنن الاستقبال النبوية للمولود الجديد",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "unit_ids": ["med-c7a1bbf6"],
        "summary": "رسم الهدي النبوي معالم استقبال المولود بأدق تفاصيلها الروحية والنفسية. تبدأ اللحظات الأولى بالأذان في أذنه اليمنى ليكون أول ما يقرع سمعه كلمة التوحيد، ثم التحنيك بتمرة ملينة لتدريب فمه. وفي اليوم السابع تُسن العقيقة إشاعةً للفرح وشكراً لله وفكاً لرهان المولود، وحلق شعره والتصدق بوزنه فضة، واختيار اسم حسن يليق به. كما يُحصن الرضيع يومياً بالمعوذات والأدعية النبوية لحفظه وبث السكينة في روحه.",
        "try_this": "هذا الأسبوع: جهزا قائمة بأدعية التحصين المأثورة («أعيذك بكلمات الله التامة من كل شيطان وهامة ومن كل عين لامة») واجعلوها روتيناً يومياً ثابتاً يُتلى بصوت عذب عند إرضاع المولود أو هدهدته للنوم، مع الاتفاق المسبق على الاسم وسنن اليوم السابع.",
        "order": 2,
        "estimated_minutes": 14,
        "reflection_prompts": [
            "كيف تساهم سنن الاستقبال النبوية في غرس الانتماء الإيماني للطفل منذ يومه الأول؟",
            "ما هي السنن التي تخططون لتطبيقها فور ولادة طفلكم؟"
        ],
        "warning_flags": ["islamic_sunnah_adherence"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "updated_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "lesson_0-3_infant_pregnancy_03",
        "path_id": "path_0-3_infant_pregnancy_foundations",
        "title": "إتقان الرضاعة الطبيعية والرعاية الجسدية المبكرة",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "unit_ids": ["6970f436-c954-45ac-ab96-30a798cf523f"],
        "summary": "الرضاعة الطبيعية ليست مجرد تغذية، بل هي الحبل السري العاطفي والمناعي بعد الولادة. قطرات اللبأ الأولى (السرسوب) غنية بالأجسام المضادة وتعد أول تطعيم طبيعي للمولود. نجاح الرضاعة يعتمد على الإلتقام العميق للحلمة والهالة لتجنب الألم والتشققات، والاستجابة لعلامات الجوع المبكرة (حركات الفم، مص اليد) قبل وصول الرضيع لمرحلة البكاء. دور الأب هنا محوري في رعاية الأم وتوفير الراحة والماء والطعام لها لتتفرغ للرضاعة.",
        "try_this": "هذا الأسبوع: تدربي على وضعيات الرضاعة المريحة (وضعية المهد، أو الاستلقاء الجانبي)، واحرصي على ملامسة جلد لجلد (Skin-to-Skin) فور الولادة وخلال الرضاعة. وعلى الأب تولي مهمة التجشؤ وتغيير الحفاض بعد الرضعة لتخفيف العبء عن الأم.",
        "order": 3,
        "estimated_minutes": 15,
        "reflection_prompts": [
            "ما التحديات التي تتوقعين مواجهتها في الرضاعة وكيف يستعد الزوج لدعمك؟",
            "كيف تلاحظين إشارات جوع طفلك قبل أن يبدأ في البكاء؟"
        ],
        "warning_flags": ["feeding_latch_guidance"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "updated_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "lesson_0-3_infant_pregnancy_04",
        "path_id": "path_0-3_infant_pregnancy_foundations",
        "title": "فك شفرة البكاء وهندسة نوم الرضيع",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "unit_ids": ["c88f868b-4f40-45eb-b357-f8867b2c327d"],
        "summary": "البكاء هو لغة الرضيع الوحيدة للتعبير عن احتياجاته: الجوع، المغص والغازات، البلل، أو فرط الاستثارة والحرارة. لتهدئة الرضيع، نطبق تقنية العناصر الخمسة الشهيرة (5 S's): التقميط الآمن، النوم الجانبي المؤقت أثناء الحمل، الضوضاء البيضاء (محاكاة صوت الرحم)، الهدهدة المنتظمة، والمص. وللنوم الآمن: يجب نوم الرضيع دائماً على ظهره في سرير مستقل بجانب الوالدين دون وسائد أو ألعاب رخوة، للوقاية الصارمة من متلازمة موت الرضع المفاجئ (SIDS).",
        "try_this": "هذا الأسبوع: تدربا على طريقة التقميط الصحيح (تثبيت اليدين مع إعطاء حرية كاملة لوركي الرضيع وساقيه لتجنب خلع المفصل)، وجهزا مصدراً لصوت الضوضاء البيضاء الهادئة أو تلاوة قرآنية رتيبة في غرفة النوم.",
        "order": 4,
        "estimated_minutes": 15,
        "reflection_prompts": [
            "كيف تتصرف إذا استمر بكاء الرضيع بعد التأكد من نظافته ورضاعته؟",
            "هل بيئة سرير طفلك مطابقة لمعايير النوم الآمن (خالية من الأغطية الثقيلة والوسائد)؟"
        ],
        "warning_flags": ["safe_sleep_sids_prevention"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "updated_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "lesson_0-3_infant_pregnancy_05",
        "path_id": "path_0-3_infant_pregnancy_foundations",
        "title": "الدرع الرقمي المبكر وصحة الوالدين النفسية",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "unit_ids": ["77e9aa1e-342f-4497-bb5b-a998ac638da2"],
        "summary": "في أول سنتين من العمر، ينمو دماغ الطفل بأسرع وتيرة في حياته عبر التفاعل البشري الحقيقي واللعب الحسي. توصي جميع المنظمات الطبية العالمية بسياسة الصفر شاشات (Zero Screens): منع الشاشات والهواتف وقنوات أغاني الرضع تماماً دون سن العامين، لحماية الطفل من تأخر الكلام وتشتت الانتباه وضعف التواصل البصري. في المقابل، يجب الاهتمام بصحة الأم النفسية: التمييز بين كآبة النفاس العابرة واكتئاب ما بعد الولادة، وتبادل الأدوار بين الزوجين للوقاية من الاحتراق النفسي والإجهاد المزمن.",
        "try_this": "هذا الأسبوع: اتفقا كزوجين على إعلان غرفة الرضيع منطقة خالية تماماً من الشاشات المفتوحة والمشتتات الرقمية. ضعا جدولاً مرناً لتبادل رعاية المولود ليلاً بحيث تنال الأم 4 ساعات متواصلة من النوم على الأقل لإعادة ترميم طاقتها النفسية والجسدية.",
        "order": 5,
        "estimated_minutes": 14,
        "reflection_prompts": [
            "ما هي البدائل الطبيعية (كلام، ترنيم، ألعاب حسية) التي ستقدمها لطفلك بدلاً من تشغيل المقاطع المرئية؟",
            "كيف نراقب ونعالج مشاعر الإرهاق النفسي بعد الولادة كفريق عمل واحد؟"
        ],
        "warning_flags": ["postpartum_mental_health", "zero_screen_policy"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "updated_at": "2026-09-12T19:00:00",
        "approved_by": None
    }
]

# ── 3. Daily Tips Data ───────────────────────────────────────────────────────
TIPS_DATA = [
    {
        "id": "tip_0-3_031",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "text": "للحامل: الجنين يسمع صوتك بوضوح من الشهر الخامس. تلاوتك اليومية للقرآن وحديثك معه يبنيان أمانه النفسي الفطري قبل الولادة.",
        "unit_id": None,
        "day_of_week": 0,
        "time_of_day": "morning",
        "tags": ["حمل", "سماع_الجنين", "قرآن"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "tip_0-3_032",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "text": "للزوج: الدعم النفسي للمرأة الحامل والرفق بها في تقلبات المزاج عبادة أسرية تخفف توتر الجنين وتدعم صحته العصبية.",
        "unit_id": None,
        "day_of_week": 1,
        "time_of_day": "evening",
        "tags": ["الزوج_الداعم", "حمل", "رفق"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "tip_0-3_033",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "text": "في أول ساعات المولود: قطرات لبن السرسوب (اللبأ) هي التطعيم الأول الطبيعي لطفلك، غنية بالمناعة والأجسام المضادة المركزة.",
        "unit_id": None,
        "day_of_week": 2,
        "time_of_day": "morning",
        "tags": ["رضاعة_طبيعية", "لبأ", "مناعة"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "tip_0-3_034",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "text": "سنة نبوية: الأذان في أذن المولود اليمنى عند ولادته يرسخ نداء التوحيد كأول صوت يدخل سمعه ويبعث السكينة في روحه.",
        "unit_id": None,
        "day_of_week": 3,
        "time_of_day": "morning",
        "tags": ["سنن_المولود", "أذان", "توحيد"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "tip_0-3_035",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "text": "عند بكاء الرضيع: طبق تقنية التقميط والضوضاء البيضاء ومص اللهاية؛ إنها تحاكي بيئة الرحم الآمنة وتهدئ جهازه العصبي سريعاً.",
        "unit_id": None,
        "day_of_week": 4,
        "time_of_day": "bedtime",
        "tags": ["بكاء_الرضيع", "تقميط", "ضوضاء_بيضاء"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "tip_0-3_036",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "text": "نوم الرضيع الآمن: دائماً على الظهر في سرير مستقل خالٍ من الوسائد والأغطية الفضفاضة، للوقاية الصارمة من متلازمة SIDS.",
        "unit_id": None,
        "day_of_week": 5,
        "time_of_day": "bedtime",
        "tags": ["نوم_آمن", "SIDS", "صحة_الرضيع"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "approved_by": None
    },
    {
        "id": "tip_0-3_037",
        "age_group": "0-3",
        "domain": "infant_pregnancy",
        "text": "قاعدة ذهبية: صفر شاشات تحت سن العامين. دماغ طفلك يحتاج وجهك وصوتك ليطور النطق والتواصل، والشاشات تؤخر الكلام.",
        "unit_id": None,
        "day_of_week": 6,
        "time_of_day": "evening",
        "tags": ["صفر_شاشات", "نمو_الدماغ", "تواصل"],
        "is_published": True,
        "version": "1.0.0",
        "created_at": "2026-09-12T19:00:00",
        "approved_by": None
    }
]

def main():
    print("Seeding Infant & Pregnancy curriculum content...")
    
    # 1. Path
    path_file = PATHS_DIR / f"{PATH_DATA['id']}.json"
    assert_clean(json.dumps(PATH_DATA, ensure_ascii=False), "PATH_DATA")
    path_file.write_text(json.dumps(PATH_DATA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created path: {path_file.name}")

    # 2. Lessons
    for lesson in LESSONS_DATA:
        assert_clean(json.dumps(lesson, ensure_ascii=False), lesson["id"])
        lesson_file = LESSONS_DIR / f"{lesson['id']}.json"
        lesson_file.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Created lesson: {lesson_file.name}")

    # 3. Tips
    for tip in TIPS_DATA:
        assert_clean(json.dumps(tip, ensure_ascii=False), tip["id"])
        tip_file = TIPS_DIR / f"{tip['id']}.json"
        tip_file.write_text(json.dumps(tip, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Created tip: {tip_file.name}")

    # 4. NotebookLM Sources
    NLM_DIR.mkdir(parents=True, exist_ok=True)
    for lesson in LESSONS_DATA:
        md_content = f"""# مصدر الدرس: {PATH_DATA['title']} / {lesson['title']}
**المعرف:** {lesson['id']}
**المسار:** {lesson['path_id']}
**الفئة العمرية:** {lesson['age_group']}
**المجال:** {lesson['domain']}
**الوحدات المرجعية:** {', '.join(lesson['unit_ids'])}

---

## ملخص الدرس
{lesson['summary']}

## جرّب هذا الأسبوع
{lesson['try_this']}

## أسئلة التأمل
1. {lesson['reflection_prompts'][0]}
2. {lesson['reflection_prompts'][1]}

## المراجع
- AAP (American Academy of Pediatrics) Guidelines on Infant Care & Safe Sleep
- WHO Guidelines on Early Child Development & Breastfeeding
- كتاب «تحفة المودود بأحكام المولود» للإمام ابن القيم الجوزية
- الهدي النبوي الشريف في رعاية النشء والمولود

---

*هذا المستند معد للرفع على Google NotebookLM / Gemini Notebook لتوليد الفيديوهات (Video Studio)، والملخصات الصوتية (Audio Overview)، وبطاقات الإنفوجرافيك.*
"""
        assert_clean(md_content, f"NLM {lesson['id']}")
        nlm_file = NLM_DIR / f"{lesson['id']}.md"
        nlm_file.write_text(md_content, encoding="utf-8")
        print(f"Created NLM source: {nlm_file.name}")

    # 5. NotebookLM README
    nlm_readme = f"""# مصادر مسار الحمل والرضع — Google NotebookLM / Gemini Notebook

هذا المجلد يضم مصادر الـ 5 دروس الخاصة بمسار:
**«{PATH_DATA['title']}»** (`{PATH_DATA['id']}`)

## كيفية الاستخدام مع Gemini Notebook / NotebookLM:
1. افتح [Google NotebookLM](https://notebooklm.google.com).
2. أنشئ نوتبوك جديد باسم: **«تطبيق المربي - مسار الحمل والرضع»**.
3. ارفع ملفات هذا المجلد الخمسة (`.md`) كمصادر للنوتبوك.
4. استخدم دليل البرومبتات في `docs/prenatal_notebooklm_prompts.md` لتوليد:
   - **فيديوهات Video Studio** (باللغة العربية).
   - **حلقات بودكاست Audio Overview** (باللغة العربية).
   - **بطاقات الإنفوجراف والملخصات الدراسية Study Guides**.
"""
    assert_clean(nlm_readme, "NLM README")
    (NLM_DIR / "README.md").write_text(nlm_readme, encoding="utf-8")

    # 6. Docs: Prompts guide
    prompts_doc = f"""# برومبتات توليد فيديوهات وإنفوجراف مسار الحمل والرضع في NotebookLM

> **لخالد:** هذه حزمة البرومبتات المهيأة لـ **Google NotebookLM / Gemini Notebook** لتوليد الفيديوهات والإنفوجراف والبودكاست الخاص بمسار **«الحمل والمولود الجديد: رحلة الرعاية والسكينة»**.
> **الإعداد الحاسم:** في إعدادات التوليد داخل NotebookLM، تأكد من اختيار **Output language: العربية**.

---

## 1) فيديو الدرس الأول: سيكولوجية الحمل والرابطة المبكرة مع الجنين
* **الملف المصدر:** `notebooklm_sources/prenatal-1/lesson_0-3_infant_pregnancy_01.md`
* **البرومبت:**
```text
أنشئ فيديو تعليمياً دافئاً ومحفزاً (~4-5 دقائق) باللغة العربية الفصحى الميسرة موجهاً للأمهات الحوامل والآباء الجدد عن سيكولوجية الحمل والرابطة المبكرة مع الجنين. النقاط الجوهرية: متى يكتمل سمع الجنين (الأسبوع 18)؛ استجابة الجنين لنبضات قلب أمه وصوت القرآن الكريم وصوت الأب؛ كيف ينعكس الأمان النفسي للأم وراحة بالها على تكوين الجهاز العصبي للجنين؛ دور الزوج المحوري في تقديم السند والرفق بالمرأة الحامل وتخفيف القلق؛ تمرين عملي: الحديث والقراءة اليومية للجنين قبل النوم. نبرة حانية، مطمئنة، مفعمة بالسكينة والإيمان.
```

---

## 2) فيديو الدرس الثاني: سنن الاستقبال النبوية للمولود الجديد
* **الملف المصدر:** `notebooklm_sources/prenatal-1/lesson_0-3_infant_pregnancy_02.md`
* **البرومبت:**
```text
أنشئ فيديو تعليمياً وإيمانياً راقياً (~4-5 دقائق) بالعربية الفصحى عن الهدي النبوي في استقبال المولود الجديد. النقاط الجوهرية: الحكمة النفسية والروحية للأذان في الأذن اليمنى ليكون التوحيد أول ما يسمعه؛ التحنيك بتمرة؛ سنن اليوم السابع: اختيار الاسم الحسن، العقيقة كشكر لله وإشاعة للمودة، وحلق الشعر والتصدق بوزنه؛ التحصين اليومي بالمعوذات والأدعية النبوية لحفظ الصغير من العين والفزع. نبرة نورانية تجمع بين روعة السنّة النبوية والارتباط الأسري العميق.
```

---

## 3) فيديو الدرس الثالث: إتقان الرضاعة الطبيعية والرعاية الجسدية المبكرة
* **الملف المصدر:** `notebooklm_sources/prenatal-1/lesson_0-3_infant_pregnancy_03.md`
* **البرومبت:**
```text
أنشئ فيديو إرشادياً عملياً وطبياً مبسطاً (~4-5 دقائق) بالعربية للأمهات والآباء الجدد عن إتقان الرضاعة الطبيعية. النقاط: المعجزة المناعية للبأ (السرسوب) في الساعات الأولى كأول تطعيم طبيعي؛ الأوضاع الصحيحة للإلتقام لتجنب تشققات وألم الحلمة؛ قراءة علامات الجوع المبكرة قبل مرحلة البكاء؛ أهمية ملامسة الجلد للجلد (Skin-to-Skin)؛ كيف يكون الزوج شريكاً عملياً في راحة الأم بعد الولادة والتجشؤ وتغيير الحفاض. نبرة علمية دقيقة مشجعة للأم وداعمة لثقتها بنفسها.
```

---

## 4) فيديو الدرس الرابع: فك شفرة البكاء وهندسة نوم الرضيع
* **الملف المصدر:** `notebooklm_sources/prenatal-1/lesson_0-3_infant_pregnancy_04.md`
* **البرومبت:**
```text
أنشئ فيديو توعوياً عملياً (~4-5 دقائق) بالعربية عن فهم بكاء الرضيع وقواعد النوم الآمن. النقاط: البكاء كلغة احتياج (جوع، غازات، فرط استثارة، بلل)؛ تقنية التهدئة الخمسية (5 S's): التقميط الصحي لليدين مع راحة الوركين، وضعية الجنب المؤقتة أثناء الحمل، الضوضاء البيضاء لمحاكاة صوت الرحم، الهدهدة اللطيفة، والمص؛ القواعد الصارمة للنوم الآمن والوقاية من متلازمة موت الرضع المفاجئ (SIDS): النوم دائماً على الظهر، في سرير مستقل بجانب الوالدين، خالي تماماً من الوسائد والأغطية الفضفاضة. نبرة عملية هادئة ومريحة لأعصاب الوالدين.
```

---

## 5) فيديو الدرس الخامس: الدرع الرقمي المبكر وصحة الوالدين النفسية
* **الملف المصدر:** `notebooklm_sources/prenatal-1/lesson_0-3_infant_pregnancy_05.md`
* **البرومبت:**
```text
أنشئ فيديو توعوياً قوياً وملهماً (~4-5 دقائق) بالعربية الفصحى عن حماية الرضيع من الشاشات والعناية بصحة الوالدين النفسية. النقاط: قاعدة الصفر شاشات التامة دون سن العامين وحظر هواتف الأطفال وأغاني الرضع الرقمية حمايةً لنمو الدماغ من تشتت الانتباه وتأخر النطق؛ البدائل الطبيعية عبر التفاعل البشري المباشر وتعبيرات الوجه والكلام؛ مراقبة صحة الأم بعد الولادة والفرق بين كآبة النفاس العابرة واكتئاب ما بعد الولادة؛ الشراكة الزوجية وجدولة ساعات النوم للوقاية من الاحتراق النفسي. رسالة ختامية واثقة وداعمة للأسرة.
```

---

## 6) برومبت لتوليد البودكاست الحواري (Audio Overview / Podcast)
* **التوجيه (Customize Prompt):**
```text
قدم حواراً صوتياً دافئاً وتفاعلياً باللغة العربية الفصحى بين مقدم ومقدمة، يناقشان فيه خلاصة رحلة الحمل ورعاية المولود الجديد: أهمية الدعم النفسي للأم، جمال السنن النبوية، أسرار نجاح الرضاعة والنوم الآمن، والتحذير من إعطاء الشاشات للرضع. الحوار يجب أن يكون مليئاً بالتعاطف، النصائح الواقعية، والروح الإيجابية التي تشعر الوالدين بأنهما ليسا وحدهما في هذه الرحلة.
```
"""
    assert_clean(prompts_doc, "PROMPTS DOC")
    (DOCS_DIR / "prenatal_notebooklm_prompts.md").write_text(prompts_doc, encoding="utf-8")
    print("Created prompts doc: docs/prenatal_notebooklm_prompts.md")
    print("All curriculum files created successfully!")

if __name__ == "__main__":
    main()
