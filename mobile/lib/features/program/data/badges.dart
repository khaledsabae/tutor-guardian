/// Achievements / badges — P1 launch item #4 (local, derived).
///
/// Badges are NOT stored — they are computed purely from the child's
/// existing progress bundle (completed-lesson count, streak, distinct
/// paths touched). No competitive points; the tone is calm parental
/// encouragement ("ما شاء الله").
///
/// The ids are permanent: the coins ledger credits each badge once, by id.
/// The words for a badge live in the ARB files and are looked up by that id.
library;

import '../../../l10n/app_localizations.dart';
import 'progress_models.dart';

class AchievementBadge {
  final String id;
  final String emoji;
  final bool earned;

  const AchievementBadge({
    required this.id,
    required this.emoji,
    required this.earned,
  });

  // An id with no entry shows as the bare id; a test walks the catalogue.
  String title(AppLocalizations l10n) => switch (id) {
        'first_step' => l10n.badgeFirstStepTitle,
        'five_lessons' => l10n.badgeFiveLessonsTitle,
        'ten_lessons' => l10n.badgeTenLessonsTitle,
        'week_streak' => l10n.badgeWeekStreakTitle,
        'month_streak' => l10n.badgeMonthStreakTitle,
        'path_explorer' => l10n.badgePathExplorerTitle,
        _ => id,
      };

  String description(AppLocalizations l10n) => switch (id) {
        'first_step' => l10n.badgeFirstStepDesc,
        'five_lessons' => l10n.badgeFiveLessonsDesc,
        'ten_lessons' => l10n.badgeTenLessonsDesc,
        'week_streak' => l10n.badgeWeekStreakDesc,
        'month_streak' => l10n.badgeMonthStreakDesc,
        'path_explorer' => l10n.badgePathExplorerDesc,
        _ => '',
      };

  /// The line that goes to the share sheet with this badge's card.
  String shareMessage(AppLocalizations l10n) =>
      l10n.badgeShareMessage(title(l10n));

  AchievementBadge _copyEarned(bool v) =>
      AchievementBadge(id: id, emoji: emoji, earned: v);
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
    const AchievementBadge(id: 'first_step', emoji: '🌱', earned: false):
        completed >= 1,
    const AchievementBadge(id: 'five_lessons', emoji: '📚', earned: false):
        completed >= 5,
    const AchievementBadge(id: 'ten_lessons', emoji: '🏅', earned: false):
        completed >= 10,
    const AchievementBadge(id: 'week_streak', emoji: '🔥', earned: false):
        streak >= 7,
    const AchievementBadge(id: 'month_streak', emoji: '⭐', earned: false):
        streak >= 30,
    const AchievementBadge(id: 'path_explorer', emoji: '🗺️', earned: false):
        distinctPaths >= 3,
  };

  return catalogue.entries
      .map((e) => e.key._copyEarned(e.value))
      .toList();
}

/// How many of the catalogue badges have been earned.
int earnedCount(List<AchievementBadge> badges) =>
    badges.where((b) => b.earned).length;
