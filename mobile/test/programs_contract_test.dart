// The contract changes from the PR #32 review (MOBILE_API §11), pinned on the
// client side:
//   · each program stands alone — a null section is hidden, never an error;
//   · child mode `available: false` shows nothing;
//   · `stage_changed` / `already_graduated` refetch quietly;
//   · the confirm's `coins` is idempotent — the device pays each mission once.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/coins/coins_service.dart';
import 'package:almorabbi/features/hub/screens/hub_screen.dart';
import 'package:almorabbi/features/missions/pending_missions_screen.dart';
import 'package:almorabbi/features/programs/data/prayer_coins_ledger.dart';
import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:almorabbi/features/programs/screens/prayer_journey_screen.dart';
import 'package:almorabbi/features/programs/screens/programs_screen.dart';
import 'package:almorabbi/features/programs/widgets/child_prayer_card.dart';

import 'programs_support.dart';

Map<String, dynamic> _withNulls({required List<String> unavailable}) {
  final j = programsJson();
  final child = Map<String, dynamic>.from((j['children'] as List).single as Map);
  if (unavailable.contains('ramadan_family')) {
    j['ramadan'] = null;
    child['ramadan'] = null;
  }
  if (unavailable.contains('prayer_journey')) child['prayer_journey'] = null;
  if (unavailable.contains('milestones')) child['milestones'] = null;
  return {...j, 'unavailable': unavailable, 'children': [child]};
}

class _GraduatedClient extends FakeProgramsClient {
  int journeyReads = 0;

  @override
  Future<Map<String, dynamic>> fetchPrayerJourney(int childId) async {
    journeyReads++;
    return super.fetchPrayerJourney(childId);
  }

  @override
  Future<Map<String, dynamic>> graduatePrayerJourney(int childId) async =>
      throw const TgApiError(409, 'x', code: 'already_graduated');
}

class _StaleClient extends FakeProgramsClient {
  int journeyReads = 0;

  @override
  Future<Map<String, dynamic>> fetchPrayerJourney(int childId) async {
    journeyReads++;
    return super.fetchPrayerJourney(childId);
  }

  @override
  Future<Map<String, dynamic>> setPrayerJourneyStage(int childId, int stage) async =>
      throw const TgApiError(409, 'x', code: 'stage_changed');
}

void main() {
  group('each program stands alone', () {
    test('null sections parse as "not served", and the list says which', () {
      final o = ProgramsOverview.fromJson(_withNulls(unavailable: ['ramadan_family', 'milestones']));
      expect(o.unavailable, ['ramadan_family', 'milestones']);
      expect(o.anyServed, isTrue);
      expect(o.ramadan.isActive, isFalse);
      final child = o.children.single;
      expect(child.milestonesServed, isFalse);
      expect(child.prayer.eligibleTrack, PrayerTrack.journey); // still served
      expect(ProgramsOverview.fromJson(programsJson()).children.single.milestonesServed, isTrue);
    });

    test('nothing served at all is nothing to enter', () {
      final o = ProgramsOverview.fromJson(
          _withNulls(unavailable: ['ramadan_family', 'prayer_journey', 'milestones']));
      expect(o.anyServed, isFalse);
    });

    testWidgets('the list hides the unserved programs and keeps the rest', (tester) async {
      final client = FakeProgramsClient()..programs = _withNulls(unavailable: ['ramadan_family', 'milestones']);
      await pumpPrograms(tester, const ProgramsScreen(), client: client);
      await settle(tester);
      expect(find.text('Family Ramadan'), findsNothing);
      expect(find.text('Important stages'), findsNothing);
      expect(find.text('The Prayer Journey'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('no program served: no «المزيد» tile', (tester) async {
      final client = FakeProgramsClient()
        ..programs = _withNulls(unavailable: ['ramadan_family', 'prayer_journey', 'milestones']);
      await pumpPrograms(tester, const HubScreen(), client: client);
      await settle(tester);
      expect(find.text('Family programs'), findsNothing);
    });
  });

  group('child mode', () {
    testWidgets('`available: false` shows nothing', (tester) async {
      final client = FakeProgramsClient()..childPrayer = {...childPrayerJson(), 'available': false};
      await pumpPrograms(tester, const Scaffold(body: ChildPrayerCard()),
          client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'tok')]);
      await settle(tester);
      expect(find.byKey(const ValueKey('child_prayer_card')), findsNothing);
    });

    testWidgets('a claim answered 503 program_unavailable takes the card away quietly', (tester) async {
      final client = FakeProgramsClient()
        ..claimError = const TgApiError(503, 'x', code: 'program_unavailable');
      await pumpPrograms(tester, const Scaffold(body: SingleChildScrollView(child: ChildPrayerCard())),
          client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'tok')]);
      await settle(tester);
      await tester.tap(find.byKey(const ValueKey('child_prayer_claim_prayer_s1_pray_beside')));
      await settle(tester);
      expect(find.byKey(const ValueKey('child_prayer_card')), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });

  testWidgets('a stage that moved under a stale screen refetches, without an error', (tester) async {
    final client = _StaleClient()..journey = journeyJson(advance: true);
    await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
    await settle(tester);
    final reads = client.journeyReads;
    await tester.tap(find.byKey(const ValueKey('prayer_advance')));
    await settle(tester);
    expect(client.journeyReads, greaterThan(reads));
    expect(find.byType(SnackBar), findsNothing);
  });

  testWidgets('a second graduation tap refetches, with no error and no second party', (tester) async {
    final client = _GraduatedClient()..journey = journeyJson(stage: 6, graduate: true);
    await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
    await settle(tester);
    final reads = client.journeyReads;
    final button = find.byKey(const ValueKey('prayer_graduate'));
    await scrollTo(tester, button);
    await tester.tap(button);
    await settle(tester, 10);
    expect(client.journeyReads, greaterThan(reads));
    expect(find.byType(SnackBar), findsNothing);
    expect(find.byType(Dialog), findsNothing); // no celebration for a repeat
  });

  test('after 1448\'s bridge the next season counts down — not off season', () {
    final next = {
      ...ramadanTodayJson(state: 'upcoming'),
      'season': {
        ...seasonJson(),
        'hijri_year': 1449,
        'starts_on': '2028-01-28',
        'eid_on': '2028-02-27',
      },
      'days_until_start': 290,
    };
    final t = RamadanToday.fromJson(next);
    expect(t.state, RamadanState.upcoming);
    expect(t.season!.hijriYear, 1449);
    expect(t.daysUntilStart, 290);
    expect(RamadanOverview.fromJson({'state': 'upcoming', 'season': next['season'], 'days_until_start': 290}).isActive,
        isTrue);
  });

  group('coins: each mission paid once', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('a duplicate in one batch, and a retried batch, pay nothing more', () async {
      final batch = [
        {'mission_id': 41, 'coins': 10},
        {'mission_id': 41, 'coins': 10},
        {'mission_id': 42, 'coins': 5},
      ];
      expect(await PrayerCoinsLedger.takeNew(batch), 15);
      expect(await PrayerCoinsLedger.takeNew(batch), 0); // the retry
      expect(await PrayerCoinsLedger.takeNew([{'mission_id': 43, 'coins': 10}]), 10);
    });

    test('keeps only the recent ids', () async {
      await PrayerCoinsLedger.takeNew([
        for (var i = 0; i < PrayerCoinsLedger.keep + 20; i++) {'mission_id': i, 'coins': 1},
      ]);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getStringList('programs.credited_prayer_missions'), hasLength(PrayerCoinsLedger.keep));
    });

    testWidgets('a confirm retried after a lost answer credits nothing twice', (tester) async {
      final client = FakeProgramsClient()
        ..pending = [
          {'mission_id': 41, 'title_ar': 'I pray beside Mum or Dad', 'child_name': kChildName,
           'estimated_minutes': 7, 'program': 'prayer_journey', 'coins': 10},
        ]
        ..confirmCoins = [
          {'mission_id': 41, 'child_id': kChildId, 'task_id': 'prayer_s1_pray_beside', 'coins': 10},
        ];
      await pumpPrograms(
        tester,
        Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.of(context)
                  .push(MaterialPageRoute<bool>(builder: (_) => const PendingMissionsScreen())),
              child: const Text('open'),
            ),
          ),
        ),
        client: client,
      );
      final start = (await CoinsService.instance.read()).balance;
      for (var round = 0; round < 2; round++) {
        await tester.tap(find.text('open'));
        await settle(tester);
        await tester.tap(find.byType(FilledButton));
        await settle(tester);
      }
      expect(client.calls.where((c) => c == 'settle'), hasLength(2));
      expect((await CoinsService.instance.read()).balance - start, 10);
    });
  });
}
