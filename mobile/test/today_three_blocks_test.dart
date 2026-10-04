/// «اليوم» — three blocks for the active child, then a divider, then the rest.
///
/// The screen was cut down because «مش عارف أبدأ منين» was the first thing
/// parents wrote. These tests pin what that cut promised: the order of the
/// three stops, that each one always ends in an action (whatever the server
/// says), that the content banks decide what block ③ offers, and that the
/// layout survives English, dark mode and 200% text.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/home/widgets/today_section.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/shell/root_tab.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/screens/home_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/theme/app_theme.dart';

void main() {
  tearDown(() => AppPalette.current = AppPalette.light);

  Future<List<int>> pumpHome(
    WidgetTester tester, {
    String? ageGroup = '7-9',
    Map<String, dynamic>? day,
    Locale locale = const Locale('ar'),
    bool dark = false,
    double textScale = 1.0,
  }) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 3.0; // a 360×800 phone
    addTearDown(tester.view.reset);

    final fake = _FakeTgClient()..day = day;
    SharedPreferences.setMockInitialValues({
      if (ageGroup != null) ...{
        OnboardingStorage.keyActiveChildId: 1,
        OnboardingStorage.keyActiveChildName: 'سارة',
        OnboardingStorage.keyActiveChildAgeGroup: ageGroup,
      },
      OnboardingStorage.keyOnboardingCompleted: true,
    });
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(overrides: [
      tgClientProvider.overrideWithValue(fake),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ]);
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);
    if (ageGroup != null) container.read(activeChildIdProvider.notifier).state = 1;

    if (dark) AppPalette.current = AppPalette.dark;
    final tabs = <int>[];
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: locale,
          theme: dark ? AppTheme.dark() : AppTheme.light(),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: TextScaler.linear(textScale)),
            child: child!,
          ),
          home: HomeScreen(onGoToTab: tabs.add),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    return tabs;
  }

  double topOf(WidgetTester tester, Finder f) => tester.getTopLeft(f).dy;

  testWidgets('three blocks, in order, all above the divider', (tester) async {
    await pumpHome(tester);

    final step = find.text('خطوة اليوم مع سارة');
    final ask = find.text('اسأل المربّي');
    final mission = find.text('مهمة سارة اليوم');
    final divider = find.text('المزيد لك اليوم');
    for (final f in [step, ask, mission]) {
      expect(f, findsOneWidget);
    }
    expect(find.byType(TodaySectionHeader), findsNWidgets(3));
    expect(topOf(tester, step), lessThan(topOf(tester, ask)));
    expect(topOf(tester, ask), lessThan(topOf(tester, mission)));
    // The divider is below the fold on a phone — which is the point.
    await tester.scrollUntilVisible(divider, 300,
        scrollable: find.byType(Scrollable).first);
    expect(topOf(tester, mission), lessThan(topOf(tester, divider)));
    // The loop slot is reserved and empty until the weekly plan ships.
    expect(find.byType(TodayLoopSlot), findsOneWidget);
    expect(TodayLoopSlot.cards, isEmpty);
  });

  testWidgets('the ask entry is there even when the tip cannot load',
      (tester) async {
    final tabs = await pumpHome(tester);
    // The fake has no coach tip — the tip card hides itself — and the block
    // must still offer a way to ask.
    await tester.tap(find.text('اكتب سؤالك'));
    expect(tabs, [RootTab.assistant]);
  });

  testWidgets('a mission band with no mission yet is invited to open one',
      (tester) async {
    await pumpHome(tester, ageGroup: '7-9');
    expect(find.text('افتح مهمة اليوم'), findsOneWidget);
  });

  testWidgets('a mission the child already opened shows the day instead',
      (tester) async {
    await pumpHome(tester, ageGroup: '7-9', day: {
      'child_id': 1,
      'child_name': 'سارة',
      'screen': {'counted_seconds': 0, 'budget_seconds': 1800},
      'listening': {'counted_seconds': 0, 'budget_seconds': 3600},
      'mission': {'status': 'assigned', 'title_ar': 'صيّاد الأخضر'},
    });
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.textContaining('صيّاد الأخضر'), findsOneWidget);
    expect(find.text('افتح مهمة اليوم'), findsNothing);
  });

  testWidgets('a band with no mission bank gets the day tracker, not a mission',
      (tester) async {
    await pumpHome(tester, ageGroup: '2-3');
    expect(find.text('يوم سارة'), findsOneWidget);
    expect(find.text('سجّل الآن'), findsOneWidget);
    expect(find.text('افتح مهمة اليوم'), findsNothing);
  });

  testWidgets('no child yet: the blocks speak generically and ask for one',
      (tester) async {
    await pumpHome(tester, ageGroup: null);
    expect(find.text('خطوة اليوم مع طفلك'), findsOneWidget);
    expect(find.text('مهمة الطفل اليوم'), findsOneWidget);
    expect(find.text('أضف طفلك'), findsOneWidget);
  });

  testWidgets('English, dark, 200% text: lays out without overflow',
      (tester) async {
    await pumpHome(tester,
        locale: const Locale('en'), dark: true, textScale: 2.0);
    expect(tester.takeException(), isNull);
    expect(find.text("Today's step with سارة"), findsOneWidget);
    // Further down at this scale; scroll to each and check it built cleanly.
    for (final text in [
      'Ask Al-Murabbi',
      'Ask your question',
      "سارة's mission today",
      "Open today's mission",
      'More for today',
      // Below the divider: the stats chips overflowed here at 200% before
      // they moved off a fixed-aspect grid.
      'Consecutive Days',
      'Educational Games',
    ]) {
      await tester.scrollUntilVisible(find.text(text), 300,
          scrollable: find.byType(Scrollable).first);
      await tester.pump();
      expect(tester.takeException(), isNull, reason: text);
      expect(find.text(text), findsOneWidget);
    }
  });
}

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? day;

  @override
  Future<Map<String, dynamic>> getChildProgress(int childId,
          {String? pathId}) async =>
      {'child_id': childId, 'lessons': []};

  // Everything else the screen reads fails fast, the way an unreachable
  // server does — the blocks must still render and still end in an action.
  @override
  Future<Map<String, dynamic>> getPathsList(
          {String? ageGroup, String? domain}) async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getNextLesson(String ageGroup,
          {int? childId}) async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getCoachTip(int childId) async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getCommunityStats() async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> fetchChildDay(int childId) async {
    final d = day;
    if (d == null) throw const TgApiError(503, 'offline');
    return d;
  }
}
