// The family-programs wire (MOBILE_API §11) through the real TgClient.
//
// What these pin: every programs call carries the family's UTC offset and the
// UI language; a refusal's machine-readable code survives into TgApiError (it
// used to be thrown away, so "already recorded" read as a failure); an old
// server's 404 reads as "not offered", not as an error; the birth month is
// sent only when given, and an explicit null clears it; and the evening
// confirm hands back the coins the device must credit.

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/programs/providers/programs_providers.dart';

class _Storage implements FlutterSecureStorage {
  final Map<String, String> store = {
    'tg_device_id': 'device-1',
    'tg_session_id': 'session-1',
    'tg_token': 'token-1',
  };

  @override
  Future<String?> read({required String key, Object? iOptions, Object? aOptions, Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async =>
      store[key];

  @override
  Future<void> write({required String key, required String? value, Object? iOptions, Object? aOptions, Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async {
    if (value == null) {
      store.remove(key);
    } else {
      store[key] = value;
    }
  }

  @override
  Future<void> delete({required String key, Object? iOptions, Object? aOptions, Object? lOptions, Object? webOptions, Object? mOptions, Object? wOptions}) async =>
      store.remove(key);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  late List<http.Request> sent;

  TgClient clientAnswering(http.Response Function(http.Request req) answer) {
    sent = [];
    final mock = MockClient((req) async {
      sent.add(req);
      return answer(req);
    });
    return TgClient.forTesting(baseUrl: 'http://api.test', httpClient: mock, storage: _Storage());
  }

  http.Response ok(Object body) => http.Response.bytes(utf8.encode(jsonEncode(body)), 200,
      headers: {'content-type': 'application/json; charset=utf-8'});

  http.Response refused(int status, Map<String, dynamic> detail) =>
      http.Response(jsonEncode({'detail': detail}), status);

  tearDown(() => TgClient.uiLanguage = null);

  group('every programs call', () {
    test('sends the family offset, the language, and the Bearer token', () async {
      TgClient.uiLanguage = 'en';
      final client = clientAnswering((_) => ok({'children': []}));
      await client.fetchPrograms();
      await client.fetchRamadanToday(12);
      await client.fetchMilestone(12, 'prayer_start');
      for (final req in sent) {
        expect(req.url.queryParameters['tz_offset_minutes'],
            '${DateTime.now().timeZoneOffset.inMinutes}', reason: req.url.path);
        expect(req.url.queryParameters['lang'], 'en', reason: req.url.path);
        expect(req.headers['Authorization'], 'Bearer token-1');
      }
      expect(sent.map((r) => r.url.path), [
        '/api/programs',
        '/api/children/12/ramadan/today',
        '/api/children/12/milestones/prayer_start',
      ]);
    });

    test('never sends `features` (this build has no weekly-plan screen)', () async {
      final client = clientAnswering((_) => ok({}));
      await client.fetchRamadanToday(12);
      expect(sent.single.url.queryParameters.containsKey('features'), isFalse);
    });

    test('Arabic is the default: no lang parameter', () async {
      final client = clientAnswering((_) => ok({}));
      await client.fetchPrograms();
      expect(sent.single.url.queryParameters.containsKey('lang'), isFalse);
    });
  });

  group('refusals keep their code', () {
    test('a structured 409 becomes TgApiError.code + details', () async {
      final client = clientAnswering(
          (_) => refused(409, {'error': 'one_stage_at_a_time', 'next_stage': 3}));
      final error = await client
          .setPrayerJourneyStage(12, 5)
          .then<Object?>((_) => null, onError: (Object e) => e);
      expect(error, isA<TgApiError>());
      final e = error as TgApiError;
      expect(e.statusCode, 409);
      expect(e.code, 'one_stage_at_a_time');
      expect(e.details?['next_stage'], 3);
    });

    test('a plain string detail still reads as the message, with no code', () async {
      final client = clientAnswering((_) => http.Response.bytes(
          utf8.encode(jsonEncode({'detail': 'الاسم مطلوب.'})), 422,
          headers: {'content-type': 'application/json; charset=utf-8'}));
      final error = await client.fetchPrograms().then<Object?>((_) => null, onError: (Object e) => e);
      expect((error as TgApiError).message, 'الاسم مطلوب.');
      expect(error.code, isNull);
    });
  });

  group("§9's branchable errors (a refused child deletion)", () {
    http.Response proofRequired() => http.Response.bytes(
        utf8.encode(jsonEncode({
          'detail': {
            'code': 'device_proof_required',
            'message': 'أكّد أن الهاتف معك أولًا.',
            'message_en': 'Confirm this phone first.',
            'support_email': 'support@alsaba.cloud',
          },
        })),
        403,
        headers: {'content-type': 'application/json; charset=utf-8'});

    test('keep the code and show the server-written message, in Arabic by default', () async {
      final client = clientAnswering((_) => proofRequired());
      final error = await client.deleteChild(12).then<Object?>((_) => null, onError: (Object e) => e);
      final e = error as TgApiError;
      expect(e.statusCode, 403);
      expect(e.code, 'device_proof_required');
      expect(e.message, 'أكّد أن الهاتف معك أولًا.');
      expect(e.details?['support_email'], 'support@alsaba.cloud');
    });

    test('…and in English for an English interface', () async {
      TgClient.uiLanguage = 'en';
      final client = clientAnswering((_) => proofRequired());
      final error = await client.deleteChild(12).then<Object?>((_) => null, onError: (Object e) => e);
      expect((error as TgApiError).message, 'Confirm this phone first.');
    });
  });

  group('old-server compatibility', () {
    test("FastAPI's 404 (no route) means the programs are not offered", () async {
      final client = clientAnswering((_) => http.Response(jsonEncode({'detail': 'Not Found'}), 404));
      final error = await client.fetchPrograms().then<Object?>((_) => null, onError: (Object e) => e);
      expect(programsUnavailable(error!), isTrue);
    });

    test('an unpublished program file is also "not offered"', () async {
      final client = clientAnswering((_) => refused(503, {'error': 'program_unavailable', 'program': 'ramadan_family'}));
      final error = await client.fetchPrograms().then<Object?>((_) => null, onError: (Object e) => e);
      expect(programsUnavailable(error!), isTrue);
    });

    test("a child that is not this device's is not a missing server", () async {
      final client = clientAnswering((_) => refused(404, {'error': 'child_not_found'}));
      final error = await client.fetchMilestones(99).then<Object?>((_) => null, onError: (Object e) => e);
      expect(programsUnavailable(error!), isFalse);
    });
  });

  group('birth month on the child profile', () {
    test('create sends it when given, and only then', () async {
      final client = clientAnswering((_) => http.Response(jsonEncode({'id': 1}), 201));
      await client.createChild(name: 'أحمد', ageGroup: '7-9', birthMonth: '2019-03');
      await client.createChild(name: 'عمر', ageGroup: '7-9');
      final first = jsonDecode(sent[0].body) as Map<String, dynamic>;
      final second = jsonDecode(sent[1].body) as Map<String, dynamic>;
      expect(first['birth_month'], '2019-03');
      expect(second.containsKey('birth_month'), isFalse);
    });

    test('update: absent leaves it alone, explicit null clears it', () async {
      final client = clientAnswering((_) => ok({'id': 1}));
      await client.updateChild(childId: 1, name: 'أحمد');
      await client.updateChild(childId: 1, birthMonth: '2019-04');
      await client.updateChild(childId: 1, clearBirthMonth: true);
      final bodies = [for (final r in sent) jsonDecode(r.body) as Map<String, dynamic>];
      expect(bodies[0].containsKey('birth_month'), isFalse);
      expect(bodies[1]['birth_month'], '2019-04');
      expect(bodies[2].containsKey('birth_month'), isTrue);
      expect(bodies[2]['birth_month'], isNull);
    });
  });

  group('bodies match the contract', () {
    test('marks, practice, settings, enrol', () async {
      final client = clientAnswering((_) => ok({}));
      await client.setRamadanMark(mark: 'challenge_done', day: 3, done: false);
      await client.setRamadanMark(mark: 'family_word', day: 28, choiceIndex: 3);
      await client.recordFastingPractice(12, done: false);
      await client.updateRamadanSettings(resetMonthDays: true);
      await client.updateRamadanSettings(startShiftDays: -1);
      await client.enrolPrayerJourney(12, track: 'journey', startStage: 3);
      final bodies = [for (final r in sent) jsonDecode(r.body) as Map<String, dynamic>];
      expect(bodies[0], {'mark': 'challenge_done', 'day': 3, 'done': false});
      expect(bodies[1], {'mark': 'family_word', 'day': 28, 'done': true, 'choice_index': 3});
      expect(bodies[2], {'done': false});
      expect(bodies[3], {'month_days': null});
      expect(bodies[4], {'start_shift_days': -1});
      expect(bodies[5], {'track': 'journey', 'start_stage': 3});
      expect(sent.map((r) => r.method), ['POST', 'POST', 'POST', 'PUT', 'PUT', 'POST']);
    });

    test('the child claims with the Child-Bearer token and the task in the query', () async {
      final client = clientAnswering((_) => ok({'ok': true, 'slots_left_today': 0}));
      await client.claimChildPrayer(childToken: 'child-tok', taskId: 'prayer_s1_pray_beside');
      final req = sent.single;
      expect(req.url.path, '/api/value-tracking/child-mode/prayer/claim');
      expect(req.url.queryParameters['task_id'], 'prayer_s1_pray_beside');
      expect(req.headers['Authorization'], 'Child-Bearer child-tok');
      expect(req.url.queryParameters.containsKey('tz_offset_minutes'), isTrue);
    });
  });

  group('the evening confirm', () {
    test('hands back the coins of confirmed prayer cards', () async {
      final client = clientAnswering((_) => ok({
            'ok': true,
            'settled': 2,
            'coins': [
              {'mission_id': 41, 'child_id': 12, 'task_id': 'prayer_s1_pray_beside', 'coins': 10},
            ],
          }));
      final result = await client.settleMissions([
        {'mission_id': 41, 'confirmed': true},
        {'mission_id': 42, 'confirmed': false},
      ]);
      expect(result.settled, 2);
      expect(result.coins.single['coins'], 10);
    });

    test('an older server sends no coins, and confirmMissions keeps its answer', () async {
      final client = clientAnswering((_) => ok({'ok': true, 'settled': 1}));
      expect(await client.confirmMissions([{'mission_id': 1, 'confirmed': true}]), 1);
      final again = await client.settleMissions([{'mission_id': 1, 'confirmed': true}]);
      expect(again.coins, isEmpty);
    });
  });
}
