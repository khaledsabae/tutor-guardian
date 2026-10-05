/// «خطة الأسبوع» on Today (MOBILE_API §9.5).
///
/// Collapsed to the focus by default (Today promises three stops); expanded:
/// three actions, the worship act, and the lesson, which opens the lesson
/// route. No lesson → no lesson row. The plan asks in the reader's language
/// with the family's offset; an older server or a failure hides it; a plan
/// whose week has ended is asked for again — once.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/core/app_routes.dart';
import 'package:almorabbi/features/home/widgets/today_loop_cards.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';

import 'memory_fakes.dart';

const _ahmad =
    ActiveChildProfile(id: 12, name: 'أحمد', ageGroup: '7-9', avatarEmoji: '🧒');

Widget _today() => Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [TodayLoopCards(profile: _ahmad)],
      ),
    );

class _Pushes extends NavigatorObserver {
  final names = <String?>[];
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) =>
      names.add(route.settings.name);
}

void main() {
  testWidgets('the focus first; the full week one tap away', (tester) async {
    final server = FakeMemoryServer()..plans[12] = planJson(12);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);

    expect(find.text('خطة أحمد هذا الأسبوع'), findsOneWidget);
    expect(find.text('نوم كافٍ لتركيز أفضل'), findsOneWidget);
    expect(find.text('بناءً على ما أخبرتنا به عن طفلك.'), findsOneWidget);
    // Collapsed: the actions are not on Today yet.
    expect(find.text('ثبّت موعد النوم في أيام الدراسة.'), findsNothing);

    await tester.tap(find.text('اعرض الخطة كاملة'));
    await settle(tester);
    for (final t in [
      'ثلاث خطوات صغيرة',
      'ثبّت موعد النوم في أيام الدراسة.',
      'أوقف الشاشات قبل النوم بساعة.',
      'خفّف السكريات في المساء.',
      'غيّرنا خطوة لم تنجح معكم من قبل.',
      'عبادة نعملها معًا',
      'اختاروا معًا عملًا خيريًا صغيرًا.',
      'درس الأسبوع',
      'النوم والتركيز',
    ]) {
      await tester.scrollUntilVisible(find.text(t), 200,
          scrollable: find.byType(Scrollable).first);
      expect(find.text(t), findsOneWidget, reason: t);
    }
    // The week as the server drew it: from its Monday, seven days.
    expect(find.textContaining('–'), findsOneWidget);
    expect(server.calls.where((c) => c.contains('weekly-plan')).single,
        'GET /api/children/12/weekly-plan lang=ar '
        'tz=${DateTime.now().timeZoneOffset.inMinutes}');
  });

  testWidgets('the lesson opens the lesson screen', (tester) async {
    final server = FakeMemoryServer()..plans[12] = planJson(12);
    final pushes = _Pushes();
    await pumpMemoryApp(tester, _today(), server: server, observers: [pushes]);
    await settle(tester);
    await tester.tap(find.text('اعرض الخطة كاملة'));
    await settle(tester);
    await tester.scrollUntilVisible(find.text('النوم والتركيز'), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('النوم والتركيز'));
    await tester.pump();
    expect(pushes.names.last, Screens.lesson);
    // Let the lesson screen's own entrance animations finish.
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('no lesson this week: no lesson row', (tester) async {
    final server = FakeMemoryServer()
      ..plans[12] = planJson(12, withLesson: false);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    await tester.tap(find.text('اعرض الخطة كاملة'));
    await settle(tester);
    expect(find.text('درس الأسبوع'), findsNothing);
    expect(find.text('عبادة نعملها معًا'), findsOneWidget);
  });

  testWidgets('needs no proof: an unproven session still gets its plan',
      (tester) async {
    final server = FakeMemoryServer()
      ..proven = false
      ..plans[12] = planJson(12);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    expect(find.text('نوم كافٍ لتركيز أفضل'), findsOneWidget);
    expect(server.starts, 0);
  });

  testWidgets('an older server, or no plan: hidden', (tester) async {
    final old = FakeMemoryServer()..memorySupported = false;
    await pumpMemoryApp(tester, _today(), server: old);
    await settle(tester);
    expect(find.text('خطة أحمد هذا الأسبوع'), findsNothing);

    final none = FakeMemoryServer(); // plans[12] missing → 404 for the child
    await pumpMemoryApp(tester, _today(), server: none);
    await settle(tester);
    expect(find.text('خطة أحمد هذا الأسبوع'), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 1));
  });

  testWidgets('a week that has ended is asked for again — once',
      (tester) async {
    final stale = planJson(12)
      ..['week'] = '2020-W02'
      ..['week_start'] = '2020-01-06';
    final server = FakeMemoryServer()..plans[12] = stale;
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester, 10);
    final asks =
        server.calls.where((c) => c.contains('weekly-plan')).length;
    expect(asks, 2, reason: 'the stale plan, then the new week — no loop');
  });

  testWidgets('English, dark, 200%: asks in English, lays out cleanly',
      (tester) async {
    final server = FakeMemoryServer()..plans[12] = planJson(12, lang: 'en');
    await pumpMemoryApp(tester, _today(),
        server: server,
        locale: const Locale('en'),
        dark: true,
        textScale: 2.0,
        phone: const Size(320, 640));
    await settle(tester);
    expect(server.calls.where((c) => c.contains('weekly-plan')).single,
        startsWith('GET /api/children/12/weekly-plan lang=en'));
    expect(find.text("أحمد's plan this week"), findsOneWidget);
    await tester.tap(find.text('Show the full plan'));
    await settle(tester);
    for (final t in [
      'Fix a bedtime on school days.',
      'Choose a small charity together.',
      'Sleep and focus',
      'Hide details',
    ]) {
      await tester.scrollUntilVisible(find.text(t), 200,
          scrollable: find.byType(Scrollable).first);
      await tester.pump();
      expect(tester.takeException(), isNull, reason: t);
    }
  });
}
