# Tutor Guardian – الذكاء التربوي الحارس

هذا المشروع يطوِّر مساعدًا تربويًا ذكيًا للأهل، يعتمد على RAG، ويجمع بين ثلاث مجالات معرفة:

المجال الطبي (سلوك ونفسية الأطفال، دون تقديم تشخيص سريري مباشر أو وصف أدوية).

المجال الشرعي والتربوي (تربية نبوية وفقه واقع الأسرة المسلمة المعاصرة).

المجال السيبراني (حماية الأطفال رقميًا من المخاطر، وإدارة استخدام الأجهزة والألعاب).

هيكل المشروع الحالي:

backend/ : خدمات الـ API ومحرك الـ RAG والـ Guardrails.

frontend/ : واجهة استخدام الأهل ولوحة التحكم.

knowledge_base/ : مستودع المعرفة الهجين، بنية JSON + Vector DB.

ops/ : سكربتات التشغيل، الأتمتة، وأدوات التطوير.

---

## التحقق من وحدات المعرفة

للتحقق من صحة ملفات JSON في knowledge_base/ مقابل الـ Schema:

```bash
python ops/tools/validate_knowledge_units.py --dir knowledge_base/examples
```

---

## تشغيل واجهة الـ API

```bash
cd /home/khalednew/projects/tutor-guardian
PYTHONPATH=$(pwd):$PYTHONPATH python -m uvicorn backend.app.main:app --reload --port 8090
```

ثم افتح http://localhost:8090/docs للاطلاع على Swagger UI، وعميل الاختبار على http://localhost:8090/ui/

> **ملاحظة:** الـ backend/API هو المنتج. صفحة `frontend/` مجرد عميل اختبار — المنتج النهائي تطبيق موبايل.

---

## التشغيل عبر Docker

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b   # لمرة واحدة
docker compose up -d backend
# API: http://localhost:8000 · عميل الاختبار: http://localhost:8000/ui/
```

الإعدادات كلها في `.env.example` (انسخه إلى `.env`). كل الاستدلال محلي عبر Ollama — لا تخرج أي بيانات.

---

## حارس سلامة قاعدة المعرفة (مهم)

يقارن وحدات المعرفة ↔ الـ schema ↔ `taxonomy.py` ↔ ChromaDB ويمنع أي انحراف صامت.

```bash
./check.sh                         # فحص سريع (schema / enums / taxonomy)
./check.sh --full                  # + تزامن ChromaDB + الاختبارات
python ops/tools/check_kb_integrity.py --check-index   # الفحص الكامل
```

الفحص يعمل تلقائياً عند كل `git commit` (عبر `.githooks/pre-commit`) وفي الـ CI.
تفعيل الـ hook بعد الاستنساخ:

```bash
git config core.hooksPath .githooks
```

عند إضافة/تعديل وحدات معرفة، شغّل التنظيف والإعادة:

```bash
python ops/tools/normalize_units.py    # تنظيف قيم enum
python ops/tools/build_vector_db.py    # إعادة بناء الفهرس + units_index.json
```

---

## الاختبارات

```bash
python -m pytest          # 22 اختبار (السلامة، taxonomy، API، سلامة قاعدة المعرفة)
```

راجع `API.md` لعقد الـ API الكامل (للفريق الذي يبني تطبيق الموبايل).
