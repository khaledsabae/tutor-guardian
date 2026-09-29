// UX-3 habits (UX_UI_ROADMAP §3.2–3.3): the 7-day strip, the streak with its
// weekly shield, and the capped milestone set.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/widgets/habit_week_strip.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

Widget _host(Widget child) => MaterialApp(
      locale: const Locale('en'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: Center(child: child)),
    );

void main() {
  group('streak', () {
    test('parses, and is zero from an older server', () {
      final s = HabitStreak.fromJson(
          {'days': 4, 'today_active': true, 'shield_used_this_week': true});
      expect([s.days, s.todayActive, s.shieldUsedThisWeek], [4, true, true]);
      expect(HabitStreak.fromJson(null).days, 0);
      expect(HabitDay.fromJson({'child_id': 1, 'date': 'd'}).streak.days, 0);
    });

    test('first effort today adds one day, once', () {
      const s = HabitStreak(days: 2);
      final after = s.withEffortToday();
      expect([after.days, after.todayActive], [3, true]);
      expect(after.withEffortToday().days, 3);
    });

    test('milestones are 3, 7 and 30 and fire only when crossed', () {
      expect(streakMilestoneCrossed(2, 3), 3);
      expect(streakMilestoneCrossed(6, 7), 7);
      expect(streakMilestoneCrossed(29, 30), 30);
      expect(streakMilestoneCrossed(3, 4), isNull);
      expect(streakMilestoneCrossed(0, 1), isNull);
    });
  });

  group('week strip', () {
    final week = HabitWeek.fromSummaryJson({
      'strip_dates': ['1', '2', '3', '4', '5', '6', '7'],
      'strip': {
        'Fajr': ['completed', null, 'partially', 'missed', null, null, null],
      },
    });

    test('parses statuses and keeps nulls', () {
      expect(week.byHabit['Fajr']![0], HabitStatus.completed);
      expect(week.byHabit['Fajr']![1], isNull);
      expect(week.byHabit['Fajr']![3], HabitStatus.missed);
    });

    test('today overrides the last cell; unknown habits are empty', () {
      expect(week.cellsFor('Fajr', today: HabitStatus.completed).last,
          HabitStatus.completed);
      expect(week.cellsFor('Other'), List<HabitStatus?>.filled(7, null));
      expect(const HabitWeek().cellsFor('x').length, 7);
    });

    testWidgets('announces effort, not misses', (t) async {
      await t.pumpWidget(_host(HabitWeekStrip(
        cells: week.cellsFor('Fajr', today: HabitStatus.completed),
      )));
      expect(find.bySemanticsLabel('Last 7 days: 2 done, 1 partly'),
          findsOneWidget);
    });
  });

  group('four-week bars', () {
    final week = HabitWeek.fromSummaryJson({
      'rates': {
        'A': {'rate': 0.5, 'prev_rate': 0.5},
        'B': {'rate': 0.4, 'prev_rate': 0.1},
        'C': {'rate': 0.9, 'prev_rate': 1.2}, // clamped to 1
      },
    });

    test('sorted by improvement, most improved first', () {
      expect(week.rates.map((r) => r.habitName), ['B', 'A', 'C']);
      expect(week.rates.last.prevRate, 1.0);
    });

    testWidgets('render percent and direction; empty has a hint', (t) async {
      await t.pumpWidget(_host(SingleChildScrollView(
        child: HabitFourWeekBars(rates: week.rates),
      )));
      expect(find.text('40%'), findsOneWidget);
      expect(find.text('↑30'), findsOneWidget);
      expect(find.text('↓10'), findsOneWidget);

      await t.pumpWidget(_host(const HabitFourWeekBars(rates: [])));
      expect(find.textContaining('Not enough records'), findsOneWidget);
    });
  });

  group('streak badge', () {
    testWidgets('hidden without a streak', (t) async {
      await t.pumpWidget(_host(const HabitStreakBadge(streak: HabitStreak())));
      expect(find.textContaining('streak'), findsNothing);
    });

    testWidgets('shows days and the used shield', (t) async {
      await t.pumpWidget(_host(const HabitStreakBadge(
        streak: HabitStreak(days: 5, shieldUsedThisWeek: true),
      )));
      expect(find.text('5-day streak'), findsOneWidget);
      expect(find.byIcon(Icons.shield_rounded), findsOneWidget);
    });
  });
}
