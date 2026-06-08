// Phase 2 unit tests — SSE parser & model decoders.
//
// We exercise the parser by pumping synthetic event streams into a fake
// http.Client. The parser is the most failure-prone piece (event/data line
// splitting, blank-line frame terminator, Arabic UTF-8).

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/models/enums.dart';

/// In-memory fake of `FlutterSecureStorage` for tests.
class _InMemoryStorage implements FlutterSecureStorage {
  final Map<String, String> _store = {};

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
      _store[key];

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
      _store.remove(key);
    } else {
      _store[key] = value;
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
    _store.remove(key);
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  group('SSE parser (event:token / event:done / event:error)', () {
    test('parses a token stream followed by done', () async {
      const body = '''event: token
data: {"delta": "أ"}

event: token
data: {"delta": "ه"}

event: token
data: {"delta": "لا"}

event: done
data: {"reply_text":"أهلا","domain":"islamic_parenting","severity":"خفيف","needs_human_review":true,"escalation_target":null,"mode":"llm_generated","session_id":"abc"}

''';

      final mock = MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/api/assistant/stream');
        return http.Response(body, 200,
            headers: {'content-type': 'text/event-stream'});
      });

      final client = TgClient(httpClient: mock);
      // Pre-seed a session by running createSession (which we also mock).
      // Then call streamQuery.
      // For brevity, build a session via the mock here too.
      final mock2 = MockClient((req) async {
        if (req.url.path == '/api/chat/sessions') {
          return http.Response(
            jsonEncode({'session_id': 's1', 'token': 'tg_tok'}),
            201,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response.bytes(
          utf8.encode(body),
          200,
          headers: {
            'content-type': 'text/event-stream; charset=utf-8',
          },
        );
      });
      final c2 = TgClient(httpClient: mock2, storage: _InMemoryStorage());
      await c2.createSession();

      final events = await c2.streamQuery(
        const AssistantQuery(
          ageGroup: AgeGroup.fourSix,
          severity: Severity.light,
          messageText: 'مرحبا',
        ),
      ).toList();

      // 3 tokens + 1 done.
      expect(events.length, 4);
      expect((events[0] as TgTokenEvent).delta, 'أ');
      expect((events[1] as TgTokenEvent).delta, 'ه');
      expect((events[2] as TgTokenEvent).delta, 'لا');
      final done = events[3] as TgDoneEvent;
      expect(done.reply.replyText, 'أهلا');
      expect(done.reply.domain, Domain.islamicParenting);
      expect(done.reply.severity, Severity.light);
      expect(done.reply.mode, ReplyMode.llmGenerated);
      expect(done.reply.needsHumanReview, true);
      c2.close();
      client.close();
    });

    test('emits stream-error on event:error', () async {
      const body = '''event: error
data: {"detail":"توقف النموذج"}

''';
      final mock = MockClient((req) async {
        if (req.url.path == '/api/chat/sessions') {
          return http.Response(
            jsonEncode({'session_id': 's1', 'token': 'tg_tok'}),
            201,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response.bytes(
          utf8.encode(body),
          200,
          headers: {'content-type': 'text/event-stream; charset=utf-8'},
        );
      });
      final c = TgClient(httpClient: mock, storage: _InMemoryStorage());
      await c.createSession();

      final events = await c.streamQuery(
        const AssistantQuery(
          ageGroup: AgeGroup.fourSix,
          severity: Severity.light,
          messageText: 'x',
        ),
      ).toList();
      expect(events.length, 1);
      expect(events.first, isA<TgStreamError>());
      expect((events.first as TgStreamError).detail, 'توقف النموذج');
      c.close();
    });
  });

  group('AssistantReply.fromJson', () {
    test('decodes a banned reply', () {
      final r = AssistantReply.fromJson({
        'reply_text': 'خارج النطاق',
        'domain': 'medical',
        'severity': 'طارئ',
        'needs_human_review': true,
        'escalation_target': 'emergency_services',
        'mode': 'banned',
        'session_id': null,
      });
      expect(r.isBanned, true);
      expect(r.isEmergency, true);
      expect(r.escalationTarget, EscalationTarget.emergencyServices);
    });

    test('ignores unknown fields (additive contract)', () {
      final r = AssistantReply.fromJson({
        'reply_text': 'ok',
        'domain': 'medical',
        'severity': 'خفيف',
        'needs_human_review': false,
        'escalation_target': null,
        'mode': 'retrieval_only',
        'session_id': 's',
        'future_field': 12345,
        'metadata': {'trace_id': 'abc'},
      });
      expect(r.replyText, 'ok');
      expect(r.metadata?['trace_id'], 'abc');
    });
  });

  group('AssistantQuery.toJson', () {
    test('omits behavior_type when empty and includes session_id', () {
      final j = const AssistantQuery(
        ageGroup: AgeGroup.sevenNine,
        severity: Severity.moderate,
        messageText: 'سؤال',
        sessionId: 's1',
      ).toJson();
      expect(j['age_group'], '7-9');
      expect(j['severity'], 'متوسط');
      expect(j['message_text'], 'سؤال');
      expect(j['session_id'], 's1');
      expect(j.containsKey('behavior_type'), false);
    });
  });
}
