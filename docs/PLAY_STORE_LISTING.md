# المربّي الذكي — حزمة ASO كاملة (Play Console)

> **مصدر الحقيقة من 1.0.73 «نور والقناديل»:** `docs/brand/store/listing_1.0.73/listing.json`
> (العنوان والوصفان بالعربية وen-US) + الصور في `docs/brand/store/listing_1.0.73/{ar,en}/`.
> الأقسام ١–٣ والقائمة الإنجليزية تحت منسوخة منه — **عدّل الملف أولًا ثم انسخ هنا.**
> الرفع: `scripts/play_listing_upload.py` — `--validate-only` آمن ويُعاد، و`--commit` وقت الإصدار فقط
> (بعد commit تعديل الإصدار نفسه، لأن commit أي edit يُبطل الـedits المفتوحة الأخرى).
>
> ```bash
> PLAY_SERVICE_ACCOUNT=~/projects/tutor-guardian/scripts/play_service_account.json \
>   python3 scripts/play_listing_upload.py --commit; echo "rc=$?"
> ```
> لو مرّرت الناتج في `tee`/`tail` فاقرأ `${PIPESTATUS[0]}` لا `$?`.

### لقطات 1.0.73 — ٨ لكل لغة، لقطات CI حقيقية في إطارات «ورق مقصوص»

مولّدة بـ`docs/brand/tools/store_listing.py build` من `manifest.json` (رقم التشغيل والملف وبصمته لكل لقطة).
التعديل الوحيد على أي لقطة قصّ لوحة المفاتيح من لقطة المساعد العربية.

| # | الشاشة | العنوان (ar) | Headline (en) | الإطار |
|---|---|---|---|---|
| 1 | `today` | خطوة صغيرة كل يوم — مجاني 100% — بلا إعلانات ولا اشتراكات | One small step a day — 100% free — no ads, no subscriptions | `frame_1_rising` |
| 2 | `family_road` | درب أسرتكم — أين أنتم الآن، وما ينتظركم على الأفق | Your family road — Where you are, and what's on the horizon | `frame_2_ivory` |
| 3 | `child_corner` | ركن الطفل — حكاية أو لعبة، ثم مهمة بعيدًا عن الشاشة | A child's corner — A story or game, then a task off-screen | `frame_3_bubble` |
| 4 | `week_lanterns` | كل خطوة تضيء قنديلًا — قناديل الأسبوع — بلا مقارنة ولا لوم | Every step lights a lantern — The week's lanterns — no streaks, no comparisons | `frame_2_ivory` |
| 5 | `story_reader` | حكايات يرويها نور — وفيها وقفة حوار مع طفلكم | Stories narrated by Noor — With a pause to talk together | `frame_1_rising` |
| 6 | `noor_follow_up` | نور يتذكّر معكم — اختاروا موعد التجربة، ثم يسألكم كيف جرت | Noor remembers with you — Pick when to try it; Noor asks how it went | `frame_2_ivory` |
| 7 | `ramadan_street` | شارع القناديل في رمضان — يضيء بما تفعلونه معًا يومًا بعد يوم | A Ramadan lantern street — Lit by what you do together, day by day | `frame_1_rising` |
| 8 | `assistant` | اسألوا عن تربية طفلكم — إجابة عملية وخطوة تجرّبونها | Ask about raising your child — A practical answer, in your language | `frame_3_bubble` |

> **أول سطر في أي نسخة:** «مجاني 100% — بلا إعلانات ولا اشتراكات، مدى الحياة.»
> هذه الجملة هي أقوى ميزة تنافسية (كل المنافسين المدفوعين) وكلمة «مجاني» كلمة بحث عالية الحجم.

---

## 1) العنوان (App title — ≤ 30 حرفًا)

```
المربّي الذكي — تربية إسلامية
```

> **بدائل للاختبار A/B:**
> - `المربّي: تربية إسلامية ومساعد ذكي` ← يجمع الميزة المميزة
> - `المربّي — مساعد تربية إسلامية` ← أقصر وأوضح

---

## 2) الوصف القصير (Short description — ≤ 80 حرفًا)

```
مجاني 100%: درب تربوي يومي لأسرتك ومساعد ذكي — من الحمل حتى ١٨ سنة
```

---

## 3) الوصف الكامل — النسخة الأساسية (Full description)

> الصق هذا في Play Console → Store listing → Full description.

```
مجاني 100% — بلا إعلانات ولا اشتراكات.

«المربّي» رفيق تربوي إسلامي يسير مع أسرتكم من الحمل حتى ١٨ سنة: خطوة صغيرة كل يوم، تفهمونها وتطبّقونها مع طفلكم.

🌙 جديد: «نور والقناديل»
• «اليوم» دربٌ من ثلاث محطات تحت سماء تتبع ساعة اليوم والمواسم، برسوم الورق المقصوص.
• «درب الأسرة»: أين أنتم الآن، وما ينتظركم «على الأفق» — رمضان، ومحطات العمر، والمسار التالي.
• قناديل الأسبوع: كل خطوة تربوية تتمّونها تضيء قنديلًا، بلا عدّاد يلومكم ولا مقارنة بأحد.
• شارع القناديل في رمضان: يضيء بما تفعلونه معًا يومًا بعد يوم.
• «ركن الطفل»: حكاية قصيرة أو لعبة، ثم مهمة بعيدًا عن الشاشة. الوقت شمعة ورقية تقصر، ولا يعود الجهاز إلا برمز الأهل.
• حكايات قبل النوم يرويها نور، وفيها وقفة حوار مع الطفل.
• نور يتذكّر ما قررتم تجربته، ثم يسألكم كيف جرى.

📚 منهج لكل مرحلة عمرية
مسارات يومية متدرّجة لكل فئة عمرية (الحمل–سنة، ٢–٣، ٤–٦، ٧–٩، ١٠–١٢، ١٣–١٥، ١٦–١٨) تشمل:
• التربية الإيمانية والعبادة والأخلاق
• سلوك الطفل وعاداته اليومية
• الأمان الرقمي ووقت الشاشة
• المهارات الحياتية

💬 مساعد تربوي يجيبكم فورًا
اسألوا عن العناد، أو التهاون في الصلاة، أو التعلّق بالشاشات، أو الغيرة بين الإخوة، وستجدون إجابة عملية مبنية على مصادر موثّقة، مع خطوة واحدة تجرّبونها مع طفلكم.

🎧 محتوى بأكثر من طريقة
دروس مكتوبة، وبودكاست صوتي، وبطاقات تعليمية، واختبارات قصيرة.

📖 القرآن والأذكار
تلاوة القرآن، وأذكار وأدعية للطفل في مكان واحد.

—
ابدؤوا بسؤال واحد: «طفلي عنيد»، «طفلي لا يصلي»، «نوبات الغضب»… وستجدون خطة عملية في ثوانٍ، مجانًا.
```

> **ملاحظة سياسة المحتوى الصحي (Google Play):** هذا التطبيق تعليمي/تربوي وليس تطبيقًا صحيًا. في نموذج بيانات التطبيقات المختصة بالصحة اختر «لا توجد ميزات متعلقة بالصحة».

---

## 4) الكلمات المفتاحية المستهدفة

### كلمات فئة (Category keywords)
| الكلمة | الأهمية |
|---|---|
| تربية الأطفال | أعلى حجم بحث |
| تربية إسلامية | تميّز عن المنافسين |
| نصائح تربوية | بحث شائع |
| تربية الطفل | مرادف عالي الحجم |
| تطور الطفل | بحث ولي الأمر |
| سلوك الطفل | بحث مشكلات |
| تأديب الأطفال | بحث مباشر |
| الأبوة والأمومة | فئة عريضة |
| عادات الطفل | روتين يومي |
| أمان رقمي | مجال متخصص |
| وقت الشاشة | مشكلة حديثة |
| القرآن للأطفال | بحث ديني |
| أذكار | بحث ديني |
| أدعية | بحث ديني |
| أخلاق الطفل | بحث تربوي |
| مربي | كلمة منتج |
| الحمل | بداية الرحلة |
| الطفولة المبكرة | فئة عمرية |
| المراهقة | فئة عمرية |

### كلمات ألم (Pain-point keywords — الآباء بيدوّروا بالمشكلة)
| العبارة | السياق |
|---|---|
| ابني عنيد | مشكلة سلوكية شائعة جدًا |
| طفلي لا يصلي | تحدي ديني يومي |
| نوبات غضب الطفل | مشكلة مرتبطة بالعناد |
| الطفل يقول كلام عيب | سلوك لفظي |
| تأخر الكلام | قلق نمائي |
| خوف الطفل | مشكلة نفسية |
| الغيرة بين الإخوة | تحدي أسراعي |
| إدمان الشاشات | مشكلة رقمية |
| رفض الطعام | تحدي تغذية |
| تربية المراهق | مرحلة صعبة |
| كيف أربي ابني | بحث عام |
| العناد والعصبية | مشكلة سلوكية |
| ضرب الطفل | بحث عن حلول إيجابية |
| كذب الطفل | سلوك مقلق |
| نوم الطفل | مشكلة يومية |
| مذاكرة الطفل | قلق أكاديمي |
| تنمر أطفال | أمان رقمي/مدرسي |

---

## 5) نسخ المتجر المخصصة (Custom Store Listings)

> في Play Console: Store presence → Custom store listings
> كل نسخة تظهر للمستخدمين في الدولة المحددة فقط.

### نسخة مصر 🇪🇬

**العنوان:**
```
المربّي — تربية إسلامية مجانًا
```

**الوصف القصير:**
```
مجاني 100%: منهج تربية إسلامية شامل + مساعد ذكي يردّ عليك فورًا
```

**الوصف الكامل:**
```
مجاني بالكامل — بلا إعلانات ولا اشتراكات، مدى الحياة. صدقة جارية لوجه الله.

「المربّي الذكي」 هو أول مساعد تربية إسلامي بالذكاء الاصطناعي في مصر — يرافق طفلك من الحمل لحد ما يكمل ١٨ سنة.

📚 منهج تربوي متكامل
مسارات يومية متدرّجة لكل مرحلة عمرية — تربية إسلامية، سلوك، عادات، أمان رقمي، وقرآن. كل مسار فيه دروس + بودكاست + فيديو + اختبارات.

💬 اسأل وجاوب فورًا
ابني عنيد؟ طفلي مش بيصلي؟ نوبات غضب؟ بيدوّر على كلام في التيك توك؟
اسأل المربّي واحصل على إجابة عملية مبنية على الأدلة الشرعية — في ثوانٍ، مجانًا.

🌟 رحلة طفلك
سجّل أول صلاة، أول صيام، حفظ القرآن — وتابع تقدّمه مع الوقت.

📖 القرآن والأذكار في مكان واحد.

💡 جرّب دلوقتي: اسأل «إزاي أخلي ابني يصلي من غير عقاب؟» وشوف الفرق.
```

> **لمسة مصرية:** استخدام «إجابة» بدل «ردّ»، «ده/دي» بدل «هو/هي»، عبارة الدعوة للتجربة بلغة مصرية.

---

### نسخة السعودية 🇸🇦

**العنوان:**
```
المربّي — تربية إسلامية متكاملة
```

**الوصف القصير:**
```
مجاني 100%: منهج تربية إسلامية + مساعد ذكي يجيبك فورًا — بلا اشتراكات
```

**الوصف الكامل:**
```
مجاني بالكامل — بلا إعلانات ولا اشتراكات، مدى الحياة. صدقة جارية لوجه الله.

「المربّي الذكي» هو أول مساعد تربية إسلامي بالذكاء الاصطناعي — يرافق طفلك من الحمل حتى ١٨ سنة بمنهج متكامل.

📚 منهج تربوي شامل لكل مرحلة عمرية
مسارات يومية متدرّجة تغطي: التربية الإسلامية، الأخلاق النبوية، سلوك الطفل، العادات اليومية، الأمان الرقمي، إدارة وقت الشاشة، وحفظ القرآن.

💬 مساعد ذكي يجيبك فورًا
ابنك عنيد؟ ما يصلي؟ نوبات غضب؟ يخاف من النوم؟
اسأل المربّي واحصل على نصيحة عملية مبنية على الأدلة الشرعية الموثّقة.

🎧 محتوى غني ومتعدّد
دروس مكتوبة + بودكاست صوتي + فيديو + بطاقات تعليمية + اختبارات تفاعلية + ألعاب إسلامية.

🌟 رحلة طفلك الإيمانية
سجّل محطات نموّ طفلك — أول صلاة، أول صيام، حفظ القرآن — وتابع تقدّمه.

📖 القرآن والأذكار في مكان واحد.

💡 جرّب الآن: اسأل «كيف أجعل طفلي يحب الصلاة؟» واحصل على خطة عملية.
```

> **ملاحظة سعودية:** استخدام «طفلك» بدل «ابنك» (م Gender-neutral)، «ما يصلي» (هجاء سعودي).

---

### نسخة إنجليزية للهند 🇮🇳 (English)

**العنوان:**
```
Al-Murabbi — Islamic Parenting Guide
```

**الوصف القصير:**
```
100% FREE: Islamic parenting curriculum + AI coach — from pregnancy to 18 years
```

**الوصف الكامل:**
```
Completely FREE forever — no ads, no subscriptions, no in-app purchases. A charity for the sake of Allah.

Al-Murabbi is the first AI-powered Islamic parenting assistant that guides you from pregnancy to age 18. Not just tips — a complete curriculum with daily plans, audio lessons, stories, and an AI coach that answers your parenting questions instantly.

📚 COMPLETE PARENTING CURRICULUM
Step-by-step daily learning tracks for every age group (0–1, 2–3, 4–6, 7–9, 10–12, 13–15, 16–18) covering:
• Islamic tarbiyah and building good character (akhlaq)
• Child development, behavior, and daily habits
• Digital safety and healthy screen time
• Building life skills and responsibility

💬 AI COACH — ASK ANYTHING
"My son is defiant" · "My child won't pray" · "Anger tantrums" · "Screen addiction" · "Fear of the dark"
Get grounded, practical answers backed by Islamic sources — in seconds, completely free.

🎧 LEARN YOUR WAY
Written lessons + audio podcasts + video introductions + flashcards + quizzes — content that fits your schedule.

🌟 CHILD'S FAITH JOURNEY
Track your child's milestones: first prayer, first fast, Quran memorization — a record you'll treasure.

📖 QURAN & ADHKAR
Daily Quran recitation and Islamic supplications for children — all in one place.

🎮 INTERACTIVE GAMES
4 educational games that teach Islamic values through play.

💡 Try it now: Ask "How do I get my child to pray without force?" and see the difference.
```

> **ملاحظة للهند:** English but culturally aware — uses Islamic terms (tarbiyah, akhlaq, adhkar) with context. Targets Indian Muslim parents who consume content in English. Pain points phrased in English for search.

---

## 6) سيناريو لقطات الشاشة (Screenshot Scenarios)

> كل لقطة = **مشكلة واضحة → إجابة مؤصلة → خطة يومية** — مش مجرد شاشة من التطبيق.
> التنسيق: صورة شاشة حقيقية + شريط نص علوي بخط Cairo على خلفية تركوازية (#0D9488).
> الـPlay Console يسمح بـ8 لقطات لكل دولة.

### اللقطات الثمانية (للنسخة الأساسية — مصر)

| # | السيناريو | الشاشة الحقيقية | النص العلوي (Headline) | النص السفلي (Sub-headline) |
|---|---|---|---|---|
| 1 | **المجانية** — أول شاشة يراها المستخدم | شاشة الأونبوردنج (صفحة الترحيب مع شارة «مجاني لوجه الله») | **مجاني 100% — بلا إعلانات ولا اشتراكات** | عمل لوجه الله — للأبد |
| 2 | **ابني عنيد** — ألم يومي | شاشة المحادثة (المساعد الذكي) مع سؤال «ابني عنيد ومش بيسمع الكلام» + إجابة مؤصلة بخطوات عملية | **ابنِ عناد طفلك بذكاء** | اسأل المربّي واحصل على خطة عملية في ثوانٍ |
| 3 | **المهجة التربوية** — العمق | شاشة قائمة المسارات (الـPaths) مع مسارات مختلفة | **منهج تربية متكامل من الحمل لـ ١٨ سنة** | ٧ مراحل عمرية × ٤ مجالات = ٢٨ مسارًا |
| 4 | **البودكاست والدروس** — تنوّع المحتوى | شاشة الدرس مع تبويبات (نص + بودكاست + فيديو) | **اسمع، اقرأ، شاهد** | دروس + بودكاست + فيديو + اختبارات |
| 5 | **رحلة الطفل** — الاحتفاء بالإنجاز | شاشة Journey مع محطات (أول صلاة، أول صيام) | **سجّل رحلة نموّ طفلك الإيمانية** | أول صلاة، أول صيام، حفظ القرآن… |
| 6 | **القرآن والأذكار** — القيمة الدينية | شاشة القرآن مع قارئ + أذكار | **ركن القرآن والأذكار يوميًا** | تلاوة + أذكار + أدعية للطفل |
| 7 | **الألعاب** — التلعيب | شاشة لعبة تعليمية (أحد ألعاب Flame الأربعة) | **ألعاب تزرع القيم بالمرح** | ٤ ألعاب تفاعلية إسلامية |
| 8 | **السؤال اليومي** — لحظة الدهشة | شاشة المحادثة مع رقاقة سؤال مقترحة (مثلاً: «ابني ٥ سنين بيضرب أخته») | **اسأل أي سؤال — واجد الإجابة** | مساعد ذكي يفهم تحدياتك |

---

### اللقطات للنسخة السعودية (8 لقطات)

نفس اللقطات الأساسية مع تعديل النصوص للهججة السعودية:

| # | النص العلوي (سعودي) | النص السفلي |
|---|---|---|
| 1 | **مجاني 100% — بلا إعلانات ولا اشتراكات** | عمل خيري — للأبد |
| 2 | **التخلص من عناد طفلك بالأسلوب الصحيح** | نصيحة فورية مبنية على الأدلة الشرعية |
| 3 | **منهج تربية إسلامية شامل** | من الحمل حتى ١٨ سنة |
| 4 | **دروس + بودكاست + فيديو** | طريقة تعلم متعددة |
| 5 | **تابع مراحل نموّ طفلك** | أول صلاة، أول صيام، حفظ القرآن |
| 6 | **قرآن وأذكار طفلك في مكان واحد** | تلاوة يومية + أذكار وأدعية |
| 7 | **ألعاب إسلامية تعليمية** | ترفيه مبني على القيم |
| 8 | **اسأل وأنت متطمن** | مساعد ذكي يجاوبك فورًا |

---

### اللقطات للنسخة الإنجليزية — الهند (8 لقطات)

| # | Headline | Sub-headline |
|---|---|---|
| 1 | **100% FREE forever** | No ads, no subscriptions — ever |
| 2 | **"My son won't pray" — ask now** | Instant AI answers grounded in Islamic sources |
| 3 | **Complete curriculum: 0–18 years** | Step-by-step daily tracks for every age group |
| 4 | **Listen, read, watch, play** | Lessons + podcasts + videos + quizzes |
| 5 | **Track your child's faith journey** | First prayer, first fast, Quran milestones |
| 6 | **Daily Quran & Adhkar** | Recitation + supplications for children |
| 7 | **Islamic educational games** | 4 interactive games teaching values |
| 8 | **Parenting help in seconds** | Ask anything — get practical guidance |

---

## 7) سكريبت فيديو 30 ثانية (App Preview Video)

> في Play Console: Store listing → Video (YouTube link أو upload مباشر)
> الهدف: إظهار التطبيق فعليًا (screen recording) مع تعليق صوتي قصير.
> الجودة: 1080×1920 (عمودي)، ≤30 ثانية.

### السكريبت:

```
[0–3 ثانية] — لقطة افتتاحية
شاشة سوداء → ظهور أيقونة المربي + شعار "مجاني 100% لوجه الله"
(صوت: "هل تبحث عن تربية إسلامية حقيقية لطفلك؟")

[3–7 ثانية] — المشكلة
شاشة: والد/والدة متعبة (أو نص على شاشة الموبايل: "ابني عنيد مش بيسمع")
(صوت: "طفلك عنيد؟ لا يعرف يصلي؟ يخاف من النوم؟")

[7–14 ثانية] — الحل: المساعد الذكي
Screen recording: المستخدم يكتب سؤالاً في المساعد → إجابة عملية تظهر بسرعة
(صوت: "اسأل المربي... واحصل على إجابة عملية في ثوانٍ — مجانًا")

[14–20 ثانية] — عمق المنهج
Scroll سريع عبر: مسارات تربوية → بودكاست → اختبارات → ألعاب
(صوت: "منهج تربوي متكامل: دروس، بودكاست، فيديو، وألعاب — من الحمل لـ ١٨ سنة")

[20–25 ثانية] — رحلة الطفل
شاشة Journey: محطات "أول صلاة" → "أول صيام" → "حفظ القرآن"
(صوت: "سجّل محطات نموّ طفلك الإيمانية")

[25–28 ثانية] — القرآن والأذكار
شاشة القرآن مع تلاوة + أذكار اليوم
(صوت: "قرآن وأذكار طفلك في مكان واحد")

[28–30 ثانية] — الدعوة للتحميل
أيقونة المربي + "حمّل المربي الآن — مجاني للأبد"
(صوت: "حمّل المربي اليوم — مجاني بالكامل، صدقة جارية.")
```

### ملاحظات الإنتاج:
- **التصوير:** Screen recording حقيقي من التطبيق (Pixel 7 أو جهاز مماثل)
- **الصوت:** صوت رجالي هادئ وواضح (أو أنثوي حسب الجمهور المستهدف — يُفضل رجالي للنسخة الأساسية)
- **الموسيقى:** خلفية هادئة (Islamic ambient — مسموح بـ30 ثانية من مقطوعة مرخّصة)
- **النص على الشاشة:** مقتطفات من الأسئلة والإجابات تظهر وتختفي بتأثير fade
- **الجودة:** 1080×1920 (عمودي)، H.264، ≤30 ثانية، ≤100MB
- **الرفع:** يُرفع كفيديو YouTube خاص (unlisted) ثم يُربط بالمتجر

---

## 8) ما الجديد (What's New) — مع كل تحديث

```
✨ تحسينات جديدة:
• مساعد ذكي أسرع وأدق
• محتوى تربوي إسلامي جديد
• تحسينات في تجربة المستخدم

💬 جرّب اسأل المربي: "ابني عنيد" — وشوف الفرق.

🤍 مجاني بالكامل — بلا إعلانات ولا اشتراكات.
```

---

## 9) بيانات App Quality (Play Console)

- **التطبيق خاص بأطفال؟** → نعم (Family Policy — لا إعلانات ولا مشتريات = أبسط امتثال ممكن)
- **نوع المحتوى:** تعليمي / تربوي (NOT صحي)
- **التصنيف الفرعي:** Parenting / Education
- **العمر المستهدف:** جميع الأعمار (0–18)
- **الإباحية:** لا
- **العنف:** لا
- **المحتوى الجنسي:** لا

---

## 10) ملخص سريع للصق في Play Console

| الحقل | القيمة |
|---|---|
| **App title** | المربّي — تربية إسلامية متكاملة |
| **Short description** | مجاني 100%: منهج تربية إسلامية متكامل + مساعد ذكي — من الحمل لـ ١٨ سنة |
| **Full description** | [النص الكامل في القسم 3] |
| **Keywords** | [القائمة في القسم 4 — وزّعها طبيعيًا في الوصف] |
| **Custom listings** | 3 نسخ: مصر 🇪🇬 / السعودية 🇸🇦 / الهند 🇮🇳 |
| **Screenshots** | 8 لقطات لكل نسخة (سيناريوهات القسم 6) |
| **Video** | فيديو 30 ثانية (سكريبت القسم 7) |
| **What's new** | [النص في القسم 8 — حدّث مع كل إصدار] |
| **Data Safety** | لا يجمع بيانات شخصية · لا يشاركها · التشفير أثناء النقل |
| **Content rating** | عائلي / تعليمي (لا محتوى للبالغين) |

---

## 8) القائمة الإنجليزية (en-US) — منشورة 2026-08-21

٢٧٪ من المستخدمين على أجهزة إنجليزية و١١٪ فرنسية، وكانت صفحة Play بلغة واحدة
(`ar`) فقط: العنوان والوصف كلاهما عربي لمن لا يقرأ العربية. القائمة الإنجليزية
نُشرت عبر `androidpublisher` (`edits().listings().update(language='en-US')`)،
والصور تُورَث من القائمة العربية إذ لا صور إنجليزية بعد.

**من 1.0.73:** للقائمة الإنجليزية صورها — أيقونة وصورة مميزة إنجليزية و٨ لقطات من رحلات CI الإنجليزية
(`docs/brand/store/listing_1.0.73/en/`). لقطة المساعد الإنجليزية داكنة: لا توجد لقطة فاتحة له في الـCI.

**لم تُنشر قبل اليوم عن قصد:** المساعد كان يجيب بالعربية على السؤال الإنجليزي
حتى `0f709b09`. الإعلان بالإنجليزية قبل ذلك كان وعدًا لا يفي به التطبيق.

### العنوان (29/30)

```
Al-Morabbi: Islamic Parenting
```

### الوصف القصير (73/80)

```
100% free: a daily Islamic parenting path + AI guide, pregnancy to age 18
```

### الوصف الكامل (2177/4000)

```
100% free — no ads, no subscriptions.

Al-Morabbi is an Islamic parenting companion that walks with your family from pregnancy to age 18: one small step a day that you understand and can try with your child.

🌙 New: Noor and the Lanterns
• Today is a path of three stops under a sky that follows the hour and the seasons, in paper-cut art.
• Your family road: where you are now, and what's on the horizon — Ramadan, age milestones, the next path.
• The week's lanterns: each parenting step you complete lights a lantern. No streak to break, no comparison with anyone.
• A Ramadan lantern street for your family, lit by what you do together, day by day.
• A child's corner: a short story or game, then a task away from the screen. Time is a paper candle that burns down, and only your PIN unlocks the device again.
• Bedtime stories narrated by Noor, with a pause to talk together.
• Noor remembers what you planned to try, and later asks how it went.

📚 A curriculum for every stage
Step-by-step daily paths for each age band (pregnancy–1, 2–3, 4–6, 7–9, 10–12, 13–15, 16–18), covering:
• Faith, worship and prophetic character
• Behaviour and daily habits
• Digital safety and screen time
• Life skills

💬 An assistant that answers in your language
Ask about defiance, missed prayers, screen habits or sibling jealousy, and get a practical answer grounded in documented sources, with one small step to try with your child. Write in English and the answer comes back in English.

Qur'an and hadith are always quoted in Arabic, as revealed and as narrated, with the meaning explained alongside. A translation is never presented as scripture.

🎧 More than one way to learn
Written lessons, audio podcasts, flashcards and short quizzes. English audio is being produced lesson by lesson; the written curriculum is complete in English.

📖 Qur'an and adhkar
Recitation, and adhkar and du'a for children, in one place.

—
Start with one question: "my child is defiant", "my child won't pray", "tantrums"… and get a practical plan in seconds, free.

Note on language: the app, the curriculum, the stories and the assistant are in English. The interactive games are Arabic only for now.
```

### ما لا يجوز ادّعاؤه بالإنجليزية — تحقّق قبل أي تعديل

| البند | الحالة اليوم (2026-08-21) | مقيس بـ |
|---|---|---|
| المنهج المكتوب والمسارات | ✅ إنجليزي كامل — ٤٠ مسارًا على الفئات السبع | `GET /api/program/paths?lang=en` |
| المساعد | ✅ يجيب بلغة السؤال | مسبار حيّ بعد `0f709b09` |
| البودكاست والإنفوجرافيك | ⚠️ **جزئي** — ٧٨ ملف صوت و١١ إنفوجرافيك | عدّ الملفات على الـVPS |
| الفلاش كاردز والاختبارات | ✅ موجودة في أصول الدرس الإنجليزية | `GET /api/program/lesson-assets/{id}?lang=en` |
| الأذكار والإشعار اليومي | ❌ **عربي فقط** — `family_adhkar.ar.json` وحده | ملفات الحزمة |
| الألعاب | ❌ **عربي فقط** — وRTL فيها صحيح لا عيب | `mobile/assets/content/games/*.ar.json` وحدها |
| القصص و«ركن الطفل» وشارع رمضان | ✅ إنجليزي (1.0.73) | لقطات CI الإنجليزية في `listing_1.0.73/manifest.json` |

الصفّان الأخيران مذكوران صراحةً في آخر الوصف. **من يترجم محتوى جديدًا يحدّث هذا
الجدول والوصف معًا** — وإلا صار الوصف يعِد بما لا يوجد، أو يعتذر عمّا صار موجودًا.

**الفرنسية (١١٪) لم تُنشر:** لا يوجد محتوى فرنسي أصلًا — لا منهج ولا واجهة. قائمة
فرنسية اليوم تجلب مستخدمًا إلى تطبيق لا يقرؤه. المساعد وحده يجيب بالفرنسية لأن
القاعدة تقول «بلغة السائل» ولا تسمّي لغة.
