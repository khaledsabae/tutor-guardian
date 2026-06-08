# Tutor Guardian — Research Phase (Phase R)

**Date:** 2026-06-08
**Phase:** R — الأبحاث الأربعة (Research)
**Status:** ✅ مكتملة
**Source files:** 12 ملف في `/home/khalednew/Downloads/`، تم توحيدها في 4 مجلدات × 3 أبحاث/موضوع.

---

## البنية (Structure)

```
docs/research/
├── README.md                          (هذا الملف)
├── 01_content_pedagogy/               المحتوى والتربية الإسلامية
│   ├── r1_framework_v2.md             ← primary: Guardian2 (أكاديمي محدّث)
│   ├── r2_medical_cyber.md            ← secondary: استشهادات طبية/سيبرانية (.docx→md)
│   └── r3_framework_v1.md             ← superseded: Guardian1 (مسوّدة سابقة)
├── 02_market_economics/               السوق والاقتصاد
│   ├── r1_english.md                  ← primary: 02_market_economics.md (إنجليزي، الأقوى)
│   ├── r2_arabic.md                   ← secondary: 02_market_econ.md (عربي، مرادف)
│   └── r3_references.md               ← alternative: .docx (مراجع فقط، competitor matrix ضعيف)
├── 03_ux_design/                      تجربة المستخدم
│   ├── r1_full.md                     ← primary: النسخة الأشمل بـ wireframes
│   ├── r2_flutter_code.md             ← secondary: .docx بـ Dart code snippets
│   └── r3_summary.md                  ← compressed: ملخص مُختصر
└── 04_ai_technical/                   التقنية والـ AI
    ├── r1_blueprint.md                ← primary: 04_ai_technical.md (هندسة داخلية)
    ├── r2_tee_deepdive.md             ← secondary: .docx — TEE/confidential compute deep-dive
    └── r3_draft.md                    ← alternative: نسخة draft فيها [استدلال]
```

## منهجية الترتيب (Ordering)

كل موضوع حصل على 3 أبحاث من 3 perspectives مختلفة (أو 3 drafts لنفس الـ research). الترتيب `r1`/`r2`/`r3` تم بناءً على:

- **r1 = primary**: البحث اللي الـ subagent قيمه كأحسن مصدر تنفيذي (executive-ready، أرقام محددة، استشهادات موثوقة، تغطية كاملة للـ subtopics).
- **r2 = secondary/complementary**: يضيف زاوية مختلفة (code snippets، TEE depth، مراجع طبية، تكميل عربي).
- **r3 = draft/superseded**: نسخة سابقة، أو draft، أو مراجع فقط.

**ملاحظة:** الحجم وحده مش مؤشر للجودة — `r3_draft.md` (36K) أكبر من `r1_blueprint.md` (24K) لكن الأخير primary لأنه أرقامه internal/instrumented مش extrapolated.

## الـ subtopics المغطاة في كل موضوع

| الموضوع | Subtopics |
|---------|-----------|
| 01_content_pedagogy | (A) Islamic foundations (tarbiyah, tazkiyah, adab) · (B) Age-group structure (0-3 → 16-18) · (C) Content domain taxonomy · (D) Lesson design & assessment |
| 02_market_economics | (A) MENA EdTech market size · (B) Competitor analysis · (C) Pricing/business model · (D) User personas |
| 03_ux_design | (A) RTL patterns for Arabic · (B) Child/parent UX flows · (C) Visual design system · (D) Accessibility |
| 04_ai_technical | (A) Arabic model benchmarks · (B) Arabic RAG (chunking, embeddings, reranking) · (C) Personalization w/o tracking · (D) Local→cloud migration w/ privacy |

## Phase R → Phase 0

Phase R مكتملة. الخطوة التالية (Phase 0) في `PROGRAM_BUILD_PLAN.md`: مكاسب سريعة (بعضها يدوي).
