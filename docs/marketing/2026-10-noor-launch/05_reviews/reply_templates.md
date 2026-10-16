# قوالب الرد على تقييمات Google Play

**القاعدة من الخطة:** نردّ على **كل** التقييمات.

## قواعد الرد

- **الطول:** حدّ Play للرد ٣٥٠ حرفًا. كل قالب هنا تحته، ويبقى مكان لجملة شخصية.
- **ابدؤوا بشيء من كلام صاحب التقييم نفسه** (اسم الميزة، أو المشكلة)، حتى لا يبدو الرد آليًا. المكان المخصّص لذلك: `{…}`.
- **التوقيع:** «فريق المربّي». **لا اسم شخص.**
- **لغة الرد = لغة التقييم.** فصحى سهلة، بلا عامية.
- **بلا وعد بموعد ولا بميزة:** «سجّلناها» لا «ستصل الشهر القادم».
- **بلا وعد بأجر، وبلا مقارنة مع أي تطبيق.**
- **قبل الرد على تقييم فيه عطل:** اقرؤوا رقم النسخة في التقييم.
  - إن كان العطل مُصلَحًا في نسخة أحدث، فقولوا ذلك واطلبوا التحديث.
  - وإلا فلا تقولوا «أصلحناه».
- **«شاركنا رأيك»** هو اسم الخيار في الإعدادات (Settings → Share your feedback). ما يُرسل منه يصل مباشرة، ويمكن الرد عليه.

---

## ١. تقييم إيجابي

**عربي:**
> جزاكم الله خيرًا على كلماتكم، وسعدنا أن {الميزة التي ذكرها} نفعتكم. التطبيق مجاني بالكامل وبلا إعلانات، وسيبقى كذلك بإذن الله. وإن خطر لكم اقتراح، فمن الإعدادات ← «شاركنا رأيك». — فريق المربّي

**English:**
> JazakAllahu khayran for your kind words. We're glad {feature} has helped your family. The app is completely free with no ads, and will stay that way, in sha Allah. If you have a suggestion, use Settings → Share your feedback. — The Al-Morabbi team

## ٢. عطل أو مشكلة تقنية

**عربي:**
> نعتذر عمّا حدث مع {وصف المشكلة باختصار}. نريد أن نفهمه بدقة: هل ترسلون لنا من الإعدادات ← «شاركنا رأيك» ما كنتم تفعلونه حين حدث، ونوع جهازكم؟ نقرأ كل رسالة، ونردّ عليها داخل التطبيق. — فريق المربّي

**إن كان مُصلَحًا في نسخة أحدث:**
> شكرًا لتنبيهكم. {المشكلة} أُصلحت في النسخة {الرقم}. حدّثوا التطبيق من Google Play، وإن بقيت فأخبرونا من الإعدادات ← «شاركنا رأيك». — فريق المربّي

**English:**
> We're sorry about {the issue}. To fix it properly, could you send us what you were doing when it happened and your phone model, via Settings → Share your feedback? We read every message and reply inside the app. — The Al-Morabbi team

## ٣. طلب ميزة

**عربي:**
> شكرًا على الاقتراح: {الميزة المطلوبة}. سجّلناه مع اقتراحات الأهل الأخرى، وما يتكرّر طلبه نبدأ به. وإن أحببتم أن تشرحوا كيف تستعملونها مع أطفالكم، فمن الإعدادات ← «شاركنا رأيك». — فريق المربّي

**إن كان الطلب نسخة آيفون:**
> شكرًا لسؤالكم. التطبيق اليوم على أندرويد فقط، ونسخة آيفون ليست جاهزة بعد. لا نستطيع أن نعد بموعد، لكننا سجّلنا طلبكم. — فريق المربّي

**English:**
> Thank you for suggesting {feature}. We've added it to the list of parents' requests, and the most requested ones come first. If you'd like to tell us how you'd use it with your children, use Settings → Share your feedback. — The Al-Morabbi team

## ٤. ملاحظة على المحتوى الشرعي

**عربي:**
> جزاكم الله خيرًا على التنبيه، فهو يهمّنا أكثر من أي شيء. نراجع كل نص شرعي على مصدره، وما ثبت خطؤه نصحّحه أو نحذفه. هل ترسلون لنا من الإعدادات ← «شاركنا رأيك» اسم الدرس أو صورة من الموضع؟ والتطبيق لا يفتي؛ فالأحكام تُؤخذ من أهل العلم. — فريق المربّي

**English:**
> JazakAllahu khayran for pointing this out. We check every religious text against its source, and we correct or remove anything shown to be wrong. Could you send the lesson name or a screenshot via Settings → Share your feedback? The app does not issue fatwas. Please take rulings from qualified scholars. — The Al-Morabbi team

**ما يُفعل بعد هذا الرد (داخليًا، ولا يُكتب في الرد):**
1. افتحوا الموضع.
2. شغّلوا حرّاس المحتوى (`bash .githooks/pre-commit`) على الملف المعني.
3. راجعوا النص على صورة صفحة المصدر نفسها، لا على ملخّص.
   - إن ثبت الخطأ: صحّحوه أو احذفوه.
   - ثم ردّوا على التقييم نفسه: «صحّحناه في النسخة {الرقم}، شكرًا لكم».
4. **«نراجعه»** وعدٌ يُنفَّذ، فلا يُكتب في الرد قبل فتح الموضع فعلًا.
