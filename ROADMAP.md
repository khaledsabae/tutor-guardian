# Tutor Guardian — Production Roadmap

> ملف مستقر للمتابعة. بعد الموافقة، أول خطوة تنفيذية = نسخ هذا الملف إلى
> ROADMAP.md و commit، عشان يبقى داخل الريبو وأي شات جديد يقدر يكمّل منه.

---

## Context — ليه بنعمل ده والهدف

tutor-guardian هو الـ CORE backend لتطبيق موبايل (Android/iOS) بيقدّم إرشاد تربوي إسلامي آمن
للأهالي العرب المسلمين، RAG محلي 100% (FastAPI + Ollama + ChromaDB). الميزات الأساسية خلصت
(W0–W4): guardrails، sessions، SSE streaming، Docker، CI، KB integrity guard.

**خط النهاية**: Backend إنتاجي جاهز للموبايل — auth، rate-limit موزّع، اختبارات شاملة، مراقبة، أمان، قاعدة معرفة كاملة.
**الترتيب**: معرفة → سرعة → تحصين → بيتا.

**مبادئ حاكمة**: الـ API هو المنتج (مش واجهة الويب) · محلي وخاص 100% · السلامة نقطة قوة.

---

## الحالة الحالية — Baseline (تم التحقق 2026-06-07)

| البند | الحالة |
|-------|--------|
| وحدات المعرفة | 197 unit — medical:56 · islamic_parenting:93 · cyber:26 · development:22 |
| ChromaDB | 197 vector مفهرس (ONNX all-MiniLM-L6-v2, 384-dim, cosine) |
| PDFs خام | 50 نزّلوا بنجاح · 32 فشلوا (404/403) · 6 يتطلبوا اشتراك (AAP). أغلب الـ 50 لسه مش متحوّلين لـ units |
| Single source of truth | backend/app/core/taxonomy.py (enums) — يفرضه check_kb_integrity.py |
| الاختبارات | 20 test (safety, taxonomy, KB integrity, API smoke) — CI gate أخضر |
| Docker/CI | docker-compose.yml (ollama+backend) · .github/workflows/ci.yml (gates بس، مفيش deploy) |
| توثيق الموبايل | MOBILE_API.md (مفصّل) + API.md |
| Home server | HP EliteBook (i7-1165G7, 32GB) — Ollama 0.30.6، qwen2.5:3b @14-16 tok/s، gemma4:e4b @9 tok/s |

**أبرز ثغرات الإنتاج المُكتشفة:**
1. زمن الاستجابة: classifier يضيف 3-5s قبل كل رد · الـ LLM الرئيسي 5-20s · تحميل بارد للـ embedding 30-60s
2. أمان: مفيش auth خالص — device_id بيتقبل بس مش بيتحقق منه
3. تكوين هش: domain_classifier.py بيستخدم OLLAMA_LOCAL_BASE_URL منفصل عن OLLAMA_BASE_URL
4. rate-limit في الذاكرة (single-instance) — هيفشل مع multi-instance
5. تغطية اختبار ناقصة: مفيش tests لـ streaming SSE، error paths، retrieval، multi-turn context
6. فجوات معرفية: صيام، زكاة، بلوغ، مراهقة، تبول لاإرادي، خوف من الظلام، قضم أظافر

---

## المرحلة 1 — اكتمال قاعدة المعرفة (KB Completeness) 📚

**الهدف**: نحوّل الـ PDFs المحمّلة لـ units، ونسدّ الفجوات المعرفية، بحيث الـ RAG يلاقي إجابة موثّقة لأغلب الأسئلة.

### 1.1 — تعميم خط الإدخال (ingest pipeline)
- **مشكلة**: ops/tools/ingest_source.py بينادي gemma4:31b-cloud على localhost:11434 — غلط.
  ingest_tarbiya_alwan.py متخصص في كتاب واحد.
- **الحل**: سكربت موحّد ops/tools/ingest_pdf.py:
  - يقرأ env (OLLAMA_LOCAL_BASE_URL + OLLAMA_LOCAL_FAST_MODEL)
  - يستخرج نص PDF (pdfplumber) أو يقرأ .txt sidecar لو موجود (OCR)
  - chunking (header-split → 250-word + overlap)
  - نفس prompt استخراج الوحدة (الحقول: text_simplified, behavior_type, age_group, severity, intervention_type, labels)
  - يكتب knowledge_base/units/{domain[:3]}-{hex}.json بالـ schema الكامل + source_meta
  - resume/checkpoint (progress.json) + rate-limit (1-2s)
  - batch mode مع --domain و --reference

### 1.2 — معالجة الـ PDFs غير المُعالَجة
- ترتيب الأولوية: development (8 PDF) → cyber (12 PDF) → medical (27 PDF)
- لكل PDF: ingest → مراجعة عيّنة من الـ units المتولّدة → build_vector_db.py
- ملفات فاضية نتجاهلها: Tawid_Salah.pdf, UNICEF_Online_Protection.pdf

### 1.3 — سدّ الفجوات المعرفية
- مواضيع ناقصة: صيام، زكاة، بلوغ، مراهقة، تبول لاإرادي، خوف من الظلام، قضم أظافر
- مصادرها غالباً في raw_sources/islamic_parenting/ (علوان، المنهج النبوي) و medical/ (NIMH/CDC)
- لكل فجوة: نتأكد فيه على الأقل unit واحد بكل age_group منطقي

### 1.4 — تحقّق المرحلة
- python ops/tools/check_kb_integrity.py → IN SYNC
- استعلامات يدوية على /api/assistant/query لكل فجوة → ترجع unit موثّق

---

## المرحلة 2 — السرعة وتجربة المستخدم (Latency & UX) ⚡

**الهدف**: نقلّل الزمن المحسوس من ~9-27s (warm) و 40-90s (cold) لمستوى مقبول للموبايل.

### 2.1 — تسريع domain classifier (يوفّر 3-5s على أغلب الطلبات)
- Fast-path بالكلمات المفتاحية: صلاة/صيام→fiqh، إدمان ألعاب→cyber، توحد/قلق→medical، مشي/أسنان→development
- LRU cache على نص السؤال
- نداء الـ LLM يفضل للأسئلة الغامضة بس
- نخلّي النداء async (httpx.AsyncClient)

### 2.2 — Warm-up عند الإقلاع (يقتل الـ cold start)
- في main.py lifespan startup: eager-load ONNX embedder + _ensure_index()
- warm-up request للـ classifier model و stream model على Ollama
- في Docker: ONNX model جوه الـ image

### 2.3 — تحسينات retrieval
- دمج Tier 1+2 في query واحد
- (اختياري) cache نتائج لـ (domain+age_group+behavior_type) شائعة

### 2.4 — مراجعة UX بعد إخفاء حقل domain
- التأكد إن الـ frontend/index.html + عقد الموبايل بيعرضوا الدومين المكتشَف بوضوح
- اختبار end-to-end للمحادثة (history badge، streaming، clear conversation)

### 2.5 — تحقّق المرحلة
- benchmark قبل/بعد: زمن الرد للأسئلة الواضحة
- أول request بعد restart مايعملش 30-60s تحميل embedding
- pytest أخضر مع tests جديدة للـ fast-path والـ cache

---

## المرحلة 3 — التحصين الإنتاجي (Production Hardening) 🔒

**الهدف**: الـ backend يبقى آمن وقابل للتوسّع وموثوق لتطبيق منشور.

### 3.1 — المصادقة (Auth — حرج قبل النشر)
- POST /api/chat/sessions يولّد device_id + token موقّع (JWT أو opaque في SQLite)
- middleware يتحقق من الـ token على /api/assistant/* و /api/chat/*
- rate-limit per-device بدل per-IP
- ملفات: backend/app/middleware/auth.py · conversation_store.py (token store) · models/api.py (token)

### 3.2 — إصلاح تكوين Ollama المزدوج
- نوحّد: domain_classifier.py و ai_gateway.py يقراوا تكوين متّسق
- في Docker production الكل يشاور على خدمة ollama الواحدة
- نوثّق الفرق في .env.example

### 3.3 — Rate-limit موزّع
- Redis اختياري (لو REDIS_URL موجود) للـ multi-instance
- in-memory fallback للتطوير
- redis في docker-compose.yml

### 3.4 — توسيع الاختبارات
- streaming SSE: عقد token/done/error، السلامة قبل أول token
- error paths: Ollama down → fallback chain → retrieval_only
- retrieval: retrieve_multi_domain (dedup، sort، 4-tier fallback)
- classifier fast-path + cache
- auth (token مطلوب/صالح/منتهي)

### 3.5 — المراقبة والتتبّع (Observability)
- موجود: ai_gateway._log_call() يكتب ops/sessions.db جدول llm_calls
- نضيف: endpoint /metrics بسيط + سكربت تقرير من sessions.db
- request/response logging middleware (مع إخفاء PII)

### 3.6 — تحقّق المرحلة
- pytest أخضر بكل الـ tests الجديدة · CI أخضر
- نداء بدون token → 401 · بـ token صالح → 200
- docker compose up (مع redis) → rate-limit شغّال عبر instance

---

## المرحلة 4 — جاهزية البيتا (Beta Readiness) 🚀

**الهدف**: نطلّق لمستخدمين حقيقيين ونقفل حلقة التغذية الراجعة.

### 4.1 — نشر
- target نشر (VPS أو سرفر البيت عبر Tailscale) + docker compose production + TLS (لو عام)
- توثيق إقلاع كامل في README.md / ROADMAP.md

### 4.2 — حلقة التغذية الراجعة
- زر/endpoint feedback بسيط (👍/👎 + تعليق) يتخزّن في SQLite
- مراجعة دورية لـ sessions.db: أسئلة رجعت "لا تتوفر معلومات" → فجوات معرفية جديدة

### 4.3 — تحقّق المرحلة
- مستخدمو بيتا يقدروا يكمّلوا محادثة كاملة بدون أعطال
- feedback بيتجمّع وبيتراجع

---

## الملفات الحرجة

**إنشاء:**
- ops/tools/ingest_pdf.py (موحّد batch)
- backend/app/middleware/auth.py
- backend/tests/test_streaming.py
- backend/tests/test_errors.py
- backend/tests/test_retrieval.py
- backend/tests/test_auth.py
- ops/tools/llm_stats.py

**تعديل:**
- backend/app/services/domain_classifier.py (fast-path+cache+async)
- backend/app/main.py (warm-up lifespan)
- backend/app/services/retrieval.py (دمج tiers + eager load)
- backend/app/middleware/rate_limit.py (Redis اختياري)
- backend/app/services/conversation_store.py (token store)
- backend/app/models/api.py (token)
- docker-compose.yml (redis اختياري)
- .env.example (توضيح Ollama المزدوج + REDIS_URL)
- backend/app/routers/assistant.py
- knowledge_base/units/*.json (units جديدة)

---

## التحقق الشامل (End-to-End)

1. **KB**: check_kb_integrity.py IN SYNC · أسئلة الفجوات ترجع units موثّقة
2. **سرعة**: أسئلة واضحة بدون overhead classifier · مفيش cold-load 30-60s بعد restart
3. **أمان**: نداء بدون token → 401 · بـ token → 200 · rate-limit per-device
4. **اختبارات**: pytest أخضر شامل streaming/error/retrieval/auth · CI أخضر
5. **Docker**: docker compose up → كل الـ endpoints شغّالة · /metrics يرجّع
6. **بيتا**: محادثة كاملة من جهاز حقيقي + feedback متخزّن

---

## ترتيب التنفيذ والـ commits (كل بند commit مستقل)

| Priority | المرحلة | المحتوى |
|----------|---------|---------|
| P0 | — | نسخ الخطة → ROADMAP.md + commit (baseline) |
| P1 | معرفة | ingest_pdf موحّد → معالجة PDFs → سدّ الفجوات → rebuild index |
| P2 | سرعة | classifier fast-path+cache+async → warm-up → retrieval tiers → UX |
| P3 | تحصين | auth → إصلاح Ollama → Redis rate-limit → tests شاملة → observability |
| P4 | بيتا | نشر → feedback loop |

**سياسة git**: push مباشر على main، مفيش PRs. كل مرحلة commits صغيرة مستقلة.

---

## ملاحظات للمتابعة (لأي شات جديد)

- **سرفر البيت**: 100.109.163.64:11434 (Tailscale) — Ollama 0.30.6. النماذج: qwen2.5:3b (سريع/classifier)، gemma4:e4b (جودة). SSH: `ssh -i ~/.ssh/id_ed25519 khaled@100.109.163.64`
- **fallback chain**: kimi-k2.6:cloud → gemma4:31b-cloud → gemma4:e4b@home → qwen2.5:3b@home. stream_chain معكوس: qwen2.5:3b@home الأول
- **taxonomy.py** هو المرجع لكل الـ enums — أي unit جديد لازم يطابقه
- **البيئة**: `source backend/.venv/bin/activate` · التشغيل المحلي port 8090، Docker port 8000
- **remote git**: مفيش remote git متظبّط على tutor-guardian حاليًا — ربط الـ remote قرار المستخدم
