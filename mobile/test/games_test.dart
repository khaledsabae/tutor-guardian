import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/games/tree_of_deeds/tree_of_deeds_game.dart';
import 'package:almorabbi/features/games/healthy_hero/healthy_hero_game.dart';
import 'package:almorabbi/features/games/shared/edu_game_models.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('TreeOfDeedsGame Question Builder Tests', () {
    test('Level 1 questions are loaded correctly', () {
      const shell = TreeOfDeedsGame();
      final questions = shell.questionBuilder(1);
      expect(questions, isNotEmpty);
      expect(questions[0].category, 'الأمانة');
      expect(questions[0].options.length, 4);
    });

    test('Level 2 questions are loaded correctly', () {
      const shell = TreeOfDeedsGame();
      final questions = shell.questionBuilder(2);
      expect(questions, isNotEmpty);
      expect(questions[0].options.any((o) => o.isCorrect), isTrue);
    });
  });

  group('HealthyHeroGame Question Builder Tests', () {
    test('Level 1 questions are loaded correctly', () {
      const shell = HealthyHeroGame();
      final questions = shell.questionBuilder(1);
      expect(questions, isNotEmpty);
      expect(questions[0].options.length, 4);
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
