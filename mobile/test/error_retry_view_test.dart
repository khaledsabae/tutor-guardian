// Parents must never be shown an exception's toString().
//
// Three screens rendered errorGeneric(e.toString()), so a dropped connection
// read as "خطأ: SocketException: Failed host lookup: 'tg-api.alsaba.cloud'" —
// English, untranslatable, and alarming to someone who only wanted to see
// their child's routine.

import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/widgets/ui/error_retry_view.dart';

Widget _host(Object error, {VoidCallback? onRetry}) => MaterialApp(
      locale: const Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: ErrorRetryView(error: error, onRetry: onRetry)),
    );

void main() {
  group('classifyFailure', () {
    test('connection problems read as offline', () {
      expect(classifyFailure(const SocketException('no host')), FailureKind.offline);
      expect(classifyFailure(const HttpException('bad')), FailureKind.offline);
      expect(classifyFailure(TimeoutException('slow')), FailureKind.offline);
      // A TgApiError with no status never reached the server either.
      expect(classifyFailure(const TgApiError(null, 'x')), FailureKind.offline);
    });

    test('5xx reads as a server problem, 4xx does not', () {
      expect(classifyFailure(const TgApiError(500, 'x')), FailureKind.server);
      expect(classifyFailure(const TgApiError(503, 'x')), FailureKind.server);
      expect(classifyFailure(const TgApiError(404, 'x')), FailureKind.unknown);
      expect(classifyFailure(const TgApiError(422, 'x')), FailureKind.unknown);
    });

    test('anything else is unknown', () {
      expect(classifyFailure(StateError('boom')), FailureKind.unknown);
      expect(classifyFailure(FormatException('bad json')), FailureKind.unknown);
    });
  });

  group('ErrorRetryView', () {
    testWidgets('shows Arabic guidance, never the exception text',
        (tester) async {
      await tester.pumpWidget(_host(const SocketException(
        "Failed host lookup: 'tg-api.alsaba.cloud'",
      )));
      await tester.pumpAndSettle();

      expect(find.textContaining('SocketException'), findsNothing);
      expect(find.textContaining('tg-api'), findsNothing);
      expect(find.text('لا يوجد اتصال بالإنترنت'), findsOneWidget);
    });

    testWidgets('a server fault says so instead of blaming the connection',
        (tester) async {
      await tester.pumpWidget(_host(const TgApiError(500, 'boom')));
      await tester.pumpAndSettle();

      expect(find.text('الخدمة لا تستجيب الآن'), findsOneWidget);
      expect(find.text('لا يوجد اتصال بالإنترنت'), findsNothing);
    });

    testWidgets('the retry button only appears when retrying is possible',
        (tester) async {
      await tester.pumpWidget(_host(StateError('boom')));
      await tester.pumpAndSettle();
      expect(find.text('إعادة المحاولة'), findsNothing);

      var retried = 0;
      await tester.pumpWidget(_host(StateError('boom'), onRetry: () => retried++));
      await tester.pumpAndSettle();

      expect(find.text('إعادة المحاولة'), findsOneWidget);
      await tester.tap(find.text('إعادة المحاولة'));
      await tester.pumpAndSettle();
      expect(retried, 1);
    });
  });
}
