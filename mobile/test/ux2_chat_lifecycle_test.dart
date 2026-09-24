// UX-2 chat lifecycle (UX_UI_ROADMAP §2): token batching keeps what the
// reader saw, the thinking state reassures after 3 s, follow-up chips send,
// and a failed turn carries its own Retry.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/message_bubble.dart';

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

/// Serves the SSE body from a controller the test drives token by token.
class _LiveSseClient extends http.BaseClient {
  final sse = StreamController<List<int>>();

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (request.url.path == '/api/chat/sessions') {
      return http.StreamedResponse(
        Stream.value(utf8.encode(jsonEncode({'session_id': 's1', 'token': 't1'}))),
        201,
        headers: {'content-type': 'application/json'},
      );
    }
    return http.StreamedResponse(sse.stream, 200,
        headers: {'content-type': 'text/event-stream; charset=utf-8'});
  }

  void token(String t) =>
      sse.add(utf8.encode('event: token\ndata: ${jsonEncode({'delta': t})}\n\n'));
}

Widget _host(Widget child) => MaterialApp(
      locale: const Locale('en'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

AssistantReply _reply() => AssistantReply.fromJson({
      'reply_text': 'Answer',
      'domain': 'medical',
      'severity': 'خفيف',
      'needs_human_review': false,
      'escalation_target': null,
      'mode': 'llm_generated',
      'session_id': 's1',
    });

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('batched tokens reach the bubble, and Stop keeps the unflushed tail',
      () async {
    final http_ = _LiveSseClient();
    final tg = TgClient.forTesting(
        baseUrl: 'http://x', httpClient: http_, storage: _MemStorage());
    final notifier = ChatNotifier(tg);
    await notifier.bootstrap();

    unawaited(notifier.sendMessage('question'));
    await Future<void>.delayed(const Duration(milliseconds: 20));
    http_.token('Hel');
    http_.token('lo ');
    await Future<void>.delayed(const Duration(milliseconds: 120));
    expect(notifier.state.messages.last.content, 'Hello ',
        reason: 'batched deltas must land within the flush window');

    http_.token('world');
    await Future<void>.delayed(const Duration(milliseconds: 5));
    notifier.stopStreaming(); // before the 60 ms flush fires
    expect(notifier.state.messages.last.content, 'Hello world');
    expect(notifier.state.phase, ChatPhase.idle);
    notifier.dispose();
    await http_.sse.close();
  });

  test('follow_ups from the server are parsed, capped at three', () {
    final r = AssistantReply.fromJson({
      'reply_text': 'x', 'domain': 'medical', 'severity': 'خفيف',
      'needs_human_review': false, 'escalation_target': null,
      'mode': 'llm_generated', 'session_id': 's',
      'follow_ups': ['a', ' ', 'b', 'c', 'd', 5],
    });
    expect(r.followUps, ['a', 'b', 'c']);
  });

  testWidgets('thinking state adds reassurance copy after 3 s', (t) async {
    final m = ChatMessageUI(id: '1', role: 'assistant', content: '', isStreaming: true);
    await t.pumpWidget(_host(MessageBubble(message: m)));
    final l10n = AppLocalizations.of(t.element(find.byType(MessageBubble)));
    expect(find.text(l10n.chatThinkingSlow), findsNothing);
    await t.pump(const Duration(seconds: 3));
    await t.pump(const Duration(milliseconds: 300));
    expect(find.text(l10n.chatThinkingSlow), findsOneWidget);
    expect(find.text('…'), findsNothing);
  });

  testWidgets('follow-up chips render under a finished answer and send', (t) async {
    final m = ChatMessageUI(id: '2', role: 'assistant', content: 'Answer')
      ..reply = _reply();
    String? sent;
    await t.pumpWidget(_host(MessageBubble(
      message: m,
      followUps: const ['Give me an example'],
      onFollowUp: (q) => sent = q,
    )));
    await t.tap(find.text('Give me an example'));
    expect(sent, 'Give me an example');
  });

  testWidgets('a failed turn carries its own Retry', (t) async {
    final m = ChatMessageUI(id: '3', role: 'assistant', content: '')
      ..error = 'Connection lost';
    var retried = false;
    await t.pumpWidget(_host(MessageBubble(message: m, onRetry: () => retried = true)));
    await t.tap(find.byIcon(Icons.refresh));
    expect(retried, isTrue);
  });
}
