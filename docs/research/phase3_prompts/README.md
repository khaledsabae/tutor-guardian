# Phase 3 Prompts — 5 prompts لتأليف المنهج

> **الاستخدام:** هذه البرومبتات جاهزة للإرسال لنماذج LLM متخصصة في تأليف المحتوى التربوي الإسلامي (مثل: Claude، GPT-4، Jais، AceGPT، Fanar، أو نماذج محلية مثل Command-R+، Qwen2.5).
>
> **التوصية:** Claude Sonnet 4.5 أو GPT-4.1 للـ orchestrator (#5) — يحتاج تخطيط. للنماذج الأخرى (1-4) يكفي Sonnet 3.5 / Haiku 4 / GPT-4.1-mini.

---

## الـ 5 Prompts

| # | الملف | الغرض | المُدخل | المُخرج |
|---|-------|-------|--------|---------|
| 1 | `01_path_author.md` | تأليف مسار واحد | age_group + domain + topic | path.json |
| 2 | `02_lesson_author.md` | تأليف درس واحد | path + 1-3 unit_ids | lesson.json |
| 3 | `03_daily_tip_author.md` | تأليف نصيحة (مفرد أو batch) | age_group + 1 unit (أو N) | tip.json (مصفوفة) |
| 4 | `04_validator.md` | quality control لأي كائن | path/lesson/tip JSON | verdict (ACCEPT/FIX/REJECT) + issues |
| 5 | `05_orchestrator.md` | master pipeline — يخطط ثم يستدعي 1-4 | age_group + topic + units | execution_plan.json |

---

## سير العمل (Workflow)

```
┌──────────────────────────────────────────────────────────┐
│ #5 Orchestrator: "أنشئ خطة لمسار X في الفئة Y"          │
│   ↓                                                      │
│   ينتج: execution_plan.json (units مختارة + skeleton)   │
└──────────────────────────────────────────────────────────┘
                         ↓
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ #1 Path      │ │ #2 Lesson    │ │ #3 Tip       │
│   Author     │ │   Author ×N  │ │   Author ×30 │
│              │ │              │ │              │
│ → path.json  │ │ → lesson.json │ │ → tip.json   │
└──────────────┘ └──────────────┘ └──────────────┘
        ↓                ↓                ↓
        └────────────────┼────────────────┘
                         ↓
                ┌────────────────┐
                │ #4 Validator   │
                │  لكل كائن     │
                │ → ACCEPT/FIX   │
                └────────────────┘
```

---

## ضمانات العقد (Hard Contract)

كل prompt يُلزم بالـ taxonomy في `backend/app/core/taxonomy.py`:

| Enum | القيم |
|------|-------|
| `age_group` | 0-3, 4-6, 7-9, 10-12, 13-15, 16-18 |
| `domain` | medical, cyber, islamic_parenting, development |
| `severity` | خفيف, متوسط, شديد, طارئ (units فقط) |
| `intervention_type` | وقائي, إرشادي, علاجي, إحالة_لطبيب (units فقط) |
| `reference_type` | DSM-5, كتاب_فقهي, حديث, كتاب_تربوي, تقرير_سيبراني, إرشاد_مهني, مقال_تنموي, تقرير_طبي, مقال_تربوي |
| `pedagogical_framework` | prophetic_7_7_7, ghazali_tazkiyah, attachment_rahma, zpd_scaffolded |

---

## Self-Check Lists (الـ LLM يراجع نفسه)

كل prompt يحتوي قسم **Self-Check قبل التسليم** — يجب أن يجتازه قبل اعتبار الخرج صالحاً. هذا يقلل الحاجة لـ validator #4 في 80% من الحالات.

---

## Cross-Reference Checks (آلي، خارج نطاق الـ LLM)

- lesson.unit_ids[i] ∈ knowledge_base/units/
- path.lesson_ids[i] ∈ knowledge_base/curriculum/lessons/
- tip.unit_id ∈ knowledge_base/units/
- لا unit_id مكرّر عبر دروس نفس المسار أو في tip + lesson لنفس المسار

هذي يقوم بها `scripts/seed_curriculum.py` (الـ pipeline المحلي) قبل commit.

---

## نصائح عملية للاستخدام

1. **اعمل dry-run أولاً:** ابعت prompt #5 (orchestrator) فقط → راجع الـ plan → ثم ابعت #1, #2, #3.
2. **قَيِّد temperature:** استخدم `temperature=0.2-0.3` للـ deterministic output (مهم للـ IDs و الـ IDs الـ ordered).
3. **اعمل JSON validation بعد كل LLM call:** قبل تسليم JSON للمستخدم، شغّل `python -c "import json; json.loads(...)"` للتأكد من الـ parse.
4. **استخدم validator #4 لكل output:** حتى لو بدا سليم، أحياناً الـ LLM يخترع مراجع.
5. **احتفظ بـ الـ prompts في version control:** أي تعديل في الـ schema → عدّل البرومبت.

---

## بعد Phase 3 (Integration)

عند استلام كل الـ JSONs من النماذج الخارجية:

1. **Commit الـ JSONs** في `knowledge_base/curriculum/{paths,lessons,daily_tips}/`.
2. **شغّل الـ cross-ref check** (Python script بسيط).
3. **شغّل `python ops/tools/check_kb_integrity.py`** — لازم يخرج 0.
4. **شغّل pytest** — `test_program.py` يضمن الـ API يرجع البيانات الصحيحة.
5. **Commit + push** على main → CI/CD يعمل deploy → الـ app يقرأ المسارات الجديدة عند الـ startup.
