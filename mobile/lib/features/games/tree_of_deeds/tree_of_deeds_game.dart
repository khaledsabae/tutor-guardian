/// Redesigned Tree of Deeds educational mini-game.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Tree of Deeds game.
class TreeOfDeedsGame extends EduGameShell {
  const TreeOfDeedsGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'tree_of_deeds',
            name: 'شجرة الأخلاق',
            heroEmoji: '🌳',
            description: 'قرارات تبني شخصية جميلة وتقربنا من الله',
            backgroundColor: Color(0xFF422006),
            surfaceColor: Color(0xFF713F12),
            accentColor: Color(0xFF84CC16),
            textColor: Colors.white,
          ),
          questionBuilder: _buildQuestions,
        );

  static List<EduQuestion> _buildQuestions(int level) {
    switch (level) {
      case 1:
        return const [
    EduQuestion(
      id: 'q_0',
      question: 'طفلك لقى محفظة على الأرض فيها فلوس. إيه الحاجة الصح؟',
      emoji: '💵',
      category: 'الأمانة',
      context: 'الأمانة من أهم القيم الإسلامية.',
      options: [
        EduOption(text: 'يدور على صاحبها أو يسلّمها لأقرب مسؤول', isCorrect: true, rationale: '✅ الأمانة واجب، وردّ المفقودات صفة محمودة.'),
        EduOption(text: 'ياخد الفلوس لأن محدش شافه', isCorrect: false, rationale: '❌ الرقابة البشرية مش معيار؛ الله بيراقب.'),
        EduOption(text: 'يسيبها مكانها', isCorrect: false, rationale: '❌ ممكن حد تاني ياخدها، الأفضل التسليم.'),
        EduOption(text: 'يشتري بيها حاجة عشان صاحبها مش هيعرف', isCorrect: false, rationale: '❌ دي سرقة.'),
      ],
    ),
    EduQuestion(
      id: 'q_1',
      question: 'ابنك جاب درجة عالية، وصاحبه جاب درجة أقل. إزاي تربيه على التواضع؟',
      emoji: '📚',
      category: 'التواضع',
      context: 'الفخر والتكبر صفات مذمومة.',
      options: [
        EduOption(text: 'نفرح بنجاحه ونشجعه يبارك لصاحبه ويساعده', isCorrect: true, rationale: '✅ التواضع والتعاون من أخلاق المؤمنين.'),
        EduOption(text: 'نقارنه بصاحبه عشان يفتخر', isCorrect: false, rationale: '❌ المقارنة بتولد تكبر أو غيرة.'),
        EduOption(text: 'نقوله \'أنا عارف إنك الأحسن\'', isCorrect: false, rationale: '❌ ده بيشجع على الكبر.'),
        EduOption(text: 'نسيبه يتباهى بدرجته', isCorrect: false, rationale: '❌ التباهي مش من الأخلاق الحميدة.'),
      ],
    ),
    EduQuestion(
      id: 'q_2',
      question: 'بنتك سمعت صاحبتها بتقول عليها كلام وحش. إيه ردّ فعلك؟',
      emoji: '🗣️',
      category: 'الغيبة',
      context: 'الغيبة والنميمة محرمات.',
      options: [
        EduOption(text: 'نعلّمها إن الغيبة حرام وننصحها تتكلم مع صاحبتها مباشرة', isCorrect: true, rationale: '✅ المواجهة الإيجابية أفضل من الرد بالغيبة.'),
        EduOption(text: 'نقول لها تردّ الغيبة عشان تدافع عن نفسها', isCorrect: false, rationale: '❌ الرد بالمعصية غلط.'),
        EduOption(text: 'نحكي للناس كلها عشان نشمت', isCorrect: false, rationale: '❌ النميمة أشد حرمة.'),
        EduOption(text: 'نسكت وما نعلّمهاش حاجة', isCorrect: false, rationale: '❌ التربية على الحدود ضرورية.'),
      ],
    ),
    EduQuestion(
      id: 'q_3',
      question: 'طفلك شاف حد كبير بيحتاج مساعدة في الشارع. إيه اللي نعلّمه؟',
      emoji: '🤝',
      category: 'الإحسان',
      context: 'بر الوالدين والإحسان للناس من الإسلام.',
      options: [
        EduOption(text: 'يساعده بطريقة آمنة، أو يسأل حد كبير قريب يساعد', isCorrect: true, rationale: '✅ الإحسان مع الحفاظ على الأمان.'),
        EduOption(text: 'يمشي وما يتدخلش عشان ميعرفوش', isCorrect: false, rationale: '❌ الإحسان للغريب من شيم المسلم.'),
        EduOption(text: 'ياخد فلوس مقابل المساعدة', isCorrect: false, rationale: '❌ الإحسان مش تجارة.'),
        EduOption(text: 'يسخر منه', isCorrect: false, rationale: '❌ السخرية من الناس ضد الأخلاق.'),
      ],
    ),
    EduQuestion(
      id: 'q_4',
      question: 'طفلك اتنرفز وكسر لعبة صاحبه. إيه اللي تعمليه؟',
      emoji: '😠',
      category: 'الغضب',
      context: 'الغضب والاعتداء على مال الغير مرفوضين.',
      options: [
        EduOption(text: 'بنعتذر، بدفع التصليح أو نشتري جديدة، ونتعلم ضبط النفس', isCorrect: true, rationale: '✅ المسؤولية والاعتذار من شيم المؤمن.'),
        EduOption(text: 'نقوله \'هو كان يستاهل\'', isCorrect: false, rationale: '❌ التبرير غلط.'),
        EduOption(text: 'نسيبه ما يعتذرش عشان كرامته', isCorrect: false, rationale: '❌ الاعتذار علامة قوة، مش ضعف.'),
        EduOption(text: 'نضربه عقاب', isCorrect: false, rationale: '❌ العنف مش تربية نبوية.'),
      ],
    ),
        ];
      case 2:
        return const [
    EduQuestion(
      id: 'q_5',
      question: 'في رمضان، طفلك عايز يفطر قدام صحابه عشان يثبت إنه \'راجل\'. إيه ردّك؟',
      emoji: '🌙',
      category: 'الصيام',
      context: 'الصيام فريضة والمحافظة عليها واجب.',
      options: [
        EduOption(text: 'نشرحله إن الصيام عبادة والشجاعة الحقيقية في طاعة الله', isCorrect: true, rationale: '✅ إعادة تعريف الشجاعة بالطاعة.'),
        EduOption(text: 'نسيبه يفطر عشان ما يتريقوش عليه', isCorrect: false, rationale: '❌ الخوف من الناس لا يبرر ترك الفرض.'),
        EduOption(text: 'نضربه عشان يصوم', isCorrect: false, rationale: '❌ العنف مش حل.'),
        EduOption(text: 'نقوله \'خلاص اعمل اللي انت عايزه\'', isCorrect: false, rationale: '❌ التربية تتطلب توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_6',
      question: 'طفلك شاف حد بيسرق من المحل. إيه اللي نعلّمه؟',
      emoji: '🛒',
      category: 'السرقة',
      context: 'السرقة حرام والإبلاغ عنها واجب.',
      options: [
        EduOption(text: 'يبلّغ البائع أو ولي أمره بأمان', isCorrect: true, rationale: '✅ منع الظلم والسرقة واجب.'),
        EduOption(text: 'يسكت عشان ما يتدخلش في حاجة مش بتاعته', isCorrect: false, rationale: '❌ السكوت عن المنكر مش جيد.'),
        EduOption(text: 'يسرق معاه', isCorrect: false, rationale: '❌ شريك في الإثم.'),
        EduOption(text: 'يصوّره وينشره', isCorrect: false, rationale: '❌ التشهير مش الحل المناسب للطفل.'),
      ],
    ),
    EduQuestion(
      id: 'q_7',
      question: 'إزاي تعلّم طفلك أهمية الصدق؟',
      emoji: '🤥',
      category: 'الصدق',
      context: 'الصدق منجاة والكذب مفتاح الشر.',
      options: [
        EduOption(text: 'بنكون قدوة في الصدق، وبنكافئه لما يعترف بالغلط', isCorrect: true, rationale: '✅ القدوة والثواب بتعزز الصدق.'),
        EduOption(text: 'بنضربه لما يكذب', isCorrect: false, rationale: '❌ العنف ممكن يخليه يكذب أكتر.'),
        EduOption(text: 'بنكذب عليه عشان \'نحسنه\'', isCorrect: false, rationale: '❌ القدوة بالكذب بتعلّمه الكذب.'),
        EduOption(text: 'بنقوله \'الكذب مش غلط لو ما حدش ضرر\'', isCorrect: false, rationale: '❌ الكذب محرم حتى بدون ضرر ظاهر.'),
      ],
    ),
    EduQuestion(
      id: 'q_8',
      question: 'طفلك عنده لعبة جديدة وصاحبه فقير مش عنده لعبة. إيه اللي نعمله؟',
      emoji: '🎁',
      category: 'الإيثار',
      context: 'الإحسان والإيثار من مكارم الإسلام.',
      options: [
        EduOption(text: 'نشجعه يشاركه اللعبة أو يديله لعبة قديمة', isCorrect: true, rationale: '✅ الإيثار بيورث المحبة.'),
        EduOption(text: 'نقوله \'خليه يشتري زيك\'', isCorrect: false, rationale: '❌ ده بيعلم الأنانية.'),
        EduOption(text: 'نمنعه من اللعب معاه', isCorrect: false, rationale: '❌ العكس هو الصح.'),
        EduOption(text: 'نقوله \'إحنا مش جمعية خيرية\'', isCorrect: false, rationale: '❌ الإحسان مش محصور على الجمعيات.'),
      ],
    ),
    EduQuestion(
      id: 'q_9',
      question: 'طفلك قال كلمة سيئة سمعها من التلفزيون. إيه ردّ فعلك؟',
      emoji: '📺',
      category: 'اللسان',
      context: 'اللسان ممكن يكون سبب دخول النار.',
      options: [
        EduOption(text: 'نشرحله إن الكلام فيه حساب، ونوجّهه للكلام الطيب', isCorrect: true, rationale: '✅ التوجيه أفضل من الزعيق.'),
        EduOption(text: 'نضربه عشان يفتكر', isCorrect: false, rationale: '❌ العنف مش أسلوب نبوي.'),
        EduOption(text: 'نضحك عشان طريفة', isCorrect: false, rationale: '❌ الضحك بيعزز السلوك.'),
        EduOption(text: 'نسيبه عشان سمعها من التلفزيون', isCorrect: false, rationale: '❌ المصدر مش مبرر.'),
      ],
    ),
        ];
      case 3:
        return const [
    EduQuestion(
      id: 'q_10',
      question: 'طفلك عايز يتبرع بفلوسه الصغيرة لحد محتاج. إيه ردّك؟',
      emoji: '🤲',
      category: 'الصدقة',
      context: 'الصدقة بتطهر المال وتنمي الإحسان.',
      options: [
        EduOption(text: 'نشجعه ونعلمه إن الصدقة بسيطة بتفرق', isCorrect: true, rationale: '✅ التشجيع على الإحسان.'),
        EduOption(text: 'نمنعه عشان فلوسه قليلة', isCorrect: false, rationale: '❌ القليل عند الله كثير.'),
        EduOption(text: 'نقوله يدّيها لينا عشان نصرفها', isCorrect: false, rationale: '❌ ده بيضيع فرصة التربية.'),
        EduOption(text: 'نستهزئ بيه', isCorrect: false, rationale: '❌ الاستهزاء بيقتل الإحسان.'),
      ],
    ),
    EduQuestion(
      id: 'q_11',
      question: 'طفلك سألك: \'ليه لازم أصلي؟\' إيه الإجابة المناسبة؟',
      emoji: '🕌',
      category: 'الصلاة',
      context: 'الصلاة عمود الدين.',
      options: [
        EduOption(text: 'لأنها تواصل مع الله، طاعة، وتنظيم لليوم', isCorrect: true, rationale: '✅ الربط بين العبادة والحياة.'),
        EduOption(text: 'عشان بابا وماما بيقولوا', isCorrect: false, rationale: '❌ التقليد مش كافي؛ محتاج فهم.'),
        EduOption(text: 'عشان الناس تشوفك كويس', isCorrect: false, rationale: '❌ الرياء مذموم.'),
        EduOption(text: 'عشان ربنا بيعاقب لو ما صليناش', isCorrect: false, rationale: '❌ الخوف بس مش تربية متوازنة.'),
      ],
    ),
    EduQuestion(
      id: 'q_12',
      question: 'طفلك بيضيع وقت الصلاة في اللعب. إزاي تتعاملي؟',
      emoji: '⏰',
      category: 'الصلاة',
      context: 'الترغيب والتسهيل أفضل من الإكراه.',
      options: [
        EduOption(text: 'نذكره بلطف ونخلي الصلاة حاجة ممتعة ومجتمعية', isCorrect: true, rationale: '✅ الترغيب والقدوة.'),
        EduOption(text: 'نضربه عشان يصلي', isCorrect: false, rationale: '❌ الصلاة بالإكراه مش مقبولة.'),
        EduOption(text: 'نسيبه عشان لسه صغير', isCorrect: false, rationale: '❌ التربية على العبادة بتبدأ بدري.'),
        EduOption(text: 'نزعقله قدام الناس', isCorrect: false, rationale: '❌ الإحراج بيبعد الطفل.'),
      ],
    ),
    EduQuestion(
      id: 'q_13',
      question: 'إزاي تعلّم طفلك احترام الكبار؟',
      emoji: '👴',
      category: 'الأدب',
      context: 'بر الوالدين والاحترام من الإسلام.',
      options: [
        EduOption(text: 'بنكون قدوة، وبنعلمه يسلم ويخفض صوته', isCorrect: true, rationale: '✅ القدوة والتعليم العملي.'),
        EduOption(text: 'بنقوله \'احترم\' بس', isCorrect: false, rationale: '❌ التلقين بدون قدوة مش فعّال.'),
        EduOption(text: 'بنضربه لما يتكلم بصوت عالي', isCorrect: false, rationale: '❌ العنف لا يعلّم أدباً.'),
        EduOption(text: 'نسمحله يتكلم مع الكبار زي ما يحب', isCorrect: false, rationale: '❌ الأدب له حدود.'),
      ],
    ),
    EduQuestion(
      id: 'q_14',
      question: 'طفلك شاف حد بيتنمر على صاحبه. إيه اللي يعمله؟',
      emoji: '🛑',
      category: 'الظلم',
      context: 'الظلم مرفوض.',
      options: [
        EduOption(text: 'يدافع عن صاحبه بأدب أو يبلّغ حد كبير', isCorrect: true, rationale: '✅ نصرة المظلوم واجب.'),
        EduOption(text: 'يضحك معاهم عشان ما يتنمروش عليه', isCorrect: false, rationale: '❌ ده شريك في الظلم.'),
        EduOption(text: 'يسكت عشان مش شغله', isCorrect: false, rationale: '❌ السكوت عن الظلم غلط.'),
        EduOption(text: 'يضرب المتنمر', isCorrect: false, rationale: '❌ الرد بالعنف مش حل.'),
      ],
    ),
        ];
      case 4:
        return const [
    EduQuestion(
      id: 'q_15',
      question: 'إزاي تعلّم طفلك شكر النعمة؟',
      emoji: '🙏',
      category: 'الشكر',
      context: 'الشكر بزيد في النعم.',
      options: [
        EduOption(text: 'نعلّمه يقول \'الحمد لله\' ونكتب معاه النعم اللي عنده', isCorrect: true, rationale: '✅ التطبيق العملي للشكر.'),
        EduOption(text: 'نقوله \'كل الناس عندها نفس حاجاتك\'', isCorrect: false, rationale: '❌ المقارنة مش شكر.'),
        EduOption(text: 'نمنعه من طلب حاجات', isCorrect: false, rationale: '❌ الشكر مش منع الرغبات.'),
        EduOption(text: 'نشتريله كل اللي يطلبه', isCorrect: false, rationale: '❌ الإسراف مش تربية.'),
      ],
    ),
    EduQuestion(
      id: 'q_16',
      question: 'طفلك عايز يصوم يوم كامل وهو لسه صغير. إيه تصرفك؟',
      emoji: '🌅',
      category: 'التدرج',
      context: 'التدرج في التربية.',
      options: [
        EduOption(text: 'نشجعه يبدأ بنصف يوم أو أيام بسيطة', isCorrect: true, rationale: '✅ التدرج يبني القدرة والمحبة.'),
        EduOption(text: 'نضطره على اليوم كامل', isCorrect: false, rationale: '❌ الإرهاق بيبعده عن الصيام.'),
        EduOption(text: 'نمنعه خالص', isCorrect: false, rationale: '❌ التشجيع المبكر مهم.'),
        EduOption(text: 'نسيبه ياكل سراً', isCorrect: false, rationale: '❌ التساهل في العبادات غلط.'),
      ],
    ),
    EduQuestion(
      id: 'q_17',
      question: 'طفلك لقى حاجة غالية اتنزلت من جيب حد. إيه الحاجة الصح؟',
      emoji: '👛',
      category: 'الأمانة',
      context: 'حفظ المال وردّه للمالك.',
      options: [
        EduOption(text: 'يسلّمها لصاحبها أو لأقرب مكان أمان', isCorrect: true, rationale: '✅ الأمانة والإحسان.'),
        EduOption(text: 'ياخدها عشان \'اللي يجد مالاً لا يخسر\'', isCorrect: false, rationale: '❌ هذا الخيار غير صحيح.'),
        EduOption(text: 'يبيعها ويشتري حاجة لنفسه', isCorrect: false, rationale: '❌ ده سرقة.'),
        EduOption(text: 'يسيبها مكانها', isCorrect: false, rationale: '❌ الأفضل التسليم.'),
      ],
    ),
    EduQuestion(
      id: 'q_18',
      question: 'إزاي تعلمي طفلك قيمة العفو؟',
      emoji: '🕊️',
      category: 'العفو',
      context: 'العفو من شيم الكرام.',
      options: [
        EduOption(text: 'نعلّمه إن العفو أقوى من الانتقام وأقرب للقلب الطيب', isCorrect: true, rationale: '✅ العفو صفة نبيلة.'),
        EduOption(text: 'نقوله \'مينفعش تسامح غلطك\'', isCorrect: false, rationale: '❌ العفو مش ضعف.'),
        EduOption(text: 'نضرب اللي زعله', isCorrect: false, rationale: '❌ الانتقام بالعنف غلط.'),
        EduOption(text: 'نتركه ينتقم بنفسه', isCorrect: false, rationale: '❌ الانتقام بيسبب دوامة.'),
      ],
    ),
    EduQuestion(
      id: 'q_19',
      question: 'طفلك رفض يساعد صاحبه عشان \'أنا مش بويا\'. إيه ردّك؟',
      emoji: '🤲',
      category: 'الإحسان',
      context: 'الإحسان مش مقصور على الأقارب.',
      options: [
        EduOption(text: 'نشرحله إن الإحسان للجميع، والله يحب المحسنين', isCorrect: true, rationale: '✅ الإحسان للغريب من شيم المسلم.'),
        EduOption(text: 'نقوله صح، مش لازم تساعد غريب', isCorrect: false, rationale: '❌ ده تعليم أنانية.'),
        EduOption(text: 'نحكّمه بفلوس', isCorrect: false, rationale: '❌ الإحسان مش بالمقابل.'),
        EduOption(text: 'نتركه يقرر هو', isCorrect: false, rationale: '❌ محتاج توجيه.'),
      ],
    ),
        ];
      case 5:
        return const [
    EduQuestion(
      id: 'q_20',
      question: 'إزاي تعلّم طفلك أهمية الاستغفار؟',
      emoji: '🌧️',
      category: 'الاستغفار',
      context: 'الاستغفار بيغسل الذنوب ويفتح الرزق.',
      options: [
        EduOption(text: 'نعلّمه يقول \'أستغفر الله\' لما يغلط، ونذكره إن الله غفور', isCorrect: true, rationale: '✅ الاستغفار تربية على التواضع والرجاء.'),
        EduOption(text: 'نقوله \'انت وحش\' لما يغلط', isCorrect: false, rationale: '❌ التجريح مش تربية.'),
        EduOption(text: 'نسيبه ما يعتذرش', isCorrect: false, rationale: '❌ الاستغفار جزء من التوبة.'),
        EduOption(text: 'نحاسبه على كل ذنب بعقاب', isCorrect: false, rationale: '❌ العقاب المستمر بيبعد الطفل من الله.'),
      ],
    ),
    EduQuestion(
      id: 'q_21',
      question: 'طفلك عايز يصرف مصروفه كله على ألعاب. إيه ردّك؟',
      emoji: '💰',
      category: 'إدارة المال',
      context: 'المال يحتاج إدارة.',
      options: [
        EduOption(text: 'نعلّمه يقسّم مصروفه: احتياجات، ادخار، وصدقة', isCorrect: true, rationale: '✅ التقسيم الصحيح.'),
        EduOption(text: 'نسيبه يصرف زي ما يحب', isCorrect: false, rationale: '❌ الإسراف مذموم.'),
        EduOption(text: 'نخلي المصروف كله علشان الأكل', isCorrect: false, rationale: '❌ محتاج توازن.'),
        EduOption(text: 'نمنعه من أي لعب', isCorrect: false, rationale: '❌ اللعب حق مشروع.'),
      ],
    ),
    EduQuestion(
      id: 'q_22',
      question: 'طفلك سألك: \'ليه رمضان مهم؟\' إيه الإجابة؟',
      emoji: '🌙',
      category: 'رمضان',
      context: 'رمضان شهر العبادة والتغيير.',
      options: [
        EduOption(text: 'شهر القرآن والصيام والتقرب لله والإحسان للناس', isCorrect: true, rationale: '✅ رمضان فيه عبادة وخلق.'),
        EduOption(text: 'عشان ناكل أكتر بالليل', isCorrect: false, rationale: '❌ ده تفسير سطحي.'),
        EduOption(text: 'عشان نشتري لبس جديد', isCorrect: false, rationale: '❌ دي عادات اجتماعية مش الجوهر.'),
        EduOption(text: 'عشان الناس تتريق على بعض', isCorrect: false, rationale: '❌ ده عكس روح رمضان.'),
      ],
    ),
    EduQuestion(
      id: 'q_23',
      question: 'إزاي تعلّم طفلك أهمية سلامة اللسان؟',
      emoji: '👅',
      category: 'اللسان',
      context: 'اللسان ممكن يدخل الجنة أو النار.',
      options: [
        EduOption(text: 'نعلّمه يقول خيراً أو يسكت، ونحذره من الكذب والغيبة', isCorrect: true, rationale: '✅ حماية اللسان.'),
        EduOption(text: 'نقوله \'قل اللي في قلبك\'', isCorrect: false, rationale: '❌ مش كل ما في القلب يقال.'),
        EduOption(text: 'نضربه لما يقول كلام غلط', isCorrect: false, rationale: '❌ العنف مش حل.'),
        EduOption(text: 'نسيبه يتعلم لوحده', isCorrect: false, rationale: '❌ محتاج توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_24',
      question: 'طفلك شاف حد بيتلفظ بألفاظ سيئة. إيه يعمل؟',
      emoji: '🚫',
      category: 'الأخلاق',
      context: 'الأذى بالقول مرفوض.',
      options: [
        EduOption(text: 'يمشي وما يقلدهوش، ويبلّغ لو محتاج', isCorrect: true, rationale: '✅ الحفاظ على الأخلاق.'),
        EduOption(text: 'يسمع ويتعلم', isCorrect: false, rationale: '❌ ده تعليق سلبي.'),
        EduOption(text: 'يرد بنفس الأسلوب', isCorrect: false, rationale: '❌ الرد بالمعصية غلط.'),
        EduOption(text: 'يسخر من الشخص', isCorrect: false, rationale: '❌ السخرية غلط.'),
      ],
    ),
        ];
      case 6:
        return const [
    EduQuestion(
      id: 'q_25',
      question: 'طفلك عايز يتبرع بدماغه (لعبة) لجار فقير. إيه ردّك؟',
      emoji: '🧸',
      category: 'الإيثار',
      context: 'الإيثار بتربية.',
      options: [
        EduOption(text: 'نشجعه ونعلمه إن العطاء بيجلب السعادة', isCorrect: true, rationale: '✅ الإيثار صفة حميدة.'),
        EduOption(text: 'نقوله \'إنت محتاجها\'', isCorrect: false, rationale: '❌ ده أنانية.'),
        EduOption(text: 'نمنعه', isCorrect: false, rationale: '❌ نمنع الإحسان.'),
        EduOption(text: 'نطلب من الجار يدفع', isCorrect: false, rationale: '❌ العطاء مش تجارة.'),
      ],
    ),
    EduQuestion(
      id: 'q_26',
      question: 'إزاي تعلّم طفلك أهمية قراءة القرآن؟',
      emoji: '📖',
      category: 'القرآن',
      context: 'القرآن هداية ونور.',
      options: [
        EduOption(text: 'نخلي قراءة القرآن جزء من الروتين اليومي، حتى لو آية واحدة', isCorrect: true, rationale: '✅ الاستمرار والتدرج.'),
        EduOption(text: 'نضربه لو ما قرأش', isCorrect: false, rationale: '❌ القرآن بالإكراه غلط.'),
        EduOption(text: 'نسيبه لحد ما يكبر', isCorrect: false, rationale: '❌ التربية بتبدأ بدري.'),
        EduOption(text: 'نقوله \'قرآن بس في رمضان\'', isCorrect: false, rationale: '❌ القرآن للكل سنة.'),
      ],
    ),
    EduQuestion(
      id: 'q_27',
      question: 'طفلك بيتكاسل عن الواجب. إيه التوجيه الصح؟',
      emoji: '📝',
      category: 'الأمانة',
      context: 'الأمانة في العمل.',
      options: [
        EduOption(text: 'نذكره بأهمية الواجب ونساعده يخطط للوقت', isCorrect: true, rationale: '✅ التنظيم والمسؤولية.'),
        EduOption(text: 'نعمل الواجب مكانه', isCorrect: false, rationale: '❌ ده بيعلم الاعتمادية.'),
        EduOption(text: 'نمنعه يلعب لحد ما يخلص بالقوة', isCorrect: false, rationale: '❌ العقاب المطول مش حل.'),
        EduOption(text: 'نسيبه وما نسألوش', isCorrect: false, rationale: '❌ المتابعة مهمة.'),
      ],
    ),
    EduQuestion(
      id: 'q_28',
      question: 'طفلك بيتكبر على صاحبه الفقير. إيه ردّك؟',
      emoji: '🦚',
      category: 'التكبر',
      context: 'التكبر محرم والفضل بالتقوى.',
      options: [
        EduOption(text: 'نعلّمه إن الله بيكرمهم وإن التقوى هي المعيار', isCorrect: true, rationale: '✅ تعليم التواضع والعدالة.'),
        EduOption(text: 'نقوله \'احنا فعلاً أحسن\'', isCorrect: false, rationale: '❌ ده تشجيع على التكبر.'),
        EduOption(text: 'نمنعه من صاحبه', isCorrect: false, rationale: '❌ العكس: نعلمه الإحسان.'),
        EduOption(text: 'نسيبه يتكبر', isCorrect: false, rationale: '❌ التكبر صفة مذمومة.'),
      ],
    ),
    EduQuestion(
      id: 'q_29',
      question: 'إزاي تربّي طفلك على الصبر؟',
      emoji: '⏳',
      category: 'الصبر',
      context: 'الصبر فضيلة عظيمة.',
      options: [
        EduOption(text: 'نعلّمه يتنفس، يقول \'اللهم أجرني في مصيبتي\'، ونكون قدوة', isCorrect: true, rationale: '✅ الأدوات العملية للصبر.'),
        EduOption(text: 'نشتريله اللي يطلبه عشان ما يزعلش', isCorrect: false, rationale: '❌ ده بيعلم عدم الصبر.'),
        EduOption(text: 'نقوله \'بطل زعلان\'', isCorrect: false, rationale: '❌ تجاهل المشاعر مش حل.'),
        EduOption(text: 'نضربه عشان يصبر', isCorrect: false, rationale: '❌ العنف عكس الصبر.'),
      ],
    ),
        ];
      case 7:
        return const [
    EduQuestion(
      id: 'q_30',
      question: 'طفلك عنده عادة غلط زي الكذب. إزاي تتعاملي؟',
      emoji: '🔄',
      category: 'تعديل السلوك',
      context: 'تغيير العادات يحتاج صبر وتوجيه.',
      options: [
        EduOption(text: 'نلاحظ متى بيكذب، نفهم السبب، ونشجع الصدق', isCorrect: true, rationale: '✅ فهم السبب ومعالجة الجذر.'),
        EduOption(text: 'نسمّيه \'كذاب\'', isCorrect: false, rationale: '❌ التلصيق بيخلي الطفل يتقبل الصفة.'),
        EduOption(text: 'نضربه كل مرة', isCorrect: false, rationale: '❌ العنف بيزود الكذب.'),
        EduOption(text: 'نسيبه عشان هيمرحلة', isCorrect: false, rationale: '❌ لازم تدخل.'),
      ],
    ),
    EduQuestion(
      id: 'q_31',
      question: 'طفلك سألك: \'إزاي أحبّ ربنا؟\' إيه الإجابة؟',
      emoji: '❤️',
      category: 'محبة الله',
      context: 'محبة الله بتتعلم بالعبادة والشكر.',
      options: [
        EduOption(text: 'بطاعته، شكر نعمه، وذكره دايماً', isCorrect: true, rationale: '✅ المحبة تتجلى في الطاعة.'),
        EduOption(text: 'بس لو ربنا أدالنا اللي عايزينه', isCorrect: false, rationale: '❌ العلاقة مش مقايضة.'),
        EduOption(text: 'مش محتاج تعمل حاجة', isCorrect: false, rationale: '❌ الإيمان يتطلب عمل.'),
        EduOption(text: 'بالخوف منه بس', isCorrect: false, rationale: '❌ المحبة والخوف متوازنان.'),
      ],
    ),
    EduQuestion(
      id: 'q_32',
      question: 'إزاي تعلّم طفلك حدود اللعب مع الجيران؟',
      emoji: '🏠',
      category: 'حقوق الجار',
      context: 'حقوق الجار مهمة في الإسلام.',
      options: [
        EduOption(text: 'نعلمه يحترم وقتهم وما يعملش ضجة في أوقات الراحة', isCorrect: true, rationale: '✅ احترام الجار.'),
        EduOption(text: 'نسيبه يلعب زي ما يحب', isCorrect: false, rationale: '❌ ده إزعاج.'),
        EduOption(text: 'نمنعه من اللعب بره خالص', isCorrect: false, rationale: '❌ ده قصوى.'),
        EduOption(text: 'نقوله \'الجار مش مهم\'', isCorrect: false, rationale: '❌ الجار له حقوق.'),
      ],
    ),
    EduQuestion(
      id: 'q_33',
      question: 'طفلك عايز يدّي فلوس لمتسول في الشارع. إيه توجيهك؟',
      emoji: '🪙',
      category: 'الصدقة',
      context: 'الصدقة محمودة بس بالحكمة.',
      options: [
        EduOption(text: 'نشجّع الإحسان ونوجهه للجمعات الموثوقة أو الطعام بدل النقد أحياناً', isCorrect: true, rationale: '✅ الصدقة بالحكمة.'),
        EduOption(text: 'نقوله ده كله نصابين', isCorrect: false, rationale: '❌ التعميم غلط.'),
        EduOption(text: 'نمنعه من العطاء', isCorrect: false, rationale: '❌ الإحسان مهم.'),
        EduOption(text: 'نسيبه يدي كل فلوسه', isCorrect: false, rationale: '❌ محتاج توازن.'),
      ],
    ),
    EduQuestion(
      id: 'q_34',
      question: 'إزاي تعلّم طفلك قيمة الوقت؟',
      emoji: '⏰',
      category: 'الوقت',
      context: 'الوقت من أغلى النعم.',
      options: [
        EduOption(text: 'نعلّمه ينظم يومه: لعب، صلاة، دراسة، نوم', isCorrect: true, rationale: '✅ التنظيم يحترم الوقت.'),
        EduOption(text: 'نسيبه يعمل اللي يحبه', isCorrect: false, rationale: '❌ بدون تنظيم بيضيع الوقت.'),
        EduOption(text: 'نجبره يدرس طول اليوم', isCorrect: false, rationale: '❌ الوقت يحتاج توازن.'),
        EduOption(text: 'نقوله \'لسه صغير\'', isCorrect: false, rationale: '❌ التربية على الوقت بتبدأ بدري.'),
      ],
    ),
        ];
      case 8:
        return const [
    EduQuestion(
      id: 'q_35',
      question: 'طفلك عنده خلاف مع صاحبه. إزاي تحلي الموقف؟',
      emoji: '🕊️',
      category: 'الصلح',
      context: 'الصلح بين الناس محبوب.',
      options: [
        EduOption(text: 'نعلّمه يعتذر أو يعفو ويحاول يفهم وجهة نظر صاحبه', isCorrect: true, rationale: '✅ الصلح والعفو.'),
        EduOption(text: 'نقوله \'ما تكلمش صاحبك تاني\'', isCorrect: false, rationale: '❌ قطع العلاقات مش حل.'),
        EduOption(text: 'نزعق لصاحبه', isCorrect: false, rationale: '❌ الأهل مش يتدخلوا بالعنف.'),
        EduOption(text: 'نسيبهم يتخانقوا', isCorrect: false, rationale: '❌ محتاج توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_36',
      question: 'طفلك شاف حد بيضرب حيوان. إيه يعمل؟',
      emoji: '🐈',
      category: 'الرحمة',
      context: 'الرحمة بالحيوان من الإسلام.',
      options: [
        EduOption(text: 'يمنعه بلطف أو يبلّغ حد كبير عن إيذاء الحيوان', isCorrect: true, rationale: '✅ الرحمة بالحيوان.'),
        EduOption(text: 'يضحك', isCorrect: false, rationale: '❌ ده قسوة.'),
        EduOption(text: 'يسيبه عشان مش شغله', isCorrect: false, rationale: '❌ الرحمة واجبة.'),
        EduOption(text: 'يضرب الشخص', isCorrect: false, rationale: '❌ الرد بالعنف غلط.'),
      ],
    ),
    EduQuestion(
      id: 'q_37',
      question: 'إزاي تعلّم طفلك أهمية دعاء الوالدين؟',
      emoji: '👨‍👩‍👧',
      category: 'بر الوالدين',
      context: 'دعاء الوالدين مستجاب.',
      options: [
        EduOption(text: 'نعلّمه يرضّيهما ويسأل ربنا يحفظهم ويدخّلهم الجنة', isCorrect: true, rationale: '✅ بر الوالدين بالفعل والدعاء.'),
        EduOption(text: 'نقوله مش مهم', isCorrect: false, rationale: '❌ دعاء الوالدين عظيم.'),
        EduOption(text: 'نطلب منه يدعي بس من غير ما يساعد', isCorrect: false, rationale: '❌ العمل أولاً.'),
        EduOption(text: 'نخافه من غضبهم', isCorrect: false, rationale: '❌ البر مش خوف.'),
      ],
    ),
    EduQuestion(
      id: 'q_38',
      question: 'طفلك عايز يشارك في مسابقة تمثيل فيها رقص. إيه ردّك؟',
      emoji: '🎭',
      category: 'الحدود',
      context: 'الحدود الشرعية في الترفيه.',
      options: [
        EduOption(text: 'نشجّع مواهب محترمة تليق بأخلاق المسلم', isCorrect: true, rationale: '✅ توجيه المواهب للحلال.'),
        EduOption(text: 'نسيبه يشارك في أي حاجة', isCorrect: false, rationale: '❌ الحدود مهمة.'),
        EduOption(text: 'نمنعه من أي نشاط فني', isCorrect: false, rationale: '❌ الفنون الحلال موجودة.'),
        EduOption(text: 'نخاف من سمعتنا فقط', isCorrect: false, rationale: '❌ المعيار مش السمعة.'),
      ],
    ),
    EduQuestion(
      id: 'q_39',
      question: 'إزاي تعلّم طفلك أهمية النية؟',
      emoji: '🎯',
      category: 'النية',
      context: 'الأعمال بالنيات.',
      options: [
        EduOption(text: 'نشرحله إن السبب وراء العمل أهم من العمل نفسه عند الله', isCorrect: true, rationale: '✅ تعليم الإخلاص.'),
        EduOption(text: 'نقوله \'المهم تخلص\'', isCorrect: false, rationale: '❌ النية مهمة.'),
        EduOption(text: 'نسيبه يعمل عشوائي', isCorrect: false, rationale: '❌ محتاج توجيه.'),
        EduOption(text: 'نكافئه بس على النتيجة', isCorrect: false, rationale: '❌ النية والجهد مهمان.'),
      ],
    ),
        ];
      case 9:
        return const [
    EduQuestion(
      id: 'q_40',
      question: 'طفلك عايز يصرف فلوسه على حاجة غير مفيدة. إيه تصرفك؟',
      emoji: '🛍️',
      category: 'إدارة المال',
      context: 'المال فيه حق لله وللنفس وللآخرين.',
      options: [
        EduOption(text: 'نناقش معاه: محتاج ولا رغبة؟ ونعلمه يأجل الفراغة', isCorrect: true, rationale: '✅ التفكير قبل الشراء.'),
        EduOption(text: 'نسيبه يصرف زي ما يحب', isCorrect: false, rationale: '❌ الإسراف مذموم.'),
        EduOption(text: 'نمنعه يصرف فلوسه خالص', isCorrect: false, rationale: '❌ محتاج يتعلم الإدارة.'),
        EduOption(text: 'نشترله نفس الحاجة أحسن', isCorrect: false, rationale: '❌ ده مش تعليم.'),
      ],
    ),
    EduQuestion(
      id: 'q_41',
      question: 'طفلك بيتكاسل عن صلاة الفجر. إيه الحل؟',
      emoji: '🌅',
      category: 'الصلاة',
      context: 'الفجر صلاة صعبة بس عظيمة.',
      options: [
        EduOption(text: 'ننام بدري، نحط منبه، ونساعد بعض في الاستيقاظ', isCorrect: true, rationale: '✅ العادات والمساعدة.'),
        EduOption(text: 'نضربه عشان يصحى', isCorrect: false, rationale: '❌ العنف في العبادة غلط.'),
        EduOption(text: 'نسيبه ينام', isCorrect: false, rationale: '❌ التربية على الصلاة مستمرة.'),
        EduOption(text: 'نقوله \'ما تنفعش الصلاة لو نايم\'', isCorrect: false, rationale: '❌ النوم معذور بس نساعده.'),
      ],
    ),
    EduQuestion(
      id: 'q_42',
      question: 'إزاي تعلّم طفلك الاستئذان قبل الدخول؟',
      emoji: '🚪',
      category: 'الأدب',
      context: 'الاستئذان آداب.',
      options: [
        EduOption(text: 'نعلّمه يدق ويستأذن قبل ما يدخل على حد', isCorrect: true, rationale: '✅ الاستئذان أدب.'),
        EduOption(text: 'نسيبه يدخل عادي', isCorrect: false, rationale: '❌ ده عدم احترام.'),
        EduOption(text: 'نضربه لو دخل من غير استئذان', isCorrect: false, rationale: '❌ العنف مش حل.'),
        EduOption(text: 'نقوله \'إنت في بيتك\'', isCorrect: false, rationale: '❌ الاستئذان مطلوب حتى في البيت.'),
      ],
    ),
    EduQuestion(
      id: 'q_43',
      question: 'طفلك سألك: \'ليه الناس بتعمل عيد الميلاد؟\' إيه ردّك؟',
      emoji: '🎄',
      category: 'الهوية',
      context: 'الهوية الإسلامية.',
      options: [
        EduOption(text: 'نشرحله إن دي أعياد غير مسلمة وإحنا عندنا أعيادنا الإسلامية', isCorrect: true, rationale: '✅ التعليم بلطف وحفظ الهوية.'),
        EduOption(text: 'نقوله \'خلاص انس الموضوع\'', isCorrect: false, rationale: '❌ المنع بدون تفسير.'),
        EduOption(text: 'نشجعه يحتفل معاهم عشان يتقبلوا', isCorrect: false, rationale: '❌ ده ضعف للهوية.'),
        EduOption(text: 'نخافه منهم', isCorrect: false, rationale: '❌ التخويف مش تربية.'),
      ],
    ),
    EduQuestion(
      id: 'q_44',
      question: 'إزاي تعلّم طفلك أهمية الأمانة في المدرسة؟',
      emoji: '✏️',
      category: 'الأمانة',
      context: 'الأمانة في العلم والامتحانات.',
      options: [
        EduOption(text: 'نعلّمه إن الغش سرقة للعلم ومخالفة للأمانة', isCorrect: true, rationale: '✅ ربط الأمانة بالدراسة.'),
        EduOption(text: 'نقوله \'الغش عادي كل بيعمله\'', isCorrect: false, rationale: '❌ التبرير غلط.'),
        EduOption(text: 'نمنعه من المذاكرة', isCorrect: false, rationale: '❌ العكس.'),
        EduOption(text: 'نسيبه يعمل اللي يقدر عليه', isCorrect: false, rationale: '❌ محتاج توجيه أخلاقي.'),
      ],
    ),
        ];
      case 10:
        return const [
    EduQuestion(
      id: 'q_45',
      question: 'إزاي تبني شخصية طفلك الإسلامية بشكل متوازن؟',
      emoji: '🌳',
      category: 'التربية الشاملة',
      context: 'التربية الإسلامية شاملة.',
      options: [
        EduOption(text: 'عبادة، أخلاق، علم، وعاطفة — كلها مع بعض بالقدوة والحب', isCorrect: true, rationale: '✅ التربية المتكاملة.'),
        EduOption(text: 'بس صلاة وصيام', isCorrect: false, rationale: '❌ العبادات وحدها مش كافية.'),
        EduOption(text: 'بقواعد صارمة فقط', isCorrect: false, rationale: '❌ القسوة تبعد.'),
        EduOption(text: 'بترك الطفل يختار بنفسه', isCorrect: false, rationale: '❌ محتاج توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_46',
      question: 'طفلك سألك: \'إيه معنى التقوى؟\'',
      emoji: '🛡️',
      category: 'التقوى',
      context: 'التقوى أساس كل خير.',
      options: [
        EduOption(text: 'إنك تتق الله في السر والعلن، فتفعل الخير وتترك المنكر', isCorrect: true, rationale: '✅ التقوى هي الحذر من الله.'),
        EduOption(text: 'إنك تلبس لبس معين', isCorrect: false, rationale: '❌ التقوى ليست شكل.'),
        EduOption(text: 'إنك ما تفرحش أبداً', isCorrect: false, rationale: '❌ التقوى مش حزن.'),
        EduOption(text: 'إنك تعيش في مسجد', isCorrect: false, rationale: '❌ التقوى في كل مكان.'),
      ],
    ),
    EduQuestion(
      id: 'q_47',
      question: 'طفلك عايز يشتري حاجة بالفلوس اللي جمعها للصدقة. إيه ردّك؟',
      emoji: '💝',
      category: 'النية',
      context: 'النية والإخلاص.',
      options: [
        EduOption(text: 'نعلّمه إن الله بيراقب القلوب والنية، ونشجعه يصرفها في المقصد الأصلي', isCorrect: true, rationale: '✅ تعليم الإخلاص.'),
        EduOption(text: 'نسيبه يعمل اللي يحبه', isCorrect: false, rationale: '❌ النية تتغير بدون توجيه.'),
        EduOption(text: 'نزعق له', isCorrect: false, rationale: '❌ العنف مش حل.'),
        EduOption(text: 'نقوله \'خلاص مش مهم\'', isCorrect: false, rationale: '❌ النية مهمة.'),
      ],
    ),
    EduQuestion(
      id: 'q_48',
      question: 'إزاي تعلّم طفلك أهمية الاستعانة بالله؟',
      emoji: '🤲',
      category: 'التوكل',
      context: 'التوكل والأخذ بالأسباب.',
      options: [
        EduOption(text: 'نساعده يبذل جهد ويدعو: \'حسبي الله ونعم الوكيل\'', isCorrect: true, rationale: '✅ الأخذ بالأسباب مع التوكل.'),
        EduOption(text: 'نقوله \'متعملش حاجة، ربنا هيعملها\'', isCorrect: false, rationale: '❌ التوكل مش كسل.'),
        EduOption(text: 'نخليه يعتمد على نفسه بس', isCorrect: false, rationale: '❌ الإنسان محتاج ربنا.'),
        EduOption(text: 'نخافه من الفشل', isCorrect: false, rationale: '❌ الخوف مش توكل.'),
      ],
    ),
    EduQuestion(
      id: 'q_49',
      question: 'إيه أهم درس تربوي إسلامي تعلمته النهاردة؟',
      emoji: '🧠',
      category: 'المراجعة',
      context: 'المراجعة بتثبت التعلم.',
      options: [
        EduOption(text: 'الإحسان والأمانة والصدق أساس حياة المسلم', isCorrect: true, rationale: '✅ الملخص الصحيح.'),
        EduOption(text: 'المهم نصوم ونصلي بس', isCorrect: false, rationale: '❌ العبادات والأخلاق مع بعض.'),
        EduOption(text: 'الناس كلها وحشة', isCorrect: false, rationale: '❌ التعميم غلط.'),
        EduOption(text: 'ما فيش حاجة اتغيرت', isCorrect: false, rationale: '❌ التعلم بيفرق.'),
      ],
    ),
        ];
      default:
        return _buildQuestions(1);
    }
  }
}
