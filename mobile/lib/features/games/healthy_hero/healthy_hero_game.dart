/// Smart Habits educational mini-game (formerly "Healthy Hero").
///
/// Reframed to teach daily habits, responsibility, social/emotional and life
/// skills — NO medical/first-aid/clinical content — so the app stays squarely
/// "Islamic education" and does not present undeclared health features.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Smart Habits game.
class HealthyHeroGame extends EduGameShell {
  const HealthyHeroGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'healthy_hero',
            name: 'بطل العادات الذكية',
            heroEmoji: '🌟',
            description: 'عادات ومهارات حياتية ذكية لطفلك',
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
      category: 'عادات الأكل',
      context: 'بناء علاقة إيجابية مع الأكل أهم من الإجبار.',
      options: [
        EduOption(text: 'بقدّمه بطريقة ممتعة أو أخلطه مع أكلة بيحبها', isCorrect: true, rationale: '✅ المرونة بتساعد الطفل يتقبّل أصناف جديدة.'),
        EduOption(text: 'بزعقله عشان ياكل', isCorrect: false, rationale: '❌ الضغط بيخلق نفور من الأكل.'),
        EduOption(text: 'بسيبه ما ياكلش خالص', isCorrect: false, rationale: '❌ من غير تشجيع مش هيجرّب أصناف جديدة.'),
        EduOption(text: 'بديله حلويات بدل الخضار', isCorrect: false, rationale: '❌ بيكافئ الرفض بعادة أسوأ.'),
      ],
    ),
    EduQuestion(
      id: 'q_1',
      question: 'عايزة تعوّدي طفلك يشرب ماء كفاية في اليوم. أفضل طريقة؟',
      emoji: '💧',
      category: 'عادات يومية',
      context: 'العادات بتترسّخ بالتكرار والتسهيل.',
      options: [
        EduOption(text: 'أخلي زجازة الماء قريبة منه، أذكّره، وأشرب معاه', isCorrect: true, rationale: '✅ التسهيل والقدوة بيكوّنوا العادة.'),
        EduOption(text: 'أمنعه من أي مشروب تاني بالقوة', isCorrect: false, rationale: '❌ المنع المفاجئ بيقابَل برفض.'),
        EduOption(text: 'أسيبه يشرب لما يعطش بس', isCorrect: false, rationale: '❌ الأطفال بينسوا، والتذكير بيساعد.'),
        EduOption(text: 'أكافئه بحلوى كل ما يشرب', isCorrect: false, rationale: '❌ بيربط الماء بمكافأة مش بعادة.'),
      ],
    ),
    EduQuestion(
      id: 'q_2',
      question: 'ألعاب طفلك مرمية بعد اللعب. إزاي تبني عنده عادة الترتيب؟',
      emoji: '🧸',
      category: 'المسؤولية',
      context: 'المسؤولية بتتعلّم بالتدريب لا التوبيخ.',
      options: [
        EduOption(text: 'نرتّب مع بعض، نحوّلها للعبة، ووقت ثابت كل يوم', isCorrect: true, rationale: '✅ المشاركة والروتين بيرسّخوا العادة.'),
        EduOption(text: 'أرتّبها أنا كل مرة بدله', isCorrect: false, rationale: '❌ مش هيتعلّم المسؤولية.'),
        EduOption(text: 'أزعقله لو ما رتّبش', isCorrect: false, rationale: '❌ التوبيخ بيخلّيها مهمة مكروهة.'),
        EduOption(text: 'أسيب الفوضى عشان يتعب منها', isCorrect: false, rationale: '❌ الطفل غالبًا ما بيربطش لوحده.'),
      ],
    ),
    EduQuestion(
      id: 'q_3',
      question: 'عايزة روتين نوم هادي لطفلك. الأنسب؟',
      emoji: '🛏️',
      category: 'الروتين',
      context: 'الروتين الثابت بيسهّل النوم.',
      options: [
        EduOption(text: 'ميعاد ثابت + قصة + إبعاد الشاشات قبلها بفترة', isCorrect: true, rationale: '✅ الهدوء والثبات بيهيّئوا للنوم.'),
        EduOption(text: 'يسهر لحد ما ينعس لوحده', isCorrect: false, rationale: '❌ النوم المتأخر بيأثّر على يومه.'),
        EduOption(text: 'يشوف موبايل لحد ما ينام', isCorrect: false, rationale: '❌ الشاشة بتأخّر النوم.'),
        EduOption(text: 'ميعاد مختلف كل يوم', isCorrect: false, rationale: '❌ غياب الثبات بيصعّب العادة.'),
      ],
    ),
    EduQuestion(
      id: 'q_4',
      question: 'إزاي تعوّدي طفلك على كلمات الأدب (من فضلك / شكرًا)؟',
      emoji: '🙏',
      category: 'مهارات اجتماعية',
      context: 'الأدب بيتعلّم بالقدوة والتكرار.',
      options: [
        EduOption(text: 'أقولها أنا قدامه وأمدحه لما يقولها', isCorrect: true, rationale: '✅ القدوة والتعزيز الإيجابي أقوى أداة.'),
        EduOption(text: 'أجبره يعتذر بالقوة', isCorrect: false, rationale: '❌ الإجبار بيفقدها معناها.'),
        EduOption(text: 'أتجاهل لو ما قالهاش', isCorrect: false, rationale: '❌ من غير تشجيع مش هتترسّخ.'),
        EduOption(text: 'أقارنه بأطفال تانيين', isCorrect: false, rationale: '❌ المقارنة بتجرح الثقة.'),
      ],
    ),
        ];
      case 2:
        return const [
    EduQuestion(
      id: 'q_5',
      question: 'طفلك عايز يقعد على الشاشة طول اليوم. أفضل تصرّف؟',
      emoji: '📱',
      category: 'وقت الشاشة',
      context: 'التوازن بيتحقق بحدود واضحة وبدائل.',
      options: [
        EduOption(text: 'نتفق على وقت محدد ونوفّر أنشطة بديلة ممتعة', isCorrect: true, rationale: '✅ الحدود + البدائل بتنظّم العادة.'),
        EduOption(text: 'أمنع الشاشة فجأة تمامًا', isCorrect: false, rationale: '❌ المنع الحاد بيسبّب صراع.'),
        EduOption(text: 'أسيبه على راحته', isCorrect: false, rationale: '❌ غياب الحدود بيكبّر المشكلة.'),
        EduOption(text: 'أديله الشاشة عشان يهدا بس', isCorrect: false, rationale: '❌ بتتحوّل لوسيلة تهدئة وحيدة.'),
      ],
    ),
    EduQuestion(
      id: 'q_6',
      question: 'طفلك مش عايز يشارك ألعابه مع أخوه. إزاي تتعاملي؟',
      emoji: '🤝',
      category: 'مهارات اجتماعية',
      context: 'المشاركة مهارة بتنمو بالتدريب.',
      options: [
        EduOption(text: 'نتدرّب على الدور بالتناوب ونمدح المشاركة', isCorrect: true, rationale: '✅ التناوب والتعزيز بيعلّموا المشاركة.'),
        EduOption(text: 'آخد اللعبة بالقوة وأديها لأخوه', isCorrect: false, rationale: '❌ بيحسّسه بالظلم.'),
        EduOption(text: 'أزعقله قدام أخوه', isCorrect: false, rationale: '❌ الإحراج بيزوّد العناد.'),
        EduOption(text: 'أمنعه من اللعب نهائيًا', isCorrect: false, rationale: '❌ العقاب الزائد مش بيعلّم.'),
      ],
    ),
    EduQuestion(
      id: 'q_7',
      question: 'عايزة طفلك يجهّز شنطة المدرسة بنفسه. الأنسب؟',
      emoji: '🎒',
      category: 'المسؤولية',
      context: 'الاستقلالية بتتبني بخطوات صغيرة.',
      options: [
        EduOption(text: 'نعمل قائمة بسيطة ويجهّز بنفسه وأنا أتابع', isCorrect: true, rationale: '✅ القائمة + المتابعة بتبني الاستقلالية.'),
        EduOption(text: 'أجهّزها أنا كل يوم', isCorrect: false, rationale: '❌ مش هياخد المسؤولية.'),
        EduOption(text: 'أسيبه ينسى عشان يتعلّم بالعقاب', isCorrect: false, rationale: '❌ الإحباط المتكرر مش بيعلّم.'),
        EduOption(text: 'أزعقه لو نسي حاجة', isCorrect: false, rationale: '❌ التوبيخ بيقلّل ثقته.'),
      ],
    ),
    EduQuestion(
      id: 'q_8',
      question: 'إزاي تثبّتي ميعاد نوم طفلك؟',
      emoji: '⏰',
      category: 'الروتين',
      context: 'الثبات بيريّح الجسم والمزاج.',
      options: [
        EduOption(text: 'نفس الميعاد كل يوم حتى في الإجازة قدر الإمكان', isCorrect: true, rationale: '✅ الانتظام بيسهّل النوم والاستيقاظ.'),
        EduOption(text: 'ينام أي وقت حسب اليوم', isCorrect: false, rationale: '❌ التذبذب بيتعب مزاجه.'),
        EduOption(text: 'ينام متأخر في الإجازات بكتير', isCorrect: false, rationale: '❌ بيكسر عادة اتعبتي في بنائها.'),
        EduOption(text: 'مفيش داعي لميعاد', isCorrect: false, rationale: '❌ الأطفال بيرتاحوا للروتين.'),
      ],
    ),
    EduQuestion(
      id: 'q_9',
      question: 'إزاي تعوّدي طفلك يغسل أسنانه صح؟',
      emoji: '🪥',
      category: 'النظافة',
      context: 'نظافة الأسنان عادة يومية بالقدوة.',
      options: [
        EduOption(text: 'أكون قدوة، فرشاة ناعمة، ووقت ثابت مرتين', isCorrect: true, rationale: '✅ القدوة والأدوات المناسبة بتثبّت العادة.'),
        EduOption(text: 'أغسلها أنا بدله كل مرة', isCorrect: false, rationale: '❌ محتاج يتعلّم بنفسه.'),
        EduOption(text: 'مرة واحدة كل كام يوم', isCorrect: false, rationale: '❌ قليلة على بناء عادة.'),
        EduOption(text: 'أسيبه يقرّر لو عايز', isCorrect: false, rationale: '❌ محتاج توجيه ثابت.'),
      ],
    ),
        ];
      case 3:
        return const [
    EduQuestion(
      id: 'q_10',
      question: 'طفلك كسر حاجة وخبّاها. إزاي تشجّعيه يقول الحقيقة؟',
      emoji: '🫣',
      category: 'الأخلاق',
      context: 'الصدق بينمو في بيئة آمنة من العقاب القاسي.',
      options: [
        EduOption(text: 'أطمّنه إنه ينفع يقول الحقيقة وأركّز على الحل', isCorrect: true, rationale: '✅ الأمان النفسي بيشجّع الصدق.'),
        EduOption(text: 'أعاقبه بشدة عشان ما يكذبش', isCorrect: false, rationale: '❌ الخوف بيعلّم الكذب أكتر.'),
        EduOption(text: 'أتجاهل الموضوع تمامًا', isCorrect: false, rationale: '❌ بيفوّت فرصة تعليم.'),
        EduOption(text: 'أفضحه قدام إخواته', isCorrect: false, rationale: '❌ الإحراج بيكسر الثقة.'),
      ],
    ),
    EduQuestion(
      id: 'q_11',
      question: 'طفلك خسر في لعبة وزعّل جدًا. إزاي تساعديه؟',
      emoji: '🎲',
      category: 'المشاعر',
      context: 'تقبّل الخسارة مهارة بتتعلّم.',
      options: [
        EduOption(text: 'أتفهّم زعله وأعلّمه إن الخسارة جزء من اللعب', isCorrect: true, rationale: '✅ احتواء المشاعر + إعادة التأطير.'),
        EduOption(text: 'أقوله "متزعلش دي حاجة تافهة"', isCorrect: false, rationale: '❌ تجاهل المشاعر بيكبّرها.'),
        EduOption(text: 'أخليه يكسب دايمًا', isCorrect: false, rationale: '❌ بيمنعه من تعلّم التقبّل.'),
        EduOption(text: 'أمنعه من اللعب عشان ما يزعلش', isCorrect: false, rationale: '❌ التجنّب مش حل.'),
      ],
    ),
    EduQuestion(
      id: 'q_12',
      question: 'عايزة تبني عند طفلك حب القراءة. الأنسب؟',
      emoji: '📚',
      category: 'التعلّم',
      context: 'القراءة بتحب بالمتعة لا الواجب.',
      options: [
        EduOption(text: 'وقت قراءة ممتع يومي ونخليه يختار الكتاب', isCorrect: true, rationale: '✅ المتعة والاختيار بيحبّبوا القراءة.'),
        EduOption(text: 'أجبره يقرأ ساعة كل يوم', isCorrect: false, rationale: '❌ الإجبار بينفّر.'),
        EduOption(text: 'أديله كتب صعبة على سنه', isCorrect: false, rationale: '❌ الإحباط بيبعّده.'),
        EduOption(text: 'أسيب الموضوع للمدرسة بس', isCorrect: false, rationale: '❌ البيت مصدر أساسي للعادة.'),
      ],
    ),
    EduQuestion(
      id: 'q_13',
      question: 'عايزة طفلك يسمع الكلام وينفّذ التعليمات. الأفضل؟',
      emoji: '👂',
      category: 'مهارات',
      context: 'الإصغاء بيتحسّن بتعليمات واضحة وقصيرة.',
      options: [
        EduOption(text: 'تعليمات بسيطة وواضحة + تواصل بالعين ومدح التنفيذ', isCorrect: true, rationale: '✅ الوضوح والتعزيز بيحسّنوا الإصغاء.'),
        EduOption(text: 'أكرّر الكلام وأنا بزعّق', isCorrect: false, rationale: '❌ الزعيق بيقلّل الاستجابة.'),
        EduOption(text: 'أديله تعليمات كتير مرة واحدة', isCorrect: false, rationale: '❌ بيتشتّت.'),
        EduOption(text: 'أعاقبه على طول لو ما نفّذش', isCorrect: false, rationale: '❌ العقاب قبل التوضيح مش عادل.'),
      ],
    ),
    EduQuestion(
      id: 'q_14',
      question: 'أفضل طريقة تشجّعي بيها طفلك على الحركة واللعب الرياضي؟',
      emoji: '⚽',
      category: 'النشاط',
      context: 'الحركة بتحب بالمتعة والمشاركة.',
      options: [
        EduOption(text: 'نلعب معاه ألعاب يحبها في الهواء الطلق', isCorrect: true, rationale: '✅ المتعة والمشاركة بتشجّعوا النشاط.'),
        EduOption(text: 'أجبره على تمرين صعب', isCorrect: false, rationale: '❌ الضغط بيبعّده.'),
        EduOption(text: 'يتمرّن لوحده ساعة', isCorrect: false, rationale: '❌ المدة الطويلة بتملّه.'),
        EduOption(text: 'أبعده عن اللعب خالص', isCorrect: false, rationale: '❌ الحركة مهمة لطاقته ومزاجه.'),
      ],
    ),
        ];
      case 4:
        return const [
    EduQuestion(
      id: 'q_15',
      question: 'طفلك بيحاول يعمل حاجة لوحده وبيفشل ويزعل. الأنسب؟',
      emoji: '🧗',
      category: 'المهارات',
      context: 'الاستقلالية بتنمو بالدعم لا الحل بدلًا منه.',
      options: [
        EduOption(text: 'أشجّعه يحاول تاني وأساعده بتلميح بسيط', isCorrect: true, rationale: '✅ الدعم التدريجي بيبني الثقة.'),
        EduOption(text: 'أعملها أنا بدله فورًا', isCorrect: false, rationale: '❌ بيمنعه من التعلّم.'),
        EduOption(text: 'أقوله "سيبها مش هتعرفها"', isCorrect: false, rationale: '❌ بيكسر ثقته.'),
        EduOption(text: 'أزعقه عشان زعل', isCorrect: false, rationale: '❌ المشاعر محتاجة احتواء.'),
      ],
    ),
    EduQuestion(
      id: 'q_16',
      question: 'طفلك مش بيستنى دوره وعايز كل حاجة حالًا. إزاي تعلّميه الصبر؟',
      emoji: '⏳',
      category: 'المشاعر',
      context: 'الصبر مهارة بتتدرّب بالتدريج.',
      options: [
        EduOption(text: 'ألعاب الدور بالتناوب وانتظار قصير بيكبر تدريجيًا مع مدح', isCorrect: true, rationale: '✅ التدرّج والتعزيز بيبنوا الصبر.'),
        EduOption(text: 'أديله اللي عايزه فورًا دايمًا', isCorrect: false, rationale: '❌ بيرسّخ عدم الصبر.'),
        EduOption(text: 'أزعقه عشان يستنى', isCorrect: false, rationale: '❌ التوتر بيصعّب التعلّم.'),
        EduOption(text: 'أتجاهله لما يلحّ', isCorrect: false, rationale: '❌ محتاج توجيه مش إهمال.'),
      ],
    ),
    EduQuestion(
      id: 'q_17',
      question: 'عايزة طفلك ينضّف مكانه بعد الأكل. الأنسب؟',
      emoji: '🍽️',
      category: 'المسؤولية',
      context: 'المسؤولية بتتبني بمهام بسيطة مناسبة لسنه.',
      options: [
        EduOption(text: 'نوضّح المهمة، نعملها مع بعض في الأول، وأمدح المجهود', isCorrect: true, rationale: '✅ النمذجة والتعزيز بيعلّموا المسؤولية.'),
        EduOption(text: 'أنضّف أنا كل مرة', isCorrect: false, rationale: '❌ مش هياخد المهارة.'),
        EduOption(text: 'أعاقبه لو ما نضّفش', isCorrect: false, rationale: '❌ العقاب بيخلّيها مكروهة.'),
        EduOption(text: 'أسيبها متّسخة', isCorrect: false, rationale: '❌ مفيش تعلّم بدون توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_18',
      question: 'إزاي تشركي طفلك في مهام البيت البسيطة؟',
      emoji: '🧹',
      category: 'المسؤولية',
      context: 'المشاركة بتنمّي الانتماء والمهارة.',
      options: [
        EduOption(text: 'مهام بسيطة مناسبة لسنه ونحتفل بإنجازها', isCorrect: true, rationale: '✅ المهام المناسبة + التشجيع بيبنوا عادة المساعدة.'),
        EduOption(text: 'مهام صعبة فوق قدرته', isCorrect: false, rationale: '❌ بتسبّب إحباط.'),
        EduOption(text: 'أعفيه من أي مهمة', isCorrect: false, rationale: '❌ بيفوّت فرصة تعلّم المسؤولية.'),
        EduOption(text: 'أديله مكافأة مادية كبيرة كل مرة', isCorrect: false, rationale: '❌ بيربط المساعدة بالمقابل بس.'),
      ],
    ),
    EduQuestion(
      id: 'q_19',
      question: 'إزاي تعوّدي طفلك يغسل إيديه كعادة نظافة؟',
      emoji: '🧼',
      category: 'النظافة',
      context: 'النظافة عادة بتتثبّت بالروتين والقدوة.',
      options: [
        EduOption(text: 'نغسل مع بعض في أوقات ثابتة (قبل الأكل / بعد اللعب)', isCorrect: true, rationale: '✅ الربط بالمواقف اليومية بيثبّت العادة.'),
        EduOption(text: 'بالماء بس من غير صابون', isCorrect: false, rationale: '❌ الصابون جزء أساسي من العادة.'),
        EduOption(text: 'مرة في اليوم بس', isCorrect: false, rationale: '❌ قليلة على ترسيخ العادة.'),
        EduOption(text: 'أفكّره بالزعيق كل مرة', isCorrect: false, rationale: '❌ الزعيق بيخلّيها مهمة متوترة.'),
      ],
    ),
        ];
      case 5:
        return const [
    EduQuestion(
      id: 'q_20',
      question: 'عايزة تعلّمي طفلك يعدّي الشارع بأمان. الأنسب؟',
      emoji: '🚦',
      category: 'السلامة',
      context: 'مهارات السلامة بتتعلّم بالتكرار والقدوة.',
      options: [
        EduOption(text: 'نقف، نبصّ شمال ويمين، ونمشي مع بعض ونشرح كل خطوة', isCorrect: true, rationale: '✅ التكرار والقدوة بيعلّموا السلامة.'),
        EduOption(text: 'أسيبه يجري قدامي', isCorrect: false, rationale: '❌ خطر وبيفوّت التعليم.'),
        EduOption(text: 'أعدّي وأنا ماسكة موبايلي', isCorrect: false, rationale: '❌ القدوة غلط.'),
        EduOption(text: 'أقوله "خليك جنبي" بس من غير شرح', isCorrect: false, rationale: '❌ محتاج يفهم الخطوات.'),
      ],
    ),
    EduQuestion(
      id: 'q_21',
      question: 'طفلك بياكل حلويات كتير كل يوم. إزاي تنظّمي العادة؟',
      emoji: '🍭',
      category: 'عادات الأكل',
      context: 'التنظيم أفضل من المنع المفاجئ.',
      options: [
        EduOption(text: 'نحدّد كمية ووقت ونوفّر بدائل زي الفاكهة', isCorrect: true, rationale: '✅ الحدود + البدائل بتنظّم العادة.'),
        EduOption(text: 'أمنعها فجأة تمامًا', isCorrect: false, rationale: '❌ المنع الحاد بيزوّد الرغبة.'),
        EduOption(text: 'أسيبه ياكل زي ما هو عايز', isCorrect: false, rationale: '❌ غياب الحدود بيكبّر العادة.'),
        EduOption(text: 'أكافئه بحلوى لو سمع الكلام', isCorrect: false, rationale: '❌ بيعزّز نفس العادة.'),
      ],
    ),
    EduQuestion(
      id: 'q_22',
      question: 'طفلك زعل وبيصرّخ من الغضب. الأنسب؟',
      emoji: '😤',
      category: 'المشاعر',
      context: 'تنظيم الانفعال مهارة بتتعلّم بالهدوء.',
      options: [
        EduOption(text: 'أهدّي نفسي، أسمّي مشاعره، وأعلّمه يتنفّس ويعبّر بالكلام', isCorrect: true, rationale: '✅ التهدئة والتسمية بتنظّموا الانفعال.'),
        EduOption(text: 'أصرّخ عليه عشان يسكت', isCorrect: false, rationale: '❌ بيزوّد التوتر.'),
        EduOption(text: 'أعاقبه على غضبه', isCorrect: false, rationale: '❌ المشاعر مش غلط، التصرّف هو اللي بيتعلّم.'),
        EduOption(text: 'أتجاهله تمامًا', isCorrect: false, rationale: '❌ محتاج احتواء وتوجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_23',
      question: 'طفلك خجول وعايز يكوّن صداقات. إزاي تساعديه؟',
      emoji: '👫',
      category: 'مهارات اجتماعية',
      context: 'المهارات الاجتماعية بتنمو بالتدريب التدريجي.',
      options: [
        EduOption(text: 'نتدرّب على البدء بالسلام والمشاركة في لعب بسيط ونشجّعه', isCorrect: true, rationale: '✅ التدرّب والتشجيع بيبنوا الثقة الاجتماعية.'),
        EduOption(text: 'أجبره يكلّم الكل فجأة', isCorrect: false, rationale: '❌ الضغط بيزوّد الخجل.'),
        EduOption(text: 'أقوله "إنت جبان"', isCorrect: false, rationale: '❌ الوصم بيكسر الثقة.'),
        EduOption(text: 'أبعده عن المواقف الاجتماعية', isCorrect: false, rationale: '❌ التجنّب بيكبّر الخجل.'),
      ],
    ),
    EduQuestion(
      id: 'q_24',
      question: 'عايزة طفلك يعبّر عن مشاعره بالكلام بدل البكاء. الأنسب؟',
      emoji: '🗣️',
      category: 'المشاعر',
      context: 'التعبير اللفظي بيتعلّم بالنمذجة.',
      options: [
        EduOption(text: 'أساعده يسمّي شعوره ("إنت زعلان؟") وأمدح التعبير بالكلام', isCorrect: true, rationale: '✅ تسمية المشاعر بتطوّر التعبير.'),
        EduOption(text: 'أقوله "بطّل عياط"', isCorrect: false, rationale: '❌ كبت المشاعر بيكبّرها.'),
        EduOption(text: 'أتجاهله لحد ما يهدا', isCorrect: false, rationale: '❌ بيفوّت فرصة تعليم.'),
        EduOption(text: 'أديله اللي عايزه عشان يسكت', isCorrect: false, rationale: '❌ بيتعلّم إن البكاء وسيلة.'),
      ],
    ),
        ];
      case 6:
        return const [
    EduQuestion(
      id: 'q_25',
      question: 'عايزة تعلّمي طفلك قيمة الفلوس والادّخار. الأنسب؟',
      emoji: '🐷',
      category: 'مهارات حياتية',
      context: 'إدارة المال مهارة بتتعلّم بالتطبيق.',
      options: [
        EduOption(text: 'حصّالة بسيطة وهدف صغير يدّخر له ونحتفل لما يوصله', isCorrect: true, rationale: '✅ الهدف المحسوس بيعلّم الادّخار.'),
        EduOption(text: 'أديله كل اللي يطلبه فورًا', isCorrect: false, rationale: '❌ مش هيتعلّم قيمة المال.'),
        EduOption(text: 'أمنعه من أي مصروف', isCorrect: false, rationale: '❌ المنع التام بيفوّت التعلّم.'),
        EduOption(text: 'أقوله الفلوس مش من شأنه', isCorrect: false, rationale: '❌ بيفوّت مهارة مهمة.'),
      ],
    ),
    EduQuestion(
      id: 'q_26',
      question: 'طفلك عند صاحبه وفيه أكل مش متعوّد عليه. إزاي تجهّزيه؟',
      emoji: '🍱',
      category: 'مهارات اجتماعية',
      context: 'التصرّف اللائق بره البيت مهارة.',
      options: [
        EduOption(text: 'نتفق إنه يشكر ويجرّب بأدب، أو يعتذر بلطف لو مش عايز', isCorrect: true, rationale: '✅ الذوق والاتفاق المسبق بيسهّلوا الموقف.'),
        EduOption(text: 'يرفض الأكل بصوت عالي', isCorrect: false, rationale: '❌ قلّة ذوق بتحرج.'),
        EduOption(text: 'يعلّق إن الأكل وحش', isCorrect: false, rationale: '❌ بيجرح المضيف.'),
        EduOption(text: 'أمنعه يزور أصحابه', isCorrect: false, rationale: '❌ المنع بيحرمه من مهارة اجتماعية.'),
      ],
    ),
    EduQuestion(
      id: 'q_27',
      question: 'غرفة طفلك دايمًا فوضى. إزاي تبني عادة الترتيب؟',
      emoji: '🧺',
      category: 'المسؤولية',
      context: 'الترتيب بيسهل بنظام بسيط وثابت.',
      options: [
        EduOption(text: 'صناديق واضحة لكل نوع ووقت ترتيب قصير يومي', isCorrect: true, rationale: '✅ النظام البسيط بيسهّل العادة.'),
        EduOption(text: 'أرتّب أنا كل يوم بدله', isCorrect: false, rationale: '❌ مش هياخد المسؤولية.'),
        EduOption(text: 'أرمي ألعابه عشان يتعلّم', isCorrect: false, rationale: '❌ العقاب القاسي بيكسر الثقة.'),
        EduOption(text: 'أسيبها فوضى خالص', isCorrect: false, rationale: '❌ مفيش تعلّم بدون نظام.'),
      ],
    ),
    EduQuestion(
      id: 'q_28',
      question: 'عايزة طفلك يلبس حزام الأمان كل مرة في العربية. الأنسب؟',
      emoji: '🚗',
      category: 'السلامة',
      context: 'عادات السلامة بتتثبّت بالثبات والقدوة.',
      options: [
        EduOption(text: 'قاعدة ثابتة: مفيش تحرّك قبل الحزام، وأنا ألبسه برضه', isCorrect: true, rationale: '✅ الثبات والقدوة بيرسّخوا العادة.'),
        EduOption(text: 'أسيبه من غير حزام لو الرحلة قصيرة', isCorrect: false, rationale: '❌ الثبات هو اللي بيبني العادة.'),
        EduOption(text: 'أزعقه كل مرة بس', isCorrect: false, rationale: '❌ القاعدة الواضحة أفضل من الزعيق.'),
        EduOption(text: 'أنا نفسي مش بلبس الحزام', isCorrect: false, rationale: '❌ القدوة العكسية بتهدم العادة.'),
      ],
    ),
    EduQuestion(
      id: 'q_29',
      question: 'طفلك اختلف مع صاحبه على لعبة. إزاي تعلّميه حل المشكلة؟',
      emoji: '🧩',
      category: 'مهارات اجتماعية',
      context: 'حل المشكلات مهارة بتتعلّم بالتوجيه.',
      options: [
        EduOption(text: 'نهدّي، نسمع الطرفين، ونلاقي حل زي التناوب', isCorrect: true, rationale: '✅ الإنصات والحل الوسط بيعلّموا التفاوض.'),
        EduOption(text: 'آخد جنب طفلي على طول', isCorrect: false, rationale: '❌ بيمنعه من تعلّم العدل.'),
        EduOption(text: 'أمنعهم من اللعب مع بعض', isCorrect: false, rationale: '❌ التجنّب مش حل.'),
        EduOption(text: 'أقوله خد اللي إنت عايزه', isCorrect: false, rationale: '❌ بيرسّخ الأنانية.'),
      ],
    ),
        ];
      case 7:
        return const [
    EduQuestion(
      id: 'q_30',
      question: 'إيه دور النوم الكافي في يوم طفلك؟',
      emoji: '😴',
      category: 'الروتين',
      context: 'النوم الكافي بيحسّن المزاج والتركيز.',
      options: [
        EduOption(text: 'بيحسّن مزاجه وتركيزه وطاقته للتعلّم واللعب', isCorrect: true, rationale: '✅ النوم الكافي أساس ليوم جيد.'),
        EduOption(text: 'بس عشان يرتاح شوية', isCorrect: false, rationale: '❌ دوره أكبر من الراحة.'),
        EduOption(text: 'مش مهم لو بياكل كويس', isCorrect: false, rationale: '❌ النوم والتغذية مكمّلين.'),
        EduOption(text: 'بيخلّيه كسلان', isCorrect: false, rationale: '❌ النوم الكافي بيزوّد نشاطه.'),
      ],
    ),
    EduQuestion(
      id: 'q_31',
      question: 'طفلك بيشرب عصائر معلّبة كل يوم. الأنسب؟',
      emoji: '🧃',
      category: 'عادات الأكل',
      context: 'الماء والفاكهة الطازجة أفضل اختيار يومي.',
      options: [
        EduOption(text: 'نقلّلها تدريجيًا ونوفّر ماء وفاكهة طازجة', isCorrect: true, rationale: '✅ التدرّج والبدائل بيغيّروا العادة.'),
        EduOption(text: 'عادي عشان فيها سكر بيدّي طاقة', isCorrect: false, rationale: '❌ السكر الزائد بيعمل تقلّب طاقة.'),
        EduOption(text: 'أحسن من الماء', isCorrect: false, rationale: '❌ الماء هو الأفضل للترطيب.'),
        EduOption(text: 'أمنعها فجأة تمامًا', isCorrect: false, rationale: '❌ المنع الحاد صعب يستمر.'),
      ],
    ),
    EduQuestion(
      id: 'q_32',
      question: 'طفلك غلط في حاجة. إزاي تعلّميه يتحمّل مسؤولية خطأه؟',
      emoji: '🙋',
      category: 'الأخلاق',
      context: 'تحمّل المسؤولية بينمو في جو آمن.',
      options: [
        EduOption(text: 'نتكلّم بهدوء عن الخطأ وإزاي نصلّحه من غير إهانة', isCorrect: true, rationale: '✅ التركيز على الحل بيعلّم المسؤولية.'),
        EduOption(text: 'أعاقبه بشدة فورًا', isCorrect: false, rationale: '❌ الخوف بيعلّم الإخفاء.'),
        EduOption(text: 'أتجاهل الخطأ', isCorrect: false, rationale: '❌ بيفوّت فرصة تعلّم.'),
        EduOption(text: 'أعايره بالخطأ بعدين', isCorrect: false, rationale: '❌ التعيير بيكسر الثقة.'),
      ],
    ),
    EduQuestion(
      id: 'q_33',
      question: 'عايزة طفلك ينظّم وقت المذاكرة واللعب. الأنسب؟',
      emoji: '⏱️',
      category: 'مهارات',
      context: 'تنظيم الوقت مهارة بتتعلّم بجدول بسيط.',
      options: [
        EduOption(text: 'جدول بسيط بفترات مذاكرة قصيرة وراحات ولعب', isCorrect: true, rationale: '✅ التنظيم والراحات بيحسّنوا التركيز.'),
        EduOption(text: 'يذاكر ساعات طويلة بدون راحة', isCorrect: false, rationale: '❌ بيقلّل التركيز.'),
        EduOption(text: 'يلعب الأول ويذاكر آخر الليل', isCorrect: false, rationale: '❌ التعب بيقلّل الاستيعاب.'),
        EduOption(text: 'من غير أي تنظيم', isCorrect: false, rationale: '❌ الفوضى بتصعّب الالتزام.'),
      ],
    ),
    EduQuestion(
      id: 'q_34',
      question: 'عايزة تخلّي البيت آمن ومرتّب لطفلك. الأنسب؟',
      emoji: '🏠',
      category: 'السلامة',
      context: 'البيئة المنظّمة بتقلّل المخاطر.',
      options: [
        EduOption(text: 'نحفظ الأدوات الخطرة بعيد، نرتّب الممرات، ونثبّت الأرفف', isCorrect: true, rationale: '✅ التنظيم والتأمين بيقلّلوا الحوادث.'),
        EduOption(text: 'نسيب كل حاجة في متناول إيده', isCorrect: false, rationale: '❌ بيزوّد خطر الحوادث.'),
        EduOption(text: 'نعتمد إنه ياخد باله لوحده', isCorrect: false, rationale: '❌ الأطفال محتاجين بيئة آمنة.'),
        EduOption(text: 'نمنعه يتحرّك في البيت', isCorrect: false, rationale: '❌ المنع مش بديل عن التأمين.'),
      ],
    ),
        ];
      case 8:
        return const [
    EduQuestion(
      id: 'q_35',
      question: 'عايزة تعلّمي طفلك يبعد عن مصادر الحرارة في المطبخ. الأنسب؟',
      emoji: '🍳',
      category: 'السلامة',
      context: 'الوعي بالخطر مهارة وقائية.',
      options: [
        EduOption(text: 'نشرح الخطر، نبعّد المقابض، ونخلّيه بعيد وقت الطبخ', isCorrect: true, rationale: '✅ الشرح + التأمين بيبنوا وعي السلامة.'),
        EduOption(text: 'نسيبه يلعب جنب البوتاجاز', isCorrect: false, rationale: '❌ خطر مباشر.'),
        EduOption(text: 'نخوّفه بالعقاب بس', isCorrect: false, rationale: '❌ الفهم أفضل من الخوف.'),
        EduOption(text: 'نقوله "ابعد" من غير شرح', isCorrect: false, rationale: '❌ محتاج يفهم السبب.'),
      ],
    ),
    EduQuestion(
      id: 'q_36',
      question: 'طفلك حاسس بعدم ارتياح من موقف أو شخص. إزاي تجهّزيه؟',
      emoji: '🛑',
      category: 'مهارات حياتية',
      context: 'التعبير عن عدم الارتياح مهارة حماية.',
      options: [
        EduOption(text: 'أعلّمه يقول "لأ"، ييجي لي، ويحكي من غير خوف', isCorrect: true, rationale: '✅ الأمان في الحكي بيحميه.'),
        EduOption(text: 'أقوله ما تتكلّمش في الكلام ده', isCorrect: false, rationale: '❌ بيخلّيه يكتم.'),
        EduOption(text: 'أتجاهل لو حكى', isCorrect: false, rationale: '❌ بيفقد الثقة في الحكي.'),
        EduOption(text: 'أزعقه عشان "بيتنطط"', isCorrect: false, rationale: '❌ بيمنعه يعبّر تاني.'),
      ],
    ),
    EduQuestion(
      id: 'q_37',
      question: 'إزاي تجهّزي لطفلك وجبة مدرسة متوازنة؟',
      emoji: '🥪',
      category: 'عادات الأكل',
      context: 'التنوّع والتوازن بيدّوا طاقة لليوم.',
      options: [
        EduOption(text: 'فاكهة وخضار وجبن ومكسّرات بكميات مناسبة', isCorrect: true, rationale: '✅ التنوّع والتوازن أفضل.'),
        EduOption(text: 'شيبسي وحلويات عشان يفرح', isCorrect: false, rationale: '❌ سكريات ودهون كتير.'),
        EduOption(text: 'مشروبات غازية للطاقة', isCorrect: false, rationale: '❌ بتعمل تقلّب طاقة.'),
        EduOption(text: 'نوع واحد بس كل يوم', isCorrect: false, rationale: '❌ التنويع أفضل للتقبّل والتوازن.'),
      ],
    ),
    EduQuestion(
      id: 'q_38',
      question: 'لقيتي طفلك بيخبط على نملة أو حشرة وهو بيلعب. إزاي توجّهيه؟',
      emoji: '🐞',
      category: 'الأخلاق',
      context: 'الرفق بالكائنات قيمة تربوية.',
      options: [
        EduOption(text: 'أعلّمه الرفق وإننا منؤذيش الكائنات ونبعد عنها بهدوء', isCorrect: true, rationale: '✅ الرفق قيمة بتتعلّم بالتوجيه.'),
        EduOption(text: 'أسيبه يلعب بأي طريقة', isCorrect: false, rationale: '❌ بيفوّت تعليم الرفق.'),
        EduOption(text: 'أخوّفه من كل الحشرات', isCorrect: false, rationale: '❌ الخوف الزائد مش الهدف.'),
        EduOption(text: 'أزعقه بشدة', isCorrect: false, rationale: '❌ التوجيه الهادئ أفضل.'),
      ],
    ),
    EduQuestion(
      id: 'q_39',
      question: 'طفلك بيقعد قريب جدًا من الشاشة لفترات طويلة. الأنسب؟',
      emoji: '📺',
      category: 'وقت الشاشة',
      context: 'عادات استخدام الشاشة بتتنظّم بمسافة ووقت.',
      options: [
        EduOption(text: 'نحدّد مسافة مناسبة ووقت محدد وراحات منتظمة', isCorrect: true, rationale: '✅ الحدود والراحات بتنظّم العادة.'),
        EduOption(text: 'عادي طول ما هو مبسوط', isCorrect: false, rationale: '❌ غياب الحدود بيكبّر العادة.'),
        EduOption(text: 'نطفّي الشاشة فجأة بزعيق', isCorrect: false, rationale: '❌ الانتقال الفجائي بيسبّب صراع.'),
        EduOption(text: 'نسيبه يقرّر المسافة والوقت', isCorrect: false, rationale: '❌ محتاج توجيه.'),
      ],
    ),
        ];
      case 9:
        return const [
    EduQuestion(
      id: 'q_40',
      question: 'عايزة تحسّني عادات أكل طفلك وتخلّيها متوازنة. الأنسب؟',
      emoji: '🍎',
      category: 'عادات الأكل',
      context: 'التوازن والحركة عادات يومية مفيدة.',
      options: [
        EduOption(text: 'نزوّد الفاكهة والخضار والماء ونشجّع الحركة', isCorrect: true, rationale: '✅ التوازن والحركة عادات يومية مفيدة.'),
        EduOption(text: 'نعتمد على الحلويات', isCorrect: false, rationale: '❌ بتفتقر للتوازن.'),
        EduOption(text: 'نقلّل الماء', isCorrect: false, rationale: '❌ الماء جزء أساسي.'),
        EduOption(text: 'نمنع الأكل فترات طويلة', isCorrect: false, rationale: '❌ الانتظام أفضل من الحرمان.'),
      ],
    ),
    EduQuestion(
      id: 'q_41',
      question: 'الجو برد. إزاي تعلّمي طفلك يلبس مناسب للطقس؟',
      emoji: '🧥',
      category: 'مهارات حياتية',
      context: 'اختيار الملبس المناسب مهارة استقلالية.',
      options: [
        EduOption(text: 'نختار مع بعض ملابس دافئة ونشرح ليه، وبعدين يختار بنفسه', isCorrect: true, rationale: '✅ المشاركة بتبني مهارة الاختيار.'),
        EduOption(text: 'يلبس نفس الهدوم في كل جو', isCorrect: false, rationale: '❌ مش مناسب للطقس.'),
        EduOption(text: 'ألبسه أنا بالكامل دايمًا', isCorrect: false, rationale: '❌ بيفوّت تعلّم الاستقلالية.'),
        EduOption(text: 'أسيبه يخرج زي ما هو', isCorrect: false, rationale: '❌ محتاج توجيه لاختيار مناسب.'),
      ],
    ),
    EduQuestion(
      id: 'q_42',
      question: 'طفلك مضايق من حاجة بس مش بيقول. إزاي تساعديه يعبّر؟',
      emoji: '💬',
      category: 'المشاعر',
      context: 'مساحة الحوار الآمنة بتسهّل التعبير.',
      options: [
        EduOption(text: 'أقعد معاه بهدوء، أسأل أسئلة بسيطة، وأطمّنه', isCorrect: true, rationale: '✅ الحوار الآمن بيشجّع التعبير.'),
        EduOption(text: 'أضغط عليه يتكلّم بسرعة', isCorrect: false, rationale: '❌ الضغط بيقفله.'),
        EduOption(text: 'أتجاهله لحد ما يتكلّم', isCorrect: false, rationale: '❌ بيكبّر انغلاقه.'),
        EduOption(text: 'أخمّن وأقرّر بدله', isCorrect: false, rationale: '❌ بيفوّت تعليمه التعبير.'),
      ],
    ),
    EduQuestion(
      id: 'q_43',
      question: 'إزاي تساعدي طفلك يقلّل السكر اليومي؟',
      emoji: '🍬',
      category: 'عادات الأكل',
      context: 'التدرّج والبدائل أنجح من الحظر.',
      options: [
        EduOption(text: 'بدائل طبيعية زي الفاكهة وتقليل العصائر تدريجيًا', isCorrect: true, rationale: '✅ التدرّج والبدائل بيغيّروا العادة.'),
        EduOption(text: 'منعه فجأة من كل حاجة', isCorrect: false, rationale: '❌ صعب يستمر.'),
        EduOption(text: 'بدائل سكرية كتير', isCorrect: false, rationale: '❌ ليها حدود برضه.'),
        EduOption(text: 'يقرّر هو لوحده', isCorrect: false, rationale: '❌ محتاج توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_44',
      question: 'إيه فايدة اللعب في الهواء الطلق لطفلك؟',
      emoji: '🌳',
      category: 'النشاط',
      context: 'الحركة والطبيعة بيحسّنوا الطاقة والمزاج.',
      options: [
        EduOption(text: 'بتدّيه طاقة ومزاج أحسن وفرص يكوّن صداقات', isCorrect: true, rationale: '✅ فوائد متعددة للنمو والمهارات.'),
        EduOption(text: 'بس عشان يتسلّى', isCorrect: false, rationale: '❌ الفايدة أكبر من التسلية.'),
        EduOption(text: 'مش مهم لو فيه ألعاب جوّه', isCorrect: false, rationale: '❌ الهواء الطلق له فوائد خاصة.'),
        EduOption(text: 'بيضيّع وقته', isCorrect: false, rationale: '❌ العكس، بينمّي مهاراته.'),
      ],
    ),
        ];
      case 10:
        return const [
    EduQuestion(
      id: 'q_45',
      question: 'إزاي تبني عادات جيدة مستدامة لطفلك؟',
      emoji: '🌱',
      category: 'العادات',
      context: 'العادات بتتكوّن بالتكرار والقدوة.',
      options: [
        EduOption(text: 'أكون قدوة، نحدّد روتين، ونحتفل بالنجاحات الصغيرة', isCorrect: true, rationale: '✅ القدوة والروتين أساس العادات.'),
        EduOption(text: 'أجبره على كل حاجة', isCorrect: false, rationale: '❌ القوة بتولّد رفض.'),
        EduOption(text: 'أبعده عن كل حاجة فجأة', isCorrect: false, rationale: '❌ التدرّج أفضل.'),
        EduOption(text: 'أسيبه يتعلّم من أصحابه بس', isCorrect: false, rationale: '❌ البيت المصدر الأساسي.'),
      ],
    ),
    EduQuestion(
      id: 'q_46',
      question: 'طفلك عنده سلوك متكرّر بيضايقه أو بيضرّه. الأنسب؟',
      emoji: '🔄',
      category: 'السلوك',
      context: 'بعض السلوكيات تحتاج رأي متخصّص تربوي.',
      options: [
        EduOption(text: 'أسجّل السلوك وأستشير أخصائي تربوي مختص', isCorrect: true, rationale: '✅ الاستشارة المتخصصة أفضل خطوة.'),
        EduOption(text: 'أعاقبه عشان يبطّل', isCorrect: false, rationale: '❌ العقاب ممكن يزوّد السلوك.'),
        EduOption(text: 'أتجاهله تمامًا', isCorrect: false, rationale: '❌ السلوك المؤذي يحتاج تقييم.'),
        EduOption(text: 'أعتمد على فيديوهات يوتيوب بس', isCorrect: false, rationale: '❌ مش بديل عن مختص.'),
      ],
    ),
    EduQuestion(
      id: 'q_47',
      question: 'طفلك بيتضايق بسرعة وبيفقد أعصابه. إزاي تعلّميه ضبط النفس؟',
      emoji: '🌬️',
      category: 'المشاعر',
      context: 'ضبط الانفعال بيتعلّم بأدوات بسيطة.',
      options: [
        EduOption(text: 'نتدرّب على التنفّس العميق والعدّ والكلام عن الشعور', isCorrect: true, rationale: '✅ أدوات التهدئة بتبني ضبط النفس.'),
        EduOption(text: 'أصرّخ عليه يهدا', isCorrect: false, rationale: '❌ بيزوّد التوتر.'),
        EduOption(text: 'أعاقبه على انفعاله', isCorrect: false, rationale: '❌ المشاعر مش غلط.'),
        EduOption(text: 'أديله اللي عايزه عشان يهدا', isCorrect: false, rationale: '❌ بيرسّخ نفس التصرّف.'),
      ],
    ),
    EduQuestion(
      id: 'q_48',
      question: 'إزاي تساعدي طفلك يختار أصدقاء وقدوات كويسة؟',
      emoji: '🌟',
      category: 'مهارات اجتماعية',
      context: 'اختيار الرفقة مهارة بتأثّر على القيم.',
      options: [
        EduOption(text: 'نتكلّم عن صفات الصديق الجيد ونشجّع العلاقات الإيجابية', isCorrect: true, rationale: '✅ الحوار بيطوّر معايير اختيار الرفقة.'),
        EduOption(text: 'نسيبه يصاحب أي حد', isCorrect: false, rationale: '❌ الرفقة بتأثّر على القيم.'),
        EduOption(text: 'نمنعه من كل الأصدقاء', isCorrect: false, rationale: '❌ العزلة مش حل.'),
        EduOption(text: 'نختار له أصحابه بالكامل', isCorrect: false, rationale: '❌ محتاج يتعلّم يختار.'),
      ],
    ),
    EduQuestion(
      id: 'q_49',
      question: 'إيه أهمية مشاعر الطفل وثقته بنفسه جنب مهاراته؟',
      emoji: '💛',
      category: 'المشاعر',
      context: 'المشاعر المتّزنة بتساعد التعلّم والعلاقات.',
      options: [
        EduOption(text: 'الطفل المطمئن بيتعلّم ويتعامل وينمو بشكل أفضل', isCorrect: true, rationale: '✅ المشاعر والمهارات مرتبطين.'),
        EduOption(text: 'مش مهمة قد المهارات', isCorrect: false, rationale: '❌ المشاعر أساس مهم.'),
        EduOption(text: 'بس للأطفال الكبار', isCorrect: false, rationale: '❌ كل الأعمار محتاجة.'),
        EduOption(text: 'بتتحسّن لوحدها', isCorrect: false, rationale: '❌ محتاجة اهتمام وتوجيه.'),
      ],
    ),
        ];
      default:
        return _buildQuestions(1);
    }
  }
}
