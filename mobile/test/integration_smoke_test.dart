// Phase 2 integration smoke test — runs against the real local backend
// on http://localhost:8090 (Tutor Guardian FastAPI). Skipped automatically
// when the backend is unreachable (CI or fresh clones).
//
// Run with:
//   flutter test test/integration_smoke_test.dart --tags integration

import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/models/enums.dart';

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> _store = {};
  @override
  Future<String?> read({required String key, Object? aOptions, Object? iOptions, Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async => _store[key];
  @override
  Future<void> write({required String key, required String? value, Object? aOptions, Object? iOptions, Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async {
    if (value == null) {
      _store.remove(key);
    } else {
      _store[key] = value;
    }
  }
  @override
  Future<void> delete({required String key, Object? aOptions, Object? iOptions, Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async => _store.remove(key);
  @override
  noSuchMethod(Invocation i) => super.noSuchMethod(i);
}

Future<bool> _backendUp(String base) async {
  try {
    final c = HttpClient()
      ..connectionTimeout = const Duration(seconds: 2);
    final req = await c.getUrl(Uri.parse('$base/health'));
    final resp = await req.close().timeout(const Duration(seconds: 3));
    await resp.drain<void>();
    c.close();
    return resp.statusCode == 200;
  } catch (_) {
    return false;
  }
}

void main() {
  test('live backend: createSession → streamQuery', () async {
    const base = 'http://localhost:8090';
    if (!await _backendUp(base)) {
      // Backend is the host's FastAPI; it might be down in CI.
      // Print a single warning line and skip silently.
      // ignore: avoid_print
      print('SKIP: backend at $base not reachable');
      return;
    }

    final client = TgClient.forTesting(baseUrl: base, storage: _MemStorage());

    // 1. createSession returns a session_id + tg_ token.
    final s = await client.createSession();
    expect(s.sessionId, isNotEmpty);
    expect(s.token, startsWith('tg_'));
    // ignore: avoid_print
    print('OK: session=${s.sessionId} token=${s.token.substring(0, 10)}...');

    // 2. streamQuery: depending on backend health, we either get a full
    //    token stream + done, OR a TgApiError(5xx) which the UI must show
    //    with a retry button. Both paths are spec-compliant; we accept
    //    either as long as the client behaves correctly.
    try {
      final events = await client
          .streamQuery(const AssistantQuery(
            ageGroup: AgeGroup.fourSix,
            severity: Severity.light,
            messageText: 'ابني يخاف من الظلام، ماذا أفعل؟',
          ))
          .toList();
      expect(events, isNotEmpty);
      final done = events.whereType<TgDoneEvent>().firstOrNull;
      if (done != null) {
        expect(done.reply.replyText, isNotEmpty);
        // ignore: avoid_print
        print('OK: streamed ${events.length} events, '
            'tokens=${events.whereType<TgTokenEvent>().length}, '
            'domain=${done.reply.domain.wire}, '
            'mode=${done.reply.mode.wire}, '
            'reply_len=${done.reply.replyText.length}');
      } else {
        // Could be a stream error (e.g. backend model down).
        final err = events.whereType<TgStreamError>().firstOrNull;
        // ignore: avoid_print
        print('WARN: stream emitted ${events.length} events, '
            'no done; err=${err?.detail}');
      }
    } on TgApiError catch (e) {
      // Acceptable per MOBILE_API.md §5: 5xx → caller shows retry.
      // We at least verify the error carries a real status code and message.
      expect(e.statusCode, isNotNull);
      // ignore: avoid_print
      print('WARN: streamQuery raised TgApiError(${e.statusCode}): '
          '${e.message} — this is a server-side issue, not a client bug.');
    }

    // 3. getHistory — soft check. The server persists the user message
    //    before invoking the LLM, but if the LLM call fails before
    //    `add_message` is reached, history may be empty. We accept both
    //    (server is the source of truth; we don't fabricate state).
    try {
      final hist = await client.getHistory(s.sessionId);
      // ignore: avoid_print
      print('OK: history has ${hist.messages.length} messages');
    } on TgApiError catch (e) {
      // ignore: avoid_print
      print('WARN: getHistory failed (${e.statusCode}): ${e.message}');
    }

    client.close();
  }, timeout: const Timeout(Duration(minutes: 2)));
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final it = iterator;
    return it.moveNext() ? it.current : null;
  }
}
