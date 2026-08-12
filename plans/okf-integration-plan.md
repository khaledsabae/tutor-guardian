# خطة دمج Open Knowledge Format (OKF) في مشروع المربّي الذكي

> الحالة: خطة تخطيطية — لا يبدأ التنفيذ الفعلي إلا بعد الموافقة عليها.
> تم إعدادها بعد بحث في هيكل المشروع ومراجعة مفاهيم OKF وفكرة LLM Wiki.

---

## 1. ملخّص الوضع الحالي

### 1.1 ما هو OKF؟

Open Knowledge Format (OKF) هو معيار مفتوح من Google لتنظيم قواعد المعرفة الشخصية (Second Brain / LLM Wiki) بحيث يمكن لأي وكيل ذكاء اصطناعي يفهم المعيار قراءتها وفهرستها وتبادلها. الركيزة:
- كل وثيقة معرفية تبدأ بـ frontmatter (metadata).
- الحقل **الإلزامي** الوحيد هو `type`.
- الملفات تُنظّم في فهارس واضحة (bundles).
- العلاقات بين الوحدات تُعرّف显式اً عبر `relations`.
- الهدف: التوافقية — معرفة المستخدم تنتقل بين الأدوات بدون lock-in.

### 1.2 هيكل المربّي الحالي

المشروع يعتمد حالياً على:
- `knowledge_base/units/*.json` — وحدات معرفة بتنسيق JSON مع Pydantic model (`KnowledgeUnit`).
- `docs/lesson_index.json` — فهرس الدروس، assets، metadata.
- `source_to_lesson.json` — mapping بين المصادر PDF والدروس.
- `scripts/infographic_prompts.md` — برومبتات توليد صور.
- `backend/app/services/knowledge_loader.py` — يحمّل الوحدات JSON.
- `backend/app/services/retrieval.py` + ChromaDB — RAG والـembeddings.
- `backend/app/curriculum_loader.py` — يحمّل المنهج (paths/lessons).

### 1.3 لماذا OKF مناسب للمربّي؟

المشروع بالفعل يبني **قاعدة معرفة تربوية إسلامية** تخدم وكيلاً واحداً (المساعد الذكي). لكن الهيكل حالياً:
- مختلط بين JSON وMarkdown وبيانات NotebookLM.
- مرتبط بتنفيذ داخلي محدد (Pydantic models معينة، مسارات ملفات ثابتة).
- لا يتيح تصدير المحتوى لوكيل آخر أو مشاركته.

بتطبيق OKF يمكن:
1. جعل المحتوى التربوي قابلاً للنقل والمشاركة.
2. تحسين الـRAG بتقسيم أوضح للوحدات وعلاقاتها (lesson → flashcard → quiz → podcast → infographic).
3. إنشاء **حزمة معرفية (OKF Bundle)** للمربّي يمكن للأهل أو المؤسسات تحميلها وتشغيلها في وكلائهم الخاصين.
4. تسهيل توسّع المحتوى مستقبلاً (إضافة دروس، ترجمات، مسارات عمرية جديدة) بدون تعديل الكود.

---

## 2. الأهداف الاستراتيجية

### 2.1 الهدف العام

تحويل «المربّي الذكي» من نظام مغلق يعتمد على JSON داخلي إلى **منصة معرفية مبنية على معيار OKF**:
- المحتوى التعليمي يُخزّن في وحدات OKF.
- الباك-إند يستطيع قراءة وكتابة OKF.
- يمكن تصدير Bundle كامل للمستخدمين أو المؤسسات.
- يمكن لأي وكيل خارجي فهم محتوى المربّي.

### 2.2 الأهداف الفرعية (قابلة للقياس)

| # | الهدف | المقياس | المدة التقديرية |
|---|-------|---------|-----------------|
| 1 | تعريف `okf_types` للمربّي | 6-8 أنواع واضحة | 1-2 أيام |
| 2 | تحويل 10% من الوحدات الحالية إلى OKF Markdown | 100-150 unit | 3-5 أيام |
| 3 | تحديث `knowledge_loader.py` ليقرأ OKF | يعمل جنب القديم | 2-3 أيام |
| 4 | تحديث `retrieval.py` ليستخدم OKF metadata + relations | تحسين F1 score | 3-5 أيام |
| 5 | إنشاء OKF Bundle exporter | ملف `.zip` قابل للتحميل | 2-3 أيام |
| 6 | توثيق OKF schema للمشروع | `docs/okf/README.md` | 1-2 يوم |

---

## 3. التحديات والمخاطر

### 3.1 التحديات التقنية

1. **الاعتماد الحالي على JSON**: الوحدات الموجودة في `knowledge_base/units/*.json` تحتوي على حقول مثل `text_original`, `text_simplified`, `intervention_type`, `severity`, `reference_type` — لا تتطابق مباشرة مع OKF.
2. **عدم توفر SPEC.md الرسمي**: محاولات جلب ملف المواصفات من GitHub فشلت (404). سنعتمد على ملخّصات الفيديو + أمثلة Cole Medin + التجربة العملية.
3. **RAG الحالي يعتمد على ChromaDB**: تحويل الوحدات لـ Markdown قد يؤثر على طول chunks وجودة embeddings.
4. **Assets المرتبطة بالدروس**: الدروس ليست نصاً فحسب، لها flashcards, quizzes, infographics, podcasts, videos, reports — يجب أن يدعم OKF هذه العلاقات.
5. **اللغة العربية والـRTL**: يجب أن يظهر OKF frontmatter والمحتوى بشكل صحيح في Markdown.

### 3.2 المخاطر التشغيلية

1. **التطبيق منتج على Google Play**: أي تغيير في هيكل البيانات يجب أن يكون **backward-compatible**.
2. **لا نعطل RAG الحالي**: يجب أن يعمل OKF loader جنباً إلى جنب مع الـloader القديم.
3. **الـDocker image والـVPS**: التغييرات يجب أن تُبنى وتُنشر دون تعطيل الخدمة.

### 3.3 الفرص

1. **التسويق والنشر**: OKF Bundle يمكن أن يكون منتجاً جانبياً (مثلاً: "حمّل معرفة المربّي لوكيلك الخاص").
2. **التعاون مع مؤثرين**: الشيوخ والمربّون يمكنهم المساهمة بمحتوى OKF.
3. **الأرشفة**: المحتوى التربوي يُحفظ بتنسيق مستدام بدلاً من JSON داخلي.

---

## 4. التصميم المقترح

### 4.1 أنواع الوحدات المعرفية (OKF Types) للمربّي

```yaml
# 1. الوحدة المعرفية الأساسية (الدرس)
type: knowledge.unit
id: lesson_7-9_aqeedah_fundamentals_05
title: "أركان الإيمان الستة"
subtitle: "درس عقيدي للأطفال 7-9 سنوات"
topics: ["aqeedah_fundamentals"]
age_group: "7-9"
domain: "aqeedah"
language: "ar"
source_id: "..."
relations:
  - type: has_flashcard
    target: knowledge/flashcards/lesson_7-9_aqeedah_fundamentals_05_fc.md
  - type: has_quiz
    target: knowledge/quizzes/lesson_7-9_aqeedah_fundamentals_05_qz.md
  - type: has_infographic
    target: assets/infographics/....png
  - type: has_podcast
    target: assets/podcasts/....mp3
  - type: belongs_to_path
    target: knowledge/paths/aqeedah_fundamentals_7-9.md
---
محتوى الدرس بالعربية...
```

```yaml
# 2. البطاقة التعليمية
type: knowledge.flashcard
id: lesson_7-9_aqeedah_fundamentals_05_fc
parent: knowledge/units/lesson_7-9_aqeedah_fundamentals_05.md
---
Q: ما هي أركان الإيمان؟
A: الإيمان بالله، ملائكته، كتبه، رسله، اليوم الآخر، والقدر خيره وشره.
```

```yaml
# 3. الاختبار
type: knowledge.quiz
id: lesson_7-9_aqeedah_fundamentals_05_qz
parent: knowledge/units/lesson_7-9_aqeedah_fundamentals_05.md
---
- question: ...
  options: [...]
  correct: 0
```

```yaml
# 4. المسار التعليمي
type: knowledge.path
id: aqeedah_fundamentals_7-9
title: "بذور العقيدة"
age_group: "7-9"
---
- lesson: knowledge/units/lesson_7-9_aqeedah_fundamentals_01.md
- lesson: knowledge/units/lesson_7-9_aqeedah_fundamentals_02.md
...
```

```yaml
# 5. المصدر
type: knowledge.source
id: source_...
title: "كتاب ..."
author: "..."
url: "..."
---
ملخص أو مرجعية المصدر.
```

```yaml
# 6. البرومبت/الدليل
type: knowledge.prompt
id: prompt_infographic_aqeedah_01
---
التعليمات التي تُولّد الانفوجراف.
```

```yaml
# 7. الإجابة النموذجية (Q&A)
type: knowledge.qa
id: qa_...
topics: ["aqeedah"]
age_group: "7-9"
---
Q: كيف أعلّم طفلي أركان الإيمان؟
A: ...
```

### 4.2 الهيكل المقترح للمجلدات

```
okf/
├── README.md                    # وصف الباندل والمعايير
├── okf.json                     # فهرس الباندل + metadata
├── knowledge/
│   ├── units/                   # الدروس الأساسية
│   ├── flashcards/              # البطاقات
│   ├── quizzes/                 # الاختبارات
│   ├── paths/                   # المسارات العمرية/الموضوعية
│   ├── sources/                 # المصادر الشرعية/التربوية
│   ├── prompts/                 # برومبتات التوليد
│   └── qa/                      # أسئلة وأجوبة نموذجية
├── assets/
│   ├── infographics/
│   ├── podcasts/
│   ├── videos/
│   └── thumbnails/
└── relations/
    └── graph.json               # علاقات بين الوحدات (اختياري)
```

### 4.3 الفهرس العام (okf.json)

```json
{
  "okf_version": "1.0",
  "bundle_name": "tutor-guardian-islamic-parenting",
  "title": "المربّي الذكي — المعرفة التربوية الإسلامية",
  "language": "ar",
  "created_at": "2026-07-02",
  "updated_at": "2026-07-02",
  "stats": {
    "units": 156,
    "flashcards": 156,
    "quizzes": 156,
    "paths": 39,
    "sources": 44,
    "infographics": 156,
    "podcasts": 109
  },
  "indexes": [
    "knowledge/units/*.md",
    "knowledge/paths/*.md",
    "knowledge/flashcards/*.md",
    "knowledge/quizzes/*.md"
  ],
  "license": "CC BY-NC-ND 4.0",
  "attribution": "فريق المربّي الذكي"
}
```

---

## 5. خطة التنفيذ المرحلية

### المرحلة 0: التحضير والتثبيت (1-2 يوم)

- [ ] البحث عن SPEC.md الرسمي لـ OKF بدقة (repo مختلف، docs Google Cloud، أمثلة).
- [ ] تحديد `okf_types` النهائية للمربّي.
- [ ] كتابة `docs/okf/README.md` داخل المشروع.
- [ ] إنشاء JSON Schema صغير للتحقق من frontmatter.
- [ ] **لا يُمسّش المحتوى الحالي**.

### المرحلة 1: OKF Loader وتكامل Backward-Compatible (2-3 أيام)

- [ ] إنشاء `backend/app/services/okf_loader.py` يقرأ ملفات `.md` ذات frontmatter.
- [ ] تحويل ملفات Markdown إلى `KnowledgeUnit` + metadata + relations.
- [ ] تحديث `knowledge_loader.py` ليدمج الوحدات القديمة (JSON) مع الجديدة (OKF Markdown).
- [ ] إضافة اختبارات (`pytest`) للـloader.
- [ ] التأكد من أن RAG الحالي لا يتأثر.

### المرحلة 2: إنشاء نماذج OKF حقيقية (3-5 أيام)

- [ ] اختيار 3-5 دروس من كل محور (عقيدة، تربية، وعي رقمي، صحة).
- [ ] تحويلها إلى `.md` OKF مع assets relations.
- [ ] تحويل flashcards وquizzes المقابلة.
- [ ] إنشاء 3 مسارات OKF (path) تجريبية.
- [ ] اختبار العرض في التطبيق.

### المرحلة 3: Exporter لـ OKF Bundle (2-3 أيام)

- [ ] إنشاء `scripts/export_okf_bundle.py`.
- [ ] يصدر من:
  - `knowledge_base/units/*.json` → `okf/knowledge/units/*.md`
  - `docs/lesson_index.json` → `okf/knowledge/paths/*.md`
  - `source_to_lesson.json` → `okf/knowledge/sources/*.md`
  - `docs/lesson_assets/*` → `okf/assets/*`
  - `scripts/infographic_prompts.md` → `okf/knowledge/prompts/`
- [ ] إنشاء `okf/okf.json` + README + relations.
- [ ] اختبار استيراد الباندل في بيئة نظيفة.

### المرحلة 4: تحسين RAG باستخدام OKF (3-5 أيام)

- [ ] تدريب `retrieval.py` على استخدام `type` و`relations` و`age_group` كفلاتر.
- [ ] Chunking محسّن: فصل السؤال والجواب والمحتوى.
- [ ] دعم semantic search على العلاقات (مثلاً: "أعطني دروس العقيدة للأطفال 7-9").
- [ ] قياس F1/recall قبل وبعد.

### المرحلة 5: الانتقال الكامل (أسبوعين - شهر)

- [ ] تحويل كل الوحدات JSON إلى OKF Markdown.
- [ ] حذف dependency على JSON القديم (بعد التأكد من الاستقرار).
- [ ] تحديث Docker image لتتضمن `okf/` directory.
- [ ] نشر bundle للمستخدمين.
- [ ] تحديث الوثائق.

### المرحلة 6: المنتجات المشتقة (اختياري)

- [ ] صفحة على الموقع: "حمّل معرفة المربّي لوكيلك".
- [ ] API endpoint: `/api/okf/bundle` يرجّع ZIP.
- [ ] Marketplace بسيط للمساهمات.

---

## 6. الاعتمادات والموارد

### 6.1 ما نحتاجه

1. **SPEC.md الرسمي**: البحث عنه في GitHub أو Google Cloud docs.
2. **أمثلة حقيقية**: bundle Cole Medin أو أي bundle OKF آخر.
3. **وقت**: المراحل 0-4 تستغرق تقريباً 2-3 أسابيع بمعدل ساعة-ساعتين يومياً.
4. **اختبار**: يجب أن تكون كل مرحلة test-covered.

### 6.2 الأدوات المقترحة

- `python-frontmatter` لقراءة/كتابة Markdown frontmatter.
- `pydantic` للتحقق من schema.
- `markdown-it-py` أو `marko` لتحليل المحتوى.
- `pytest` للاختبارات.

---

## 7. القرارات المطلوبة منك

قبل بدء التنفيذ، نحتاج قرارك في النقاط التالية:

1. **هل نبدأ فوراً بالمرحلة 0 والـ1 (loader backward-compatible)؟**
2. **هل تريد أن يكون OKF Bundle منتجاً جانبياً للمستخدمين؟**
3. **هل تقبل تغيير اسم/هيكل `knowledge_base/units/` في المستقبل؟**
4. **هل لديك تفضيل لترخيص المحتوى عند التصدير؟** (مثلاً CC BY-NC-ND).
5. **هل تريد أن أبحث الآن عن SPEC.md الرسمي ونماذج OKF حقيقية؟**

---

## 8. الخلاصة

OKF فرصة قوية للمربّي لأنه يحوّل المحتوى التربوي من بيانات داخلية مغلقة إلى **معرفة قابلة للنقل والمشاركة والتوسّع**. التنفيذ يتم بشكل تدريجي ولا يؤثر على التطبيق المنشور. المرحلة الأولى (loader + نماذج محدودة) محدودة المخاطر وعائدها عالٍ.

**التوصية:** الموافقة على بدء المرحلة 0 والمرحلة 1.
