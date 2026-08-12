# تقرير المراجعة الشرعية للترجمة الإنجليزية — الفئات 10-12، 13-15، 16-18

**المراجع:** مراجع شرعي مستقل  
**التاريخ:** 2026-08-12  
**النطاق:** 179 ملف (72 درس + 17 مسار + 90 نصيحة يومية)  
**المنهج:** مقارنة كل ملف إنجليزي مع أصله العربي في `knowledge_base/curriculum/lessons/`, `paths/`, `daily_tips/`  
**ملاحظة:** لم يتم تعديل أي ملف. هذا بلاغ فقط.

---

## ملخص تنفيذي

تم فحص جميع الملفات التي تحتوي محتوى دينيًا حساسًا (أحاديث، آيات، مصطلحات إسلامية، عقيدة، فقه). تم العثور على **8 اشتباهات ذات خطورة متوسطة أو عالية** تتطلب تصحيحًا، بالإضافة إلى عشرات الاشتباهات منخفضة الخطورة (تحويل «ابنك» إلى «your child» متكرر في أغلب الملفات لكنه نمط منتشر وليس تحريفًا شرعيًا).

---

## الاشتباهات مرتبة حسب الخطورة

### 🔴 خطورة عالية (HIGH) — 3 اشتباهات

---

#### 1. تحريف مصطلح: «rifq» بدلاً من «lutf» (مصطلح خاطئ)

```json
{
  "file": "daily_tips/tip_10-12_006.json",
  "field": "text",
  "issue_type": "term_error (تحريف مصطلح شرعي)",
  "arabic_text": "اسأله بلطف",
  "english_text": "Ask him with rifq (gentleness)",
  "why": "العربية تقول «بلطف» (lutf)، والترجمة نقلتها إلى «rifq» (رفق). هذا مصطلح إسلامي مختلف. الرفق غير اللطف في الاصطلاح. الترجمة تضع كلمة شرعية في فم النص لم يقلها. نفس الخطأ الذي حدث مع حديث «إن الله رفيق يحب الرفق» لكن هنا العكس: النص يقول لطف والترجمة تقول rifq.",
  "severity": "high",
  "recommended_fix": "استبدل «with rifq (gentleness)» بـ «with lutf (gentleness)» أو ببساطة «gently»."
}
```

---

#### 2. إدراج مصطلح شرعي غير موجود: «rifq» بدلاً من «بهدوء» (إضافة دينية لم يقلها الأصل)

```json
{
  "file": "daily_tips/tip_13-15_014.json",
  "field": "text",
  "issue_type": "term_error (إضافة مصطلح شرعي غير موجود في الأصل)",
  "arabic_text": "اشرح المخاطر بهدوء",
  "english_text": "explain the risks with rifq (gentleness)",
  "why": "العربية تقول «بهدوء» (calmly) — لا تذكر رفق ولا أي مصطلح شرعي. الترجمة أضافت «rifq (gentleness)» من عندها، مما يضع مصطلحًا إسلاميًا في النص لم يُكتب أصلًا. هذا تحريف بالإضافة: النص العلماني/التربوي يُفترض فيه أنه محايد، لكن الترجمة تصبغه بصبغة دينية لم يقصدها المؤلف.",
  "severity": "high",
  "recommended_fix": "استبدل «with rifq (gentleness)» بـ «calmly»."
}
```

---

#### 3. خطأ عقائدي في العنوان: «A Conscience that Watches Allah» (ضمير يراقب الله)

```json
{
  "file": "lessons/lesson_13-15_islamic_parenting_steadfast_04.json",
  "field": "title",
  "issue_type": "religious_error (خطأ عقائدي في الصياغة)",
  "arabic_text": "القدوة الداخلية: ضميرٌ يراقب الله",
  "english_text": "The Inner Exemplar: A Conscience that Watches Allah",
  "why": "الترجمة الحرفية تقلب المعنى العقائدي. العربي يقول «ضميرٌ يراقب الله» أي ضمير يستحضر مراقبة الله له (الله يراقبه هو). الإنجليزية تقول «A Conscience that Watches Allah» أي الضمير نفسه يراقب الله — وهذا معنى مقلوب لاهوتيًا. المراقب هو الله، لا أن الضمير يراقب الله. هذا يشوه مفهوم الإحسان والمراقبة. العنوان كنص تربوي يُقرأه الآباء قد يوصل عقيدة معكوسة.",
  "severity": "high",
  "recommended_fix": "استبدل بـ «A Conscience Mindful of Allah» أو «A Conscience Aware of Allah's Watchfulness»."
}
```

---

### 🟡 خطورة متوسطة (MEDIUM) — 5 اشتباهات

---

#### 4. إضافة «MashaAllah» لم يقلها الأصل (إضافة دينية)

```json
{
  "file": "lessons/lesson_10-12_medical_puberty_wellbeing_b04.json",
  "field": "try_this",
  "issue_type": "term_error (إضافة عبارة دينية غير موجودة)",
  "arabic_text": "يا سلام على قوّتك لمّا حِملت ده!",
  "english_text": "MashaAllah at your strength when you carried that!",
  "why": "الأصل العربي تعبير عامي محايد «يا سلام» (Wow). الترجمة أضافت «MashaAllah» — عبارة إسلامية لم يكتبها المؤلف. ربما ظن المترجم أنها أنسب في سياق إسلامي، لكنها إضافة ليست في الأصل. في تطبيق تربوي، إضافة عبارة دينية لم يقصد المؤلف كتابتها يمكن أن تُفهم على أنها تأصيل شرعي لموقف لم يُؤصَّل هكذا.",
  "severity": "medium",
  "recommended_fix": "استبدل «MashaAllah» بـ «Wow» أو احذف المقدمة الدينية."
}
```

---

#### 5. استخدام «seerah» في سياق مهني علماني (تطبيق خاطئ لمصطلح شرعي)

```json
{
  "file": "daily_tips/tip_16-18_013.json",
  "field": "text",
  "issue_type": "term_error (استخدام مصطلح شرعي في سياق علماني)",
  "arabic_text": "بصمتك الرقمية = سيرتك المهنية",
  "english_text": "Your digital footprint = your professional seerah",
  "why": "كلمة «سيرة» هنا تعني السيرة المهنية (career/professional bio) — ليست المصطلح الإسلامي «Seerah» (سيرة النبي ﷺ). نقلها صوتيًا كـ «seerah» يوهم القارئ الإنجليزي أنها مصطلح إسلامي. في سياق نصيحة عن LinkedIn وGitHub، هذا مضلل ويطبق مصطلحًا دينيًا على أمر دنيوي محض.",
  "severity": "medium",
  "recommended_fix": "استبدل «your professional seerah» بـ «your professional profile» أو «your career story»."
}
```

---

#### 6. ترجرة العناوين كنقل صوتي فقط (فقدان المعنى بالكامل)

```json
{
  "file": "paths/path_10-12_aqeedah_growth.json",
  "field": "title",
  "issue_type": "meaning_change (عنوان منقول صوتيًا بلا ترجمة)",
  "arabic_text": "ترسيخ العقيدة: من المعرفة إلى المراقبة",
  "english_text": "Tarsikh al-ʿAqeedah: min al-Maʿrifah ilá al-Muraqabah",
  "why": "العنوان الإنجليزي مجرد نقل صوتي للحروف العربية. قارئ إنجليزي لا يفهم شيئًا. الأصل يقول «Establishing the Creed: From Knowledge to Watchfulness». نفس المشكلة تظهر في ملفات أخرى:\n- paths/path_10-12_islamic_parenting_worship_love.json → «Al-'Ibadah 'an Muhabbah: min al-'Adah ila al-Qalb»\n- lessons/lesson_10-12_aqeedah_growth_03.json → «Al-Qada' wal-Qadar: Al-Rida wal-Tawakkul»\n- lessons/lesson_10-12_islamic_parenting_identity_02.json → «Al-Qur'an: Dustur al-Hayah wa Busulah al-Murahiqa»\n- lessons/lesson_16-18_islamic_parenting_adult_faith_02.json → «Al-'iffah wa al-isti'dad li al-zawaj: hiwar sarīḥ bilā khajal»",
  "severity": "medium",
  "recommended_fix": "أضف الترجمة الإنجليزية بين قوسين أو بدل النقل الصوتي بالترجمة، مثلاً: «Establishing the Creed: From Knowledge to Watchfulness (Tarsikh al-ʿAqeedah)»."
}
```

---

#### 7. تحويل «رضا» (rida = contentment) إلى «accept» (استسلام)

```json
{
  "file": "lessons/lesson_10-12_aqeedah_growth_03.json",
  "field": "summary",
  "issue_type": "meaning_change (إضعاف مفهوم عقائدي)",
  "arabic_text": "نرضى بما قدّر",
  "english_text": "accept what He has decreed",
  "why": "العربية تقول «نرضى» (we are content/pleased) — وهذا هو مفهوم الرضا (rida) وهو مقصد عقدي مركزي في عنوان الدرس. الترجمة «accept» تُضعفه إلى مجرد القبول/الاستسلام، فاقدةً المعنى الروحي للرضا. العنوان نفسه يقول «Al-Rida wal-Tawakkul» لكن المتن يترجم الرضا إلى accept.",
  "severity": "medium",
  "recommended_fix": "استبدل «accept what He has decreed» بـ «be content with what He has decreed»."
}
```

---

#### 8. تغيير صيغة الخطاب من المثنى إلى المفرد/المبهم

```json
{
  "file": "lessons/lesson_13-15_islamic_parenting_teen_identity_02.json",
  "field": "try_this",
  "issue_type": "meaning_change (فقدان التثنية)",
  "arabic_text": "اختارا سورة قصيرة",
  "english_text": "Choose a short surah",
  "why": "العربية تستخدم صيغة المثنى «اختارا» (الأب والابن معًا). الإنجليزية «Choose» مبهمة وممكن تُقرأ كأنها موجهة للأب وحده. هذا يتكرر في دروس أخرى بصيغ المثنى (استخدما، ابحثا، ناقشا) في الفئات 13-15 و16-18. فقدان التثنية يُضعف المعنى التربوي التعاوني.",
  "severity": "medium",
  "recommended_fix": "استبدل «Choose» بـ «Choose together with your child» أو «You and your child: choose»."
}
```

---

### 🟡 خطورة متوسطة — اشتباه إضافي مكتشف بالمراجعة

---

#### 9. «سفينة» (ship) مترجمة «companionship» — خطأ محتمل في الأصل العربي نفسه

```json
{
  "file": "daily_tips/tip_16-18_016.json",
  "field": "text",
  "issue_type": "meaning_change (كلمة لا معنى لها في السياق)",
  "arabic_text": "مودة، نفقة، سفينة",
  "english_text": "affection, financial support, and companionship",
  "why": "كلمة «سفينة» (ship) لا معنى لها في سياق حقوق الزواج. المراجع السابق (deepseek) اقترح أنها ربما خطأ مطبعي لـ«سكينة» (tranquility). الترجمة الإنجليزية تخمّنت وترجمتها «companionship» — وهي تخمين لا يستند للنص. يجب التحقق من الأصل العربي. إذا كان المقصود «سكينة» فالترجمة الإنجليزية خاطئة (companionship ≠ tranquility). إذا كان «صحبة» فربما قريبة. لكن «سفينة» بحد ذاتها خطأ يجب رفعه للجنة العربية أولاً.",
  "severity": "medium",
  "recommended_fix": "تحقق من الأصل العربي أولاً. إذا كان «سكينة» → أصلح الإنجليزية إلى «tranquility». إذا كان «صحبة» → «companionship» مقبولة. أما «سفينة» فلا تُترك كما هي."
}
```

---

### 🟢 خطورة منخفضة (LOW) — ملاحظات متكررة (نمط عام)

التالي تكرر في أغلب الملفات (50+ ملف) لكنه ليس تحريفًا شرعيًا بل قرار ترجمة:

#### نمط: تحويل «ابنك» (your son) → «your child» (your child)

العربية تستخدم «ابنك» (your son) باستمرار، والترجمة الإنجليزية تستخدم «your child» (محايدة الجنس). هذا قرار ترجمة مقصود ربما لتعميم الجمهور، لكنه يفقد التحديد الذي في الأصل. **ليس تحريفًا شرعيًا** لكنه تغيير معنوي خفيف. يظهر في:
- lesson_10-12_islamic_parenting_worship_love_01.json
- lesson_13-15_islamic_mockery_01.json
- lesson_16-18_islamic_parenting_adult_faith_01.json
- lesson_16-18_islamic_parenting_adult_faith_04.json
- ... وأغلب الدروس

#### نمط: عناوين منقولة صوتيًا بدلاً من مترجمة

6 ملفات على الأقل (مذكورة في الاشتباه رقم 6 أعلاه) تستخدم النقل الصوتي الكامل للعنوان العربي بدلاً من الترجمة، مما يجعلها غير مفهومة لقارئ إنجليزي.

#### نقاط منخفضة أخرى:

- **lesson_10-12_aqeedah_growth_01.json**: «رسله» → «the messengers» بدلاً من «His messengers» (فقد الضمير العائد على الله) — severity: low
- **lesson_13-15_aqeedah_certainty_01.json**: «دلائل الإيمان» → «Signs of Faith» بدلاً من «Proofs of Faith» — severity: low (دلالة ≠ آية)
- **lesson_13-15_islamic_parenting_steadfast_03.json**: عدم اتساق في نقل «الإخلاص» → Al-Ikhlas / Ikhlas / ikhlas في نفس الملف — severity: low
- **lesson_10-12_islamic_parenting_identity_02.json**: «المراهق» (مذكر) → «al-Murahiqa» (مؤنث) — خطأ في الجنس — severity: low

---

## فحص الأحاديث — نتائج مفصلة

### حديث 1: «بدأ الإسلام غريبًا وسيعود غريبًا كما بدأ، فطوبى للغرباء»
**الملف:** lesson_10-12_islamic_peer_difference_01.json  
**الترجمة الإنجليزية:** «Islam began as something strange and will return to being strange as it began, so glad tidings to the strangers» (reported by Muslim)  
**الـﷺ محفوظة؟** نعم ✅  
**أمانة المعنى؟** مطابق ✅ — الترجمة صحيحة ومعنى الحديث محفوظ. «طوبى» → «glad tidings» مقبول.  
**الراوي:** «reported by Muslim» — صحيح (رواه مسلم).  
**الحكم:** لا اشتباه.

### حديث 2: «سبعة يظلهم الله في ظله يوم لا ظل إلا ظله» — ومنهم «شابٌّ نشأ في عبادة الله»
**الملف:** lesson_13-15_islamic_mockery_01.json  
**الترجمة الإنجليزية:** «Seven whom Allah will shade in His shade on the Day when there is no shade except His shade»—among them, «a youth who grew up in the worship of Allah» (reported by al-Bukhari)  
**الـﷺ محفوظة؟** نعم ✅  
**أمانة المعنى؟** مطابق ✅ — «شاب نشأ في عبادة الله» → «a youth who grew up in the worship of Allah» صحيح.  
**الراوي:** «reported by al-Bukhari» — صحيح (رواه البخاري).  
**الحكم:** لا اشتباه.

### حديث 3 (إشارة): أمر النبي ﷺ بتعويد الصلاة من 7 سنوات
**الملف:** lesson_13-15_islamic_mockery_01.json  
**الترجمة الإنجليزية:** «The Prophet ﷺ commanded fathers to train their children in Salah from the age of seven and to follow up firmly from the age of ten (reported by Abu Dawud and authenticated by al-Albani).»  
**الأصل العربي:** «وأمر النبي ﷺ الآباء بتعويد أبنائهم على الصلاة من سن السابعة والمتابعة الحازمة من سن العاشرة (رواه أبو داود وصححه الألباني).»  
**الـﷺ محفوظة؟** نعم ✅  
**أمانة المعنى؟** مطابق ✅  
**الراوي والتحقيق:** «reported by Abu Dawud and authenticated by al-Albani» — صحيح (رواه أبو داود، وصححه الألباني).  
**الحكم:** لا اشتباه.

### ملاحظة على حديث رفع الأيدي: لم أجد في الملفات المفحوصة أي حديث مرفوع أو ضعيف ينسب للنبي ﷺ بلا سند. جميع الأحاديث منسوبة لمصادرها بشكل صحيح.

---

## فحص الآيات القرآنية — نتائج مفصلة

### آية 1: سورة الحجرات 11
**الملف:** lesson_10-12_islamic_peer_difference_01.json  
**النص العربي:** «يَا أَيُّهَا الَّذِينَ آمَنُوا لَا يَسْخَرْ قَوْمٌ مِّن قَوْمٍ عَسَىٰ أَن يَكُونُوا خَيْرًا مِّنْهُمْ»  
**الترجمة الإنجليزية:** «O you who have believed, let not a people ridicule [another] people; perhaps they may be better than them»  
**المقارنة مع Saheeh International:** Saheeh International: «O you who have believed, let not a people ridicule [another] people; perhaps they may be better than them.»  
**الحكم:** مطابق لـ Saheeh International ✅. لا اشتباه.

### آية 2: سورة المطففين 29-34 (إشارة)
**الملف:** lesson_13-15_islamic_mockery_01.json  
**النص العربي (اقتباس جزئي):** «فَالْيَوْمَ الَّذِينَ آمَنُوا مِنَ الْكُفَّارِ يَضْحَكُونَ»  
**الترجمة الإنجليزية:** «So today those who believed are laughing at the disbelievers»  
**المقارنة مع Saheeh International:** Saheeh International: «So today those who believed are laughing at the disbelievers.»  
**الحكم:** مطابق لـ Saheeh International ✅. لا اشتباه.

### آية 3: دعاء «قدّر الله وما شاء فعل»
**الملف:** lesson_10-12_aqeedah_growth_03.json  
**النص العربي:** «قدّر الله وما شاء فعل»  
**الترجمة الإنجليزية:** «Qaddar Allahu wa ma sha'a fa'al (Allah has decreed, and He does what He wills)»  
**الحكم:** ترجمة المعنى صحيحة ✅. النقل الصوتي محفوظ مع الترجمة بين قوسين. لا اشتباه.

### ملاحظة عامة على الآيات: جميع الآيات المذكورة مطابقة لترجمة Saheeh International أو قريبة جدًا. لم أعثر على أي آية محرفة أو مغيّرة.

---

## فحص المصطلحات الإسلامية — نتائج مفصلة

| المصطلح | النقل الصوتي المستخدم | صحيح؟ | ملاحظات |
|---------|----------------------|-------|---------|
| tarbiyah | tarbiyah | ✅ | صحيح، مستخدم في lesson_13-15_islamic_parenting_steadfast_04 و tip_16-18_018 |
| akhlaq | akhlaq | ✅ | صحيح، مستخدم في tip_16-18_018 و tip_16-18_016 |
| adhkar | — | — | لم يظهر في ملفات الفئات المفحوصة |
| fitrah | fitrah | ✅ | صحيح، مستخدم في lesson_13-15_aqeedah_certainty_01 و tip_16-18_016 |
| rifq | rifq | ⚠️ | **مشكلة**: مستخدم في tip_10-12_006 و tip_13-15_014 لكن الأصل العربي يقول «لطف» و«هدوء» على التوالي — انظر الاشتباه رقم 1 و 2 |
| aqeedah | aqeedah / ʿaqeedah | ✅ | صحيح، مستخدم باستمرار (مع عدم اتساق في علامات التشكيل ʿ) |
| seerah | seerah | ⚠️ | **مشكلة**: مستخدم في tip_16-18_013 لكن في سياق مهني علماني لا علاقة له بسيرة النبي — انظر الاشتباه رقم 5 |
| khushu' | khushu' | ✅ | صحيح، مستخدم في عدة دروس |
| ikhlas | ikhlas / Al-Ikhlas | ⚠️ | عدم اتساق في الكتابة داخل نفس الملف (lesson_13-15_islamic_parenting_steadfast_03) |
| muraqabah | muraqabah | ✅ | صحيح |
| ihsan | ihsan | ✅ | صحيح، لكن العنوان الذي يستخدمه مشكل (الاشتباه 3) |
| taklif | taklif | ⚠️ | مترجم «responsibility» بدلاً من «legal obligation/moral accountability» — المعنى الشرعي أضعف |
| taqlid | taqlid | ✅ | صحيح |
| yaqeen | yaqeen | ✅ | صحيح |
| tawakkul | tawakkul | ✅ | صحيح |
| du'a | du'a | ✅ | صحيح |
| deen | deen | ✅ | صحيح |
| birr al-walidayn | birr al-walidayn | ✅ | صحيح |
| qudwah | qudwah | ✅ | صحيح، مع شرح (role model) |
| wird | wird | ✅ | صحيح، مع شرح (portion) |
| tadabbur | tadabbur | ✅ | صحيح |
| istiqamah | istiqamah | ✅ | صحيح |
| 'iffah | 'iffah | ✅ | صحيح، مع شرح (chastity) |
| haya | haya | ✅ | صحيح، مع شرح (modesty) |
| ikhtilat | ikhtilat | ✅ | صحيح، مع شرح (mixing) |
| mahram | mahram | ✅ | صحيح |
| khalwah | khalwah | ✅ | صحيح، مع شرح (seclusion) |
| shar'i | shar'i | ✅ | صحيح، مع شرح (legal) |
| niyyah | niyyah | ✅ | صحيح، مع شرح (intention) |
| itqan | itqan | ✅ | صحيح، مع شرح (excellence) |
| ummah | ummah | ✅ | صحيح |

---

## توصيات عامة

1. **أصلح الـ3 اشتباهات عالية الخطورة فورًا** (الأرقام 1-3): مصطلح rifq الخاطئ في نصين، والعنوان العقائدي المعكوس.
2. **أصلح الـ5 اشتباهات متوسطة الخطورة** (الأرقام 4-9): إضافة MashaAllah، seerah في سياق مهني، عناوين منقولة صوتيًا، إضعاف مفهوم الرضا، فقدان التثنية.
3. **تحقق من «سفينة» في tip_16-18_016** — ارفعه للجنة العربية لتحديد الكلمة الصحيحة.
4. **وحّد نقل المصطلحات**: ikhlas تظهر Al-Ikhlas / Ikhlas / ikhlas — يجب توحيد الصيغة.
5. **ترجم العناوين المنقولة صوتيًا**: 6 ملفات على الأقل لها عناوين لا يفهمها قارئ إنجليزي.
6. **النمط المتكرر لـ«ابنك» → «your child»** ليس تحريفًا شرعيًا لكنه قرار يجب توثيقه وتطبيقه باتساق.

---

*تم إعداد هذا التقرير كبلاغ فقط. لم يتم تعديل أي ملف.*