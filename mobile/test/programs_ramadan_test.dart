// «رمضان العائلة» on screen: every season state, the family's tick-only
// marks, the fasting ladder with its safety guidance first, the family's own
// moon sighting, and the «رمضان عائلتنا» card that never carries the
// children's fasting.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:almorabbi/features/programs/screens/fasting_ladder_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_day_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_recap_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_screen.dart';
import 'package:almorabbi/features/programs/widgets/ramadan_recap_card.dart';

import 'programs_support.dart';

/// Words that would turn a tick list into a shame metric.
final _missWords = RegExp(r'miss|fail|behind|late|فات|فائت|تأخّر|فشل', caseSensitive: false);

void expectNoMissLanguage(WidgetTester tester) {
  final texts = tester.widgetList<Text>(find.byType(Text)).map((t) => t.data ?? t.textSpan?.toPlainText() ?? '');
  for (final t in texts) {
    expect(_missWords.hasMatch(t), isFalse, reason: 'shame wording on screen: "$t"');
  }
}

void main() {
  group('during the month', () {
    testWidgets("today's card: challenge, the child's part, the note, the Quran, the story", (tester) async {
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: FakeProgramsClient());
      await settle(tester);
      expect(find.text('Day 3'), findsOneWidget);
      expect(find.text('The first ten days'), findsOneWidget);
      expect(find.text('The iftar table'), findsOneWidget);
      expect(find.text('Set the table together and begin with Bismillah'), findsOneWidget);
      expect(find.text('10 min'), findsOneWidget);
      expect(find.text('At iftar'), findsOneWidget);
      await scrollTo(tester, find.text("سارة's part"));
      expect(find.text('Your job: water and cups on the table.'), findsOneWidget);
      // The hadith: Arabic text and source, and in English its meaning, labelled.
      await scrollTo(tester, find.text('يا غلام سم الله وكل بيمينك وكل مما يليك'));
      expect(find.text('صحيح البخاري — حديث ٥٣٧٦'), findsOneWidget);
      expect(find.text('Meaning'), findsOneWidget);
      // The Quran in Arabic, never translated; English says so.
      await scrollTo(tester, find.text('The Quran is shown in its Arabic text.'));
      expect(find.textContaining('آية 1'), findsOneWidget);
      await scrollTo(tester, find.text("Parents' khatma: juz 3"));
      await scrollTo(tester, find.text("Tonight's story: Abdullah and Bismillah"));
    });

    testWidgets('marks are ticks: tick, untick, and no "missed" anywhere', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      final chip = find.byKey(const ValueKey('ramadan_mark_challenge_done'));
      await scrollTo(tester, chip);
      expect(tester.widget<FilterChip>(chip).selected, isFalse);
      await tester.tap(chip);
      await settle(tester);
      expect(client.bodies.last, {'mark': 'challenge_done', 'day': 3, 'done': true, 'choice_index': null});
      expect(tester.widget<FilterChip>(chip).selected, isTrue);
      await tester.tap(chip);
      await settle(tester);
      expect(client.bodies.last['done'], isFalse);
      expect(tester.widget<FilterChip>(chip).selected, isFalse);
      expect(find.text("Tick only what you did — anything else simply isn't recorded."), findsOneWidget);
      expectNoMissLanguage(tester);
    });

    testWidgets('day 28: the family word is picked from the list, never typed', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(
          day: 28,
          content: dayContentJson(day: 28, tracks: ['challenge_done', 'family_word'], word: true),
          marks: {'challenge_done': false, 'family_word': null},
        );
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      await scrollTo(tester, find.text('Joy'));
      expect(find.byType(TextField), findsNothing);
      await tester.tap(find.text('Joy'));
      await settle(tester);
      expect(client.bodies.last['mark'], 'family_word');
      expect(client.bodies.last['choice_index'], 2);
    });

    testWidgets('odd nights are named as odd nights, never as Laylat al-Qadr', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(day: 22, content: dayContentJson(day: 22, oddNight: true));
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('✨ Tonight is one of the odd nights of the last ten.'), findsOneWidget);
      expect(find.textContaining('Qadr'), findsNothing);
    });

    testWidgets('day 29 evening asks "Is tomorrow Eid?"; the morning does not', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = ramadanTodayJson(day: 29, content: dayContentJson(day: 29));
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId),
          client: client, now: DateTime(2027, 3, 8, 20));
      await settle(tester);
      await scrollTo(tester, find.text('Is tomorrow Eid?'));
      expect(find.text('Is tomorrow Eid?'), findsOneWidget);
    });

    testWidgets('…and not in the morning', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = ramadanTodayJson(day: 29, content: dayContentJson(day: 29));
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId),
          client: client, now: DateTime(2027, 3, 8, 9));
      await settle(tester);
      await scrollTo(tester, find.text('Days of the month'));
      expect(find.text('Is tomorrow Eid?'), findsNothing);
    });

    testWidgets("the fasting step: practised today is a tick, the week's count only grows", (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      final toggle = find.byKey(const ValueKey('fasting_practised_today'));
      await scrollTo(tester, toggle);
      expect(find.text("سارة's step: Morning hours"), findsOneWidget);
      await tester.tap(toggle);
      await settle(tester);
      expect(client.bodies.last, {'day': null, 'done': true});
      expect(find.text('3 times this week'), findsOneWidget);
      // The step's cap reached: care, not a score.
      expect(find.text("🌿 That's enough for this week — let tomorrow be a rest day."), findsOneWidget);
      expectNoMissLanguage(tester);
    });

    testWidgets('the moon settings: a day earlier', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      await tester.tap(find.byIcon(Icons.nightlight_round_outlined));
      await settle(tester);
      expect(find.text('Your moon sighting'), findsWidgets);
      await tester.tap(find.byKey(const ValueKey('ramadan_shift_-1')));
      await settle(tester);
      expect(client.bodies.last['start_shift_days'], -1);
      await tester.tap(find.byKey(const ValueKey('ramadan_days_29')));
      await settle(tester);
      expect(client.bodies.last['month_days'], 29);
      await tester.tap(find.byKey(const ValueKey('ramadan_days_auto')));
      await settle(tester);
      expect(client.bodies.last['reset'], isTrue);
    });

    testWidgets('every day of the month is reachable from the strip', (tester) async {
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: FakeProgramsClient());
      await settle(tester);
      final day5 = find.byKey(const ValueKey('ramadan_day_5'));
      await scrollTo(tester, day5);
      await tester.tap(day5);
      await settle(tester);
      expect(find.byType(RamadanDayScreen), findsOneWidget);
    });
  });

  group('any day', () {
    testWidgets('a day not reached yet is a preview — no ticks', (tester) async {
      await pumpPrograms(tester, const RamadanDayScreen(childId: kChildId, day: 5), client: FakeProgramsClient());
      await settle(tester);
      expect(find.text('Day 5'), findsWidgets);
      await scrollTo(tester, find.text("This day hasn't come yet — you can tick it on the day."));
      expect(find.byKey(const ValueKey('ramadan_mark_challenge_done')), findsNothing);
    });

    testWidgets('a past day shows what was ticked, and can still be ticked', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const RamadanDayScreen(childId: kChildId, day: 2), client: client);
      await settle(tester);
      final chip = find.byKey(const ValueKey('ramadan_mark_challenge_done'));
      await scrollTo(tester, chip);
      expect(tester.widget<FilterChip>(chip).selected, isTrue);
      final wird = find.byKey(const ValueKey('ramadan_mark_wird_done'));
      await tester.tap(wird);
      await settle(tester);
      expect(client.bodies.last, {'mark': 'wird_done', 'day': 2, 'done': true, 'choice_index': null});
      expectNoMissLanguage(tester);
    });
  });

  group('around the month', () {
    testWidgets('before: the countdown, how to get ready, the fasting step', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = ramadanTodayJson(state: 'upcoming', fasting: fastingSummaryJson(step: null));
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('12 days until Ramadan'), findsOneWidget);
      expect(find.textContaining('Expected to start on'), findsOneWidget);
      expect(find.text('Before Ramadan begins'), findsOneWidget);
      expect(find.text('Pick a fixed time for the challenge.'), findsOneWidget);
      await scrollTo(tester, find.text("سارة's step isn't chosen yet."));
      expect(find.text('Choose their step'), findsOneWidget);
      // No practice outside the month.
      expect(find.byKey(const ValueKey('fasting_practised_today')), findsNothing);
    });

    testWidgets('Eid: the day, and the family card up front', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = ramadanTodayJson(state: 'eid', recap: true);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('Eid day'), findsOneWidget);
      await scrollTo(tester, find.text("Open «Our Family's Ramadan»"));
      await tester.tap(find.text("Open «Our Family's Ramadan»"));
      await settle(tester);
      expect(find.byType(RamadanRecapScreen), findsOneWidget);
    });

    testWidgets('after: the bridge week in its fallback words, the habits, the next program', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = ramadanTodayJson(state: 'after', recap: true);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('After Ramadan: keep going together'), findsOneWidget);
      await scrollTo(tester, find.text('Week 4: Beyond the bridge'));
      expect(find.text('Keep the two habits, and choose a path for each child.'), findsOneWidget);
      await scrollTo(tester, find.text('The charity box'));
      await scrollTo(tester, find.text('The Prayer Journey'));
    });

    testWidgets('off season: a short goodbye, no settings', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = ramadanTodayJson(state: 'off_season', noFasting: true);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('This Ramadan season is over. See you next Ramadan, God willing.'), findsOneWidget);
      expect(find.byIcon(Icons.nightlight_round_outlined), findsNothing);
    });

    testWidgets('prenatal-1: the family challenge only, no fasting block', (tester) async {
      final client = FakeProgramsClient()..ramadanToday = ramadanTodayJson(noFasting: true);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client);
      await settle(tester);
      await scrollTo(tester, find.text('Days of the month'));
      expect(find.text('The fasting ladder'), findsNothing);
    });
  });

  group('the fasting ladder', () {
    testWidgets('safety first: the urgent signs and what to do come before any step', (tester) async {
      await pumpPrograms(tester, const FastingLadderScreen(childId: kChildId),
          client: FakeProgramsClient(), phone: const Size(400, 3000));
      await settle(tester);
      final urgent = find.text('Urgent signs');
      final action = find.text('Call an ambulance at once; nothing by mouth until fully awake.');
      final firstStep = find.text('Morning hours').first;
      expect(urgent, findsOneWidget);
      expect(action, findsOneWidget);
      expect(find.text('What to do straight away'), findsOneWidget);
      expect(find.text('When to break the fast straight away'), findsOneWidget);
      expect(tester.getTopLeft(urgent).dy, lessThan(tester.getTopLeft(firstStep).dy));
      expect(tester.getTopLeft(action).dy, lessThan(tester.getTopLeft(firstStep).dy));
    });

    testWidgets('a step above the age is shown but cannot be chosen; a step up is celebrated', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const FastingLadderScreen(childId: kChildId),
          client: client, phone: const Size(400, 3000));
      await settle(tester);
      final asr = find.byKey(const ValueKey('fasting_step_until_asr'));
      expect(find.descendant(of: asr, matching: find.text('Not for their age yet')), findsOneWidget);
      expect(find.descendant(of: asr, matching: find.text('Make this the step')), findsNothing);
      final dhuhr = find.byKey(const ValueKey('fasting_step_until_dhuhr'));
      await tester.tap(find.descendant(of: dhuhr, matching: find.text('Make this the step')));
      await settle(tester);
      expect(client.bodies.last['step_key'], 'until_dhuhr');
      expect(find.text('Moved up a step — well done!'), findsOneWidget);
    });

    testWidgets('reached puberty is a quiet toggle at the bottom', (tester) async {
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const FastingLadderScreen(childId: kChildId), client: client);
      await settle(tester);
      final toggle = find.byKey(const ValueKey('fasting_puberty'));
      await scrollTo(tester, toggle);
      expect(find.text('سارة has reached puberty'), findsOneWidget);
      await tester.tap(toggle);
      await settle(tester);
      expect(client.bodies.last['reached_puberty'], isTrue);
    });
  });

  group('«رمضان عائلتنا»', () {
    testWidgets('the shared image carries the card only — the fasting stays in the app', (tester) async {
      await pumpPrograms(tester, const RamadanRecapScreen(), client: FakeProgramsClient());
      await settle(tester);
      final shareCard = find.byType(RamadanRecapShareCard);
      expect(shareCard, findsOneWidget);
      expect(find.descendant(of: shareCard, matching: find.text("Our Family's Ramadan 1448")), findsOneWidget);
      expect(find.descendant(of: shareCard, matching: find.text('Family challenges: 12')), findsOneWidget);
      expect(find.descendant(of: shareCard, matching: find.text('May Allah accept from us and from you')), findsOneWidget);
      // family_only: on screen, outside the card.
      final familyOnly = find.text('Fasting steps our children climbed');
      await scrollTo(tester, familyOnly);
      expect(familyOnly, findsOneWidget);
      expect(find.descendant(of: shareCard, matching: familyOnly), findsNothing);
      expect(find.descendant(of: shareCard, matching: find.textContaining('asting')), findsNothing);
      expect(find.text('For your family only'), findsOneWidget);
    });

    testWidgets('the card renders nothing but what it is given', (tester) async {
      await pumpPrograms(
        tester,
        const Scaffold(
          body: FittedBox(
            child: RamadanRecapShareCard(
              card: RecapCardFixture.card,
            ),
          ),
        ),
        client: FakeProgramsClient(),
      );
      await settle(tester);
      final texts = tester
          .widgetList<Text>(find.descendant(of: find.byType(RamadanRecapShareCard), matching: find.byType(Text)))
          .map((t) => t.data)
          .whereType<String>()
          .toSet();
      expect(texts, containsAll(['H 1448', 'Line one: 3']));
      expect(texts.any((t) => t.contains('Omar') || t.contains('7')), isFalse);
    });

    testWidgets('before Eid: counters only, and when the card arrives', (tester) async {
      final client = FakeProgramsClient()..recap = recapJson(available: false);
      await pumpPrograms(tester, const RamadanRecapScreen(), client: client);
      await settle(tester);
      expect(find.byType(RamadanRecapShareCard), findsNothing);
      expect(find.byKey(const ValueKey('recap_share')), findsNothing);
      expect(find.textContaining('The card will be ready on Eid'), findsOneWidget);
      expect(find.text('Family challenges'), findsOneWidget);
      // A count, not "12 of 30".
      expect(find.text('12'), findsOneWidget);
      expect(find.textContaining('/30'), findsNothing);
    });
  });
}

/// A card with nothing personal in it — what the server builds.
abstract final class RecapCardFixture {
  static const card = RecapCard(headline: 'H 1448', lines: ['Line one: 3'], closing: 'C');
}
