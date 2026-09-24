// Audit M12 / M13 / H5 (client side): one shared client, one session mint at
// a time, a 401 renews the session once and replays the request, and a reply
// stream that goes silent ends with a retryable error instead of hanging.

import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/l10n_global.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/models/enums.dart';
import 'package:almorabbi/state/chat_notifier.dart';

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> store = {};

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async =>
      store[key];

  @override
  Future<void> write({
    required String key,
    required String? value,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (value == null) {
      store.remove(key);
    } else {
      store[key] = value;
    }
  }

  @override
  Future<void> delete({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    store.remove(key);
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// A fake server: mints tok1, tok2, … and accepts only the newest token.
class _Server {
  int mints = 0;
  final proofs = <String?>[];
  bool mintFails = false;

  String get current => 'tok$mints';

  Future<http.Response> handle(http.Request req) async {
    if (req.method == 'POST' && req.url.path == '/api/chat/sessions') {
      proofs.add(req.headers['Authorization']);
      if (mintFails) return http.Response('{"detail":"down"}', 500);
      mints++;
      return http.Response(
        jsonEncode({'session_id': 's$mints', 'token': current}),
        201,
        headers: {'content-type': 'application/json'},
      );
    }
    final auth = req.headers['Authorization'];
    if (auth != 'Bearer $current') {
      return http.Response.bytes(
          utf8.encode('{"detail":"Token غير صالح أو منتهي."}'), 401);
    }
    return http.Response(
      jsonEncode({'children': [], 'seen_token': auth}),
      200,
      headers: {'content-type': 'application/json'},
    );
  }
}

const _q = AssistantQuery(
  ageGroup: AgeGroup.fourSix,
  severity: Severity.light,
  messageText: 'مرحبا',
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('session recovery (H5 client side)', () {
    test('an expired token is renewed once and the request replayed', () async {
      final server = _Server();
      final c = TgClient.forTesting(
        baseUrl: 'http://t',
        httpClient: MockClient(server.handle),
        storage: _MemStorage(),
      );
      await c.createSession(); // tok1
      server.mints++; // the server "expires" tok1: only tok2 would pass

      // Simulate: tok1 is refused; recovery mints tok3 which is current.
      final out = await c.listChildren();

      expect(out['seen_token'], 'Bearer tok3');
      expect(server.mints, 3);
      // The expired token proved the device when minting its successor.
      expect(server.proofs.last, 'Bearer tok1');
      // A renewed token, not a new conversation.
      expect(await c.currentSessionId(), 's1');
    });

    test('when renewal fails the original 401 reaches the caller', () async {
      final server = _Server();
      final c = TgClient.forTesting(
        baseUrl: 'http://t',
        httpClient: MockClient(server.handle),
        storage: _MemStorage(),
      );
      await c.createSession();
      server.mints++; // tok1 expires
      server.mintFails = true;
      await expectLater(
        c.listChildren(),
        throwsA(isA<TgApiError>().having((e) => e.statusCode, 'status', 401)),
      );
    });

    test('child-mode calls are never replayed with a parent session', () async {
      var mints = 0;
      final c = TgClient.forTesting(
        baseUrl: 'http://t',
        storage: _MemStorage(),
        httpClient: MockClient((req) async {
          if (req.url.path == '/api/chat/sessions') {
            mints++;
            return http.Response(
                jsonEncode({'session_id': 's', 'token': 't$mints'}), 201);
          }
          return http.Response('{"detail":"x"}', 401);
        }),
      );
      await c.createSession();
      await expectLater(
        c.fetchChildAgreement('child-token'),
        throwsA(isA<TgApiError>().having((e) => e.statusCode, 'status', 401)),
      );
      expect(mints, 1); // no parent session was minted for a child call
    });
  });

  group('shared client (M12)', () {
    test('concurrent ensureSession calls mint exactly one session', () async {
      final server = _Server();
      final gate = Completer<void>();
      final c = TgClient.forTesting(
        baseUrl: 'http://t',
        storage: _MemStorage(),
        httpClient: MockClient((req) async {
          await gate.future; // hold the mint so every caller overlaps
          return server.handle(req);
        }),
      );
      final calls = List.generate(5, (_) => c.ensureSession());
      gate.complete();
      final sessions = await Future.wait(calls);
      expect(server.mints, 1);
      expect(sessions.map((s) => s.token).toSet(), {'tok1'});
    });

    test('tgClientProvider hands out the shared instance and never closes it',
        () async {
      final previous = TgClient.shared;
      final mine = TgClient.forTesting(baseUrl: 'http://t', storage: _MemStorage());
      TgClient.shared = mine;
      try {
        final container = ProviderContainer();
        expect(container.read(tgClientProvider), same(mine));
        expect(mine.onNeedActiveChildId, isNotNull);
        container.dispose();
        expect(mine.onNeedActiveChildId, isNull);
        expect(TgClient.shared, same(mine)); // still usable by services
      } finally {
        TgClient.shared = previous;
      }
    });
  });

  group('stream idle timeout (M13)', () {
    Future<List<TgStreamEvent>> run(
      Stream<List<int>> Function() body, {
      Duration idle = const Duration(milliseconds: 120),
    }) async {
      final c = TgClient.forTesting(
        baseUrl: 'http://t',
        storage: _MemStorage(),
        streamIdleTimeout: idle,
        httpClient: MockClient.streaming((req, _) async {
          if (req.url.path == '/api/chat/sessions') {
            return http.StreamedResponse(
              Stream.value(utf8.encode(jsonEncode({'session_id': 's', 'token': 't'}))),
              201,
            );
          }
          return http.StreamedResponse(body(), 200,
              headers: {'content-type': 'text/event-stream'});
        }),
      );
      await c.createSession();
      return c.streamQuery(_q).toList();
    }

    test('a stream that goes silent ends with a stalled error', () async {
      final events = await run(() {
        final ctl = StreamController<List<int>>();
        ctl.add(utf8.encode('event: token\ndata: {"delta":"أ"}\n\n'));
        return ctl.stream; // never closes, never sends again
      });
      expect(events, hasLength(2));
      expect((events.first as TgTokenEvent).delta, 'أ');
      expect((events.last as TgStreamError).detail, AppL10n.current.apiStreamStalled);
    });

    test('keep-alive comments hold the stream open past the idle limit', () async {
      final events = await run(() async* {
        for (var i = 0; i < 5; i++) {
          await Future<void>.delayed(const Duration(milliseconds: 60));
          yield utf8.encode(': keep-alive\n\n'); // 300 ms total > 120 ms idle
        }
        yield utf8.encode('event: token\ndata: {"delta":"ب"}\n\n');
        yield utf8.encode(
            'event: done\ndata: {"reply_text":"ب","domain":"general","severity":"خفيف",'
            '"needs_human_review":false,"escalation_target":null,"mode":"llm_generated"}\n\n');
      });
      expect(events.whereType<TgStreamError>(), isEmpty);
      expect(events.last, isA<TgDoneEvent>());
    });
  });
}
