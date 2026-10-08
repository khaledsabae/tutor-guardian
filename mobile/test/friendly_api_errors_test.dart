// Raw server text must never reach a parent.
//
// An E2E run caught the lesson screen showing, under «تعذّر تحميل الدرس»:
//   TgApiError(502): The origin web server returned an invalid or incomplete
//   response to Cloudflare. This typically indicates the origin is overloaded
//   or misconfigured.
// The screen interpolated '$err' straight into its subtitle, and Cloudflare's
// JSON problem page carries a `detail` string, so the client took it for a
// server-written message. These tests pin the mapper every error surface now
// goes through, the lesson screen in both languages, and a source scan so the
// next '$err' in a widget fails here instead of in front of a parent.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/failures.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/program_providers.dart';
import 'package:almorabbi/features/program/screens/lesson_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/app_localizations_ar.dart';
import 'package:almorabbi/l10n/app_localizations_en.dart';
import 'package:almorabbi/widgets/ui/error_retry_view.dart';

const _cloudflare502 =
    'The origin web server returned an invalid or incomplete response to '
    'Cloudflare. This typically indicates the origin is overloaded or '
    'misconfigured.';

/// What must never appear on screen, whatever the failure.
const _leaks = [
  'Cloudflare',
  'TgApiError',
  'origin web server',
  'SocketException',
  'Exception',
  'HTTP 50',
  '<html',
  'Failed host lookup',
];

void _expectNoLeak(String text) {
  for (final leak in _leaks) {
    expect(text.toLowerCase(), isNot(contains(leak.toLowerCase())),
        reason: 'leaked "$leak" in: $text');
  }
}

void main() {
  final AppLocalizations ar = AppLocalizationsAr();
  final AppLocalizations en = AppLocalizationsEn();

  group('classifyFailure', () {
    test('every 5xx — Cloudflare 502/520 included — is the server', () {
      for (final code in [500, 502, 503, 504, 520, 522, 524]) {
        expect(classifyFailure(TgApiError(code, _cloudflare502)),
            FailureKind.server,
            reason: '$code');
      }
    });

    test('404 is not-found, 401/403 is the session, 429 is rate-limited', () {
      expect(classifyFailure(const TgApiError(404, 'Not Found')),
          FailureKind.notFound);
      expect(classifyFailure(const TgApiError(401, 'x')),
          FailureKind.unauthorized);
      expect(classifyFailure(const TgApiError(403, 'x')),
          FailureKind.unauthorized);
      expect(classifyFailure(const TgApiError(429, 'x')),
          FailureKind.rateLimited);
    });

    test('a dropped connection is offline whatever raised it', () {
      expect(classifyFailure(http.ClientException('Connection closed')),
          FailureKind.offline);
      expect(classifyFailure(TimeoutException('slow')), FailureKind.offline);
      expect(classifyFailure(const TgApiError(null, 'x')), FailureKind.offline);
    });

    test('stale data still only beats offline and server failures', () {
      expect(staleDataBeatsError(const TgApiError(502, 'x')), isTrue);
      expect(staleDataBeatsError(const SocketException('x')), isTrue);
      expect(staleDataBeatsError(const TgApiError(404, 'x')), isFalse);
      expect(staleDataBeatsError(const TgApiError(401, 'x')), isFalse);
    });
  });

  group('friendlyError', () {
    test('a Cloudflare 502 reads as "the service is unwell", in both languages',
        () {
      for (final l10n in [ar, en]) {
        final f = friendlyError(l10n, const TgApiError(502, _cloudflare502));
        expect(f.kind, FailureKind.server);
        expect(f.title, l10n.errorServerTitle);
        expect(f.body, l10n.errorServerBody);
        _expectNoLeak('${f.title} ${f.body}');
      }
    });

    test('a 5xx never passes its message through, even an Arabic one', () {
      final f = friendlyError(ar, const TgApiError(500, 'خطأ داخلي: KeyError'));
      expect(f.body, ar.errorServerBody);
    });

    test('404/401/429 get their own words', () {
      expect(friendlyError(ar, const TgApiError(404, 'Not Found')).body,
          ar.errorNotFoundBody);
      expect(friendlyError(en, const TgApiError(404, 'Not Found')).body,
          en.errorNotFoundBody);
      expect(friendlyError(ar, const TgApiError(401, 'Unauthorized')).body,
          ar.errorSessionBody);
      expect(friendlyError(ar, const TgApiError(429, 'Too Many Requests')).body,
          ar.errorRateLimitedBody);
    });

    test('a server-written message in the reader\'s language still reaches them',
        () {
      // The gentle daily-quota line and «الطفل غير موجود» are written for the
      // parent; replacing them with a generic sentence would lose information.
      const quota = 'وصلت إلى حدّ الأسئلة لهذا اليوم. نلتقي غدًا إن شاء الله.';
      expect(friendlyError(ar, const TgApiError(429, quota)).body, quota);
      expect(friendlyError(ar, const TgApiError(404, 'الطفل غير موجود')).body,
          'الطفل غير موجود');
      // …but not to a reader who cannot read it.
      expect(friendlyError(en, const TgApiError(429, quota)).body,
          en.errorRateLimitedBody);
    });

    test('a 4xx that looks like plumbing is not passed through', () {
      for (final raw in [
        'Not Found',
        'Method Not Allowed',
        '<!DOCTYPE html><html><body>Bad gateway</body></html>',
        'Traceback (most recent call last): ...',
        'خطأ HTTP 404',
      ]) {
        final body = friendlyError(ar, TgApiError(404, raw)).body;
        expect(body, ar.errorNotFoundBody, reason: raw);
      }
    });

    test('offline and unknown never echo the exception', () {
      final off = friendlyError(
          ar, const SocketException("Failed host lookup: 'tg-api.alsaba.cloud'"));
      expect(off.body, ar.errorOfflineBody);
      final unk = friendlyError(en, StateError('Bad state: boom'));
      expect(unk.body, en.errorUnknownBody);
      _expectNoLeak('${off.body} ${unk.body}');
    });

    test('describeFailure is the same body', () {
      expect(describeFailure(ar, const TgApiError(502, _cloudflare502)),
          ar.errorServerBody);
    });
  });

  group('TgClient keeps Cloudflare out of TgApiError.message', () {
    Future<TgApiError> fetch(http.Response response) async {
      final client = TgClient.forTesting(
        baseUrl: 'https://api.test',
        httpClient: MockClient((_) async => response),
      );
      try {
        await client.getLesson('l1');
      } on TgApiError catch (e) {
        return e;
      }
      fail('expected a TgApiError');
    }

    test('Cloudflare\'s JSON problem page (RFC 9457)', () async {
      final e = await fetch(http.Response.bytes(
        utf8.encode(jsonEncode({
          'type': 'https://developers.cloudflare.com/support/troubleshooting/'
              'cloudflare-errors/troubleshooting-cloudflare-5xx-errors/',
          'title': 'Error 502: Bad gateway',
          'status': 502,
          'detail': _cloudflare502,
          'error_code': 502,
          'ray_id': '8f00000000000000',
        })),
        502,
        headers: {'content-type': 'application/problem+json'},
      ));
      expect(e.statusCode, 502);
      // The generic «خطأ HTTP 502» is fine here — no screen shows a 5xx's
      // message — but the proxy's words must not be in it.
      for (final leak in ['Cloudflare', 'origin web server', '<html', 'Bad Gateway']) {
        expect(e.message, isNot(contains(leak)));
      }
      // Kept for diagnostics, just not as the message.
      expect(e.raw, contains('Cloudflare'));
    });

    test('an HTML error page', () async {
      final e = await fetch(http.Response(
          '<!DOCTYPE html><html><head><title>502 Bad Gateway</title></head>'
          '<body>cloudflare</body></html>',
          502,
          headers: {'content-type': 'text/html'}));
      expect(e.statusCode, 502);
      // The generic «خطأ HTTP 502» is fine here — no screen shows a 5xx's
      // message — but the proxy's words must not be in it.
      for (final leak in ['Cloudflare', 'origin web server', '<html', 'Bad Gateway']) {
        expect(e.message, isNot(contains(leak)));
      }
      expect(e.raw, contains('<html'));
    });

    test('our own JSON detail is still the message', () async {
      final e = await fetch(http.Response.bytes(
          utf8.encode(jsonEncode({'detail': 'الدرس غير موجود'})), 404,
          headers: {'content-type': 'application/json'}));
      expect(e.message, 'الدرس غير موجود');
      expect(e.raw, isNull);
    });
  });

  group('lesson screen error state', () {
    Future<void> pumpLesson(WidgetTester t, Locale locale, Object error) async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(overrides: [
        sharedPreferencesProvider.overrideWith((_) async => prefs),
        lessonProvider.overrideWith((ref, id) => Future.error(error)),
      ]);
      addTearDown(container.dispose);
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: locale,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const LessonScreen(lessonId: 'l1', ageGroup: '4-6'),
        ),
      ));
      await t.pumpAndSettle();
    }

    String allText(WidgetTester t) => t
        .widgetList<Text>(find.byType(Text))
        .map((w) => w.data ?? w.textSpan?.toPlainText() ?? '')
        .join('\n');

    for (final (locale, l10n) in [(const Locale('ar'), ar), (const Locale('en'), en)]) {
      final lang = locale.languageCode;

      testWidgets('Cloudflare 502 shows friendly text, keeps retry ($lang)',
          (t) async {
        await pumpLesson(t, locale, const TgApiError(502, _cloudflare502));
        expect(find.text(l10n.lessonErrorLoading), findsOneWidget);
        expect(find.text(l10n.errorServerBody), findsOneWidget);
        expect(find.text(l10n.retry), findsOneWidget);
        _expectNoLeak(allText(t));
      });

      testWidgets('a network failure says to check the connection ($lang)',
          (t) async {
        await pumpLesson(t, locale,
            const SocketException("Failed host lookup: 'tg-api.alsaba.cloud'"));
        expect(find.text(l10n.errorOfflineBody), findsOneWidget);
        expect(find.text(l10n.retry), findsOneWidget);
        _expectNoLeak(allText(t));
      });

      testWidgets('a 404 says the lesson is not available ($lang)', (t) async {
        await pumpLesson(t, locale, const TgApiError(404, 'Not Found'));
        expect(find.text(l10n.errorNotFoundBody), findsOneWidget);
        _expectNoLeak(allText(t));
      });
    }
  });

  group('ErrorRetryView', () {
    for (final (error, title) in [
      (const TgApiError(502, _cloudflare502), ar.errorServerTitle),
      (const TgApiError(404, 'Not Found'), ar.errorNotFoundTitle),
      (const TgApiError(401, 'x'), ar.errorSessionTitle),
      (const TgApiError(429, 'x'), ar.errorRateLimitedTitle),
    ]) {
      testWidgets('titles a ${(error).statusCode} by its category', (t) async {
        await t.pumpWidget(MaterialApp(
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(body: ErrorRetryView(error: error, onRetry: () {})),
        ));
        await t.pumpAndSettle();
        expect(find.text(title), findsOneWidget);
        expect(find.text(ar.retry), findsOneWidget);
        expect(find.textContaining('Cloudflare'), findsNothing);
      });
    }
  });

  // A guard on the source rather than the screens: there are dozens of error
  // surfaces and most are not reachable from a widget test without a whole
  // app. Each pattern below is a way an exception's own text was put in front
  // of a parent before this change.
  test('no UI text is built from a raw exception', () {
    final patterns = <RegExp>[
      // subtitle: '$err', error: '$e', Text('$e')
      RegExp(r"""['"]\$\{?(e|err|error|ex|exception)\}?['"]"""),
      // e.toString() — the exception's own text
      RegExp(r'\b(e|err|error|ex|exception)\.toString\(\)'),
      // l10n.somethingFailed(e.message), `? e.message :` — a server or
      // transport string used as text
      RegExp(r'\b(e|err|error|ex|inner)\.message\s*[),;:]'),
      // '…: $e' / '${l10n.x}\n$error' inside a longer literal
      RegExp(r"""['"][^'"]*\$\{?(e|err|error|ex)\}?[^'"\w][^'"]*['"]"""),
    ];
    // Lines that match a pattern but never reach the screen.
    bool exempt(String line) =>
        line.contains('debugPrint') ||
        line.contains('developer.log') ||
        line.contains('recordError') ||
        line.trimLeft().startsWith('//') ||
        line.trimLeft().startsWith('///');
    // Files whose matches are known and not UI text, with the reason.
    const allow = <String, String>{
      // `(e) => e.toString()` over a JSON list of strings, not an exception.
      'lib/features/program/data/story_models.dart': 'json list mapping',
      // A TgApiError's own toString(), for logs.
      'lib/api/tg_client.dart': 'toString for diagnostics',
      // The mapper itself reads error.message to decide whether to pass it.
      'lib/core/failures.dart': 'the mapper',
      // Classifies a 403's code by searching its text, never displayed.
      'lib/features/routine/providers/child_mode_providers.dart':
          'code matching, stored only for diagnostics',
      // Matches a platform exception's message against known transient codes.
      'lib/features/push/push_service.dart': 'not UI',
      // Proof errors whose message is server-written for the parent (§9.0).
      'lib/features/child_memory/widgets/memory_errors.dart':
          'server-written, gated by isProofError',
      'lib/features/child_memory/widgets/proof_views.dart':
          'server-written proof message',
      // A backup file's JSON parse error — the user's own file, not the server.
      'lib/features/program/data/backup_service.dart': 'local file parse',
      // Reads a FlutterError's text to triage it for Crashlytics.
      'lib/core/crash_triage.dart': 'crash triage, not UI',
    };

    final hits = <String>[];
    for (final f in Directory('lib').listSync(recursive: true)) {
      if (f is! File || !f.path.endsWith('.dart')) continue;
      final path = f.path.replaceAll(r'\', '/');
      if (path.startsWith('lib/l10n/')) continue;
      if (allow.containsKey(path)) continue;
      final lines = f.readAsLinesSync();
      for (var i = 0; i < lines.length; i++) {
        final line = lines[i];
        if (exempt(line)) continue;
        if (patterns.any((p) => p.hasMatch(line))) {
          hits.add('$path:${i + 1}: ${line.trim()}');
        }
      }
    }
    expect(hits, isEmpty,
        reason: 'Show friendlyError/describeFailure instead:\n${hits.join('\n')}');
  });
}
