// Regression tests for the parenting-quiz game screen's load paths.
//
// v1.0.30 softened the payload parse from `data['questions'] as List` to
// `as List? ?? []`. That stopped a TypeError, but it made an empty question
// list reachable: `_currentIndex (0) >= _questions.length (0)` is true, so the
// screen routed straight to the results view, where `_score / (length * 10)`
// is 0/0 — and `double.nan.round()` throws UnsupportedError. A 200 response
// with no questions turned a load failure into a crash.
//
// An empty list is a failed load, so the retry UI is the correct destination.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:almorabbi/features/program/screens/quiz_game_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

Widget _host(http.Client client) => ProviderScope(
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: QuizGameScreen(client: client),
      ),
    );

http.Client _respondingWith(String body, {int status = 200}) =>
    MockClient((_) async => http.Response(
          body,
          status,
          headers: {'content-type': 'application/json; charset=utf-8'},
        ));

void main() {
  group('QuizGameScreen load failures', () {
    testWidgets('200 with an empty question list shows retry, not results',
        (tester) async {
      await tester.pumpWidget(_host(_respondingWith(jsonEncode({'questions': []}))));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('200 with no questions key shows retry, not results',
        (tester) async {
      await tester.pumpWidget(_host(_respondingWith(jsonEncode({'ok': true}))));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('a body that is not JSON shows retry without throwing',
        (tester) async {
      await tester.pumpWidget(_host(_respondingWith('<html>captive portal</html>')));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('questions missing a field build_Question needs are dropped',
        (tester) async {
      // No 'choices' key: rendering this would throw inside build, where the
      // user has no retry affordance.
      final body = jsonEncode({
        'questions': [
          {'question': 'سؤال ناقص', 'answer': 0, 'domain': 'cyber'}
        ]
      });
      await tester.pumpWidget(_host(_respondingWith(body)));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('a real question list renders the question, not the retry UI',
        (tester) async {
      final body = jsonEncode({
        'questions': [
          {
            'question': 'سؤال تجريبي',
            'choices': ['أ', 'ب', 'ج', 'د'],
            'answer': 0,
            'domain': 'cyber',
          }
        ]
      });
      await tester.pumpWidget(_host(_respondingWith(body)));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(tester.takeException(), isNull);
      expect(find.byIcon(Icons.refresh), findsNothing);
      expect(find.text('سؤال تجريبي'), findsOneWidget);
    });
  });
}
