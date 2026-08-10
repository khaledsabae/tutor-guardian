// Pins the Arabic decoding of the quiz payload.
//
// This screen is the only place in the app that reads `resp.body` instead of
// `utf8.decode(resp.bodyBytes)`, and the API answers with
// `content-type: application/json` carrying no charset. package:http used to
// fall back to latin1 in exactly that case, which would mojibake every
// question; 1.2.2 decodes as UTF-8 instead, verified directly against
// Response.body with and without the charset parameter.
//
// So this is a guard, not a bug report: if that default ever changes, or the
// endpoint starts declaring a different charset, Arabic breaks silently for
// every parent and this test is what says so.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:almorabbi/features/program/screens/quiz_game_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

const _arabicQuestion = 'كيف تحمي طفلك من المحتوى غير المناسب؟';

void main() {
  testWidgets('an Arabic question survives a response with no charset',
      (tester) async {
    final payload = jsonEncode({
      'questions': [
        {
          'question': _arabicQuestion,
          'choices': ['أ', 'ب', 'ج', 'د'],
          'answer': 0,
          'domain': 'cyber',
        }
      ]
    });

    // Exactly what production sends: UTF-8 bytes, no charset in the header.
    final client = MockClient((_) async => http.Response.bytes(
          utf8.encode(payload),
          200,
          headers: {'content-type': 'application/json'},
        ));

    await tester.pumpWidget(ProviderScope(
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: QuizGameScreen(client: client),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(tester.takeException(), isNull);
    expect(find.text(_arabicQuestion), findsOneWidget);
  });
}
