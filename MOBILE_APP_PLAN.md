# Tutor Guardian — Mobile App Build Plan (Flutter / Android-first)

> **هذا الملف هو لوحة المتابعة.** الوكيل المنفّذ يقرأه، ينفّذ مرحلة مرحلة، ويحدّث
> **Progress Log** في آخر الملف بعد كل مرحلة. أي شات/وكيل جديد يكمّل من هنا.
>
> **كود التطبيق:** مجلد جديد `mobile/` داخل هذا الريبو.
> **عقد الـ API المرجعي:** `MOBILE_API.md` (v1) — مصدر الحقيقة للـ endpoints. لا تُعدّل الـ backend.

---

## Context — ليه وإيه الهدف

`tutor-guardian` هو الـ backend (FastAPI + Ollama + ChromaDB) لمساعد تربوي إسلامي آمن للأهل
العرب. الـ backend **جاهز تماماً كـ mobile API**: sessions + Bearer token + SSE streaming +
safety flags + feedback. الواجهة الحالية `frontend/index.html` مجرد عميل اختبار — والـ README
بيقول صراحة **المنتج النهائي تطبيق موبايل**.

**الهدف:** بناء تطبيق **Flutter** (أندرويد أولاً) يستهلك الـ API الموجود ويقدّم تجربة محادثة
عربية احترافية (RTL، streaming، safety banners)، وكشف الـ backend على HTTPS عام.

**القرارات المحسومة:**
- التقنية: **Flutter** (Dart) — أفضل دعم RTL، كود واحد Android+iOS.
- المنصة: **Android أولاً** (بدون Mac)، iOS لاحقاً.
- الـ Backend: الخطة تتضمن **كشفه على HTTPS عام** (nginx + شهادة) — **يتولاها صاحب المشروع (صلاحيات VPS)، ليست مهمة وكيل بناء التطبيق.**

---

## ثوابت من الكود (لا تخالفها)

**Enums (من `backend/app/core/taxonomy.py` و `MOBILE_API.md` — هاردكود آمن في التطبيق):**
| الحقل | القيم |
|------|------|
| `age_group` | `0-3`, `4-6`, `7-9`, `10-12`, `13-15`, `16-18`, `unspecified` |
| `severity` | `خفيف`, `متوسط`, `شديد`, `طارئ` ← **تُرسل بالعربية حرفياً** |
| `domain` (مُرجَع) | `medical`, `cyber`, `islamic_parenting`, `development` |
| `mode` (مُرجَع) | `retrieval_only`, `llm_generated`, `banned`, `emergency` |
| `escalation_target` | `pediatrician`, `cybersecurity_specialist`, `emergency_services`, `null` |

**تدفّق الـ API:**
1. `POST /api/chat/sessions` (بـ `{device_id?, metadata?}`) → `{session_id, token}` (token صيغته `tg_` + 64 hex).
2. كل الطلبات التالية: header `Authorization: Bearer tg_...`.
3. `POST /api/assistant/stream` (body: `age_group`, `severity`, `behavior_type?`, `message_text`, `session_id`) → SSE.
   - مع `session_id` السيرفر يملك الـ history → **لا ترسل `conversation_history`**.
4. `GET /api/chat/sessions/{id}` → استرجاع المحادثة.
5. `POST /api/feedback` (body: `{session_id?, rating: "up"|"down", comment?}`).

**عقد الـ SSE:** إطارات مفصولة بـ `\n\n`. `event: token` / `data: {"delta":"..."}` (صفر أو أكثر)،
ثم **حدث ختامي واحد** `event: done` / `data: {<AssistantReply>}`، أو `event: error` / `data:{"detail":...}`.
- ردود السلامة (banned/emergency/no-context) تُرسل كـ **done واحد بدون أي token** — تعامل معها كرد كامل.
- `done.reply_text` هو النص النهائي الموثوق (استبدل به تراكم الـ deltas).

**أخطاء يتعامل معها التطبيق:** `401` (أنشئ session جديدة)، `404` (احذف session_id واعمل جديدة)،
`422` (تحقق من الحقول/enums)، `429` (راجع header `Retry-After` وأعد المحاولة)، `5xx` (زر إعادة محاولة).
Rate-limit: 30/دقيقة على `/api/assistant/*`.

---

## Phase 0 — كشف الـ Backend على HTTPS عام 🌐 (يتولاها صاحب المشروع)

> الـ `tg_backend` حالياً على شبكة Docker الداخلية للـ VPS (منفذ 8080→8000 محلي) بدون دومين عام.
> يُكشف عبر nginx الموجود على الـ VPS. **وكيل بناء التطبيق لا ينفّذ هذه المرحلة** — يطوّر مؤقتاً
> مقابل الـ backend الحالي، ويأخذ الـ public base URL النهائي عند جهوزه.

- [ ] اختيار سابدومين (مقترح: `tg-api.alsaba.cloud`).
- [ ] DNS A record → IP الـ VPS (`72.62.44.131`).
- [ ] nginx reverse proxy → `tg_backend:8000` (أو `127.0.0.1:8080`). **مهم للـ SSE:**
      `proxy_buffering off;` + `proxy_http_version 1.1;` + `proxy_set_header Connection '';` + `proxy_read_timeout 300s;`.
- [ ] شهادة TLS عبر certbot/Let's Encrypt.
- [ ] تحديث `CORS_ORIGINS` في `.env` على الـ VPS.
- [ ] **تحقق:** `curl https://tg-api.alsaba.cloud/health` → `{"status":"ok"}` + اختبار SSE بدون buffering.

---

## Phase 1 — هيكلة مشروع Flutter 📱

- [ ] `flutter create` في `mobile/` بـ org `com.alsaba`، اسم الحزمة `com.alsaba.tutorguardian`.
- [ ] اسم التطبيق المعروض: **المربي الذكي** (من `frontend/manifest.json`)، short: المربي.
- [ ] ضبط Android: `minSdkVersion 23`، `targetSdk` حديث، RTL افتراضي.
- [ ] الاعتماديات في `pubspec.yaml`: `http` (أو `dio`)، `flutter_riverpod`، `uuid`،
      `flutter_secure_storage`، `flutter_markdown`، `google_fonts` (Cairo/Tajawal)، `connectivity_plus`.
- [ ] هيكل المجلدات: `lib/api/`، `lib/models/`، `lib/screens/`، `lib/widgets/`، `lib/state/`، `lib/theme/`، `lib/config/`.
- [ ] `MaterialApp`: `locale: Locale('ar')`، `Directionality.rtl`، theme لون أساسي teal `#1A5F7A`.
- [ ] `lib/config/app_config.dart`: قراءة `API_BASE_URL` عبر `--dart-define` (افتراضي backend الحالي).
- [ ] **تحقق:** `flutter run` على جهاز أندرويد → شاشة بالثيم والاتجاه RTL صح.

---

## Phase 2 — طبقة الـ API Client 🔌

- [ ] `lib/models/`: `AssistantReply`، `SessionResponse`، `ChatMessage`، وenums مع `fromJson`/`toJson`. **تجاهل الحقول غير المعروفة** (العقد additive).
- [ ] `lib/api/tg_client.dart`:
  - [ ] `device_id`: توليد UUID مرة واحدة وتخزينه في secure storage.
  - [ ] `createSession()` → POST `/api/chat/sessions` → خزّن `token` + `session_id`.
  - [ ] حقن `Authorization: Bearer <token>` في كل الطلبات.
  - [ ] `streamQuery(...)` → POST `/api/assistant/stream` → parser للـ SSE (token/done/error)، يرجّع Stream.
  - [ ] `query(...)` → POST `/api/assistant/query` (fallback غير streaming).
  - [ ] `getHistory(sessionId)` → GET `/api/chat/sessions/{id}`.
  - [ ] `sendFeedback(rating, comment?)` → POST `/api/feedback`.
- [ ] معالجة الأخطاء مركزياً: `401`→أنشئ session، `404`→احذف وأنشئ، `429`→backoff بـ Retry-After، `5xx`→قابل لإعادة المحاولة.
- [ ] **تحقق:** createSession يرجّع token، streamQuery يطبع deltas ثم done على سؤال حقيقي.

---

## Phase 3 — واجهة المحادثة 💬

> مرجع بصري: `frontend/index.html` (نفس الألوان والسلوك). teal `#1A5F7A`، فقاعة المستخدم teal يمين،
> فقاعة المساعد رمادي `#F1F3F5` يسار، نجاح `#28A745`، تحذير `#FFF3CD`، خطر `#F8D7DA`.

- [ ] `ChatScreen`: AppBar «🛡️ المربي الذكي»، خيط رسائل، حالة فاضية (درع + ترحيب).
- [ ] شريط الإعدادات: dropdown `age_group` (افتراضي 4-6)، dropdown `severity` (افتراضي متوسط)، حقل `behavior_type` (اختياري).
- [ ] `MessageBubble`: RTL، عرض Markdown (bold/italic/code).
- [ ] Streaming حي: ألحق الـ delta، typing indicator، استبدل بالنص النهائي عند done.
- [ ] **Safety banners** (من كائن done، لا تحلل النص):
      `needs_human_review==true` → شريط أصفر «راجع مختصاً».
      `escalation_target=="emergency_services"` → شريط أحمر «حالة طارئة» + زر اتصال.
      `mode=="banned"` → إشعار «خارج النطاق».
- [ ] شرائح ميتاداتا: domain + mode + severity تحت الرد.
- [ ] أزرار feedback (👍/👎) → POST feedback، مع «✅ شكراً».
- [ ] منطقة الإدخال: textarea بارتفاع تلقائي + زر إرسال (معطّل وقت الطلب)، Enter يرسل.
- [ ] زر «🔄 بدء محادثة جديدة» + شارة عدد الأسئلة.
- [ ] **تحقق:** محادثة متعددة الأدوار تظهر streaming، banners، feedback على جهاز حقيقي.

---

## Phase 4 — الحالة والتخزين 🗄️

- [ ] `ChatNotifier` (Riverpod): قائمة الرسائل، حالة الجلسة، حالة التحميل/الخطأ.
- [ ] تخزين `device_id` + `session_id` + `token` في `flutter_secure_storage`.
- [ ] عند فتح التطبيق: `getHistory` لاسترجاع المحادثة (أو بدء جديد لو 404).
- [ ] إدارة دورة حياة الجلسة: 401/انتهاء → إعادة إنشاء شفافة.
- [ ] **تحقق:** اقفل التطبيق وافتحه → المحادثة تُسترجع؛ امسح الجلسة → يبدأ نظيف.

---

## Phase 5 — الصقل والـ Native ✨

- [ ] أيقونة + splash بهوية الدرع 🛡️ teal (`flutter_launcher_icons` + `flutter_native_splash`).
- [ ] Android adaptive icon + اسم «المربي الذكي».
- [ ] معالجة الأوفلاين: `connectivity_plus`، رسالة «غير متصل»، إعادة محاولة.
- [ ] Network security: HTTPS فقط (لا cleartext في production).
- [ ] حالات تحميل/خطأ مصقولة في كل المسارات.
- [ ] **تحقق:** قطع النت → رسالة واضحة؛ رجوعه → استئناف.

---

## Phase 6 — البناء والبيتا (Android) 🚀

- [ ] keystore توقيع + `key.properties` و `build.gradle`.
- [ ] `flutter build appbundle --release --dart-define=API_BASE_URL=https://tg-api.alsaba.cloud`.
- [ ] مسار اختبار داخلي على Google Play (أو APK مباشر للبيتا).
- [ ] **تحقق نهائي:** جهاز حقيقي → محادثة كاملة بدون أعطال، streaming سلس، banners تظهر، feedback يُحفظ في `ops/sessions.db`.

---

## Phase 7 — iOS (مؤجّل) 🍎

- [ ] يتطلب Mac + اشتراك Apple Developer. نفس الكود؛ ضبط `ios/`، أيقونات، TestFlight. بعد استقرار بيتا أندرويد.

---

## الملفات الحرجة

**إنشاء (في `mobile/`):** `pubspec.yaml` · `lib/main.dart` · `lib/config/app_config.dart` ·
`lib/api/tg_client.dart` · `lib/models/*.dart` · `lib/screens/chat_screen.dart` ·
`lib/widgets/message_bubble.dart` · `lib/widgets/safety_banner.dart` · `lib/state/chat_notifier.dart` · `lib/theme/app_theme.dart`

**لا يُعدّل:** أي شيء تحت `backend/` — العقد ثابت (إلا بنقاش مسبق عند نقص حقيقي).

---

## التحقق الشامل (End-to-End)

1. **HTTPS:** `https://<domain>/health` يرجّع ok؛ الـ SSE بدون buffering.
2. **جلسة:** التطبيق ينشئ session ويخزّن token؛ إعادة الفتح تسترجع المحادثة.
3. **محادثة:** سؤال عربي → streaming حي → done بنص نهائي + domain/mode صحيحين.
4. **سلامة:** سؤال طارئ → banner أحمر؛ خارج النطاق → إشعار banned.
5. **أخطاء:** 401/404/429 يتعامل معها التطبيق بسلاسة.
6. **بيتا:** APK/AAB على جهاز حقيقي → محادثة كاملة + feedback متخزّن.

---

## سياسة العمل للوكيل المنفّذ

- نفّذ **مرحلة مرحلة بالترتيب** (Phase 1 → 6؛ Phase 0 يتولاها صاحب المشروع). لا تبدأ مرحلة قبل اجتياز «تحقق» السابقة.
- بعد كل مرحلة: **حدّث Progress Log** تحت — علّم ✅، تاريخ + ملاحظة قصيرة + أي انحراف.
- التزم بالعربية في كل نصوص الواجهة، RTL، والـ enums حرفياً من الجدول أعلاه.
- لو احتجت تغيير في الـ backend: **قف وناقش** — الافتراض إن العقد ثابت.

---

## Progress Log (يحدّثه الوكيل المنفّذ)

| التاريخ | المرحلة | الحالة | ملاحظة |
|---------|---------|--------|--------|
| 2026-06-08 | — | 📝 الخطة مكتوبة | في انتظار بدء التنفيذ (Phase 1) |
