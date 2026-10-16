# قوالب الرد على تقييمات Play + رسالة التبرّع والشفافية

> العلامات ⏳ معرّفة في [`00_README.md`](00_README.md). خالد يلصق الرد بنفسه في Play Console؛ لا ردّ آلي
> (اقتراح وكيل المسودات في `plans/review-reply-agent-proposal.md` ما زال قرارًا معلّقًا).
> **(2026-10-16)** حُدّثت لهوية «نور والقناديل»: التوقيع «— المربّي» بدل الاسم، والمخاطبة بالجمع، وأُعيد عدّ الحروف.

## ١. قواعد الرد

1. **خلال ٤٨ ساعة** من المراجعة، وكل يوم في الموسم (١٥ يناير → ١٥ مارس). `scripts/play_reviews.py` يرى آخر ٧ أيام فقط — فلا تتأخر.
2. **حد Play للرد ٣٥٠ حرفًا.** كل قالب أدناه محسوب بجانبه (`len` في Python).
3. **بلغة المراجعة:** عربية ← رد عربي فصيح سهل (الرد نص عام على صفحة المتجر)؛ إنجليزية ← إنجليزي؛ فرنسية ← القالب الفرنسي القصير.
4. **خصّص سطرًا واحدًا على الأقل** باسم ما ذكره المراجع — القالب نقطة بداية لا لصق أعمى.
5. **لا وعود بمواعيد، ولا جدال، ولا أحكام شرعية، ولا وعد بأجر**، ولا ذكر لميزة ⏳ لم تُشحن.
6. **لا تطلب من أحد تغيير تقييمه.** إن أصلحنا ما اشتكى منه، نحدّث الرد نفسه ونقول ذلك؛ وهو يقرر.
7. **لا بيانات شخصية** في الرد، ولا تطلب منه رقمًا أو بريدًا علنًا — التواصل الخاص عبر زر «أرسل ملاحظاتك».
8. التوقيع «— المربّي» / "— Al-Morabbi" (2026-10-16): لا يُذكر اسم خالد في أي نص عام (`00` §٢.٧). كان التوقيع «— خالد».
9. المخاطبة بالجمع («جزاكم الله خيرًا»، «طفلكم») لأن المراجِع قد يكون أبًا أو أمًّا، وصوت الأسرة واحد.

أسماء الأزرار مطابقة لملفات الترجمة اليوم: «أرسل ملاحظاتك» / "Send Feedback" (`sendFeedback`)، «إشعارات أذكار الأسرة» /
"Family Adhkar Notifications" (`settingsFamilyAdhkar` — مفتاح الإشعارات الوحيد في الإعدادات مع الورد)، «سياسة الخصوصية» /
"Privacy Policy"، شاشة «اليوم» / "Today". إن تغيّرت في التطبيق تُغيَّر هنا.

## ٢. القوالب

### R1 — ٥★ شكر عام

```
جزاكم الله خيرًا على كلماتكم الطيبة. يسعدنا أن المربّي نفعكم ونفع أسرتكم. وإن خطرت لكم فكرة تجعله أنفع، فاكتبوها لنا من زر «أرسل ملاحظاتك» داخل التطبيق؛ نقرأ كل رسالة. — المربّي
```
_177/350_

```
JazakAllahu khayran for your kind words. We're glad Al-Morabbi is helping your family. If you have an idea that would make it more useful, send it from the Send Feedback button in the app — every message is read. — Al-Morabbi
```
_225/350_

### R2 — ٥★ يذكر ميزة بعينها

```
شكرًا لكم! سعدنا أن [الميزة] أفادتكم مع طفلكم. وأي فكرة ترسلونها من زر «أرسل ملاحظاتك» في التطبيق تصل إلينا مباشرة. — المربّي
```
_125/350_

```
Thank you! We're happy [feature] has helped with your child. Any idea you send from the Send Feedback button in the app reaches us directly. — Al-Morabbi
```
_153/350_

### R3 — ٤★ مع اقتراح

```
شكرًا على التقييم وعلى اقتراحكم عن [الاقتراح]. سجّلناه، ولا نعدكم بموعد قبل أن نتأكد أنه سينفع الأسر فعلًا. إن أحببتم أن تشرحوا أكثر، فزر «أرسل ملاحظاتك» في التطبيق يصلنا مباشرة. — المربّي
```
_188/350_

```
Thanks for the rating and for suggesting [suggestion]. It's noted. We won't promise a date until we're sure it will truly help families. If you'd like to explain more, the Send Feedback button in the app reaches us directly. — Al-Morabbi
```
_237/350_

### R4 — ٣★ «لا أعرف من أين أبدأ»

```
شكرًا لصراحتكم، وهذه أكثر ملاحظة نسمعها. ابدؤوا من شاشة «اليوم»: سجّلوا طفلكم ثم امشوا مع نور في محطات الدرب الثلاث، أو اكتبوا للمربّي مشكلة واحدة تشغلكم الآن. ونعمل على تبسيط البداية أكثر. — المربّي
```
_199/350_

```
Thank you for being honest — this is the feedback we hear most. Start from the Today screen: add your child, then walk the three stops of today's path with Noor, or tell Al-Morabbi about one thing that's on your mind. We're making the start simpler. — Al-Morabbi
```
_262/350_

### R5 — ١–٢★ عطل أو توقف

```
نعتذر عن هذا. ساعدونا لنصلحه: ما نوع هاتفكم، وفي أي شاشة حدث العطل؟ اكتبوا لنا من زر «أرسل ملاحظاتك» في التطبيق إن استطعتم فتحه، أو أضيفوا التفاصيل إلى مراجعتكم. وسنحدّث هذا الرد حين يصل الإصلاح. — المربّي
```
_205/350_

```
We're sorry about this. Please help us fix it: which phone do you have, and on which screen did it happen? Write to us from the Send Feedback button if the app opens, or add the details to your review. We'll update this reply when the fix ships. — Al-Morabbi
```
_258/350_

### R6 — ١–٣★ محتوى عربي لمستخدم إنجليزي

```
معكم حق، ونعتذر. التطبيق والدروس والحكايات والمساعد متاحة بالإنجليزية، والأذكار بشروح إنجليزية مع نصها العربي؛ أما الألعاب التفاعلية فما زالت بالعربية فقط. ذكرنا ذلك في وصف التطبيق، ونعمل على أن يصلكم كل شيء بلغتكم. — المربّي
```
_225/350_

```
You're right, and we're sorry. The app, the lessons, the stories and the assistant are in English, and the adhkar come with English explanations alongside the Arabic text; only the interactive games are still Arabic-only. We say so in the store description, and we're working to bring everything to you in English. — Al-Morabbi
```
_327/350_

### R7 — طلب نسخة آيفون

```
شكرًا لاهتمامكم. المربّي على أندرويد فقط حاليًا؛ ونسخة آيفون في خطتنا بعد أن تثبت نسخة أندرويد استقرارها، ولا نريد أن نعدكم بموعد لا نضمنه. — المربّي
```
_149/350_

```
Thank you for asking. Al-Morabbi is Android-only for now. An iPhone version is in our plans once the Android app has proven stable — we'd rather not promise a date we can't keep. — Al-Morabbi
```
_191/350_

### R8 — إجابة المساعد غير مناسبة

```
شكرًا لأنكم أخبرتمونا؛ هذا أهم ما يساعدنا. المساعد قد يخطئ، ونراجع كل إجابة يُبلَّغ عنها. إن استطعتم، فقيّموا الإجابة نفسها من تحتها في التطبيق، فتصلنا كما هي. — المربّي
```
_169/350_

```
Thank you for telling us — it's the most useful thing you can do. The assistant can make mistakes, and we review every answer that's reported. If you can, rate that answer from just below it in the app so it reaches us exactly as it was. — Al-Morabbi
```
_250/350_

### R9 — بلاغ عن خطأ في نص شرعي

```
جزاكم الله خيرًا على التنبيه؛ النص الشرعي أمانة. نراجعه الآن مقابل مصدره، ونصحّحه فور التحقق، وسنحدّث هذا الرد حين يُصلَح. وإن ذكرتم لنا موضعه بالضبط من زر «أرسل ملاحظاتك»، فذلك يعجّل الإصلاح. — المربّي
```
_202/350_

```
JazakAllahu khayran for pointing this out — religious text is a trust. We are checking it against its source now, will correct it as soon as it's verified, and will update this reply when it's fixed. Telling us exactly where it appears, via the Send Feedback button, makes the fix faster. — Al-Morabbi
```
_301/350_

### R10 — المساعد رفض سؤال فتوى

```
نتفهّم ذلك. المربّي مساعد تربوي لا يفتي، وأسئلة الحلال والحرام نحيلها إلى أهل العلم احترامًا لها. ويسعده أن يساعدكم في الجانب التربوي: كيف تشرحون الأمر لطفلكم، وكيف تتعاملون معه في البيت. — المربّي
```
_197/350_

```
We understand. Al-Morabbi is a parenting companion, not a source of fatwas; questions of halal and haram are referred to people of knowledge, out of respect for them. It's happy to help with the parenting side: how to explain it to your child and how to handle it at home. — Al-Morabbi
```
_285/350_

### R11 — قلق من الخصوصية

```
سؤالكم في محله. تبدؤون بلا حساب ولا بريد إلكتروني، ويُحذف اسم طفلكم من سؤالكم قبل إرساله إلى نموذج الذكاء الاصطناعي، ولا إعلانات ولا بيع بيانات. سياسة الخصوصية كاملة في إعدادات التطبيق. — المربّي
```
_195/350_

```
A fair question. You start without an account or email, your child's name is removed from your question before it's sent to the AI model, and there are no ads and no data selling. The full privacy policy is in the app's settings. — Al-Morabbi
```
_242/350_

### R12 — إشعارات كثيرة

```
نعتذر عن الإزعاج. يمكنكم إيقاف «إشعارات أذكار الأسرة» والورد من «الإعدادات» داخل التطبيق، وأي إشعار آخر يزعجكم أخبرونا عنه من زر «أرسل ملاحظاتك»؛ ملاحظتكم تساعدنا على تقليلها للجميع. — المربّي
```
_192/350_

```
Sorry for the noise. You can turn off Family Adhkar Notifications and the daily wird reminder in the app's Settings. If another notification bothers you, tell us via Send Feedback — it helps us send fewer for everyone. — Al-Morabbi
```
_231/350_

### R13 — «هل هو مجاني فعلًا؟»

```
نعم، مجاني بالكامل لوجه الله: لا إعلانات ولا اشتراكات ولا ميزة مقفلة، اليوم وغدًا. وإن نفعكم، فدُلّوا عليه أسرة أخرى. — المربّي
```
_127/350_

```
Yes — completely free, for the sake of Allah: no ads, no subscriptions, nothing locked, today or later. If it helps you, tell another family about it. — Al-Morabbi
```
_163/350_

### R14 — ملاحظة على «رمضان العائلة» (F-RAMADAN حيّ في 1.0.73)

```
تقبّل الله منكم. شكرًا على رأيكم في «رمضان العائلة»، وخاصة [الملاحظة]. نجمع ملاحظات هذا العام لنحسّن برنامج العام القادم، فإن كان عندكم المزيد فزر «أرسل ملاحظاتك» يصلنا مباشرة. — المربّي
```
_186/350_

```
May Allah accept from you. Thank you for your thoughts on Family Ramadan, especially [point]. We're gathering this year's feedback to improve next year's program — if you have more, the Send Feedback button reaches us directly. — Al-Morabbi
```
_240/350_

### R-FR — Réponse courte en français (optionnelle — 11 % des appareils sont en français)

```
Merci pour votre avis. Al-Morabbi est disponible en arabe et en anglais ; il n'existe pas encore de version française. L'assistant répond toutefois dans la langue de votre question. — Al-Morabbi
```
_194/350_

---

## ٣. التبرّع والشفافية ⏳ F-DONATE

**كل ما في هذا القسم موقوف على:** (١) حسم سياسة Play للتبرعات (الخطة ٠.٤: المطوّر فرد لا جمعية، فالأرجح أن التبرع يمر عبر
Play Billing كمنتج استهلاكي)، (٢) بناء الشاشة وصفحة الشفافية، (٣) وجود رقم تكلفة حقيقي. **لا أرقام مختلقة**: الحقول بين
[قوسين] تُملأ من فواتير حقيقية.

### القرارات

| القرار | البديل المرفوض | لماذا |
|---|---|---|
| التبرّع **لا يفتح أي ميزة** ولا شارة ولا اسم في لوحة | «داعم ذهبي» أو ميزة للداعمين | يناقض «لوجه الله»، ويحوّل التطبيق إلى freemium مقنّع (قرار خالد: لا freemium) |
| **لا نصفه بالزكاة**، ونقول صراحة إنه ليس قناة زكاة | ترك المسألة مفتوحة | أهلية مصرف الزكاة مسألة فقهية، والمربّي لا يفتي؛ والمطوّر فرد لا جهة زكاة |
| **لا نقول «صدقة جارية لك»** حكمًا | وعد بالأجر | نرجو ولا نجزم: «نسأل الله أن يتقبّل» |
| طلب الدعم في **ثلاثة أماكن فقط:** الإعدادات، وصفحة الشفافية، ورسالة واحدة بعد العيد | إشعار دوري أو نافذة منبثقة | الإلحاح يهدم الثقة التي يقوم عليها التطبيق؛ ولا إشعارات للتبرع إطلاقًا |
| **الشفافية قبل الطلب:** صفحة التكلفة تظهر لكل أحد، تبرّع أو لم يتبرع | إظهارها للداعمين فقط | الثقة هي المقصود، والتبرّع أثرها |

### شاشة الدعم داخل التطبيق — عربي

```
ادعم المربّي

المربّي مجاني لوجه الله، وسيبقى كذلك لمن دعم ولمن لم يدعم.
لكن تشغيله له تكلفة كل شهر: خوادم، ونماذج ذكاء اصطناعي تجيب أسئلتكم.

إن أردتم أن تعينوا على ذلك، فاختاروا مبلغًا:
[مبلغ ١]   [مبلغ ٢]   [مبلغ ٣]

• لا يفتح الدعم أي ميزة؛ كل شيء متاح للجميع.
• هذا ليس قناة زكاة.
• ترون أين يذهب المال في «صفحة الشفافية».

نسأل الله أن يتقبّل منكم.
```

### Support screen — English

```
Support Al-Morabbi

Al-Morabbi is free, for the sake of Allah — and it stays free whether you give or not.
Running it does cost money every month: servers, and the AI models that answer your questions.

If you'd like to help with that, choose an amount:
[amount 1]   [amount 2]   [amount 3]

• A gift unlocks nothing — everything is available to everyone.
• This is not a zakat channel.
• See where the money goes on the Transparency page.

May Allah accept it from you.
```

### صفحة الشفافية — الهيكل

```
تكلفة المربّي في [الشهر]

إجمالي التكلفة:              [X] $
  • الخوادم:                  [..] $
  • نماذج الذكاء الاصطناعي:   [..] $
  • أخرى (نطاق، متجر…):      [..] $

ما غطّاه الداعمون:            [Y] $  ([Y/X] ٪)
ما غطّاه المطوّر من ماله:      [X−Y] $

عدد الأسر التي استعملت المربّي هذا الشهر: [N]
تُحدَّث هذه الصفحة أول كل شهر.
```
(والنسخة الإنجليزية بنفس الحقول: "What Al-Morabbi cost in [month]" …)

**مصدر الأرقام:** فواتير المزوّدين الفعلية (VPS، DeepSeek، Ollama Cloud) وتقرير Play للمدفوعات. لا تقدير ولا تقريب يُعرض
على أنه رقم. إن لم يتوفر رقم شهر ما، تقول الصفحة ذلك.

### رسالة ما بعد العيد (مرة واحدة — في القناة وفي «ما الجديد»)

```
تقبّل الله منّا ومنكم.
في رمضان هذا العام استعمل المربّي [N] أسرة، وكلّف تشغيله [X] $، غطّى الداعمون منها [Y] ٪.
التطبيق باقٍ مجانيًا للجميع. ومن أراد أن يعين، ففي «الإعدادات ← ادعم المربّي» تفاصيل كل شيء.
```

```
Taqabbal Allahu minna wa minkum.
This Ramadan, [N] families used Al-Morabbi. Running it cost $[X], and supporters covered [Y]%.
The app stays free for everyone. If you'd like to help, Settings → Support Al-Morabbi shows exactly where it goes.
```

### ردّ على مراجعة تسأل عن التبرع (بعد شحن F-DONATE)

```
سؤال في محله. الدعم اختياري تمامًا ولا يفتح أي ميزة؛ التطبيق مجاني للجميع. وفي «صفحة الشفافية» داخل التطبيق ترون تكلفة كل شهر وما غطّاه الداعمون. — المربّي
```
```
A fair question. Giving is entirely optional and unlocks nothing — the app is free for everyone. The Transparency page in the app shows each month's cost and how much supporters covered. — Al-Morabbi
```
