/// «خطة أسبوع بتتعلّم عليها» (نور والقناديل phase 3, MOBILE_API §9.5.1).
///
/// A step is ticked with one tap: the tick shows before the server answers,
/// a snack bar offers «تراجع» (the DELETE), and a failed PUT puts the step
/// back. The ticks a plan already has come from its GET `marks`. On the new
/// plan's Monday the first open reveals the steps one after another — once,
/// and with no motion under reduced motion.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/clock.dart';
import 'package:almorabbi/features/child_memory/widgets/today_weekly_plan_card.dart';
import 'package:almorabbi/features/home/widgets/today_loop_cards.dart';
import 'package:almorabbi/features/lanterns/widgets/week_lantern_string.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/widgets/ui/paper_lantern.dart';

import 'lantern_fakes.dart';
import 'memory_fakes.dart';

const _ahmad =
    ActiveChildProfile(id: 12, name: 'أحمد', ageGroup: '7-9', avatarEmoji: '🧒');

Widget _today({bool reduceMotion = false}) => Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: reduceMotion),
        child: Scaffold(
          body: ListView(
            padding: const EdgeInsets.all(16),
            children: const [TodayLoopCards(profile: _ahmad)],
          ),
        ),
      ),
    );

const _step2 = 'أوقف الشاشات قبل النوم بساعة.';

/// The tappable row of a plan step.
Finder _row(String text) =>
    find.ancestor(of: find.text(text), matching: find.byType(InkWell)).first;

bool _ticked(WidgetTester tester, String text) => find
    .descendant(of: _row(text), matching: find.byIcon(Icons.check_rounded))
    .evaluate()
    .isNotEmpty;

Future<void> _expand(WidgetTester tester) async {
  await tester.tap(find.text('اعرض الخطة كاملة'));
  await settle(tester);
  await tester.scrollUntilVisible(find.text(_step2), 200,
      scrollable: find.byType(Scrollable).first);
}

DateTime get _thisMonday => mondayOf(DateTime.now());

void main() {
  testWidgets('the GET marks show as ticked; the card counts them', (
    tester,
  ) async {
    final server = FakeMemoryServer()
      ..plans[12] = (planJson(12)..['marks'] = ['a2', 'w1']);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    // Collapsed: only what was done, as a positive count (action + worship).
    expect(find.text('أتممتم خطوتين هذا الأسبوع'), findsOneWidget);
    await _expand(tester);
    expect(_ticked(tester, _step2), isTrue);
    expect(_ticked(tester, 'ثبّت موعد النوم في أيام الدراسة.'), isFalse);
    expect(_ticked(tester, 'اختاروا معًا عملًا خيريًا صغيرًا.'), isTrue);
  });

  testWidgets('an older server sends no marks: nothing ticked, no count', (
    tester,
  ) async {
    final server = FakeMemoryServer()..plans[12] = planJson(12);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    expect(find.textContaining('أتممتم'), findsNothing);
    await _expand(tester);
    expect(_ticked(tester, _step2), isFalse);
  });

  testWidgets('a tap ticks at once, then PUT; «تراجع» sends the DELETE', (
    tester,
  ) async {
    final gate = Completer<void>();
    final server = FakeMemoryServer()
      ..plans[12] = planJson(12)
      ..markGate = gate;
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    await _expand(tester);

    await tester.tap(find.text(_step2));
    await tester.pump();
    // Before the server answers.
    expect(_ticked(tester, _step2), isTrue);
    expect(find.text('تمّت الخطوة. أحسنتم!'), findsOneWidget);
    final week = dateWire(_thisMonday);
    expect(server.calls.last,
        'PUT /api/children/12/weekly-plan/marks $week a2');

    gate.complete();
    await settle(tester);
    expect(_ticked(tester, _step2), isTrue);
    expect(server.marks[12], ['a2']);
    expect(find.text('أتممتم خطوة واحدة هذا الأسبوع'), findsOneWidget);

    await tester.tap(find.text('تراجع'));
    await settle(tester);
    expect(server.calls.last,
        'DELETE /api/children/12/weekly-plan/marks $week a2');
    expect(_ticked(tester, _step2), isFalse);
    expect(server.marks[12], isEmpty);
    expect(find.textContaining('أتممتم'), findsNothing);
  });

  testWidgets('tapping a ticked step takes the tick back', (tester) async {
    final server = FakeMemoryServer()
      ..plans[12] = (planJson(12)..['marks'] = ['a2']);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    await _expand(tester);
    await tester.tap(find.text(_step2));
    await settle(tester);
    expect(server.calls.last, startsWith('DELETE '));
    expect(_ticked(tester, _step2), isFalse);
  });

  testWidgets('a PUT that fails puts the step back and says why', (
    tester,
  ) async {
    final gate = Completer<void>();
    final server = FakeMemoryServer()
      ..plans[12] = planJson(12)
      ..markError = const TgApiError(503, 'offline')
      ..markGate = gate;
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    await _expand(tester);
    await tester.tap(find.text(_step2));
    await tester.pump();
    expect(_ticked(tester, _step2), isTrue);
    gate.complete();
    await settle(tester);
    expect(_ticked(tester, _step2), isFalse);
    expect(find.textContaining('أتممتم'), findsNothing);
    // The failure is said, in place of the «done» line.
    expect(find.text('تمّت الخطوة. أحسنتم!'), findsNothing);
    expect(find.byType(SnackBar), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('a tick asks the lanterns again — the server lights them, '
      'never the client (worship lights none)', (tester) async {
    final server = FakeMemoryServer()
      ..plans[12] = planJson(12)
      ..familyWeek = familyWeekJson();
    await pumpMemoryApp(
      tester,
      Scaffold(
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: const [
            TodayLoopCards(profile: _ahmad),
            WeekLanternString(),
          ],
        ),
      ),
      server: server,
    );
    await settle(tester);
    int asks() => server.calls.where((c) => c.contains('/family/week')).length;
    final before = asks();
    await _expand(tester);

    // The worship act: ticked, asked again, and still no lantern — the
    // server never counts worship, and the client adds nothing of its own.
    await tester.scrollUntilVisible(
        find.text('اختاروا معًا عملًا خيريًا صغيرًا.'), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('اختاروا معًا عملًا خيريًا صغيرًا.'));
    await settle(tester, 10);
    expect(asks(), before + 1);
    expect(find.byType(PaperLantern), findsNothing);

    // An action: the server now has a plan_tick lantern, and it shows.
    server.familyWeek = familyWeekJson(
        acts: [act('plan_tick', 0, title: 'أوقف الشاشات قبل النوم بساعة.')]);
    await tester.scrollUntilVisible(find.text(_step2), -200,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text(_step2));
    await settle(tester, 30);
    expect(asks(), before + 2);
    expect(find.byType(PaperLantern, skipOffstage: false), findsOneWidget);
  });

  group('Monday reveal', () {
    Future<SharedPreferences> pumpOn(
      WidgetTester tester,
      DateTime now, {
      bool reduceMotion = false,
    }) async {
      final server = FakeMemoryServer()..plans[12] = planJson(12);
      final container = await pumpMemoryApp(
        tester,
        _today(reduceMotion: reduceMotion),
        server: server,
        overrides: [clockProvider.overrideWithValue(() => now)],
      );
      await settle(tester);
      return container.read(sharedPreferencesProvider.future);
    }

    testWidgets('the plan’s Monday opens the card and brings the steps in', (
      tester,
    ) async {
      final prefs = await pumpOn(tester, _thisMonday.add(const Duration(hours: 9)));
      // Opened on its own, rows still arriving one after another.
      expect(find.text('أخفِ التفاصيل'), findsOneWidget);
      expect(find.byType(Animate), findsWidgets);
      await tester.pump(const Duration(seconds: 2));
      expect(find.text(_step2), findsOneWidget);
      expect(prefs.getString(TodayWeeklyPlanCard.revealKey(12)),
          dateWire(_thisMonday));
    });

    testWidgets('once a week: the next open stays collapsed', (tester) async {
      final monday = _thisMonday.add(const Duration(hours: 9));
      final server = FakeMemoryServer()..plans[12] = planJson(12);
      final container = await pumpMemoryApp(tester, _today(),
          server: server,
          overrides: [clockProvider.overrideWithValue(() => monday)]);
      await settle(tester);
      await tester.pump(const Duration(seconds: 2));
      expect(find.text('أخفِ التفاصيل'), findsOneWidget);

      // «اليوم» opened again on the same phone, the same Monday.
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: _today(),
        ),
      ));
      await settle(tester);
      expect(find.text('اعرض الخطة كاملة'), findsOneWidget);
      expect(find.text(_step2), findsNothing);
    });

    testWidgets('any other day: collapsed as always', (tester) async {
      await pumpOn(tester, _thisMonday.add(const Duration(days: 2, hours: 9)));
      expect(find.text('اعرض الخطة كاملة'), findsOneWidget);
      expect(find.text(_step2), findsNothing);
    });

    testWidgets('reduced motion: revealed, but with no motion', (tester) async {
      await pumpOn(tester, _thisMonday.add(const Duration(hours: 9)),
          reduceMotion: true);
      expect(find.text('أخفِ التفاصيل'), findsOneWidget);
      expect(find.text(_step2), findsOneWidget);
      expect(find.byType(Animate), findsNothing);
    });
  });
}
