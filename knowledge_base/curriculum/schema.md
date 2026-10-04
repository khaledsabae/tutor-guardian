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

---

## 8. برامج الأسرة — `programs/`

ثلاثة برامج، كل برنامج **ملف واحد** بالعربية وترجمته بالبنية نفسها حرفًا بحرف:

| البرنامج | الملف العربي | الترجمة | المخطّط |
|---|---|---|---|
| «رمضان العائلة» — ٣٠ يومًا + العيد + ما بعده | `programs/ramadan_family.json` | `i18n/en/programs/ramadan_family.json` | `schema/program_ramadan_family.schema.json` |
| «رحلة الصلاة» — ٧–١٠ سنوات، ١٢ أسبوعًا | `programs/prayer_journey.json` | `i18n/en/programs/prayer_journey.json` | `schema/program_prayer_journey.schema.json` |
| المراحل الاستباقية — تنبيه قبل الموعد بشهر | `programs/milestones.json` | `i18n/en/programs/milestones.json` | `schema/program_milestones.schema.json` |

**التحميل:** `content_lang.localised(CURRICULUM / "programs", "<file>.json", lang)` يعيد الترجمة إن وُجدت وإلا العربي — نفس آلية الميثاق والمهام والرخصة. المخطّط يُختار بحقل `program_type` لا باسم المجلد (`check_curriculum_schema.py`).

### 8.1 قواعد مشتركة

- **ثابت ومترجَم.** المعرّفات والأرقام والتعدادات والمراجع (`id`, `key`, `day`, `until`, `addressed_to`, `unit_ids`, `story_id`, `surah/from/to`, `coins` …) متطابقة بين الملفين؛ النصوص وحدها تُترجَم. القائمة الكاملة في `INVARIANT_KEYS` داخل `ops/tools/check_programs.py`. مفتاح تعدادي جديد يجب أن يُضاف هناك، وإلا فشل فحص «العربي فيه عربية».
- **القرآن مراجع فقط.** `{"surah", "from", "to", "topic"?}` — التطبيق يعرض النص من `mobile/assets/data/quran.json`. لا نصّ آية في أي حقل، ولا ترجمة لها؛ `topic` اسم موضوع متداول («آيات الصيام») لا تفسير. للمستخدم الإنجليزي: الآية بالعربية، ومعناها — إن عُرض — من مصدر تفسير منشور (`tafsir_service`) معنونًا أنه تفسير.
- **الأحاديث في البطاقات فقط.** مصفوفة `evidence` في كل ملف: `{"id": "h_…", "kind": "hadith", "text_ar", "source": "صحيح البخاري — حديث ٦٣١", "provenance": {"book", "number"}, "context", "meaning"(الإنجليزي فقط)}`. اللفظ متصل كما في الصحيح، و«صلى الله عليه وسلم» حروفًا لا رمزًا (المطابقة بالهيكل الصامت). يفحصها `check_hadith_citations.py` في الملفين. العناصر تشير إليها بـ`evidence_ids`، والنص الحرّ يقول «الحديث المرفق» ولا يقتبس. **البرامج الحالية من البخاري وحده** — ترقيم مسلم في الفهرس يخالف الترقيم المتداول، فأُجّل حتى يُصلَح.
- **حديث خارج الصحيحين** (مثل «مروهم بالصلاة لسبع») يُوصَف ولا يُقتبس، وسنده وحدة معرفة نوع مرجعها `حديث` في `unit_ids`.
- **ذكر النبي ﷺ في نصّ حرّ** مسموح فقط في عنصر يحمل `evidence_ids` أو وحدة حديث — هكذا لا يُنسب إليه شيء بلا سند.
- **كل ملاحظة تربوية لها أصل:** `unit_ids` (وحدة واحدة على الأقل) من `knowledge_base/units/`.
- **القصص** معرّفات من `mobile/assets/data/stories.json` **ولها ترجمة** في `stories_en.json` (خمس قصص من ١٩ بلا ترجمة ولا تُستعمل).
- **ختم المراجعة:** `generation.approved_by = "auto-review:<models>+guards"` — مشروع فردي بلا مراجع بشري؛ الختم يوثّق النماذج المراجِعة (من عائلة غير عائلة الكاتب) والحرّاس.

### 8.2 «رمضان العائلة» — `program_type: ramadan_family`

```
season · bands(covered, band_map, text) · evidence[] · kickoff · fasting_ladder
days[30]: day · phase · key · title · family_challenge{title, steps[2-5], minutes≤15, cost, at_home, when, materials}
          parent_note{text, unit_ids, evidence_ids} · variants{0-3,4-6,7-9,10-12,13-15: {addressed_to, text}}
          quran{together, theme_ref, parent_juz} · story_id · last_ten · odd_night · may_not_occur · tracks[]
eid · after_ramadan{keep_habits, weeks[4], links} · recap · generation
```

- **مَن يرى ماذا (`band_map`):** نسخ الأيام لخمس فئات. `2-3` ← نسخة `0-3`، و`16-18` ← نسخة `13-15`، و`prenatal-1` ← لا نسخة طفل (التحدّي العائلي وملاحظته فقط). `0-3` و`4-6` موجَّهتان للوالد؛ `7-9` فما فوق للطفل وتصلح لوضع الطفل (المخاطَب مذكّر عام كبنك المهام).
- **الليلة تسبق نهارها.** ليلة ٢١ هي مساء اليوم ٢٠؛ فـ`odd_night = true` للأيام ٢٠، ٢٢، ٢٤، ٢٦، ٢٨ وحدها، ونشاطها مسائي. `last_ten` تقويمي (الأيام ٢١–٣٠). لا يُقال عن ليلة بعينها إنها ليلة القدر، ولا تُقسَّم العشر «رحمة/مغفرة/عتق».
- **اليوم ٣٠** `may_not_occur`؛ لا يُبنى عليه شيء: كلمة العائلة ووعدها في اليوم ٢٨، وتجهيز العيد في اليوم ٢٩.
- **الورد:** `together` سورة قصيرة تتكرّر يومين للحفظ؛ `theme_ref` مقطع يرتبط بموضوع اليوم أو `null`؛ `parent_juz` = رقم اليوم (ختمة اختيارية للوالدين). حدود الأجزاء في `JUZ_STARTS` بالمدقّق، ويتحقّق أن كل بداية تقع على علامة ۞ في المصحف المعروض.
- **سلّم الصيام** (`fasting_ladder.bands`): `fasts ∈ no | partial | partial_to_full | full_supported`؛ كل درجة `{key, label, until ∈ none|mid_morning|dhuhr|asr|maghrib, approx_hours, min_age_years, max_days_per_week?, advance_when, text}`. المدقّق يفرض: لا إمساك تحت السابعة (`until=none` و`approx_hours=0` لـ0-3 و4-6)، ولا يوم كامل لـ7-9، والدرجات متصاعدة. ومعها `doctor_first` و`stop_signs` و`stop_action` و`urgent_signs`.
- **البطاقة «رمضان عائلتنا»** (`recap`): كل مقياس `{key, source, label, max, choices?}`؛ `source` هو ما يسجّله التطبيق: `challenge_done`/`wird_done`/`story_heard`/`juz_read` علامة «تمّ» من بطاقة اليوم، و`night_joined` في أمسيات الأيام ٢٠–٢٨، و`fasting_step_up` من شاشة السلّم في أي يوم، و`family_word` اختيار من `choices` في اليوم ٢٨. القوالب تستعمل `{key}` و`{hijri_year}` و`{app_link}`، ويُحذف السطر الذي قيمته دون `min_to_show`. **الخصوصية ثابتة في المخطّط:** لا أسماء ولا أعمار ولا صور ولا نصّ حرّ.

### 8.3 «رحلة الصلاة» — `program_type: prayer_journey`

```
age{7,10,12 أسبوعًا} · bands(covered, band_map → preparation|journey|ownership|null, text) · entry_rules[]
basis{text, unit_ids, evidence_ids} · principles[] · reward_policy{text, daily_cap: 60, unit_ids} · evidence[]
preparation (دون السابعة) · stages[6]{stage, key, week_from, week_to, title, goal, parent_assignments[], child_tasks[],
          confirmation{how, counts_when}, encouragement[], if_struggling, covenant{coins_target, examples[]},
          unit_ids, evidence_ids, lesson_ids, quran[], journey_milestone_key}
graduation{…, journey_milestone_keys, covenant} · ownership (١٠ فما فوق) · generation
```

- **مهام الطفل بشكل بنك المهام** لتمرّ بدورة claim/confirm الموجودة (`child_missions`): `id → id`، `title → title_ar`، `instruction → instruction_ar`؛ ومعها `per_week` (هدف لا شرط) و`coins`. لا تخضع لعتبة الـ١٥ دقيقة — تلك لمهام «خارج الشاشة».
- **العملات تتناقص** مرحلةً بعد مرحلة (المدقّق يرفض الزيادة)، ومجموع عملات اليوم الأقصى ≤ `CoinsService.dailyEarnCap` (٦٠). العهد (`covenant`) يحوّلها مكافأة حقيقية. **لا عقاب ولا ضرب ولا تعيير** — موقف التطبيق، والوحدات التي تقول بالضرب مستبعدة من الإسناد.
- **مَن يرى ماذا:** بالعمر إن عُرف (`entry_rules`)، وإلا بالفئة (`band_map`): `4-6` ← تهيئة، `7-9` ← الرحلة، `10-12` ← الرحلة (ابن العاشرة) أو «صلاتي مسؤوليتي»، `13-15` ← «صلاتي مسؤوليتي»؛ ودون الرابعة وفوق الخامسة عشرة لا يظهر البرنامج.

### 8.4 المراحل الاستباقية — `program_type: milestones`

```
alert_policy{default_days_before: 30, max_alerts_per_child_per_month, text} · evidence[]
milestones[]: key · order · trigger{type: age|season_age, age_months, alert_days_before, season?, min/max_age_months?, band_fallback[]}
              audience{gender: any|female|male, if_gender_unknown: show|ask} · medical · title · alert{title≤50, body≤160}
              cards[3-5]{title, body} · red_flags[] (إلزامي إن medical) · unit_ids · evidence_ids · quran[] · links{program_ids, path_ids, lesson_ids, story_ids, features}
```

- **🚨 اعتماد على حقل غير موجود بعد:** التوقيت بالأشهر من الميلاد (`age_months − alert_days_before`)، و`child_profiles` اليوم فيه `age_group` و`gender` ولا تاريخ ميلاد. **وكيل الربط سيضيف شهر ميلاد اختياريًا للطفل.** إلى أن يوجد: لا إشعار؛ تظهر البطاقة في مكتبة الوالد لطفل في إحدى فئات `band_fallback`.
- `season_age`: يُطلق قبل رمضان بـ`alert_days_before` لكل طفل عمره عند بداية الموسم بين `min_age_months` و`max_age_months`.
- المراحل الخاصة بجنس (`female`/`male`) لا تُرسل قبل أن يُعرف جنس الطفل (`if_gender_unknown: ask`): يُعرض طلب إكمال الملف بدلًا منها.
- إن تزامنت مرحلتان لطفل واحد يُرسل الأصغر `order` ويؤجَّل الآخر (`max_alerts_per_child_per_month`).

### 8.5 الفحص

| الفحص | ماذا يسأل |
|---|---|
| `check_curriculum_schema.py` | الملفان يطابقان مخطّط نوعهما (`program_type`) |
| `check_programs.py` | المراجع موجودة (وحدات، قصص بلغتين، دروس، مسارات، آيات في حدودها، بطاقات أحاديث) · تطابق بنية اللغتين · لا قرآن مقتبس في النص الحرّ (مقارنة بكل المصحف بالهيكل الصامت، خمس كلمات) · لا حديث مقتبس خارج بطاقته · لا «قال النبي/رواه» · ذكر النبي ﷺ بسند · لا عامية · لا CJK · قيود كل برنامج (الصيام، الليالي الوترية، العملات، المراحل) |
| `check_hadith_citations.py` | بطاقات الأحاديث تطابق الصحيحين لفظًا ورقمًا |

الثلاثة على `.githooks/pre-commit`، ولكل منها self-tests توقفه بـ`exit 2` إن تعطّل. والتستات في `backend/tests/test_program_banks.py`.
