// Leaving the app mid-answer (2026-10 reliability fix).
//
// The chat used to stop a streaming answer on `inactive`/`paused` — the
// notification shade, the app switcher, a screen lock. 23 of 290 parent
// questions in September 2026 ended as a few words and «تم الإيقاف». Now the
// stream keeps running in the background, and if the OS cuts the connection
// anyway, coming back fetches the answer the server finished on its own.
// Against an older server (which never stored it) the turn keeps its Retry.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/screens/chat_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> _store = {};
  @override
  Future<String?> read({required String key, Object? aOptions, Object? iOptions,
          Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async =>
      _store[key];
  @override
  Future<void> write({required String key, required String? value, Object? aOptions,
      Object? iOptions, Object? lOptions, Object? webOptions, Object? mOptions,
      Object? wOptions}) async {
    if (value == null) {
      _store.remove(key);
    } else {
      _store[key] = value;
    }
  }
  @override
  Future<void> delete({required String key, Object? aOptions, Object? iOptions,
          Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async =>
      _store.remove(key);
  @override
  dynamic noSuchMethod(Invocation i) => super.noSuchMethod(i);
}

/// A server: sessions, an SSE stream the test drives, and the history
/// endpoint the app reads when it comes back.
class _Server extends http.BaseClient {
  final sse = StreamController<List<int>>();
  List<Map<String, Object?>> history = [];
  int historyReads = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final path = request.url.path;
    if (path == '/api/chat/sessions' && request.method == 'POST') {
      return _json({'session_id': 's1', 'token': 't1'}, 201);
    }
    if (path == '/api/chat/sessions/s1' && request.method == 'GET') {
      historyReads++;
      return _json({
        'id': 's1',
        'created_at': '2026-10-04T10:00:00',
        'updated_at': '2026-10-04T10:00:00',
        'metadata': <String, Object?>{},
        'messages': history,
      }, 200);
    }
    return http.StreamedResponse(sse.stream, 200,
        headers: {'content-type': 'text/event-stream; charset=utf-8'});
  }

  http.StreamedResponse _json(Object body, int status) => http.StreamedResponse(
        Stream.value(utf8.encode(jsonEncode(body))),
        status,
        headers: {'content-type': 'application/json'},
      );

  void token(String t) =>
      sse.add(utf8.encode('event: token\ndata: ${jsonEncode({'delta': t})}\n\n'));

  void done(String text) => sse.add(utf8.encode('event: done\ndata: ${jsonEncode({
        'reply_text': text,
        'domain': 'medical',
        'severity': 'خفيف',
        'needs_human_review': false,
        'escalation_target': null,
        'mode': 'llm_generated',
        'session_id': 's1',
      })}\n\n'));

  /// The OS drops the connection while the app is in the background.
  void drop() => sse.addError(http.ClientException('Connection closed'));
}

Map<String, Object?> _msg(String role, String content, [String? mode]) => {
      'role': role,
      'content': content,
      'mode': mode,
      'created_at': '2026-10-04T10:00:00',
    };

Future<void> _settle() => Future<void>.delayed(const Duration(milliseconds: 120));

Future<(ChatNotifier, _Server)> _asking(String question) async {
  final server = _Server();
  final tg = TgClient.forTesting(
      baseUrl: 'http://x', httpClient: server, storage: _MemStorage());
  final notifier = ChatNotifier(tg);
  await notifier.bootstrap();
  unawaited(notifier.sendMessage(question));
  await Future<void>.delayed(const Duration(milliseconds: 20));
  return (notifier, server);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('going to the background does not stop a streaming answer', () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.token('Start ');
    await _settle();

    notifier.onAppPaused(); // shade pulled down, app switched, screen locked
    await _settle();
    expect(server.sse.hasListener, isTrue,
        reason: 'the answer must keep streaming while the app is away');

    server.token('and more');
    server.done('Start and more.');
    await _settle();
    final last = notifier.state.messages.last;
    expect(last.content, 'Start and more.');
    expect(last.error, isNull);
    expect(notifier.state.phase, ChatPhase.idle);
    notifier.dispose();
    await server.sse.close();
  });

  test('a waiting answer is not saved as an empty bubble', () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    notifier.onAppPaused(); // before the first word
    await _settle();

    final prefs = await SharedPreferences.getInstance();
    final snap = jsonDecode(prefs.getString('tg.chat_snapshot')!) as Map;
    final roles = (snap['messages'] as List).map((m) => (m as Map)['role']).toList();
    expect(roles, ['user']);
    notifier.dispose();
    await server.sse.close();
  });

  test('connection cut while away: the finished answer is reloaded on resume',
      () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.token('Start ');
    await _settle();
    notifier.onAppPaused();
    server.drop();
    await _settle();
    expect(notifier.state.messages.last.error, isNotNull);

    // A 2026-10 server finished the answer after the reader left.
    server.history = [
      _msg('user', 'How do I calm bedtime?'),
      _msg('assistant', 'Start with a calm, fixed routine.', 'llm_generated'),
    ];
    final restored =
        await notifier.recoverInterruptedAnswer(retryDelay: Duration.zero);

    expect(restored, isTrue);
    final last = notifier.state.messages.last;
    expect(last.content, 'Start with a calm, fixed routine.');
    expect(last.error, isNull);
    expect(notifier.state.phase, ChatPhase.idle);
    notifier.dispose();
  });

  test('older server stored only a fragment: the turn keeps its Retry',
      () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.token('Start ');
    await _settle();
    server.drop();
    await _settle();

    server.history = [
      _msg('user', 'How do I calm bedtime?'),
      _msg('assistant', 'Start', 'interrupted'),
    ];
    final restored = await notifier.recoverInterruptedAnswer(
        attempts: 2, retryDelay: Duration.zero);

    expect(restored, isFalse);
    expect(server.historyReads, 2);
    final last = notifier.state.messages.last;
    expect(last.content, 'Start ');
    expect(last.error, isNotNull, reason: 'Retry must stay on the failed turn');
    expect(notifier.state.phase, ChatPhase.error);
    notifier.dispose();
  });

  test('a server apology is not taken for the answer', () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.drop();
    await _settle();
    server.history = [
      _msg('user', 'How do I calm bedtime?'),
      _msg('assistant', 'تعذّر توليد الرد، يُرجى المحاولة لاحقاً.', 'error'),
    ];
    expect(
        await notifier.recoverInterruptedAnswer(
            attempts: 1, retryDelay: Duration.zero),
        isFalse);
    notifier.dispose();
  });

  test('a live stream is left alone on resume', () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.token('Start ');
    await _settle();

    expect(await notifier.recoverInterruptedAnswer(retryDelay: Duration.zero),
        isFalse);
    expect(server.historyReads, 0);
    expect(notifier.state.phase, ChatPhase.streaming);
    notifier.dispose();
    await server.sse.close();
  });

  testWidgets('the chat screen pauses without stopping and recovers on resume',
      (t) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    await OnboardingStorage(prefs).markOnboardingCompleted();
    final tg = TgClient.forTesting(
        baseUrl: 'http://x', httpClient: _Server(), storage: _MemStorage());
    final spy = _SpyNotifier(tg);
    final container = ProviderContainer(overrides: [
      tgClientProvider.overrideWithValue(tg),
      chatNotifierProvider.overrideWith((ref) => spy),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ]);
    await container.read(sharedPreferencesProvider.future);
    addTearDown(container.dispose);
    await t.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        locale: Locale('en'),
        home: ChatScreen(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
      ),
    ));
    await t.pump(const Duration(milliseconds: 100));

    for (final s in [
      AppLifecycleState.inactive,
      AppLifecycleState.hidden,
      AppLifecycleState.paused,
      AppLifecycleState.hidden,
      AppLifecycleState.inactive,
      AppLifecycleState.resumed,
    ]) {
      t.binding.handleAppLifecycleStateChanged(s);
    }
    await t.pump();

    expect(spy.calls, contains('paused'));
    expect(spy.calls, contains('resumed'));
    expect(spy.calls, isNot(contains('stop')));
  });
}

class _SpyNotifier extends ChatNotifier {
  _SpyNotifier(super.client);
  final calls = <String>[];

  @override
  Future<void> bootstrap() async {}

  @override
  void onAppPaused() {
    calls.add('paused');
    super.onAppPaused();
  }

  @override
  void onAppResumed() {
    calls.add('resumed');
  }

  @override
  void stopStreaming() {
    calls.add('stop');
    super.stopStreaming();
  }
}
