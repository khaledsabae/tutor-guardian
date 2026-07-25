/// Invariants for the central route registry.
///
/// Every screen's analytics identity comes from `Screens.*`, and the whole
/// "where do users get lost?" instrumentation depends on those names being
/// present and distinct. Two screens sharing a name would silently merge in
/// Firebase — the numbers would still look plausible, which is exactly what
/// makes it worth a test.
library;

import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/core/app_routes.dart';

/// Reads the `Screens` constants straight out of the source so the test covers
/// constants added later without anyone remembering to update this list.
Map<String, String> _screenConstantsFromSource() {
  final source = File('lib/core/app_routes.dart').readAsStringSync();
  final classStart = source.indexOf('abstract final class Screens');
  // Not `expect`: this helper also runs at group-declaration time, where the
  // test framework has no active test to attach a failure to.
  if (classStart < 0) {
    throw StateError('the Screens class was renamed or removed');
  }
  final classEnd = source.indexOf('\n}', classStart);
  final body = source.substring(classStart, classEnd);

  final pattern = RegExp(r"static const (\w+) = '([^']*)';");
  return {
    for (final m in pattern.allMatches(body)) m.group(1)!: m.group(2)!,
  };
}

void main() {
  group('Screens constants', () {
    final constants = _screenConstantsFromSource();

    test('the source actually parsed', () {
      expect(constants.length, greaterThan(30),
          reason: 'parsed too few constants — the regex or class shape drifted');
    });

    test('are all non-empty', () {
      for (final entry in constants.entries) {
        expect(entry.value, isNotEmpty, reason: 'Screens.${entry.key} is empty');
      }
    });

    test('are all unique', () {
      final seen = <String, String>{};
      for (final entry in constants.entries) {
        final clash = seen[entry.value];
        expect(
          clash,
          isNull,
          reason: 'Screens.${entry.key} duplicates Screens.$clash '
              '("${entry.value}") — they would merge into one funnel',
        );
        seen[entry.value] = entry.key;
      }
    });

    test('are snake_case and within Firebase parameter limits', () {
      for (final entry in constants.entries) {
        expect(
          RegExp(r'^[a-z][a-z0-9_]*$').hasMatch(entry.value),
          isTrue,
          reason: 'Screens.${entry.key} ("${entry.value}") is not snake_case',
        );
        expect(entry.value.length, lessThanOrEqualTo(40),
            reason: 'Screens.${entry.key} exceeds the 40-char Firebase limit');
      }
    });
  });

  group('AppRoutes factories', () {
    // Only the factories whose arguments are cheap to fabricate. The ones
    // needing a Story / ChildProfile / game session are covered indirectly by
    // the widget tests that navigate to them.
    final routes = <String, Route<dynamic>>{
      'search': AppRoutes.search(),
      'favorites': AppRoutes.favorites(),
      'quizGame': AppRoutes.quizGame(),
      'pathDetail': AppRoutes.pathDetail('p1', '4-6'),
      'lesson': AppRoutes.lesson('l1', '4-6'),
      'video': AppRoutes.video('https://x/v.mp4', 'title'),
      'podcast': AppRoutes.podcast('https://x/a.mp3', 'title'),
      'flashcards': AppRoutes.flashcards(const ['d1']),
      'quiz': AppRoutes.quiz(const ['q1']),
      'infographic': AppRoutes.infographic('https://x/i.png'),
      'report': AppRoutes.report('https://x/r.pdf'),
      'dataTable': AppRoutes.dataTable('https://x/d.csv'),
      'gameDataDefender': AppRoutes.gameDataDefender(),
      'gameHealthyHero': AppRoutes.gameHealthyHero(),
      'gameTreeOfDeeds': AppRoutes.gameTreeOfDeeds(),
      'gameEmotionMaze': AppRoutes.gameEmotionMaze(),
      'storyBookshelf': AppRoutes.storyBookshelf(),
      'storyGenerator': AppRoutes.storyGenerator(),
      'childrenList': AppRoutes.childrenList(),
      'addChild': AppRoutes.addChild(),
      'childJourney': AppRoutes.childJourney(childId: 1, childName: 'س'),
      'childModeLock':
          AppRoutes.childModeLock<void>(childId: 1, childName: 'س'),
      'childModeExpired': AppRoutes.childModeExpired<void>('expired'),
      'dailyRoutine': AppRoutes.dailyRoutine(),
      'habitCustomize': AppRoutes.habitCustomize(),
      'parentingInsights': AppRoutes.parentingInsights(),
      'quran': AppRoutes.quran(),
      'surahReading': AppRoutes.surahReading(
        chapterNumber: 1,
        initialVerse: 1,
        quranData: const {},
      ),
      'quranMemorization':
          AppRoutes.quranMemorization(childId: 1, childName: 'س'),
      'coins': AppRoutes.coins(),
      'badges': AppRoutes.badges(),
      'exclusiveBadges': AppRoutes.exclusiveBadges(),
      'covenant': AppRoutes.covenant(),
      'settings': AppRoutes.settings(),
      'identity': AppRoutes.identity(),
      'invite': AppRoutes.invite(),
      'feedback': AppRoutes.feedback(),
    };

    test('every route carries a name', () {
      // An unnamed route is invisible to TgNavObserver, so a factory that
      // bypasses the private helper would silently create a blind spot.
      for (final entry in routes.entries) {
        expect(entry.value.settings.name, isNotNull,
            reason: 'AppRoutes.${entry.key}() produced an unnamed route');
        expect(entry.value.settings.name, isNotEmpty,
            reason: 'AppRoutes.${entry.key}() produced an empty route name');
      }
    });

    test('every route name is a known Screens constant', () {
      final known = _screenConstantsFromSource().values.toSet();
      for (final entry in routes.entries) {
        expect(known, contains(entry.value.settings.name),
            reason: 'AppRoutes.${entry.key}() uses an ad-hoc name');
      }
    });

    test('no two factories share a name', () {
      final seen = <String, String>{};
      for (final entry in routes.entries) {
        final name = entry.value.settings.name!;
        final clash = seen[name];
        expect(clash, isNull,
            reason: 'AppRoutes.${entry.key}() and AppRoutes.$clash() both '
                'report as "$name"');
        seen[name] = entry.key;
      }
    });

    test('routes that resolve to a value are typed', () {
      // Call sites await these; if the factory returned Route<void> the result
      // would silently arrive as null and the caller would skip its refresh.
      expect(AppRoutes.addChild(), isA<Route<bool>>());
    });

    test('the root name is reserved and not reused by any factory', () {
      // TgNavObserver maps the framework's '/' home route onto Screens.root.
      for (final entry in routes.entries) {
        expect(entry.value.settings.name, isNot(Screens.root),
            reason: 'AppRoutes.${entry.key}() collides with the root route');
      }
    });
  });
}
