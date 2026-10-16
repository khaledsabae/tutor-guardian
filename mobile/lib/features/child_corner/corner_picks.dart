/// What the corner offers today: one story and one game, chosen by the day.
///
/// Not a shelf. A child handed a list of nineteen books and four games spends
/// the session choosing; one of each is a session that has an end. The same
/// pick holds all day — opening the corner twice does not reshuffle it, so
/// there is nothing to gain by going in and out — and it moves on with the
/// calendar, never with how much the child played.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../../widgets/ui/brand_glyph.dart';
import '../games/data_defender/data_defender_game.dart';
import '../games/emotion_maze/emotion_maze_game.dart';
import '../games/games_catalog.dart';
import '../games/healthy_hero/healthy_hero_game.dart';
import '../games/shared/edu_game_models.dart';
import '../games/shared/edu_game_shell.dart';
import '../games/tree_of_deeds/tree_of_deeds_game.dart';
import '../handover/child_surface_policy.dart';
import '../program/data/story_models.dart';

/// [kChildCornerGameEnabled] as a provider, so a test can switch the game on
/// and keep its path — no score, no coins, back to the corner — covered while
/// the launch has it off.
final childCornerGameEnabledProvider = Provider<bool>(
  (_) => kChildCornerGameEnabled,
);

/// A stable number for the local calendar day.
int cornerDayIndex(DateTime now) => DateTime.utc(
  now.year,
  now.month,
  now.day,
).difference(DateTime.utc(2026)).inDays;

/// The item for this day. [salt] keeps two lists of the same length (or two
/// children on one device) from always moving in step.
T? pickOfTheDay<T>(List<T> items, DateTime now, {int salt = 0}) {
  if (items.isEmpty) return null;
  final i = (cornerDayIndex(now) + salt) % items.length;
  return items[i < 0 ? i + items.length : i];
}

/// Today's story: one with pages to read.
Story? cornerStoryFor(List<Story> stories, DateTime now, {int salt = 0}) =>
    pickOfTheDay(
      [
        for (final s in stories)
          if (s.pages.isNotEmpty) s,
      ],
      now,
      salt: salt,
    );

/// One of the four existing games, as the corner shows it.
class CornerGame {
  const CornerGame({
    required this.entry,
    required this.theme,
    required this.glyph,
  });

  /// The catalogue entry: the stable id and the translated name.
  final GameEntry entry;

  /// The game's own look and its question pack's id.
  final EduGameTheme theme;

  /// The paper glyph on the corner's card.
  final BrandIcon glyph;

  String get id => entry.id;
  String label(AppLocalizations l10n) => entry.label(l10n);
}

/// The four games, in catalogue order. Built from the games themselves, so a
/// game's theme here is the one its own screen uses.
List<CornerGame> cornerGames() {
  final shells = <String, (EduGameShell, BrandIcon)>{
    'data_defender': (const DataDefenderGame(), BrandIcon.door),
    'healthy_hero': (const HealthyHeroGame(), BrandIcon.sun),
    'tree_of_deeds': (const TreeOfDeedsGame(), BrandIcon.sprig),
    'emotion_maze': (const EmotionMazeGame(), BrandIcon.speechBubble),
  };
  return [
    for (final entry in kGames)
      if (shells[entry.id] case (final shell, final glyph))
        CornerGame(entry: entry, theme: shell.theme, glyph: glyph),
  ];
}

/// Whether the games' questions are written in [contentLanguage].
///
/// The four packs exist in Arabic only (`assets/content/games/*.ar.json`). A
/// child whose family reads the app in English is not handed a quiz they
/// cannot read: the corner leaves the game out for them, exactly as it does
/// for a band the policy gives no game.
bool cornerGamesSpeak(String contentLanguage) => contentLanguage == 'ar';

/// The level the child plays: the furthest one open to them, so a corner
/// visit continues the game rather than restarting it — without saying so.
int cornerLevelFor(EduGameProgress progress, EduQuestionPack pack) {
  var level = progress.highestUnlockedLevel;
  while (level > 1 && pack.forLevel(level).isEmpty) {
    level--;
  }
  return level;
}
