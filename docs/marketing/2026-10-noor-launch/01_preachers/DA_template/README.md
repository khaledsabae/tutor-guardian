# قالب حزمة داعية جديد (`DAxx_<slug>/`)

لكل اسم جديد من بحث خالد. الوصفة نفسها التي نجحت مع د. هيثم طلعت (انظر `../README.md`).

## الخطوات

1. **انسخوا القالب:** `cp -r DA_template DA07_<slug>`.
   - أعطوه أول كود `DA` غير مستعمل في `../README.md`.
   - إن كان جمهوره بالإنجليزية فله أيضًا كود `EN` غير مستعمل.
2. **تحقّقوا من صفحاته العامة** واكتبوا `notes.md` على مثال `DA02_fadel_soliman/notes.md`، وفيه:
   - الروابط والحجم، والتخصص بدليل
   - أي حساسية تحتاج قرار خالد
   - التوقيت
   - **بيانات عامة فقط:** لا هواتف ولا عناوين.
3. **اختاروا موضوعًا من بنك الإنفوجراف** في `../../_build/infographics.json` يطابق تخصصه.
   - المتاح الآن: `ramadan_teen`، و`teen_doubts`، و`teen_identity`، و`prayer_journey`، و`tantrums_2_3`، و`akhlaq_7_9`، و`aqeedah_seeds_4_6`، و`screens_7_9`، و`puberty_10_12`، و`ramadan_family`، و`child_faith_questions`، و`child_faith_questions_en`، و`teen_prayer_ownership`، و`emotions_7_9`، و`ramadan_family_en`.
   - نسخ مرسومة منها كلها في `scratch/launch/infographic_bank/`.
   - وإن لم يطابقه موضوع، فأضيفوا موضوعًا جديدًا إلى الـJSON. النص منقول من درس أو برنامج حقيقي في `knowledge_base/curriculum/`، والمصدر يُكتب في `source`، وبلا آيات ولا أحاديث إن أمكن.
   - ثم ارسموه:
     ```
     python3 docs/marketing/2026-10-noor-launch/_build/render_infographics.py --out-dir /tmp/ig <topic>
     cp /tmp/ig/<topic>.png docs/marketing/2026-10-noor-launch/01_preachers/DA07_<slug>/infographic.png
     ```
4. **انسخوا ٣–٤ لقطات تناسب الموضوع** إلى `screenshots/`، من قائمة المتجر.
   - استعملوا `origin/main` بعد دمج PR #135 فقط. قبل دمجه استعملوا `origin/noor/store-capture`، فالنسخة التي على main أقدم وليس فيها `phone_08_family_programs`.
   ```
   git show origin/main:docs/brand/store/listing_1.0.73/ar/<name>.png > DA07_<slug>/screenshots/<name>.png
   ```
   الأسماء المتاحة: `phone_01_today`، و`phone_02_family_road`، و`phone_03_child_corner`، و`phone_04_week_lanterns`، و`phone_05_story_reader`، و`phone_06_noor_follow_up`، و`phone_07_ramadan_street`، و`phone_08_family_programs`.
5. **املؤوا `message.txt` و`post_ar.txt`** واحذفوا كل `{…}`، واستبدلوا `DAxx` بالكود.
6. **راجعوا القواعد** قبل الـcommit، ثم شغّلوا `bash .githooks/pre-commit`:
   - فصحى سهلة
   - مخاطبة الأهل لا الأم وحدها
   - بلا وعد بأجر
   - بلا مقارنة مع تطبيقات أخرى أو بين أطفال
   - ركن الطفل = حكاية ثم مهمة بعيدًا عن الشاشة، لا لعبة
   - **لا اسم لخالد**
   - لا أرقام غير مقيسة
