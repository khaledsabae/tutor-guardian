// «رحلة الصلاة»: the parent's view, the child's card in child mode, and the
// evening confirmation that turns a claim into coins.
//
// The loop the plan rests on: the parent starts the journey → the child taps
// once in child mode → the parent confirms in the evening (the existing
// missions screen) → the device credits the coins toward a covenant.
// Nothing on any of these screens may read as a punishment or a shortfall.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/coins/coins_service.dart';
import 'package:almorabbi/features/missions/pending_missions_screen.dart';
import 'package:almorabbi/features/programs/screens/prayer_journey_screen.dart';
import 'package:almorabbi/features/programs/widgets/child_prayer_card.dart';
import 'package:almorabbi/features/routine/screens/child_mode_lock_screen.dart';

import 'programs_support.dart';

final _harshWords = RegExp(r'miss|fail|behind|punish|lazy|فات|تقصير|عقوبة|كسول', caseSensitive: false);

void expectGentle(WidgetTester tester) {
  for (final t in tester.widgetList<Text>(find.byType(Text))) {
    final text = t.data ?? t.textSpan?.toPlainText() ?? '';
    expect(_harshWords.hasMatch(text), isFalse, reason: 'harsh wording on screen: "$text"');
  }
}

void main() {
  group('the parent', () {
    testWidgets('not started: what it is, then one button to start', (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(enrolled: false);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('Twelve weeks from love to responsibility'), findsOneWidget);
      final start = find.byKey(const ValueKey('prayer_enrol'));
      await scrollTo(tester, start);
      await tester.tap(start);
      await settle(tester);
      expect(client.calls, contains('enrol'));
      expect(client.bodies.last, {'track': null, 'start_stage': null, 'restart': false});
      // Now on the journey.
      await scrollTo(tester, find.text('Stage 1 of 6'));
    });

    testWidgets('on the journey: the stage, the tasks as counts, the hand-over', (tester) async {
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: FakeProgramsClient());
      await settle(tester);
      expect(find.text('Stage 1 of 6'), findsOneWidget);
      expect(find.text('Week 1'), findsOneWidget);
      expect(find.text('Prayer is a meeting we love'), findsOneWidget);
      await scrollTo(tester, find.text('I pray beside Mum or Dad'));
      expect(find.text('This week: 2'), findsOneWidget);
      expect(find.text('Suggested: 5 a week'), findsOneWidget); // a suggestion, not a quota
      expect(find.text('🪙 10 coins'), findsOneWidget);
      final handOver = find.byKey(const ValueKey('prayer_hand_over'));
      await scrollTo(tester, handOver);
      await tester.tap(handOver);
      await settle(tester);
      final lock = tester.widget<ChildModeLockScreen>(find.byType(ChildModeLockScreen));
      expect(lock.childId, kChildId);
      expect(lock.surface, 'habit'); // the surface that carries the prayer card
    });

    testWidgets('a profile still set to 4–6 is pointed to its age group, not to a refusal', (tester) async {
      final client = FakeProgramsClient()
        ..children = [
          {'id': kChildId, 'name': kChildName, 'age_group': '4-6', 'birth_month': '2019-03', 'created_at': '', 'updated_at': ''},
        ];
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      final note = find.byKey(const ValueKey('prayer_hand_over_needs_band'));
      await scrollTo(tester, note);
      expect(note, findsOneWidget);
      expect(find.byKey(const ValueKey('prayer_hand_over')), findsNothing);
    });

    testWidgets('claims waiting: one tap to the evening confirmation', (tester) async {
      final client = FakeProgramsClient()
        ..journey = journeyJson(pending: 1)
        ..pending = [
          {'mission_id': 41, 'title_ar': 'I pray beside Mum or Dad', 'child_name': kChildName, 'estimated_minutes': 7,
           'program': 'prayer_journey', 'task_id': 'prayer_s1_pray_beside', 'coins': 10},
        ];
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('1 task waiting for you to confirm'), findsOneWidget);
      await tester.tap(find.text('Confirm now'));
      await settle(tester);
      expect(find.byType(PendingMissionsScreen), findsOneWidget);
    });

    testWidgets("a stage's weeks done: moving on is suggested, and the parent's call", (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(advance: true);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text("This stage's weeks are done"), findsOneWidget);
      expect(find.textContaining("it's your call"), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('prayer_advance')));
      await settle(tester);
      expect(client.bodies.last, {'stage': 2});
    });

    testWidgets('graduation is a celebration with the certificate', (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(stage: 6, graduate: true);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      final button = find.byKey(const ValueKey('prayer_graduate'));
      await scrollTo(tester, button);
      await tester.tap(button);
      await settle(tester, 10);
      expect(client.calls, contains('graduate'));
      expect(find.text('The holder completed twelve weeks of learning to pray.'), findsWidgets);
    });

    testWidgets('a child the journey is not for is told so, without a button', (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(enrolled: false, eligible: null, allowed: []);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text("The Prayer Journey isn't for سارة's age right now."), findsOneWidget);
      expect(find.byKey(const ValueKey('prayer_enrol')), findsNothing);
    });

    testWidgets('a refused change is explained in words', (tester) async {
      final client = _RefusingClient()..journey = journeyJson(advance: true);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      await tester.tap(find.byKey(const ValueKey('prayer_advance')));
      await settle(tester);
      expect(find.text('You move on one stage at a time.'), findsOneWidget);
    });

    for (final locale in const [Locale('en'), Locale('ar')]) {
      testWidgets('the parent screen is gentle (${locale.languageCode})', (tester) async {
        await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId),
            client: FakeProgramsClient()..journey = journeyJson(pending: 2, advance: true), locale: locale);
        await settle(tester);
        expectGentle(tester);
      });
    }
  });

  group('the child, in child mode', () {
    testWidgets('one tap, recorded at once, and the parent sees it tonight', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const Scaffold(body: SingleChildScrollView(child: ChildPrayerCard())),
          client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'child-tok')]);
      await settle(tester);
      expect(find.text('My prayer today'), findsOneWidget);
      expect(find.text('I pray beside Mum or Dad'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('child_prayer_claim_prayer_s1_pray_beside')));
      await settle(tester);
      expect(client.calls, contains('claim:prayer_s1_pray_beside'));
      expect(find.text('Recorded ✓ Mum or Dad will see it this evening.'), findsOneWidget);
      expect(find.byKey(const ValueKey('child_prayer_claim_prayer_s1_pray_beside')), findsNothing);
    });

    testWidgets('already done today shows ✓, not an error', (tester) async {
      final client = FakeProgramsClient()..childPrayer = childPrayerJson(slotsLeft: 0);
      await pumpPrograms(tester, const Scaffold(body: SingleChildScrollView(child: ChildPrayerCard())),
          client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'child-tok')]);
      await settle(tester);
      expect(find.text('Done for today ✓'), findsOneWidget);
      expect(find.byType(FilledButton), findsNothing);
    });

    testWidgets('a "day complete" refusal also lands as ✓', (tester) async {
      final client = FakeProgramsClient()..claimError = const TgApiError(409, 'x', code: 'day_complete');
      await pumpPrograms(tester, const Scaffold(body: SingleChildScrollView(child: ChildPrayerCard())),
          client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'child-tok')]);
      await settle(tester);
      await tester.tap(find.byKey(const ValueKey('child_prayer_claim_prayer_s1_pray_beside')));
      await settle(tester);
      expect(find.text('Done for today ✓'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('not on the journey (or the preparation track): nothing at all', (tester) async {
      final client = FakeProgramsClient()..childPrayer = childPrayerJson(enrolled: false);
      await pumpPrograms(tester, const Scaffold(body: ChildPrayerCard()),
          client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'child-tok')]);
      await settle(tester);
      expect(find.byKey(const ValueKey('child_prayer_card')), findsNothing);
    });

    testWidgets('no child token: no call, nothing shown', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const Scaffold(body: ChildPrayerCard()),
          client: client, overrides: [childPrayerTokenProvider.overrideWithValue(() async => null)]);
      await settle(tester);
      expect(client.calls, isNot(contains('child_prayer')));
      expect(find.byKey(const ValueKey('child_prayer_card')), findsNothing);
    });
  });

  group('the evening confirmation', () {
    testWidgets('a prayer card shows its coins, and confirming credits them on the device', (tester) async {
      final client = FakeProgramsClient()
        ..pending = [
          {'mission_id': 41, 'title_ar': 'I pray beside Mum or Dad', 'child_name': kChildName, 'estimated_minutes': 7,
           'program': 'prayer_journey', 'task_id': 'prayer_s1_pray_beside', 'coins': 10},
          {'mission_id': 42, 'title_ar': 'Green hunter', 'child_name': kChildName, 'estimated_minutes': 15},
        ]
        ..confirmCoins = [
          {'mission_id': 41, 'child_id': kChildId, 'task_id': 'prayer_s1_pray_beside', 'coins': 10},
        ];
      await pumpPrograms(
        tester,
        Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: TextButton(
                onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<bool>(builder: (_) => const PendingMissionsScreen())),
                child: const Text('open'),
              ),
            ),
          ),
        ),
        client: client,
      );
      final before = (await CoinsService.instance.read()).balance;
      await tester.tap(find.text('open'));
      await settle(tester);
      expect(find.textContaining('🪙 10 coins'), findsOneWidget); // the prayer card
      expect(find.textContaining('Green hunter'), findsOneWidget);
      await tester.tap(find.byType(FilledButton));
      await settle(tester);
      expect(client.calls, contains('settle'));
      final after = (await CoinsService.instance.read()).balance;
      expect(after - before, 10);
      expect(find.text('10 coins added'), findsOneWidget);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getInt('coins.balance'), after);
    });
  });
}

class _RefusingClient extends FakeProgramsClient {
  @override
  Future<Map<String, dynamic>> setPrayerJourneyStage(int childId, int stage) async =>
      throw const TgApiError(409, 'x', code: 'one_stage_at_a_time', details: {'next_stage': 2});
}
