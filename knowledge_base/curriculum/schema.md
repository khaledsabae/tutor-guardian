# Curriculum Schema — `knowledge_base/curriculum/`

**Source of truth** لهيكل المنهج التفاعلي في Tutor Guardian. يُكمّل `knowledge_base/schema/knowledge_unit.schema.json` (وحدات المعرفة الخام في الـ RAG) بطبقة curriculum أعلى تُجمّع الوحدات في رحلات عملية للوالد.

> **المرجع التربوي:** البحث 1 في `docs/research/01_content_pedagogy/r1_framework_v2.md` (Prophetic 7-7-7 + Al-Ghazali tazkiyah + Piaget/Erikson/Vygotsky per age band).
> **عقد API:** `MOBILE_API.md` (الـ enums في `backend/app/core/taxonomy.py` هي المرجع).
> **حارس السلامة:** `ops/tools/check_kb_integrity.py` — يضمن تطابق `knowledge_unit.schema.json` مع `taxonomy.py`. الـ curriculum schemas هنا تتحقق ذاتياً فقط (`Draft202012Validator.check_schema`).

---

## 1. نظرة عامة (3 طبقات)

```
┌─────────────────────────────────────────────────────────────┐
│ PATH (knowledge_base/curriculum/paths/*.json)               │
│ رحلة تربوية متكاملة ≤ 30 يوم لفئة عمرية ومجال محددين     │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ LESSON (knowledge_base/curriculum/lessons/*.json)     │  │
│  │ درس واحد — 5 دقائق قراءة + try_this + reflection     │  │
│  │                                                       │  │
│  │  ┌──────────────────────────────────────────────┐    │  │
│  │  │ KNOWLEDGE UNIT (knowledge_base/units/*.json) │    │  │
│  │  │ وحدة معرفة خام — مرجع علمي/شرعي             │    │  │
│  │  │ text_original + text_simplified              │    │  │
│  │  └──────────────────────────────────────────────┘    │  │
│  │  × 1-10 units per lesson                            │  │
│  └───────────────────────────────────────────────────────┘  │
│  × 3-10 lessons per path                                   │
└─────────────────────────────────────────────────────────────┘

DAILY TIP (knowledge_base/curriculum/daily_tips/*.json) — مستقل
نصيحة مختصرة (≤ 280 حرف) مستخرجة من unit واحد، تظهر في الواجهة الرئيسية
```

| الطبقة | المفتاح | العدد/المسار | المدة | الاستخدام |
|--------|--------|---------------|-------|-----------|
| **Path** | `path_{age}_{domain}_{variant}` | — | ≤ 30 يوم | رحلة تربوية (3-10 دروس) |
| **Lesson** | `lesson_{path_slug}_{order}` | 3-10 | 3-15 دقيقة | درس واحد + try_this عملي |
| **Daily Tip** | `tip_{age}_{seq}` | 7+ pool لكل age | ≤ 280 حرف | عرض في الواجهة الرئيسية (rotating) |
| **Knowledge Unit** | UUID | 1-10 per lesson | — | مرجع خام في الـ RAG |

---

## 2. الـ enums (مرجعية من `taxonomy.py`)

| الحقل | القيم | المصدر |
|-------|-------|--------|
| `age_group` | `0-3`, `4-6`, `7-9`, `10-12`, `13-15`, `16-18` | `CANONICAL_AGE_GROUPS` |
| `domain` | `medical`, `cyber`, `islamic_parenting`, `development` | `CANONICAL_DOMAINS` |
| `severity` | `خفيف`, `متوسط`, `شديد`, `طارئ` | `CANONICAL_SEVERITIES` (في الـ units فقط) |
| `intervention_type` | `وقائي`, `إرشادي`, `علاجي`, `إحالة_لطبيب` | `CANONICAL_INTERVENTIONS` (في الـ units فقط) |
| `reference_type` | `DSM-5`, `كتاب_فقهي`, `حديث`, `كتاب_تربوي`, `تقرير_سيبراني`, `إرشاد_مهني`, `مقال_تنموي`, `تقرير_طبي`, `مقال_تربوي` | `CANONICAL_REFERENCE_TYPES` |

> **للـ paths/lessons/tips نستخدم 4 age groups (بدون `unspecified`) و 4 domains الأساسية فقط.** الـ `severity` و `intervention_type` خاصين بـ `knowledge_unit` فقط (تشخيص ربع).

---

## 3. القواعد المعمارية (Design Decisions)

### 3.1 ترتيب زمني صارم
- **Path**: ≤ 30 يوم. لو محتاجين أطول → انقسام لمسارين منفصلين (مثلاً: "تأسيس" 14 يوم + "تعميق" 14 يوم).
- **Lesson**: ≤ 15 دقيقة قراءة. الـ ZPD يقتضي تجزئة، فدرس طويل ينقسم لاثنين.
- **Daily Tip**: ≤ 280 حرف. Twitter-class — للقراءة في 5 ثوانٍ.

### 3.2 الربط بين الطبقات
- **Path.lesson_ids** = `[lesson_id_1, lesson_id_2, ...]` مرتبة.
- **Lesson.path_id** = path_id أب (1:1 reverse).
- **Lesson.unit_ids** = UUIDs لـ knowledge units (1-10).
- **DailyTip.unit_id** = UUID لـ knowledge unit واحد فقط.
- **DailyTip لا تتبع path** — مستقلة ومفلترة على age_group.

### 3.3 المعرفات (IDs)
- **Path**: `path_{age_group}_{domain_slug}_{variant}` — مثال: `path_4-6_islamic_parenting_bond`.
- **Lesson**: `lesson_{path_id_slug}_{order}` — مثال: `lesson_4-6_islamic_parenting_bond_01`.
- **DailyTip**: `tip_{age_group}_{seq}` — مثال: `tip_4-6_001` (الـ seq لكل age_group مستقل).

### 3.4 التوافق مع taxonomy
- `age_group` و `domain` في كل كائن **يجب** أن يطابق الـ parent (path → lesson). الـ integrity guard extension (مستقبلاً) سيتحقق آلياً.
- الـ `behavior_type` (string) في knowledge units حرّ — مثل "قلق", "عناد", "فرط حركة". الـ curriculum لا يُعرّف behavior_types منفصلة.

### 3.5 الإنذارات (warning_flags في lesson)
- `needs_professional_followup`: الدرس يستدعي متابعة مختص (طبيب أطفال / أخصائي نفسي / إلخ).
- `regional_fiqh_variation`: المضمون يختلف باختلاف المذهب/البلد. الواجهة تعرض "راجع مفتياً محلياً".
- `developmental_red_flag`: العلامة قد تكون red flag طبياً — يستوجب إحالة.

### 3.6 الـ Pedagogical Framework (path-level)
- `prophetic_7_7_7`: الافتراضي لـ islamic_parenting (7-7-7 gradualism).
- `ghazali_tazkiyah`: للتركيز على تزكية النفس (nafs stages).
- `attachment_rahma`: لـ 0-3 (Prophetic رحم + Bowlby attachment theory).
- `zpd_scaffolded`: لمنهج ZPD-heavy (skill trees in 7-9 / 10-12).

---

## 4. علاقتها بـ Knowledge Base والـ RAG

```
                        ┌──────────────────────┐
                        │ MOBILE_APP (Flutter) │
                        └──────────┬───────────┘
                                   │ GET /api/program/paths
                                   │ GET /api/program/lessons/:id
                                   │ GET /api/program/daily-tip
                                   ▼
                        ┌──────────────────────┐
                        │ BACKEND (FastAPI)    │
                        │ - routers/program.py │  ← Phase 2
                        │ - curriculum_loader  │  ← Phase 2
                        │ - retrieval (RAG)    │  ← موجود
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
   │ curriculum/     │  │ curriculum/     │  │ curriculum/     │
   │ paths/          │  │ lessons/        │  │ daily_tips/     │
   │  (رحلات)        │  │  (دروس)         │  │  (نصائح)        │
   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
            │ unit_ids           │ unit_ids          │ unit_id (1:1)
            ▼                    ▼                    ▼
                 ┌─────────────────────────────┐
                 │ units/*.json                │
                 │ (292 knowledge units)       │
                 │ RAG via ChromaDB ONNX       │
                 └─────────────────────────────┘
```

**في الـ Phase 2** (Backend layer) هنبني:
- `routers/program.py` بـ 3 endpoints: `GET /api/program/paths`, `GET /api/program/paths/{id}/lessons`, `GET /api/program/daily-tip`.
- `curriculum_loader.py` يحمّل JSON files عند الإقلاع.
- DB v4 يضيف `lesson_progress` و `child_profiles` لتتبع الإكمال.

**في الـ Phase 5** (Chat context awareness): الـ system prompt للـ assistant يحقن `path_id` و `lesson_id` الحاليين عشان إجابات الشات تكون متوافقة مع سياق المنهج.

---

## 5. مسارات النشر (Lifecycle)

| المرحلة | الحالة | المجلد |
|---------|--------|--------|
| Draft | `is_published: false` | يبقى في `curriculum/{paths,lessons,daily_tips}/` لكن endpoint يرجع 404 |
| Published | `is_published: true` | endpoint يرجع الكائن في الـ listing |
| Deprecated | `is_published: false` + `version` باقٍ | للرجوع التاريخي — الـ UI يعرض "نسخة سابقة" |

---

## 6. معايير القبول (Acceptance Criteria لكل Phase)

### Phase 1 (الحالية)
- [x] `curriculum/schema/*.json` (3 schemas) موجودين ومتوافقين مع taxonomy
- [x] `curriculum/schema.md` (هذا الملف) يوثّق الهيكل
- [x] مسار واحد كامل (بكل دروسه) موجود كـ JSON
- [x] pool نصائح لمرحلة عمرية واحدة (≥ 7 نصائح) موجود

### Phase 2 (لاحقة)
- [ ] `routers/program.py` بـ 3 endpoints تعمل
- [ ] `curriculum_loader.py` يحمّل عند startup
- [ ] `pytest` tests للـ endpoints

### Phase 3+ (لاحقة)
- [ ] 6 مسارات (واحد لكل age_group × islamic_parenting) على الأقل
- [ ] 30+ lesson إجمالي
- [ ] 50+ daily tip في الـ pool (متنوعة عبر domains)

---

## 7. مرجع سريع — مثال IDs من Phase 1

```
path_4-6_islamic_parenting_bond
├── lesson_4-6_islamic_parenting_bond_01   (بناء الثقة)
├── lesson_4-6_islamic_parenting_bond_02   (اللعب المعرفي)
└── lesson_4-6_islamic_parenting_bond_03   (الحوار مع الطفل)

tip_4-6_001 .. tip_4-6_007  (7 نصائح للـ pool)
```

الكائنات الفعلية في `paths/`, `lessons/`, `daily_tips/`.
