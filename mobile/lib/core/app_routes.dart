/// Central route registry.
///
/// The app navigates imperatively (`Navigator.push`) rather than through a
/// declarative router — see the note below on why. The cost of that choice is
/// that routes carry no identity, which makes it impossible to observe
/// navigation centrally. This file buys the identity back: every screen gets a
/// stable name in [Screens] and a single factory in [AppRoutes] that stamps
/// it onto `RouteSettings.name`.
///
/// That one property is what lets `TgNavObserver` name all ~40 destinations
/// without touching a single call site, which in turn is what makes the
/// "where do users get lost?" instrumentation possible.
///
/// **Rules**
///  * Never build a `MaterialPageRoute` inline in a screen — add a factory here.
///  * Never pass a free-text screen name to analytics — use a [Screens]
///    constant, or Firebase's event cardinality explodes and the funnels
///    become unusable.
///
/// The [Screens] constants map 1:1 onto go_router path names, so adopting a
/// declarative router later (web build, or more than a handful of deep-link
/// patterns) is a migration of this file, not of the whole app.
library;

import 'package:flutter/material.dart';

import '../features/coins/coins_screen.dart';
import '../features/coins/covenant_screen.dart';
import '../features/coins/exclusive_badges_screen.dart';
import '../features/coins/story_screen.dart';
import '../features/feedback/feedback_screen.dart';
import '../features/games/data_defender/game_screen.dart';
import '../features/games/emotion_maze/game_screen.dart';
import '../features/games/healthy_hero/game_screen.dart';
import '../features/games/shared/edu_game_models.dart';
import '../features/games/screens/games_screen.dart';
import '../features/games/shared/edu_game_shell.dart';
import '../features/games/tree_of_deeds/game_screen.dart';
import '../features/identity/identity_screen.dart';
import '../features/journey/screens/child_journey_screen.dart';
import '../features/journey/screens/quran_memorization_screen.dart';
import '../features/program/data/progress_models.dart';
import '../features/program/data/story_models.dart';
import '../features/program/screens/add_child_screen.dart';
import '../features/program/screens/badges_screen.dart';
import '../features/program/screens/bedtime_routine_screen.dart';
import '../features/program/screens/children_list_screen.dart';
import '../features/program/screens/data_table_screen.dart';
import '../features/program/screens/edit_child_screen.dart';
import '../features/program/screens/favorites_screen.dart';
import '../features/program/screens/flashcards_screen.dart';
import '../features/program/screens/infographic_screen.dart';
import '../features/program/screens/lesson_screen.dart';
import '../features/program/screens/path_detail_screen.dart';
import '../features/program/screens/podcast_player_screen.dart';
import '../features/program/screens/quiz_game_screen.dart';
import '../features/program/screens/quiz_screen.dart';
import '../features/program/screens/report_screen.dart';
import '../features/program/screens/search_screen.dart';
import '../features/program/screens/settings_screen.dart';
import '../features/program/screens/story_bookshelf_screen.dart';
import '../features/program/screens/story_reader_screen.dart';
import '../features/program/screens/video_player_screen.dart';
import '../features/quran/screens/quran_screen.dart';
import '../features/quran/screens/surah_reading_screen.dart';
import '../features/referral/invite_screen.dart';
import '../features/routine/screens/child_mode_lock_screen.dart';
import '../features/routine/screens/daily_routine_screen.dart';
import '../features/routine/screens/habit_customize_screen.dart';
import '../features/routine/screens/parenting_insights_screen.dart';

/// Stable analytics identity for every navigable surface.
///
/// These strings are written to Firebase and compared across releases —
/// **renaming one breaks historical continuity**, so treat them as a wire
/// format, not as labels.
abstract final class Screens {
  // Shell — the root route created by MaterialApp's `home:`.
  static const root = 'root';

  // Bottom-navigation tabs (reported by the shell, not by the observer,
  // because switching an IndexedStack index is not a route change).
  static const tabToday = 'tab_today';
  static const tabLearn = 'tab_learn';
  static const tabAssistant = 'tab_assistant';
  static const tabMore = 'tab_more';

  // Program / curriculum
  static const pathDetail = 'path_detail';
  static const lesson = 'lesson';
  static const search = 'search';
  static const favorites = 'favorites';
  static const quizGame = 'quiz_game';

  // Lesson content types
  static const video = 'video';
  static const podcast = 'podcast';
  static const flashcards = 'flashcards';
  static const quiz = 'quiz';
  static const infographic = 'infographic';
  static const report = 'report';
  static const dataTable = 'data_table';

  // Games
  static const gameDataDefender = 'game_data_defender';
  static const gameHealthyHero = 'game_healthy_hero';
  static const gameTreeOfDeeds = 'game_tree_of_deeds';
  static const gameEmotionMaze = 'game_emotion_maze';
  static const gameRunner = 'game_runner';
  static const games = 'games';

  // Stories
  static const storyBookshelf = 'story_bookshelf';
  static const bedtimeRoutine = 'bedtime_routine';
  static const storyReader = 'story_reader';
  static const storyGenerator = 'story_generator';

  // Child management
  static const childrenList = 'children_list';
  static const addChild = 'add_child';
  static const editChild = 'edit_child';
  static const childJourney = 'child_journey';
  static const childModeLock = 'child_mode_lock';
  static const childModeExpired = 'child_mode_expired';

  // Routine & habits
  static const dailyRoutine = 'daily_routine';
  static const habitCustomize = 'habit_customize';
  static const parentingInsights = 'parenting_insights';

  // Quran
  static const quran = 'quran';
  static const surahReading = 'surah_reading';
  static const quranMemorization = 'quran_memorization';

  // Rewards
  static const coins = 'coins';
  static const badges = 'badges';
  static const exclusiveBadges = 'exclusive_badges';
  static const covenant = 'covenant';

  // Account & meta
  static const settings = 'settings';
  static const identity = 'identity';
  static const invite = 'invite';
  static const feedback = 'feedback';
  static const hub = 'hub';
}

/// Where a game was entered from, for the `entry_point` param on the game
/// events. Lives here rather than in the games feature for the same reason
/// [Screens] does: it is an analytics identifier, and the rule above says those
/// are constants, never free text.
///
/// Only two real values exist. The home shortcut, the hub tile and the help
/// sheet all route to the games index rather than to a game, so they are
/// already separable one level up via `home_card_tapped`, `hub_item_tapped`
/// and `help_intent_tapped`; the in-lesson button is the only path that
/// bypasses the index. Add a value here when a fifth entry point does the same.
abstract final class GameSources {
  /// Tapped a card on the games index.
  static const index = 'index';

  /// The «العب وتعلم» button inside a lesson of the matching domain.
  static const lesson = 'lesson';

  /// A route was built without naming its source — a missing call-site update,
  /// not a real entry point. If this shows up in GA4, something new pushes a
  /// game route and did not say so.
  static const unknown = 'unknown';
}

/// Builds every pushable route, tagged with its [Screens] name.
abstract final class AppRoutes {
  static Route<T> _r<T>(String name, WidgetBuilder builder,
          {Object? arguments}) =>
      MaterialPageRoute<T>(
        builder: builder,
        settings: RouteSettings(name: name, arguments: arguments),
      );

  // ── Program / curriculum ────────────────────────────────────────────────
  static Route<void> pathDetail(String pathId, String ageGroup) => _r(
        Screens.pathDetail,
        (_) => PathDetailScreen(pathId: pathId, ageGroup: ageGroup),
      );

  static Route<void> lesson(String lessonId, String ageGroup, {int? childId}) =>
      _r(
        Screens.lesson,
        (_) => LessonScreen(
          lessonId: lessonId,
          ageGroup: ageGroup,
          childId: childId,
        ),
      );

  static Route<void> search() => _r(Screens.search, (_) => const SearchScreen());

  static Route<void> favorites() =>
      _r(Screens.favorites, (_) => const FavoritesScreen());

  static Route<void> quizGame() =>
      _r(Screens.quizGame, (_) => const QuizGameScreen());

  // ── Lesson content types ────────────────────────────────────────────────
  // `url` is intentionally nullable: the player screens render their own
  // "asset unavailable" state rather than making every caller null-check.
  static Route<void> video(String? url, String title, {String? thumbnailUrl}) =>
      _r(
        Screens.video,
        (_) => VideoPlayerScreen(
          url: url,
          title: title,
          thumbnailUrl: thumbnailUrl,
        ),
      );

  static Route<void> podcast(String? url, String title) => _r(
        Screens.podcast,
        (_) => PodcastPlayerScreen(url: url, title: title),
      );

  static Route<void> flashcards(List<String> deckIds) =>
      _r(Screens.flashcards, (_) => FlashcardsScreen(deckIds: deckIds));

  static Route<void> quiz(List<String> quizIds) =>
      _r(Screens.quiz, (_) => QuizScreen(quizIds: quizIds));

  static Route<void> infographic(String url) =>
      _r(Screens.infographic, (_) => InfographicScreen(url: url));

  static Route<void> report(String url) =>
      _r(Screens.report, (_) => ReportScreen(url: url));

  static Route<void> dataTable(String url) =>
      _r(Screens.dataTable, (_) => DataTableScreen(url: url));

  // ── Games ───────────────────────────────────────────────────────────────
  /// The games index. They were previously reachable only from inside a lesson
  /// of the matching domain, which made them invisible to a parent who just
  /// wanted to hand their child something to play.
  static Route<void> games() => _r(Screens.games, (_) => const GamesScreen());

  // Each game route carries where it was entered from in RouteSettings.
  // arguments, which EduGameShell reads back for `entry_point`. Passing it
  // through the widget tree instead would mean threading a parameter through
  // four const screens and four game subclasses to reach the one place that
  // logs. The parameter is optional so these stay assignable to
  // `Route<void> Function()` in GameEntry, and an entry point that forgets to
  // name itself degrades to GameSources.unknown rather than to silence.
  static Route<void> gameDataDefender({String source = GameSources.unknown}) =>
      _r(Screens.gameDataDefender, (_) => const DataDefenderGameScreen(),
          arguments: {'source': source});

  static Route<void> gameHealthyHero({String source = GameSources.unknown}) =>
      _r(Screens.gameHealthyHero, (_) => const HealthyHeroGameScreen(),
          arguments: {'source': source});

  static Route<void> gameTreeOfDeeds({String source = GameSources.unknown}) =>
      _r(Screens.gameTreeOfDeeds, (_) => const TreeOfDeedsGameScreen(),
          arguments: {'source': source});

  static Route<void> gameEmotionMaze({String source = GameSources.unknown}) =>
      _r(Screens.gameEmotionMaze, (_) => const EmotionMazeGameScreen(),
          arguments: {'source': source});

  static Route<void> gameRunner({
    required EduGameTheme theme,
    required int level,
    required List<EduQuestion> questions,
    required void Function(EduGameResult) onComplete,
  }) =>
      _r(
        Screens.gameRunner,
        (_) => EduGameRunner(
          theme: theme,
          level: level,
          questions: questions,
          onComplete: onComplete,
        ),
      );

  // ── Stories ─────────────────────────────────────────────────────────────
  static Route<void> storyBookshelf() =>
      _r(Screens.storyBookshelf, (_) => const StoryBookshelfScreen());

  static Route<void> bedtimeRoutine(Story story) =>
      _r(Screens.bedtimeRoutine, (_) => BedtimeRoutineScreen(story: story));

  static Route<void> storyReader(Story story) =>
      _r(Screens.storyReader, (_) => StoryReaderScreen(story: story));

  static Route<void> storyGenerator() =>
      _r(Screens.storyGenerator, (_) => const StoryScreen());

  // ── Child management ────────────────────────────────────────────────────
  static Route<void> childrenList() =>
      _r(Screens.childrenList, (_) => const ChildrenListScreen());

  /// Resolves to `true` when a child was actually added.
  static Route<bool> addChild() =>
      _r<bool>(Screens.addChild, (_) => const AddChildScreen());

  /// Resolves to `true` when the profile was saved.
  static Route<bool> editChild(ChildProfile child) =>
      _r<bool>(Screens.editChild, (_) => EditChildScreen(child: child));

  static Route<void> childJourney({
    required int childId,
    required String childName,
    String? ageGroup,
  }) =>
      _r(
        Screens.childJourney,
        (_) => ChildJourneyScreen(
          childId: childId,
          childName: childName,
          ageGroup: ageGroup,
        ),
      );

  static Route<T> childModeLock<T>({
    required int childId,
    required String childName,
    bool isExit = false,
  }) =>
      _r<T>(
        Screens.childModeLock,
        (_) => ChildModeLockScreen(
          childId: childId,
          childName: childName,
          isExit: isExit,
        ),
      );

  /// Terminal state for a child-mode session that expired without a resolvable
  /// child id — there is nothing to unlock, so we can only explain.
  static Route<T> childModeExpired<T>(String message) => _r<T>(
        Screens.childModeExpired,
        (_) => Scaffold(body: Center(child: Text(message))),
      );

  // ── Routine & habits ────────────────────────────────────────────────────
  static Route<void> dailyRoutine() =>
      _r(Screens.dailyRoutine, (_) => const DailyRoutineScreen());

  static Route<void> habitCustomize() =>
      _r(Screens.habitCustomize, (_) => const HabitCustomizeScreen());

  static Route<void> parentingInsights() =>
      _r(Screens.parentingInsights, (_) => const ParentingInsightsScreen());

  // ── Quran ───────────────────────────────────────────────────────────────
  static Route<void> quran() => _r(Screens.quran, (_) => const QuranScreen());

  static Route<void> surahReading({
    required int chapterNumber,
    required int initialVerse,
    required Map<String, List<dynamic>> quranData,
  }) =>
      _r(
        Screens.surahReading,
        (_) => SurahReadingScreen(
          chapterNumber: chapterNumber,
          initialVerse: initialVerse,
          quranData: quranData,
        ),
      );

  static Route<void> quranMemorization({
    required int childId,
    required String childName,
  }) =>
      _r(
        Screens.quranMemorization,
        (_) => QuranMemorizationScreen(childId: childId, childName: childName),
      );

  // ── Rewards ─────────────────────────────────────────────────────────────
  static Route<void> coins() => _r(Screens.coins, (_) => const CoinsScreen());

  static Route<void> badges() =>
      _r(Screens.badges, (_) => const BadgesScreen());

  static Route<void> exclusiveBadges() =>
      _r(Screens.exclusiveBadges, (_) => const ExclusiveBadgesScreen());

  static Route<void> covenant() =>
      _r(Screens.covenant, (_) => const CovenantScreen());

  // ── Account & meta ──────────────────────────────────────────────────────
  static Route<void> settings() =>
      _r(Screens.settings, (_) => const SettingsScreen());

  static Route<void> identity() =>
      _r(Screens.identity, (_) => const IdentityScreen());

  static Route<void> invite() =>
      _r(Screens.invite, (_) => const InviteScreen());

  static Route<void> feedback() =>
      _r(Screens.feedback, (_) => const FeedbackScreen());
}
