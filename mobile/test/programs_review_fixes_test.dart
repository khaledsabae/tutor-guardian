// PR #34 review — one test per finding, built from the reviewer's repros
// (/tmp/review-pr34/zz_review_repro_test.dart) and turned to assert the fix.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/coins/coins_service.dart';
import 'package:almorabbi/features/deeplink/deep_link_handler.dart';
import 'package:almorabbi/features/missions/mission_confirmations.dart';
import 'package:almorabbi/features/missions/pending_missions_screen.dart';
import 'package:almorabbi/features/programs/providers/programs_providers.dart';
import 'package:almorabbi/features/programs/screens/prayer_journey_screen.dart';
import 'package:almorabbi/features/programs/screens/programs_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_recap_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_screen.dart';
import 'package:almorabbi/features/programs/widgets/child_prayer_card.dart';
import 'package:almorabbi/features/programs/widgets/programs_home_card.dart';
import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/routine/screens/habit_child_mode_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

import 'programs_support.dart';

class _SlowSettle extends FakeProgramsClient {
  final gate = Completer<void>();
  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    calls.add('settle');
    await gate.future;
    return applySettle(items);
  }
}

/// Applies the batch, like the real server, but the answer never arrives.
class _LostAnswer extends FakeProgramsClient {
  bool lose = true;
  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    calls.add('settle');
    bodies.add({'items': items});
    final answer = applySettle(items);
    if (lose) throw const TgApiError(null, 'timeout');
    return answer;
  }
}

class _SlowEnrol extends FakeProgramsClient {
  final gate = Completer<void>();
  @override
  Future<Map<String, dynamic>> enrolPrayerJourney(int childId,
      {String? track, int? startStage, bool restart = false}) async {
    calls.add('enrol');
    await gate.future;
    return journey = journeyJson();
  }
}

class _ActiveChildMode extends ChildModeNotifier {
  _ActiveChildMode(super.client, [ChildModeState? state]) {
    this.state = state ?? const ChildModeState(active: true, childId: kChildId);
  }
}

final _card = {
  'mission_id': 41, 'title_ar': 'I pray beside Mum or Dad', 'child_name': kChildName,
  'estimated_minutes': 7, 'program': 'prayer_journey', 'coins': 10,
};
final _coins = [
  {'mission_id': 41, 'child_id': kChildId, 'task_id': 'prayer_s1_pray_beside', 'coins': 10},
];

Widget _opener(Widget Function() screen) => Builder(
      builder: (context) => Scaffold(
        body: TextButton(
          onPressed: () => Navigator.of(context).push(MaterialPageRoute<bool>(builder: (_) => screen())),
          child: const Text('open'),
        ),
      ),
    );

Future<int> _balance() async => (await CoinsService.instance.read()).balance;

void main() {
  group('1 · leaving the evening screen mid-confirm', () {
    testWidgets('still pays the coins, once, with no error', (tester) async {
      final client = _SlowSettle()
        ..pending = [_card]
        ..confirmCoins = _coins;
      await pumpPrograms(tester, _opener(() => const PendingMissionsScreen()), client: client);
      final start = await _balance();
      await tester.tap(find.text('open'));
      await settle(tester);
      await tester.tap(find.byType(FilledButton));
      await tester.pump();
      tester.state<NavigatorState>(find.byType(Navigator)).pop(); // back, mid-request
      await settle(tester, 25); // the page transition runs out
      expect(find.byType(PendingMissionsScreen), findsNothing);
      client.gate.complete();
      await settle(tester);
      expect(tester.takeException(), isNull);
      expect(await _balance() - start, 10);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getStringList('programs.credited_prayer_missions'), contains('41'));
      expect(await MissionConfirmations.outbox(), isEmpty);
    });
  });

  group('2 · a lost answer', () {
    testWidgets('reopening resends the batch and pays what the server applied', (tester) async {
      final client = _LostAnswer()
        ..pending = [_card]
        ..confirmCoins = _coins;
      await pumpPrograms(tester, _opener(() => const PendingMissionsScreen()), client: client);
      final start = await _balance();
      await tester.tap(find.text('open'));
      await settle(tester);
      await tester.tap(find.byType(FilledButton));
      await settle(tester);
      // Applied on the server, never answered: nothing paid, the batch waits.
      expect(client.pending, isEmpty);
      expect(await _balance() - start, 0);
      expect((await MissionConfirmations.outbox()).single['mission_id'], 41);

      tester.state<NavigatorState>(find.byType(Navigator)).pop();
      await settle(tester, 25);
      client.lose = false; // the connection is back
      await tester.tap(find.text('open'));
      await settle(tester);
      expect(await _balance() - start, 10);
      // Shown by every Scaffold under the messenger while the page slides in.
      expect(find.text('10 coins added'), findsWidgets);
      expect(await MissionConfirmations.outbox(), isEmpty);
      // The retry carried the same decision.
      expect(client.bodies.last['items'], [
        {'mission_id': 41, 'confirmed': true},
      ]);
    });

    test('a new batch carries the waiting one; a fresh decision wins', () async {
      SharedPreferences.setMockInitialValues({});
      final client = _LostAnswer()
        ..pending = [_card, {..._card, 'mission_id': 42}]
        ..confirmCoins = _coins;
      await expectLater(
        MissionConfirmations.send(client, [{'mission_id': 41, 'confirmed': true}]),
        throwsA(isA<TgApiError>()),
      );
      client.lose = false;
      final result = await MissionConfirmations.send(client, [
        {'mission_id': 42, 'confirmed': false},
        {'mission_id': 41, 'confirmed': true},
      ]);
      expect(result.coins, 10);
      expect(client.bodies.last['items'], hasLength(2));
      expect(await MissionConfirmations.outbox(), isEmpty);
    });

    test('a non-HTTP failure keeps the batch too', () async {
      SharedPreferences.setMockInitialValues({});
      final client = _Broken()..pending = [_card];
      await expectLater(
        MissionConfirmations.send(client, [{'mission_id': 41, 'confirmed': true}]),
        throwsA(isA<StateError>()),
      );
      expect(await MissionConfirmations.outbox(), hasLength(1));
    });

    testWidgets('…and the screen does not spin forever on it', (tester) async {
      final client = _Broken()..pending = [_card];
      await pumpPrograms(tester, _opener(() => const PendingMissionsScreen()), client: client);
      await tester.tap(find.text('open'));
      await settle(tester);
      await tester.tap(find.byType(FilledButton));
      await settle(tester);
      expect(tester.takeException(), isNull);
      expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed, isNotNull);
    });
  });

  group('3 · parent-confirmed program coins and the daily cap', () {
    testWidgets('are paid in full past the games\' cap, and the snackbar says what was paid', (tester) async {
      final client = FakeProgramsClient()
        ..pending = [_card, {..._card, 'mission_id': 42}]
        ..confirmCoins = [..._coins, {..._coins.first, 'mission_id': 42, 'child_id': 13}];
      await pumpPrograms(tester, _opener(() => const PendingMissionsScreen()), client: client);
      await CoinsService.instance.earn(50); // the games earned 50 of today's 60
      final start = await _balance();
      await tester.tap(find.text('open'));
      await settle(tester);
      await tester.tap(find.byType(FilledButton));
      await settle(tester);
      expect(await _balance() - start, 20);
      expect(find.text('20 coins added'), findsOneWidget);
    });

    test('earn reports what it granted, not what was asked', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await CoinsService.instance.earn(50), 50);
      expect(await CoinsService.instance.earn(50), 10); // the cap
      expect(await CoinsService.instance.earn(5), 0);
      // Program coins do not spend the games' allowance either.
      expect(await CoinsService.instance.creditConfirmedMissions([{'mission_id': 1, 'coins': 10}]), 10);
      expect((await CoinsService.instance.read()).earnableToday, 0);
      expect((await CoinsService.instance.read()).balance, 70);
    });
  });

  group('4 · no link opens a parent screen over child mode', () {
    for (final link in ['/missions', '/license', '/inbox', '/l/lesson_7-9_x', '/p/path_7-9_x',
        '/milestones/$kChildId/prayer_start', '/go?ref=ABC']) {
      testWidgets(link, (tester) async {
        final key = GlobalKey<NavigatorState>();
        final client = FakeProgramsClient()..pending = [_card];
        await pumpPrograms(tester, const Scaffold(body: Text('child surface')),
            client: client,
            navigatorKey: key,
            overrides: [childModeProvider.overrideWith((ref) => _ActiveChildMode(client))]);
        DeepLinkHandler.instance.handleForTest(Uri.parse(link), key);
        await settle(tester);
        expect(find.text('child surface'), findsOneWidget);
        expect(find.byType(PendingMissionsScreen), findsNothing);
        expect(tester.state<NavigatorState>(find.byType(Navigator)).canPop(), isFalse);
      });
    }

    testWidgets('outside child mode /missions still opens the evening screen', (tester) async {
      final key = GlobalKey<NavigatorState>();
      await pumpPrograms(tester, const Scaffold(body: Text('home')),
          client: FakeProgramsClient()..pending = [_card], navigatorKey: key);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/missions'), key);
      await settle(tester);
      expect(find.byType(PendingMissionsScreen), findsOneWidget);
    });
  });

  testWidgets('5 · a quick double tap on a two-a-day task records once', (tester) async {
    final client = FakeProgramsClient()..childPrayer = childPrayerJson(slotsLeft: 2);
    var reads = 0;
    await pumpPrograms(tester, const Scaffold(body: SingleChildScrollView(child: ChildPrayerCard())),
        client: client,
        overrides: [
          childPrayerTokenProvider.overrideWithValue(() async {
            // secure storage is a platform round trip
            if (reads++ > 0) await Future<void>.delayed(const Duration(milliseconds: 80));
            return 'child-tok';
          }),
        ]);
    await settle(tester);
    final button = find.byKey(const ValueKey('child_prayer_claim_prayer_s1_pray_beside'));
    await tester.tap(button);
    await tester.pump(const Duration(milliseconds: 30));
    await tester.tap(button, warnIfMissed: false);
    await settle(tester, 10);
    expect(client.calls.where((c) => c.startsWith('claim:')), hasLength(1));
  });

  group('6 · accessibility', () {
    testWidgets('a program row is one button with its label and subtitle', (tester) async {
      final handle = tester.ensureSemantics();
      final client = FakeProgramsClient()..programs = programsJson(enrolled: true, stage: 2);
      await pumpPrograms(tester, const ProgramsScreen(), client: client);
      await settle(tester);
      final data = tester.getSemantics(find.text('The Prayer Journey').first).getSemanticsData();
      expect(data.flagsCollection.isButton, isTrue);
      expect(data.hasAction(SemanticsAction.tap), isTrue);
      expect(data.label, contains('Stage 2'));
      handle.dispose();
    });

    testWidgets('the Home card has no tappable row inside a tappable card', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpPrograms(tester, const Scaffold(body: SingleChildScrollView(child: ProgramsHomeCard())),
          client: FakeProgramsClient());
      await settle(tester);
      final card = find.byKey(const ValueKey('programs_home_card'));
      final wells = find.descendant(of: card, matching: find.byType(InkWell));
      expect(wells, findsWidgets);
      for (final well in wells.evaluate()) {
        expect(find.descendant(of: find.byWidget(well.widget), matching: find.byType(InkWell)), findsNothing);
      }
      for (final text in ['Family programs', 'Day 3 of 30 of Ramadan']) {
        final data = tester.getSemantics(find.text(text)).getSemanticsData();
        expect(data.flagsCollection.isButton, isTrue, reason: text);
      }
      handle.dispose();
    });

    testWidgets('a day of the month is a button that says which day', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: FakeProgramsClient());
      await settle(tester);
      final day5 = find.byKey(const ValueKey('ramadan_day_5'));
      await scrollTo(tester, day5);
      final data = tester.getSemantics(day5).getSemanticsData();
      expect(data.flagsCollection.isButton, isTrue);
      expect(data.label, 'Day 5');
      handle.dispose();
    });
  });

  group('7 · lifecycle', () {
    testWidgets('leaving the journey mid-change still refreshes it and the overview', (tester) async {
      final client = _SlowEnrol()..journey = journeyJson(enrolled: false);
      final container = await pumpPrograms(
          tester, _opener(() => const PrayerJourneyScreen(childId: kChildId)), client: client);
      await container.read(programsOverviewProvider.future);
      final before = client.calls.where((c) => c == 'programs').length;
      await tester.tap(find.text('open'));
      await settle(tester);
      final enrol = find.byKey(const ValueKey('prayer_enrol'));
      await scrollTo(tester, enrol);
      await tester.tap(enrol);
      await tester.pump();
      tester.state<NavigatorState>(find.byType(Navigator)).pop();
      await settle(tester, 25);
      client.gate.complete();
      await settle(tester);
      expect(tester.takeException(), isNull);
      await container.read(programsOverviewProvider.future);
      expect(client.calls.where((c) => c == 'programs').length, before + 1);
    });

    testWidgets('the prayer card is a sliver header, not an item a list recycles', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const HabitChildModeScreen(),
          client: client,
          overrides: [
            childPrayerTokenProvider.overrideWithValue(() async => 'child-tok'),
            childModeProvider.overrideWith((ref) => _ActiveChildMode(
                client,
                ChildModeState(
                  active: true,
                  childId: kChildId,
                  day: HabitDay(
                    childId: kChildId,
                    date: '2026-10-04',
                    events: const [],
                    habits: [
                      for (var i = 0; i < 12; i++)
                        TodayHabitItem(category: HabitCategory.worship, habitName: 'Habit $i', source: 'default'),
                    ],
                  ),
                ))),
          ]);
      await settle(tester);
      final card = find.byType(ChildPrayerCard);
      expect(card, findsOneWidget);
      expect(find.ancestor(of: card, matching: find.byType(SliverToBoxAdapter)), findsOneWidget);
      // Scrolled far away, it is still mounted (a claim in flight survives).
      await tester.drag(find.byType(CustomScrollView), const Offset(0, -3000));
      await settle(tester);
      expect(find.byType(ChildPrayerCard, skipOffstage: false), findsOneWidget);
    });
  });

  testWidgets('8 · a 401 the client could not recover from hides the card', (tester) async {
    final client = _Unauthorized();
    await pumpPrograms(tester, const Scaffold(body: ChildPrayerCard()),
        client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'tok')]);
    await settle(tester);
    expect(find.byKey(const ValueKey('child_prayer_card')), findsNothing);
  });

  group('9 · copy', () {
    final ar = lookupAppLocalizations(const Locale('ar'));
    final en = lookupAppLocalizations(const Locale('en'));

    test('the empty recap points at the control that exists', () {
      expect(en.recapEmpty, contains(en.ramadanMarksTitle));
      expect(ar.recapEmpty, contains(ar.ramadanMarksTitle));
      for (final s in [ar.recapEmpty, ar.ramadanDayPreviewNote]) {
        expect(s.contains('«تمّ»'), isFalse, reason: s);
      }
      expect(en.recapEmpty.contains('«Done»'), isFalse);
    });

    test('the month-length choice says plainly what it follows', () {
      expect(en.ramadanDaysAuto, 'Follow the official announcement');
      expect(en.ramadanShiftNone, 'On the announced day');
      expect(ar.ramadanDaysAuto, 'حسب الإعلان الرسمي');
    });
  });

  group('10 · last season\'s card during the next countdown', () {
    Map<String, dynamic> countdown1449() => {
          ...ramadanTodayJson(state: 'upcoming'),
          'season': {...seasonJson(), 'hijri_year': 1449, 'starts_on': '2028-01-28', 'eid_on': '2028-02-27'},
        };

    testWidgets('stays reachable', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = countdown1449();
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      final link = find.byKey(const ValueKey('ramadan_last_recap'));
      await scrollTo(tester, link);
      await tester.tap(link);
      await settle(tester);
      expect(find.byType(RamadanRecapScreen), findsOneWidget);
    });

    testWidgets('is absent before the very first season', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(state: 'upcoming') // 1448 itself
        ..recap = recapJson(available: false);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      await scrollTo(tester, find.text('Who sees what'));
      expect(find.byKey(const ValueKey('ramadan_last_recap')), findsNothing);
    });
  });
}

class _Broken extends FakeProgramsClient {
  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
          List<Map<String, dynamic>> items) async =>
      throw StateError('not an HTTP failure');
}

class _Unauthorized extends FakeProgramsClient {
  @override
  Future<Map<String, dynamic>> fetchChildPrayerToday(String childToken) async =>
      throw TgClient.childSessionExpired;
}
