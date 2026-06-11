// Badges/achievements tests (P1 #4) — pure computeBadges logic.

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/badges.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';

LessonProgress _done(String lesson, String path) => LessonProgress(
      lessonId: lesson,
      pathId: path,
      status: ProgressStatus.completed,
    );

ChildProgressBundle _bundle({
  List<LessonProgress> lessons = const [],
  int streak = 0,
}) =>
    ChildProgressBundle(childId: 1, lessons: lessons, streakDays: streak);

AchievementBadge _byId(List<AchievementBadge> badges, String id) =>
    badges.firstWhere((b) => b.id == id);

void main() {
  group('computeBadges', () {
    test('null bundle → nothing earned, full catalogue returned', () {
      final badges = computeBadges(null);
      expect(badges, isNotEmpty);
      expect(earnedCount(badges), 0);
      expect(badges.every((b) => !b.earned), isTrue);
    });

    test('first lesson unlocks "first_step" only', () {
      final badges = computeBadges(_bundle(lessons: [_done('l1', 'p1')]));
      expect(_byId(badges, 'first_step').earned, isTrue);
      expect(_byId(badges, 'five_lessons').earned, isFalse);
    });

    test('5 and 10 lesson milestones', () {
      final five = List.generate(5, (i) => _done('l$i', 'p1'));
      final b5 = computeBadges(_bundle(lessons: five));
      expect(_byId(b5, 'five_lessons').earned, isTrue);
      expect(_byId(b5, 'ten_lessons').earned, isFalse);

      final ten = List.generate(10, (i) => _done('l$i', 'p1'));
      final b10 = computeBadges(_bundle(lessons: ten));
      expect(_byId(b10, 'ten_lessons').earned, isTrue);
    });

    test('streak badges at 7 and 30 days', () {
      expect(_byId(computeBadges(_bundle(streak: 7)), 'week_streak').earned,
          isTrue);
      expect(_byId(computeBadges(_bundle(streak: 6)), 'week_streak').earned,
          isFalse);
      expect(_byId(computeBadges(_bundle(streak: 30)), 'month_streak').earned,
          isTrue);
    });

    test('path_explorer needs completed lessons in 3 distinct paths', () {
      final twoPaths = computeBadges(_bundle(lessons: [
        _done('a', 'p1'),
        _done('b', 'p2'),
      ]));
      expect(_byId(twoPaths, 'path_explorer').earned, isFalse);

      final threePaths = computeBadges(_bundle(lessons: [
        _done('a', 'p1'),
        _done('b', 'p2'),
        _done('c', 'p3'),
      ]));
      expect(_byId(threePaths, 'path_explorer').earned, isTrue);
    });

    test('in-progress lessons do not count toward badges', () {
      const bundle = ChildProgressBundle(childId: 1, lessons: [
        LessonProgress(
            lessonId: 'x', pathId: 'p1', status: ProgressStatus.inProgress),
      ]);
      expect(_byId(computeBadges(bundle), 'first_step').earned, isFalse);
    });
  });
}
