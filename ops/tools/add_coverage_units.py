#!/usr/bin/env python3
"""
Add knowledge units for under-covered domains: ADHD, Autism, Gaming Disorder.
Content is conservative, parent-facing, evidence-aligned (CDC / AAP / DSM-5 /
ICD-11) and NON-diagnostic — consistent with the guardrails (no diagnosis, no
medication). IDs are deterministic (uuid5) so re-running won't duplicate.
"""
import json
import uuid
from pathlib import Path

UNITS_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "units"
NS = uuid.UUID("11111111-2222-3333-4444-555555555555")  # fixed namespace
TS = "2026-06-07T00:00:00Z"

UNITS = [
    # ─────────────── ADHD (medical) ───────────────
    {
        "slug": "adhd-4-6-signs",
        "domain": "medical", "age_group": "4-6",
        "behavior_type": "فرط_الحركة_وتشتت_الانتباه",
        "intervention_type": "إرشادي", "severity": "خفيف",
        "reference_type": "DSM-5",
        "reference_info": "CDC — ADHD in Young Children; APA DSM-5",
        "text_original": (
            "ADHD is marked by a persistent pattern of inattention and/or "
            "hyperactivity-impulsivity that is more frequent and severe than is "
            "typical for the child's age (DSM-5). In preschoolers, high activity "
            "and short attention are often developmentally normal; concern rises "
            "when symptoms appear in multiple settings and impair daily life (CDC)."
        ),
        "text_simplified": (
            "الحركة الزائدة وقِصَر الانتباه في سن ٤–٦ سنوات كثيراً ما تكون طبيعية في هذه "
            "المرحلة. يزيد القلق فقط عندما تظهر الأعراض في أكثر من مكان (البيت والحضانة) "
            "وتؤثر على حياة الطفل اليومية. راقب طفلك في مواقف مختلفة، ووفّر روتيناً ثابتاً "
            "وتعليمات قصيرة وواضحة. هذا ليس تشخيصاً — إن استمرت الصعوبة فاستشر مختصاً."
        ),
        "labels": ["adhd", "فرط_حركة", "cdc", "dsm-5"],
    },
    {
        "slug": "adhd-7-9-strategies",
        "domain": "medical", "age_group": "7-9",
        "behavior_type": "فرط_الحركة_وتشتت_الانتباه",
        "intervention_type": "إرشادي", "severity": "متوسط",
        "reference_type": "تقرير_طبي",
        "reference_info": "AAP Clinical Practice Guideline for ADHD; CDC",
        "text_original": (
            "Behavioral parent training and classroom supports are first-line for "
            "school-age children: consistent routines, clear and brief instructions, "
            "breaking tasks into steps, and immediate positive reinforcement for "
            "desired behavior (AAP)."
        ),
        "text_simplified": (
            "للأطفال في سن المدرسة تساعد الاستراتيجيات السلوكية كثيراً: نظام يومي ثابت، "
            "تعليمات قصيرة وواضحة، تقسيم المهمة إلى خطوات صغيرة، ومكافأة فورية على السلوك "
            "الجيد. قلّل المشتتات أثناء الواجب، واتفق مع المعلّم على خطة موحّدة بين البيت "
            "والمدرسة. تجنّب العقاب القاسي فهو يزيد المشكلة."
        ),
        "labels": ["adhd", "سلوكي", "aap", "مدرسة"],
    },
    {
        "slug": "adhd-10-12-referral",
        "domain": "medical", "age_group": "10-12",
        "behavior_type": "فرط_الحركة_وتشتت_الانتباه",
        "intervention_type": "إحالة_لطبيب", "severity": "شديد",
        "reference_type": "DSM-5",
        "reference_info": "DSM-5 ADHD criteria; CDC diagnostic guidance",
        "text_original": (
            "Evaluation by a qualified clinician is warranted when symptoms persist "
            "for 6+ months, appear before age 12, occur in two or more settings, and "
            "clearly impair academic or social functioning (DSM-5). Diagnosis is made "
            "by professionals, not by checklists alone."
        ),
        "text_simplified": (
            "إذا استمرت أعراض ضعف الانتباه أو فرط الحركة أكثر من ٦ أشهر، وتظهر في البيت "
            "والمدرسة معاً، وتؤثر بوضوح على الدراسة أو العلاقات — فهذا وقت استشارة طبيب "
            "أطفال أو أخصائي نفسي. التشخيص يقوم به المختص ولا يُؤخذ من قوائم الإنترنت. "
            "التقييم المبكر يفتح باب الدعم المناسب."
        ),
        "labels": ["adhd", "إحالة", "تشخيص", "dsm-5"],
    },
    # ─────────────── Autism (medical) ───────────────
    {
        "slug": "autism-0-3-early-signs",
        "domain": "medical", "age_group": "0-3",
        "behavior_type": "التوحد",
        "intervention_type": "إرشادي", "severity": "متوسط",
        "reference_type": "DSM-5",
        "reference_info": "CDC Learn the Signs · Act Early; M-CHAT-R",
        "text_original": (
            "Early signs that may warrant developmental screening include limited "
            "eye contact, not responding to name by 12 months, lack of joint "
            "attention (pointing/showing), and loss of previously gained skills "
            "(CDC). The M-CHAT-R is a validated parent screening tool for 16–30 months."
        ),
        "text_simplified": (
            "من العلامات المبكرة التي تستدعي المتابعة: قلّة التواصل بالعين، عدم الالتفات "
            "عند مناداته باسمه بعد عمر سنة، عدم الإشارة أو مشاركة الاهتمام، أو فقدان مهارات "
            "كان قد اكتسبها. هذه علامات للمتابعة وليست تشخيصاً. التدخّل المبكر مفيد جداً، "
            "فلا تنتظر — استشر مختص نمو الطفل عند القلق."
        ),
        "labels": ["autism", "توحد", "cdc", "علامات_مبكرة"],
    },
    {
        "slug": "autism-4-6-support",
        "domain": "medical", "age_group": "4-6",
        "behavior_type": "التوحد",
        "intervention_type": "إرشادي", "severity": "متوسط",
        "reference_type": "تقرير_طبي",
        "reference_info": "CDC; WHO Caregiver Skills Training",
        "text_original": (
            "Structured routines, visual schedules, clear simple language, and "
            "following the child's interests support communication and reduce "
            "anxiety in autistic children (WHO/CDC). Early intervention services "
            "improve long-term outcomes."
        ),
        "text_simplified": (
            "الطفل على طيف التوحد يرتاح مع الروتين الثابت والجداول المصوّرة واللغة البسيطة "
            "الواضحة. ابنِ التواصل انطلاقاً من اهتماماته هو، وامنحه وقتاً للاستجابة. قلّل "
            "المثيرات الحسّية الزائدة (الضوضاء/الإضاءة). برامج التدخّل المبكر تُحسّن النتائج "
            "على المدى الطويل، فالتحق بها مبكراً."
        ),
        "labels": ["autism", "توحد", "تدخل_مبكر", "who"],
    },
    {
        "slug": "autism-4-6-referral",
        "domain": "medical", "age_group": "4-6",
        "behavior_type": "التوحد",
        "intervention_type": "إحالة_لطبيب", "severity": "شديد",
        "reference_type": "DSM-5",
        "reference_info": "DSM-5 ASD criteria; CDC Act Early",
        "text_original": (
            "Persistent deficits in social communication plus restricted/repetitive "
            "behaviors present in early development and causing impairment warrant "
            "comprehensive evaluation by a developmental specialist (DSM-5)."
        ),
        "text_simplified": (
            "إذا لاحظت صعوبات مستمرة في التواصل الاجتماعي مع سلوكيات متكرّرة أو اهتمامات "
            "محدودة جداً تؤثر على حياة طفلك — اطلب تقييماً شاملاً من أخصائي نمو الطفل. "
            "التقييم لا يعني وصمة، بل خطة دعم. كلما كان أبكر كان أفضل لتطوّر الطفل."
        ),
        "labels": ["autism", "توحد", "إحالة", "dsm-5"],
    },
    # ─────────────── Gaming Disorder (cyber) ───────────────
    {
        "slug": "gaming-10-12-prevention",
        "domain": "cyber", "age_group": "10-12",
        "behavior_type": "إدمان_الألعاب",
        "intervention_type": "وقائي", "severity": "خفيف",
        "reference_type": "تقرير_سيبراني",
        "reference_info": "AAP Family Media Plan; WHO",
        "text_original": (
            "Preventive guidance: agree on a family media plan with consistent time "
            "limits, screen-free zones (meals, bedrooms, before sleep), and balance "
            "with sleep, physical activity, and offline relationships (AAP)."
        ),
        "text_simplified": (
            "للوقاية من الإفراط في الألعاب: اتفقوا كعائلة على خطة واضحة لوقت الشاشة، "
            "وحدّدوا أوقاتاً وأماكن خالية من الأجهزة (الطعام، غرفة النوم، قبل النوم). "
            "احرص على توازن الألعاب مع النوم الكافي والنشاط البدني والعلاقات الواقعية. "
            "كن قدوة في استخدامك أنت للأجهزة."
        ),
        "labels": ["gaming", "إدمان_ألعاب", "aap", "وقاية"],
    },
    {
        "slug": "gaming-13-15-signs",
        "domain": "cyber", "age_group": "13-15",
        "behavior_type": "إدمان_الألعاب",
        "intervention_type": "إرشادي", "severity": "متوسط",
        "reference_type": "تقرير_سيبراني",
        "reference_info": "WHO ICD-11 Gaming Disorder (6C51)",
        "text_original": (
            "ICD-11 describes Gaming Disorder as impaired control over gaming, "
            "increasing priority given to gaming over other activities, and "
            "continuation despite negative consequences, typically over 12 months "
            "and causing significant impairment (WHO)."
        ),
        "text_simplified": (
            "حسب منظمة الصحة العالمية، علامات الاستخدام المُشكِل للألعاب: فقدان السيطرة على "
            "وقت اللعب، تقديم اللعب على الدراسة والنوم والأصدقاء، والاستمرار رغم الضرر "
            "الواضح. تحدّث مع ابنك بهدوء بلا مواجهة، اتفقا على حدود متدرّجة، وعزّز بدائل "
            "ممتعة. المنع المفاجئ الكامل غالباً يأتي بنتيجة عكسية."
        ),
        "labels": ["gaming", "إدمان_ألعاب", "icd-11", "who"],
    },
    {
        "slug": "gaming-13-15-referral",
        "domain": "cyber", "age_group": "13-15",
        "behavior_type": "إدمان_الألعاب",
        "intervention_type": "إحالة_لطبيب", "severity": "شديد",
        "reference_type": "تقرير_طبي",
        "reference_info": "WHO ICD-11; AAP mental-health guidance",
        "text_original": (
            "When gaming significantly impairs sleep, school, mood, or family "
            "functioning despite consistent limits, evaluation by a mental-health "
            "professional is recommended; co-occurring anxiety or depression is common."
        ),
        "text_simplified": (
            "إذا أضرّ اللعب بشكل كبير بنوم ابنك أو دراسته أو مزاجه أو علاقاته رغم وضع حدود "
            "ثابتة، فيُنصح باستشارة أخصائي نفسي. كثيراً ما يصاحب الإفراط قلقٌ أو اكتئاب يحتاج "
            "دعماً. اطلب المساعدة مبكراً بدل انتظار تفاقم المشكلة."
        ),
        "labels": ["gaming", "إدمان_ألعاب", "إحالة", "صحة_نفسية"],
    },
]


def main() -> int:
    written = 0
    for u in UNITS:
        uid = str(uuid.uuid5(NS, u["slug"]))
        unit = {
            "id": uid,
            "domain": u["domain"],
            "age_group": u["age_group"],
            "behavior_type": u["behavior_type"],
            "intervention_type": u["intervention_type"],
            "severity": u["severity"],
            "reference_type": u["reference_type"],
            "reference_info": u["reference_info"],
            "text_original": u["text_original"],
            "text_simplified": u["text_simplified"],
            "labels": u["labels"],
            "created_at": TS,
            "updated_at": TS,
            "version": "1.0.0",
        }
        path = UNITS_DIR / f"{uid}.json"
        path.write_text(json.dumps(unit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
        print(f"  ✓ {u['domain']:18s} {u['behavior_type']:30s} {u['age_group']:6s} {uid}")
    print(f"\n  Wrote {written} units → {UNITS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
