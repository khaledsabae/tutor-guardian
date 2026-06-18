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

  const JourneyMilestone({
    required this.key,
    required this.title,
    required this.description,
    required this.emoji,
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
