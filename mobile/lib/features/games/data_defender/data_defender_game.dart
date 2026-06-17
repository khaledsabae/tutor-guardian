/// Redesigned Data Defender educational mini-game.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Data Defender game.
class DataDefenderGame extends EduGameShell {
  const DataDefenderGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'data_defender',
            name: 'حارس البيانات',
            heroEmoji: '🛡️',
            description: 'تعلّم أمانك وخصوصيتك العائلية من الفيروسات والاحتيال',
            backgroundColor: Color(0xFF0B1120),
            surfaceColor: Color(0xFF1E293B),
            accentColor: Color(0xFF06B6D4),
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
      question: 'طفلك بعتلك لينك غريب على واتساب وقال \'افتحه بسرعة\'. إيه اللي تعمليه؟',
      emoji: '🔗',
      category: 'الأمان الرقمي',
      context: 'الروابط المشبوهة ممكن تسرق بياناتك أو تخترق جهازك.',
      options: [
        EduOption(text: 'مش بفتحه غير لما اتأكد إنه من مصدر موثوق', isCorrect: true, rationale: '✅ التأكد قبل الفتح بيحمي بياناتك وجهازك.'),
        EduOption(text: 'بفتحه فوراً عشان ابني قاللي', isCorrect: false, rationale: '❌ حتى حسابات الأهل ممكن تتاخترق. اسأل طفلك قبل ما تفتح.'),
        EduOption(text: 'ببعته لكل الناس عشان نشوف إيه فيه', isCorrect: false, rationale: '❌ نشر الرابط المشبوه بيضر غيرك كمان.'),
        EduOption(text: 'بحط فيه بياناتي عشان أشوف المحتوى', isCorrect: false, rationale: '❌ أي موقع بيطلب بيانات شخصية بدون سبب ممكن يكون مخادع.'),
      ],
    ),
    EduQuestion(
      id: 'q_1',
      question: 'إزاي تعرفي إن التطبيق الجديد اللي هتنزّليه آمن؟',
      emoji: '📱',
      category: 'الأمان الرقمي',
      context: 'بعض التطبيقات بتسرق بياناتك أو بتسبب مشاكل للجهاز.',
      options: [
        EduOption(text: 'بنزّله من المتجر الرسمي وبقرأ التقييمات', isCorrect: true, rationale: '✅ المتجر الرسمي + التقييمات بتقلل المخاطر.'),
        EduOption(text: 'بنزّله من أي موقع على الإنترنت', isCorrect: false, rationale: '❌ ملفات APK من مواقع عشوائية ممكن تحتوي فيروسات.'),
        EduOption(text: 'بده كل الصلاحيات اللي يطلبها', isCorrect: false, rationale: '❌ لازم ترفضي الصلاحيات غير المبررة زي الوصول للكاميرا أو جهات الاتصال.'),
        EduOption(text: 'بنزّله عشان صحابي قالولي', isCorrect: false, rationale: '❌ توصية الصحاب مش دليل أمان.'),
      ],
    ),
    EduQuestion(
      id: 'q_2',
      question: 'طلب منك موقع على الإنترنت إنك تسجّلي باسمك الكامل ورقم التليفون والعنوان. إيه ردّك؟',
      emoji: '🛡️',
      category: 'حماية البيانات',
      context: 'البيانات الشخصية ثمينة ومفروض ما نسيبهاش في أي مكان.',
      options: [
        EduOption(text: 'بسأل: هل الموقع موثوق وهل محتاج كل البيانات دي؟', isCorrect: true, rationale: '✅ التفكير قبل المشاركة بيحمي خصوصيتك.'),
        EduOption(text: 'بسجّل كل البيانات عشان أخلص بسرعة', isCorrect: false, rationale: '❌ المعلومات الزيادة ممكن تتسرب أو تتباع.'),
        EduOption(text: 'بسجّل بيانات غلط عشان أهزر', isCorrect: false, rationale: '❌ البيانات الغلط مش حل؛ الأفضل إنك تسأل وتقرر بوعي.'),
        EduOption(text: 'بشيل كل الحسابات بتاعتي من الجهاز', isCorrect: false, rationale: '❌ مش كل موقع خطر، بس لازم الحذر.'),
      ],
    ),
    EduQuestion(
      id: 'q_3',
      question: 'اتصل بيك شخص زاعم إنه من البنك وطلب رقم الكارت والرقم السري. إيه تصرفك؟',
      emoji: '🏦',
      category: 'الاحتيال الإلكتروني',
      context: 'البنوك الحقيقية مش بتطلب الرقم السري أبداً.',
      options: [
        EduOption(text: 'مش بديه أي بيانات وأتصل بالبنك من الرقم الرسمي', isCorrect: true, rationale: '✅ التحقق من المصدر الرسمي هو أمانك.'),
        EduOption(text: 'بديه الرقم السري عشان يحلولي المشكلة', isCorrect: false, rationale: '❌ أي طلب للرقم السري = احتيال تقريباً.'),
        EduOption(text: 'بسجّل البيانات عشان ما يقفلش الحساب', isCorrect: false, rationale: '❌ التهديد بقفل الحساب غالباً يكون خدعة.'),
        EduOption(text: 'بطلب منه إنه يبعتلي صورة بطاقته', isCorrect: false, rationale: '❌ الصور ممكن تكون مزورة بسهولة.'),
      ],
    ),
    EduQuestion(
      id: 'q_4',
      question: 'اكتشفت إن صورة شخصية لطفلك اتنشرت على صفحة عامة. إيه أول حاجة تعمليها؟',
      emoji: '🖼️',
      category: 'خصوصية الأسرة',
      context: 'صور الأطفال محتاجة حماية خاصة على الإنترنت.',
      options: [
        EduOption(text: 'بتبلّغي عن الصورة وبتطلبي إزالتها فوراً', isCorrect: true, rationale: '✅ التبليغ السريع بيساعد في إزالة المحتوى المضر.'),
        EduOption(text: 'بعمل like على الصورة عشان ما تزعلش', isCorrect: false, rationale: '❌ تفاعلك ممكن يساعد في انتشارها.'),
        EduOption(text: 'بعمل share عشان الناس تعرف', isCorrect: false, rationale: '❌ نشر الصورة أكتر بيضر الطفل.'),
        EduOption(text: 'بسكت وما بعملش حاجة', isCorrect: false, rationale: '❌ الصمت مش حل؛ خصوصية الطفل حق.'),
      ],
    ),
        ];
      case 2:
        return const [
    EduQuestion(
      id: 'q_5',
      question: 'جهازك بقى بطيء وفيه رسايل غريبة بتظهر. ده معناه إيه؟',
      emoji: '🦠',
      category: 'الفيروسات',
      context: 'الأعراض دي ممكن تكون علامة على وجود فيروس.',
      options: [
        EduOption(text: 'ممكن يكون فيروس — هعمل فحص أمان فوراً', isCorrect: true, rationale: '✅ الفحص المنتظم بيساعد في اكتشاف المشاكل بدري.'),
        EduOption(text: 'هكمل استخدام الجهاز عادي', isCorrect: false, rationale: '❌ تجاهل الأعراض ممكن يسمح للفيروس يسرق بياناتك.'),
        EduOption(text: 'هشيل البطارية وهارجعها تاني', isCorrect: false, rationale: '❌ دي حاجة مؤقتة ومش حل لمشكلة برمجية.'),
        EduOption(text: 'هنزل أي برنامج من الإنترنت عشان يسرعه', isCorrect: false, rationale: '❌ برامج عشوائية ممكن تزود المشكلة.'),
      ],
    ),
    EduQuestion(
      id: 'q_6',
      question: 'إيه الفرق بين كلمة سر قوية وكلمة سر ضعيفة؟',
      emoji: '🔑',
      category: 'كلمات السر',
      context: 'كلمات السر الضعيفة بتسهل على المخترقين دخول حساباتك.',
      options: [
        EduOption(text: 'القوية بتجمع أحرف، أرقام، ورموز وما بتكونش اسم أو تاريخ ميلاد', isCorrect: true, rationale: '✅ التنوع والطول بيصعّبوا التخمين.'),
        EduOption(text: 'كلمة زي \'123456\' كويسة لو سهلة للحفظ', isCorrect: false, rationale: '❌ كلمات السر الشائعة بتتكسر في ثواني.'),
        EduOption(text: 'كلمة السر مفروض تكون نفسها لكل الحسابات', isCorrect: false, rationale: '❌ لو اتكسر حساب واحد، كل حساباتك بتتعرض.'),
        EduOption(text: 'مش مهم كلمة السر طالما ما بنزلش تطبيقات', isCorrect: false, rationale: '❌ كلمة السر مهمة حتى في التصفح العادي.'),
      ],
    ),
    EduQuestion(
      id: 'q_7',
      question: 'Wi-Fi عام في مقهى أو مطار — إيه الحاجات اللي متعملهاش عليه؟',
      emoji: '📶',
      category: 'الشبكات',
      context: 'الشبكات العامة ممكن تكون غير آمنة.',
      options: [
        EduOption(text: 'مش بعمل معاملات بنكية أو بدخل بيانات حساسة', isCorrect: true, rationale: '✅ البيانات الحساسة تستنى شبكة موثوقة.'),
        EduOption(text: 'بعمل كل حاجة زي أي شبكة عادية', isCorrect: false, rationale: '❌ الشبكات العامة سهلة التجسس عليها.'),
        EduOption(text: 'بنزل تطبيقات من الموقع الرسمي للمقهى', isCorrect: false, rationale: '❌ أي QR code أو لينك في مكان عام ممكن يكون مزيف.'),
        EduOption(text: 'بسيب الجهاز مفتوح على الطاولة', isCorrect: false, rationale: '❌ السرقة الفعلية للجهاز خطر كبير كمان.'),
      ],
    ),
    EduQuestion(
      id: 'q_8',
      question: 'طفلك عايز يعمل live أو ينشر فيديو لنفسه على منصة عامة. إيه موقفك؟',
      emoji: '📹',
      category: 'خصوصية الأطفال',
      context: 'المحتوى العام بيفضل موجود وممكن يوصل لناس مش محترمة.',
      options: [
        EduOption(text: 'بناقش معاه الخطر ونخلي المحتوى خاص أو محدود', isCorrect: true, rationale: '✅ الحوار والحدود بتحمي الطفل على المدى الطويل.'),
        EduOption(text: 'يسيبه ينشر اللي هو عايزه', isCorrect: false, rationale: '❌ الأطفال مش واعيين بالمخاطر.'),
        EduOption(text: 'بمنعه من استخدام الإنترنت نهائياً', isCorrect: false, rationale: '❌ المنع التام مش واقعي؛ التوجيه أفضل.'),
        EduOption(text: 'بسيبه بس بتابع من بعيد', isCorrect: false, rationale: '❌ المتابعة من بعيد مش كفاية لحمايته.'),
      ],
    ),
    EduQuestion(
      id: 'q_9',
      question: 'بريدك الإلكتروني وصلك إيميل بيقول \'فزت بجائزة\' ومحتاج تدخل بياناتك. إيه تصرفك؟',
      emoji: '📧',
      category: 'الاحتيال الإلكتروني',
      context: 'رسائل الفوز الوهمي من أكتر أنواع الاحتيال انتشاراً.',
      options: [
        EduOption(text: 'بشك في الإيميل ومش بدخل أي بيانات', isCorrect: true, rationale: '✅ الشك أول خطوة للأمان.'),
        EduOption(text: 'بدخل البيانات عشان ممكن فعلاً أكسب', isCorrect: false, rationale: '❌ الجوائز الحقيقية مش بتطلب بيانات حساسة عبر إيميل.'),
        EduOption(text: 'برد على الإيميل بسؤال', isCorrect: false, rationale: '❌ الرد ممكن يؤكد للمحتال إن الإيميل فعّال.'),
        EduOption(text: 'بنشر الخبر مع العيلة', isCorrect: false, rationale: '❌ نشر المحتوى المشبوه بيضر غيرك.'),
      ],
    ),
        ];
      case 3:
        return const [
    EduQuestion(
      id: 'q_10',
      question: 'إيه معنى \'تحديث البرنامج\' وليه مهم؟',
      emoji: '🔄',
      category: 'التحديثات',
      context: 'التحديثات مش مجرد مزايا جديدة، غالباً بتصلح ثغرات أمان.',
      options: [
        EduOption(text: 'بتصلح مشاكل أمان وبتزود حماية الجهاز', isCorrect: true, rationale: '✅ التحديثات المنتظمة خط دفاع أساسي.'),
        EduOption(text: 'بس بتغيّر الشكل ومش مهمة', isCorrect: false, rationale: '❌ الأمان هو السبب الرئيسي في كثير من التحديثات.'),
        EduOption(text: 'بتبطّئ الجهاز فمش بنعملها', isCorrect: false, rationale: '❌ التهرب من التحديث بيخلي الجهاز عرضة للاختراق.'),
        EduOption(text: 'مفروض نعملها بس لما الجهاز يعلق', isCorrect: false, rationale: '❌ الانتظار لحد ما يحصل مشكلة غالباً بيكون متأخر.'),
      ],
    ),
    EduQuestion(
      id: 'q_11',
      question: 'طلب منك أحد على وسائل التواصل صورة شخصية أو فيديو خاص. إيه ردّك؟',
      emoji: '👤',
      category: 'التفاعل مع الغرباء',
      context: 'الغرباء أونلاين ممكن يكونوا أشخاص غير محترمة.',
      options: [
        EduOption(text: 'مش ببعت أي محتوى خاص لحد مش بعرفه شخصياً', isCorrect: true, rationale: '✅ الحدود الرقمية جزء من الحماية الشخصية.'),
        EduOption(text: 'ببعت عشان هو لطيف', isCorrect: false, rationale: '❌ اللطافة أونلاين مش دليل أمان أو نية حسنة.'),
        EduOption(text: 'ببعت صورة قديمة مش هتفرق', isCorrect: false, rationale: '❌ أي صورة شخصية ممكن تتسخدم بطريقة ضارة.'),
        EduOption(text: 'ببلّغ عنه بس برضه ببعت', isCorrect: false, rationale: '❌ التبليغ لا يعفي من خطر إرسال المحتوى.'),
      ],
    ),
    EduQuestion(
      id: 'q_12',
      question: 'إيه هو \'التصيد الاحتيالي\' (Phishing)؟',
      emoji: '🎣',
      category: 'المصطلحات',
      context: 'فهم المصطلح بيساعدك تتجنب الخدع.',
      options: [
        EduOption(text: 'محاولة خداعك عشان تدخل بياناتك على موقع مزيف', isCorrect: true, rationale: '✅ ده التعريف الصحيح للتصيد الاحتيالي.'),
        EduOption(text: 'نوع من ألعاب الصيد', isCorrect: false, rationale: '❌ التشابه في اللفظ مش المعنى.'),
        EduOption(text: 'برنامج يسرّع الإنترنت', isCorrect: false, rationale: '❌ ده كلام إعلاني مضلل.'),
        EduOption(text: 'طريقة لإصلاح الجهاز', isCorrect: false, rationale: '❌ Phishing مش صيانة، هو احتيال.'),
      ],
    ),
    EduQuestion(
      id: 'q_13',
      question: 'في لعبة أونلاين، شخص طلب من طفلك يقابله بره اللعبة. إيه تصرف الطفل الصح؟',
      emoji: '🎮',
      category: 'الألعاب الأونلاين',
      context: 'الألعاب الأونلاين ممكن تكون بوابة للتواصل غير الآمن.',
      options: [
        EduOption(text: 'يقول \'لا\' ويبلّغك فوراً', isCorrect: true, rationale: '✅ رفض التواصل خارج اللعبة وإخبار الوالدين هو الأمان.'),
        EduOption(text: 'يقابله عشان شكله لطيف', isCorrect: false, rationale: '❌ اللطافة أونلاين ممكن تكون خدعة.'),
        EduOption(text: 'يعطيه حسابه الشخصي', isCorrect: false, rationale: '❌ مشاركة الحسابات بتفتح باب التواصل غير المرغوب.'),
        EduOption(text: 'يسكت وما يقولش لحد', isCorrect: false, rationale: '❌ السكوت بيخلي الطفل عرضة للخطر.'),
      ],
    ),
    EduQuestion(
      id: 'q_14',
      question: 'إزاي تحمي حساباتك من الاختراق بشكل عام؟',
      emoji: '🔐',
      category: 'حماية الحسابات',
      context: 'طبقات الحماية المتعددة أفضل من حماية واحدة.',
      options: [
        EduOption(text: 'كلمة سر قوية + تفعيل التحقق بخطوتين + تحديثات', isCorrect: true, rationale: '✅ الحماية المتعددة بتقلل احتمالية الاختراق جداً.'),
        EduOption(text: 'كلمة سر واحدة قوية بس', isCorrect: false, rationale: '❌ لو حد عرفها، كل حساباتك بتتفتح.'),
        EduOption(text: 'مش بعمل تحديثات عشان الجهاز يفضل سريع', isCorrect: false, rationale: '❌ التحديثات مهمة للأمان.'),
        EduOption(text: 'بسيب الحساب مفتوح عشان ما أنساش', isCorrect: false, rationale: '❌ الحساب المفتوح خطر لو الجهاز اتسرق أو اتستخدم.'),
      ],
    ),
        ];
      case 4:
        return const [
    EduQuestion(
      id: 'q_15',
      question: 'طلب منك موقع تفعيل \'الموقع الجغرافي\' عشان تستخدمه. إيه تصرفك؟',
      emoji: '📍',
      category: 'خصوصية الموقع',
      context: 'بعض التطبيقات بتجمع موقعك بدون حاجة حقيقية.',
      options: [
        EduOption(text: 'بسمح بس لو التطبيق فعلاً محتاجه (زي خرائط)', isCorrect: true, rationale: '✅ مشاركة الموقع لازم تكون مبررة ومحدودة.'),
        EduOption(text: 'بسمح دائماً لكل التطبيقات', isCorrect: false, rationale: '❌ تتبع الموقع المستمر بيعرض تحركاتك للتطبيقات.'),
        EduOption(text: 'بسيبه \'أثناء الاستخدام\' بس', isCorrect: false, rationale: '❌ حتى \'أثناء الاستخدام\' ممكن يكون زيادة على الحاجة.'),
        EduOption(text: 'بقفل الموقع نهائياً على كل حاجة', isCorrect: false, rationale: '❌ بعض التطبيقات محتاجة الموقع عشان تشتغل.'),
      ],
    ),
    EduQuestion(
      id: 'q_16',
      question: 'بنتك سألتك: \'هل في حد كلمك وقالك تبعدي عن بابا وماما؟\' إيه تعملي؟',
      emoji: '💬',
      category: 'الاستغلال الأونلاين',
      context: 'المعتدين أونلاين غالباً بيحاولوا يفصلوا الطفل عن أهله.',
      options: [
        EduOption(text: 'بتكلميها بهدوء وتبلّغي وتوقفي التواصل مع الشخص ده', isCorrect: true, rationale: '✅ الإصغاء والتدخل السريع بيحمي الطفل.'),
        EduOption(text: 'بتقوليلها إنها بتبالغ', isCorrect: false, rationale: '❌ تجاهل إحساس الطفل ممكن يخليه يسكت لاحقاً.'),
        EduOption(text: 'بتشتمي الشخص على طول', isCorrect: false, rationale: '❌ العنف مش حل؛ حماية الطفل وتبليغ الجهة المختصة أفضل.'),
        EduOption(text: 'بتسكتي عشان ما تحرجيهاش', isCorrect: false, rationale: '❌ الصمت بيخلي المعتدي يستمر.'),
      ],
    ),
    EduQuestion(
      id: 'q_17',
      question: 'إيه اللي تعمليه لو حسابك على منصة اجتماعية اتاخترق؟',
      emoji: '🚨',
      category: 'الاختراق',
      context: 'سرعة الرد بتحدد حجم الضرر.',
      options: [
        EduOption(text: 'بغيّر كلمة السر فوراً وبفعل التحقق بخطوتين وببلّغ الأصدقاء', isCorrect: true, rationale: '✅ الخطوات دي بتحدد الضرر وبتوقف الاختراق.'),
        EduOption(text: 'بعمل حساب جديد وبسيب القديم', isCorrect: false, rationale: '❌ الحساب القديم ممكن يضلّ يضر غيرك.'),
        EduOption(text: 'بنتظر شوية عشان أشوف ممكن يرجع لوحده', isCorrect: false, rationale: '❌ الانتظار بيدي وقت للمخترق يعمل ضرر أكتر.'),
        EduOption(text: 'بدي نفس كلمة السر للحساب الجديد', isCorrect: false, rationale: '❌ لو كلمة السر اتكسر مرة، مش آمنة تاني.'),
      ],
    ),
    EduQuestion(
      id: 'q_18',
      question: 'إزاي تفرّقي بين تطبيق أصلي وتطبيق مزيف؟',
      emoji: '🎭',
      category: 'التطبيقات',
      context: 'تطبيقات مزيفة بتتنكر لتطبيقات مشهورة.',
      options: [
        EduOption(text: 'من اسم المطوّر، عدد التحميلات، التقييمات، والأذونات', isCorrect: true, rationale: '✅ التحقق من تفاصيل التطبيق بيساعد تمييز المزيف.'),
        EduOption(text: 'لو الشكل شبه الأصلي يبقى كويس', isCorrect: false, rationale: '❌ الواجهة ممكن تتقلد بسهولة.'),
        EduOption(text: 'بنزّله لو رخيص أو مجاني', isCorrect: false, rationale: '❌ السعر المنخفض ممكن يكون فخ.'),
        EduOption(text: 'بسأل أي حد على الإنترنت', isCorrect: false, rationale: '❌ التحقق من مصادر موثوقة أهم.'),
      ],
    ),
    EduQuestion(
      id: 'q_19',
      question: 'طفلك حمل لعبة طلبت منه الوصول للكاميرا والميكروفون. إيه تصرفك؟',
      emoji: '🎰',
      category: 'أذونات التطبيقات',
      context: 'بعض الألعاب بتجمع بيانات أكتر من اللازم.',
      options: [
        EduOption(text: 'بسأل: اللعبة محتاجة الكاميرا فعلاً؟ لو لا برفض', isCorrect: true, rationale: '✅ منح الأذونات يكون مبرر فقط.'),
        EduOption(text: 'بسيب كل الأذونات عشان يلعب', isCorrect: false, rationale: '❌ الأذونات غير المبررة بتعرض خصوصيتك.'),
        EduOption(text: 'بشيل اللعبة كلها من غير ما أقول له', isCorrect: false, rationale: '❌ من الأفضل شرح السبب للطفل.'),
        EduOption(text: 'بحظره من اللعب نهائياً', isCorrect: false, rationale: '❌ الحظر التام مش هيعلّمه حدود الأمان.'),
      ],
    ),
        ];
      case 5:
        return const [
    EduQuestion(
      id: 'q_20',
      question: 'إيه أهمية النسخ الاحتياطي (Backup) للبيانات؟',
      emoji: '💾',
      category: 'النسخ الاحتياطي',
      context: 'الأجهزة ممكن تتسرق أو تتعطل أو تتاخترق.',
      options: [
        EduOption(text: 'بيحمي الصور والملفات المهمة لو حصل أي ضرر للجهاز', isCorrect: true, rationale: '✅ النسخ الاحتياطي بيضمن إنك ما تفقدش الذكريات والملفات.'),
        EduOption(text: 'بيبطّئ الجهاز فمش مهم', isCorrect: false, rationale: '❌ الفقدان أسوأ من أي تأثير طفيف على السرعة.'),
        EduOption(text: 'مفروض نعمله مرة واحدة بس', isCorrect: false, rationale: '❌ النسخ المستمر بيضمن أحدث البيانات محفوظة.'),
        EduOption(text: 'بس للتطبيقات المهمة زي البنك', isCorrect: false, rationale: '❌ الصور والفيديوهات الشخصية مهمة كمان.'),
      ],
    ),
    EduQuestion(
      id: 'q_21',
      question: 'لقيت تعليق سلبي وعنيف على صورة طفلك. إيه ردّك الأول؟',
      emoji: '💔',
      category: 'التنمر الأونلاين',
      context: 'التعليقات السلبية بتأثر نفسية الطفل.',
      options: [
        EduOption(text: 'بعمل report للتعليق وب comforting الطفل', isCorrect: true, rationale: '✅ التبليغ + دعم الطفل أولوية.'),
        EduOption(text: 'برد على الشخص بنفس الأسلوب', isCorrect: false, rationale: '❌ الرد بالعنف ممكن يزود المشكلة.'),
        EduOption(text: 'بسيب التعليق عشان الناس تحترم', isCorrect: false, rationale: '❌ تجاهل التنمر بيسمح له يستمر.'),
        EduOption(text: 'بزعق لطفلي عشان ينزل صور تاني', isCorrect: false, rationale: '❌ الزعل من الطفل غلط؛ المذنب هو المتنمر.'),
      ],
    ),
    EduQuestion(
      id: 'q_22',
      question: 'إيه اللي تعمليه لو جهاز طفلك اتسرق؟',
      emoji: '📱',
      category: 'فقدان الأجهزة',
      context: 'سرقة الجهاز بتعرض البيانات والحسابات.',
      options: [
        EduOption(text: 'بغيّر كلمات السر وبتتبّع الجهاز لو متاح وبتبلّغ', isCorrect: true, rationale: '✅ تغيير الباسوردات بيحمي الحسابات حتى لو الجهاز راح.'),
        EduOption(text: 'بستنى يمكن يرجع', isCorrect: false, rationale: '❌ الانتظار بيدي وقت للي سرقه يفتح حساباتك.'),
        EduOption(text: 'بشتري جهاز جديد وبسيب كل حاجة زي ما هي', isCorrect: false, rationale: '❌ كلمات السر القديمة ممكن تتاخترق.'),
        EduOption(text: 'بسيب الطفل يتصرف', isCorrect: false, rationale: '❌ الطفل مش قادر يتعامل مع التداعيات الأمنية.'),
      ],
    ),
    EduQuestion(
      id: 'q_23',
      question: 'إزاي تعلمي طفلك يتعامل مع المحتوى المزعج اللي بيشوفه أونلاين؟',
      emoji: '🚸',
      category: 'تربية رقمية',
      context: 'الأطفال هيشوفوا حاجات غير مناسبة، والتوجيه مهم.',
      options: [
        EduOption(text: 'بعلمه يقفل ويجيلي ونتحدث عما شافه', isCorrect: true, rationale: '✅ الحوار المفتوح بيبني وعي الأمان.'),
        EduOption(text: 'بمنعه من كل الأجهزة', isCorrect: false, rationale: '❌ المنع التام مش واقعي.'),
        EduOption(text: 'بقول له ما يقولش لحد', isCorrect: false, rationale: '❌ الطفل لازم يعرف إنك مكان آمن للحديث.'),
        EduOption(text: 'بسيبه يتعامل لوحده', isCorrect: false, rationale: '❌ الأطفال محتاجين توجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_24',
      question: 'إيه اللي تتجنبي نشره على وسائل التواصل عن طفلك؟',
      emoji: '🤐',
      category: 'خصوصية الأطفال',
      context: 'بعض البيانات ممكن تستخدم ضد الطفل لاحقاً.',
      options: [
        EduOption(text: 'مكان المدرسة، تفاصيل يومية، صور العري، ومعلومات حساسة', isCorrect: true, rationale: '✅ كل ما قلّت البيانات المنشورة كل ما زاد الأمان.'),
        EduOption(text: 'كل حاجة عادي، ده ابني', isCorrect: false, rationale: '❌ الإفراط في النشر بيعرض الطفل لمخاطر مستقبلية.'),
        EduOption(text: 'بس الصور الحلوة', isCorrect: false, rationale: '❌ حتى الصور العادية ممكن تتسخدم بشكل ضار.'),
        EduOption(text: 'الاحتفال بإنجازاته مع الناس كلها', isCorrect: false, rationale: '❌ ممكن نشارك الفرحة بس بحدود وحذر.'),
      ],
    ),
        ];
      case 6:
        return const [
    EduQuestion(
      id: 'q_25',
      question: 'طفلك سألك: \'إيه الـ VPN؟\' الإجابة الصحيحة هي:',
      emoji: '🌐',
      category: 'الشبكات',
      context: 'VPN بيعمل اتصال أكتر أمان، بس مش كل VPN موثوق.',
      options: [
        EduOption(text: 'أداة بتشفّر اتصالك على الإنترنت وتخفي موقعك', isCorrect: true, rationale: '✅ ده تعريف VPN الأساسي.'),
        EduOption(text: 'برنامج يسرّع الإنترنت دايماً', isCorrect: false, rationale: '❌ مش كل VPN بيسرّع، وبعضه أبطأ.'),
        EduOption(text: 'أداة بتخليك تشوف كل المواقع مجاناً', isCorrect: false, rationale: '❌ ده استخدام غلط وممكن يكون غير قانوني.'),
        EduOption(text: 'جهاز بيوصلك بالقمر الصناعي', isCorrect: false, rationale: '❌ VPN مش قمر صناعي.'),
      ],
    ),
    EduQuestion(
      id: 'q_26',
      question: 'إزاي تحددي وقت شاشة آمن لطفلك؟',
      emoji: '⏱️',
      category: 'الوقت الأمن',
      context: 'الإفراط في الشاشات بيأثر على النوم والعين والتركيز.',
      options: [
        EduOption(text: 'بحدد وقت يومي حسب عمره وبشجع فترات راحة', isCorrect: true, rationale: '✅ الحدود المسبقة بتقلل الصراع وتحمي صحته.'),
        EduOption(text: 'يسيبه يستخدم لحد ما ينام', isCorrect: false, rationale: '❌ الشاشة قبل النوم بتؤثر على جودة النوم.'),
        EduOption(text: 'ما بسيبهوش خالص أول ما ياخد الجهاز', isCorrect: false, rationale: '❌ الحدود ممكن تكون مرنة وواضحة بدل المنع.'),
        EduOption(text: 'بعاقبه بإغلاق الشاشة لما يغلط', isCorrect: false, rationale: '❌ الشاشة مش أداة عقاب.'),
      ],
    ),
    EduQuestion(
      id: 'q_27',
      question: 'إيه أول حاجة تعمليها لو لقيت إن بياناتك الشخصية اتسربت؟',
      emoji: '🔓',
      category: 'التسريبات',
      context: 'التسريبات بتحصل كتير ومحتاجة رد سريع.',
      options: [
        EduOption(text: 'بغيّر كلمات السر وفعل التحقق بخطوتين وراقب الحسابات', isCorrect: true, rationale: '✅ التغيير السريع بيقلل الاستغلال.'),
        EduOption(text: 'بنعمل حساب جديد على كل حاجة', isCorrect: false, rationale: '❌ ده مرهق ومش ضروري في كل الحالات.'),
        EduOption(text: 'بسيب الموضوع عشان الاحتمالات كتير', isCorrect: false, rationale: '❌ التسريب يحتاج إجراءات حماية فعلية.'),
        EduOption(text: 'بشتم الشركة وبس', isCorrect: false, rationale: '❌ الغضب مش حل؛ الحماية هي الحل.'),
      ],
    ),
    EduQuestion(
      id: 'q_28',
      question: 'ليه مهم نعلم الأطفال إنهم ما يشاركوش موقعهم مع أحد أونلاين؟',
      emoji: '🗺️',
      category: 'خصوصية الموقع',
      context: 'الموقع الحقيقي بيكشف مكان الطفل.',
      options: [
        EduOption(text: 'لأن أي حد ممكن يعرف فين ساكن الطفل ويتواصل معاه', isCorrect: true, rationale: '✅ الموقع الحقيقي معلومة خطيرة جداً.'),
        EduOption(text: 'عشان ما يقعدوش كتير على الجهاز', isCorrect: false, rationale: '❌ دي مشكة وقت، مش موقع.'),
        EduOption(text: 'عشان يحفظوا بيانات الجهاز', isCorrect: false, rationale: '❌ الموقع مش بيانات جهاز.'),
        EduOption(text: 'مش مهم لو كان مع أصحابه', isCorrect: false, rationale: '❌ الموقع خطير حتى مع أصحابه.'),
      ],
    ),
    EduQuestion(
      id: 'q_29',
      question: 'إيه هو \'التحقق بخطوتين\' (2FA)؟',
      emoji: '📲',
      category: 'حماية الحسابات',
      context: 'إضافة خطوة تانية بتزود أمان الحساب.',
      options: [
        EduOption(text: 'بيطلب رمز تاني غير كلمة السر عشان تدخل', isCorrect: true, rationale: '✅ 2FA بيضيف طبقة حماية إضافية.'),
        EduOption(text: 'بتخلي كلمة السر بتتغير كل يوم', isCorrect: false, rationale: '❌ 2FA مش تغيير كلمة السر التلقائي.'),
        EduOption(text: 'بتسجّل دخول مرتين', isCorrect: false, rationale: '❌ دي مش الفكرة.'),
        EduOption(text: 'خيار غير متاح', isCorrect: false, rationale: '❌ خيار غير صحيح.'),
      ],
    ),
        ];
      case 7:
        return const [
    EduQuestion(
      id: 'q_30',
      question: 'طفلك بيحمل تطبيق يطلب \'الوصول لجهات الاتصال\'. إيه ردّك المناسب؟',
      emoji: '📇',
      category: 'أذونات التطبيقات',
      context: 'جهات الاتصال فيها بيانات أصدقاء وعيلة كتير.',
      options: [
        EduOption(text: 'برفض لو التطبيق مش محتاجها، وأشوف هل التطبيق موثوق', isCorrect: true, rationale: '✅ الأذونات لازم تكون مبررة.'),
        EduOption(text: 'بسمح عشان التطبيق هيشتغل كويس', isCorrect: false, rationale: '❌ السماح غير المبرر بيجمع بيانات غيرك.'),
        EduOption(text: 'بشيل التطبيق من غير ما أقول له', isCorrect: false, rationale: '❌ التوضيح أهم من الحظر التام.'),
        EduOption(text: 'بحظر طفلي من الجهاز', isCorrect: false, rationale: '❌ الحظر مش حل تربوي.'),
      ],
    ),
    EduQuestion(
      id: 'q_31',
      question: 'إيه اللي تعمليه لو طفلك شاف محتوى عنيف على يوتيوب؟',
      emoji: '🎬',
      category: 'المحتوى',
      context: 'الأطفال ممكن يشوفوا حاجات تفوق سنهم.',
      options: [
        EduOption(text: 'بقفل الفيديو وبتحدثي معاه بهدوء عن اللي شافه', isCorrect: true, rationale: '✅ التواصل والحدود بيساعدوا الطفل يتعامل.'),
        EduOption(text: 'بسيبه يكمل عشان يتعلم الواقع', isCorrect: false, rationale: '❌ المحتوى العنيف ممكن يأثر نفسياً.'),
        EduOption(text: 'بزعقله عشان فتح الفيديو', isCorrect: false, rationale: '❌ الزعل بيبعد الطفل عن الحوار.'),
        EduOption(text: 'بمنعه من يوتيوب نهائياً', isCorrect: false, rationale: '❌ المنع التام مش دايماً واقعي.'),
      ],
    ),
    EduQuestion(
      id: 'q_32',
      question: 'إزاي تفرّقي بين متجر تطبيقات رسمي وآخر مزيف؟',
      emoji: '🏪',
      category: 'المتاجر',
      context: 'المتاجر المزيفة بتنشر تطبيقات خبيثة.',
      options: [
        EduOption(text: 'اسم الشركة، التقييمات، عدد التحميلات، والتحديثات', isCorrect: true, rationale: '✅ التحقق من هوية المطور أهم خطوة.'),
        EduOption(text: 'لو الشكل زي المتجر الأصلي', isCorrect: false, rationale: '❌ الواجهة ممكن تتقلد.'),
        EduOption(text: 'لو فيه ألعاب مجانية كتير', isCorrect: false, rationale: '❌ كثرة المحتوى المجاني ممكن تكون فخ.'),
        EduOption(text: 'لو صحابي قالولي عليه', isCorrect: false, rationale: '❌ التحقق من المصدر الرسمي أهم.'),
      ],
    ),
    EduQuestion(
      id: 'q_33',
      question: 'إيه اللي تعمليه لو جهازك فيه إعلانات بتظهر كل شوية؟',
      emoji: '🛑',
      category: 'البرمجيات الخبيثة',
      context: 'الإعلانات المفاجئة ممكن تكون برمجيات خبيثة أو adware.',
      options: [
        EduOption(text: 'بفحص الجهاز بأداة أمان وبحذف التطبيقات المشبوهة', isCorrect: true, rationale: '✅ الفحص والتنظيف بيساعدوا في إزالة السبب.'),
        EduOption(text: 'بكبس على الإعلان عشان أشوف إيه', isCorrect: false, rationale: '❌ كبس الإعلانات ممكن يثبت برامج ضارة.'),
        EduOption(text: 'بعمل restart للجهاز وبس', isCorrect: false, rationale: '❌ الريستارت مش بيعالج المشكلة الأساسية.'),
        EduOption(text: 'بستنى لحد ما الإعلانات تختفي', isCorrect: false, rationale: '❌ التأخير بيزود الخطر.'),
      ],
    ),
    EduQuestion(
      id: 'q_34',
      question: 'ليه المفروض تفعلي \'إخفاء معاينة الإشعارات\' على قفل الشاشة؟',
      emoji: '🔔',
      category: 'الإشعارات',
      context: 'الإشعارات ممكن تظهر رسايل خاصة لأي حد يمسك جهازك.',
      options: [
        EduOption(text: 'عشان الرسايل الخاصة متبنش لأي حد', isCorrect: true, rationale: '✅ الخصوصية بتبدأ من أصغر الحاجات.'),
        EduOption(text: 'عشان الشاشة تبقى نظيفة', isCorrect: false, rationale: '❌ ده سبب تجميلي مش أمني.'),
        EduOption(text: 'عشان البطارية تفضل أطول', isCorrect: false, rationale: '❌ الفرق في البطارية طفيف جداً.'),
        EduOption(text: 'مش مهم عندي', isCorrect: false, rationale: '❌ كل طبقة حماية بتفرق.'),
      ],
    ),
        ];
      case 8:
        return const [
    EduQuestion(
      id: 'q_35',
      question: 'طفلك استلم رسالة فيها تهديد أو ابتزاز. إيه أول خطوة؟',
      emoji: '⚠️',
      category: 'الابتزاز',
      context: 'الابتزاز الإلكتروني جريمة ومحتاجة تدخل سريع.',
      options: [
        EduOption(text: 'بتبلّغي فوراً وما بتدفعيش وما تتفاوضيش', isCorrect: true, rationale: '✅ التبليغ للجهات الأمنية/الأسرة هو الحل.'),
        EduOption(text: 'بتدفعي عشان يمسح المحتوى', isCorrect: false, rationale: '❌ الدفع بيشجع المبتز على الاستمرار.'),
        EduOption(text: 'بتقولي لطفلك إنه غلطان بس', isCorrect: false, rationale: '❌ إلقاء اللوم على الطفل بيزود الأذى.'),
        EduOption(text: 'بتسكتي عشان ما تحرجوهوش', isCorrect: false, rationale: '❌ الصمت بيدي للمبتز سلطة.'),
      ],
    ),
    EduQuestion(
      id: 'q_36',
      question: 'إيه اللي تعمليه لو سمعتي عن تطبيق بيشتغل في الخلفية ويسرق بيانات؟',
      emoji: '👁️',
      category: 'التطبيقات الخبيثة',
      context: 'بعض التطبيقات بتستغل صلاحياتها.',
      options: [
        EduOption(text: 'بشيل التطبيق فوراً وبعمل فحص أمان', isCorrect: true, rationale: '✅ الإزالة والفحص أول خطوة.'),
        EduOption(text: 'بسيبه عشان مش واثقة', isCorrect: false, rationale: '❌ الشك في التطبيق كافٍ للتصرف.'),
        EduOption(text: 'بعمل له update', isCorrect: false, rationale: '❌ لو التطبيق خبيث، update مش حل.'),
        EduOption(text: 'بستخدمه بس مش بنزل حاجة منه', isCorrect: false, rationale: '❌ التطبيق ممكن يسرق بيانات من غير ما تحمّل.'),
      ],
    ),
    EduQuestion(
      id: 'q_37',
      question: 'إزاي تعلمي طفلك يميّز بين خبر حقيقي وخبر كاذب؟',
      emoji: '📰',
      category: 'الأخبار',
      context: 'المعلومات الغلط منتشرة بكثرة.',
      options: [
        EduOption(text: 'نشوف المصدر، التاريخ، والصورة — ونسأل إذا شككنا', isCorrect: true, rationale: '✅ التحقق من المصادر مهارة رقمية مهمة.'),
        EduOption(text: 'لو صورة حزينة يبقى صح', isCorrect: false, rationale: '❌ الصور ممكن تكون من سياق آخر أو مفبركة.'),
        EduOption(text: 'لو اتنشر كتير يبقى حقيقي', isCorrect: false, rationale: '❌ الانتشار الكثير مش دليل صحة.'),
        EduOption(text: 'نشوف العنوان بس', isCorrect: false, rationale: '❌ العناوين غالباً مضللة.'),
      ],
    ),
    EduQuestion(
      id: 'q_38',
      question: 'إيه أهم حاجة في كلمة السر للحسابات المهمة؟',
      emoji: '🔒',
      category: 'كلمات السر',
      context: 'حسابات زي البريد والبنك تحتاج حماية أقوى.',
      options: [
        EduOption(text: 'أنها تكون طويلة وفريدة ومتكررش في مكان تاني', isCorrect: true, rationale: '✅ الفريدة والطويلة صعبة التخمين.'),
        EduOption(text: 'سهلة الحفظ عشان ما تنساش', isCorrect: false, rationale: '❌ السهلة غالباً بتكون ضعيفة.'),
        EduOption(text: 'نفس كلمة السر لكل الحسابات', isCorrect: false, rationale: '❌ لو اتكسر واحد، كلهم يتكسر.'),
        EduOption(text: 'مكتوبة على ورقة جنب الجهاز', isCorrect: false, rationale: '❌ ده بيخلي أي حد يقدر يدخل.'),
      ],
    ),
    EduQuestion(
      id: 'q_39',
      question: 'ليه مهم نعلم الأطفال إنهم يبلّغوا عن أي تواصل غريب؟',
      emoji: '📣',
      category: 'التواصل',
      context: 'التبليغ المبكر بيمنع التصاعد.',
      options: [
        EduOption(text: 'لأن الصمت بيدي الفرصة للمعتدي، والتبليغ بيوقفه', isCorrect: true, rationale: '✅ التبليغ هو خط الدفاع الأول.'),
        EduOption(text: 'عشان نرقبهم أكتر', isCorrect: false, rationale: '❌ التبليغ مش مراقبة، هو حماية.'),
        EduOption(text: 'مش مهم لو ما حصلش حاجة', isCorrect: false, rationale: '❌ حتى التواصل الغريب يستحق التبليغ.'),
        EduOption(text: 'عشان نخافهم من الإنترنت', isCorrect: false, rationale: '❌ الهدف الوعي مش الخوف.'),
      ],
    ),
        ];
      case 9:
        return const [
    EduQuestion(
      id: 'q_40',
      question: 'طفلك عايز يعمل حساب على منصة جديدة. إيه اللي تعمليه؟',
      emoji: '🆕',
      category: 'المنصات',
      context: 'كل منصة لها قواعد وحد عمر.',
      options: [
        EduOption(text: 'بتشوفي عمر المنصة المسموح، الإعدادات، والخصوصية', isCorrect: true, rationale: '✅ الفحص المسبق بيحمي الطفل.'),
        EduOption(text: 'تسيبه يعمل الحساب بسرعة', isCorrect: false, rationale: '❌ المنصات غير المناسبة للعمر بتعرض الطفل لمحتوى خطير.'),
        EduOption(text: 'بتعملي الحساب باسمك', isCorrect: false, rationale: '❌ ده بيخلي الطفل غير مسؤول عن تصرفاته.'),
        EduOption(text: 'تمنعه نهائياً من كل منصة', isCorrect: false, rationale: '❌ المنع التام مش واقعي.'),
      ],
    ),
    EduQuestion(
      id: 'q_41',
      question: 'إيه اللي تعمليه لو اتنشر عنك كلام غلط على الإنترنت؟',
      emoji: '💭',
      category: 'السمعة الرقمية',
      context: 'الشائعات ممكن تضر السمعة.',
      options: [
        EduOption(text: 'بتجمعي أدلة، بتبلّغي المنصة، وبتسألي قانونياً لو لزم', isCorrect: true, rationale: '✅ التصرف المنظم بيحمي حقك.'),
        EduOption(text: 'بتردي على كل الناس وتشتمي', isCorrect: false, rationale: '❌ الرد بالعنف بيزود المشكلة.'),
        EduOption(text: 'بتسكتي عشان مفيش فايدة', isCorrect: false, rationale: '❌ المنصات عندها أدوات للإبلاغ.'),
        EduOption(text: 'بتنشري كلام غلط عن اللي اتهمك', isCorrect: false, rationale: '❌ الانتقام بيزود المشاكل القانونية.'),
      ],
    ),
    EduQuestion(
      id: 'q_42',
      question: 'إزاي تحمي صورك الشخصية من التزوير بالذكاء الاصطناعي؟',
      emoji: '🤖',
      category: 'التزوير',
      context: 'التزوير العميق (deepfake) منتشر.',
      options: [
        EduOption(text: 'بتقللي الصور العامة، وبتحافظي على الخصوصية، وبتراقبي', isCorrect: true, rationale: '✅ الوقاية أهم من العلاج.'),
        EduOption(text: 'بتنشري كل صورك عشان يعرفوا إنها ليك', isCorrect: false, rationale: '❌ النشر الكثير بيزود الخطر.'),
        EduOption(text: 'مش مهمة لو مش مشهورة', isCorrect: false, rationale: '❌ أي حد ممكن يتعرض للتزوير.'),
        EduOption(text: 'بتستخدمي فلاتر بس', isCorrect: false, rationale: '❌ الفلاتر مش حماية حقيقية.'),
      ],
    ),
    EduQuestion(
      id: 'q_43',
      question: 'إيه اللي تعمليه لو طفلك سألك عن \'الجريمة الإلكترونية\'؟',
      emoji: '👮',
      category: 'التوعية',
      context: 'شرح المفاهيم ببساطة بيبني وعي الأطفال.',
      options: [
        EduOption(text: 'بشرحله إنها أفعال ضارة على الإنترنت وليها عقوبات زي الحقيقة', isCorrect: true, rationale: '✅ التبسيط والربط بالواقع بيساعد الطفل يفهم.'),
        EduOption(text: 'بقول له سيب الموضوع ده للكبار', isCorrect: false, rationale: '❌ الطفل محتاج يفهم حدوده.'),
        EduOption(text: 'بخوفه من الإنترنت', isCorrect: false, rationale: '❌ الخوف مش حل تربوي.'),
        EduOption(text: 'بقول له أي حاجة عشان يسكت', isCorrect: false, rationale: '❌ المعلومات الغلط بتزود الخطر.'),
      ],
    ),
    EduQuestion(
      id: 'q_44',
      question: 'إيه معنى \'تصفح آمن\'؟',
      emoji: '🛡️',
      category: 'المفاهيم',
      context: 'التصفح الآمن مجموعة عادات.',
      options: [
        EduOption(text: 'استخدام مواقع موثوقة، عدم مشاركة بيانات، وتحديث الأمان', isCorrect: true, rationale: '✅ التصفح الآمن هو مجموعة عادات.'),
        EduOption(text: 'استخدام برنامج حماية بس', isCorrect: false, rationale: '❌ البرنامج مش كفاية لوحد.'),
        EduOption(text: 'عدم استخدام الإنترنت', isCorrect: false, rationale: '❌ الإنترنت أداة مهمة، الأمان هو الهدف.'),
        EduOption(text: 'تصفح سريع بدون إعلانات', isCorrect: false, rationale: '❌ السرعة والإعلانات مش مقياس أمان.'),
      ],
    ),
        ];
      case 10:
        return const [
    EduQuestion(
      id: 'q_45',
      question: 'إزاي تبقي عائلتك محمية بشكل شامل أونلاين؟',
      emoji: '👨‍👩‍👧‍👦',
      category: 'الخطة العائلية',
      context: 'الأمان العائلي يحتاج قواعد وتواصل.',
      options: [
        EduOption(text: 'قواعد واضحة، حوار مفتوح، حدود للأجهزة، وفحص دوري', isCorrect: true, rationale: '✅ الحماية الشاملة = تواصل + قواعد + تكنولوجيا.'),
        EduOption(text: 'منع الأطفال من الإنترنت نهائياً', isCorrect: false, rationale: '❌ المنع التام مش واقعي.'),
        EduOption(text: 'شراء أغلى برنامج حماية', isCorrect: false, rationale: '❌ التقنية وحدها مش كافية.'),
        EduOption(text: 'الاعتماد على المدرسة بس', isCorrect: false, rationale: '❌ البيت هو المكان الأساسي للتوجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_46',
      question: 'إيه اللي تعمليه لو شركة اتصلت بيك وقالت إنك فزت وجائزة ومحتاجة بيانات؟',
      emoji: '📞',
      category: 'الاحتيال',
      context: 'الاحتيال التلفوني منتشر.',
      options: [
        EduOption(text: 'بتنهي المكالمة وتتصل بالشركة من الرقم الرسمي', isCorrect: true, rationale: '✅ التحقق من المصدر الرسمي أهم خطوة.'),
        EduOption(text: 'بتدهم البيانات عشان تستلم الجائزة', isCorrect: false, rationale: '❌ الشركات الحقيقية مش بتطلب بيانات حساسة للفوز.'),
        EduOption(text: 'بتسألهم عن تفاصيل الجائزة', isCorrect: false, rationale: '❌ المكالمة نفسها ممكن تكون خدعة.'),
        EduOption(text: 'بتسجل المكالمة وتنشرها', isCorrect: false, rationale: '❌ النشر مش حل؛ التحقق أولاً.'),
      ],
    ),
    EduQuestion(
      id: 'q_47',
      question: 'طفلك بيتعلم برمجة. إزاي تشجعيه بطريقة آمنة؟',
      emoji: '💻',
      category: 'البرمجة',
      context: 'البرمجة مهمة بس فيها أخلاقيات.',
      options: [
        EduOption(text: 'بتعلمه احترام الخصوصية، عدم التطفل، والإبلاغ عن الثغرات', isCorrect: true, rationale: '✅ الأخلاقيات جزء أساسي من التعلم.'),
        EduOption(text: 'بتسيبه يجرب كل حاجة', isCorrect: false, rationale: '❌ التجربة الحرة ممكن تجر لأفعال غير قانونية.'),
        EduOption(text: 'بتقول له يركز على البرمجة بس', isCorrect: false, rationale: '❌ الأمان والأخلاقيات مهمة زي الكود.'),
        EduOption(text: 'بتمنعه من التعلم', isCorrect: false, rationale: '❌ البرمجة مهارة قيمة مع التوجيه.'),
      ],
    ),
    EduQuestion(
      id: 'q_48',
      question: 'إيه أهم درس في الأمان الرقمي تعلمته النهاردة؟',
      emoji: '🧠',
      category: 'المراجعة',
      context: 'التذكر بيساعد التطبيق.',
      options: [
        EduOption(text: 'التحقق والحذر والتبليغ هم أهم 3 عادات', isCorrect: true, rationale: '✅ الملخص الصحيح.'),
        EduOption(text: 'مش استخدم إنترنت أبداً', isCorrect: false, rationale: '❌ الإنترنت مش عدو، الأمان هو المطلوب.'),
        EduOption(text: 'كل الناس على الإنترنت أشرار', isCorrect: false, rationale: '❌ التعميم غلط.'),
        EduOption(text: 'كلمة السر بس هي الحماية', isCorrect: false, rationale: '❌ الحماية مجموعة عادات مش حاجة واحدة.'),
      ],
    ),
    EduQuestion(
      id: 'q_49',
      question: 'إزاي تقيّم مستوى أمان عيلتك؟',
      emoji: '📊',
      category: 'التقييم',
      context: 'التقييم المستمر بيساعد التحسين.',
      options: [
        EduOption(text: 'بسأل: كلنا بنعمل update؟ بنستخدم كلمات سر قوية؟ عندنا حوار مفتوح؟', isCorrect: true, rationale: '✅ التقييم العملي بيحدد النقص.'),
        EduOption(text: 'لو مفيش مشاكل ظاهرة يبقى كويس', isCorrect: false, rationale: '❌ المشاكل ممكن تكون مخفية.'),
        EduOption(text: 'بس لو عندنا برنامج حماية', isCorrect: false, rationale: '❌ البرنامج مش كل شيء.'),
        EduOption(text: 'مش مهم نقيّم', isCorrect: false, rationale: '❌ التقييم بيساعد التحسين المستمر.'),
      ],
    ),
        ];
      default:
        return _buildQuestions(1);
    }
  }
}
