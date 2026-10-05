/// «المربّي يعرف ابنك» — the wire (MOBILE_API §9–§10) and its parsing.
///
/// What each group pins:
///   * the requests are the contract's: paths, `tz_offset_minutes`, `lang`,
///     `confirm=true`, and `child_id` on every question;
///   * errors keep their stable `code`, the message in the reader's language,
///     `available_at` and the support address;
///   * `device_proof_required` proves once and retries once — a cooldown is
///     never retried, and nothing else triggers a proof;
///   * FastAPI's bare 404 (today's production) reads as "not here", not as
///     "not yours";
///   * account deletion makes this install a brand-new device the moment the
///     server answers;
///   * timestamps are UTC (`Z`, and the old zoneless shape too), and names are
///     swapped in on the device only.
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/device_id_claim.dart';
import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/child_memory/data/memory_models.dart';
import 'package:almorabbi/features/child_memory/data/memory_repository.dart';
import 'package:almorabbi/features/child_memory/data/placeholder_names.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
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
  Future<void> deleteAll({
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    store.clear();
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// One recorded request.
class _Seen {
  _Seen(this.method, this.url, this.body);
  final String method;
  final Uri url;
  final String body;
}

/// A client over a scripted server: [answer] decides each response.
({TgClient client, List<_Seen> seen, _MemStorage storage}) _client(
  http.Response Function(http.Request req, int n) answer,
) {
  final seen = <_Seen>[];
  final storage = _MemStorage()
    ..store['tg_device_id'] = 'dev-old'
    ..store['tg_session_id'] = 's1'
    ..store['tg_token'] = 'tok1';
  final client = TgClient.forTesting(
    baseUrl: 'http://api.test',
    storage: storage,
    httpClient: MockClient((req) async {
      seen.add(_Seen(req.method, req.url, req.body));
      return answer(req, seen.length);
    }),
  );
  return (client: client, seen: seen, storage: storage);
}

http.Response _json(Object body, [int status = 200]) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AppL10n.current = lookupAppLocalizations(const Locale('ar'));
  });
  tearDown(() {
    AppL10n.current = lookupAppLocalizations(const Locale('ar'));
    TgClient.uiLanguage = null;
  });

  group('requests follow the contract', () {
    test('due follow-ups and the weekly plan carry the family\'s UTC offset',
        () async {
      final c = _client((req, _) => req.url.path.endsWith('/due')
          ? _json({'followups': []})
          : _json({'child_id': 12}));
      await c.client.getDueFollowups(tzOffsetMinutes: 180);
      await c.client.getWeeklyPlan(12, lang: 'en', tzOffsetMinutes: -300);
      expect(c.seen[0].url.path, '/api/children/followups/due');
      expect(c.seen[0].url.queryParameters,
          {'limit': '10', 'tz_offset_minutes': '180'});
      expect(c.seen[1].url.path, '/api/children/12/weekly-plan');
      expect(c.seen[1].url.queryParameters,
          {'lang': 'en', 'tz_offset_minutes': '-300'});
    });

    test('the repository sends the device\'s real offset', () async {
      final c = _client((req, _) => _json({'followups': []}));
      await MemoryRepository(c.client).dueFollowups();
      expect(c.seen.single.url.queryParameters['tz_offset_minutes'],
          '${DateTime.now().timeZoneOffset.inMinutes}');
    });

    test('memory routes: paths, methods and bodies', () async {
      final c = _client((req, _) {
        if (req.method == 'POST' && req.url.path.endsWith('/memory')) {
          return _json(factJsonFor(1), 201);
        }
        if (req.url.path.endsWith('/start')) {
          return _json({'challenge_id': 'q3Vb0J7xQ2m8YtKa', 'expires_in': 300}, 202);
        }
        return _json({'ok': true});
      });
      final api = c.client;
      await api.getChildMemory(12);
      await api.addChildFact(12, category: 'goal', fact: 'يحفظ الملك');
      await api.patchChildFact(12, 41, status: 'active');
      await api.deleteChildFact(12, 41);
      await api.deleteChildMemory(12);
      await api.putMemorySettings(enabled: false);
      await api.answerFollowup(7, outcome: 'didnt_work', note: '  ');
      await api.dismissFollowup(7);
      await api.deleteAllMemory();
      await api.startDeviceProof();
      await api.completeDeviceProof('q3Vb0J7xQ2m8YtKa', 'the-code');

      String line(_Seen s) =>
          '${s.method} ${s.url.path}${s.url.hasQuery ? '?${s.url.query}' : ''}';
      expect(c.seen.map(line), [
        'GET /api/children/12/memory?status=all',
        'POST /api/children/12/memory',
        'PATCH /api/children/12/memory/41',
        'DELETE /api/children/12/memory/41',
        'DELETE /api/children/12/memory',
        'PUT /api/children/memory/settings',
        'POST /api/children/followups/7/answer',
        'POST /api/children/followups/7/dismiss',
        'DELETE /api/privacy/memory',
        'POST /api/device-proof/start',
        'POST /api/device-proof/complete',
      ]);
      expect(jsonDecode(c.seen[1].body), {'category': 'goal', 'fact': 'يحفظ الملك'});
      // PATCH sends only what changed.
      expect(jsonDecode(c.seen[2].body), {'status': 'active'});
      expect(jsonDecode(c.seen[5].body), {'enabled': false});
      // A blank note is no note.
      expect(jsonDecode(c.seen[6].body), {'outcome': 'didnt_work'});
      expect(jsonDecode(c.seen[10].body),
          {'challenge_id': 'q3Vb0J7xQ2m8YtKa', 'code': 'the-code'});
    });

    test('every question names the active child', () {
      const q = AssistantQuery(
        ageGroup: AgeGroup.sevenNine,
        severity: Severity.light,
        messageText: 'كيف أعوّده على الصلاة؟',
        sessionId: 's1',
        childId: 12,
      );
      expect(q.toJson()['child_id'], 12);
      const none = AssistantQuery(
        ageGroup: AgeGroup.sevenNine,
        severity: Severity.light,
        messageText: 'سؤال',
      );
      expect(none.toJson().containsKey('child_id'), isFalse);
    });

    test('the chat sends the child that is active at send time', () async {
      final bodies = <Map<String, dynamic>>[];
      final storage = _MemStorage()
        ..store['tg_device_id'] = 'dev'
        ..store['tg_session_id'] = 's1'
        ..store['tg_token'] = 'tok1';
      final client = TgClient.forTesting(
        baseUrl: 'http://api.test',
        storage: storage,
        httpClient: MockClient.streaming((req, body) async {
          final text = await body.bytesToString();
          if (req.url.path == '/api/assistant/stream') {
            bodies.add(jsonDecode(text) as Map<String, dynamic>);
          }
          final done = jsonEncode({
            'reply_text': 'ok',
            'domain': 'islamic_parenting',
            'severity': 'خفيف',
            'needs_human_review': false,
            'escalation_target': null,
            'mode': 'llm_generated',
            'session_id': 's1',
            'metadata': {'child_id': 12, 'memory_facts_used': 2},
          });
          return http.StreamedResponse(
            Stream.value(utf8.encode('event: done\ndata: $done\n\n')),
            200,
            headers: {'content-type': 'text/event-stream'},
          );
        }),
      );
      var active = 12;
      final notifier = ChatNotifier(client, activeChildId: () => active);
      notifier.setOnline(true);
      await notifier.sendMessage('سؤال عن الصلاة');
      active = 13;
      await notifier.sendMessage('سؤال عن النوم');
      expect(bodies.map((b) => b['child_id']), [12, 13]);
      final reply = notifier.state.messages.last.reply!;
      expect(reply.memoryFactsUsed, 2);
      expect(reply.memoryChildId, 12);
      notifier.dispose();
    });
  });

  group('errors keep what the app branches on', () {
    test('code, available_at and the support address survive', () async {
      final c = _client((req, _) => _json({
            'detail': {
              'code': 'device_proof_cooldown',
              'message': 'الرسالة',
              'message_en': 'The message',
              'support_email': 'support@alsaba.cloud',
              'available_at': '2026-10-07T18:30:00Z',
            }
          }, 403));
      final e = await c.client.getChildMemory(1).then<TgApiError?>((_) => null,
          onError: (Object e) => e as TgApiError);
      expect(e!.statusCode, 403);
      expect(e.code, 'device_proof_cooldown');
      expect(e.message, 'الرسالة');
      expect(e.supportEmail, 'support@alsaba.cloud');
      expect(e.availableAt, DateTime.utc(2026, 10, 7, 18, 30));
      expect(e.isMissingEndpoint, isFalse);
      // A zoneless value is UTC too — never the phone's local time.
      const zoneless = TgApiError(403, 'm',
          code: 'device_proof_cooldown',
          details: {'available_at': '2026-10-07 18:30:00'});
      expect(zoneless.availableAt, DateTime.utc(2026, 10, 7, 18, 30));
    });

    test('an English reader gets message_en, and never Arabic-only text',
        () async {
      // Both follow one resolver in the app (l10n_global.dart): the client
      // picks the server's text by `uiLanguage`, its own lines by AppL10n.
      AppL10n.current = lookupAppLocalizations(const Locale('en'));
      TgClient.uiLanguage = 'en';
      final withEn = _client((req, _) => _json({
            'detail': {'code': 'no_push_token', 'message': 'ع', 'message_en': 'E'}
          }, 409));
      final a = await withEn.client
          .startDeviceProof()
          .then<TgApiError?>((_) => null, onError: (Object e) => e as TgApiError);
      expect(a!.message, 'E');
      final arabicOnly = _client((req, _) => _json({
            'detail': {'code': 'fact_too_long', 'message': 'النص أطول'}
          }, 422));
      final b = await arabicOnly.client
          .getChildMemory(1)
          .then<TgApiError?>((_) => null, onError: (Object e) => e as TgApiError);
      expect(b!.code, 'fact_too_long');
      expect(b.message, isNot(contains('النص')));
    });

    test('FastAPI\'s bare 404 is a missing endpoint; a coded 404 is not',
        () async {
      final bare = _client((req, _) => _json({'detail': 'Not Found'}, 404));
      final e1 = await bare.client
          .getMemorySettings()
          .then<TgApiError?>((_) => null, onError: (Object e) => e as TgApiError);
      expect(e1!.isMissingEndpoint, isTrue);
      final coded = _client((req, _) => _json({
            'detail': {'code': 'followup_not_found', 'message': 'غير موجودة'}
          }, 404));
      final e2 = await coded.client
          .getFollowup(9)
          .then<TgApiError?>((_) => null, onError: (Object e) => e as TgApiError);
      expect(e2!.isMissingEndpoint, isFalse);
      expect(e2.code, 'followup_not_found');
    });

    test('an older server hides the features instead of failing', () async {
      final c = _client((req, _) => _json({'detail': 'Not Found'}, 404));
      final repo = MemoryRepository(c.client);
      expect(await repo.settings(), isNull);
      expect(await repo.dueFollowups(), isNull);
      expect(await repo.weeklyPlan(1, lang: 'ar'), isNull);
      expect(await repo.proofStatus(), isNull);
    });
  });

  group('device_proof_required proves once and retries once', () {
    test('a protected call proves, then succeeds on the retry', () async {
      var proven = false;
      final c = _client((req, n) => proven
          ? _json({'child_id': 1, 'facts': []})
          : _json({
              'detail': {'code': 'device_proof_required', 'message': 'م'}
            }, 403));
      var proofs = 0;
      c.client.onDeviceProofRequired = () async {
        proofs++;
        proven = true;
      };
      final memory = await MemoryRepository(c.client).facts(1);
      expect(memory.childId, 1);
      expect(proofs, 1);
      expect(c.seen.length, 2);
    });

    test('a cooldown is never retried, and never starts a proof', () async {
      final c = _client((req, n) => _json({
            'detail': {
              'code': 'device_proof_cooldown',
              'message': 'م',
              'available_at': '2026-10-07T18:30:00Z',
            }
          }, 403));
      var proofs = 0;
      c.client.onDeviceProofRequired = () async => proofs++;
      await expectLater(MemoryRepository(c.client).facts(1),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'device_proof_cooldown')));
      expect(proofs, 0);
      expect(c.seen.length, 1);
    });

    test('a failed proof reaches the caller with its own message', () async {
      final c = _client((req, n) => _json({
            'detail': {'code': 'device_proof_required', 'message': 'م'}
          }, 403));
      c.client.onDeviceProofRequired = () async =>
          throw const TgApiError(409, 'no token', code: 'no_push_token');
      await expectLater(MemoryRepository(c.client).facts(1),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'no_push_token')));
    });

    test('child deletion and progress reset prove and retry too', () async {
      var proven = false;
      final c = _client((req, n) => proven
          ? _json({'deleted': true})
          : _json({
              'detail': {'code': 'device_proof_required', 'message': 'م'}
            }, 403));
      c.client.onDeviceProofRequired = () async => proven = true;
      expect((await c.client.deleteChild(5))['deleted'], isTrue);
      proven = false;
      expect((await c.client.resetChildProgress(5))['deleted'], isTrue);
      expect(c.seen.where((s) => s.method == 'DELETE').length, 4);
    });

    test('the Today list never starts a proof', () async {
      final c = _client((req, n) => _json({
            'detail': {'code': 'device_proof_required', 'message': 'م'}
          }, 403));
      var proofs = 0;
      c.client.onDeviceProofRequired = () async => proofs++;
      expect(await MemoryRepository(c.client).dueFollowups(), isNull);
      expect(proofs, 0);
    });

    test('switching memory off never asks for a proof', () async {
      final c = _client((req, n) => _json({
            'enabled': false,
            'collecting': false,
            'proven': false,
            'cooldown_until': null
          }));
      var proofs = 0;
      c.client.onDeviceProofRequired = () async => proofs++;
      final s = await MemoryRepository(c.client).setEnabled(false);
      expect(s.enabled, isFalse);
      expect(proofs, 0);
    });
  });

  group('account deletion', () {
    test('sends confirm=true and becomes a brand-new device at once', () async {
      final c = _client((req, n) => _json({
            'devices': 2,
            'signed_in': true,
            'deleted': {'child_profiles': 2},
            'deleted_at': '2026-10-04T18:40:00Z',
          }));
      final result = await MemoryRepository(c.client).deleteAccount();
      // A live token first (a 401 to the DELETE must mean "gone"), then the
      // DELETE itself.
      expect(c.seen.map((r) => '${r.method} ${r.url.path}'),
          ['GET /api/device-proof', 'DELETE /api/privacy/account']);
      expect(c.seen.last.url.queryParameters, {'confirm': 'true'});
      expect(result.devices, 2);
      expect(result.signedIn, isTrue);
      expect(result.deletedAt, DateTime.utc(2026, 10, 4, 18, 40));

      // The revoked token and the erased id are gone from this install.
      final fresh = c.storage.store['tg_device_id'];
      expect(fresh, isNotNull);
      expect(fresh, isNot('dev-old'));
      expect(c.storage.store.containsKey('tg_token'), isFalse);
      expect(c.storage.store.containsKey('tg_session_id'), isFalse);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), fresh);
    });

    test('the device-twin claim follows the fresh id, never the erased one',
        () async {
      // PR #29's claim file is consulted when the keystore and the backup are
      // both empty — it must not hand the deleted account's id back.
      final dir = await Directory.systemTemp.createTemp('wt-memui-claim');
      addTearDown(() => dir.delete(recursive: true));
      final claimFile = File('${dir.path}/tg_device_id.claim');
      await claimFile.writeAsString('dev-old');
      final storage = _MemStorage()
        ..store['tg_device_id'] = 'dev-old'
        ..store['tg_session_id'] = 's1'
        ..store['tg_token'] = 'tok1';
      final client = TgClient.forTesting(
        baseUrl: 'http://api.test',
        storage: storage,
        deviceIdClaim: DeviceIdClaim(() async => dir),
        httpClient: MockClient((req) async =>
            _json({'devices': 1, 'signed_in': false, 'deleted': {}})),
      );
      await client.deleteAccount();
      final fresh = storage.store['tg_device_id'];
      expect(fresh, isNot('dev-old'));
      expect(await claimFile.readAsString(), fresh);
    });

    test('a 5xx keeps the identity and the record: unknown, not "nothing"',
        () async {
      final c = _client((req, n) => req.method == 'DELETE'
          ? _json({'detail': 'boom'}, 500)
          : _json({'proven': true}));
      await expectLater(
          MemoryRepository(c.client).deleteAccount(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_deletion_unconfirmed')));
      expect(c.storage.store['tg_device_id'], 'dev-old');
      expect(c.storage.store['tg_token'], 'tok1');
      expect(await c.client.accountDeletionState(), kAccountDeletionRequested);
    });

    test('no live session: nothing is sent, nothing recorded', () async {
      final c = _client((req, n) => throw http.ClientException('offline'));
      await expectLater(MemoryRepository(c.client).deleteAccount(),
          throwsA(isA<TgApiError>()));
      expect(c.seen.where((r) => r.method == 'DELETE'), isEmpty);
      expect(await c.client.accountDeletionState(), isNull);
    });
  });

  group('parsing', () {
    test('timestamps are UTC, with Z and in the old zoneless shape', () {
      expect(parseServerTime('2026-10-04T18:30:00Z'),
          DateTime.utc(2026, 10, 4, 18, 30));
      expect(parseServerTime('2026-10-04 18:30:00'),
          DateTime.utc(2026, 10, 4, 18, 30));
      expect(parseServerTime('2026-10-04T21:30:00+03:00'),
          DateTime.utc(2026, 10, 4, 18, 30));
      expect(parseServerTime(null), isNull);
      expect(parseServerTime(''), isNull);
      expect(parseServerTime('not a date'), isNull);
      // A day, not an instant: no zone shift.
      expect(parseServerDate('2026-10-05'), DateTime(2026, 10, 5));
    });

    test('facts group by category; pending and rejected stay out of them', () {
      final m = ChildMemory.fromJson({
        'child_id': 1,
        'facts': [
          factJsonFor(1, category: 'goal'),
          factJsonFor(2, category: 'temperament'),
          factJsonFor(3, category: 'health_note', status: 'pending'),
          factJsonFor(4, category: 'temperament', status: 'rejected'),
          factJsonFor(5, category: 'not_a_category'),
        ],
        'settings': {'enabled': true, 'collecting': true},
        'limits': {'max_fact_chars': 160, 'max_facts': 40},
      });
      expect(m.activeByCategory.keys, ['temperament', 'goal', 'other']);
      expect(m.activeByCategory['temperament']!.map((f) => f.id), [2]);
      expect(m.pending.map((f) => f.id), [3]);
      expect(m.settings!.enabled, isTrue);
    });

    test('a plan without focus or actions is not shown', () {
      expect(
          WeeklyPlan.fromJson({
            'child_id': 1,
            'week': '2026-W41',
            'focus': {'title': ''},
            'actions': [],
          }).isUsable,
          isFalse);
      final p = WeeklyPlan.fromJson({
        'child_id': 1,
        'week': '2026-W41',
        'week_start': '2026-10-05',
        'focus': {'title': 'نوم كافٍ', 'reason_text': 'لأن…'},
        'actions': [
          {'key': 'a', 'text': 'أ'},
          {'key': 'b', 'text': ''},
          'junk',
        ],
        'lesson': null,
      });
      expect(p.isUsable, isTrue);
      expect(p.actions.map((a) => a.text), ['أ']);
      expect(p.lesson, isNull);
      expect(p.nextWeekStart, DateTime(2026, 10, 12));
    });
  });

  group('names are put back on the device only', () {
    test('the child\'s placeholder, in Arabic and English', () {
      expect(renderMemoryText('طفلي يخاف من الظلام', childName: 'أحمد'),
          'أحمد يخاف من الظلام');
      expect(renderMemoryText('نريد لطفلي روتينًا', childName: 'أحمد'),
          'نريد لأحمد روتينًا');
      expect(renderMemoryText("My child is shy; my child's teacher agrees",
              childName: 'Sara'),
          "Sara is shy; Sara's teacher agrees");
      // Without a name, the placeholder stays.
      expect(renderMemoryText('طفلي يخاف'), 'طفلي يخاف');
    });

    test('siblings by the server\'s letters, in profile order', () {
      final family = [
        const FamilyMember(id: 30, name: 'ليلى'),
        const FamilyMember(id: 12, name: 'أحمد'),
        const FamilyMember(id: 7, name: 'س'), // too short: the server skips it
      ];
      // Order by id among names of ≥ 2 characters: أحمد (12) = أ, ليلى (30) = ب.
      expect(
          renderMemoryText('الطفل ب تغار من طفلي', childName: 'أحمد', family: family),
          'ليلى تغار من أحمد');
      expect(renderMemoryText('أعطِ للطفل أ وقتًا', family: family),
          'أعطِ لأحمد وقتًا');
      // An unknown letter stays as it is.
      expect(renderMemoryText('الطفل ج', family: family), 'الطفل ج');
    });
  });
}

Map<String, dynamic> factJsonFor(int id,
        {String category = 'temperament', String status = 'active'}) =>
    {
      'id': id,
      'child_id': 1,
      'category': category,
      'fact': 'طفلي',
      'source': 'chat',
      'confidence': 0.9,
      'status': status,
      'lang': 'ar',
      'created_at': '2026-10-04T18:20:11Z',
      'updated_at': '2026-10-04T18:20:11Z',
    };
