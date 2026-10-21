# قالب: داعية جديد في موجة رمضان (`DA13`… / `EN06`…)

وكيل الحملة تواصل مع أسماء بأكواد حتى `DA19`/`EN10`، لكن قائمتها ليست في المستودع. لكل اسم منها:

1. **الكود في السجلّ أولًا:** اكتبوا الخانة في `docs/marketing/campaign_codes.md` (الاسم يبقى في ملاحظات خالد المحلية لا هنا).
2. **المجلد:** `mkdir DA13_<slug>` ثم انسخوا `message.txt` (أو `message_en.txt`) من هنا واملؤوا كل `{…}`.
3. **الموضوع:** اختاروا من `../_build/topics.json` ما يطابق تخصصه — كلها جاهزة بالعربية:
   `ramadan_teen` · `ramadan_akhlaq` · `ramadan_family` · `fasting_ladder_love` · `ramadan_phone` · `ramadan_10_12` ·
   `fasting_safety` · `ramadan_little_ones` · `ramadan_prepare` · `ramadan_stories` · `ramadan_last_ten` · `ramadan_7_9`،
   وبالإنجليزية: `ramadan_akhlaq_en` · `first_fasts_en` · `last_ten_en` · `ramadan_7_9_en` · `fasting_safety_en`.
   - وإن لم يطابقه موضوع، فأضيفوا موضوعًا: النص منقول من `knowledge_base/curriculum/programs/ramadan_family.json`، والمصدر في `source`، بلا آيات ولا أحاديث.
4. **الرسم:** أضيفوا المجلد إلى `../_build/packages.json` ثم:
   ```
   python3 docs/marketing/2027-01-ramadan-preachers/_build/render.py DA13_<slug>
   ```
   يكتب `infographic.svg` و`infographic.png` (1080×1350).
5. **المنشور:** انسخوا `post_ar.txt` من حزمة بالموضوع نفسه، وغيّروا الكود في الرابط فقط: `https://tg-api.alsaba.cloud/go?ref=DA13`.
6. **اللقطات:** ٣–٤ من `docs/brand/store/listing_1.0.73/ar/` (أو `en/`)، و`phone_07_ramadan_street.png` أولًا دائمًا.
7. **قبل الـcommit:** `bash .githooks/pre-commit`، وفحص النصوص بـ`scripture_scan.scan_text` (الأمر في `../README.md`).
