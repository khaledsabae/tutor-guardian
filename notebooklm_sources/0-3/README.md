# مصادر NotebookLM — منهج 0-3

هذا المجلد يحتوي على **14 ملف مصدر** معدّة للرفع على **Google NotebookLM** لتوليد **Audio Overview بالعربية** (بودكاست MP3) لكل درس من دروس المرحلة 0-3.

## الاستخدام
1. افتح [notebooklm.google.com](https://notebooklm.google.com)
2. أنشئ نوتبوك جديد لكل درس (أو ادمج عدة دروس)
3. ارفع ملف الـ`.md` الخاص بالدرس (Source)
4. اضغط **Audio Overview** → **Generate** → اختر **Arabic** كلغة الإخراج
5. انزّل الـMP3 وارفعه على Cloudflare R2
6. حدّث `lesson-assets` endpoint في الباك إند برابط الـCDN

## قائمة المصادر
| الدرس | الملف |
|-------|-------|
| medical_early_milestones / 01 | `lesson_0-3_medical_early_milestones_01.md` |
| medical_early_milestones / 02 | `lesson_0-3_medical_early_milestones_02.md` |
| medical_early_milestones / 03 | `lesson_0-3_medical_early_milestones_03.md` |
| medical_early_milestones / 04 | `lesson_0-3_medical_early_milestones_04.md` |
| islamic_parenting_attachment / 01 | `lesson_0-3_islamic_parenting_attachment_01.md` |
| islamic_parenting_attachment / 02 | `lesson_0-3_islamic_parenting_attachment_02.md` |
| islamic_parenting_attachment / 03 | `lesson_0-3_islamic_parenting_attachment_03.md` |
| islamic_parenting_attachment / 04 | `lesson_0-3_islamic_parenting_attachment_04.md` |
| cyber_screen_foundations / 01 | `lesson_0-3_cyber_screen_foundations_01.md` |
| cyber_screen_foundations / 02 | `lesson_0-3_cyber_screen_foundations_02.md` |
| cyber_screen_foundations / 03 | `lesson_0-3_cyber_screen_foundations_03.md` |
| development_early_moments / 01 | `lesson_0-3_development_early_moments_01.md` |
| development_early_moments / 02 | `lesson_0-3_development_early_moments_02.md` |
| development_early_moments / 03 | `lesson_0-3_development_early_moments_03.md` |

## بوابات الجودة
- ✅ 14/14 ملف نظيف من CJK/Cyrillic
- ✅ 14/14 ملف يطابق منهج المنهج 0-3 (summary + try_this + reflection)
- ✅ جميع المراجع والوحدات حقيقية من `knowledge_base/units/`

## ملاحظات
- هذه الملفات مخصصة للنوتبوك الأداة فقط — **لا تُـcommit** لمحتوى MP3 النهائي في git (مستضاف على R2)
- الملفات `*.md` نفسها آمنة للـcommit (محتوى نصي صغير)
- `kaggle_logs_*.txt` و `ops/data/kaggle_*` مُتجاهَلة في `.gitignore`
