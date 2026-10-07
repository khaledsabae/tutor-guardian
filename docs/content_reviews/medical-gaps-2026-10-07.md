# Medical gap units: source verification, 7 October 2026

This is an automated source comparison and software review, not approval by a clinician or scholar. A reviewer fetched all 20 unique cited public-health URLs in PR #50 through the page-reading backend; all returned readable content. The following corrections were applied before integration.

| Unit | Verified correction | Primary source |
| --- | --- | --- |
| `med-80a3871c` | Remove the unsupported one-hour wait. Dark/reduced urine, unusual drowsiness, persistent dizziness on standing, rapid breathing/heartbeat and few tears require urgent assessment. Emergency symptoms retain immediate escalation. | [NHS Dehydration](https://www.nhs.uk/conditions/dehydration/) |
| `med-f8cc198a` | Distinguish general adult 21–35-day cycles from adolescent evaluation triggers: intervals shorter than 21 or longer than 45 days, counted first day to first day. Keep the three-month warning. | [AAP Menstrual Disorders in Teens](https://www.healthychildren.org/English/health-issues/conditions/genitourinary-tract/Pages/Menstrual-Disorders.aspx) |
| `med-f8cc198a` | Preserve source urgency: one soaked pad/hour for six hours, pallor, unexplained bruising/nosebleeds or prepubertal bleeding require care now; six soaked pads/day requires care within 24 hours. Ongoing severe bleeding, fainting or inability to stand retain emergency escalation. | [AAP KidsDoc Vaginal Bleeding](https://www.healthychildren.org/English/tips-tools/symptom-checker/Pages/symptomviewer.aspx?symptom=Vaginal+Bleeding) |
| `med-360b9041` | Clarify sex-specific typical onset: girls 8–13, boys 9–14. Retain early-onset and absent-onset assessment thresholds and the first-period warning by age 15. | [AAP Physical Changes During Puberty](https://www.healthychildren.org/English/ages-stages/gradeschool/puberty/Pages/Physical-Development-of-School-Age-Children.aspx), [NHS Starting Periods](https://www.nhs.uk/conditions/periods/starting-periods/) |
| `dev-7562f817` | Add testicular pain continuing at rest to the emergency triggers. | [NHS Testicle Pain](https://www.nhs.uk/symptoms/testicle-pain/) |

The same unsupported one-hour wait was removed from the Ramadan fasting ladder in both Arabic and English. Internal program files establish product context, not independent medical authority. Provenance now distinguishes model/software review from human specialist approval.

Focused regression tests initially failed against the original content; after correction, 31 passed with exit 0. Required content guards also passed. Full integration CI and deployment remain separate gates.
