// A read that meets the server mid-restart is tried again; a write never is,
// and the app's own 503s (JSON with a reason) are shown at once.
import 'dart:convert';

import 'package:almorabbi/api/tg_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _instant = [
  Duration.zero,
  Duration.zero,
  Duration.zero,
  Duration.zero,
  Duration.zero,
];

http.Response _lesson() => http.Response.bytes(
  utf8.encode(jsonEncode({'id': 'l1', 'title': 'درس'})),
  200,
  headers: {'content-type': 'application/json'},
);

http.Response _gateway(int code) => http.Response(
  '<html>Bad gateway</html>',
  code,
  headers: {'content-type': 'text/html'},
);

({TgClient client, List<String> seen}) _client(
  Future<http.Response> Function(http.Request req, int n) answer, {
  List<Duration>? delays = _instant,
}) {
  final seen = <String>[];
  final client = TgClient.forTesting(
    baseUrl: 'https://api.test',
    transientRetryDelays: delays,
    httpClient: MockClient((req) async {
      seen.add('${req.method} ${req.url.path}');
      return answer(req, seen.length);
    }),
  );
  return (client: client, seen: seen);
}

void main() {
  test(
    'a read that meets a restart (502) is answered on the next try',
    () async {
      final c = _client((_, n) async => n < 3 ? _gateway(502) : _lesson());
      final lesson = await c.client.getLesson('l1');
      expect(lesson, isNotNull);
      expect(c.seen, hasLength(3));
    },
  );

  test('gives up after the last wait and shows the 502 as before', () async {
    final c = _client((_, _) async => _gateway(502));
    await expectLater(
      c.client.getLesson('l1'),
      throwsA(isA<TgApiError>().having((e) => e.statusCode, 'status', 502)),
    );
    expect(c.seen, hasLength(_instant.length + 1));
  });

  test('the app\'s own 503 (JSON with a reason) is shown at once', () async {
    final c = _client(
      (_, _) async => http.Response(
        jsonEncode({'detail': 'program_unavailable'}),
        503,
        headers: {'content-type': 'application/json'},
      ),
    );
    await expectLater(c.client.getLesson('l1'), throwsA(isA<TgApiError>()));
    expect(c.seen, hasLength(1));
  });

  test('a 500 is a bug, not a restart: no retry', () async {
    final c = _client((_, _) async => http.Response('boom', 500));
    await expectLater(c.client.getLesson('l1'), throwsA(isA<TgApiError>()));
    expect(c.seen, hasLength(1));
  });

  test('a long Retry-After is respected by not retrying', () async {
    final c = _client(
      (_, _) async => http.Response(
        'busy',
        503,
        headers: {'content-type': 'text/plain', 'retry-after': '120'},
      ),
    );
    await expectLater(c.client.getLesson('l1'), throwsA(isA<TgApiError>()));
    expect(c.seen, hasLength(1));
  });

  test('a write is never repeated, even on a 502', () async {
    var calls = 0;
    final client = TransientRetryClient(
      MockClient((_) async {
        calls++;
        return _gateway(502);
      }),
      _instant,
    );
    final r = await client.post(
      Uri.parse('https://api.test/api/x'),
      body: '{}',
    );
    expect(r.statusCode, 502);
    expect(calls, 1);
  });

  test('an injected transport does not retry unless a test asks', () async {
    final c = _client((_, _) async => _gateway(502), delays: null);
    await expectLater(c.client.getLesson('l1'), throwsA(isA<TgApiError>()));
    expect(c.seen, hasLength(1));
  });

  test('the production waits fit inside one request timeout', () {
    final total = kTransientRetryDelays.fold(Duration.zero, (a, b) => a + b);
    expect(total, lessThanOrEqualTo(const Duration(seconds: 30)));
    expect(kTransientRetryDelays, isNotEmpty);
  });
}
