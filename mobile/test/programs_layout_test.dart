// Every programs screen survives dark mode, 200% text, both directions and a
// small phone: scrolled top to bottom, nothing overflows or throws.
//
// "The screens I opened look fine" is not "no screen breaks" — so this walks
// all of them, in both languages, rather than the ones someone remembered.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/screens/add_child_screen.dart';
import 'package:almorabbi/features/programs/screens/fasting_ladder_screen.dart';
import 'package:almorabbi/features/programs/screens/milestones_screen.dart';
import 'package:almorabbi/features/programs/screens/prayer_journey_screen.dart';
import 'package:almorabbi/features/programs/screens/programs_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_day_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_recap_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_screen.dart';
import 'package:almorabbi/features/programs/widgets/child_prayer_card.dart';
import 'package:almorabbi/features/programs/widgets/programs_home_card.dart';

import 'programs_support.dart';

typedef _Case = ({String name, Widget Function() screen, void Function(FakeProgramsClient c)? setup});

final List<_Case> _cases = [
  (name: 'programs list', screen: () => const ProgramsScreen(), setup: (c) => c.programs = programsJson(enrolled: true, stage: 2, pending: 3, needsProfile: ['birth_month'])),
  (name: 'home card', screen: () => const Scaffold(body: SingleChildScrollView(child: ProgramsHomeCard())), setup: (c) => c.programs = programsJson(enrolled: true, stage: 2, pending: 1)),
  (name: 'ramadan · today', screen: () => const RamadanScreen(childId: kChildId), setup: null),
  (name: 'ramadan · day 28', screen: () => const RamadanScreen(childId: kChildId), setup: (c) => c.ramadanToday = ramadanTodayJson(day: 28, content: dayContentJson(day: 28, tracks: ['challenge_done', 'night_joined', 'family_word'], word: true, oddNight: true), marks: {'challenge_done': true, 'night_joined': false})),
  (name: 'ramadan · upcoming', screen: () => const RamadanScreen(childId: kChildId), setup: (c) => c.ramadanToday = ramadanTodayJson(state: 'upcoming')),
  (name: 'ramadan · eid', screen: () => const RamadanScreen(childId: kChildId), setup: (c) => c.ramadanToday = ramadanTodayJson(state: 'eid', recap: true)),
  (name: 'ramadan · after', screen: () => const RamadanScreen(childId: kChildId), setup: (c) => c.ramadanToday = ramadanTodayJson(state: 'after', recap: true)),
  (name: 'ramadan · past day', screen: () => const RamadanDayScreen(childId: kChildId, day: 2), setup: null),
  (name: 'fasting ladder', screen: () => const FastingLadderScreen(childId: kChildId), setup: null),
  (name: 'recap', screen: () => const RamadanRecapScreen(), setup: null),
  (name: 'recap · before eid', screen: () => const RamadanRecapScreen(), setup: (c) => c.recap = recapJson(available: false)),
  (name: 'prayer · enrolled', screen: () => const PrayerJourneyScreen(childId: kChildId), setup: (c) => c.journey = journeyJson(pending: 2, advance: true)),
  (name: 'prayer · not started', screen: () => const PrayerJourneyScreen(childId: kChildId), setup: (c) => c.journey = journeyJson(enrolled: false, eligible: 'ownership', allowed: ['ownership', 'journey'])),
  (name: 'prayer · graduation', screen: () => const PrayerJourneyScreen(childId: kChildId), setup: (c) => c.journey = journeyJson(stage: 6, graduate: true)),
  (name: 'milestones', screen: () => const MilestonesScreen(childId: kChildId), setup: (c) => c.milestones = milestonesJson(needs: ['birth_month', 'gender'])),
  (name: 'milestone detail', screen: () => const MilestoneDetailScreen(childId: kChildId, milestoneKey: 'first_fasting'), setup: (c) => c.milestoneByKey['first_fasting'] = milestoneJson(key: 'first_fasting', medical: true)),
  (name: 'child prayer card', screen: () => const Scaffold(body: SingleChildScrollView(child: ChildPrayerCard())), setup: null),
  (name: 'add child + birth month', screen: () => const AddChildScreen(), setup: null),
];

/// Drags the main scrollable to its end, checking for an exception at every step.
Future<void> sweep(WidgetTester tester, String label) async {
  expect(tester.takeException(), isNull, reason: '$label: on first frame');
  final scrollables = find.byType(Scrollable);
  if (scrollables.evaluate().isEmpty) return;
  for (var i = 0; i < 40; i++) {
    final state = tester.state<ScrollableState>(scrollables.first);
    final position = state.position;
    if (position.pixels >= position.maxScrollExtent) break;
    await tester.drag(scrollables.first, const Offset(0, -300));
    await tester.pump(const Duration(milliseconds: 60));
    expect(tester.takeException(), isNull, reason: '$label: after scrolling to ${position.pixels}');
  }
}

void main() {
  const configs = [
    (locale: Locale('en'), dark: true, scale: 2.0, phone: Size(360, 740)),
    (locale: Locale('ar'), dark: false, scale: 2.0, phone: Size(320, 640)),
    (locale: Locale('ar'), dark: true, scale: 1.0, phone: Size(360, 740)),
  ];

  for (final config in configs) {
    final tag = '${config.locale.languageCode}, ${config.dark ? 'dark' : 'light'}, ${config.scale}x';
    for (final c in _cases) {
      testWidgets('${c.name} — $tag', (tester) async {
        final client = FakeProgramsClient();
        c.setup?.call(client);
        await pumpPrograms(
          tester,
          c.screen(),
          client: client,
          locale: config.locale,
          dark: config.dark,
          textScale: config.scale,
          phone: config.phone,
          overrides: [childPrayerTokenProvider.overrideWithValue(() async => 'child-tok')],
        );
        await settle(tester);
        await sweep(tester, '${c.name} ($tag)');
        // The direction follows the language.
        final dir = Directionality.of(tester.element(find.byType(Scaffold).first));
        expect(dir, config.locale.languageCode == 'ar' ? TextDirection.rtl : TextDirection.ltr);
      });
    }
  }
}
