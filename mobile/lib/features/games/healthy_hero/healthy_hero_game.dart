/// Redesigned Healthy Hero educational mini-game.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Healthy Hero game.
class HealthyHeroGame extends EduGameShell {
  const HealthyHeroGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'healthy_hero',
            name: 'البطل الصحي',
            heroEmoji: '🩺',
            description: 'اختيارات ذكية للأكل والنوم والصحة اليومية',
            backgroundColor: Color(0xFF0F3D4A),
            surfaceColor: Color(0xFF164E63),
            accentColor: Color(0xFF22C55E),
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
      question: 'طفلك رفض ياكل الخضار من الصبح. إيه ردّ فعلك الأفضل؟',
      emoji: '🥦',
      category: 'التغذية',
      context: 'التغذية السليمة ضرورية للنمو.',
      options: [
        EduOption(text: 'بقدّمه بطريقة ممتعة أو أخلطه مع أكلة بيحبها', isCorrect: true, rationale: '✅ المرونة والإبداع بتساعد الطفل يتقبل الأكل الصحي.'),
        EduOption(text: 'بزعقله عشان ياكل', isCorrect: false, rationale: '❌ الضغط بيبعد الطفل عن الأكل الصحي.'),
        EduOption(text: 'بسيبه ما ياكلش خالص', isCorrect: false, rationale: '❌ بيسيبه بدون عناصر غذائية مهمة.'),
        EduOption(text: 'بديله حلويات بدل الخضار', isCorrect: false, rationale: '❌ الحلويات مش بديل صحي.'),
      ],
    ),
    EduQuestion(
      id: 'q_1',
      question: 'إيه علامات الجفاف عند الأطفال الصغار؟',
      emoji: '💧',
      category: 'الماء',
      context: 'الجفاف خطر على الأطفال.',
      options: [
        EduOption(text: 'قليل البكاء بدون دموع، فم جاف، وقلة التبول', isCorrect: true, rationale: '✅ دي علامات كلاسيكية للجفاف.'),
        EduOption(text: 'بكاء كتير ومزاج سيئ', isCorrect: false, rationale: '❌ البكاء بكثرة مش علامة جفاف.'),
        EduOption(text: 'جوع شديد ونوم كتير', isCorrect: false, rationale: '❌ دي مش علامات جفاف رئيسية.'),
        EduOption(text: 'حرارة عالية بس', isCorrect: false, rationale: '❌ الجفاف ممكن يحصل من غير حرارة.'),
      ],
    ),
    EduQuestion(
      id: 'q_2',
      question: 'طفلك عنده حمى 38.5 درجة. إيه أول خطوة؟',
      emoji: '🌡️',
      category: 'الحمى',
      context: 'الحمى رد فعل طبيعي بس محتاجة رعاية.',
      options: [
        EduOption(text: 'بعطيه ماء، أراحة، وأراقب درجة الحرارة', isCorrect: true, rationale: '✅ الترطيب والراحة أساسية.'),
        EduOption(text: 'بغطيه ببطانيات كتير', isCorrect: false, rationale: '❌ الغطاء الزيادة بيرفع الحرارة.'),
        EduOption(text: 'بديله مضاد حيوي فوراً', isCorrect: false, rationale: '❌ المضاد الحيوي يحتاج تشخيص طبيب.'),
        EduOption(text: 'بسيبه لحد ما الحمى تزيد', isCorrect: false, rationale: '❌ الانتظار ممكن يأخر العلاج.'),
      ],
    ),
    EduQuestion(
      id: 'q_3',
      question: 'إيه أفضل وضعية نوم للأطفال الرضع؟',
      emoji: '🛏️',
      category: 'النوم',
      context: 'وضعية النوم بتأثر على سلامة الطفل.',
      options: [
        EduOption(text: 'على ظهره على سطح ممتد وصلب', isCorrect: true, rationale: '✅ وضعية الظهر بتقلل متلازمة الموت المفاجئ.'),
        EduOption(text: 'على بطنه عشان ينام أعمق', isCorrect: false, rationale: '❌ البطن بتزود خطر الاختناق.'),
        EduOption(text: 'على جنبه بمخدة طرية', isCorrect: false, rationale: '❌ المخدات طرية خطرة على الرضع.'),
        EduOption(text: 'في سريره مع بطانية ثقيلة', isCorrect: false, rationale: '❌ البطانيات الثقيلة خطرة.'),
      ],
    ),
    EduQuestion(
      id: 'q_4',
      question: 'طفلك عض ظفره بقوة واتقطع. إيه اللي تعمليه؟',
      emoji: '🩹',
      category: 'الإسعافات',
      context: 'الجروح الصغيرة محتاجة تنظيف.',
      options: [
        EduOption(text: 'بتغسليه بماء نظيف وتضعي مطهر طفيف وضمادة', isCorrect: true, rationale: '✅ التنظيف والحماية بيمنع العدوى.'),
        EduOption(text: 'بتحطي عليه تراب أو سكر', isCorrect: false, rationale: '❌ دي طرق غير صحية وبتسبب عدوى.'),
        EduOption(text: 'بتسيبيه عشان الجو بي dries', isCorrect: false, rationale: '❌ ممكن يتلوث.'),
        EduOption(text: 'بتستخدمي glue', isCorrect: false, rationale: '❌ glue مش مطهر وخطير على الجروح.'),
      ],
    ),
        ];
      case 2:
        return const [
    EduQuestion(
      id: 'q_5',
      question: 'إزاي تحمي طفلك من أشعة الشمس في الصيف؟',
      emoji: '☀️',
      category: 'الوقاية',
      context: 'الأشعة فوق البنفسجية ضارة للبشرة.',
      options: [
        EduOption(text: 'واقي شمس مناسب للأطفال، قبعة، وتجنب أوقات الذروة', isCorrect: true, rationale: '✅ الحماية متعددة أفضل.'),
        EduOption(text: 'بسيبه يلعب عادي عشان ياخد فيتامين د', isCorrect: false, rationale: '❌ التعرض المباشر ممكن يسبب حروق.'),
        EduOption(text: 'بده يلبس ملابس سوداء', isCorrect: false, rationale: '❌ اللون الأسود بيسخن أكتر.'),
        EduOption(text: 'بغطيه بالكامل بطبقة كريم', isCorrect: false, rationale: '❌ الكمية الزيادة مش أفضل.'),
      ],
    ),
    EduQuestion(
      id: 'q_6',
      question: 'طفلك بلع قطعة صغيرة من لعبة. إيه تصرفك السليم؟',
      emoji: '🚫',
      category: 'الطوارئ',
      context: 'الاختناق من أكبر المخاطر.',
      options: [
        EduOption(text: 'لو بيسعل أو يتنفس بصعوبة، باتصل بالإسعاف فوراً', isCorrect: true, rationale: '✅ الاختناق حالة طوارئ.'),
        EduOption(text: 'بده يشرب ماء كتير عشان ينزل', isCorrect: false, rationale: '❌ الماء ممكن يزود الاختناق.'),
        EduOption(text: 'بحاول أطلعها بإصبعي من بعيد', isCorrect: false, rationale: '❌ ممكن أدفعها أعمق.'),
        EduOption(text: 'بسيبه عشان هتنزل لوحدها', isCorrect: false, rationale: '❌ بعض القطع بتسبب انسداد.'),
      ],
    ),
    EduQuestion(
      id: 'q_7',
      question: 'إيه علامات الحساسية الغذائية عند الأطفال؟',
      emoji: '🥜',
      category: 'الحساسية',
      context: 'الحساسية محتاجة رد سريع.',
      options: [
        EduOption(text: 'طفح جلدي، انتفاخ الشفايف، صعوبة تنفس، أو تقيؤ', isCorrect: true, rationale: '✅ دي علامات تحتاج تدخل طبي.'),
        EduOption(text: 'بس عدم رغبة في الأكل', isCorrect: false, rationale: '❌ دي مش علامة حساسية.'),
        EduOption(text: 'بكاء خفيف بعد الأكل', isCorrect: false, rationale: '❌ البكاء ممكن يكون لأي سبب.'),
        EduOption(text: 'كثرة النوم', isCorrect: false, rationale: '❌ النوم مش علامة حساسية.'),
      ],
    ),
    EduQuestion(
      id: 'q_8',
      question: 'كم ساعة نوم محتاجها الطفل في عمر 3-5 سنوات؟',
      emoji: '😴',
      category: 'النوم',
      context: 'النوم الكافي ضروري للنمو والتركيز.',
      options: [
        EduOption(text: '10-13 ساعة يومياً', isCorrect: true, rationale: '✅ التوصيات بتقول 10-13 ساعة للفئة العمرية دي.'),
        EduOption(text: '6-8 ساعات كفاية', isCorrect: false, rationale: '❌ ده قليل جداً وبيأثر على النمو.'),
        EduOption(text: '14-16 ساعة', isCorrect: false, rationale: '❌ ده مناسب أكتر للرضع.'),
        EduOption(text: 'ما يهمش عدد الساعات', isCorrect: false, rationale: '❌ النوم الكافي مهم جداً.'),
      ],
    ),
    EduQuestion(
      id: 'q_9',
      question: 'إزاي تساعدي طفلك يغسل أسنانه بطريقة صحيحة؟',
      emoji: '🦷',
      category: 'النظافة',
      context: 'نظافة الأسنان بتمنع التسوس.',
      options: [
        EduOption(text: 'بعمليه قدوة، أستخدمي معجون مناسب، وأفرشاه ناعمة', isCorrect: true, rationale: '✅ القدوة والأدوات المناسبة مهمة.'),
        EduOption(text: 'بغسلهاله بنفسي كل مرة', isCorrect: false, rationale: '❌ الطفل محتاج يتعلم بنفسه.'),
        EduOption(text: 'بستخدمي معجون للكبار', isCorrect: false, rationale: '❌ معجون الكبار ممكن يكون قوي على طفل.'),
        EduOption(text: 'مرة واحدة في اليوم كفاية', isCorrect: false, rationale: '❌ التوصية مرتين يومياً.'),
      ],
    ),
        ];
      case 3:
        return const [
    EduQuestion(
      id: 'q_10',
      question: 'طفلك تعب فجأة في المدرسة. إيه أول حاجة تسأليها المعلمة؟',
      emoji: '🏫',
      category: 'المدرسة',
      context: 'التواصل السليم بيساعد في التقييم.',
      options: [
        EduOption(text: 'ما هي الأعراض ومتى بدأت؟ هل فيه حمى أو تقيؤ؟', isCorrect: true, rationale: '✅ التفاصيل بتساعد في قرار العودة للبيت.'),
        EduOption(text: 'هل زعلان من حد؟', isCorrect: false, rationale: '❌ ممكن، بس الأعراض الجسدية أولوية.'),
        EduOption(text: 'هل أكل كتير؟', isCorrect: false, rationale: '❌ ممكن بس مش أول سؤال.'),
        EduOption(text: 'خلاصه يرجع البيت على طول', isCorrect: false, rationale: '❌ لازم نفهم السبب الأول.'),
      ],
    ),
    EduQuestion(
      id: 'q_11',
      question: 'إيه اللي تعمليه لو طفلك وقع من على درجة وجرح ركبته؟',
      emoji: '🦵',
      category: 'الإسعافات',
      context: 'السقوط شائع والتقييم مهم.',
      options: [
        EduOption(text: 'بتهديه، بتفحصي الجرح والتورم، وتنظفي الجرح', isCorrect: true, rationale: '✅ الهدوء والفحص أول خطوة.'),
        EduOption(text: 'بتحطله حرام مباشرة عشان يسخن', isCorrect: false, rationale: '❌ الحرارة في البداية ممكن تزود التورم.'),
        EduOption(text: 'بتجبريه على المشي فوراً', isCorrect: false, rationale: '❌ ممكن يكون فيه كسر.'),
        EduOption(text: 'بتدهله مسكن قوي فوراً', isCorrect: false, rationale: '❌ المسكنات الأطفال لازم تكون آمنة.'),
      ],
    ),
    EduQuestion(
      id: 'q_12',
      question: 'إزاي تختاري واقي الشمس المناسب للأطفال؟',
      emoji: '🧴',
      category: 'الوقاية',
      context: 'واقي الشمس مهم بس لازم مناسب.',
      options: [
        EduOption(text: 'SPF 30 على الأقل، مقاوم للماء، ومناسب للأطفال', isCorrect: true, rationale: '✅ المواصفات دي مهمة.'),
        EduOption(text: 'أي واقي شمس رخيص', isCorrect: false, rationale: '❌ الأطفال بشرتهم حساسة.'),
        EduOption(text: 'SPF 5-10 كفاية', isCorrect: false, rationale: '❌ الحماية منخفضة جداً.'),
        EduOption(text: 'باستخدم واقي للكبار', isCorrect: false, rationale: '❌ ممكن يسبب تهيج.'),
      ],
    ),
    EduQuestion(
      id: 'q_13',
      question: 'طفلك بيشتكي من ألم في أذنه. ده ممكن يكون:',
      emoji: '👂',
      category: 'الألم',
      context: 'ألم الأذن شائع في الأطفال.',
      options: [
        EduOption(text: 'التهاب أذن وسطى أو عدوى — محتاج كشف طبي', isCorrect: true, rationale: '✅ ألم الأذن غالباً يحتاج طبيب.'),
        EduOption(text: 'مجرد مزاج سيئ', isCorrect: false, rationale: '❌ الألم الحقيقي مش مزاج.'),
        EduOption(text: 'عسر هضم', isCorrect: false, rationale: '❌ العسر الهضمي مش مرتبط بالأذن.'),
        EduOption(text: 'مشكلة في الأسنان', isCorrect: false, rationale: '❌ مش غالباً.'),
      ],
    ),
    EduQuestion(
      id: 'q_14',
      question: 'إيه أفضل طريقة لتشجيع طفلك على الرياضة؟',
      emoji: '⚽',
      category: 'الرياضة',
      context: 'النشاط البدني مهم للصحة.',
      options: [
        EduOption(text: 'نلعب معاه ألعاب يحبها في الهواء الطلق', isCorrect: true, rationale: '✅ المتعة والمشاركة بتشجع النشاط.'),
        EduOption(text: 'بجبره على تمرين صعب', isCorrect: false, rationale: '❌ الضغط بيبعده عن الرياضة.'),
        EduOption(text: 'بده يتمرن لوحده ساعة', isCorrect: false, rationale: '❌ المدة الطويلة ممكن تمله.'),
        EduOption(text: 'بعده عن الألعاب بس', isCorrect: false, rationale: '❌ لازم نعوّض بأنشطة بديلة.'),
      ],
    ),
        ];
      case 4:
        return const [
    EduQuestion(
      id: 'q_15',
      question: 'إيه اللي تعمليه لو طفلك قالك إنه مش قادر يتنفس بسهولة؟',
      emoji: '😮‍💨',
      category: 'الطوارئ',
      context: 'صعوبة التنفس حالة طوارئ.',
      options: [
        EduOption(text: 'بتطمئنيه وتتصل بالإسعاف فوراً', isCorrect: true, rationale: '✅ صعوبة التنفس تحتاج تدخل سريع.'),
        EduOption(text: 'بتدهله عصير', isCorrect: false, rationale: '❌ العصير مش حل.'),
        EduOption(text: 'بتسيبه يستريح ونشوف', isCorrect: false, rationale: '❌ ممكن يكون خطر.'),
        EduOption(text: 'بتدهله دواء عشوائي', isCorrect: false, rationale: '❌ الدواء بدون تشخيص خطر.'),
      ],
    ),
    EduQuestion(
      id: 'q_16',
      question: 'إزاي تعرفي إن طفلك عنده أنيميا؟',
      emoji: '🩸',
      category: 'التغذية',
      context: 'الأنيميا بتأثر على النشاط والنمو.',
      options: [
        EduOption(text: 'تعب مستمر، شحوب، ضعف شهية، وصعوبة تركيز', isCorrect: true, rationale: '✅ دي علامات محتملة.'),
        EduOption(text: 'كثرة البكاء فقط', isCorrect: false, rationale: '❌ البكاء مش علامة أنيميا.'),
        EduOption(text: 'زيادة الوزن', isCorrect: false, rationale: '❌ مش علامة.'),
        EduOption(text: 'شعر خشن', isCorrect: false, rationale: '❌ ممكن يكون من أسباب تانية.'),
      ],
    ),
    EduQuestion(
      id: 'q_17',
      question: 'طفلك عنده إسهال. إيه أولوية العلاج؟',
      emoji: '💩',
      category: 'الإسهال',
      context: 'الإسهال ممكن يسبب جفاف.',
      options: [
        EduOption(text: 'الترطيب المستمر (ORS أو ماء) وتغذية خفيفة', isCorrect: true, rationale: '✅ السوائل أولوية.'),
        EduOption(text: 'منع الأكل نهائياً', isCorrect: false, rationale: '❌ التغذية الخفيفة مهمة.'),
        EduOption(text: 'مضاد حيوي فوراً', isCorrect: false, rationale: '❌ الإسهال غالباً فيروسي.'),
        EduOption(text: 'دواء لوقف الإسهال', isCorrect: false, rationale: '❌ مش دايماً مناسب للأطفال.'),
      ],
    ),
    EduQuestion(
      id: 'q_18',
      question: 'إيه أهمية تطعيم الأطفال؟',
      emoji: '💉',
      category: 'التطعيم',
      context: 'التطعيمات بتمنع أمراض خطيرة.',
      options: [
        EduOption(text: 'بتحمي من أمراض خطيرة وتقلل مضاعفاتها', isCorrect: true, rationale: '✅ التطعيم أمان علمي مثبت.'),
        EduOption(text: 'مش ضروري لو الطفل بصحة جيدة', isCorrect: false, rationale: '❌ الأمراض ممكن تصيب الأصحاء.'),
        EduOption(text: 'بسبب آثار جانبية خطيرة', isCorrect: false, rationale: '❌ الفوائد أكبر بكثير من المخاطر.'),
        EduOption(text: 'بس للأطفال الضعفاء', isCorrect: false, rationale: '❌ كل الأطفال محتاجين.'),
      ],
    ),
    EduQuestion(
      id: 'q_19',
      question: 'إزاي تعلمي طفلك غسل إيديه بطريقة صحيحة؟',
      emoji: '🧼',
      category: 'النظافة',
      context: 'غسل اليدين بيمنع العدوى.',
      options: [
        EduOption(text: 'تحت الماء الجاري بالصابون لمدة 20 ثانية', isCorrect: true, rationale: '✅ المدة والصابون أساسية.'),
        EduOption(text: 'بالماء بس', isCorrect: false, rationale: '❌ الصابون مطلوب.'),
        EduOption(text: 'بمناديل مبللة', isCorrect: false, rationale: '❌ المناديل مش بديل.'),
        EduOption(text: '5 ثواني كفاية', isCorrect: false, rationale: '❌ المدة قصيرة جداً.'),
      ],
    ),
        ];
      case 5:
        return const [
    EduQuestion(
      id: 'q_20',
      question: 'إيه اللي تعمليه لو طفلك تعرض لعضة حشرة؟',
      emoji: '🦟',
      category: 'الإسعافات',
      context: 'عضات الحشرات ممكن تسبب تورم أو حساسية.',
      options: [
        EduOption(text: 'بتغسلي المكان، تضعي كمادات باردة، وتراقبي التورم', isCorrect: true, rationale: '✅ التنظيف والتبريد أول خطوة.'),
        EduOption(text: 'بتحطي زيت دافئ', isCorrect: false, rationale: '❌ الحرارة ممكن تزود الحكة.'),
        EduOption(text: 'بتحكي المكان', isCorrect: false, rationale: '❌ الحك بيسبب عدوى.'),
        EduOption(text: 'بتقصي الجلد عشان تطلع السم', isCorrect: false, rationale: '❌ ده خطر جداً.'),
      ],
    ),
    EduQuestion(
      id: 'q_21',
      question: 'طفلك بياكل سكريات كتير. إيه التأثير المتوقع؟',
      emoji: '🍭',
      category: 'التغذية',
      context: 'السكريات الزيادة بتأثر الصحة.',
      options: [
        EduOption(text: 'تسوس أسنان، زيادة وزن، وطاقة متقلبة', isCorrect: true, rationale: '✅ دي تأثيرات معروفة.'),
        EduOption(text: 'بس يبقى نشط أكتر', isCorrect: false, rationale: '❌ التقلب ممكن يحصل بس مش صحة مستدامة.'),
        EduOption(text: 'لا يوجد تأثير', isCorrect: false, rationale: '❌ السكريات الزيادة ليها تأثيرات.'),
        EduOption(text: 'بيقلل وزنه', isCorrect: false, rationale: '❌ عكس ذلك غالباً.'),
      ],
    ),
    EduQuestion(
      id: 'q_22',
      question: 'إيه علامات التهاب الحلق اللي تحتاج طبيب؟',
      emoji: '🤒',
      category: 'الأعراض',
      context: 'بعض التهابات الحلق بكتيرية وتحتاج علاج.',
      options: [
        EduOption(text: 'حمى عالية، صعوبة بلع، أو انتفاخ في الغدد', isCorrect: true, rationale: '✅ دي علامات تحتاج كشف.'),
        EduOption(text: 'سعال خفيف', isCorrect: false, rationale: '❌ ممكن يكون فيروسي بسيط.'),
        EduOption(text: 'عطس', isCorrect: false, rationale: '❌ مش علامة خطيرة.'),
        EduOption(text: 'صوت مبحوح', isCorrect: false, rationale: '❌ ممكن يتحسن لوحده.'),
      ],
    ),
    EduQuestion(
      id: 'q_23',
      question: 'إزاي تحمي طفلك من الأمراض المعدية في المدرسة؟',
      emoji: '🦠',
      category: 'الوقاية',
      context: 'العدوى شائعة في الأماكن المزدحمة.',
      options: [
        EduOption(text: 'غسل اليدين، تطعيمات محدثة، والبقاء في البيت لما يكون مريض', isCorrect: true, rationale: '✅ الوقاية الشخصية أفضل.'),
        EduOption(text: 'بمنعه من الذهاب للمدرسة', isCorrect: false, rationale: '❌ المنع مش حل.'),
        EduOption(text: 'بده أدوية وقائية كل يوم', isCorrect: false, rationale: '❌ الأدوية الوقائية غير ضرورية.'),
        EduOption(text: 'بغطيه بالكمامة بس', isCorrect: false, rationale: '❌ الكمامة مهمة بس مش كفاية.'),
      ],
    ),
    EduQuestion(
      id: 'q_24',
      question: 'إيه اللي تعمليه لو طفلك بيقلب عينيه أو بيشتكي من صداع؟',
      emoji: '🤕',
      category: 'الأعراض',
      context: 'الصداع عند الأطفال له أسباب متعددة.',
      options: [
        EduOption(text: 'بتطمنه، بتعطيه ماء، وتراقب إذا استمر أو زاد', isCorrect: true, rationale: '✅ المراقبة مهمة.'),
        EduOption(text: 'بتهمله عشان بيتصنع', isCorrect: false, rationale: '❌ الصداع الحقيقي مش تصنع.'),
        EduOption(text: 'بتدهله مسكن قوي فوراً', isCorrect: false, rationale: '❌ لازم تكون جرعات آمنة.'),
        EduOption(text: 'بتسيبه يلعب عادي', isCorrect: false, rationale: '❌ الراحة ممكن تكون أفضل.'),
      ],
    ),
        ];
      case 6:
        return const [
    EduQuestion(
      id: 'q_25',
      question: 'إيه أهمية الزيارة الدورية لطبيب الأطفال؟',
      emoji: '🩺',
      category: 'المتابعة',
      context: 'المتابعة الصحية بتكشف المشاكل بدري.',
      options: [
        EduOption(text: 'لمراقبة النمو، التطعيمات، والكشف المبكر', isCorrect: true, rationale: '✅ المتابعة وقاية.'),
        EduOption(text: 'مش مهمة لو الطفل بصحة جيدة', isCorrect: false, rationale: '❌ الفحص الدوري بيكشف حاجات مش ظاهرة.'),
        EduOption(text: 'بس لما الطفل يتعب', isCorrect: false, rationale: '❌ الوقاية أفضل.'),
        EduOption(text: 'لأخذ أدوية', isCorrect: false, rationale: '❌ مش كل زيارة تحتاج دواء.'),
      ],
    ),
    EduQuestion(
      id: 'q_26',
      question: 'طفلك عنده حساسية منبيض. إزاي تتعاملي مع الأكل بره البيت؟',
      emoji: '🥚',
      category: 'الحساسية',
      context: 'الحساسية تحتاج حذر.',
      options: [
        EduOption(text: 'بسأل عن المكونات وبخلي معاه دواء الطوارئ لو وصف', isCorrect: true, rationale: '✅ التوضيح والاستعداد مهمان.'),
        EduOption(text: 'بسيبه ياكل عادي', isCorrect: false, rationale: '❌ الحساسية خطيرة.'),
        EduOption(text: 'بمنعه من الأكل بره نهائياً', isCorrect: false, rationale: '❌ التوضيح أفضل من المنع.'),
        EduOption(text: 'بده دواء قبل الأكل بدون وصفة', isCorrect: false, rationale: '❌ الأدوية تحتاج توجيه طبي.'),
      ],
    ),
    EduQuestion(
      id: 'q_27',
      question: 'إيه اللي تعمليه لو طفلك بلع دواء بالغلط؟',
      emoji: '💊',
      category: 'الطوارئ',
      context: 'الأدوية خطرة على الأطفال بجرعات زيادة.',
      options: [
        EduOption(text: 'بتتصل بالإسعاف أو مركز السموم فوراً', isCorrect: true, rationale: '✅ ده حالة طوارئ.'),
        EduOption(text: 'بتدهله ماء كتير عشان يتقيأ', isCorrect: false, rationale: '❌ القيء ممكن يزود الضرر.'),
        EduOption(text: 'بتسيبه ينام', isCorrect: false, rationale: '❌ النوم خطر.'),
        EduOption(text: 'بتدهله دواء تاني عشوائي', isCorrect: false, rationale: '❌ ده خطير جداً.'),
      ],
    ),
    EduQuestion(
      id: 'q_28',
      question: 'إزاي تختاري مقعد السيارة المناسب لطفلك؟',
      emoji: '🚗',
      category: 'السلامة',
      context: 'مقاعد السيارة بتنقذ حياة.',
      options: [
        EduOption(text: 'حسب الوزن والطول والعمر، وموجهة للخلف للرضع', isCorrect: true, rationale: '✅ المقاس الصحيح أهم.'),
        EduOption(text: 'أي مقعد كبير يكفي', isCorrect: false, rationale: '❌ المقعد الكبير مش آمن.'),
        EduOption(text: 'مقعد موجه للأمام لحديث الولادة', isCorrect: false, rationale: '❌ الرضع يحتاجون للخلف.'),
        EduOption(text: 'مش مهم لو الرحلة قصيرة', isCorrect: false, rationale: '❌ الحوادث ممكن تحصل في رحلات قصيرة.'),
      ],
    ),
    EduQuestion(
      id: 'q_29',
      question: 'إيه اللي تعمليه لو طفلك تعرض للاختناق وكان يتنفس؟',
      emoji: '😤',
      category: 'الطوارئ',
      context: 'الاختناق الجزئي يحتاج تشجيع على السعال.',
      options: [
        EduOption(text: 'بتشجعه يسعل وما تحطيش إيدك في بؤه', isCorrect: true, rationale: '✅ السعال أحسن آلية طبيعية.'),
        EduOption(text: 'بتضربه على ظهره بقوة', isCorrect: false, rationale: '❌ ممكن تزود الانسداد.'),
        EduOption(text: 'بتديله ماء', isCorrect: false, rationale: '❌ الماء ممكن يزود المشكلة.'),
        EduOption(text: 'بتشيل اللي بيسد بإصبعك', isCorrect: false, rationale: '❌ ممكن تدفعه أعمق.'),
      ],
    ),
        ];
      case 7:
        return const [
    EduQuestion(
      id: 'q_30',
      question: 'إيه دور النوم في نمو الطفل؟',
      emoji: '🧠',
      category: 'النوم',
      context: 'النوم مرتبط بالنمو والذاكرة.',
      options: [
        EduOption(text: 'بيساعد النمو الجسدي، الذاكرة، والمناعة', isCorrect: true, rationale: '✅ النوم ضروري لتطور الطفل.'),
        EduOption(text: 'بس للراحة', isCorrect: false, rationale: '❌ دور النوم أكبر من الراحة.'),
        EduOption(text: 'مش مهم لو الطفل بياكل كويس', isCorrect: false, rationale: '❌ النوم والتغذية مهمين.'),
        EduOption(text: 'بيخليه كسول', isCorrect: false, rationale: '❌ النوم الكافي بيحسن النشاط.'),
      ],
    ),
    EduQuestion(
      id: 'q_31',
      question: 'طفلك بيشرب عصائر معلبة كل يوم. إيه المشكلة؟',
      emoji: '🧃',
      category: 'التغذية',
      context: 'العصائر المعلبة غالباً فيها سكر كتير.',
      options: [
        EduOption(text: 'السكر الزيادة بيسبب تسوس أسنان وزيادة وزن', isCorrect: true, rationale: '✅ الماء والفاكهة الطازجة أفضل.'),
        EduOption(text: 'مش فيها مشكلة عشان فيها فيتامينات', isCorrect: false, rationale: '❌ السكر غالباً بيزود عن الفائدة.'),
        EduOption(text: 'أحسن من المياه', isCorrect: false, rationale: '❌ الماء هو الأفضل.'),
        EduOption(text: 'بتمنع العطش فقط', isCorrect: false, rationale: '❌ العصائر مش أفضل مرطب.'),
      ],
    ),
    EduQuestion(
      id: 'q_32',
      question: 'إزاي تتعاملي مع طفلك لما يرفض الدواء؟',
      emoji: '🥄',
      category: 'الدواء',
      context: 'إعطاء الدواء للأطفال يحتاج حيلة.',
      options: [
        EduOption(text: 'بتستخدمي أداة قياس مناسبة أو تحطي الدواء في كمية صغيرة من أكل بيحبه', isCorrect: true, rationale: '✅ الأدوات والدمج مع الأكل بيساعدوا.'),
        EduOption(text: 'بتجبره بالعنف', isCorrect: false, rationale: '❌ ده بيخلق رفض مستقبلي.'),
        EduOption(text: 'بتسيبيه ما ياخدهوش', isCorrect: false, rationale: '❌ الدواء مهم.'),
        EduOption(text: 'بتخلطه في المشروب كله', isCorrect: false, rationale: '❌ لو ما شربش الكل، الجرعة هتقل.'),
      ],
    ),
    EduQuestion(
      id: 'q_33',
      question: 'إيه علامات الالتهاب الرئوي عند الأطفال؟',
      emoji: '🫁',
      category: 'الأعراض',
      context: 'الالتهاب الرئوي خطير ومحتاج طبيب.',
      options: [
        EduOption(text: 'حمى، سعال، صعوبة تنفس، وألم صدر', isCorrect: true, rationale: '✅ دي علامات تحتاج كشف طبي.'),
        EduOption(text: 'عطس خفيف', isCorrect: false, rationale: '❌ مش علامة التهاب رئوي.'),
        EduOption(text: 'كحة بسيطة', isCorrect: false, rationale: '❌ ممكن يكون برد عادي.'),
        EduOption(text: 'إسهال', isCorrect: false, rationale: '❌ مش العرض الرئيسي.'),
      ],
    ),
    EduQuestion(
      id: 'q_34',
      question: 'إزاي تحمي طفلك من التسمم بالمنزل؟',
      emoji: '⚗️',
      category: 'السلامة المنزلية',
      context: 'المنزل فيه مواد خطرة.',
      options: [
        EduOption(text: 'نحفظ المنظفات والأدوية بعيدة ومحكمة الإغلاق', isCorrect: true, rationale: '✅ التخزين الآمن أهم خطوة.'),
        EduOption(text: 'نخليها في الأدراج العادية', isCorrect: false, rationale: '❌ الأطفال بيفتحوا الأدراج.'),
        EduOption(text: 'نحطهم على الأرض', isCorrect: false, rationale: '❌ ده أسهل وصول للطفل.'),
        EduOption(text: 'نشيل التسمومات بس', isCorrect: false, rationale: '❌ المنظفات كمان خطرة.'),
      ],
    ),
        ];
      case 8:
        return const [
    EduQuestion(
      id: 'q_35',
      question: 'طفلك تعرض لحروق بسيطة من مياه ساخنة. إيه أول إجراء؟',
      emoji: '🔥',
      category: 'الإسعافات',
      context: 'الحروق محتاجة تبريد سريع.',
      options: [
        EduOption(text: 'بتجري الماء البارد على المكان لمدة 10-20 دقيقة', isCorrect: true, rationale: '✅ التبريد أول خطوة.'),
        EduOption(text: 'تحطي زبدة أو معجون أسنان', isCorrect: false, rationale: '❌ المواد دي ممكن تسبب عدوى.'),
        EduOption(text: 'بتفقع البثور', isCorrect: false, rationale: '❌ ده بيزود خطر العدوى.'),
        EduOption(text: 'تحطي كريم حرارة', isCorrect: false, rationale: '❌ ممنوع.'),
      ],
    ),
    EduQuestion(
      id: 'q_36',
      question: 'إيه اللي تعمليه لو طفلك بلع قطعة صغيرة وبدأ يتنفس بصعوبة؟',
      emoji: '😮',
      category: 'الطوارئ',
      context: 'ده اختناق جزئي أو كلي.',
      options: [
        EduOption(text: 'بتشجعه يسعل وبتتصل بالإسعاف فوراً', isCorrect: true, rationale: '✅ السعال والإسعاف أولوية.'),
        EduOption(text: 'بتديله ماء', isCorrect: false, rationale: '❌ الماء ممكن يزود الانسداد.'),
        EduOption(text: 'بتصفعه على ظهره', isCorrect: false, rationale: '❌ ممكن يزود المشكلة.'),
        EduOption(text: 'بتسيبه يتعامل لوحده', isCorrect: false, rationale: '❌ ده خطر على حياته.'),
      ],
    ),
    EduQuestion(
      id: 'q_37',
      question: 'إزاي تختاري طعام صحي لطفلك في المدرسة؟',
      emoji: '🍱',
      category: 'التغذية',
      context: 'السناكس المدرسية بتأثر التغذية.',
      options: [
        EduOption(text: 'فاكهة، خضار، جبن، ومكسرات بكميات مناسبة', isCorrect: true, rationale: '✅ التنوع والتوازن أفضل.'),
        EduOption(text: 'شيبسي وحلويات عشان يفرح', isCorrect: false, rationale: '❌ السكريات والدهون المهدرجة كتير.'),
        EduOption(text: 'مشروبات غازية للطاقة', isCorrect: false, rationale: '❌ بتعمل تقلب طاقة.'),
        EduOption(text: 'بس ساندوتشات', isCorrect: false, rationale: '❌ لو مش متوازنة مش كفاية.'),
      ],
    ),
    EduQuestion(
      id: 'q_38',
      question: 'إيه اللي تعمليه لو طفلك تعرض لقرصة نحلة؟',
      emoji: '🐝',
      category: 'الإسعافات',
      context: 'قرصات الحشرات ممكن تسبب تورم.',
      options: [
        EduOption(text: 'بنشل اللاسعة لو موجودة، بنظف، ونضع كمادات باردة', isCorrect: true, rationale: '✅ الإجراء الصحيح.'),
        EduOption(text: 'بنحط عسل على المكان', isCorrect: false, rationale: '❌ العسل ممكن يسبب عدوى.'),
        EduOption(text: 'بنضغط على المكان بقوة', isCorrect: false, rationale: '❌ ممكن يزود التورم.'),
        EduOption(text: 'بنتركه من غير تنظيف', isCorrect: false, rationale: '❌ التنظيف مهم.'),
      ],
    ),
    EduQuestion(
      id: 'q_39',
      question: 'إزاي تعرفي إن طفلك محتاج زيارة طبيب عيون؟',
      emoji: '👀',
      category: 'العيون',
      context: 'الرؤية بتأثر على التعلم.',
      options: [
        EduOption(text: 'إنه يقرب من الشاشة، يحكي عينيه، أو يشتكي من صداع', isCorrect: true, rationale: '✅ دي علامات تحتاج فحص.'),
        EduOption(text: 'إنه يلبس نظارة شمسية', isCorrect: false, rationale: '❌ مش علامة مشكلة.'),
        EduOption(text: 'إنه يبكي كتير', isCorrect: false, rationale: '❌ البكاء له أسباب كتير.'),
        EduOption(text: 'إنه ينام قليل', isCorrect: false, rationale: '❌ مش دليل مباشر.'),
      ],
    ),
        ];
      case 9:
        return const [
    EduQuestion(
      id: 'q_40',
      question: 'طفلك بيعاني من إمساك. إيه الحلول الأولية؟',
      emoji: '🚽',
      category: 'الهضم',
      context: 'الإمساك شائع ومحتاج تغذية وماء.',
      options: [
        EduOption(text: 'زيادة الماء، الألياف، والتحرك البدني', isCorrect: true, rationale: '✅ الح lifestyle changes أول خطوة.'),
        EduOption(text: 'ملينات قوية فوراً', isCorrect: false, rationale: '❌ محتاجة استشارة طبيب.'),
        EduOption(text: 'منع الأكل', isCorrect: false, rationale: '❌ الألياف مهمة.'),
        EduOption(text: 'الحليب بس', isCorrect: false, rationale: '❌ الحليب ممكن يزود الإمساك عند بعض الأطفال.'),
      ],
    ),
    EduQuestion(
      id: 'q_41',
      question: 'إزاي تحمي طفلك من أمراض الشتاء؟',
      emoji: '🧣',
      category: 'الوقاية',
      context: 'التهابات الجهاز التنفسي شائعة في الشتاء.',
      options: [
        EduOption(text: 'غسل اليدين، تدفئة مناسبة، تطعيمات، والابتعاد عن المرضى', isCorrect: true, rationale: '✅ الوقاية المتعددة.'),
        EduOption(text: 'بنمنعه من الخروج نهائياً', isCorrect: false, rationale: '❌ ده مش واقعي.'),
        EduOption(text: 'بنده أدوية وقائية', isCorrect: false, rationale: '❌ مفيش أدوية وقائية عامة.'),
        EduOption(text: 'بنعطيه مكملات عشوائية', isCorrect: false, rationale: '❌ المكملات تحتاج نصيحة.'),
      ],
    ),
    EduQuestion(
      id: 'q_42',
      question: 'إيه اللي تعمليه لو طفلك بيشتكي من ألم في بطنه؟',
      emoji: '🤢',
      category: 'الأعراض',
      context: 'ألم البطن له أسباب متعددة.',
      options: [
        EduOption(text: 'بتطمنه، بتعطيه ماء، وتراقب الألم — وتروحي الطبيب لو استمر', isCorrect: true, rationale: '✅ المراقبة ثم الكشف لو استمر.'),
        EduOption(text: 'بتدهله مسكن فوراً', isCorrect: false, rationale: '❌ المسكن ممكن يخفي علامات خطيرة.'),
        EduOption(text: 'بتجبره ياكل عشان يعدي', isCorrect: false, rationale: '❌ الأكل ممكن يزود الألم.'),
        EduOption(text: 'بتهمله عشان غالباً غازات', isCorrect: false, rationale: '❌ ممكن يكون سبب خطير.'),
      ],
    ),
    EduQuestion(
      id: 'q_43',
      question: 'إزاي تساعدي طفلك يقلل من السكر اليومي؟',
      emoji: '🍬',
      category: 'التغذية',
      context: 'تقليل السكر مهم للصحة.',
      options: [
        EduOption(text: 'بتقدمي بدائل طبيعية زي الفاكهة وتقللي العصائر والحلويات', isCorrect: true, rationale: '✅ التدريج والبدائل أفضل.'),
        EduOption(text: 'بتمنعه فجأة من كل حاجة', isCorrect: false, rationale: '❌ الحظر المفاجئ بيكون صعب.'),
        EduOption(text: 'بتديله سكر بديل كتير', isCorrect: false, rationale: '❌ البدائل كمان ليها حدود.'),
        EduOption(text: 'بتسيبه يقرر هو', isCorrect: false, rationale: '❌ الأطفال محتاجين توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_44',
      question: 'إيه أهمية اللعب في الهواء الطلق للأطفال؟',
      emoji: '🌳',
      category: 'النشاط',
      context: 'الطبيعة والحركة مهمة.',
      options: [
        EduOption(text: 'بتحسن النمو الجسدي، المناعة، والصحة النفسية', isCorrect: true, rationale: '✅ الفوائد متعددة.'),
        EduOption(text: 'بس عشان يتسلى', isCorrect: false, rationale: '❌ الفايدة أكبر من التسلية.'),
        EduOption(text: 'مش مهم لو فيه ألعاب داخلية', isCorrect: false, rationale: '❌ الهواء الطلق له فوائد خاصة.'),
        EduOption(text: 'بيسبب مرض أكتر', isCorrect: false, rationale: '❌ العكس صحيح.'),
      ],
    ),
        ];
      case 10:
        return const [
    EduQuestion(
      id: 'q_45',
      question: 'إزاي تبني عادات صحية مستدامة لطفلك؟',
      emoji: '🌱',
      category: 'العادات',
      context: 'العادات بتتكون بالتكرار والقدوة.',
      options: [
        EduOption(text: 'بكوني قدوة، نحدد روتين، ونحتفل بالنجاحات الصغيرة', isCorrect: true, rationale: '✅ القدوة والروتين أساس العادات.'),
        EduOption(text: 'بجبره على كل حاجة', isCorrect: false, rationale: '❌ القوة بتولد رفض.'),
        EduOption(text: 'بعده عن كل حاجة غير صحية فجأة', isCorrect: false, rationale: '❌ التدرج أفضل.'),
        EduOption(text: 'بسيبه يتعلم من أصحابه', isCorrect: false, rationale: '❌ البيت هو المصدر الأساسي.'),
      ],
    ),
    EduQuestion(
      id: 'q_46',
      question: 'طفلك عنده سلوك ت repetitive يضر نفسه. إيه تصرفك؟',
      emoji: '🔄',
      category: 'السلوك',
      context: 'بعض السلوكيات تحتاج تقييم متخصص.',
      options: [
        EduOption(text: 'بتسجّلي السلوك وتعرضيه على أخصائي', isCorrect: true, rationale: '✅ هذا الخيار صحيح.'),
        EduOption(text: 'بتعاقبيه عشان يبطل', isCorrect: false, rationale: '❌ العقاب ممكن يزود السلوك.'),
        EduOption(text: 'بتتجاهليه تماماً', isCorrect: false, rationale: '❌ السلوك المؤذي يحتاج تقييم.'),
        EduOption(text: 'بتشوفي فيديوهات على يوتيوب بس', isCorrect: false, rationale: '❌ الفيديوهات مش بديل عن متخصص.'),
      ],
    ),
    EduQuestion(
      id: 'q_47',
      question: 'إيه اللي تعمليه لو طفلك اتعرض لحادث ورأسه اتخبطت بس ما فيش نزيف؟',
      emoji: '🧠',
      category: 'الإصابات',
      context: 'إصابات الرأس محتاجة مراقبة حتى لو بسيطة.',
      options: [
        EduOption(text: 'براقب الطفل 24 ساعة لعلامات زي الغثيان أو النعاس الغير طبيعي', isCorrect: true, rationale: '✅ المراقبة ضرورية بعد ضربة الرأس.'),
        EduOption(text: 'بسيبه عشان مفيش نزيف', isCorrect: false, rationale: '❌ النزيف مش العلامة الوحيدة.'),
        EduOption(text: 'بده دواء مسكن قوي', isCorrect: false, rationale: '❌ المسكنات ممكن تخفي أعراض.'),
        EduOption(text: 'بخلي ينام طول اليوم', isCorrect: false, rationale: '❌ النوم الزيادة ممكن يكون علامة خطيرة.'),
      ],
    ),
    EduQuestion(
      id: 'q_48',
      question: 'إزاي تختاري طبيب الأطفال المناسب؟',
      emoji: '👨‍⚕️',
      category: 'الرعاية',
      context: 'العلاقة مع الطبيب بتأثر على صحة الطفل.',
      options: [
        EduOption(text: 'بشوف خبرته، سمعته، وسهولة التواصل معاه', isCorrect: true, rationale: '✅ التواصل والخبرة مهمان.'),
        EduOption(text: 'بختار أقرب واحد بس', isCorrect: false, rationale: '❌ القرب مفيد بس مش المعيار الوحيد.'),
        EduOption(text: 'بسأل أي حد في الشارع', isCorrect: false, rationale: '❌ التوصيات لازم تكون من مصادر موثوقة.'),
        EduOption(text: 'بختار الأرخص دايماً', isCorrect: false, rationale: '❌ السعر مش مؤشر على الجودة.'),
      ],
    ),
    EduQuestion(
      id: 'q_49',
      question: 'إيه أهمية الصحة النفسية للطفل جنب الصحة الجسدية؟',
      emoji: '🧘',
      category: 'الصحة النفسية',
      context: 'الصحة النفسية بتأثر على التعلم والعلاقات.',
      options: [
        EduOption(text: 'النفسية السليمة بتساعده يتعلم، يتعامل، وينمو بشكل أفضل', isCorrect: true, rationale: '✅ العقل والجسد مرتبطين.'),
        EduOption(text: 'مش مهمة زي الجسدية', isCorrect: false, rationale: '❌ النفسية مهمة جداً.'),
        EduOption(text: 'بس للأطفال الكبار', isCorrect: false, rationale: '❌ كل الأعمار محتاجة.'),
        EduOption(text: 'بتتحسن لوحده', isCorrect: false, rationale: '❌ محتاجة اهتمام وتوجيه.'),
      ],
    ),
        ];
      default:
        return _buildQuestions(1);
    }
  }
}
