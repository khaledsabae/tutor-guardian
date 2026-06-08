// Phase 4 lifecycle tests — bootstrap rehydration + session recycling.
//
// We use a custom BaseClient (so we can return a real StreamedResponse for
// the SSE path) and an in-memory FlutterSecureStorage to drive the
// notifier through realistic app restart sequences:
//   1. Cold start with no persisted session → createSession called.
//   2. Cold start with a persisted (still-valid) session → getHistory
//      called and messages rehydrated.
//   3. Cold start with a session that returns 404 → storage is cleared
//      and a new session is created transparently.
//   4. 401 mid-turn → the notifier catches it, clears the session,
//      creates a new one, and retries the request exactly once.

import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/state/chat_notifier.dart';

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> _store = {};
  @override
  Future<String?> read({
    required String key,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async =>
      _store[key];
  @override
  Future<void> write({
    required String key,
    required String? value,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async {
    if (value == null) {
      _store.remove(key);
    } else {
      _store[key] = value;
    }
  }
  @override
  Future<void> delete({
    required String key,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async =>
      _store.remove(key);
  @override
  noSuchMethod(Invocation i) => super.noSuchMethod(i);
}

/// A scripted BaseClient — handlers are popped off in FIFO order.
class _ScriptedClient extends http.BaseClient {
  final List<http.StreamedResponse Function(http.BaseRequest req)> handlers = [];
  final List<http.Request> seen = [];

  void route(http.StreamedResponse Function(http.BaseRequest) h) =>
      handlers.add(h);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    seen.add(request as http.Request);
    if (handlers.isEmpty) {
      return http.StreamedResponse(
        Stream.value(utf8.encode('{}')),
        500,
        headers: {'content-type': 'application/json'},
      );
    }
    return handlers.removeAt(0)(request);
  }
}

http.StreamedResponse _sseOkResponse() {
  const sse = '''event: token
data: {"delta": "في "}

event: token
data: {"delta": "هذه "}

event: token
data: {"delta": "الحالة."}

event: done
data: {"reply_text":"في هذه الحالة.","domain":"medical","severity":"خفيف","needs_human_review":true,"escalation_target":null,"mode":"llm_generated","session_id":"s1"}

''';
  return http.StreamedResponse(
    Stream.value(utf8.encode(sse)),
    200,
    headers: {'content-type': 'text/event-stream; charset=utf-8'},
  );
}

http.StreamedResponse _jsonResponse(int status, Object body) {
  return http.StreamedResponse(
    Stream.value(utf8.encode(jsonEncode(body))),
    status,
    headers: {'content-type': 'application/json'},
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('Cold start: no persisted session → createSession is called',
      () async {
    final storage = _MemStorage();
    final client = _ScriptedClient();
    client.route((_) => _jsonResponse(201,
        {'session_id': 'new-1', 'token': 'tg_new'}));

    final tg = TgClient.forTesting(
      baseUrl: 'http://x',
      httpClient: client,
      storage: storage,
    );
    final notifier = ChatNotifier(tg);

    await notifier.bootstrap();

    expect(notifier.state.sessionId, 'new-1');
    expect(notifier.state.messages, isEmpty);
    expect(notifier.state.turnCount, 0);
    expect(await storage.read(key: 'tg_session_id'), 'new-1');
    expect(await storage.read(key: 'tg_token'), 'tg_new');
  });

  test('Cold start: persisted valid session → getHistory rehydrates',
      () async {
    final storage = _MemStorage();
    await storage.write(key: 'tg_session_id', value: 'old-1');
    await storage.write(key: 'tg_token', value: 'tg_old');

    final client = _ScriptedClient();
    client.route((req) {
      expect(req.url.path, '/api/chat/sessions/old-1');
      return _jsonResponse(200, {
        'id': 'old-1',
        'device_id': 'd',
        'created_at': '2026-06-08T10:00:00',
        'updated_at': '2026-06-08T10:01:00',
        'metadata': <String, dynamic>{},
        'messages': [
          {
            'role': 'user',
            'content': 'سؤال ١',
            'domain': null,
            'severity': null,
            'mode': null,
            'needs_human_review': false,
            'created_at': '2026-06-08T10:00:00',
          },
          {
            'role': 'assistant',
            'content': 'جواب ١',
            'domain': 'medical',
            'severity': 'خفيف',
            'mode': 'llm_generated',
            'needs_human_review': true,
            'created_at': '2026-06-08T10:00:30',
          },
        ],
      });
    });

    final tg = TgClient.forTesting(
      baseUrl: 'http://x',
      httpClient: client,
      storage: storage,
    );
    final notifier = ChatNotifier(tg);

    await notifier.bootstrap();

    expect(notifier.state.sessionId, 'old-1');
    expect(notifier.state.messages.length, 2);
    expect(notifier.state.messages[0].role, 'user');
    expect(notifier.state.messages[0].content, 'سؤال ١');
    expect(notifier.state.messages[1].content, 'جواب ١');
    expect(notifier.state.turnCount, 1);
  });

  test('Cold start: persisted session 404 → storage cleared + new session',
      () async {
    final storage = _MemStorage();
    await storage.write(key: 'tg_session_id', value: 'stale-1');
    await storage.write(key: 'tg_token', value: 'tg_stale');

    final client = _ScriptedClient();
    client.route((req) =>
        _jsonResponse(404, {'detail': 'Session not found'}));
    client.route((_) => _jsonResponse(201,
        {'session_id': 'fresh-1', 'token': 'tg_fresh'}));

    final tg = TgClient.forTesting(
      baseUrl: 'http://x',
      httpClient: client,
      storage: storage,
    );
    final notifier = ChatNotifier(tg);

    await notifier.bootstrap();

    expect(notifier.state.sessionId, 'fresh-1');
    expect(await storage.read(key: 'tg_session_id'), 'fresh-1');
    expect(await storage.read(key: 'tg_token'), 'tg_fresh');
  });

  test('sendMessage: 401 mid-stream triggers transparent session rotation',
      () async {
    final storage = _MemStorage();
    await storage.write(key: 'tg_session_id', value: 'orig-1');
    await storage.write(key: 'tg_token', value: 'tg_orig');

    final client = _ScriptedClient();
    // Bootstrap re-checks the session: 404 → rotate.
    client.route((_) => _jsonResponse(404, {'detail': 'not found'}));
    client.route((_) => _jsonResponse(201,
        {'session_id': 'rot-1', 'token': 'tg_rot'}));

    // First stream attempt with rot-1: still 401.
    client.route(
        (_) => _jsonResponse(401, {'detail': 'Token غير صالح.'}));

    // sendMessage catches 401, clears, creates rot-2.
    client.route((_) => _jsonResponse(201,
        {'session_id': 'rot-2', 'token': 'tg_rot2'}));

    // Second stream attempt: SSE success.
    client.route((_) => _sseOkResponse());

    final tg = TgClient.forTesting(
      baseUrl: 'http://x',
      httpClient: client,
      storage: storage,
    );
    final notifier = ChatNotifier(tg);

    await notifier.bootstrap();
    await notifier.sendMessage('ابني يخاف من الظلام');

    expect(notifier.state.sessionId, 'rot-2');
    expect(notifier.state.phase, ChatPhase.idle);
    expect(notifier.state.messages.length, 2);
    expect(notifier.state.messages[1].content, 'في هذه الحالة.');
    expect(notifier.state.messages[1].reply, isNotNull);
    expect(notifier.state.turnCount, 1);
  });
}
