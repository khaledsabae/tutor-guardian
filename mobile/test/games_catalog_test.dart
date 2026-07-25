/// The games index and the «أين أجد…؟» help sheet.
///
/// Both exist to rescue someone who is already lost, so a broken entry in
/// either is worse than not offering it: it confirms the app is confusing.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/games/games_catalog.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

void main() {
  final locales = {
    'ar': lookupAppLocalizations(const Locale('ar')),
    'en': lookupAppLocalizations(const Locale('en')),
  };

  group('games catalog', () {
    test('lists every game', () {
      expect(kGames.length, 4);
    });

    test('labels resolve in both locales', () {
      for (final entry in locales.entries) {
        for (final game in kGames) {
          expect(game.label(entry.value), isNotEmpty,
              reason: '"${game.id}" has no ${entry.key} label');
        }
      }
    });

    test('every game builds a named route and ids are unique', () {
      final seenIds = <String>{};
      final seenRoutes = <String>{};
      for (final game in kGames) {
        final name = game.route().settings.name;
        expect(name, isNotNull, reason: '"${game.id}" builds an unnamed route');
        expect(seenIds.add(game.id), isTrue, reason: 'duplicate id ${game.id}');
        expect(seenRoutes.add(name!), isTrue,
            reason: 'two games open the same screen: $name');
      }
    });

    test('the parent quiz is not listed as a child game', () {
      // «اختبر معلوماتك التربوية» tests the parent, not the child — putting it
      // here would hand a five-year-old a parenting exam.
      for (final game in kGames) {
        expect(game.id, isNot('quiz_game'));
      }
      for (final game in kGames) {
        expect(game.route().settings.name, isNot('quiz_game'));
      }
    });

    test('every game has an emoji', () {
      for (final game in kGames) {
        expect(game.emoji, isNotEmpty, reason: '"${game.id}" has no emoji');
      }
    });
  });
}
