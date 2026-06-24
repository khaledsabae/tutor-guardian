/// Family parenting content — authentic Quran verses, hadiths, and practical
/// parenting tips used for daily push notifications.
///
/// All hadith are from Sahih al-Bukhari, Sahih Muslim, or graded sahih by
/// al-Albani. All verses are parenting-related. Tips are short, actionable,
/// and rooted in the same sources. No generic morning/evening adhkar.
library;

class ParentingContent {
  final String text;
  final String source;
  final String topic;
  /// 'hadith' | 'verse' | 'tip'
  final String kind;

  const ParentingContent({
    required this.text,
    required this.source,
    required this.topic,
    required this.kind,
  });
}

const List<ParentingContent> familyAdhkar = [
  // ── Hadiths on upbringing ───────────────────────────────────────────
  ParentingContent(
    text: 'ما نحل والد ولداً من نحل أفضل من أدب حسن',
    source: 'رواه الترمذي وحسّنه، وصححه الألباني',
    topic: 'الأدب',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'كلكم راعٍ وكلكم مسؤول عن رعيته',
    source: 'صحيح البخاري ٨٩٣، صحيح مسلم ١٨٢٩',
    topic: 'المسؤولية',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'اتقوا الله واعدلوا بين أولادكم',
    source: 'صحيح البخاري ٢٥٨٧، صحيح مسلم ١٦٢٣',
    topic: 'العدل',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'إن الرفق لا يكون في شيء إلا زانه، ولا يُنزع من شيء إلا شانه',
    source: 'صحيح مسلم ٢٥٩٤',
    topic: 'الرفق',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'من لا يَرحم لا يُرحم',
    source: 'صحيح البخاري ٥٩٩٧، صحيح مسلم ٢٣١٨',
    topic: 'الرحمة',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'ارحموا من في الأرض يرحمكم من في السماء',
    source: 'صحيح — رواه الترمذي وصححه الألباني',
    topic: 'الرحمة',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'إن الله رفيق يحب الرفق في الأمر كله',
    source: 'صحيح البخاري ٦٩٢٧، صحيح مسلم ٢٥٩٣',
    topic: 'الرفق',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'خيركم خيركم لأهله، وأنا خيركم لأهلي',
    source: 'صحيح — رواه الترمذي وصححه الألباني',
    topic: 'الزوجية',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'استوصوا بالنساء خيراً',
    source: 'صحيح البخاري ٥١٨٦، صحيح مسلم ١٤٦٨',
    topic: 'الزوجية',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'ليس منا من لم يرحم صغيرنا ويعرف حق كبيرنا',
    source: 'رواه أحمد والترمذي وصححه الألباني',
    topic: 'الاحترام المتبادل',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'تبسمك في وجه أخيك صدقة',
    source: 'رواه الترمذي وصححه الألباني',
    topic: 'الابتسامة في البيت',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'إذا مات ابن آدم انقطع عمله إلا من ثلاث: صدقة جارية، أو علم ينتفع به، أو ولد صالح يدعو له',
    source: 'صحيح مسلم ١٦٣١',
    topic: 'الذرية الصالحة',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'من سلك طريقاً يلتمس فيه علماً سهل الله له به طريقاً إلى الجنة',
    source: 'صحيح مسلم ٢٦٩٩',
    topic: 'تشجيع التعلم',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'رضا الرب في رضا الوالد، وسخط الرب في سخط الوالد',
    source: 'رواه الترمذي وصححه الألباني',
    topic: 'بر الوالدين',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'رغم أنفه، رغم أنفه، رغم أنفه — من أدرك والديه عنده الكبر أحدهما أو كليهما ثم لم يدخل الجنة',
    source: 'صحيح مسلم ٢٥٥١',
    topic: 'بر الوالدين',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'المؤمن الذي يخالط الناس ويصبر على أذاهم أعظم أجراً من المؤمن الذي لا يخالط الناس ولا يصبر على أذاهم',
    source: 'رواه أحمد وابن ماجه وصححه الألباني',
    topic: 'الصبر على أطفالنا',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'عجباً لأمر المؤمن إن أمره كله خير … إن أصابته سراء شكر فكان خيراً له، وإن أصابته ضراء صبر فكان خيراً له',
    source: 'صحيح مسلم ٢٩٩٩',
    topic: 'الصبر والشكر',
    kind: 'hadith',
  ),
  ParentingContent(
    text: 'إنما الصبر عند الصدمة الأولى',
    source: 'صحيح البخاري ١٢٨٣، صحيح مسلم ٩٢٦',
    topic: 'الصبر',
    kind: 'hadith',
  ),
  // ── Quranic verses for parents ────────────────────────────────────────
  ParentingContent(
    text: 'رب اجعلني مقيم الصلاة ومن ذريتي ربنا وتقبل دعاء',
    source: 'سورة إبراهيم — آية ٤٠',
    topic: 'دعاء',
    kind: 'verse',
  ),
  ParentingContent(
    text: 'ربنا هب لنا من أزواجنا وذرياتنا قرة أعين واجعلنا للمتقين إماماً',
    source: 'سورة الفرقان — آية ٧٤',
    topic: 'دعاء',
    kind: 'verse',
  ),
  ParentingContent(
    text: 'رب أوزعني أن أشكر نعمتك التي أنعمت علي وعلى والدي وأن أعمل صالحاً ترضاه وأصلح لي في ذريتي',
    source: 'سورة الأحقاف — آية ١٥',
    topic: 'دعاء',
    kind: 'verse',
  ),
  ParentingContent(
    text: 'ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار',
    source: 'سورة البقرة — آية ٢٠١',
    topic: 'دعاء',
    kind: 'verse',
  ),
  ParentingContent(
    text: 'وَاعْبُدُوا اللَّهَ وَلَا تُشْرِكُوا بِهِ شَيْئاً ۖ وَبِالْوَالِدَيْنِ إِحْسَاناً',
    source: 'سورة النساء — آية ٣٦',
    topic: 'بر الوالدين',
    kind: 'verse',
  ),
  ParentingContent(
    text: 'يَا أَيُّهَا الَّذِينَ آمَنُوا قُوا أَنفُسَكُمْ وَأَهْلِيكُمْ نَاراً',
    source: 'سورة التحريم — آية ٦',
    topic: 'حماية الأسرة',
    kind: 'verse',
  ),
  ParentingContent(
    text: 'وَاللَّهُ جَعَلَ لَكُم مِّنْ أَنفُسِكُمْ أَزْوَاجاً وَجَعَلَ لَكُم مِّن أَزْوَاجِكُم بَنِينَ وَحَفَدَةً',
    source: 'سورة النحل — آية ٧٢',
    topic: 'الأسرة',
    kind: 'verse',
  ),
  ParentingContent(
    text: 'وَبِالْوَالِدَيْنِ إِحْسَاناً ۚ إِمَّا يَبْلُغَنَّ عِندَكَ الْكِبَرَ أَحَدُهُمَا أَوْ كِلَاهُمَا فَلَا تَقُل لَّهُمَا أُفٍّ وَلَا تَنْهَرْهُمَا',
    source: 'سورة الإسراء — آية ٢٣',
    topic: 'بر الوالدين',
    kind: 'verse',
  ),
  // ── Practical parenting tips (rooted in sources) ──────────────────────
  ParentingContent(
    text: 'ابدأ يومك بتبسّم في وجه أطفالك: الابتسامة صدقة، والبيت يتشكّل من أول لحظة صباح.',
    source: 'نصيحة تربوية — مستمدة من حديث: «تبسمك في وجه أخيك صدقة»',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'قبل النقد، امسح على رأس الطفل وخفّض صوتك: الرفق لا يكون في شيء إلا زانه.',
    source: 'نصيحة تربوية — مستمدة من حديث الرفق',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'خصّص ١٠ دقائق يوميًا تسمع فيها طفلك بلا مقاطعة — يشعره بالأمان والاحترام.',
    source: 'نصيحة تربوية',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'لا تقارن أطفالك ببعضهم أو بأبناء الآخرين؛ العدل بينهم يبدأ بإدراك فرديتهم.',
    source: 'نصيحة تربوية — مستمدة من: «اتقوا الله واعدلوا بين أولادكم»',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'علّم طفلك دعاء واحد هذا الأسبوع وردّده معه: العلم يسلّك به طريقاً إلى الجنة.',
    source: 'نصيحة تربوية — مستمدة من حديث العلم',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'احتفل بأصغر إنجاز بكلمة طيبة: الثناء البناء يُنشئ طفلاً واثقاً محباً للخير.',
    source: 'نصيحة تربوية',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'إذا غضبت من طفلك، خُذ نفساً قبل الرد: الصبر عند الصدمة الأولى.',
    source: 'نصيحة تربوية — مستمدة من حديث الصبر',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'اقرأ مع طفلك قصة نبي أو صحابي كل يوم قبل النوم: القلب ينبت بالقدوة.',
    source: 'نصيحة تربوية',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'لا تُلغي العبادة بالبيت؛ صلاة الجماعة مع الأطفال — ولو ركعتين — أقوى من ألف موعظة.',
    source: 'نصيحة تربوية',
    topic: 'نصيحة',
    kind: 'tip',
  ),
  ParentingContent(
    text: 'سامح نفسك على الأخطاء التربوية، واسأل الله التوفيق: الوالد راعٍ والراعي أحياناً يُخطئ ثم يُصلح.',
    source: 'نصيحة تربوية — مستمدة من حديث الراعي',
    topic: 'نصيحة',
    kind: 'tip',
  ),
];

/// Generic morning/evening adhkar were removed. All notifications now use
/// [familyAdhkar] which is exclusively parenting-related content.
