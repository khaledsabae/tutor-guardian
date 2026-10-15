# المربّي — دليل الأصول البصرية

النظام البصري كله **«ورق مقصوص»**: طبقات ورق مسطّحة بألوان ثابتة، وكل شكل له ظل ورقي مزاح من غير blur.
خالد اختاره يوم 2026-10-14 من ٣ عيّنات. طقم «الفانوس» القديم (برومبتات Recraft، صور PNG بتدرّجات)
**اتلغى** — ماترجعلوش، ولا تولّد صور بالذكاء الاصطناعي للتطبيق.

| الطبقة | المكان | الحالة |
|---|---|---|
| رسومات جوه التطبيق | `mobile/assets/svg/` | ✅ شغّالة (d3feb863) |
| أيقونة التطبيق | `docs/brand/icon/` ← `mobile/android/app/src/main/res/` | ⏳ مستنية اعتماد خالد |
| صور المتجر | `docs/brand/store/` | ⏳ مستنية اعتماد خالد — **مارفعتش حاجة على Play** |

---

## ١) الرسومات جوه التطبيق — `mobile/assets/svg/`

**الدليل الملزم: [`mobile/assets/svg/STYLE.md`](../mobile/assets/svg/STYLE.md)** — الألوان بالـhex، العناصر
المسموحة في flutter_svg، إزاحة الظل، مسار هلال نور المرجعي، وقواعد رسم البشر.

| المجلد | فيه إيه |
|---|---|
| `noor/` | نور (الهلال) بـ٧ حالات: awake, calm, happy, reading, sleepy, tender, thinking |
| `icons/` | ١٧ أيقونة صغيرة (`viewBox 0 0 48 48`) |
| `art/` | الشارات (٦)، المجالات (٥)، الحالات الفاضية (٣)، المحطات (٣)، `onboarding_welcome`، `share_bg_celebration`، `logo_mark` |

- كل ملف SVG مكتوب باليد، ≤ 12KB، من غير نص ولا تدرّجات ولا filters.
- `test/svg_assets_test.dart` بيفتح كل ملف؛ المجلدات متسجّلة في `pubspec.yaml`.
- رسم جديد = ملف SVG على نفس القواعد. لو مجلد جديد سجّله في `pubspec.yaml`.

## ٢) الهوية برّه التطبيق — `docs/brand/`

```
docs/brand/
  icon/    icon_a_seal.svg  icon_b_noor.svg  icon_c_hills.svg   ← مصادر الأيقونة (٣ اتجاهات)
  review/  icon_compare_sizes.png  icon_compare_masks.png  icon_home_screen.png
  store/   feature_graphic.svg/.png  frame_{1,2,3}_*.svg/.png  play_icon_512.png  example_*.png
  tools/   brand_build.py   ← كل الـPNG والـXML بتطلع منه؛ الـSVG هو المصدر
```

`brand_build.py` محتاج بس اللي على اللابتوب أصلًا (python3-gi: Rsvg + Pango، pycairo، Pillow)، وبيقرا خط
Cairo من `mobile/assets/google_fonts/` من غير ما يسطّب حاجة على النظام:

```bash
python3 docs/brand/tools/brand_build.py review        # لوحات المقارنة
python3 docs/brand/tools/brand_build.py android b     # أيقونة Android من الاتجاه b (أو a / c)
python3 docs/brand/tools/brand_build.py store         # صور المتجر + أمثلة الإطارات
python3 docs/brand/tools/brand_build.py frame --frame frame_1_rising \
        --shot shot.png --title "يومك مع طفلك" --subtitle "خطوة صغيرة كل يوم" --out out.png
```

## ٣) أيقونة التطبيق

### الفكرة
نفس هوية الأيقونة اللي الناس شايفاها على Play — **هلال بوجه نائم + كتاب طالع منه نبتة + نجمة، فاتح على
زمردي** — مترجمة للورق المقصوص. الوش هو وش نور (`noor_sleepy`) فالأيقونة والتميمة بقوا شخص واحد.

| الاتجاه | الملف | الفرق |
|---|---|---|
| A «الختم» | `icon_a_seal.svg` | الحلقة باقية — الأقرب للحالية، بس المحتوى جوه الحلقة صغير على 48px |
| **B «نور» ★ المُوصى به** | `icon_b_noor.svg` | من غير حلقة — نفس العناصر أكبر؛ الأوضح على 48px |
| C «الطبقات» | `icon_c_hills.svg` | نور طالع ورا تلال ورقية زي كروت التطبيق — الأدفى، بس التلال بتعمل دوشة تحت على 48px |

### شكل ملف المصدر
كل ملف فيه ٣ مجموعات عليا: `background` و`foreground` و`monochrome` (مخفية). مساحة الرسم `0 0 240 240` =
الـ72dp **الظاهرة** من الأيقونة التكيّفية (108dp)، فالمنطقة الآمنة (دايرة 66dp) = نصف قطر 110 حوالين
(120,120) — أي حاجة مهمة لازم تفضل جواها. الخلفية مرسومة من −60 لـ300 عشان تغطي الـ108dp كلها.
مسموح بس `translate()`/`scale()` وعناصر STYLE.md، عشان الملف يتحوّل لـVectorDrawable بالظبط.

`monochrome` = نسخة لون واحد لأيقونات Android 13 الملوّنة بالثيم: من غير تداخل، والتفاصيل (العينين، فاصل
الكتاب) ثقوب `evenodd` مش رسم فوق رسم.

### على Android (ورا الاعتماد)
- الأيقونة الجديدة باسم جديد: `ic_launcher_paper` — `drawable/ic_launcher_paper_{background,foreground,monochrome}.xml`
  (VectorDrawable) + `mipmap-anydpi-v26/ic_launcher_paper{,_round}.xml` + PNG لكل كثافة لـAPI 24–25.
- الأيقونة القديمة (`ic_launcher*`) **ماتلمستش**.
- التفعيل في commit لوحده اسمه **«تفعيل الأيقونة الجديدة»**: بيوجّه `android:icon`/`android:roundIcon` في
  `AndroidManifest.xml` للجديدة، وبيقفل الجزء بتاع Android في `flutter_launcher_icons` (لأنه لو اتشغّل بيرجّع
  `android:icon` لـ`ic_launcher` من غير ما حد ياخد باله).
- **الرجوع:** `git revert` لـcommit التفعيل بس — والأيقونة القديمة ترجع زي ما هي.
- **اتجاه تاني؟** `brand_build.py android a` (أو c) بيعيد كتابة نفس الملفات؛ الأمر بيرفض يكتب لو الـVectorDrawable
  مش مطابق للـSVG بكسل ببكسل، وبيعدّي كل XML على `aapt2 compile`.

### فخاخ لازم تعرفها
- `notification_service.dart` بيستخدم `@mipmap/ic_launcher` (القديمة) — **ماتمسحش الموارد القديمة** من غير ما تغيّره.
- شاشة البداية (`flutter_native_splash`) لسه بالشعار القديم من `frontend/icons/icon-512.png`، و`assets/images/logo.png`
  (علامة الإنفوجرافيك) قديم برضه، وأيقونات iOS قديمة (iOS لسه مانزلش). دول خطوة بعدين.
- أيقونة Play (512×512) **مش بتطلع من البناء** — بتترفع باليد في Play Console: `docs/brand/store/play_icon_512.png`
  (مربّع كامل؛ Play بيقصّه بنفسه).

## ٤) صور المتجر — `docs/brand/store/`

### Feature graphic (1024×500)
`feature_graphic.svg` ← `.png`: نور على الشمال، وعلى اليمين الأيقونة + «المربّي» + «رفيقك في تربية طفلك».
النص `<text>` حقيقي بخط Cairo (سهل يتعدّل). المهم بعيد عن الحواف.

### إطارات لقطات الشاشة (1080×1920)
**ليه إطارات أصلًا:** لقطات معرض الـCI من محاكي Pixel 7 مقاسها 1080×2400 (نسبة 2.22)، وPlay بيرفض أي لقطة ضلعها
الطويل أكتر من ضعف القصير. الإطار 9:16 بيحلّها ويضيف عنوان.

| الإطار | الشكل |
|---|---|
| `frame_1_rising` | زمردي، العنوان فوق، الشاشة طالعة من ورا التلال (الجزء التحتاني من اللقطة بيتقص) |
| `frame_2_ivory` | ورق عاجي، الشاشة **كاملة** على كارت زمردي، ونور بيبص من الركن |
| `frame_3_bubble` | نور بيقول العنوان في فقاعة ورق، والشاشة طالعة من تحت |

- مكان اللقطة = `<rect id="slot">`؛ العنوان `id="title"` والسطر التاني `id="subtitle"`؛ الطبقات `under` / `placeholder` / `over`.
- العنوان بيصغر لوحده لو أطول من `data-max-width`.
- اللقطات: artifact اسمه `e2e-gallery` من workflow «Mobile E2E (emulator)» ← `brand_build.py frame ...`.
- `example_*.png` معمولة بلقطات يونيو القديمة من `docs/marketing/screenshots/raw/` **عشان تبيّن المقاس بس** — بدّلها بلقطات جديدة قبل أي رفع.

### قواعد الكلام على الصور
وصف، مش ادعاء. ممنوع «مجاني» و«الأفضل» و«رقم ١» و«حمّل الآن» وأي سعر/عرض — سياسة بيانات Play بتمنعها على الصور.
مثال مقبول: «اسأل عن تربية طفلك». مثال مرفوض: «إجابات موثوقة ١٠٠٪».
