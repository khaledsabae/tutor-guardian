/// «رحلة الطفل» — the spiritual-milestone catalogue (Phase 1, local).
///
/// A curated, ordered list of Islamic milestones a parent can mark for
/// their child. NOT generated — calm, encouraging tone («ما شاء الله»),
/// never medical, never age-gated baby advice. Pillar 2 (developmental,
/// age-derived from the curriculum) lands in a later phase; the
/// `first_surah` milestone will link to Quran memorization tracking
/// (Phase 4).
library;

class JourneyMilestone {
  final String key;
  final String title;
  final String description;
  final String emoji;

  /// Optional, gentle, DEVELOPMENTAL-only "what if it's late" note shown
  /// under a suggested milestone. Never medical, never a diagnosis —
  /// always routes to «استشر مختصًا» for the few items that warrant it.
  final String? concernNote;

  const JourneyMilestone({
    required this.key,
    required this.title,
    required this.description,
    required this.emoji,
    this.concernNote,
  });
}

/// Display order = a rough spiritual-growth sequence; the parent is free
/// to mark them in any order.
const List<JourneyMilestone> spiritualMilestones = [
  JourneyMilestone(
    key: 'shahada',
    title: 'نطق الشهادة',
    description: 'أول مرة ينطق الشهادتين',
    emoji: '🤍',
  ),
  JourneyMilestone(
    key: 'first_dua',
    title: 'حفظ أول دعاء',
    description: 'تعلّم دعاءً صار يردده',
    emoji: '🤲',
  ),
  JourneyMilestone(
    key: 'first_prayer',
    title: 'أول صلاة',
    description: 'صلّى أول صلاة بنفسه',
    emoji: '🕌',
  ),
  JourneyMilestone(
    key: 'keeps_prayer',
    title: 'يحافظ على الصلاة',
    description: 'بدأ يحافظ على صلواته',
    emoji: '🌟',
  ),
  JourneyMilestone(
    key: 'first_surah',
    title: 'حفظ أول سورة',
    description: 'أتمّ حفظ أول سورة من القرآن',
    emoji: '📖',
  ),
  JourneyMilestone(
    key: 'first_fast',
    title: 'أول يوم صيام',
    description: 'صام أول يوم في رمضان',
    emoji: '🌙',
  ),
  JourneyMilestone(
    key: 'good_manner',
    title: 'موقف خُلق حسن',
    description: 'موقف أظهر فيه خُلقًا جميلًا',
    emoji: '💛',
  ),
  JourneyMilestone(
    key: 'helped_others',
    title: 'ساعد غيره',
    description: 'بادر بمساعدة أحد من حوله',
    emoji: '🤝',
  ),
  JourneyMilestone(
    key: 'quran_khatma',
    title: 'ختمة قرآن',
    description: 'أتمّ ختمة كاملة للقرآن',
    emoji: '🏆',
  ),
];

/// Reward id namespaced per child so each child's milestone is rewarded
/// exactly once (the device-wide coins ledger dedups by id).
String journeyRewardId(int childId, String milestoneKey) =>
    'journey:$childId:$milestoneKey';

/// The 9 spiritual milestones that ship with a custom badge illustration
/// (assets/images/milestones/<key>.png). Developmental + custom milestones
/// have no badge and fall back to their emoji.
const Set<String> _badgeMilestoneKeys = {
  'shahada',
  'first_dua',
  'first_prayer',
  'keeps_prayer',
  'first_surah',
  'first_fast',
  'good_manner',
  'helped_others',
  'quran_khatma',
};

/// Asset path for a milestone's badge illustration, or null if it has none
/// (the caller then shows [JourneyMilestone.emoji] / [MilestoneEntry.emoji]).
String? milestoneBadgeAsset(String key) =>
    _badgeMilestoneKeys.contains(key) ? 'assets/images/milestones/$key.png' : null;

/// Developmental milestones, by age band — curated from the `development`
/// domain of the curriculum. Keys are `dev_*`-prefixed to share the per-child
/// store with the spiritual ones without colliding. The handful of
/// `concernNote`s are gentle, developmental, never medical.
const Map<String, List<JourneyMilestone>> _developmentalByAge = {
  'prenatal-1': [
    JourneyMilestone(
      key: 'dev_social_smile',
      title: 'ابتسامته الأولى',
      description: 'ابتسم لك ابتسامة اجتماعية',
      emoji: '😊',
    ),
    JourneyMilestone(
      key: 'dev_sit_crawl',
      title: 'جلس أو بدأ يحبو',
      description: 'تحكّم في جسده — جلس بمفرده أو حبا',
      emoji: '🍼',
    ),
    JourneyMilestone(
      key: 'dev_first_babble',
      title: 'أول مناغاة',
      description: 'بدأ يناغي ويردد مقاطع («ماما/بابا»)',
      emoji: '🗣️',
      concernNote: 'لو لم يناغِ أو يلتفت للصوت قرب نهاية العام، اذكرها لطبيبه.',
    ),
    JourneyMilestone(
      key: 'dev_secure_attach',
      title: 'يهدأ بين يديك',
      description: 'علامة ارتباط آمن — يطمئن بحضنك',
      emoji: '🤱',
    ),
  ],
  '2-3': [
    JourneyMilestone(
      key: 'dev_two_word',
      title: 'أول جملة من كلمتين',
      description: 'ركّب كلمتين معاً («عايز ماء»)',
      emoji: '🗣️',
      concernNote: 'لو لم يركّب كلمتين قرب نهاية الثالثة، استشر مختص نطق.',
    ),
    JourneyMilestone(
      key: 'dev_toilet',
      title: 'التدريب على الحمام',
      description: 'بدأ يستخدم الحمام باستقلالية',
      emoji: '🚽',
    ),
    JourneyMilestone(
      key: 'dev_pretend_play',
      title: 'اللعب التخيّلي',
      description: 'تظاهر باللعب (يُطعم دميته)',
      emoji: '🧸',
    ),
    JourneyMilestone(
      key: 'dev_name_feeling',
      title: 'سمّى مشاعره',
      description: 'عبّر عن شعور بكلمة بدل النوبة',
      emoji: '💛',
    ),
  ],
  '4-6': [
    JourneyMilestone(
      key: 'dev_dress_self',
      title: 'يلبس بنفسه',
      description: 'استقلالية يومية — يلبس ويأكل وحده',
      emoji: '👕',
    ),
    JourneyMilestone(
      key: 'dev_friendships',
      title: 'يلعب مع غيره',
      description: 'كوّن صداقات ويتشارك في اللعب',
      emoji: '🤝',
    ),
    JourneyMilestone(
      key: 'dev_draw_write',
      title: 'يمسك القلم ويرسم',
      description: 'يرسم أشكالاً ويحاول كتابة اسمه',
      emoji: '✏️',
    ),
    JourneyMilestone(
      key: 'dev_express_words',
      title: 'يعبّر بالكلام',
      description: 'يصف مشاعره بالكلمات بدل النوبات',
      emoji: '🗣️',
    ),
  ],
  '7-9': [
    JourneyMilestone(
      key: 'dev_reads_alone',
      title: 'يقرأ بمفرده',
      description: 'قرأ جملة أو قصة قصيرة وحده',
      emoji: '📖',
    ),
    JourneyMilestone(
      key: 'dev_responsibility',
      title: 'تحمّل مسؤولية',
      description: 'مهمة بيت أو إدارة مصروفه',
      emoji: '💪',
    ),
    JourneyMilestone(
      key: 'dev_resolve_conflict',
      title: 'يحل خلافاً',
      description: 'حافظ على صداقة وحلّ خلافاً بنفسه',
      emoji: '🤝',
    ),
    JourneyMilestone(
      key: 'dev_manage_time',
      title: 'ينظّم وقته',
      description: 'وازن بين الواجب واللعب',
      emoji: '⏰',
    ),
  ],
  '10-12': [
    JourneyMilestone(
      key: 'dev_puberty_talk',
      title: 'حوار البلوغ',
      description: 'تحدّثت معه بثقة عن تغيّرات جسده',
      emoji: '🌱',
    ),
    JourneyMilestone(
      key: 'dev_screen_deal',
      title: 'يدير وقت الشاشة',
      description: 'التزم باتفاق منظّم لوقت الشاشة',
      emoji: '📱',
    ),
    JourneyMilestone(
      key: 'dev_respectful_opinion',
      title: 'يناقش باحترام',
      description: 'عبّر عن رأيه وناقش بأدب',
      emoji: '💬',
    ),
    JourneyMilestone(
      key: 'dev_self_manage',
      title: 'يدير مهامه',
      description: 'مسؤولية أكبر — ينجز بنفسه',
      emoji: '✅',
    ),
  ],
  '13-15': [
    JourneyMilestone(
      key: 'dev_future_goal',
      title: 'يخطط لهدف',
      description: 'وضع هدفاً مستقبلياً وخطوات له',
      emoji: '🎯',
    ),
    JourneyMilestone(
      key: 'dev_peer_pressure',
      title: 'قرار واعٍ تحت الضغط',
      description: 'اتخذ قراراً صحيحاً رغم ضغط الأصدقاء',
      emoji: '🧭',
    ),
    JourneyMilestone(
      key: 'dev_identity_talk',
      title: 'حوار القيم والهوية',
      description: 'نقاش ناضج عن قيمه وهويته',
      emoji: '💬',
    ),
    JourneyMilestone(
      key: 'dev_graded_indep',
      title: 'استقلال بمسؤولية',
      description: 'استقلال متدرّج مع التزام بالحدود',
      emoji: '🕊️',
    ),
  ],
  '16-18': [
    JourneyMilestone(
      key: 'dev_life_ready',
      title: 'استعداد للحياة',
      description: 'يستعد للجامعة أو العمل بثقة',
      emoji: '🎓',
    ),
    JourneyMilestone(
      key: 'dev_financial',
      title: 'إدارة مالية',
      description: 'يدير ميزانيته ومسؤولياته',
      emoji: '💼',
    ),
    JourneyMilestone(
      key: 'dev_big_decisions',
      title: 'قرارات كبيرة بثقة',
      description: 'اتخذ قراراً كبيراً بحكمة واستشارة',
      emoji: '🧭',
    ),
    JourneyMilestone(
      key: 'dev_mature_bond',
      title: 'علاقة ناضجة معك',
      description: 'علاقة متبادلة قائمة على الثقة',
      emoji: '🤝',
    ),
  ],
};

/// Developmental milestones for a child's age band. `0-3` is the legacy
/// alias for `prenatal-1`. Returns `[]` for unknown bands.
List<JourneyMilestone> developmentalMilestonesFor(String? ageGroup) {
  if (ageGroup == null) return const [];
  final band = ageGroup == '0-3' ? 'prenatal-1' : ageGroup;
  return _developmentalByAge[band] ?? const [];
}
