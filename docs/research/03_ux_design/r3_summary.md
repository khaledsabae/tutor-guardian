# UX Architecture & RTL Interface Design: Tutor Guardian

## 1. Architectural UX/UI Recommendations
### 1.1 Flutter Arabic RTL Engineering Safeguards
1. Wrap the entire app in a single `Directionality`/`MaterialApp` locale configuration and rely on `TextDirection.rtl` with `EdgeInsetsDirectional`, `AlignmentDirectional`, and `Padding` directional variants only, avoiding any hard-coded `left`/`right` values that will not flip under RTL.[web:9][web:19][web:14]
2. Standardize icon usage by preferring `Icons.arrow_back`, `Icons.chevron_left`, and other `matchTextDirection`-aware icons, and manually supply mirrored `Transform` or separate RTL assets only for non-reversible icons such as "search", "send", and "share" to prevent semantic reversal.[web:14][web:19]
3. Constrain text widgets with `maxLines`, `softWrap`, and responsive `FittedBox`/`LayoutBuilder` wrappers when using Arabic fonts like Tajawal or Cairo via packages such as `google_fonts_arabic` or `arabic_font`, and test on max system font scale to avoid clipping on narrow devices.[web:13][web:18][web:23]
4. For custom clippers, bezier paths, and physics-based animations (e.g., `Tween<Offset>` in `SlideTransition`), encapsulate the offset definitions in helper functions that take `TextDirection` and return mirrored values so that hero transitions, drawers, and sheets slide from the right edge in RTL without rebuilding separate widgets.[web:19][web:14]
5. Establish an RTL QA checklist: verify scroll physics (e.g., `PageView` swiping from right-to-left), nested `ListView`/`TabBar` indicators alignment, and hit targets for back/home actions on the right thumb zone, filing Flutter RTL bugs with minimal repros when framework defaults misalign, as recommended by the Flutter community.[web:14][web:19]

### 1.2 Culturally Aligned Gamification Alternatives
- **The Core Issue with Leaderboards:** Public leaderboards push users into extrinsic, competitive comparison, which empirical HCI and education studies link to increased stress, anxiety, and disengagement for lower-ranked participants, and which, in Islamic ethics, can overlap with showing off (Riya'a), cultivating pride, and valuing status over sincere intention and quiet consistency in good deeds.[web:11][web:16][web:21]
- **Alternative 1 (Intrinsic Progress):** Use a private "Parent Journey" timeline that only the family sees, where each completed lesson or reflection adds a subtle milestone card (date, topic, short dua or principle) and a soft progress meter for each child path, emphasizing narrative growth over numerical rank while allowing parents to scroll back and see how their intentions and actions have accumulated over weeks and months.[web:16][web:21]
- **Alternative 2 (Habit Consistency Rings):** Replace points with daily and weekly integrity rings that fill when parents perform micro-actions (e.g., reading one tip, reflecting with a child, logging a calm conversation), resetting gently without punishment, and visually highlighting streaks of consistency rather than volume, mirroring evidence that habit formation and self-regulation, not competition, drive sustainable behavioral change in educational settings.[web:16][web:21]

## 2. Information Architecture & Navigation Strategy
### 2.1 Navigation Layout Evaluation (Bottom Nav vs. Drawer vs. Tabs)
| Layout Option | Cognitive Load Score | RTL Usability Pitfalls | Recommended Approach for Tutor Guardian |
|---|---|---|---|
| Bottom Navigation | Low for 3–5 primary sections; thumb-friendly and aligns with modern Android/iOS patterns parents already know.[web:17][web:22] | Requires careful icon mirroring and short labels so Arabic text does not wrap or clip on small devices when system font scale is high.[web:19] | Use a 3–4 item bottom bar (Home, Paths, Chat, More) as the primary scaffold, with icons that respect `matchTextDirection` and concise Arabic labels. |
| Persistent Drawer | Medium–High due to hidden options; extra tap and vertical scanning for each navigation decision, which can slow stressed parents.[web:17][web:12] | Standard left-edge drawers feel reversed in RTL; right-edge drawers can conflict with system back gestures and are harder to reach for bottom-thumb use.[web:19] | Avoid as primary navigation; reserve a right-edge modal drawer for infrequent utilities (account, data sovereignty, settings) opened from a bottom "More" tab. |
| Custom Top Tabs | Medium; users must visually scan across the top, which is harder on large phones, but tabs are excellent for closely related sub-modes like switching between children or active paths.[web:17][web:22] | In RTL, tab order reverses; long Arabic labels can cause overflow and scrolling, and top placement is outside the comfortable thumb zone for one-handed use.[web:19][web:22] | Use scrollable top tabs only inside detail screens (e.g., Path Detail: Overview / Lessons / Reflections), keeping labels short and relying on the bottom nav for primary sections. |

## 3. Wireframe User Flows (ASCII/Text Layouts)
### 3.1 Global Navigation Map
[Onboarding Step 1]
|
v
[Onboarding Step 2]
|
v
[Onboarding Step 3 - Child Profile Summary]
|
v
[Home]
|
|
| --[Path Directory]
| |
| v
| [Path Detail]
| |
| v
| [Lesson Reader]
| |
| +--> [AI Chat Panel]
| ^
| |
| (context: lesson ID,
| child profile,
| active concern)
| --[Account & Data Sovereignty]

Bottom Navigation (persistent across main app after onboarding):
[Home] [Paths] [Chat] [More]

Tapping Paths opens Path Directory.

From Lesson Reader, opening AI Chat slides up a panel without leaving the route.

More opens a sheet/drawer with Account & Data Sovereignty, Language, and Support.

text

### 3.2 The Onboarding Stream (Step 1 to Step 3)
Screen: Step 1 - ترحيب

+--------------------------------------+

+--------------------------------------+

| شريط تقدم (● ○ ○) |

| العنوان: |

"مرحباً بك في Tutor Guardian"
نص تمهيدي قصير عن دور الوالدين
وأمان البيانات المحلية.
[زر أساسي عريض]: "ابدأ"
(ممتد بعرض الشاشة تقريباً،
في أسفل المنطقة الآمنة)
+------------------+-------------------+

+------------------+-------------------+
| "تخطي" | "التالي" |

Screen: Step 2 - بيانات الطفل الأساسية

+--------------------------------------+

+--------------------------------------+

| شريط تقدم (● ● ○) |

العنوان: "لنعرّف طفلك"
التسمية: "اسم الطفل"
[حقل إدخال نص عربي RTL]
مثال داخل الحقل: "محمد"
التسمية: "العمر"
[شريط تمرير / قائمة منسدلة]
4–6، 7–9، 10–12، 13–15
التسمية: "الجنس"
[أزرار اختيار متجاورة RTL]:
(●) ذكر (○) أنثى
+------------------+-------------------+

+------------------+-------------------+
| "السابق" | "التالي" |

Screen: Step 3 - أهم ما يشغلك الآن

+--------------------------------------+

+--------------------------------------+

| شريط تقدم (● ● ●) |

العنوان: "ما هو أهم ما يشغلك؟"
نص مساعد:
"اختر مجالاً واحداً ليركز عليه
التطبيق في النصائح اليومية."
[أزرار اختيار بحجم بطاقة]:
[الوقت على الشاشة والأجهزة]
[الطاعة والاحترام]
[الهدوء وإدارة الغضب]
[الهوية والقيم الإسلامية]
(+) خيار "غير ذلك" مع حقل نص
بسيط عند الاختيار.
مربع اختيار:
[] "أرغب في تفعيل النصيحة
اليومية الذكية"
+------------------+-------------------+

+------------------+-------------------+
| "السابق" | [إنهاء الإعداد]|

جميع الحقول RTL افتراضياً، مع محاذاة النص إلى اليمين
ومؤشرات الأخطاء أسفل الحقول بنفس المحاذاة.

text

## 4. Flutter Curated Package Ecosystem
Provide a strict, verified list of production-ready packages optimized for this architecture:
- **State Management:** `flutter_riverpod` + `riverpod_annotation` (Rationale: compile-time safety for dynamic context switching and the ability to keep lesson and chat providers decoupled yet synchronized via shared IDs and immutable models, following best-practice guidance on provider composition and auto-dispose/keepAlive strategies.[web:20][web:10][web:15])
- **Typography & Layout:** Use `google_fonts` with Arabic-capable families (e.g., Cairo, Tajawal) via `google_fonts_arabic` or `arabic_font`, combined with `MediaQuery.textScaleFactor` and responsive `LayoutBuilder` breakpoints to ensure legible RTL text on low-end regional Android devices without overflow.[web:13][web:18][web:23] Prefer `EdgeInsetsDirectional`, `AlignmentDirectional`, and `TextAlign.right`/`TextAlign.start` to respect RTL direction automatically.[web:19]
- **Animations/Micro-interactions:** Rely on Flutter’s built-in `AnimatedSwitcher`, `AnimatedOpacity`, and `ImplicitlyAnimatedReorderableList` where possible, and selectively introduce `animations` (Flutter team package) for container transforms and shared-axis transitions so that bottom-nav and chat panel transitions feel smooth without heavy custom physics that might break in RTL.[web:19][web:14] For more expressive, yet controlled micro-interactions, use `rive` or `lottie` with mirrored assets for RTL, ensuring all animations remain subtle and do not distract from reading and reflection.[web:23]

## 5. UI Quality & Performance Scoring
Evaluate the UX rendering strategy using the system framework:
\(Quality\_Score = \frac{Intuitiveness \times Accessibility - Component\_Friction}{Frame\_Drop\_Latency}\) [1]

- **Edge Case 1:** Font scaling breaking layout constraints when system accessibility font sizes are maxed out on regional low-end Android devices.
  - Treat all primary text containers as flexible: avoid fixed heights, wrap titles in `Flexible`/`Expanded`, and use `TextOverflow.ellipsis` with multi-line allowances so that Arabic words do not clip mid-glyph at high `textScaleFactor` values.[web:19][web:23]
  - Test with `textScaleFactor` ≥ 1.5 across Home, Path, and Lesson screens, iterating until critical actions remain visible above the fold; adjust bottom navigation icon+label sizes separately to keep tap targets large while preventing label wrapping.

- **Edge Case 2:** Chat overlay viewport layout overlapping native keyboard mechanics during RTL input switches.
  - Use `Scaffold` with `resizeToAvoidBottomInset: true` and a dedicated `SafeArea`-wrapped chat composer anchored to the bottom, ensuring the message list is inside a `Flexible` that resizes correctly when the keyboard appears in RTL.[web:19]
  - When opening the AI chat from the Lesson Reader, push a semi-modal bottom sheet (`showModalBottomSheet` with `isScrollControlled: true`) that occupies a fixed fraction of height on large phones but can expand full-screen, and verify that switching input methods (Arabic/English) does not shift the text field out of view by relying on `MediaQuery.viewInsets` rather than hard-coded paddings.

