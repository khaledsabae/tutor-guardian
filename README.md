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

ثم افتح http://localhost:8090/docs للاطلاع على Swagger UI.
