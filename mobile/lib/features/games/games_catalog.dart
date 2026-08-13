/// The four educational games, as data.
///
/// The games were reachable only from inside a lesson, and only from a lesson
/// in the matching domain — three levels deep, and invisible to a parent who
/// simply wanted to hand their child something to play. They are some of the
/// most valuable content in the app for kids, so they now also have a
/// destination of their own.
///
/// The in-lesson entry points stay: there the game is contextual to the
/// domain being taught, which is a different (and good) reason to offer it.
library;

import 'package:flutter/widgets.dart';

import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';

class GameEntry {
  const GameEntry({
    required this.id,
    required this.emoji,
    required this.label,
    required this.route,
  });

  /// Stable analytics id — never translated.
  ///
  /// Must equal the `EduGameTheme.id` of the game this entry points at: the
  /// catalog id and the theme id are two independently-maintained strings that
  /// both land in `game_id`, so a mismatch splits one game's numbers in two
  /// without any error. `games_catalog_test` pins them together.
  final String id;
  final String emoji;
  final String Function(AppLocalizations l10n) label;

  /// Takes the entry point so the route can carry it to the shell — see
  /// [GameSources]. Named and optional, so a caller with nothing to say still
  /// matches `route()`.
  final Route<void> Function({String source}) route;
}

/// Not `const`: the callbacks are function literals.
final List<GameEntry> kGames = [
  GameEntry(
    id: 'data_defender',
    emoji: '🛡️',
    label: (l10n) => l10n.dataDefender,
    route: AppRoutes.gameDataDefender,
  ),
  GameEntry(
    id: 'healthy_hero',
    emoji: '🥗',
    label: (l10n) => l10n.healthyHero,
    route: AppRoutes.gameHealthyHero,
  ),
  GameEntry(
    id: 'tree_of_deeds',
    emoji: '🌳',
    label: (l10n) => l10n.treeOfDeeds,
    route: AppRoutes.gameTreeOfDeeds,
  ),
  GameEntry(
    id: 'emotion_maze',
    emoji: '🎭',
    label: (l10n) => l10n.emotionMaze,
    route: AppRoutes.gameEmotionMaze,
  ),
  // Deliberately not listed here: «اختبر معلوماتك التربوية» is a quiz for the
  // *parent*, not something to hand a child. It has its own entry points.
];
