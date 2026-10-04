# قوالب الرد على تقييمات Play + رسالة التبرّع والشفافية

> العلامات ⏳ معرّفة في [`00_README.md`](00_README.md). خالد يلصق الرد بنفسه في Play Console؛ لا ردّ آلي
> (اقتراح وكيل المسودات في `plans/review-reply-agent-proposal.md` ما زال قرارًا معلّقًا).

## ١. قواعد الرد

1. **خلال ٤٨ ساعة** من المراجعة، وكل يوم في الموسم (١٥ يناير → ١٥ مارس). `scripts/play_reviews.py` يرى آخر ٧ أيام فقط — فلا تتأخر.
2. **حد Play للرد ٣٥٠ حرفًا.** كل قالب أدناه محسوب بجانبه (`len` في Python).
3. **بلغة المراجعة:** عربية ← رد عربي فصيح سهل (الرد نص عام على صفحة المتجر)؛ إنجليزية ← إنجليزي؛ فرنسية ← القالب الفرنسي القصير.
4. **خصّص سطرًا واحدًا على الأقل** باسم ما ذكره المراجع — القالب نقطة بداية لا لصق أعمى.
5. **لا وعود بمواعيد، ولا جدال، ولا أحكام شرعية**، ولا ذكر لميزة ⏳ لم تُشحن.
6. **لا تطلب من أحد تغيير تقييمه.** إن أصلحنا ما اشتكى منه، نحدّث الرد نفسه ونقول ذلك؛ وهو يقرر.
7. **لا بيانات شخصية** في الرد، ولا تطلب منه رقمًا أو بريدًا علنًا — التواصل الخاص عبر زر «أرسل ملاحظاتك».
8. التوقيع «— خالد»: مشروع فردي، والاسم الحقيقي يبني ثقة لا يبنيها «فريق الدعم».

أسماء الأزرار مطابقة لملفات الترجمة اليوم: «أرسل ملاحظاتك» / "Send Feedback" (`sendFeedback`)، «إشعارات أذكار الأسرة» /
"Family Adhkar Notifications" (`settingsFamilyAdhkar` — مفتاح الإشعارات الوحيد في الإعدادات مع الورد)، «سياسة الخصوصية» /
"Privacy Policy"، شاشة «اليوم» / "Today". إن تغيّرت في التطبيق تُغيَّر هنا.

## ٢. القوالب

### R1 — ٥★ شكر عام

```
جزاك الله خيرًا على كلماتك الطيبة. يسعدنا أن المربّي نفعك أنت وأسرتك. وإن خطرت لك فكرة تجعله أنفع، فاكتبها لنا من زر «أرسل ملاحظاتك» داخل التطبيق؛ نقرأ كل رسالة. — خالد
```
_168/350_

```
JazakAllahu khayran for your kind words. We're glad Al-Morabbi is helping your family. If you have an idea that would make it more useful, send it from the Send Feedback button in the app — every message is read. — Khaled
```
_221/350_

### R2 — ٥★ يذكر ميزة بعينها

```
شكرًا لك! سعدنا أن [الميزة] أفادتك مع طفلك. وأي فكرة ترسلها من زر «أرسل ملاحظاتك» في التطبيق تصل إلينا مباشرة. — خالد
```
_117/350_

```
Thank you! We're happy [feature] has helped with your child. Any idea you send from the Send Feedback button in the app reaches us directly. — Khaled
```
_149/350_

### R3 — ٤★ مع اقتراح

```
شكرًا على التقييم وعلى اقتراحك عن [الاقتراح]. سجّلناه، ولا نعدك بموعد قبل أن نتأكد أنه سينفع الأسر فعلًا. إن أحببت أن تشرح أكثر، فزر «أرسل ملاحظاتك» في التطبيق يصلنا مباشرة. — خالد
```
_180/350_

```
Thanks for the rating and for suggesting [suggestion]. It's noted. We won't promise a date until we're sure it will truly help families. If you'd like to explain more, the Send Feedback button in the app reaches us directly. — Khaled
```
_233/350_

### R4 — ٣★ «لا أعرف من أين أبدأ»

```
شكرًا لصراحتك، وهذه أكثر ملاحظة نسمعها. ابدأ من شاشة «اليوم»: سجّل طفلك ثم افتح الخطوة المقترحة لعمره، أو اكتب للمربّي مشكلة واحدة تشغلك الآن. ونعمل على تبسيط البداية أكثر. — خالد
```
_179/350_

```
Thank you for being honest — this is the feedback we hear most. Start from the Today screen: add your child, then open the suggested step for their age, or tell Al-Morabbi about one thing that's on your mind. We're making the start simpler. — Khaled
```
_249/350_

### R5 — ١–٢★ عطل أو توقف

```
نعتذر عن هذا. ساعدنا لنصلحه: ما نوع هاتفك، وفي أي شاشة حدث العطل؟ اكتب لنا من زر «أرسل ملاحظاتك» في التطبيق إن استطعت فتحه، أو أضف التفاصيل إلى مراجعتك. وسنحدّث هذا الرد حين يصل الإصلاح. — خالد
```
_193/350_

```
We're sorry about this. Please help us fix it: which phone do you have, and on which screen did it happen? Write to us from the Send Feedback button if the app opens, or add the details to your review. We'll update this reply when the fix ships. — Khaled
```
_254/350_

### R6 — ١–٣★ محتوى عربي لمستخدم إنجليزي

```
معك حق، ونعتذر. الدروس والمسارات والمساعد متاحة بالإنجليزية كاملة، أما الأذكار والألعاب والقصص فما زالت بالعربية فقط، وترجمتها جارية. ذكرنا ذلك في وصف التطبيق، ونعمل على أن يصلك كل شيء بلغتك. — خالد
```
_198/350_

```
You're right, and we're sorry. The lessons, paths and assistant are fully in English; the adhkar, games and stories are still Arabic-only, and translation is under way. We say so in the store description, and we're working to bring everything to you in English. — Khaled
```
_270/350_

### R7 — طلب نسخة آيفون

```
شكرًا لاهتمامك. المربّي على أندرويد فقط حاليًا؛ ونسخة آيفون في خطتنا بعد أن تثبت نسخة أندرويد استقرارها، ولا نريد أن نعدك بموعد لا نضمنه. — خالد
```
_144/350_

```
Thank you for asking. Al-Morabbi is Android-only for now. An iPhone version is in our plans once the Android app has proven stable — we'd rather not promise a date we can't keep. — Khaled
```
_187/350_

### R8 — إجابة المساعد غير مناسبة

```
شكرًا لأنك أخبرتنا؛ هذا أهم ما يساعدنا. المساعد قد يخطئ، ونراجع كل إجابة يُبلَّغ عنها. إن استطعت، فقيّم الإجابة نفسها من تحتها في التطبيق، فتصلنا كما هي. — خالد
```
_160/350_

```
Thank you for telling us — it's the most useful thing you can do. The assistant can make mistakes, and we review every answer that's reported. If you can, rate that answer from just below it in the app so it reaches us exactly as it was. — Khaled
```
_246/350_

### R9 — بلاغ عن خطأ في نص شرعي

```
جزاك الله خيرًا على التنبيه؛ النص الشرعي أمانة. نراجعه الآن مقابل مصدره، ونصحّحه فور التحقق، وسنحدّث هذا الرد حين يُصلَح. وإن ذكرت لنا موضعه بالضبط من زر «أرسل ملاحظاتك»، فذلك يعجّل الإصلاح. — خالد
```
_197/350_

```
JazakAllahu khayran for pointing this out — religious text is a trust. We are checking it against its source now, will correct it as soon as it's verified, and will update this reply when it's fixed. Telling us exactly where it appears, via the Send Feedback button, makes the fix faster. — Khaled
```
_297/350_

### R10 — المساعد رفض سؤال فتوى

```
نتفهّم ذلك. المربّي مساعد تربوي لا يفتي، وأسئلة الحلال والحرام نحيلها إلى أهل العلم احترامًا لها. ويسعده أن يساعدك في الجانب التربوي: كيف تشرح الأمر لطفلك، وكيف تتعامل معه في البيت. — خالد
```
_188/350_

```
We understand. Al-Morabbi is a parenting companion, not a source of fatwas; questions of halal and haram are referred to people of knowledge, out of respect for them. It's happy to help with the parenting side: how to explain it to your child and how to handle it at home. — Khaled
```
_281/350_

### R11 — قلق من الخصوصية

```
سؤالك في محله. تبدأ بلا حساب ولا بريد إلكتروني، ويُحذف اسم طفلك من سؤالك قبل إرساله إلى نموذج الذكاء الاصطناعي، ولا إعلانات ولا بيع بيانات. سياسة الخصوصية كاملة في إعدادات التطبيق. — خالد
```
_187/350_

```
A fair question. You start without an account or email, your child's name is removed from your question before it's sent to the AI model, and there are no ads and no data selling. The full privacy policy is in the app's settings. — Khaled
```
_238/350_

### R12 — إشعارات كثيرة

```
نعتذر عن الإزعاج. يمكنك إيقاف «إشعارات أذكار الأسرة» والورد من «الإعدادات» داخل التطبيق، وأي إشعار آخر يزعجك أخبرنا عنه من زر «أرسل ملاحظاتك»؛ ملاحظتك تساعدنا على تقليلها للجميع. — خالد
```
_185/350_

```
Sorry for the noise. You can turn off Family Adhkar Notifications and the daily wird reminder in the app's Settings. If another notification bothers you, tell us via Send Feedback — it helps us send fewer for everyone. — Khaled
```
_227/350_

### R13 — «هل هو مجاني فعلًا؟»

```
نعم، مجاني بالكامل لوجه الله: لا إعلانات ولا اشتراكات ولا ميزة مقفلة، اليوم وغدًا. وإن نفعك، فدُلّ عليه أسرة أخرى. — خالد
```
_121/350_

```
Yes — completely free, for the sake of Allah: no ads, no subscriptions, nothing locked, today or later. If it helps you, tell another family about it. — Khaled
```
_159/350_

### R14 — ⏳ F-RAMADAN ملاحظة على برنامج رمضان

```
تقبّل الله منكم. شكرًا على رأيك في برنامج رمضان، وخاصة [الملاحظة]. نجمع ملاحظات هذا العام لنحسّن برنامج العام القادم، فإن كان عندك المزيد فزر «أرسل ملاحظاتك» يصلنا مباشرة. — خالد
```
_178/350_

```
May Allah accept from you. Thank you for your thoughts on the Ramadan program, especially [point]. We're gathering this year's feedback to improve next year's program — if you have more, the Send Feedback button reaches us directly. — Khaled
```
_241/350_

### R-FR — Réponse courte en français (optionnelle — 11 % des appareils sont en français)

```
Merci pour votre avis. Al-Morabbi est disponible en arabe et en anglais ; il n'existe pas encore de version française. L'assistant répond toutefois dans la langue de votre question. — Khaled
```
_190/350_

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

إن أردت أن تعين على ذلك، فاختر مبلغًا:
[مبلغ ١]   [مبلغ ٢]   [مبلغ ٣]

• لا يفتح الدعم أي ميزة؛ كل شيء متاح للجميع.
• هذا ليس قناة زكاة.
• ترى أين يذهب المال في «صفحة الشفافية».

نسأل الله أن يتقبّل منك.
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
ما غطّاه خالد:                [X−Y] $

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
سؤال في محله. الدعم اختياري تمامًا ولا يفتح أي ميزة؛ التطبيق مجاني للجميع. وفي «صفحة الشفافية» داخل التطبيق ترى تكلفة كل شهر وما غطّاه الداعمون. — خالد
```
```
A fair question. Giving is entirely optional and unlocks nothing — the app is free for everyone. The Transparency page in the app shows each month's cost and how much supporters covered. — Khaled
```
