// PR #34 delta review (3a706677) — one group per finding, from the reviewer's
// repros R1–R6 (/tmp/review-pr34b/zz_review34b_*_test.dart), turned to assert
// the fix.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
// ignore: depend_on_referenced_packages
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/coins/coins_service.dart';
import 'package:almorabbi/features/deeplink/deep_link_handler.dart';
import 'package:almorabbi/features/missions/mission_confirmations.dart';
import 'package:almorabbi/features/missions/pending_missions_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_screen.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/models/api_models.dart';

import 'programs_support.dart';

Map<String, dynamic> _card(int id) => {
      'mission_id': id, 'title_ar': 'Task $id', 'child_name': kChildName,
      'estimated_minutes': 7, 'program': 'prayer_journey', 'coins': 10,
    };
Map<String, dynamic> _coin(int id) =>
    {'mission_id': id, 'child_id': kChildId, 'task_id': 'prayer_s1_pray_beside', 'coins': 10};
Map<String, dynamic> _yes(int id) => {'mission_id': id, 'confirmed': true};

Future<int> _balance() async => (await CoinsService.instance.read()).balance;

/// A slow server: every request waits for [gate], then applies like the
/// real one.
class _Gated extends FakeProgramsClient {
  final gate = Completer<void>();
  int settles = 0;
  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    settles++;
    bodies.add({'items': items});
    await gate.future;
    return applySettle(items);
  }
}

/// Restoring child mode on a cold start: the old surface is checked on the
/// network until [gate] opens.
class _SlowRestore extends FakeProgramsClient {
  final gate = Completer<void>();
  @override
  Future<Map<String, dynamic>> fetchChildTodayHabits({required String childToken}) async {
    await gate.future;
    throw const TgApiError(401, 'expired');
  }
}

/// Call 1: applied, answer held on [gate]. Later calls: applied, answer lost
/// while [lose] is set.
class _FirstHeldRestLost extends FakeProgramsClient {
  final gate = Completer<void>();
  bool lose = true;
  int n = 0;
  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    n++;
    bodies.add({'items': items});
    final answer = applySettle(items);
    if (n == 1) {
      await gate.future;
      return answer;
    }
    if (lose) throw const TgApiError(null, 'timeout');
    return answer;
  }
}

/// The server's bound (MissionConfirmIn.items, max_length 200), a network
/// that loses answers while [lose] is set, and ids it refuses outright.
class _Bounded extends FakeProgramsClient {
  bool lose = false;
  Set<int> loseFor = {};
  Set<int> refuse = {};
  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    bodies.add({'items': items});
    if (items.length > 200) throw const TgApiError(422, 'items: at most 200');
    if (items.any((i) => refuse.contains(i['mission_id']))) {
      throw const TgApiError(422, 'refused', code: 'validation');
    }
    final answer = applySettle(items);
    if (lose || items.any((i) => loseFor.contains(i['mission_id']))) {
      throw const TgApiError(null, 'timeout');
    }
    return answer;
  }
}

/// Persists like a device; "dies" on the first write of the paid-ids list.
class _DyingStore extends InMemorySharedPreferencesStore {
  _DyingStore() : super.empty();
  bool die = true;
  @override
  Future<bool> setValue(String valueType, String key, Object value) async {
    if (die && key == 'flutter.programs.credited_prayer_missions') {
      die = false;
      throw StateError('process killed');
    }
    return super.setValue(valueType, key, value);
  }
}

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

class _ActiveChildMode extends ChildModeNotifier {
  _ActiveChildMode(super.client) {
    state = const ChildModeState(active: true, childId: kChildId);
  }
  void leave() => state = const ChildModeState();
}

/// Stands in for TgClient.shared on the referral path.
class _ReferralClient extends FakeProgramsClient {
  final claimed = <String>[];
  @override
  Future<SessionResponse> ensureSession() async => const SessionResponse(sessionId: 's', token: 't');
  @override
  Future<Map<String, dynamic>> claimReferral(String code) async {
    claimed.add(code);
    return {'ok': true};
  }
}

void main() {
  setUp(MissionConfirmations.resetForTest);

  group('1 · the outbox never pays twice and never loses a batch', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('R1: two concurrent credits of the same answer pay once', () async {
      final entries = [_coin(41)];
      final paid = await Future.wait([
        CoinsService.instance.creditConfirmedMissions(entries),
        CoinsService.instance.creditConfirmedMissions(entries),
      ]);
      expect(paid..sort(), [0, 10]);
      expect(await _balance(), 10);
    });

    test('R2: a flush racing an in-flight send waits, and finds nothing left', () async {
      final client = _Gated()
        ..pending = [_card(41)]
        ..confirmCoins = [_coin(41)];
      final a = MissionConfirmations.send(client, [_yes(41)]);
      await pumpEventQueue();
      final b = MissionConfirmations.flush(client);
      await pumpEventQueue();
      client.gate.complete();
      expect((await a).coins, 10);
      expect(await b, isNull);
      expect(client.settles, 1);
      expect(await _balance(), 10);
    });

    test('R3: a later batch whose answer is lost stays in the outbox', () async {
      final client = _FirstHeldRestLost()
        ..pending = [_card(41), _card(42)]
        ..confirmCoins = [_coin(41), _coin(42)];
      final a = MissionConfirmations.send(client, [_yes(41)]);
      await pumpEventQueue();
      final b = MissionConfirmations.send(client, [_yes(42)]); // queued behind a
      await pumpEventQueue();
      client.gate.complete();
      expect((await a).coins, 10);
      await expectLater(b, throwsA(isA<TgApiError>())); // applied, answer lost
      expect((await MissionConfirmations.outbox()).map((e) => e['mission_id']), [42]);
      client.lose = false;
      expect((await MissionConfirmations.flush(client))!.coins, 10);
      expect(await _balance(), 20);
      expect(await MissionConfirmations.outbox(), isEmpty);
    });

    test('only what was answered leaves the outbox', () async {
      final client = _Bounded()
        ..pending = [_card(41), _card(42)]
        ..confirmCoins = [_coin(41), _coin(42)]
        ..loseFor = {41};
      await expectLater(MissionConfirmations.send(client, [_yes(41)]), throwsA(isA<TgApiError>()));
      // Tonight: the waiting 41 is answered, then 42's answer is lost.
      client.loseFor = {42};
      await expectLater(MissionConfirmations.send(client, [_yes(42)]), throwsA(isA<TgApiError>()));
      expect(await _balance(), 10);
      expect((await MissionConfirmations.outbox()).map((e) => e['mission_id']), [42]);
      client.loseFor = {};
      expect((await MissionConfirmations.flush(client))!.coins, 10);
      expect(await _balance(), 20);
      expect(await MissionConfirmations.outbox(), isEmpty);
    });

    test('R5: killed between the two writes, the resend pays exactly once', () async {
      final store = _DyingStore();
      SharedPreferencesStorePlatform.instance = store;
      SharedPreferences.resetStatic();
      final client = FakeProgramsClient()
        ..pending = [_card(41)]
        ..confirmCoins = [_coin(41)];
      await expectLater(MissionConfirmations.send(client, [_yes(41)]), throwsA(isA<StateError>()));
      SharedPreferences.resetStatic(); // relaunch: only what was persisted
      expect(await _balance(), 0);
      await MissionConfirmations.flush(client);
      expect(await _balance(), 10);
      await MissionConfirmations.flush(client); // and nothing more after
      expect(await _balance(), 10);
    });
  });

  group('2 · the outbox cannot block later evenings', () {
    late List<Object> dropped;
    setUp(() {
      SharedPreferences.setMockInitialValues({});
      dropped = [];
      final report = MissionConfirmations.reportDropped;
      MissionConfirmations.reportDropped = (e, _) => dropped.add(e);
      addTearDown(() => MissionConfirmations.reportDropped = report);
    });

    test('R4: over 200 waiting, sent on its own in chunks the server accepts', () async {
      final client = _Bounded()
        ..pending = [for (var i = 1; i <= 120; i++) _card(i)]
        ..confirmCoins = [for (var i = 1; i <= 210; i++) _coin(i)];
      client.lose = true; // evening 1: applied, answer lost
      await expectLater(
          MissionConfirmations.send(client, [for (var i = 1; i <= 120; i++) _yes(i)]),
          throwsA(isA<TgApiError>()));
      client.pending = [for (var i = 121; i <= 210; i++) _card(i)]; // evening 2
      await expectLater(
          MissionConfirmations.send(client, [for (var i = 121; i <= 210; i++) _yes(i)]),
          throwsA(isA<TgApiError>()));
      client.lose = false; // the network is back
      final result = await MissionConfirmations.flush(client);
      expect(result!.coins, 2100);
      expect(await _balance(), 2100);
      expect(await MissionConfirmations.outbox(), isEmpty);
      for (final body in client.bodies) {
        expect((body['items'] as List).length, lessThanOrEqualTo(200));
      }
      expect(dropped, isEmpty);
    });

    test('a permanent refusal drops the waiting batch, recorded, and tonight goes through', () async {
      final client = _Bounded()
        ..pending = [_card(41), _card(42)]
        ..confirmCoins = [_coin(41), _coin(42)]
        ..lose = true;
      await expectLater(MissionConfirmations.send(client, [_yes(41)]), throwsA(isA<TgApiError>()));
      client
        ..lose = false
        ..refuse = {41}; // the waiting batch can never be accepted now
      final result = await MissionConfirmations.send(client, [_yes(42)]);
      expect(result.coins, 10); // tonight's card, paid
      expect(dropped, hasLength(1));
      expect(await MissionConfirmations.outbox(), isEmpty);
    });

    test("tonight's own refused decision is shown to the parent and not kept", () async {
      final client = _Bounded()
        ..pending = [_card(41)]
        ..refuse = {41};
      await expectLater(MissionConfirmations.send(client, [_yes(41)]),
          throwsA(isA<TgApiError>().having((e) => e.statusCode, 'status', 422)));
      expect(await MissionConfirmations.outbox(), isEmpty);
      expect(dropped, hasLength(1));
    });
  });

  group('3 · the 401 renewal is for the child holding the phone', () {
    test('R6: child mode for 13 (from its journey), active child 12 → renews for 13', () async {
      SharedPreferences.setMockInitialValues({kChildModeChildIdKey: 13});
      final log = <String>[];
      final storage = _Storage();
      final mock = MockClient((req) async {
        final auth = req.headers['Authorization'] ?? '';
        log.add('${req.method} ${req.url.path} ${req.url.queryParameters['child_id'] ?? ''} $auth');
        if (req.url.path.endsWith('/child-sessions')) {
          final id = req.url.queryParameters['child_id'];
          return http.Response(jsonEncode({'token': 'child-$id-token', 'session_id': 99}), 200);
        }
        if (auth == 'Child-Bearer child-13-expired') return http.Response('{"detail":"x"}', 401);
        return http.Response(jsonEncode({'ok': true, 'recorded_today': 1}), 200);
      });
      final client = TgClient.forTesting(
        baseUrl: 'http://api.test',
        httpClient: mock,
        storage: storage,
        onNeedActiveChildId: () async => 12, // the parent UI's active child
      );
      await client.claimChildPrayer(childToken: 'child-13-expired', taskId: 'prayer_s1_fajr');
      final renewals = log.where((l) => l.contains('/child-sessions')).toList();
      expect(renewals, hasLength(1));
      expect(renewals.single, startsWith('POST /api/value-tracking/child-sessions 13 '));
      expect(log.last, allOf(contains('/prayer/claim'), endsWith('Child-Bearer child-13-token')));
      expect(storage.store['tg_child_session_token'], 'child-13-token');
    });

    test('concurrent 401s share one renewal, and both succeed', () async {
      SharedPreferences.setMockInitialValues({kChildModeChildIdKey: 13});
      var renewals = 0;
      final mock = MockClient((req) async {
        final auth = req.headers['Authorization'] ?? '';
        if (req.url.path.endsWith('/child-sessions')) {
          renewals++;
          await Future<void>.delayed(const Duration(milliseconds: 20));
          return http.Response(jsonEncode({'token': 'fresh', 'session_id': 1}), 200);
        }
        if (auth == 'Child-Bearer stale') return http.Response('{"detail":"x"}', 401);
        return http.Response(jsonEncode({'enrolled': true, 'tasks': []}), 200);
      });
      final client = TgClient.forTesting(
          baseUrl: 'http://api.test', httpClient: mock, storage: _Storage());
      final both = await Future.wait([
        client.fetchChildPrayerToday('stale'),
        client.fetchChildPrayerToday('stale'),
      ]);
      expect(both.every((b) => b['enrolled'] == true), isTrue);
      expect(renewals, 1);
    });
  });

  group('4 · a link held back by child mode opens when it ends', () {
    testWidgets('/missions opens once the parent leaves child mode', (tester) async {
      final key = GlobalKey<NavigatorState>();
      final client = FakeProgramsClient()..pending = [_card(41)];
      late _ActiveChildMode mode;
      await pumpPrograms(tester, const Scaffold(body: Text('child surface')),
          client: client,
          navigatorKey: key,
          overrides: [childModeProvider.overrideWith((ref) => mode = _ActiveChildMode(client))]);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/missions'), key);
      await settle(tester);
      expect(find.byType(PendingMissionsScreen), findsNothing);
      mode.leave(); // exit with the PIN — or restore() ending a cold start
      await settle(tester);
      expect(find.byType(PendingMissionsScreen), findsOneWidget);
    });

    testWidgets('the latest held link wins', (tester) async {
      final key = GlobalKey<NavigatorState>();
      final client = FakeProgramsClient()..milestoneByKey['prayer_start'] = milestoneJson();
      late _ActiveChildMode mode;
      await pumpPrograms(tester, const Scaffold(body: Text('child surface')),
          client: client,
          navigatorKey: key,
          overrides: [childModeProvider.overrideWith((ref) => mode = _ActiveChildMode(client))]);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/missions'), key);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/milestones/$kChildId/prayer_start'), key);
      await settle(tester);
      mode.leave();
      await settle(tester);
      expect(find.byType(PendingMissionsScreen), findsNothing);
      expect(client.calls, contains('milestone:prayer_start'));
    });

    testWidgets('a link landing while a cold start restores child mode is not dropped',
        (tester) async {
      FlutterSecureStorage.setMockInitialValues(
          {'tg_child_mode_active': '1', 'tg_child_session_token': 'old'});
      final key = GlobalKey<NavigatorState>();
      final client = _SlowRestore()..pending = [_card(41)];
      final container = await pumpPrograms(tester, const Scaffold(body: Text('home')),
          client: client, navigatorKey: key);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(kChildModeChildIdKey, kChildId);
      final restoring = container.read(childModeProvider.notifier).restore();
      await tester.pump();
      expect(container.read(childModeProvider).active, isTrue); // checking the old surface
      DeepLinkHandler.instance.handleForTest(Uri.parse('/missions'), key);
      await settle(tester);
      expect(find.byType(PendingMissionsScreen), findsNothing);
      client.gate.complete(); // the old surface is gone: back to the parent app
      await restoring;
      await settle(tester);
      expect(container.read(childModeProvider).active, isFalse);
      expect(find.byType(PendingMissionsScreen), findsOneWidget);
    });

    testWidgets('/go saves its referral code even over a child surface', (tester) async {
      final key = GlobalKey<NavigatorState>();
      final client = FakeProgramsClient();
      final referral = _ReferralClient();
      TgClient.shared = referral;
      addTearDown(() => TgClient.shared = null);
      await pumpPrograms(tester, const Scaffold(body: Text('child surface')),
          client: client,
          navigatorKey: key,
          overrides: [childModeProvider.overrideWith((ref) => _ActiveChildMode(client))]);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/go?ref=abc123'), key);
      await settle(tester);
      expect(referral.claimed, ['ABC123']);
      expect(find.text('child surface'), findsOneWidget);
    });
  });

  testWidgets('5 · the list shows while a slow resend is still in flight', (tester) async {
    final client = _Gated()
      ..pending = [_card(41), _card(42)]
      ..confirmCoins = [_coin(41)];
    await pumpPrograms(tester, Builder(
      builder: (context) => Scaffold(
        body: TextButton(
          onPressed: () => Navigator.of(context)
              .push(MaterialPageRoute<bool>(builder: (_) => const PendingMissionsScreen())),
          child: const Text('open'),
        ),
      ),
    ), client: client);
    // An earlier evening's batch that never got through (written after the
    // pump, which resets preferences).
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('missions.confirm_outbox', jsonEncode([_yes(41)]));
    await tester.tap(find.text('open'));
    await settle(tester);
    // The resend is still waiting on the server; tonight's list is here.
    expect(client.settles, 1);
    expect(client.gate.isCompleted, isFalse);
    expect(find.text('Task 41'), findsOneWidget);
    expect(find.text('Task 42'), findsOneWidget);
    client.gate.complete();
    await settle(tester);
    expect(await _balance(), 10);
    // Card 41 was settled by the resend: the list is refetched without it.
    expect(find.text('Task 41'), findsNothing);
    expect(find.text('Task 42'), findsOneWidget);
    expect(await MissionConfirmations.outbox(), isEmpty);
  });

  testWidgets('6 · today\'s day chip says it is today', (tester) async {
    final handle = tester.ensureSemantics();
    await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: FakeProgramsClient());
    await settle(tester);
    final today = find.byKey(const ValueKey('ramadan_day_3'));
    await scrollTo(tester, today);
    final data = tester.getSemantics(today).getSemanticsData();
    expect(data.label, 'Day 3, today');
    expect(data.flagsCollection.isButton, isTrue);
    expect(tester.getSemantics(find.byKey(const ValueKey('ramadan_day_4'))).getSemanticsData().label, 'Day 4');
    handle.dispose();
  });
}
