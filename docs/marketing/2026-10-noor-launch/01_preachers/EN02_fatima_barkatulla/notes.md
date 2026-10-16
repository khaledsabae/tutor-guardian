# EN02: Ustadha Fatima Barkatulla (ملاحظات لخالد، ولا تُرسل)

# ⏸️ أرسِل بعد 1.0.74

**السبب:** الواجهة الإنجليزية ما زالت تُظهر عناوين دروس عربية بعد تبديل اللغة (الإصلاح في PR #137). وجمهور هذا الاسم إنجليزي بالكامل.

**قبل الإرسال:**
1. ثبّتوا 1.0.74 من Play.
2. بدّلوا لغة التطبيق إلى الإنجليزية.
3. افتحوا «اليوم» والمسارات وركن الطفل، وتأكّدوا ألا يظهر عنوان عربي.

## الصفحات العامة

تحقّقتُ منها في 2026-10-16:
- raisingbelievers.com
- linktr.ee/fatimabarkatulla
- يوتيوب: youtube.com/c/FatimaBarkatulla
- إنستغرام: @fatima_barkatulla
- X: @fatimabarkatula

## التركيز الحالي (مؤكَّد)

- «Raising Believers Islamic Parenting Masterclass» في لندن، و«Raising a Hafiz».
- مجموعات واتساب للأهل.
- تقدّم IslamiQA على Islam Channel.

## الزاوية

- تحديات الأسر المسلمة في الغرب، والواجهة الإنجليزية، وركن الطفل، والدرب اليومي.
- الإنفوجراف «When your child asks about Allah»، من الترجمة الإنجليزية للتطبيق نفسه (`i18n/en/lessons`)، وهو نفسه الذي في حزمة DA02.
- اللقطات إنجليزية، من قائمة المتجر 1.0.73.

## الكود

`EN02` (`EN` في السجل = دعاة بالإنجليزية).

```
curl -s "https://tg-api.alsaba.cloud/go?c=EN02" | grep -o 'referrer=ref_EN02'
```

## المخاطرة

لم أجد ما يُقلق.
