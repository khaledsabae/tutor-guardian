// Leaving the app mid-answer (2026-10 reliability fix + PR #24 review).
//
// The chat used to stop a streaming answer on `inactive`/`paused` — the
// notification shade, the app switcher, a screen lock. 23 of 290 parent
// questions in September 2026 ended as a few words and «تم الإيقاف». Now the
// stream keeps running in the background, and if the connection is cut
// anyway, the answer the server finished on its own is fetched — matched by
// the id the server gave the question (M1), retried with backoff and also
// after a stream error (M2), only for turns really cut on this side (M4).
// Probes 1–4 are the review's scenarios (/tmp/review-pr24/mobile-probe).

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
import 'package:almorabbi/l10n/l10n_global.dart';
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

/// A server: sessions, one scripted SSE stream per question (or an HTTP
/// status), the history endpoint, and the stop endpoint.
class _Server extends http.BaseClient {
  _Server({this.sendsTurns = true});

  /// Servers before 2026-10 send no `turn` frame and no message ids.
  final bool sendsTurns;

  /// Send the `turn` frame as the stream opens (servers since round 2 of
  /// PR #24); false = the test sends it with [turn], after "thinking".
  bool turnAtOpen = true;

  /// Holds history reads until completed — a fetch still in flight.
  Completer<void>? historyGate;
  final streams = <StreamController<List<int>>>[];
  final statuses = <int?>[]; // per question: null = SSE stream, else that status
  int streamCalls = 0;
  int nextId = 1;
  List<Map<String, Object?>> history = [];
  int historyReads = 0;
  final stops = <Map<String, Object?>>[];
  int feedbackStatus = 201;

  StreamController<List<int>> get sse => streams.last;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final path = request.url.path;
    if (path == '/api/chat/sessions' && request.method == 'POST') {
      return _json({'session_id': 's1', 'token': 't1'}, 201);
    }
    if (path.startsWith('/api/chat/sessions/') &&
        !path.endsWith('/stop') &&
        request.method == 'GET') {
      historyReads++;
      final gate = historyGate;
      if (gate != null) await gate.future;
      return _json({
        'id': path.split('/').last,
        'created_at': '2026-10-04T10:00:00',
        'updated_at': '2026-10-04T10:00:00',
        'metadata': <String, Object?>{},
        'messages': history,
      }, 200);
    }
    if (path == '/api/chat/sessions/s1/stop') {
      final body = (request as http.Request).body;
      stops.add(body.isEmpty ? {} : jsonDecode(body) as Map<String, Object?>);
      return _json({'stopped': true}, 200);
    }
    if (path == '/api/feedback') {
      return _json({'detail': 'boom'}, feedbackStatus);
    }
    final i = streamCalls++;
    final st = i < statuses.length ? statuses[i] : null;
    if (st != null) {
      return _json({'detail': 'طلبات كثيرة، يُرجى المحاولة بعد قليل.'}, st);
    }
    final c = StreamController<List<int>>();
    streams.add(c);
    if (sendsTurns && turnAtOpen) {
      c.add(utf8.encode('event: turn\ndata: ${jsonEncode({'message_id': nextId})}\n\n'));
    }
    return http.StreamedResponse(c.stream, 200,
        headers: {'content-type': 'text/event-stream; charset=utf-8'});
  }

  http.StreamedResponse _json(Object body, int status) => http.StreamedResponse(
        Stream.value(utf8.encode(jsonEncode(body))),
        status,
        headers: {'content-type': 'application/json'},
      );

  void token(String t) =>
      sse.add(utf8.encode('event: token\ndata: ${jsonEncode({'delta': t})}\n\n'));

  void turn(int id) =>
      sse.add(utf8.encode('event: turn\ndata: ${jsonEncode({'message_id': id})}\n\n'));

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

Map<String, Object?> _msg(String role, String content, [String? mode, int? id]) => {
      'id': ?id,
      'role': role,
      'content': content,
      'mode': mode,
      'created_at': '2026-10-04T10:00:00',
    };

Future<void> _settle() => Future<void>.delayed(const Duration(milliseconds: 120));

Future<(ChatNotifier, _Server)> _asking(String question,
    {_Server? server, Duration recoveryDelay = const Duration(seconds: 2)}) async {
  final s = server ?? _Server();
  final tg = TgClient.forTesting(baseUrl: 'http://x', httpClient: s, storage: _MemStorage());
  final notifier = ChatNotifier(tg, recoveryDelay: recoveryDelay);
  await notifier.bootstrap();
  unawaited(notifier.sendMessage(question));
  await Future<void>.delayed(const Duration(milliseconds: 20));
  return (notifier, s);
}

const _chip = 'أعطني مثالاً عمليًا'; // a generic follow-up chip, sent more than once

/// Polls [check] until true; fails after [within].
Future<void> _until(bool Function() check,
    {Duration within = const Duration(seconds: 5), String? reason}) async {
  final sw = Stopwatch()..start();
  while (!check()) {
    if (sw.elapsed > within) fail('timed out: ${reason ?? 'condition'}');
    await Future<void>.delayed(const Duration(milliseconds: 10));
  }
}

/// A notifier restarted on a session the server already has (cold start).
Future<(ChatNotifier, _Server)> _coldStart(_Server server,
    {Map<String, Object>? prefs, Duration recoveryDelay = const Duration(milliseconds: 30)}) async {
  SharedPreferences.setMockInitialValues(prefs ?? {});
  final storage = _MemStorage();
  await storage.write(key: 'tg_session_id', value: 's1');
  await storage.write(key: 'tg_token', value: 't1');
  final tg = TgClient.forTesting(baseUrl: 'http://x', httpClient: server, storage: storage);
  final n = ChatNotifier(tg, recoveryDelay: recoveryDelay);
  await n.bootstrap();
  return (n, server);
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

  test('connection cut: the finished answer is found by the question id',
      () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.token('Start ');
    await _settle();
    expect(notifier.state.messages.last.turnId, 1);
    // A server since 2026-10 finished the answer after the reader left.
    server.history = [
      _msg('user', 'How do I calm bedtime?', null, 1),
      _msg('assistant', 'Start with a calm, fixed routine.', 'llm_generated', 2),
    ];
    server.drop();
    await _settle();
    final last = notifier.state.messages.last;
    // M2 — the stream's own error starts the recovery; no resume needed.
    expect(last.content, 'Start with a calm, fixed routine.');
    expect(last.error, isNull);
    expect(last.interrupted, isFalse);
    expect(notifier.state.phase, ChatPhase.idle);
    notifier.dispose();
  });

  test('older server stored only a fragment: the turn keeps its Retry',
      () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.token('Start ');
    await _settle();
    server.history = [
      _msg('user', 'How do I calm bedtime?', null, 1),
      _msg('assistant', 'Start', 'interrupted', 2),
    ];
    server.drop();
    await _settle();
    final restored = await notifier.recoverInterruptedAnswer(
        attempts: 2, retryDelay: Duration.zero);

    expect(restored, isFalse);
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
      _msg('user', 'How do I calm bedtime?', null, 1),
      _msg('assistant', 'تعذّر توليد الرد، يُرجى المحاولة لاحقاً.', 'error', 2),
    ];
    expect(
        await notifier.recoverInterruptedAnswer(attempts: 1, retryDelay: Duration.zero),
        isFalse);
    notifier.dispose();
  });

  test('a live stream is left alone on resume', () async {
    final (notifier, server) = await _asking('How do I calm bedtime?');
    server.token('Start ');
    await _settle();

    expect(await notifier.recoverInterruptedAnswer(retryDelay: Duration.zero), isFalse);
    expect(server.historyReads, 0);
    expect(notifier.state.phase, ChatPhase.streaming);
    notifier.dispose();
    await server.sse.close();
  });

  test('PROBE 1: a re-sent chip rejected with 429 never takes an earlier answer',
      () async {
    // M1 — matching by text restored "EXAMPLE ABOUT LYING" under a chip that
    // the server never received.
    final server = _Server()..statuses.addAll([null, null, null, 429]);
    final tg = TgClient.forTesting(baseUrl: 'http://x', httpClient: server, storage: _MemStorage());
    final n = ChatNotifier(tg);
    await n.bootstrap();
    for (final (q, a) in [
      ('ابني يكذب كثيرًا فماذا أفعل؟', 'A1 about lying'),
      (_chip, 'EXAMPLE ABOUT LYING'),
      ('ابنتي تنفجر غضبًا عند النوم', 'A3 about tantrums'),
    ]) {
      server.nextId += 2;
      unawaited(n.sendMessage(q));
      await _settle();
      server.done(a);
      await _settle();
    }
    unawaited(n.sendMessage(_chip)); // → 429, never stored server-side
    await _settle();
    expect(n.state.messages.last.error, isNotNull);
    server.history = [
      _msg('user', 'ابني يكذب كثيرًا فماذا أفعل؟', null, 3),
      _msg('assistant', 'A1 about lying', 'llm_generated', 4),
      _msg('user', _chip, null, 5),
      _msg('assistant', 'EXAMPLE ABOUT LYING', 'llm_generated', 6),
      _msg('user', 'ابنتي تنفجر غضبًا عند النوم', null, 7),
      _msg('assistant', 'A3 about tantrums', 'llm_generated', 8),
    ];
    expect(await n.recoverInterruptedAnswer(attempts: 1, retryDelay: Duration.zero),
        isFalse);
    expect(n.state.messages.last.content, isNot('EXAMPLE ABOUT LYING'));
    expect(server.historyReads, 0, reason: 'a rejected request is not a cut answer');
    n.dispose();
  });

  test('PROBE 2: an answer cut after interrupt-by-send never gets the previous one',
      () async {
    // M1/M3 — the old server stored A1 after Q2; text matching then put A1
    // under Q2. The server now keeps Q1, A1, Q2 in order and the app matches
    // by Q2's id, so nothing is restored until A2 itself exists.
    final server = _Server();
    final tg = TgClient.forTesting(baseUrl: 'http://x', httpClient: server, storage: _MemStorage());
    final n = ChatNotifier(tg);
    await n.bootstrap();
    server.nextId = 1;
    unawaited(n.sendMessage('Q1 bedtime'));
    await _settle();
    server.token('Start of A1 ');
    await _settle();
    server.nextId = 3;
    unawaited(n.sendMessage('Q2 screens')); // interrupts Q1 locally
    await _settle();
    server.token('Start of A2 ');
    await _settle();
    server.history = [
      _msg('user', 'Q1 bedtime', null, 1),
      _msg('assistant', 'Start of A1', 'interrupted', 2),
      _msg('user', 'Q2 screens', null, 3),
    ];
    server.drop();
    await _settle();
    expect(await n.recoverInterruptedAnswer(attempts: 1, retryDelay: Duration.zero),
        isFalse);
    expect(n.state.messages.last.content, 'Start of A2 ');

    server.history = [
      ...server.history,
      _msg('assistant', 'FULL A2 (screens)', 'llm_generated', 4),
    ];
    expect(await n.recoverInterruptedAnswer(attempts: 1, retryDelay: Duration.zero),
        isTrue);
    expect(n.state.messages.last.content, 'FULL A2 (screens)');
    n.dispose();
  });

  test('PROBE 3: resume before the dead socket is noticed still recovers',
      () async {
    // M2 — resume arrived while the phase was still "streaming": it returned
    // without fetching, and nothing looked again after the socket died.
    final (n, server) = await _asking('Q bedtime');
    server.token('Start ');
    await _settle();
    n.onAppPaused();
    server.history = [
      _msg('user', 'Q bedtime', null, 1),
      _msg('assistant', 'Start — the server finished the answer', 'llm_generated', 2),
    ];
    n.onAppResumed(); // lifecycle event first…
    await _settle();
    server.drop(); // …then the dead socket is noticed
    await _settle();
    expect(n.state.messages.last.content, 'Start — the server finished the answer');
    expect(n.state.phase, ChatPhase.idle);
    n.dispose();
  });

  test('PROBE 4: a rating that failed to save is not a lost answer', () async {
    // M4 — any error on the last bubble was taken for an interruption:
    // a refetch and a turnCount bump on every resume.
    final server = _Server()..feedbackStatus = 500;
    final tg = TgClient.forTesting(baseUrl: 'http://x', httpClient: server, storage: _MemStorage());
    final n = ChatNotifier(tg);
    await n.bootstrap();
    unawaited(n.sendMessage('Q bedtime'));
    await _settle();
    server.done('Full answer');
    await _settle();
    final before = n.state.turnCount;
    await n.submitFeedback(n.state.messages.last.id, 'up');
    expect(n.state.messages.last.error, isNotNull);
    server.history = [
      _msg('user', 'Q bedtime', null, 1),
      _msg('assistant', 'Full answer', 'llm_generated', 2),
    ];
    expect(await n.recoverInterruptedAnswer(retryDelay: Duration.zero), isFalse);
    expect(n.state.turnCount, before);
    expect(server.historyReads, 0);
    n.dispose();
  });

  test('Retry first takes the answer the server already finished', () async {
    // M2 — Retry generated the answer a second time (two answers stored).
    final (n, server) = await _asking('Q bedtime');
    server.token('Start ');
    await _settle();
    server.drop();
    await _settle(); // background recovery finds nothing yet
    final callsBefore = server.streamCalls;
    server.history = [
      _msg('user', 'Q bedtime', null, 1),
      _msg('assistant', 'Start and the rest', 'llm_generated', 2),
    ];
    await n.retryLastTurn();
    expect(server.streamCalls, callsBefore, reason: 'no second generation');
    expect(n.state.messages.last.content, 'Start and the rest');
    n.dispose();
  });

  test('Stop tells the server which turn to stop; sending a new question does not',
      () async {
    final (n, server) = await _asking('Q bedtime');
    server.token('Start ');
    await _settle();
    n.stopStreaming(notifyServer: true); // the Stop button
    await _settle();
    expect(server.stops, [
      {'message_id': 1}
    ]);
    unawaited(n.sendMessage('Another question'));
    await _settle();
    n.stopStreaming(); // what sendMessage does internally on interrupt
    await _settle();
    expect(server.stops.length, 1);
    n.dispose();
  });

  test('older server (no ids): only its last question, continuing the partial',
      () async {
    final server = _Server(sendsTurns: false);
    final (n, _) = await _asking('Q bedtime', server: server);
    server.token('Start ');
    await _settle();
    server.drop();
    await _settle();
    server.history = [
      _msg('user', 'Q bedtime'),
      _msg('assistant', 'A different answer entirely', 'llm_generated'),
    ];
    expect(await n.recoverInterruptedAnswer(attempts: 1, retryDelay: Duration.zero),
        isFalse, reason: 'it does not continue what was shown');
    server.history = [
      _msg('user', 'Q bedtime'),
      _msg('assistant', 'Start and finish', 'llm_generated'),
    ];
    expect(await n.recoverInterruptedAnswer(attempts: 1, retryDelay: Duration.zero),
        isTrue);
    expect(n.state.messages.last.content, 'Start and finish');
    n.dispose();
  });

  // ── PR #24 round 2 (/tmp/review-pr24/mobile-probe2: N2, N4–N10) ────────

  test('T2 (N5a): Stop before the turn frame is sent once the server names it',
      () async {
    final server = _Server()..turnAtOpen = false;
    final (n, _) = await _asking('Q1 wrong age', server: server);
    await _settle(); // the server is still classifying: no turn frame yet
    n.stopStreaming(notifyServer: true);
    await _settle();
    expect(n.state.phase, ChatPhase.idle);
    expect(n.state.messages.last.isStreaming, isFalse);
    expect(server.stops, isEmpty);
    expect(server.sse.hasListener, isTrue,
        reason: 'kept open, unseen, until the server names the turn');

    server.turn(41);
    await _settle();
    expect(server.stops, [
      {'message_id': 41}
    ]);
    expect(server.sse.hasListener, isFalse);
    expect(n.state.messages.last.content, AppL10n.current.chatResponseStopped,
        reason: 'nothing from the stopped stream is shown');
    n.dispose();
  });

  test('T2: a server too old to name turns is just closed at its first word',
      () async {
    final server = _Server(sendsTurns: false);
    final (n, _) = await _asking('Q1', server: server);
    await _settle();
    n.stopStreaming(notifyServer: true);
    server.token('Start ');
    await _settle();
    expect(server.stops, isEmpty);
    expect(server.sse.hasListener, isFalse);
    n.dispose();
  });

  test('N8: a second question while thinking closes the first, sends no stop',
      () async {
    final server = _Server()..turnAtOpen = false;
    final (n, _) = await _asking('Q1 my son lies', server: server);
    await _settle();
    unawaited(n.sendMessage('Q2 he is 5'));
    await _settle();
    expect(server.streamCalls, 2);
    expect(n.state.messages.map((m) => m.isStreaming), [false, false, false, true]);
    expect(server.stops, isEmpty, reason: 'the server cuts the older turn itself');
    n.dispose();
  });

  test('T4 (N6): cold start while the server is still writing the answer',
      () async {
    final server = _Server()
      ..history = [
        _msg('user', 'Q1 bedtime', null, 1),
        _msg('assistant', 'Start', 'pending', 2),
      ];
    final (n, _) = await _coldStart(server);
    var last = n.state.messages.last;
    expect(last.turnId, 1);
    expect(last.interrupted, isTrue, reason: 'a fragment must not look final');
    expect(last.error, AppL10n.current.chatAnswerStillComing);

    server.history = [
      _msg('user', 'Q1 bedtime', null, 1),
      _msg('assistant', 'Start and the full rest', 'llm_generated', 2),
    ];
    await _until(() => n.state.messages.last.content == 'Start and the full rest',
        reason: 'the recovery started at cold start');
    last = n.state.messages.last;
    expect(last.error, isNull);
    expect(last.interrupted, isFalse);
    n.dispose();
  });

  test('T4: cold start on an unanswered question waits for its answer', () async {
    final server = _Server()..history = [_msg('user', 'Q1 bedtime', null, 1)];
    final (n, _) = await _coldStart(server);
    expect(n.state.messages.map((m) => m.role), ['user', 'assistant']);
    expect(n.state.messages.last.turnId, 1);
    expect(n.state.messages.last.interrupted, isTrue);

    server.history = [
      _msg('user', 'Q1 bedtime', null, 1),
      _msg('assistant', 'The answer', 'llm_generated', 2),
    ];
    await _until(() => n.state.messages.last.content == 'The answer');
    n.dispose();
  });

  test('T4: a cut fragment comes back with its Retry, and Retry asks again',
      () async {
    final server = _Server()
      ..history = [
        _msg('user', 'Q1 bedtime', null, 1),
        _msg('assistant', 'Start', 'interrupted', 2),
      ];
    final (n, _) = await _coldStart(server);
    final last = n.state.messages.last;
    expect(last.interrupted, isTrue);
    expect(last.error, AppL10n.current.chatConnectionInterrupted);
    await _settle();
    final reads = server.historyReads;
    unawaited(n.retryLastTurn());
    await _settle();
    expect(server.streamCalls, 1, reason: 'a fragment is final: generate again');
    expect(server.historyReads, reads + 1);
    n.dispose();
  });

  test('T4: the cut turn and its id survive in the local snapshot', () async {
    final (n, server) = await _asking('Q1 bedtime');
    server.token('Start ');
    await _settle();
    server.history = [_msg('user', 'Q1 bedtime', null, 1)];
    server.drop();
    await _settle();
    final prefs = await SharedPreferences.getInstance();
    final snap = jsonDecode(prefs.getString('tg.chat_snapshot')!) as Map;
    final reply = (snap['messages'] as List).last as Map;
    expect(reply['turn_id'], 1);
    expect(reply['interrupted'], isTrue);
    n.dispose();

    // The process dies; the local copy (with the partial) is longer than the
    // server's, so it is the one restored — still recoverable.
    final (restarted, _) = await _coldStart(server,
        prefs: {'tg.chat_snapshot': prefs.getString('tg.chat_snapshot')!});
    final last = restarted.state.messages.last;
    expect(last.content, 'Start ');
    expect((last.turnId, last.interrupted), (1, true));
    server.history = [
      _msg('user', 'Q1 bedtime', null, 1),
      _msg('assistant', 'Start and the rest', 'llm_generated', 2),
    ];
    await _until(() => restarted.state.messages.last.content == 'Start and the rest');
    restarted.dispose();
  });

  test('T4: opening a past conversation marks and recovers its cut turn',
      () async {
    final (n, server) = await _asking('Q in s1');
    server.done('A in s1');
    await _settle();
    server.history = [
      _msg('user', 'Q in s2', null, 7),
      _msg('assistant', 'Start', 'pending', 8),
    ];
    await n.switchToSession('s2');
    expect(n.state.messages.last.turnId, 7);
    expect(n.state.messages.last.interrupted, isTrue);
    n.dispose();
  });

  test('T5 (N2): recovery keeps looking past the old one-minute window',
      () async {
    // The old loop looked six times (~60 s) and gave up while the server may
    // take up to its 300 s deadline. Scaled: 10 ms first gap — six looks are
    // over within ~0.3 s; the answer lands at 0.7 s.
    final (n, server) =
        await _asking('Q1 long', recoveryDelay: const Duration(milliseconds: 10));
    server.token('Start ');
    await _settle();
    server.history = [
      _msg('user', 'Q1 long', null, 1),
      _msg('assistant', 'Start', 'pending', 2),
    ];
    server.drop();
    await Future<void>.delayed(const Duration(milliseconds: 700));
    expect(n.state.messages.last.error, AppL10n.current.chatAnswerStillComing);
    server.history = [
      _msg('user', 'Q1 long', null, 1),
      _msg('assistant', 'Start and the long rest', 'llm_generated', 2),
    ];
    await _until(() => n.state.messages.last.content == 'Start and the long rest',
        within: const Duration(seconds: 3));
    expect(server.historyReads, greaterThan(6));
    n.dispose();
  });

  test('T5: the defaults wait as long as the server may write', () {
    expect(ChatNotifier.answerDeadline, greaterThanOrEqualTo(const Duration(seconds: 300)));
    expect(ChatNotifier.maxRecoveryGap, lessThanOrEqualTo(const Duration(seconds: 30)));
  });

  test('T5 (N7): resume wakes a recovery sleeping through its back-off',
      () async {
    final (n, server) =
        await _asking('Q1', recoveryDelay: const Duration(seconds: 20));
    server.token('Start ');
    await _settle();
    server.history = [_msg('user', 'Q1', null, 1), _msg('assistant', 'Start', 'pending', 2)];
    server.drop(); // first look: still being written → sleeps 20 s
    await _settle();
    server.history = [
      _msg('user', 'Q1', null, 1),
      _msg('assistant', 'Start and the rest', 'llm_generated', 2),
    ];
    final sw = Stopwatch()..start();
    n.onAppResumed(); // the parent is back
    await _until(() => n.state.messages.last.content == 'Start and the rest',
        within: const Duration(seconds: 2));
    expect(sw.elapsed, lessThan(const Duration(seconds: 2)));
    n.dispose();
  });

  test('T6 (N4): Retry while the server is still writing does not generate it again',
      () async {
    final (n, server) =
        await _asking('Q1', recoveryDelay: const Duration(seconds: 20));
    server.token('Start ');
    await _settle();
    server.history = [_msg('user', 'Q1', null, 1), _msg('assistant', 'Start', 'pending', 2)];
    server.drop();
    await _settle();
    final calls = server.streamCalls;
    await n.retryLastTurn();
    expect(server.streamCalls, calls, reason: 'Q1, A1, Q1′, A1′ — two answers');
    expect(n.state.messages.last.error, AppL10n.current.chatAnswerStillComing);
    expect(n.state.messages.where((m) => m.role == 'user').length, 1);

    server.history = [
      _msg('user', 'Q1', null, 1),
      _msg('assistant', 'Start and the rest', 'llm_generated', 2),
    ];
    await n.retryLastTurn(); // a second tap looks again, now
    expect(n.state.messages.last.content, 'Start and the rest');
    expect(server.streamCalls, calls);
    n.dispose();
  });

  test('T6 (N10): Retry during the recovery fetch shares it', () async {
    final (n, server) = await _asking('Q1');
    server.token('Start ');
    await _settle();
    server.history = [
      _msg('user', 'Q1', null, 1),
      _msg('assistant', 'Start and the rest', 'llm_generated', 2),
    ];
    server.historyGate = Completer<void>();
    server.drop(); // the loop's first fetch starts and blocks
    await _settle();
    final calls = server.streamCalls;
    final retry = n.retryLastTurn(); // tapped while that fetch is pending
    await _settle();
    server.historyGate!.complete();
    server.historyGate = null;
    await retry;
    expect(server.streamCalls, calls);
    expect(server.historyReads, 1);
    expect(n.state.messages.last.content, 'Start and the rest');
    expect(n.state.phase, ChatPhase.idle);
    n.dispose();
  });

  test('N9: a newer question after ours ends the wait at once', () async {
    final (n, server) = await _asking('Q1', recoveryDelay: const Duration(seconds: 20));
    server.token('Start ');
    await _settle();
    server.history = [
      _msg('user', 'Q1', null, 1),
      _msg('user', 'Asked from another device', null, 3),
      _msg('assistant', 'Its answer', 'llm_generated', 4),
    ];
    server.drop();
    await _settle();
    expect(server.historyReads, 1);
    expect(n.state.messages.last.content, 'Start ',
        reason: 'another turn\'s answer is never taken');
    expect(n.state.messages.last.error, AppL10n.current.chatConnectionInterrupted);
    n.dispose();
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
  void stopStreaming({bool notifyServer = false}) {
    calls.add('stop');
    super.stopStreaming(notifyServer: notifyServer);
  }
}
