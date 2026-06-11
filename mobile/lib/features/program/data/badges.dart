/// Achievements / badges — P1 launch item #4 (local, derived).
///
/// Badges are NOT stored — they are computed purely from the child's
/// existing progress bundle (completed-lesson count, streak, distinct
/// paths touched). No competitive points; the tone is calm parental
/// encouragement ("ما شاء الله").
library;

import 'progress_models.dart';

class AchievementBadge {
  final String id;
  final String title;
  final String description;
  final String emoji;
  final bool earned;

  const AchievementBadge({
    required this.id,
    required this.title,
    required this.description,
    required this.emoji,
    required this.earned,
  });

  AchievementBadge _copyEarned(bool v) => AchievementBadge(
        id: id,
        title: title,
        description: description,
        emoji: emoji,
        earned: v,
      );
}

/// The full badge catalogue, each with its earn-condition evaluated
/// against [bundle]. Returns every badge (earned + locked) in display
/// order so the UI can show progress, not just unlocked ones.
List<AchievementBadge> computeBadges(ChildProgressBundle? bundle) {
  final completed = bundle?.completedCount ?? 0;
  final streak = bundle?.streakDays ?? 0;
  final distinctPaths = bundle == null
      ? 0
      : bundle.lessons
          .where((l) => l.status == ProgressStatus.completed)
          .map((l) => l.pathId)
          .toSet()
          .length;

  final catalogue = <AchievementBadge, bool>{
    const AchievementBadge(
      id: 'first_step',
      title: 'أول خطوة',
      description: 'أكملت أول درس — بداية الطريق',
      emoji: '🌱',
      earned: false,
    ): completed >= 1,
    const AchievementBadge(
      id: 'five_lessons',
      title: 'خمسة دروس',
      description: 'أكملت 5 دروس — استمرّ',
      emoji: '📚',
      earned: false,
    ): completed >= 5,
    const AchievementBadge(
      id: 'ten_lessons',
      title: 'عشرة دروس',
      description: 'أكملت 10 دروس — ما شاء الله',
      emoji: '🏅',
      earned: false,
    ): completed >= 10,
    const AchievementBadge(
      id: 'week_streak',
      title: 'أسبوع متواصل',
      description: '7 أيام متتالية من التعلّم',
      emoji: '🔥',
      earned: false,
    ): streak >= 7,
    const AchievementBadge(
      id: 'month_streak',
      title: 'سلسلة شهر',
      description: '30 يوماً متتالية — التزام رائع',
      emoji: '⭐',
      earned: false,
    ): streak >= 30,
    const AchievementBadge(
      id: 'path_explorer',
      title: 'مستكشف المسارات',
      description: 'دروس مكتملة في 3 مسارات مختلفة',
      emoji: '🗺️',
      earned: false,
    ): distinctPaths >= 3,
  };

  return catalogue.entries
      .map((e) => e.key._copyEarned(e.value))
      .toList();
}

/// How many of the catalogue badges have been earned.
int earnedCount(List<AchievementBadge> badges) =>
    badges.where((b) => b.earned).length;
