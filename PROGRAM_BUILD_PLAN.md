# PROGRAM_BUILD_PLAN.md — خطة تحويل Tutor Guardian من Chatbot إلى برنامج تربوي متكامل

> **المصدر الأوحد للحقيقة** لمراحل التطوير القادمة.  
> **سياسة العقد:** الباك إند ثابت كعقد v1؛ أي إضافة endpoints تكون additive فقط — راجع `MOBILE_API.md`.

---

## القسم أ — الوضع الحالي الدقيق (Baseline)

### البنية التحتية الشغّالة

| المكوّن | التفاصيل |
|---------|----------|
| API Gateway | `tg-api.alsaba.cloud` عبر Cloudflare Tunnel (لا nginx مباشر) |
| CI/CD | GitHub Actions — push على `main` يُطلق الـ pipeline |
| APK/AAB | AAB موقّع 53MB — جاهز للرفع، Play قيد مراجعة الهوية |
| الـ Backend (local) | FastAPI على port 8090 |
| الـ Backend (docker) | FastAPI على port 8000 |
| Tailscale Ollama | `100.109.163.64:11434` |

### النماذج

| الدور | النموذج |
|-------|---------|
| Primary (local) | `qwen2.5:3b` |
| Fallback (local) | `gemma4:e4b` |
| docker-compose default | `gemma4:e4b-it-qat` |
| Cloud (.env.example) | `kimi-k2.6:cloud` / `gemma4:31b-cloud` |

### قاعدة المعرفة

- **292 وحدة** موزّعة تحت `knowledge_base/units/*.json`
- حقول كل وحدة: `id`, `age_group`, `domain`, `text_simplified`, `reference_info`, `behavior_keywords`, `severity_hint`
- يتحقق منها `check_kb_integrity.py` عند كل push

### عقد الـ API

راجع `MOBILE_API.md` كمصدر الحقيقة الوحيد.  
**Enums ثابتة (لا تكرّر، استورد من `backend/app/middleware/taxonomy.py`):**

```
age_group : 0-3 | 4-6 | 7-9 | 10-12 | 13-15 | 16-18
domain    : medical | cyber | islamic_parenting | development
severity  : خفيف | متوسط | شديد | طارئ  ← قيم عربية حرفية على السلك
```

---

## القسم ب — التشخيص: chatbot-first → program-first

| ما اتبنى ✅ | ما ينقص ❌ |
|------------|-----------|
| شاتبوت عربي streaming كامل | واجهة برنامج تربوي (paths/lessons) |
| Safety banners + escalation | ملف الطفل (child profile) |
| 292 وحدة KB منظّمة | منهج مرتّب (curriculum layer) |
| SSE + session management | تتبع التقدّم (progress tracking) |
| RAG عربي + fallback models | نصيحة اليوم (daily tip) |
| CI/CD + Docker + Cloudflare | Onboarding flow |
| AAB موقّع جاهز | Deep-link من الدرس للشات |

**البشرى:** أصعب جزء (الـ AI + الشاتبوت + الـ infra) خلص. الناقص = طبقة محتوى وتجربة — أسهل بكثير.

---

## القسم ج — الفرضية المبدئية لهيكل البرنامج

> نقطة بداية تتأكد/تتعدّل بعد أبحاث القسم د.

- **محور التنظيم:** الطفل (المرحلة العمرية `age_group`) أساسي — الموضوع/الـ domain ثانوي
- **v1 target:** الأب هو المتعلّم — واجهة الطفل المستقلة مؤجّلة لـ v2

### اللبنات السبع

1. **Onboarding** → إنشاء ملف الطفل: `name` / `birth_year → age_group` / `gender`
2. **الرئيسية (Home):** نصيحة اليوم + تقدّم المسار الحالي + زر «اسأل المربي»
3. **المسارات (Paths):** مناهج مرتّبة — أساسية بالمرحلة العمرية، كل درس موسوم بـ domain
4. **الدرس (Lesson):** محتوى منسَّق من وحدات الـ KB (تستخدم الحقول الموجودة: `age_group`/`domain`/`text_simplified`/`reference_info`) + خلاصة + «جرّب ده» + زر «اسأل»
5. **التقدّم والإنجازات:** streak + إنجازات بصياغة قيمية (لا تنافسية)
6. **المساعد «اسأل المربي»:** الشاتبوت الموجود مُعاد توضيعه — يستقبل `context` من الدرس/الطفل (`domain`/`age_group`/`behavior_type`)
7. **واجهة الطفل:** مؤجّلة لـ v2

---

## القسم د — خارطة الأبحاث (4 برومبتات متوازية)

> كل برومبت = مهمة لوكيل بحث عميق مستقل.  
> الأبحاث **لا تحجب** التنفيذ — شغّل Phase 0 و Phase 1 بالتوازي معها.  
> اجمع التقارير في `docs/research/`.

---

### بحث 1 — التربية والمحتوى

```
أنت باحث متخصص في التربية الإسلامية وعلم النفس التنموي.

السياق: نبني تطبيق "Tutor Guardian" — برنامج تربوي للآباء العرب المسلمين.
لدينا 292 وحدة معرفية منظّمة بحقول: age_group (0-3, 4-6, 7-9, 10-12, 13-15, 16-18),
domain (medical, cyber, islamic_parenting, development), text_simplified, reference_info.

المطلوب — ابحث وأخرج:
1. نظريات التربية الإسلامية المعاصرة الأكثر استخداماً في التطبيقات التفاعلية
2. نظريات علم النفس التنموي المرتبطة بكل مرحلة عمرية (Piaget, Vygotsky, وغيرهم)
3. المصادر الأولية المقترحة لكل domain × age_group (كتب، بحوث، مناهج رسمية)
4. أكثر 20 موضوعاً تربوياً بحثاً من الآباء العرب (Google Trends, منتديات, etc.)

المخرَج المطلوب: ملف `docs/research/01_content_pedagogy.md` يحتوي:
- خارطة محتوى منهجي (domain × age_group matrix)
- قائمة مصادر مرجعية موثّقة
- اقتراح أولويات الوحدات التي تُحوَّل لدروس أولاً
```

---

### بحث 2 — السوق والاقتصاد

```
أنت محلل سوق متخصص في تطبيقات التعليم والتربية في العالم العربي.

السياق: تطبيق "Tutor Guardian" — مساعد تربوي ذكي للآباء المسلمين، يعمل محلياً
100% (لا بيانات تخرج)، باللغة العربية، مع AI محلي (Ollama/qwen2.5).
الأسواق المستهدفة: السعودية، مصر، الخليج، شمال أفريقيا.

المطلوب — ابحث وأخرج:
1. المنافسون المباشرون (تطبيقات تربية الأطفال العربية/الإسلامية) + نقاط قوتهم وضعفهم
2. حجم سوق parenting apps العربي 2024-2026 + معدلات النمو
3. نماذج الإيراد الأنجح في هذا القطاع (freemium / subscription / one-time)
4. عوامل الثقة الأهم عند الآباء العرب عند اختيار تطبيق تربوي

المخرَج المطلوب: ملف `docs/research/02_market_economics.md` يحتوي:
- تموضع تنافسي مقترح (positioning statement)
- نموذج أعمال مقترح مع أرقام مرجعية
- top 3 فرص غير محتلة في السوق
```

---

### بحث 3 — تجربة المستخدم UX

```
أنت مصمم UX متخصص في تطبيقات عربية وإسلامية للمحتوى التعليمي.

السياق: نبني واجهة Flutter عربية RTL لـ"Tutor Guardian". الآب هو المستخدم الأساسي.
التدفق الحالي المتوقع: Onboarding (ملف الطفل) → Home (نصيحة + مسار) → قائمة مسارات
→ تفاصيل مسار → عرض درس → فتح شات بـcontext → شاشة الحساب.
الثيم الحالي: teal #1A5F7A، Riverpod للـstate، Arabic RTL.

المطلوب — ابحث وأخرج:
1. أفضل ممارسات onboarding للتطبيقات العائلية العربية (عدد الخطوات، نوع الأسئلة)
2. هياكل navigation الأنسب لـ parenting apps (bottom nav vs drawer vs tabs)
3. Gamification يتوافق مع القيم الإسلامية (بدائل للـleaderboards التنافسية)
4. اعتبارات تصميم RTL العربي في Flutter (typography, layout, iconography)

المخرَج المطلوب: ملف `docs/research/03_ux_design.md` يحتوي:
- توصيات UX مرقّمة + مبررات
- wireframe flows مقترحة (نصية أو ASCII)
- قائمة مكتبات Flutter المقترحة مع أسباب الاختيار
```

---

### بحث 4 — التقنية والـ AI

```
أنت مهندس AI/ML متخصص في النماذج العربية ونشرها على hardware محدود.

السياق: Tutor Guardian يعمل على:
- Backend: FastAPI + SQLite + Ollama local
- Primary model: qwen2.5:3b | Fallback: gemma4:e4b
- Tailscale home server: 100.109.163.64:11434
- Mobile: Flutter Android (v1) + iOS (v2)
- لا بيانات تخرج — خصوصية 100% محلية

المطلوب — ابحث وأخرج:
1. مقارنة النماذج العربية القابلة للتشغيل على 8-16GB RAM: qwen2.5:3b, gemma4, phi-4, etc.
   (جودة الإجابة التربوية، سرعة inference، حجم الموديل)
2. تحسينات RAG العربي: chunking strategies، embedding models للعربية، reranking
3. Personalization بدون بيانات خارجية: كيف نشخصن الـcontext بـ(age_group, domain, progress)
   فقط دون أي tracking خارجي
4. Scalability: كيف نتحول من Ollama local لـcloud inference وقت الحاجة دون كسر العقد

المخرَج المطلوب: ملف `docs/research/04_ai_technical.md` يحتوي:
- جدول مقارنة النماذج مع أرقام قياسية (benchmarks)
- توصيات RAG مع أمثلة كود
- معمارية personalization مقترحة
- خطة migration للـcloud مع الحفاظ على privacy
```

---

## القسم هـ — خطة التنفيذ بالمراحل

> كل مرحلة لها **بوابة تحقق** — الوكيل لا ينتقل للتالية قبل اجتيازها.

---

### Phase R — أبحاث (متوازية، لا تحجب)

**الإجراء:** شغّل الـ4 برومبتات في القسم د، اجمع التقارير في `docs/research/`.  
**التوازي:** يمكن بدء Phase 0 و Phase 1 فوراً دون انتظار الأبحاث.

---

### Phase 0 — مكاسب سريعة ✅ (بعضها يُنجز يدوياً)

**الإجراءات:**
```bash
# 1. تنظيف الملفات الفارغة
find . -name ".hermes-tmp.*" -delete

# 2. التحقق من توليد الـdataset
python backend/app/knowledge_loader.py --verify
```

**الملفات المطلوب إنشاؤها:**
- `docs/privacy-policy.md` — قالب سياسة الخصوصية (القالب في القسم ملحق-1 أدناه)
- استضافة `privacy-policy.md` على `tg-api.alsaba.cloud/privacy-policy` (مطلوبة للـ Play)

**بوابة التحقق:**  
☐ لا يوجد `.hermes-tmp.*`  
☐ `https://tg-api.alsaba.cloud/privacy-policy` يرجع 200  
☐ `python check_kb_integrity.py` ينتهي بلا أخطاء

---

### Phase 1 — حسم نموذج المحتوى

**الإجراءات:**
1. ثبّت الـ schema النهائي للمنهج (JSON) بناءً على الفرضية + نتائج بحث 1
2. أنشئ `knowledge_base/curriculum/schema.md` يوثّق الهيكل

**Schema المقترح (نقطة بداية):**

```json
// knowledge_base/curriculum/paths/{path_id}.json
{
  "id": "path_islamic_parenting_4-6",
  "title": "تربية الطفل من 4 إلى 6 سنوات",
  "age_group": "4-6",
  "domain": "islamic_parenting",
  "description": "...",
  "lesson_ids": ["lesson_001", "lesson_002"],
  "estimated_days": 14
}

// knowledge_base/curriculum/lessons/{lesson_id}.json
{
  "id": "lesson_001",
  "path_id": "path_islamic_parenting_4-6",
  "title": "بناء الثقة عند الطفل",
  "age_group": "4-6",
  "domain": "islamic_parenting",
  "unit_ids": ["unit_045", "unit_112"],
  "summary": "...",
  "try_this": "جرّب هذا الأسبوع: ...",
  "order": 1
}

// knowledge_base/curriculum/daily_tips/{tip_id}.json
{
  "id": "tip_4-6_001",
  "age_group": "4-6",
  "domain": "development",
  "text": "نصيحة اليوم: ...",
  "unit_id": "unit_023"
}
```

**بوابة التحقق:**  
☐ `knowledge_base/curriculum/schema.md` موجود ومعتمد  
☐ مسار واحد كامل (بكل دروسه) موجود كـ JSON  
☐ pool نصائح لمرحلة عمرية واحدة (≥7 نصائح) موجود

---

### Phase 2 — Backend: طبقة المحتوى

**الملفات الجديدة:**

```
backend/app/
├── routers/
│   └── program.py          ← router جديد
├── db/
│   └── init_db.py          ← رفع SCHEMA_VERSION من 3 → 4
└── curriculum_loader.py    ← يحمّل JSON files عند الإقلاع
```

**DB v4 — جداول جديدة (أضف لـ `init_db.py`):**

```sql
-- SCHEMA_VERSION = 4
CREATE TABLE IF NOT EXISTS child_profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    age_group   TEXT NOT NULL,  -- enum من taxonomy
    gender      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lesson_progress (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL,
    lesson_id    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'not_started',  -- not_started | in_progress | completed
    completed_at TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(device_id, lesson_id)
);
```

**Endpoints الجديدة (`/api` prefix، v1 additive):**

```
GET  /api/program/paths?age_group={age_group}
GET  /api/program/paths/{id}
GET  /api/program/lessons/{id}
GET  /api/program/daily-tip?age_group={age_group}
POST /api/program/progress          ← Bearer (device_id)
GET  /api/program/progress?lesson_id={id}  ← Bearer
POST /api/program/children          ← Bearer
GET  /api/program/children          ← Bearer
```

**قواعد التنفيذ:**
- أعد استخدام `get_conn()` من `db/init_db.py` — لا تنشئ connection جديد
- أعد استخدام `middleware/auth.py` (Bearer token) — لا تكتب auth من الصفر
- استورد الـenums من `middleware/taxonomy.py` — لا تكرّرها
- سجّل الـrouter في `main.py`: `app.include_router(program_router, prefix="/api")`
- اتبع نمط `routers/assistant.py` في الهيكل

**بوابة التحقق:**  
☐ `GET /api/program/paths?age_group=4-6` يرجع قائمة مسارات  
☐ `GET /api/program/daily-tip?age_group=4-6` يرجع نصيحة  
☐ `POST /api/program/progress` بـ Bearer يحفظ، `GET` يسترجع  
☐ `pytest` أخضر  
☐ `check_kb_integrity.py` يعدّي

---

### Phase 3 — تأليف منهج بذرة

**الهدف:** التطبيق لا يفتح فارغاً.

**المطلوب:**
- مسار كامل لمرحلة عمرية واحدة (مقترح: `4-6` أو `7-9`) — 5-7 دروس
- كل درس يستخدم 2-3 وحدات من الـ292 وحدة الموجودة
- pool نصائح يومية: 30 نصيحة موزّعة على الـdomains للمرحلة المختارة

**الأداة:** سكريبت `scripts/seed_curriculum.py` يولّد الـ JSON files تلقائياً من وحدات الـ KB

**بوابة التحقق:**  
☐ مسار واحد كامل قابل للتشغيل في التطبيق  
☐ 30 نصيحة يومية موجودة  
☐ الـ API يرجع البيانات صحيحة

---

### Phase 4 — Flutter: واجهة البرنامج

**الملفات الجديدة تحت `mobile/lib/`:**

```
screens/
├── onboarding_screen.dart     ← اسم الطفل + تاريخ الميلاد → age_group + جنس
├── home_screen.dart           ← نصيحة اليوم + تقدّم المسار + زر «اسأل»
├── paths_screen.dart          ← قائمة المسارات المتاحة للطفل
├── path_detail_screen.dart    ← دروس المسار + مؤشر التقدّم
└── lesson_screen.dart         ← محتوى الدرس + «جرّب ده» + زر «اسأل المربي»

state/
├── program_notifier.dart      ← Riverpod — paths/lessons/daily-tip
└── child_profile_notifier.dart ← Riverpod — child profile + auth device_id

models/
├── path_model.dart
├── lesson_model.dart
├── daily_tip_model.dart
└── child_profile_model.dart
```

**Bottom Navigation (4 تبويبات):**
```
الرئيسية | المسارات | المساعد | حسابي
   🏠         📚         💬        👤
```

**قواعد التنفيذ:**
- أعد استخدام `theme/app_theme.dart` (teal #1A5F7A) — لا تعرّف ألواناً جديدة
- أعد استخدام `widgets/safety_banner.dart` — لا تعيد كتابته
- أعد استخدام `models/enums.dart` — استورد الـenums
- `chat_screen.dart` يبقى كما هو كتبويب «المساعد»
- استخدم `flutter_secure_storage` لـ `device_id`
- كل النصوص عربية RTL — `textDirection: TextDirection.rtl`
- أضف دوال البرنامج الجديدة لـ `api/tg_client.dart` (لا تنشئ client جديد)

**بوابة التحقق:**  
☐ Onboarding يُكمل ويحفظ ملف الطفل  
☐ Home يعرض نصيحة اليوم + مسار  
☐ فتح درس يعمل  
☐ الشات القديم لا يزال يعمل من تبويب المساعد  
☐ `flutter build apk --debug` ينجح

---

### Phase 5 — دمج الشات سياقياً

**الهدف:** زر «اسأل المربي» في الدرس يفتح الشات بـ context مُعبّأ.

**الـ Deep-link:**
```dart
// في lesson_screen.dart
Navigator.pushNamed(
  context,
  '/chat',
  arguments: ChatContext(
    domain: lesson.domain,           // e.g. "islamic_parenting"
    ageGroup: child.ageGroup,        // e.g. "4-6"
    lessonTitle: lesson.title,
    behaviorType: lesson.domain,     // يُستخدم كـ behavior_type في الـ API
  ),
);
```

**في `POST /api/assistant/stream`:**
```json
{
  "age_group": "4-6",
  "severity": "خفيف",
  "behavior_type": "islamic_parenting",
  "message_text": "سؤال المستخدم هنا",
  "session_id": "uuid",
  "lesson_context": "بناء الثقة عند الطفل"
}
```

> ملاحظة: `lesson_context` حقل جديد additive — الـ backend يتجاهله إن لم يتعرّف عليه (backward compatible).  
> إن أردت استخدامه في الـ system prompt، أضف الـ endpoint كـ additive بدون كسر العقد.

**بوابة التحقق:**  
☐ فتح الدرس → «اسأل» → الشات يفتح بـ context صحيح  
☐ الـ context يظهر في الـ system prompt (يمكن التحقق من logs)  
☐ الشات المباشر (بدون context) لا يزال يعمل

---

### Phase 6 — صقل + بيتا

**الإجراءات:**
1. **Streak:** احسب من `lesson_progress.completed_at` — لا تحتاج جدول إضافي
2. **إنجازات:** JSON file بسيط `knowledge_base/curriculum/achievements.json`
3. **Local Notifications:** مكتبة `flutter_local_notifications` — تذكير يومي بالنصيحة
4. **إعادة بناء AAB موقّع:**
   ```bash
   cd mobile
   flutter build appbundle --release
   # sign with existing keystore
   ```
5. **Internal Testing:** رفع AAB لـ Play Console → Internal Testing track

**بوابة التحقق:**  
☐ Streak يحسب صحيح  
☐ `pytest` أخضر كامل  
☐ `check_kb_integrity.py` يعدّي  
☐ AAB يُبنى موقّعاً  
☐ لا كسر لعقد `MOBILE_API.md` v1  
☐ تشغيل `MOBILE_API.md` §7 Client Flow يعمل end-to-end

---

## القسم و — تصميم Backend طبقة المحتوى (مرجع تفصيلي)

### هيكل الملفات

```
knowledge_base/
└── curriculum/
    ├── schema.md           ← توثيق الـ schema
    ├── paths/
    │   └── *.json          ← مسار لكل age_group × domain
    ├── lessons/
    │   └── *.json          ← دروس تستخدم unit_ids من الـ KB
    ├── daily_tips/
    │   └── *.json          ← نصائح يومية
    └── achievements.json   ← إنجازات (Phase 6)

backend/app/
├── curriculum_loader.py    ← يحمّل JSON عند الإقلاع (مثل knowledge_loader.py)
├── routers/
│   └── program.py          ← endpoints جديدة
└── db/
    └── init_db.py          ← SCHEMA_VERSION 3→4 + جداول جديدة
```

### نمط الـ Migration (اتبع النمط الموجود)

```python
# في init_db.py — أضف داخل الـ migration chain الموجود
if current_version < 4:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS child_profiles (...)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lesson_progress (...)
    """)
    conn.execute("PRAGMA user_version = 4")
```

---

## القسم ز — تصميم Mobile طبقة البرنامج (مرجع تفصيلي)

### الـ State Management (Riverpod)

```dart
// child_profile_notifier.dart
@riverpod
class ChildProfileNotifier extends _$ChildProfileNotifier {
  @override
  Future<ChildProfile?> build() async {
    // load from secure storage
  }
  Future<void> saveChild(ChildProfile child) async { ... }
}

// program_notifier.dart
@riverpod
Future<List<ProgramPath>> programPaths(
  ProgramPathsRef ref,
  String ageGroup,
) async {
  final client = ref.watch(tgClientProvider);
  return client.getProgramPaths(ageGroup);
}
```

### توسعة `tg_client.dart`

```dart
// أضف هذه الدوال للـ TgClient الموجود:
Future<List<ProgramPath>> getProgramPaths(String ageGroup);
Future<ProgramPath> getProgramPath(String pathId);
Future<Lesson> getLesson(String lessonId);
Future<DailyTip> getDailyTip(String ageGroup);
Future<void> saveProgress(String lessonId, String status);
Future<List<LessonProgress>> getProgress();
Future<ChildProfile> saveChild(ChildProfile child);
Future<List<ChildProfile>> getChildren();
```

---

## القسم ح — المرجع التقني (للوكيل الجديد، مكتفٍ بذاته)

### متغيرات البيئة الحرجة

```env
OLLAMA_BASE_URL=http://100.109.163.64:11434   # Tailscale home server
OLLAMA_MODEL=qwen2.5:3b                       # primary
OLLAMA_FALLBACK_MODEL=gemma4:e4b              # fallback
SECRET_KEY=<generate with: openssl rand -hex 32>
CONVERSATIONS_DB=./data/conversations.db
REDIS_URL=redis://localhost:6379              # اختياري — rate limiting
```

### أوامر التشغيل

```bash
# Local development
cd backend && uvicorn app.main:app --port 8090 --reload

# Docker
docker-compose up -d

# Production (Cloudflare Tunnel)
# tg-api.alsaba.cloud → localhost:8000 (docker)

# Tests
cd backend && pytest

# KB Integrity
python check_kb_integrity.py

# Flutter Debug
cd mobile && flutter run

# Flutter Release AAB
cd mobile && flutter build appbundle --release
```

### Git Workflow

```bash
# Push مباشر على main — CI/CD يُطلق تلقائياً
git add .
git commit -m "feat: ..."
git push origin main
```

### مسارات الملفات الحرجة

```
backend/app/main.py                    ← نقطة دخول FastAPI
backend/app/db/init_db.py              ← DB schema + migrations
backend/app/middleware/taxonomy.py     ← Enums الثابتة
backend/app/routers/assistant.py       ← مرجع نمط الـ router
mobile/lib/api/tg_client.dart          ← HTTP client
mobile/lib/theme/app_theme.dart        ← teal #1A5F7A
mobile/lib/models/enums.dart           ← Enums Flutter
MOBILE_API.md                          ← عقد API (مصدر الحقيقة)
```

---

## القسم ط — Progress Log

| التاريخ | المرحلة | الحالة | ملاحظة |
|---------|---------|--------|--------|
| 2026-06-08 | الخطة | ✅ مكتوبة | `PROGRAM_BUILD_PLAN.md` أُنشئ |
| 2026-06-08 | Phase R — الأبحاث | ✅ مكتملة | 4 مواضيع × 3 أبحاث في `docs/research/{01..04}/`. هيكلة كاملة: r1=primary, r2=secondary, r3=draft/extra. `.docx` اتحوّلت لـ `.md`. `docs/research/README.md` فيه الفهرس |
| 2026-06-08 | Phase 0 — مكاسب سريعة | ✅ مكتملة | تنظيف 6 ملفات `.hermes-tmp.*`. `docs/privacy-policy.md` (عربي+EN). `backend/app/routers/privacy.py` يقدّمها على `GET /privacy-policy` (public, no /api prefix). Live test: 200/text-markdown. `check_kb_integrity.py`: 292 units in sync. **Production fixed**: Dockerfile COPY docs/ + remove inline comment; tg-api.alsaba.cloud/privacy-policy → HTTP 200 + body 1107 bytes (verified post-deploy). |
| 2026-06-08 | Phase 1 — حسم نموذج المحتوى | ✅ مكتملة | `knowledge_base/curriculum/`: 3 schemas (path/lesson/daily_tip) + schema.md. مثال: 1 path × 3 lessons × 7 daily_tips للمرحلة 4-6 (path_4-6_islamic_parenting_bond). All 11 data files validate (0 errors). Cross-ref check: 0 errors, 0 warnings. KB integrity: 292 units unchanged. |
| 2026-06-08 | Phase 2 — Backend: طبقة المحتوى | ✅ مكتملة | `curriculum_loader.py` + `routers/program.py` بـ 4 endpoints (paths list/detail, lesson detail, daily-tip). DB v4: child_profiles + lesson_progress tables (idempotent). `test_program.py`: 19/19 pass. Full suite: 44/44 green. Endpoints public (read-only). Mutating endpoints (POST progress) deferred per user instruction. |

> **الوكيل:** حدّث هذا الجدول بعد إنجاز كل مرحلة.

---

## القسم ي — برومبت التسليم للوكيل البرمجي

```
أنت وكيل برمجي يعمل على مشروع Tutor Guardian.

**أولاً: اقرأ هذه الملفات قبل أي شيء:**
1. `PROGRAM_BUILD_PLAN.md` — الخطة الكاملة (أنت فيه الآن)
2. `MOBILE_API.md` — عقد API v1 (مصدر الحقيقة للـ endpoints)
3. `backend/app/middleware/taxonomy.py` — الـ enums الثابتة
4. `backend/app/db/init_db.py` — نمط الـ DB والـ migrations
5. `backend/app/routers/assistant.py` — نمط الـ router

**ثانياً: نفّذ مرحلة مرحلة بهذا الترتيب:**
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

**بعد كل مرحلة:**
- شغّل بوابة التحقق الخاصة بها
- حدّث جدول Progress Log في هذا الملف
- اعمل `git push origin main`

**قواعد صارمة:**
1. **اللغة:** العربية في كل النصوص والتعليقات والـ commit messages — لا إنجليزي إلا في الكود
2. **RTL:** كل شاشة Flutter تستخدم `textDirection: TextDirection.rtl`
3. **Enums:** استخدم الـ enums حرفياً كما في `taxonomy.py` و `MOBILE_API.md` — لا تعرّف قيماً جديدة
4. **العقد:** الباك إند عقد ثابت — أي endpoint جديد يكون additive تحت `/api` بلا كسر للموجود
5. **إذا احتجت تغيير في عقد الـ API:** قف وأخبر المستخدم — لا تكسر `MOBILE_API.md` v1
6. **لا تكرّر:** استورد بدل أن تنسخ (auth، enums، theme، get_conn)
7. **اختبارات:** لكل router جديد اكتب test في `backend/tests/`

**تحقق نهائي end-to-end:**
1. `GET /api/program/paths?age_group=4-6` → يرجع مسارات
2. `GET /api/program/daily-tip?age_group=4-6` → يرجع نصيحة
3. `POST /api/program/progress` بـ Bearer → يحفظ، `GET` يسترجع
4. Flutter: Onboarding → Home (نصيحة + مسار) → درس → «اسأل» (شات بـcontext)
5. الشات القديم streaming + safety banners لا يزال يعمل من تبويب المساعد
6. `pytest` أخضر | `check_kb_integrity.py` يعدّي | `flutter build appbundle` ينجح
7. لا كسر لعقد `MOBILE_API.md` v1
```

---

## ملحق 1 — قالب سياسة الخصوصية (`docs/privacy-policy.md`)

```markdown
# سياسة الخصوصية — Tutor Guardian
**آخر تحديث:** 2026-06-08

## عربي

### المعلومات التي نجمعها
لا نجمع أي معلومات شخصية. جميع البيانات تُخزَّن محلياً على جهازك فقط.

### كيف تعمل التطبيق
- جميع الاستفسارات والإجابات تُعالَج على خادم خاص ولا تُرسَل لأي طرف ثالث
- لا نشارك أي بيانات مع أطراف خارجية
- لا نستخدم أي أدوات تتبع أو تحليل

### تواصل معنا
للاستفسارات: support@alsaba.cloud

---

# Privacy Policy — Tutor Guardian
**Last Updated:** 2026-06-08

## English

### Information We Collect
We do not collect any personal information. All data is stored locally on your device only.

### How the App Works
- All queries and responses are processed on a private server and are not sent to any third party
- We do not share any data with external parties
- We do not use any tracking or analytics tools

### Contact Us
For inquiries: support@alsaba.cloud
```

---

*هذا الملف يُدار من قِبَل مدير المشروع + يُحدَّث من الوكيل البرمجي بعد كل مرحلة.*
