/// Question packs — the four games' content lives in
/// `assets/content/games/*.ar.json` since 2026-08-13, not in Dart literals.
///
/// What these pin is what the move could plausibly have broken: the shape of
/// each pack, the level fallback the old `switch`'s `default:` arm provided,
/// and the rule that made the move safe — which option is right is carried by
/// its key, not by where it sits.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/games/shared/edu_game_models.dart';

/// The four packs, by the id the shell loads them with ([EduGameTheme.id]).
const _games = ['data_defender', 'tree_of_deeds', 'emotion_maze', 'healthy_hero'];

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('question packs', () {
    test('every game ships a pack of 10 levels × 5 questions', () async {
      for (final game in _games) {
        final pack = await EduGameContent.load(game);
        expect(pack.game, game);
        expect(pack.questionCount, 50, reason: game);
        for (var level = 1; level <= 10; level++) {
          expect(pack.forLevel(level).length, 5, reason: '$game level $level');
        }
      }
    });

    test('an unknown level falls back to level 1, as the old switch did',
        () async {
      final pack = await EduGameContent.load('tree_of_deeds');
      expect(pack.forLevel(99).first.id, pack.forLevel(1).first.id);
      expect(pack.forLevel(0).first.id, pack.forLevel(1).first.id);
    });

    test('ids are namespaced per game so a flat map cannot collide', () async {
      // All four packs used q_0..q_49. Merging them on those ids would have
      // collided four ways and silently kept one game's wording.
      final seen = <String>{};
      for (final game in _games) {
        final pack = await EduGameContent.load(game);
        for (var level = 1; level <= 10; level++) {
          for (final q in pack.forLevel(level)) {
            expect(q.id, startsWith('$game.'), reason: q.id);
            expect(seen.add(q.id), isTrue, reason: 'duplicate id ${q.id}');
          }
        }
      }
      expect(seen.length, 200);
    });

    test('correctness is carried by key, not by position', () async {
      // A translated pack will carry key + text and no verdict; correctness is
      // merged in from here by key. That only holds if the keys are present,
      // distinct and ordered, and exactly one option is right.
      for (final game in _games) {
        final pack = await EduGameContent.load(game);
        for (var level = 1; level <= 10; level++) {
          for (final q in pack.forLevel(level)) {
            expect(q.options.length, 4, reason: q.id);
            expect(q.options.map((o) => o.key).toList(), ['a', 'b', 'c', 'd'],
                reason: q.id);
            expect(q.options.where((o) => o.isCorrect).length, 1, reason: q.id);
            expect(q.options.every((o) => o.text.trim().isNotEmpty), isTrue,
                reason: q.id);
          }
        }
      }
    });

    test('an option with no stated verdict is not treated as correct', () {
      // A translated pack omits `is_correct`. Defaulting a missing verdict to
      // true would mark every wrong answer right.
      final pack = EduQuestionPack.fromJson({
        'game': 'x',
        'levels': [
          {
            'level': 1,
            'questions': [
              {
                'id': 'x.q_0',
                'question': 'q',
                'options': [
                  {'key': 'a', 'text': 'a'},
                  {'key': 'b', 'text': 'b'},
                ],
              }
            ],
          }
        ],
      });
      expect(pack.forLevel(1).first.options.every((o) => !o.isCorrect), isTrue);
    });

    test('the level-1 content the games shipped with is still there', () async {
      // Pinned from the Dart literals this pack replaced.
      final tree = await EduGameContent.load('tree_of_deeds');
      expect(tree.forLevel(1).first.category, 'الأمانة');
      expect(tree.forLevel(1).first.id, 'tree_of_deeds.q_0');
      final healthy = await EduGameContent.load('healthy_hero');
      expect(healthy.forLevel(1).first.options.length, 4);
    });
  });

  group('EduGameProgress Tests', () {
    test('EduGameProgress initialization and getters', () {
      const progress = EduGameProgress(
        gameId: 'test_game',
        totalScore: 120,
        gamesPlayed: 5,
      );

      expect(progress.gameId, 'test_game');
      expect(progress.totalScore, 120);
      expect(progress.gamesPlayed, 5);
      expect(progress.highestUnlockedLevel, 1);
    });
  });
}
