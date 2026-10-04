// The proactive milestones: a card list per child, a detail with its cards,
// red flags shown plainly, and a graceful path when the birth month (or the
// gender) is missing.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/screens/edit_child_screen.dart';
import 'package:almorabbi/features/programs/screens/milestones_screen.dart';
import 'package:almorabbi/features/programs/screens/prayer_journey_screen.dart';

import 'programs_support.dart';

void main() {
  testWidgets('due first, then upcoming; a medical card is marked', (tester) async {
    await pumpPrograms(tester, const MilestonesScreen(childId: kChildId), client: FakeProgramsClient());
    await settle(tester);
    expect(find.text("سارة's stages"), findsOneWidget);
    final due = find.text('Due now');
    final upcoming = find.text('Coming up');
    expect(due, findsOneWidget);
    expect(upcoming, findsOneWidget);
    expect(tester.getTopLeft(due).dy, lessThan(tester.getTopLeft(upcoming).dy));
    expect(find.text('First fasting attempts'), findsOneWidget);
    expect(find.text('🩺'), findsOneWidget);
  });

  testWidgets('no birth month: the cards still show by age, under a prompt to add it', (tester) async {
    final client = FakeProgramsClient()..milestones = milestonesJson(needs: ['birth_month'], library: true);
    await pumpPrograms(tester, const MilestonesScreen(childId: kChildId), client: client);
    await settle(tester);
    expect(find.byKey(const ValueKey('milestones_needs_birth_month')), findsOneWidget);
    expect(find.textContaining("Add سارة's birth month"), findsOneWidget);
    expect(find.text("For سارة's age"), findsOneWidget);
    expect(find.text('Starting to teach prayer'), findsOneWidget);
    // The prompt leads to the profile, where the month can be added.
    await tester.tap(find.text('Complete the profile'));
    await settle(tester);
    expect(find.byType(EditChildScreen), findsOneWidget);
  });

  testWidgets('a gender-specific card waits for the gender, with a prompt instead', (tester) async {
    final client = FakeProgramsClient()..milestones = milestonesJson(needs: ['gender']);
    await pumpPrograms(tester, const MilestonesScreen(childId: kChildId), client: client);
    await settle(tester);
    expect(find.byKey(const ValueKey('milestones_needs_gender')), findsOneWidget);
  });

  testWidgets('the detail: its cards, the red flags in plain sight, and where to go next', (tester) async {
    final client = FakeProgramsClient()..milestoneByKey['first_fasting'] = milestoneJson(key: 'first_fasting', medical: true);
    await pumpPrograms(tester, const MilestoneDetailScreen(childId: kChildId, milestoneKey: 'first_fasting'), client: client);
    await settle(tester);
    expect(find.text('Turning seven next month'), findsOneWidget);
    expect(find.text('Love before duty'), findsOneWidget);
    expect(find.text('One thing at a time'), findsOneWidget);
    final flags = find.byKey(const ValueKey('milestone_red_flags'));
    await scrollTo(tester, flags);
    expect(find.text('When to see a professional'), findsOneWidget);
    expect(find.text('Fainting or confusion → emergency services at once.'), findsOneWidget);
    expect(find.text('General information — not a substitute for a doctor.'), findsOneWidget);
    await scrollTo(tester, find.text('The Prayer Journey'));
    await tester.tap(find.text('The Prayer Journey'));
    await settle(tester);
    expect(find.byType(PrayerJourneyScreen), findsOneWidget);
  });

  testWidgets('a card that is not this child\'s opens the list instead', (tester) async {
    await pumpPrograms(tester, const MilestoneDetailScreen(childId: kChildId, milestoneKey: 'puberty_boys'),
        client: FakeProgramsClient());
    await settle(tester, 10);
    expect(find.byType(MilestoneDetailScreen), findsNothing);
    expect(find.byType(MilestonesScreen), findsOneWidget);
  });
}
