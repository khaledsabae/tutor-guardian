# الفيديو القصير: تقويم ١٠ أسابيع (الموجة ١: ٢٥ أكتوبر – ٣١ ديسمبر)

ثلاثة منشورات في الأسبوع:
- **الأحد:** فيديو
- **الثلاثاء:** بطاقة نصيحة (إنفوجراف)
- **الخميس:** فيديو

المنصات: تيك توك، وYouTube Shorts، وInstagram Reels، وFacebook Reels.

## الملفات

- **الفيديوهات** (خارج git): `scratch/videos/noor-campaign/` و`scratch/videos/noor-teaser/`.
  - استعملوا نسخة `_vo` حيث وُجدت (v1 وv3 وv5).
  - تسجيل الصوت لـv2 وv4 وv6 والـteaser الجديد ينتظر حصة Gemini (الخطة، المرحلة أ-٦). حين يجهز يحلّ محل النسخة الصامتة في الجدول نفسه.
- **بطاقات النصيحة** (1080×1350):
  - كلها في `scratch/launch/infographic_bank/<topic>.png`.
  - مصدرها `_build/infographics.json`.
  - لا تصلح لـYouTube Shorts (صور)، فتُنشر على الثلاث الأخرى فقط: تيك توك بوضع الصور، وإنستغرام وفيسبوك منشورًا عاديًا.
- **`v5_ramadan` محجوز للموجة ٢** (من ١١ يناير، مع عدّاد نور)، فلا يظهر هنا.

## الأكواد: كود لكل منصة

| المنصة | الكود | أين يوضع الرابط |
|---|---|---|
| تيك توك | `OT01` | رابط الملف الشخصي (bio)، فالروابط في الوصف لا تُضغط |
| YouTube Shorts | `OT02` | الوصف + تعليق مثبّت |
| Instagram Reels | `OT03` | رابط الملف الشخصي (bio) |
| Facebook Reels / الصفحة | `OT04` | الوصف مباشرة |

الرابط: `https://tg-api.alsaba.cloud/go?c=OT0x`.

**لماذا `OT`:** سجل الأكواد في `backend/app/services/attribution.py` ليس فيه بادئة للفيديو القصير. `OT` («أخرى») هي البادئة المقبولة الوحيدة اليوم.
- إن أضاف ملف `docs/marketing/campaign_codes.md` (فرع `noor/campaign-codes`) بادئات للمنصات، فاستبدلوا الأربعة.

**الـQR داخل الفيديوهات** ما زال يشير إلى Play مباشرة بـ`utm` فقط، فلا يراه `campaign_report.py`.
- إعادة توليده بـ`/go?c=<CODE>` بند في المرحلة أ-٢ من الخطة، خارج هذه الحزمة.
- إلى أن يتم ذلك، الرابط في الوصف هو الذي يُقاس.

## الجدول

| الأسبوع | الأحد | الثلاثاء (بطاقة) | الخميس |
|---|---|---|---|
| ١ | ٢٥ أكتوبر: `noor_teaser_ar` · T-A | ٢٧ أكتوبر: `prayer_journey` · C-prayer | ٢٩ أكتوبر: `v2_road` · V2-A |
| ٢ | ١ نوفمبر: `v1_remember_vo` · V1-A | ٣ نوفمبر: `tantrums_2_3` · C-tantrums | ٥ نوفمبر: `v3_ask_vo` · V3-A |
| ٣ | ٨ نوفمبر: `v6_stories` · V6-A | ١٠ نوفمبر: `screens_7_9` · C-screens | ١٢ نوفمبر: `v4_handover` · V4-A |
| ٤ | ١٥ نوفمبر: `noor_teaser_en` · T-EN | ١٧ نوفمبر: `child_faith_questions` (+`_en`) · C-faith | ١٩ نوفمبر: `v2_road` · V2-B |
| ٥ | ٢٢ نوفمبر: `v3_ask_vo` · V3-B | ٢٤ نوفمبر: `akhlaq_7_9` · C-akhlaq | ٢٦ نوفمبر: `v1_remember_vo` · V1-B |
| ٦ | ٢٩ نوفمبر: `v6_stories` · V6-B | ١ ديسمبر: `aqeedah_seeds_4_6` · C-seeds | ٣ ديسمبر: `v4_handover` · V4-B |
| ٧ | ٦ ديسمبر: `noor_teaser_ar_world` · T-B | ٨ ديسمبر: `teen_doubts` · C-doubts | ١٠ ديسمبر: `v3_ask_vo` · V3-A |
| ٨ | ١٣ ديسمبر: `v2_road` · V2-A | ١٥ ديسمبر: `puberty_10_12` · C-puberty | ١٧ ديسمبر: `v6_stories` · V6-A |
| ٩ | ٢٠ ديسمبر: `v1_remember_vo` · V1-A | ٢٢ ديسمبر: `teen_identity` · C-identity | ٢٤ ديسمبر: `v4_handover` · V4-A |
| ١٠ | ٢٧ ديسمبر: `noor_teaser_ar` · T-A | ٢٩ ديسمبر: `ramadan_family` · C-ramadan | ٣١ ديسمبر: `v3_ask_vo` · V3-B |

**الحسابات الإنجليزية** (إن وُجدت): تنشر الأسبوع ٤ (`noor_teaser_en` و`child_faith_questions_en`) بتعليقات EN. وفي باقي الأسابيع تنشر الفيديوهات العربية بتعليق EN يوضّح أن الفيديو بالعربية وأن واجهة التطبيق إنجليزية.

**بعد كل أسبوعين:** قارنوا الأكواد الأربعة في تقرير الأحد (التثبيتات وD1 لكل كود). المنصة التي يبقى D1 لها دون ١٠٪ أربعة أسابيع متتالية تُترك، ويُعاد وقتها إلى الأفضل.

---

## بنك التعليقات

**الوسوم:**
- بالعربية: `#تربية_الأبناء #تربية_إسلامية #المربي #نصائح_للأهل #الأسرة_المسلمة`
- بالإنجليزية: `#MuslimParenting #IslamicParenting #MuslimFamily #ParentingTips #AlMorabbi`

اكتفوا بثلاثة إلى خمسة وسوم.

**السطر الأخير ثابت في كل تعليق:**
- بالعربية: «مجاني بالكامل، بلا إعلانات ولا اشتراكات • أندرويد • الرابط في الصفحة»، أو الرابط نفسه على يوتيوب وفيسبوك.
- بالإنجليزية: "100% free, with no ads and no subscriptions • Android only • link in bio".

### الفيديوهات

| المعرّف | العربية | English |
|---|---|---|
| T-A (teaser) | في ليلة هادئة يطلّ نور… رفيقكم في تربية أطفالكم. كل خطوة صغيرة مع طفلكم تضيء قنديلًا. 🌙 | Noor is here: your companion in raising your children. Every small step lights a lantern. 🌙 (The video is in Arabic; the app has an English interface.) |
| T-B (teaser world) | هذا عالم «المربّي» الجديد: درب كل يوم، وقناديل الأسبوع، ونور الذي يسألكم: كيف جرت؟ | Meet the new world of Al-Morabbi: a daily path, the week's lanterns, and Noor, who asks how it went. (Video in Arabic.) |
| T-EN (teaser en) | — | Noor is a paper-cut crescent who walks with your family, one small parenting step a day, from pregnancy to 18. In English and Arabic. 🌙 |
| V1-A | نصيحة سمعتموها ثم نسيتموها؟ في «المربّي» يسألكم نور: متى ستجرّبونها؟ ثم يعود ليسأل: كيف جرت؟ | Heard good advice, then forgot it? Noor asks when you'll try it, then comes back to ask how it went. (Video in Arabic.) |
| V1-B | مربٍّ يتذكّر معكم: تختارون خطوة واحدة، ونور يذكّركم بها، ثم يسألكم عن نتيجتها. | A companion that remembers with you: pick one step, and Noor follows up. (Video in Arabic.) |
| V2-A | لا تعرفون من أين تبدؤون؟ كل يوم ثلاث خطوات صغيرة: درس في دقائق، وسؤال للمربّي، ومهمة لطفلكم. | Not sure where to start? Three small steps a day: a short lesson, a question, and a task for your child. (Video in Arabic.) |
| V2-B | درب اليوم: ثلاث محطات تحت سماء تتبع ساعة يومكم. خطوة صغيرة كل يوم تكفي. | Today's path: three stops under a sky that follows your day. One small step is enough. (Video in Arabic.) |
| V3-A | «طفلي يعاند وقت النوم… ماذا أفعل؟» اسألوا المربّي، فيجيب بخطوات هادئة تناسب عمر طفلكم. | "My child fights bedtime. What do I do?" Ask, and get calm steps that fit your child's age. You can ask in English too. |
| V3-B | سؤالكم أنتم، عن طفلكم أنتم: المساعد يعرف عمره، ويعطيكم خطوة واحدة تجرّبونها الليلة. | Your question, about your child: the assistant knows their age and gives you one step to try tonight. |
| V4-A | الشاشة… لكن بنيّة. في «ركن الطفل» حكاية قصيرة، ثم مهمة بعيدًا عن الشاشة، ولا يعود الجهاز إلا برمز الأهل. | Screen time with a purpose: a short story, then a task away from the screen. Only your PIN unlocks the device again. (Video in Arabic.) |
| V4-B | «يا يوسف، دورك الآن!» وقت الشاشة شمعة ورقية تقصر، ثم يعيد الجهاز إليكم. | "Your turn now!" Screen time is a paper candle that burns down, then the device comes back to you. (Video in Arabic.) |
| V6-A | حكاية قبل النوم يرويها نور: «يوسف وغرسة الأمل»، وفيها وقفة يسأل فيها نور طفلكم: ماذا كنت ستفعل؟ | A bedtime story told by Noor, with a pause where Noor asks your child: what would you do? |
| V6-B | سؤال صغير… وحديث بينكما. حكايات نور تنتهي بحوار، لا بشاشة أخرى. | One small question, and a talk between you. Noor's stories end in a conversation, not another screen. |

### بطاقات النصيحة

| المعرّف | العربية | English |
|---|---|---|
| C-prayer | رحلة الصلاة في ستّ محطات: من «الصلاة لقاء نحبه» إلى «أصلّي وحدي»، بلا عقاب ولا مقارنة. احفظوها. 🌙 | The Prayer Journey in six stages, from "a meeting we love" to "I pray on my own", with no punishment and no comparison. |
| C-tantrums | نوبة الغضب في الثانية والثالثة: ماذا تفعلون قبلها، وأثناءها، وبعدها. | Toddler tantrums: what to do before, during and after. |
| C-screens | الشاشة في بيتنا: اتفاقٌ لا معركة. أربع خطوات لطفل بين ٧ و٩. | Screens at home: an agreement, not a battle. Four steps for ages 7–9. |
| C-faith | حين يسأل طفلكم عن الله: إجابات هادئة تبني هوية واثقة. | When your child asks about Allah: calm answers that build a confident identity. |
| C-akhlaq | الصدق والرحمة والمسؤولية: أخلاق تُبنى بالموقف لا بالموعظة. | Honesty, mercy and responsibility are built through moments, not lectures. |
| C-seeds | أول تعريف بالله لطفل بين ٤ و٦: أربع بذور. | Introducing Allah to a 4–6-year-old: four seeds. |
| C-doubts | حين يسأل ابنكم المراهق: كيف أعرف أن الله موجود؟ الحوار لا الإسكات. | When your teen asks "How do I know Allah exists?": dialogue, not silence. |
| C-puberty | قبل عاصفة المراهقة: البلوغ والمزاج وصورة الجسد، لمن بين ١٠ و١٢. | Before the storm of adolescence: puberty, mood and body image, ages 10–12. |
| C-identity | هوية المراهق المسلم: من متلقٍّ يتأثر إلى صانعٍ يؤثّر. | A Muslim teen's identity: from being shaped to shaping. |
| C-ramadan | «رمضان العائلة»: ثلاثون يومًا، وتحدٍّ واحد كل يوم لا يزيد على ربع ساعة. جهّزوا له من الآن. | "Family Ramadan": 30 days, one challenge a day of 15 minutes or less. Get ready now. |
