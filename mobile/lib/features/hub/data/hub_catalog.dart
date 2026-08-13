/// What lives in the «المزيد» hub, and how it is grouped.
///
/// The app has ~40 screens but only four tabs. Everything that is not part of
/// the daily loop lives here, grouped by what a parent is trying to *do*
/// rather than by which feature folder it came from. Before this existed, a
/// screen like the custom-story generator sat three levels deep (الرئيسية →
/// العملات → القصة) and was effectively undiscoverable.
///
/// Keeping the structure as data — rather than as widgets in the screen — is
/// what keeps `hub_screen.dart` small and makes it cheap to assert in tests
/// that every entry resolves to a real route *and* a real translated label.
///
/// Only parameterless destinations belong here. Screens that need a specific
/// child (child journey, edit child, Quran memorisation) stay reachable
/// through «أطفالي», where a child has actually been chosen.
library;

import 'package:flutter/widgets.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../routine/screens/daily_routine_screen.dart' show habitTabLabel;

/// One destination tile.
class HubItem {
  const HubItem({
    required this.id,
    required this.emoji,
    required this.label,
    required this.route,
  });

  /// Stable analytics id — reported via `hub_item_tapped`. Never translated.
  final String id;
  final String emoji;

  /// [ageGroup] is the active child's, for the one label that legitimately
  /// depends on it (the 0-6 routine tracker vs the 7-18 habit balance).
  final String Function(AppLocalizations l10n, String ageGroup) label;

  final Route<void> Function() route;
}

/// A titled section of the hub.
class HubGroup {
  const HubGroup({required this.id, required this.title, required this.items});

  final String id;
  final String Function(AppLocalizations l10n) title;
  final List<HubItem> items;
}

/// Not `const`: the label/route callbacks are function literals, which Dart
/// does not treat as compile-time constants.
final List<HubGroup> kHubGroups = [
  HubGroup(
    id: 'child',
    title: (l10n) => l10n.hubGroupChild,
    items: [
      HubItem(
        id: 'children_list',
        emoji: '👨‍👩‍👧',
        label: (l10n, _) => l10n.hubMyChildren,
        route: AppRoutes.childrenList,
      ),
      HubItem(
        id: 'daily_routine',
        emoji: '📊',
        // The only age-dependent label in the app. It used to sit on a bottom
        // nav tab, where switching child silently relabelled the tab under the
        // user's thumb; here it is harmless.
        label: (l10n, ageGroup) => habitTabLabel(ageGroup, l10n),
        route: AppRoutes.dailyRoutine,
      ),
      HubItem(
        id: 'habit_customize',
        emoji: '🎯',
        label: (l10n, _) => l10n.hubCustomizeHabits,
        route: AppRoutes.habitCustomize,
      ),
      HubItem(
        id: 'parenting_insights',
        emoji: '🧠',
        label: (l10n, _) => l10n.hubInsights,
        route: AppRoutes.parentingInsights,
      ),
    ],
  ),
  // Second, not fourth. Games are the smallest stock in the app and the most
  // re-used thing in it, and they used to sit below `achievements` and
  // `library` — about 550dp down a ~600dp viewport, so reaching them from here
  // required scrolling past thirteen other tiles. A parent asked for
  // "games for the child" in written feedback on 2026-08-01 while four were
  // already shipping.
  //
  // If this moves the needle it should show up as a rising share of
  // `hub_item_tapped` with group='games'; the pre-2026-08-13 baseline for that
  // is the only one available, since `hub_opened` was removed as unreliable.
  HubGroup(
    id: 'games',
    title: (l10n) => l10n.hubGroupGames,
    items: [
      HubItem(
        id: 'games',
        emoji: '🎮',
        label: (l10n, _) => l10n.educationalGames,
        route: AppRoutes.games,
      ),
      HubItem(
        id: 'quiz_game',
        emoji: '❓',
        label: (l10n, _) => l10n.quizzes,
        route: AppRoutes.quizGame,
      ),
    ],
  ),
  HubGroup(
    id: 'achievements',
    title: (l10n) => l10n.hubGroupAchievements,
    items: [
      HubItem(
        id: 'badges',
        emoji: '🏅',
        label: (l10n, _) => l10n.badges,
        route: AppRoutes.badges,
      ),
      HubItem(
        id: 'coins',
        emoji: '🪙',
        label: (l10n, _) => l10n.coins,
        route: AppRoutes.coins,
      ),
      HubItem(
        id: 'exclusive_badges',
        emoji: '✨',
        label: (l10n, _) => l10n.coinsRedeemBadges,
        route: AppRoutes.exclusiveBadges,
      ),
      HubItem(
        id: 'covenant',
        emoji: '📜',
        label: (l10n, _) => l10n.covenant,
        route: AppRoutes.covenant,
      ),
      HubItem(
        id: 'favorites',
        emoji: '⭐',
        label: (l10n, _) => l10n.favoritesTitle,
        route: AppRoutes.favorites,
      ),
    ],
  ),
  HubGroup(
    id: 'library',
    title: (l10n) => l10n.hubGroupLibrary,
    items: [
      HubItem(
        id: 'story_bookshelf',
        emoji: '🌙',
        label: (l10n, _) => l10n.bedtimeStories,
        route: AppRoutes.storyBookshelf,
      ),
      HubItem(
        id: 'story_generator',
        emoji: '📖',
        label: (l10n, _) => l10n.hubCreateStory,
        route: AppRoutes.storyGenerator,
      ),
      HubItem(
        id: 'quran',
        emoji: '📗',
        label: (l10n, _) => l10n.holyQuran,
        route: AppRoutes.quran,
      ),
      HubItem(
        id: 'search',
        emoji: '🔍',
        label: (l10n, _) => l10n.search,
        route: AppRoutes.search,
      ),
    ],
  ),
  // The individual games live behind one entry rather than five tiles: the hub
  // is an index, and five near-identical rows here crowded out everything else
  // in it. GamesScreen is the index for the games themselves.
  HubGroup(
    id: 'help',
    title: (l10n) => l10n.hubGroupHelp,
    items: [
      HubItem(
        id: 'settings',
        emoji: '⚙️',
        label: (l10n, _) => l10n.settings,
        route: AppRoutes.settings,
      ),
      HubItem(
        id: 'identity',
        emoji: '👤',
        label: (l10n, _) => l10n.hubAccount,
        route: AppRoutes.identity,
      ),
      HubItem(
        id: 'invite',
        emoji: '🤍',
        label: (l10n, _) => l10n.inviteFriend,
        route: AppRoutes.invite,
      ),
      HubItem(
        id: 'feedback',
        emoji: '💬',
        label: (l10n, _) => l10n.feedbackTitle,
        route: AppRoutes.feedback,
      ),
    ],
  ),
];
