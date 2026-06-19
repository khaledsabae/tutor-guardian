# المربّي — دليل الأصول البصرية (Visual Assets Spec)

قائمة الصور المخصّصة المطلوبة لإثراء التطبيق بصريًا. **إنت تولّدها، وأنا أركّبها** بمجرد ما تبعتها.

## كيفية التسليم
- صيغة **PNG بخلفية شفافة** (إلا ما يُذكر غير ذلك).
- ضع كل ملف في مجلده بالاسم المحدّد بالظبط — التركيب وقتها تلقائي.
- لو مولّد الصور بيطلّع SVG، PNG عالي الدقة كافٍ ومفضّل.

## ستايل موحّد (الصق ده في بداية كل برومبت)
```
Flat modern vector illustration, soft rounded shapes, warm and friendly,
child-and-parent friendly, modest and appropriate for an Islamic family app,
NO realistic human faces (use simple symbolic or abstract figures, or none),
clean professional, consistent set style, transparent background.
Color palette: teal #0D9488, amber/gold #F59E0B, warm cream #FAF7F2,
emerald #10B981, ink #1E293B.
```

---

## 1) التميمة «نور» (فانوس) — `assets/images/mascot/`
الهوية البصرية الأساسية. شخصية رفيقة تظهر في كل التطبيق. **١٠٢٤×١٠٢٤**.

البرومبت الأساسي (+ الستايل الموحّد فوق):
```
A cute friendly glowing Ramadan lantern (fanoos) mascot, simple geometric
body, soft rounded edges, two small dot eyes and a tiny gentle smile,
NO human face, warm golden inner glow, teal and amber color scheme,
centered, soft long shadow. POSE: <…>
```
الملفات (نفس البرومبت، بدّل POSE):
| الملف | POSE | الاستخدام |
|---|---|---|
| `noor_idle.png` | `standing calmly, gentle glow` | الهوم / الترويسة |
| `noor_wave.png` | `waving hello with one little arm` | الترحيب / الأونبوردنج |
| `noor_celebrate.png` | `arms up, surrounded by sparkles, joyful` | الاحتفال بالمحطات |
| `noor_think.png` | `tilting with a small question mark above` | المساعد / لا نتائج |
| `noor_sleep.png` | `sleeping peacefully with Zzz` | الحالات الهادئة/المسائية |

## 2) رسومات الحالات الفارغة — `assets/images/empty/` (**٨٠٠×٦٠٠**)
| الملف | البرومبت (+ الستايل) | الاستخدام |
|---|---|---|
| `empty_children.png` | `an empty cozy nameplate / open door with a small star, inviting to add a first child profile` | شاشة «مفيش أطفال» |
| `empty_journey.png` | `an open blank journal with a tiny growing plant and a star, symbolizing a child's journey beginning` | الرحلة الفارغة |
| `empty_search.png` | `a friendly magnifying glass with a small dotted path, no results found` | البحث بدون نتائج |

## 3) أيقونات المحطات الإيمانية — `assets/images/milestones/` (**٥١٢×٥١٢**, badge شكل دائري)
البرومبت (+ الستايل): `Flat rounded circular badge icon with a soft gradient and a thin gold rim, emerald and amber accents, single centered symbol: <SYMBOL>, minimal modern Islamic style.`
| الملف | SYMBOL | المحطة |
|---|---|---|
| `shahada.png` | `a glowing white heart with a subtle crescent` | نطق الشهادة |
| `first_dua.png` | `two small raised duaa hands` | حفظ أول دعاء |
| `first_prayer.png` | `a small prayer rug` | أول صلاة |
| `keeps_prayer.png` | `a prayer rug with a shining star` | يحافظ على الصلاة |
| `first_surah.png` | `an open Quran with a soft light` | حفظ أول سورة |
| `first_fast.png` | `a crescent moon with a date fruit` | أول يوم صيام |
| `good_manner.png` | `a heart with a small star (good character)` | موقف خُلق حسن |
| `helped_others.png` | `two hands helping / a small gift` | ساعد غيره |
| `quran_khatma.png` | `a closed Quran with a golden ribbon and a trophy glow` | ختمة قرآن |

## 4) رسومات المجالات — `assets/images/domains/` (**٨٠٠×٦٠٠**)
البرومبت (+ الستايل): `Flat illustration scene representing <THEME>, simple symbolic figures (no realistic faces), <COLOR> dominant palette.`
| الملف | THEME | COLOR |
|---|---|---|
| `islamic_parenting.png` | `Islamic upbringing — a parent and child near a mosque silhouette and an open book` | emerald #10B981 |
| `development.png` | `child growth & development — a growing plant, building blocks, a brain-star` | purple #8B5CF6 |
| `cyber.png` | `digital safety — a friendly shield over a tablet` | blue #3B82F6 |
| `health.png` | `child health & wellbeing — a heart, an apple, a water drop` | rose #FB7185 |

## 5) مشاهد الأونبوردنج — `assets/images/onboarding/` (**٩٠٠×٧٠٠**)
| الملف | البرومبت (+ الستايل) |
|---|---|
| `ob_welcome.png` | `warm welcome scene — the lantern mascot Noor waving beside an open book, soft sunrise` |
| `ob_journey.png` | `a winding path with milestone stars leading up, a small plant growing, symbolizing the child's journey` |
| `ob_quran.png` | `an open Quran radiating soft light with floating stars and a crescent` |

---

## حالة التركيب (يحدّثها كلود)
- [ ] التميمة «نور» (٥)
- [ ] الحالات الفارغة (٣)
- [ ] محطات إيمانية (٩)
- [ ] رسومات المجالات (٤)
- [ ] أونبوردنج (٣)

> **المسار المفتوح المصدر** (كونفيتي الاحتفال) ✅ اتعمل بالفعل (إعادة استخدام `widgets/ui/celebration_overlay.dart`).
