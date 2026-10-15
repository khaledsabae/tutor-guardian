// «رحلة الصلاة», phase 4 of NOOR_WAL_QANADIL_PLAN: moving up a stage is a
// quiet moment — «انتقل أحمد إلى «الوضوء». أعانكم الله وتقبّل منكم» — on a
// sheet of paper with Noor, no confetti. Moving back is silent. A child with
// the default name «طفلي» is not addressed by it: the family moves on. And
// the 4–6 band sees no stage numbers anywhere on the screen.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/programs/screens/prayer_journey_screen.dart';
import 'package:almorabbi/features/programs/widgets/prayer_stage_moment.dart';

import 'programs_support.dart';

const _moment = ValueKey('prayer_stage_moment');

Map<String, Object?> _child({String name = kChildName, String band = '7-9', String gender = 'female'}) => {
      'id': kChildId,
      'name': name,
      'age_group': band,
      'gender': gender,
      'avatar_emoji': '👧',
      'birth_month': '2019-03',
      'created_at': '',
      'updated_at': '',
    };

Future<void> _advance(WidgetTester tester) async {
  final button = find.byKey(const ValueKey('prayer_advance'));
  await scrollTo(tester, button);
  await tester.tap(button);
  await settle(tester);
}

/// Any «Stage N» / «المرحلة N» on screen, or a bare number badge.
List<String> _stageNumbersOnScreen(WidgetTester tester) => [
      for (final t in tester.widgetList<Text>(find.byType(Text)))
        if (RegExp(r'(Stage|المرحلة)\s*\d|^\d+$').hasMatch(t.data ?? t.textSpan?.toPlainText() ?? ''))
          t.data ?? t.textSpan!.toPlainText(),
    ];

void main() {
  group('moving up a stage', () {
    testWidgets('is a quiet moment that names the stage and the child', (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(advance: true);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.byKey(_moment), findsNothing);

      await _advance(tester);
      expect(client.bodies.last, {'stage': 2});
      expect(find.byKey(_moment), findsOneWidget);
      expect(find.text('$kChildName has moved on to “Stage title 2”.'), findsOneWidget);
      expect(find.text('May Allah help you, and accept it from you.'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('prayer_stage_moment_close')));
      await settle(tester);
      expect(find.byKey(_moment), findsNothing);
    });

    testWidgets('in Arabic, for a girl: «انتقلت سارة إلى …»', (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(advance: true);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId),
          client: client, locale: const Locale('ar'));
      await settle(tester);
      await _advance(tester);
      expect(find.text('انتقلت سارة إلى «Stage title 2».'), findsOneWidget);
      expect(find.text('أعانكم الله وتقبّل منكم'), findsOneWidget);
    });

    testWidgets('in Arabic, for a boy: «انتقل أحمد إلى …»', (tester) async {
      final client = FakeProgramsClient()
        ..journey = journeyJson(advance: true)
        ..children = [_child(name: 'أحمد', gender: 'male')];
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId),
          client: client, locale: const Locale('ar'));
      await settle(tester);
      await _advance(tester);
      expect(find.text('انتقل أحمد إلى «Stage title 2».'), findsOneWidget);
    });

    testWidgets('a child still named «طفلي»: the family moves on, nobody is called «طفلي»', (tester) async {
      final client = FakeProgramsClient()
        ..journey = journeyJson(advance: true)
        ..children = [_child(name: 'طفلي')];
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId),
          client: client, locale: const Locale('ar'));
      await settle(tester);
      await _advance(tester);
      expect(find.text('انتقلتم إلى «Stage title 2».'), findsOneWidget);
      expect(find.descendant(of: find.byKey(_moment), matching: find.textContaining('طفلي')), findsNothing);
    });

    testWidgets('no confetti, no celebration: one paper sheet with Noor', (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(advance: true);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      await _advance(tester);
      expect(find.byType(PrayerStageMoment), findsOneWidget);
      expect(find.textContaining('🎉'), findsNothing);
      expect(find.textContaining('🎊'), findsNothing);
    });
  });

  testWidgets('moving back is silent', (tester) async {
    final client = FakeProgramsClient()..journey = journeyJson(stage: 3);
    await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
    await settle(tester);
    final back = find.text('Go back to an earlier stage');
    await scrollTo(tester, back);
    await tester.tap(back);
    await settle(tester);
    await tester.tap(find.text('Stage 1 — Stage title 1'));
    await settle(tester);
    expect(client.bodies.last, {'stage': 1});
    expect(find.byKey(_moment), findsNothing);
  });

  testWidgets('a refused move up is no moment', (tester) async {
    final client = _RefusingClient()..journey = journeyJson(advance: true);
    await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
    await settle(tester);
    await _advance(tester);
    expect(find.byKey(_moment), findsNothing);
  });

  group('the 4–6 band sees no stage numbers', () {
    testWidgets('on the journey: the stage by name, moving on by name', (tester) async {
      final client = FakeProgramsClient()
        ..journey = journeyJson(advance: true)
        ..children = [_child(band: '4-6')];
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('Prayer is a meeting we love'), findsOneWidget);
      expect(find.text('Go to “Stage title 2”'), findsOneWidget);
      expect(find.textContaining('Move on to “Stage title 2”'), findsOneWidget);
      expect(_stageNumbersOnScreen(tester), isEmpty);

      // The moment names the stage, as it always does.
      await _advance(tester);
      expect(find.text('$kChildName has moved on to “Stage title 2”.'), findsOneWidget);
      expect(_stageNumbersOnScreen(tester), isEmpty);
      await tester.tap(find.byKey(const ValueKey('prayer_stage_moment_close')));
      await settle(tester);

      // The outline, opened: marks, not numbers.
      final outline = find.text('🗺️ The stages');
      await scrollTo(tester, outline);
      await tester.tap(outline);
      await settle(tester);
      await scrollTo(tester, find.text('Stage title 6'));
      expect(find.byKey(const ValueKey('prayer_stage_mark_1')), findsOneWidget);
      expect(_stageNumbersOnScreen(tester), isEmpty);
    });


    testWidgets('the preparation track, before it starts: the stages listed without numbers', (tester) async {
      final client = FakeProgramsClient()
        ..journey = journeyJson(enrolled: false, eligible: 'preparation', allowed: ['preparation'])
        ..children = [_child(band: '4-6')];
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      await scrollTo(tester, find.text('Stage title 6'));
      expect(find.byKey(const ValueKey('prayer_stage_mark_6')), findsOneWidget);
      expect(_stageNumbersOnScreen(tester), isEmpty);
    });

    testWidgets('a 7–9 child keeps the numbers', (tester) async {
      final client = FakeProgramsClient()..journey = journeyJson(advance: true);
      await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId), client: client);
      await settle(tester);
      expect(find.text('Stage 1 of 6'), findsOneWidget);
      expect(find.text('Go to stage 2'), findsOneWidget);
    });
  });

  for (final dark in [false, true]) {
    for (final locale in const [Locale('ar'), Locale('en')]) {
      testWidgets('200% text${dark ? ', dark' : ''} (${locale.languageCode}): the moment fits', (tester) async {
        final client = FakeProgramsClient()..journey = journeyJson(advance: true);
        await pumpPrograms(tester, const PrayerJourneyScreen(childId: kChildId),
            client: client, locale: locale, dark: dark, textScale: 2);
        await settle(tester);
        await _advance(tester);
        expect(find.byKey(_moment), findsOneWidget);
        await tester.scrollUntilVisible(
          find.byKey(const ValueKey('prayer_stage_moment_close')),
          100,
          scrollable: find.descendant(of: find.byKey(_moment), matching: find.byType(Scrollable)),
        );
        expect(tester.takeException(), isNull);
      });
    }
  }
}

class _RefusingClient extends FakeProgramsClient {
  @override
  Future<Map<String, dynamic>> setPrayerJourneyStage(int childId, int stage) async =>
      throw StateError('offline');
}
