/// Redesigned Emotion Maze educational mini-game.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Emotion Maze game.
class EmotionMazeGame extends EduGameShell {
  const EmotionMazeGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'emotion_maze',
            name: 'متاهة المشاعر',
            heroEmoji: '🧠',
            description: 'تعلّم كيف تتعامل مع المشاعر وتحل الأزمات الأسرية بهدوء',
            backgroundColor: Color(0xFF2E1065),
            surfaceColor: Color(0xFF4C1D95),
            accentColor: Color(0xFFA855F7),
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
      question: 'طفلك بيعيط بقوة عشان لعبته وقعت واتكسرت. إيه أول ردّ فعل يساعده؟',
      emoji: '🧸',
      category: 'التعاطف',
      context: 'التعاطف بيمنح الطفل أمان عاطفي.',
      options: [
        EduOption(text: '\'أنا فاهم إنك زعلان. تعالى ناخد نفس ونشوف نصلحها ولا نعمل حاجة تانية\'', isCorrect: true, rationale: '✅ التعاطف + التنظيم العاطفي + الحل.'),
        EduOption(text: '\'متعيطش، دي لعبة بس\'', isCorrect: false, rationale: '❌ تقليل مشاعره بيخلي يكتم.'),
        EduOption(text: '\'هاجبلك واحدة جديدة بكرة\'', isCorrect: false, rationale: '❌ ده بيهرب من التعامل مع الزعل.'),
        EduOption(text: '\'زعلان ليه؟ إنت كبير\'', isCorrect: false, rationale: '❌ الضغط على الطفل يبطل زعل مش صحي.'),
      ],
    ),
    EduQuestion(
      id: 'q_1',
      question: 'صاحبة بنتك خدت لعبة من إيدها من غير ما تسأل. إزاي تساعدي بنتك تتصرف؟',
      emoji: '🙋‍♀️',
      category: 'الحدود',
      context: 'تعليم الأطفال التعبير عن حدودهم بطريقة محترمة.',
      options: [
        EduOption(text: '\'ممكن تقولي: أنا لسه بلعب بيها، هنلعب بيها مع بعض بعد شوية\'', isCorrect: true, rationale: '✅ تعبير واضح ومهذب عن الحدود.'),
        EduOption(text: '\'خليها تاخدها، إنتي مش محتاجاها\'', isCorrect: false, rationale: '❌ ده بيعلم إن مشاعرها مش مهمة.'),
        EduOption(text: '\'هاتيها بالعافية من إيدها\'', isCorrect: false, rationale: '❌ العنف مش حل.'),
        EduOption(text: '\'متكلميهاش تاني\'', isCorrect: false, rationale: '❌ قطع العلاقات مش تربية.'),
      ],
    ),
    EduQuestion(
      id: 'q_2',
      question: 'طفلك قاللك \'أنا مش عارف أتكلم قدام الناس\'. إيه ردّك الداعم؟',
      emoji: '🗣️',
      category: 'القلق',
      context: 'القلق الاجتماعي شائع في الطفولة.',
      options: [
        EduOption(text: '\'أنا فاهم، خلينا نتدرب مع بعض في البيت الأول\'', isCorrect: true, rationale: '✅ التدريج والدعم.'),
        EduOption(text: '\'إنت لازم تتكلم، متخافش\'', isCorrect: false, rationale: '❌ التصحيح بدون تدريب بيضيف ضغط.'),
        EduOption(text: '\'إنت كده مش هتعرف تعمل حاجة\'', isCorrect: false, rationale: '❌ التخويف بيزود القلق.'),
        EduOption(text: '\'خلاص متتكلمش\'', isCorrect: false, rationale: '❌ التجنب بيقوّي القلق.'),
      ],
    ),
    EduQuestion(
      id: 'q_3',
      question: 'طفلك جاب درجة ضعيفة ومخبي الورقة. إيه تصرفك؟',
      emoji: '📄',
      category: 'الثقة',
      context: 'الخوف من الرد الفعل بيخلّي الطفل يكتم.',
      options: [
        EduOption(text: '\'مفيش مشكلة نتكلم مع بعض ونشوف إزاي نحسّن\'', isCorrect: true, rationale: '✅ الأمان النفسي بيساعد الطفل يواجه المشكلة.'),
        EduOption(text: '\'ليه خبيتها؟ إنت فاشل\'', isCorrect: false, rationale: '❌ التجريح بيبعد الطفل.'),
        EduOption(text: '\'هتعاقب لحد ما تجيب تقدير أحسن\'', isCorrect: false, rationale: '❌ العقاب مش تعليم.'),
        EduOption(text: '\'متقولش لحد\'', isCorrect: false, rationale: '❌ التستر على الأخطاء مش حل.'),
      ],
    ),
    EduQuestion(
      id: 'q_4',
      question: 'طفلك بيتعصب لما بيخسر في اللعبة. إزاي تساعده؟',
      emoji: '🏆',
      category: 'الخسارة',
      context: 'تقبل الخسارة مهارة اجتماعية مهمة.',
      options: [
        EduOption(text: '\'ممكن نزعل شوية، بس اللعب أهم من الفوز. تعالى نهنّي اللي كسب\'', isCorrect: true, rationale: '✅ تقبل المشاعر وتعليم الرياضة.'),
        EduOption(text: '\'إنت لازم تكسب عشان تبقى راجل\'', isCorrect: false, rationale: '❌ ربط الفوز بالهوية غلط.'),
        EduOption(text: '\'ما تلعبش تاني لو هتزعل\'', isCorrect: false, rationale: '❌ التجنب مش حل.'),
        EduOption(text: '\'هو بيغش أكيد\'', isCorrect: false, rationale: '❌ التبرير والاتهام بيعلم سلوك غلط.'),
      ],
    ),
        ];
      case 2:
        return const [
    EduQuestion(
      id: 'q_5',
      question: 'صاحب طفلك قاله \'لو مش هتلعب معايا، هاخد ألعابك\'. إيه تصرف صح؟',
      emoji: '🎲',
      category: 'الابتزاز',
      context: 'الابتزاز العاطفي بين الأطفال.',
      options: [
        EduOption(text: '\'كلام ده مش لطيف. ممكن تقوله: أنا مش هقبل التهديد\'', isCorrect: true, rationale: '✅ تعليم الوقوف ضد الابتزاز.'),
        EduOption(text: '\'يلا العب معاه عشان ما يزعلش\'', isCorrect: false, rationale: '❌ ده بيعلم الطفل يخضع للابتزاز.'),
        EduOption(text: '\'هات ألعابك وما تكلمش صاحبك تاني\'', isCorrect: false, rationale: '❌ قطع العلاقة مش أول حل.'),
        EduOption(text: '\'إنت ضعيف لو سمحت له\'', isCorrect: false, rationale: '❌ تجريح الطفل غلط.'),
      ],
    ),
    EduQuestion(
      id: 'q_6',
      question: 'طفلك قالك إن فيه حد بيتنمر عليه. إيه تعملي؟',
      emoji: '😢',
      category: 'التنمر',
      context: 'التنمر محتاج تدخل سريع وحاسم.',
      options: [
        EduOption(text: 'بتطمّنيه وتسأليه بالتفصيل وتتواصلي مع المدرسة', isCorrect: true, rationale: '✅ الإصغاء والتدخل المنظم.'),
        EduOption(text: '\'ردّ عليه زي ما بيعمل معاك\'', isCorrect: false, rationale: '❌ الرد بالعنف مش حل.'),
        EduOption(text: '\'إنسى الموضوع، ده عادي\'', isCorrect: false, rationale: '❌ التجاهل بيسمح للتنمر يستمر.'),
        EduOption(text: 'بتروحي تضربي المتنمرين', isCorrect: false, rationale: '❌ العنف من الأهل بيزود المشكلة.'),
      ],
    ),
    EduQuestion(
      id: 'q_7',
      question: 'بنتك رفضت تلبس فستان جديد عشان صحابها قالولها مش حلو. إيه ردّك؟',
      emoji: '👗',
      category: 'الثقة بالنفس',
      context: 'تأثير الأقران والثقة بالنفس.',
      options: [
        EduOption(text: '\'رأي صحابك مهم، بس رأيك في نفسك أهم. إنتي تحبّيه؟\'', isCorrect: true, rationale: '✅ التحقق من الذات وتعزيز الثقة.'),
        EduOption(text: '\'صحابك عندهم حق، يلا غيّري\'', isCorrect: false, rationale: '❌ ده بيضعف ثقة الطفل.'),
        EduOption(text: '\'إنتي مش هتسمعي لحد أبداً\'', isCorrect: false, rationale: '❌ رفض كل الرأي مش توازن.'),
        EduOption(text: '\'همنعك من صحابك\'', isCorrect: false, rationale: '❌ المنع التام مش حل.'),
      ],
    ),
    EduQuestion(
      id: 'q_8',
      question: 'طفلك بيتجنب صاحبه عشان اتخانقوا. إزاي تساعده يرجع يتكلم معاه؟',
      emoji: '🤝',
      category: 'حل الخلافات',
      context: 'حل الخلافات مهارة اجتماعية.',
      options: [
        EduOption(text: '\'ممكن تقوله: أنا آسف لو زعلتك، هنرجع صحاب؟\'', isCorrect: true, rationale: '✅ الاعتذار والمبادرة.'),
        EduOption(text: '\'إنت مالك، هو الغلطان\'', isCorrect: false, rationale: '❌ التحيز بيعلم الأنانية.'),
        EduOption(text: '\'هات كذا صاحب بدل واحد\'', isCorrect: false, rationale: '❌ الهروب من المشكلة مش حل.'),
        EduOption(text: '\'خلاص ما تكلمش صاحبك أبداً\'', isCorrect: false, rationale: '❌ قطع العلاقة مش حل.'),
      ],
    ),
    EduQuestion(
      id: 'q_9',
      question: 'طفلك بيقول \'أنا مش زاكي زي صاحبي\'. إيه ردّك؟',
      emoji: '🧠',
      category: 'المقارنة',
      context: 'المقارنة بتأثر الثقة.',
      options: [
        EduOption(text: '\'كل واحد عنده مواهب مختلفة. إنت شاطر في حاجات كتير\'', isCorrect: true, rationale: '✅ التركيز على الفردية والقوة.'),
        EduOption(text: '\'أيوا، لازم تتعب أكتر عشان توصله\'', isCorrect: false, rationale: '❌ المقارنة بتولد ضغط.'),
        EduOption(text: '\'إنت فعلاً أقل منه\'', isCorrect: false, rationale: '❌ ده بيزود الشعور بالنقص.'),
        EduOption(text: '\'مش مهم الدراسة\'', isCorrect: false, rationale: '❌ التقليل من التعليم مش حل.'),
      ],
    ),
        ];
      case 3:
        return const [
    EduQuestion(
      id: 'q_10',
      question: 'طفلك عنده أخ صغير جديد وبيدّي علامات غيرة. إزاي تتعاملي؟',
      emoji: '👶',
      category: 'الغيرة',
      context: 'الغيرة الطبيعية محتاجة إعادة تأمين.',
      options: [
        EduOption(text: '\'أنا فاهم إنك تحس إنك مش مركز. إنت كمان مهم جداً\'', isCorrect: true, rationale: '✅ إعادة تأمين الطفل.'),
        EduOption(text: '\'إنت كبير، لازم تفهم\'', isCorrect: false, rationale: '❌ التقليل من مشاعره بيزود الغيرة.'),
        EduOption(text: '\'لو هتزعل، هنبعد أخوك\'', isCorrect: false, rationale: '❌ التهديد والابتزاز غلط.'),
        EduOption(text: '\'أنا هعاقبك لو زعلت أخوك\'', isCorrect: false, rationale: '❌ العقاب بيزود العداوة.'),
      ],
    ),
    EduQuestion(
      id: 'q_11',
      question: 'طفلك بيتكسف يسأل المعلمة لما مش فاهم. إيه توجيهك؟',
      emoji: '🙋',
      category: 'السؤال',
      context: 'السؤال علامة قوة.',
      options: [
        EduOption(text: '\'السؤال شجاعة، والمعلمة هتحب تساعدك\'', isCorrect: true, rationale: '✅ إعادة إطار السؤال كقوة.'),
        EduOption(text: '\'إنت لازم تفهم لوحدك\'', isCorrect: false, rationale: '❌ الطفل محتاج مساعدة.'),
        EduOption(text: '\'لو سألت هيقولوا عليك غبي\'', isCorrect: false, rationale: '❌ ده بيزود الخجل.'),
        EduOption(text: '\'اسأل صاحبك بدل المعلمة\'', isCorrect: false, rationale: '❌ ممكن يضلّله.'),
      ],
    ),
    EduQuestion(
      id: 'q_12',
      question: 'طفلك قال كلام جارح لصاحبه وهو متضايق. إيه اللي يعمله؟',
      emoji: '💔',
      category: 'الاعتذار',
      context: 'الاعتذار بيصلح العلاقات.',
      options: [
        EduOption(text: '\'أنا آسف إن زعلتك. كلامي كان غلط\'', isCorrect: true, rationale: '✅ الاعتذار الصادق.'),
        EduOption(text: '\'إنت بدأت أنت\'', isCorrect: false, rationale: '❌ التبرير ما بيصلحش.'),
        EduOption(text: '\'خلاص ننسى\'', isCorrect: false, rationale: '❌ الاعتذار مهم للشفاء.'),
        EduOption(text: '\'هو كمان قالي كلام وحش\'', isCorrect: false, rationale: '❌ المقارنة ما بتعتذرش.'),
      ],
    ),
    EduQuestion(
      id: 'q_13',
      question: 'طفلك بيقلد سلوكيات غير لطيفة من صحابه عشان يتقبل. إيه ردّك؟',
      emoji: '🎭',
      category: 'ضغط الأقران',
      context: 'ضغط الأقران والهوية.',
      options: [
        EduOption(text: '\'اللي يحبّك هيقبلك زي ما إنت. متغيّرش عشان حد\'', isCorrect: true, rationale: '✅ تعزيز الهوية الصحيحة.'),
        EduOption(text: '\'إعمل زيهم عشان تبقى منهم\'', isCorrect: false, rationale: '❌ القبول بثمن غلط.'),
        EduOption(text: '\'إنت وحيد ومش محتاج صحاب\'', isCorrect: false, rationale: '❌ العزلة مش حل.'),
        EduOption(text: '\'همنعك منهم\'', isCorrect: false, rationale: '❌ المنع التام مش حل.'),
      ],
    ),
    EduQuestion(
      id: 'q_14',
      question: 'طفلك بيتكاسل عن المدرسة ويقول \'مش عايز أروح\'. إيه أول خطوة؟',
      emoji: '🏫',
      category: 'الرفض',
      context: 'الرفض ممكن يكون وراه سبب.',
      options: [
        EduOption(text: '\'تعالى نتكلم: إيه اللي مضايقك في المدرسة؟\'', isCorrect: true, rationale: '✅ فهم السبب قبل الحكم.'),
        EduOption(text: '\'لازم تروح، ما فيش كلام\'', isCorrect: false, rationale: '❌ ده بيهمل السبب.'),
        EduOption(text: '\'خلاص ما تروحش\'', isCorrect: false, rationale: '❌ التساهل مش حل.'),
        EduOption(text: '\'هتعاقب لو ما رحتش\'', isCorrect: false, rationale: '❌ العقاب قبل الفهم غلط.'),
      ],
    ),
        ];
      case 4:
        return const [
    EduQuestion(
      id: 'q_15',
      question: 'طفلك قالك إنه \'مش حاسس إنه محبوب\'. إيه ردّك؟',
      emoji: '❤️',
      category: 'الحب',
      context: 'احتياج الحب والانتماء أساسي.',
      options: [
        EduOption(text: '\'أنا بحبك جداً، وده مش مرتبط بأي حاجة بتعملها\'', isCorrect: true, rationale: '✅ الحب غير المشروط.'),
        EduOption(text: '\'إنت محبوب لما تكون كويس\'', isCorrect: false, rationale: '❌ الحب المشروط بيخلق قلق.'),
        EduOption(text: '\'إنت بتبالغ\'', isCorrect: false, rationale: '❌ إلغاء المشاعر.'),
        EduOption(text: '\'كل الناس بتحبك، إنت مش شايف\'', isCorrect: false, rationale: '❌ التصحيح بدون إصغاء.'),
      ],
    ),
    EduQuestion(
      id: 'q_16',
      question: 'طفلك عنده anxiety قبل الامتحان. إزاي تساعده؟',
      emoji: '😰',
      category: 'القلق',
      context: 'القلق الامتحاني شائع.',
      options: [
        EduOption(text: '\'خلينا نتنفس مع بعض ونذاكر خطوة بخطوة\'', isCorrect: true, rationale: '✅ التنظيم والتنفس بيقللوا القلق.'),
        EduOption(text: '\'إنت لازم تجيب درجة عالية\'', isCorrect: false, rationale: '❌ الضغط بيزود القلق.'),
        EduOption(text: '\'الامتحان مش مهم\'', isCorrect: false, rationale: '❌ التقليل مش حل.'),
        EduOption(text: '\'لو خفت هتعاقب\'', isCorrect: false, rationale: '❌ التهديد بيزود القلق.'),
      ],
    ),
    EduQuestion(
      id: 'q_17',
      question: 'صاحب طفلك بيتكبر عليه دايماً. إزاي تساعد طفلك؟',
      emoji: '😤',
      category: 'العلاقات',
      context: 'العلاقات غير المتكافئة بتأثر النفسية.',
      options: [
        EduOption(text: '\'ممكن تقوله: أنا مش بقبل الكلام ده. لو متوقفتش هبعد\'', isCorrect: true, rationale: '✅ وضع حدود واضحة.'),
        EduOption(text: '\'إسكت له عشان يفضل صاحبك\'', isCorrect: false, rationale: '❌ القبول بالإهانة غلط.'),
        EduOption(text: '\'إنت فعلاً أقل منه\'', isCorrect: false, rationale: '❌ تجريح.'),
        EduOption(text: '\'هاتلي منه\'', isCorrect: false, rationale: '❌ الرد بالعنف.'),
      ],
    ),
    EduQuestion(
      id: 'q_18',
      question: 'طفلك بيخاف ينام لوحده. إيه ردّك المطمئن؟',
      emoji: '🌙',
      category: 'الخوف',
      context: 'الخوف من الظلام طبيعي.',
      options: [
        EduOption(text: '\'أنا قريب، خلينا نشغل إضاءة خافتة ونقرأ حاجة هادية\'', isCorrect: true, rationale: '✅ التهدئة والبيئة الآمنة.'),
        EduOption(text: '\'إنت كبير، متخافش\'', isCorrect: false, rationale: '❌ تقليل الخوف مش حل.'),
        EduOption(text: '\'هنام معاك كل يوم\'', isCorrect: false, rationale: '❌ التعود المستمر بيخلي الطفل معتمد.'),
        EduOption(text: '\'الظلام مفيش فيه حاجة\'', isCorrect: false, rationale: '❌ المنطق ما بيشيلش الخوف.'),
      ],
    ),
    EduQuestion(
      id: 'q_19',
      question: 'طفلك تعرض لموقف محرج قدام صحابه. إزاي تساعده يرجع ثقته؟',
      emoji: '😳',
      category: 'الإحراج',
      context: 'الإحراج الاجتماعي يحتاج إعادة تأطير.',
      options: [
        EduOption(text: '\'كلنا بنتعرض لمواقف زي دي، ومش هتتذكر بعد كام يوم\'', isCorrect: true, rationale: '✅ إعادة الإطار وتقليل الكارثية.'),
        EduOption(text: '\'إنت عملت فضيحة\'', isCorrect: false, rationale: '❌ تضخيم الموقف.'),
        EduOption(text: '\'متروحش المدرسة كام يوم\'', isCorrect: false, rationale: '❌ التجنب بيقوي الخجل.'),
        EduOption(text: '\'قول لصحابك إنهم غلطانين\'', isCorrect: false, rationale: '❌ الاتهام غلط.'),
      ],
    ),
        ];
      case 5:
        return const [
    EduQuestion(
      id: 'q_20',
      question: 'طفلك بيحسد صاحبه على لعبة جديدة. إزاي تتعاملي مع الغيرة؟',
      emoji: '🎮',
      category: 'الغيرة',
      context: 'الغيرة فرصة للتعلم.',
      options: [
        EduOption(text: '\'أنا فاهم إنك عايزها. خلينا نحطها هدف ونادخر\'', isCorrect: true, rationale: '✅ تحويل الغيرة لطموح.'),
        EduOption(text: '\'ما تكونش حسود\'', isCorrect: false, rationale: '❌ التلصيق بيعلم الطفل إنه \'سيئ\'.'),
        EduOption(text: 'خيار غير متاح', isCorrect: false, rationale: '❌ خيار غير صحيح.'),
        EduOption(text: 'خيار غير متاح', isCorrect: false, rationale: '❌ خيار غير صحيح.'),
      ],
    ),
    EduQuestion(
      id: 'q_21',
      question: 'طفلك بيتنرفز بسرعة من أخوه الصغير. إزاي تساعده يضبط غضبه؟',
      emoji: '🌋',
      category: 'الغضب',
      context: 'إدارة الغضب مهارة.',
      options: [
        EduOption(text: '\'خلينا نتنفس: شهيق من الأنف وزفير من البؤ. بعدين نتكلم\'', isCorrect: true, rationale: '✅ التنفس بيساعد الضبط.'),
        EduOption(text: '\'إنت كبير، متزعقش\'', isCorrect: false, rationale: '❌ تقليل المشاعر.'),
        EduOption(text: '\'هعاقبك لو زعقت تاني\'', isCorrect: false, rationale: '❌ العقاب ما بيعلّمش تنظيم.'),
        EduOption(text: '\'سيبه ينرفزك عادي\'', isCorrect: false, rationale: '❌ ده بيسمح بالغضب.'),
      ],
    ),
    EduQuestion(
      id: 'q_22',
      question: 'طفلك عايز يشارك في مسرحية المدرسة بس خايف. إيه دعمه؟',
      emoji: '🎤',
      category: 'الشجاعة',
      context: 'الخوف من الأداء العلني.',
      options: [
        EduOption(text: '\'الخوف طبيعي، وكلنا بنخاف. خلينا نتدرب مع بعض\'', isCorrect: true, rationale: '✅ تطبيع الخوف والتدريب.'),
        EduOption(text: '\'إنت لازم تشارك عشان تبقى شجاع\'', isCorrect: false, rationale: '❌ الضغط.'),
        EduOption(text: '\'متشاركش لو خايف\'', isCorrect: false, rationale: '❌ التجنب بيخلي الخوف يكبر.'),
        EduOption(text: '\'هيتريقوا عليك لو رفضت\'', isCorrect: false, rationale: '❌ التخويف.'),
      ],
    ),
    EduQuestion(
      id: 'q_23',
      question: 'صاحب طفلك بيستعير حاجاته وما يرجعهاش. إيه توجيهك؟',
      emoji: '🔄',
      category: 'الحدود',
      context: 'تعليم حدود العطاء.',
      options: [
        EduOption(text: '\'ممكن تقوله: أنا محتاجها تاني، يرجع لي بكرة\'', isCorrect: true, rationale: '✅ طلب واضح.'),
        EduOption(text: '\'إسكت، ده صاحبك\'', isCorrect: false, rationale: '❌ الصداقة مش تعني سلب الحقوق.'),
        EduOption(text: '\'هاتها بالعافية\'', isCorrect: false, rationale: '❌ العنف.'),
        EduOption(text: '\'خلاص ما تدهاش له تاني\'', isCorrect: false, rationale: '❌ ده حل جزئي، التواصل أولاً.'),
      ],
    ),
    EduQuestion(
      id: 'q_24',
      question: 'طفلك بيتعرض للتجاهل من مجموعة في المدرسة. إزاي تساعده؟',
      emoji: '👥',
      category: 'التجاهل',
      context: 'التجاهل صورة من التنمر.',
      options: [
        EduOption(text: '\'أنا فاهم إن ده مؤلم. خلينا نوسّع دائرة صحابك\'', isCorrect: true, rationale: '✅ التعاطف وتنويع العلاقات.'),
        EduOption(text: '\'إسعي عشان يرجعوا يحبوك\'', isCorrect: false, rationale: '❌ chasing القبول غلط.'),
        EduOption(text: '\'إنت مش محتاجهم\'', isCorrect: false, rationale: '❌ تقليل الحاجة للانتماء.'),
        EduOption(text: '\'هروح أتكلم معاهم\'', isCorrect: false, rationale: '❌ التدخل المباشر ممكن يزود المشكلة.'),
      ],
    ),
        ];
      case 6:
        return const [
    EduQuestion(
      id: 'q_25',
      question: 'طفلك بيتعلّق بيك أوي وبيخاف يروح المدرسة. إيه تصرفك؟',
      emoji: '👋',
      category: 'الانفصال',
      context: 'القلق الانفصالي.',
      options: [
        EduOption(text: '\'أنا هاجي أخدك بعد المدرسة. دلوقتي أنا بجيبلك مناسب\'', isCorrect: true, rationale: '✅ الضمان والوداع القصير.'),
        EduOption(text: '\'إسكت وروح بسرعة\'', isCorrect: false, rationale: '❌ ده بيزود القلق.'),
        EduOption(text: '\'أنا هفضل معاك النهاردة\'', isCorrect: false, rationale: '❌ التعود بيخلي الانفصال أصعب.'),
        EduOption(text: '\'إنت كبير، متبكيش\'', isCorrect: false, rationale: '❌ تقليل المشاعر.'),
      ],
    ),
    EduQuestion(
      id: 'q_26',
      question: 'طفلك قالك إن صاحبه بيضغط عليه يشرب سجاير. إيه تصرفك؟',
      emoji: '🚬',
      category: 'الضغط',
      context: 'ضغط الأقران على مواد ضارة.',
      options: [
        EduOption(text: '\'أنا فخور إنك قولتلي. ممكن تقول: لا، أنا مش بحب الكلام ده\'', isCorrect: true, rationale: '✅ الثناء + تعليم الرفض.'),
        EduOption(text: '\'إبعد عنه نهائياً\'', isCorrect: false, rationale: '❌ المنع التام مش دايماً حل.'),
        EduOption(text: '\'جرب مرة بس عشان ما يتريقوش\'', isCorrect: false, rationale: '❌ ده خطير.'),
        EduOption(text: '\'هتضربني لو جربت\'', isCorrect: false, rationale: '❌ التهديد مش تربية.'),
      ],
    ),
    EduQuestion(
      id: 'q_27',
      question: 'طفلك عنده رد فعل عنيف لما بتقولي \'لا\'. إزاي تحطّي حدود؟',
      emoji: '🛑',
      category: 'الحدود',
      context: 'الرفض محتاج إطار هادئ.',
      options: [
        EduOption(text: '\'أنا فاهم إنك زعلان، بس الرد ده مش مقبول. نتكلم لما تهدى\'', isCorrect: true, rationale: '✅ حدود + تعاطف.'),
        EduOption(text: '\'إنت كده هتتعاقب\'', isCorrect: false, rationale: '❌ التهديد في لحظة الغضب بيزود الصراع.'),
        EduOption(text: '\'طيب خلاص يا سيدي\'', isCorrect: false, rationale: '❌ الاستسلام بيعلم الابتزاز.'),
        EduOption(text: '\'إسكت ولا كلمة\'', isCorrect: false, rationale: '❌ كبت المشاعر.'),
      ],
    ),
    EduQuestion(
      id: 'q_28',
      question: 'طفلك بيتكاسل عن تنظيف أوضته. إزاي تحفزيه؟',
      emoji: '🧹',
      category: 'المسؤولية',
      context: 'المسؤولية المنزلية.',
      options: [
        EduOption(text: '\'خلينا نعملها مع بعض 10 دقايق وبعدين نلعب\'', isCorrect: true, rationale: '✅ المشاركة والمكافأة.'),
        EduOption(text: '\'إنت بتعيش هنا لازم تنظف\'', isCorrect: false, rationale: '❌ التوبيخ بيقلل الحماس.'),
        EduOption(text: '\'هعملها أنا\'', isCorrect: false, rationale: '❌ الاعتمادية.'),
        EduOption(text: '\'هتعاقب\'', isCorrect: false, rationale: '❌ العقاب بدون تشجيع.'),
      ],
    ),
    EduQuestion(
      id: 'q_29',
      question: 'طفلك بيحس إنه \'غبي\' لأنه اتأخر في شوية. إيه ردّك؟',
      emoji: '🐢',
      category: 'الثقة',
      context: 'الثقة بالقدرات.',
      options: [
        EduOption(text: '\'كل واحد بيتعلم بسرعته. إنت شاطر في حاجات تانية وده هيتحسن بالتدريب\'', isCorrect: true, rationale: '✅ إعادة الإطار والتشجيع.'),
        EduOption(text: '\'أيوا، لازم تتعب أكتر\'', isCorrect: false, rationale: '❌ ده بيزود الشعور بالنقص.'),
        EduOption(text: '\'إنت فعلاً بطيء\'', isCorrect: false, rationale: '❌ التلصيق.'),
        EduOption(text: '\'متفكرش في الموضوع\'', isCorrect: false, rationale: '❌ تجاهل المشكلة.'),
      ],
    ),
        ];
      case 7:
        return const [
    EduQuestion(
      id: 'q_30',
      question: 'طفلك بيشعر بالذنب لأنه كسر حاجة. إيه تصرفك؟',
      emoji: '🥺',
      category: 'الذنب',
      context: 'الذنب المفرط محتاج إعادة تأطير.',
      options: [
        EduOption(text: '\'حاجات بتحصل. المهم نعتذر ونساعد في التصليح\'', isCorrect: true, rationale: '✅ التركيز على الحل.'),
        EduOption(text: '\'إنت دايماً بتكسر حاجات\'', isCorrect: false, rationale: '❌ التعميم.'),
        EduOption(text: '\'هتتعاقب\'', isCorrect: false, rationale: '❌ العقاب بدون تعليم.'),
        EduOption(text: '\'إنسى الموضوع\'', isCorrect: false, rationale: '❌ المسؤولية مهمة.'),
      ],
    ),
    EduQuestion(
      id: 'q_31',
      question: 'طفلك عنده عادة قول \'مش قادر\'. إزاي تشجعه؟',
      emoji: '💪',
      category: 'التحفيز',
      context: 'اللغة الداخلية بتأثر الأداء.',
      options: [
        EduOption(text: '\'خلينا نقول: هحاول. ولو محتاج مساعدة أنا هنا\'', isCorrect: true, rationale: '✅ إعادة صياغة اللغة.'),
        EduOption(text: '\'إنت قادر، متقولش كده\'', isCorrect: false, rationale: '❌ التصحيح المباشر مش حل.'),
        EduOption(text: '\'طيب سيبها\'', isCorrect: false, rationale: '❌ التساهل.'),
        EduOption(text: '\'هتعاقب لو ما حاولتش\'', isCorrect: false, rationale: '❌ التهديد.'),
      ],
    ),
    EduQuestion(
      id: 'q_32',
      question: 'طفلك عايز يبقى \'شعبي\' في المدرسة. إيه توجيهك؟',
      emoji: '⭐',
      category: 'القبول',
      context: 'القبول والشهرة.',
      options: [
        EduOption(text: '\'الناس الحقيقية بتحبّك زي ما إنت. متغيّرش قيمك عشان حد\'', isCorrect: true, rationale: '✅ الهوية الصحيحة.'),
        EduOption(text: '\'إعمل اللي بيعملوه\'', isCorrect: false, rationale: '❌ التقليد الأعمى.'),
        EduOption(text: '\'أهم حاجة تبقى محبوب\'', isCorrect: false, rationale: '❌ القبول بأي ثمن.'),
        EduOption(text: '\'الشعبية مش مهمة\'', isCorrect: false, rationale: '❌ تقليل الحاجة.'),
      ],
    ),
    EduQuestion(
      id: 'q_33',
      question: 'طفلك بيتضايق لما بتقارنه بأخوه. إزاي تتوقفي عن المقارنة؟',
      emoji: '⚖️',
      category: 'المقارنة',
      context: 'المقارنة بين الأشقاء بتؤذي.',
      options: [
        EduOption(text: '\'كل واحد فيكم مختلف ومواهبه مختلفة\'', isCorrect: true, rationale: '✅ الاحتفال بالفردية.'),
        EduOption(text: '\'أخوك فعلاً أحسن\'', isCorrect: false, rationale: '❌ ده يؤذي.'),
        EduOption(text: '\'إنت حساس أوي\'', isCorrect: false, rationale: '❌ تقليل المشاعر.'),
        EduOption(text: '\'هبطل أقارن\'', isCorrect: false, rationale: '❌ الوعد لوحده مش كفاية، محتاج تطبيق.'),
      ],
    ),
    EduQuestion(
      id: 'q_34',
      question: 'طفلك بيتردد يعبر عن رأيه في العيلة. إزاي تشجعه؟',
      emoji: '💬',
      category: 'التعبير',
      context: 'التعبير عن الرأي مهارة.',
      options: [
        EduOption(text: '\'رأيك مهم، قوله بلطف وأنا هسمع\'', isCorrect: true, rationale: '✅ خلق بيئة آمنة للتعبير.'),
        EduOption(text: '\'إنت صغير على الكلام\'', isCorrect: false, rationale: '❌ كبت الرأي.'),
        EduOption(text: '\'قول اللي أنا عايزه\'', isCorrect: false, rationale: '❌ ده مش تعبير حر.'),
        EduOption(text: '\'متكلمش لو هتزعل حد\'', isCorrect: false, rationale: '❌ كبت التعبير.'),
      ],
    ),
        ];
      case 8:
        return const [
    EduQuestion(
      id: 'q_35',
      question: 'طفلك بيتأثر بالإعلانات وعايز كل اللي يشوفه. إزاي تساعده؟',
      emoji: '📺',
      category: 'الاستهلاك',
      context: 'التسويق والرغبة.',
      options: [
        EduOption(text: '\'نقول: محتاج ولا عايز؟ وليه؟\'', isCorrect: true, rationale: '✅ التفكير النقدي.'),
        EduOption(text: '\'هاجبلك كل حاجة\'', isCorrect: false, rationale: '❌ الإسراف.'),
        EduOption(text: '\'إعلانات كلها كذابة\'', isCorrect: false, rationale: '❌ التعميم.'),
        EduOption(text: '\'متشوفش تلفزيون\'', isCorrect: false, rationale: '❌ المنع التام.'),
      ],
    ),
    EduQuestion(
      id: 'q_36',
      question: 'طفلك بيتعرض لانتقاد كتير من المعلمة. إزاي تسنده؟',
      emoji: '👩‍🏫',
      category: 'الانتقاد',
      context: 'الانتقاد المستمر بيؤثر على الثقة.',
      options: [
        EduOption(text: '\'نفصل بين سلوكك وقيمتك. تعالى نشوف نحسّن إيه\'', isCorrect: true, rationale: '✅ دعم الهوية + تحسين.'),
        EduOption(text: '\'المعلمة غلطانة\'', isCorrect: false, rationale: '❌ التحامل على المعلمة مش حل.'),
        EduOption(text: '\'إنت لازم تتغير عشان ترضيها\'', isCorrect: false, rationale: '❌ الرضا بأي ثمن.'),
        EduOption(text: '\'خلاص متروحش المدرسة\'', isCorrect: false, rationale: '❌ الهروب.'),
      ],
    ),
    EduQuestion(
      id: 'q_37',
      question: 'طفلك عنده مشاعر مختلطة عن فراق جدته. إزاي تساعده؟',
      emoji: '🕯️',
      category: 'الفقدان',
      context: 'الحزن والفقدان.',
      options: [
        EduOption(text: '\'الحزن طبيعي. احكيلي عن ذكرياتك معاها\'', isCorrect: true, rationale: '✅ التطبيع والتعبير.'),
        EduOption(text: '\'إنت لازم تكون قوي\'', isCorrect: false, rationale: '❌ كبت الحزن.'),
        EduOption(text: '\'متفكرش في الموضوع\'', isCorrect: false, rationale: '❌ تجاهل المشاعر.'),
        EduOption(text: '\'هنشتري لك حاجة تنسيك\'', isCorrect: false, rationale: '❌ الهروب.'),
      ],
    ),
    EduQuestion(
      id: 'q_38',
      question: 'طفلك بيتصرف بطريقة \'مش من نفسه\'. إيه تعملي؟',
      emoji: '🌊',
      category: 'التغيرات',
      context: 'التغيرات المفاجئة محتاجة انتباه.',
      options: [
        EduOption(text: '\'لاحظت إنك متغير. عايز تتكلم؟\'', isCorrect: true, rationale: '✅ الاهتمام والفتح.'),
        EduOption(text: '\'إنت مش متغير\'', isCorrect: false, rationale: '❌ إنكار ملاحظة الطفل.'),
        EduOption(text: '\'هتتعاقب لو كملت كده\'', isCorrect: false, rationale: '❌ العقاب قبل الفهم.'),
        EduOption(text: '\'سيبك من اللي حواليك\'', isCorrect: false, rationale: '❌ التبسيط المفرط.'),
      ],
    ),
    EduQuestion(
      id: 'q_39',
      question: 'طفلك عنده أهداف كبيرة بس بييأس بسرعة. إزاي تدعمه؟',
      emoji: '🎯',
      category: 'الإصرار',
      context: 'مقاومة اليأس.',
      options: [
        EduOption(text: '\'نقسّم الهدف لخطوات صغيرة ونحتفل بكل خطوة\'', isCorrect: true, rationale: '✅ التقسيم والاحتفال.'),
        EduOption(text: '\'إنت طموحك أكبر منك\'', isCorrect: false, rationale: '❌ التقليل.'),
        EduOption(text: '\'استسلم لو صعب\'', isCorrect: false, rationale: '❌ تشجيع الاستسلام.'),
        EduOption(text: '\'هدفك مش مهم\'', isCorrect: false, rationale: '❌ تقليل الأحلام.'),
      ],
    ),
        ];
      case 9:
        return const [
    EduQuestion(
      id: 'q_40',
      question: 'طفلك بيحب يساعد الناس. إزاي تشجعه؟',
      emoji: '🌟',
      category: 'الإحسان',
      context: 'تعزيز الإحسان.',
      options: [
        EduOption(text: '\'أنا فخور بيك، ساعدة بتفرق\'', isCorrect: true, rationale: '✅ التعزيز الإيجابي.'),
        EduOption(text: '\'متساعدش كل الناس\'', isCorrect: false, rationale: '❌ تقليل الإحسان.'),
        EduOption(text: '\'إنت هتتعب\'', isCorrect: false, rationale: '❌ الترغيب في الأنانية.'),
        EduOption(text: '\'ساعد بس اللي يساعدوك\'', isCorrect: false, rationale: '❌ الإحسان مش مقايضة.'),
      ],
    ),
    EduQuestion(
      id: 'q_41',
      question: 'إزاي تخلّي البيت مكان آمن عاطفياً لطفلك؟',
      emoji: '🏠',
      category: 'البيئة العاطفية',
      context: 'البيئة العاطفية بتأثر على كل شيء.',
      options: [
        EduOption(text: '\'نسمع، نحترم مشاعره، ونكون قدوة في التعامل مع المشاعر\'', isCorrect: true, rationale: '✅ البيئة الآمنة.'),
        EduOption(text: '\'نمنع أي زعل\'', isCorrect: false, rationale: '❌ المشاعر السلبية طبيعية.'),
        EduOption(text: '\'نقوله دايماً إنه كويس\'', isCorrect: false, rationale: '❌ الثناء المستمر مش صادق.'),
        EduOption(text: '\'نخبّي مشاكلنا عنه\'', isCorrect: false, rationale: '❌ الطفل يحس بالتوتر.'),
      ],
    ),
    EduQuestion(
      id: 'q_42',
      question: 'طفلك بيتعلم إزاي يتعامل مع مشاعره. إيه أهم درس؟',
      emoji: '🧠',
      category: 'الذكاء العاطفي',
      context: 'الذكاء العاطفي.',
      options: [
        EduOption(text: '\'كل مشاعرك مقبولة، والتصرفات ليها حدود\'', isCorrect: true, rationale: '✅ الفصل بين المشاعر والتصرفات.'),
        EduOption(text: '\'مشاعرك الغضب غلط\'', isCorrect: false, rationale: '❌ إدانة المشاعر.'),
        EduOption(text: '\'تصرف زي ما تحس\'', isCorrect: false, rationale: '❌ التصرفات محتاجة تنظيم.'),
        EduOption(text: '\'متشعرش كتير\'', isCorrect: false, rationale: '❌ كبت المشاعر.'),
      ],
    ),
    EduQuestion(
      id: 'q_43',
      question: 'طفلك بيكبر وعايز استقلالية أكتر. إزاي توازني؟',
      emoji: '🕊️',
      category: 'الاستقلالية',
      context: 'الاستقلالية مرحلة طبيعية.',
      options: [
        EduOption(text: '\'ندّيله مسؤوليات صغيرة ونثق فيه تدريجياً\'', isCorrect: true, rationale: '✅ التدرج والثقة.'),
        EduOption(text: '\'إنت لسه صغير\'', isCorrect: false, rationale: '❌ تقليل رغبة النمو.'),
        EduOption(text: '\'خلاص اعمل اللي تحبه\'', isCorrect: false, rationale: '❌ غياب الحدود.'),
        EduOption(text: '\'هتحتاجني طول عمرك\'', isCorrect: false, rationale: '❌ الاعتمادية.'),
      ],
    ),
    EduQuestion(
      id: 'q_44',
      question: 'طفلك سألك: \'إزاي أبقى سعيد؟\'',
      emoji: '😊',
      category: 'السعادة',
      context: 'السعادة مهارة.',
      options: [
        EduOption(text: '\'بالشكر، العلاقات الحلوة، والمساعدة\'', isCorrect: true, rationale: '✅ السعادة من العلاقات والمعنى.'),
        EduOption(text: '\'بالحصول على كل اللي عايزه\'', isCorrect: false, rationale: '❌ السعادة مش استهلاك.'),
        EduOption(text: '\'بعدم الشعور بزعل\'', isCorrect: false, rationale: '❌ الزعل جزء من الحياة.'),
        EduOption(text: '\'بالنجاح بس\'', isCorrect: false, rationale: '❌ السعادة مش حلقة نجاح.'),
      ],
    ),
        ];
      case 10:
        return const [
    EduQuestion(
      id: 'q_45',
      question: 'إيه أهم حاجة في علاقتك بطفلك؟',
      emoji: '💖',
      category: 'العلاقة',
      context: 'العلاقة هي الأساس.',
      options: [
        EduOption(text: '\'إنه يحس إني بسمعه وبقبله مهما كان\'', isCorrect: true, rationale: '✅ القبول غير المشروط.'),
        EduOption(text: '\'إنه ينفذ تعليماتي\'', isCorrect: false, rationale: '❌ الطاعة مش هدف وحده.'),
        EduOption(text: '\'إنه يبقى ناجح\'', isCorrect: false, rationale: '❌ النجاح مش مقياس علاقة.'),
        EduOption(text: '\'إنه ما يغلطش\'', isCorrect: false, rationale: '❌ الأخطاء طبيعية.'),
      ],
    ),
    EduQuestion(
      id: 'q_46',
      question: 'سؤال إضافي عن التعامل مع المشاعر.',
      emoji: '💬',
      category: 'المشاعر',
      context: 'التعاطف والحوار بيساعدوا.',
      options: [
        EduOption(text: 'نحكي مع الطفل بهدوء', isCorrect: true, rationale: '✅ الحوار أفضل.'),
        EduOption(text: 'نزعق', isCorrect: false, rationale: '❌ العنف بيبعد.'),
        EduOption(text: 'نهمل', isCorrect: false, rationale: '❌ الإهمال بيزود المشكلة.'),
        EduOption(text: 'نعاقب', isCorrect: false, rationale: '❌ العقاب بدون فهم غلط.'),
      ],
    ),
    EduQuestion(
      id: 'q_47',
      question: 'سؤال إضافي عن التعامل مع المشاعر.',
      emoji: '💬',
      category: 'المشاعر',
      context: 'التعاطف والحوار بيساعدوا.',
      options: [
        EduOption(text: 'نحكي مع الطفل بهدوء', isCorrect: true, rationale: '✅ الحوار أفضل.'),
        EduOption(text: 'نزعق', isCorrect: false, rationale: '❌ العنف بيبعد.'),
        EduOption(text: 'نهمل', isCorrect: false, rationale: '❌ الإهمال بيزود المشكلة.'),
        EduOption(text: 'نعاقب', isCorrect: false, rationale: '❌ العقاب بدون فهم غلط.'),
      ],
    ),
    EduQuestion(
      id: 'q_48',
      question: 'سؤال إضافي عن التعامل مع المشاعر.',
      emoji: '💬',
      category: 'المشاعر',
      context: 'التعاطف والحوار بيساعدوا.',
      options: [
        EduOption(text: 'نحكي مع الطفل بهدوء', isCorrect: true, rationale: '✅ الحوار أفضل.'),
        EduOption(text: 'نزعق', isCorrect: false, rationale: '❌ العنف بيبعد.'),
        EduOption(text: 'نهمل', isCorrect: false, rationale: '❌ الإهمال بيزود المشكلة.'),
        EduOption(text: 'نعاقب', isCorrect: false, rationale: '❌ العقاب بدون فهم غلط.'),
      ],
    ),
    EduQuestion(
      id: 'q_49',
      question: 'سؤال إضافي عن التعامل مع المشاعر.',
      emoji: '💬',
      category: 'المشاعر',
      context: 'التعاطف والحوار بيساعدوا.',
      options: [
        EduOption(text: 'نحكي مع الطفل بهدوء', isCorrect: true, rationale: '✅ الحوار أفضل.'),
        EduOption(text: 'نزعق', isCorrect: false, rationale: '❌ العنف بيبعد.'),
        EduOption(text: 'نهمل', isCorrect: false, rationale: '❌ الإهمال بيزود المشكلة.'),
        EduOption(text: 'نعاقب', isCorrect: false, rationale: '❌ العقاب بدون فهم غلط.'),
      ],
    ),
        ];
      default:
        return _buildQuestions(1);
    }
  }
}
