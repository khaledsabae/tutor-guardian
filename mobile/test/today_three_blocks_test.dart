/// «اليوم» — three blocks for the active child, then a divider, then the rest.
///
/// The screen was cut down because «مش عارف أبدأ منين» was the first thing
/// parents wrote. These tests pin what that cut promised: the order of the
/// three stops, that each one always ends in an action (whatever the server
/// says), that the content banks decide what block ③ offers, and that the
/// layout survives English, dark mode and 200% text — with no Arabic left on
/// the English screen.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:almorabbi/features/program/widgets/active_child_chip.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/home/widgets/home_stats_row.dart';
import 'package:almorabbi/features/home/widgets/today_section.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/parent_day/child_day_card.dart';
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
    String childName = 'سارة',
    Map<String, dynamic>? day,
    Map<String, dynamic>? progress,
    Locale locale = const Locale('ar'),
    bool dark = false,
    double textScale = 1.0,
    Size phone = const Size(360, 800),
  }) async {
    tester.view.physicalSize = phone * 3.0;
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);

    final fake = _FakeTgClient()
      ..day = day
      ..progress = progress;
    SharedPreferences.setMockInitialValues({
      if (ageGroup != null) ...{
        OnboardingStorage.keyActiveChildId: 1,
        OnboardingStorage.keyActiveChildName: childName,
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

  for (final locale in const [Locale('ar'), Locale('en')]) {
    testWidgets('Today actions have localized button semantics (${locale.languageCode})', (t) async {
      final semantics = t.ensureSemantics();
      try {
        await pumpHome(t, locale: locale);
        final l10n = AppLocalizations.of(t.element(find.byType(HomeScreen)));
        final ask = find.bySemanticsLabel(l10n.todayAskCta);
        expect(ask, findsOneWidget);
        final data = t.getSemantics(ask).getSemanticsData();
        expect(data.flagsCollection.isButton, isTrue);
        expect(data.hasAction(SemanticsAction.tap), isTrue);
        final child = find.byType(ActiveChildChip);
        final childData = t.getSemantics(child).getSemanticsData();
        expect(childData.label, locale.languageCode == 'ar'
            ? 'اختيار الطفل: سارة' : 'Choose child: سارة');
        expect(childData.flagsCollection.isButton, isTrue);
        expect(t.getSize(child).height, greaterThanOrEqualTo(48));
        expect(t.getSize(child).width, greaterThanOrEqualTo(48));
      } finally {
        semantics.dispose();
      }
    });
  }

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

  testWidgets('English, dark: no Arabic script anywhere on the screen',
      (tester) async {
    // E2E run 37203122941 (English, dark) showed Arabic on «اليوم»: the switch
    // hint and the games card were literals in home_screen.dart. The hint
    // moved to the ARB files and the card went with the three-block cut; this
    // pins the whole screen so the next literal is caught here, not on a
    // device. The child gets a Latin name — a parent's Arabic name is no leak.
    await pumpHome(tester,
        locale: const Locale('en'), dark: true, childName: 'Sara');
    expect(find.text('Tap to switch or add another child'), findsOneWidget);

    // The list builds lazily: walk it to the end, reading every text on the way.
    final seen = <String>{};
    final position =
        tester.state<ScrollableState>(find.byType(Scrollable).first).position;
    for (var step = 0;; step++) {
      for (final rich in tester.widgetList<RichText>(
          find.byType(RichText, skipOffstage: false))) {
        seen.add(rich.text.toPlainText());
      }
      if (position.pixels >= position.maxScrollExtent) break;
      expect(step, lessThan(100), reason: 'the list never ended');
      position.jumpTo(math.min(position.pixels + 300, position.maxScrollExtent));
      await tester.pump();
    }
    // The walk really got below the divider, to the last cards.
    expect(seen, containsAll(['More for today', 'Educational Games']));

    // The four the E2E run caught, by name — and then any other.
    expect(
        seen.intersection({
          'اضغط للتبديل أو إضافة طفل آخر',
          'الألعاب والمسابقات التعليمية',
          'ألعاب تفاعلية ومسابقات قيم وتربية لطفلك',
          'العب الآن',
        }),
        isEmpty);
    final arabic = RegExp(
        r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufefc]');
    expect(seen.where(arabic.hasMatch).toList(), isEmpty);
  });

  Map<String, dynamic> dayWith({
    required int childId,
    int screenSeconds = 0,
    Map<String, dynamic>? mission,
  }) =>
      {
        'child_id': childId,
        'child_name': 'سارة',
        'screen': {'counted_seconds': screenSeconds, 'budget_seconds': 1800},
        'listening': {'counted_seconds': 0, 'budget_seconds': 3600},
        'mission': mission,
      };

  testWidgets('minutes on the screen are not a mission: the hand-over stays',
      (tester) async {
    // Item 10: twenty minutes of screen and no mission used to show only the
    // minutes, hiding the one thing the block exists to offer.
    await pumpHome(tester, ageGroup: '7-9',
        day: dayWith(childId: 1, screenSeconds: 1200));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.scrollUntilVisible(find.text('افتح مهمة اليوم'), 200,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('افتح مهمة اليوم'), findsOneWidget);
    expect(find.textContaining('20 دقيقة شاشة من 30'), findsOneWidget);
  });

  testWidgets('a young band with minutes keeps its summary and no mission CTA',
      (tester) async {
    await pumpHome(tester, ageGroup: '2-3',
        day: dayWith(childId: 1, screenSeconds: 600));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.scrollUntilVisible(find.textContaining('10 دقيقة شاشة'), 200,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('افتح مهمة اليوم'), findsNothing);
  });

  testWidgets('switching child mid-load never shows the older child\'s day',
      (tester) async {
    // Item 16: the slower, older answer used to overwrite the newer child's.
    final fake = _FakeTgClient()..pendingDays = {};
    final container = ProviderContainer(overrides: [
      tgClientProvider.overrideWithValue(fake),
    ]);
    addTearDown(container.dispose);
    container.read(activeChildIdProvider.notifier).state = 1;
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(body: ChildDayCard(whenEmpty: Text('EMPTY'))),
      ),
    ));
    await tester.pump();
    expect(fake.pendingDays!.keys, [1]);

    container.read(activeChildIdProvider.notifier).state = 2;
    await tester.pump();
    await tester.pump();
    expect(fake.pendingDays!.keys, [1, 2]);

    fake.pendingDays![2]!.complete(dayWith(
        childId: 2, mission: {'status': 'assigned', 'title_ar': 'مهمة الثاني'}));
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('مهمة الثاني'), findsOneWidget);

    fake.pendingDays![1]!.complete(dayWith(
        childId: 1, mission: {'status': 'assigned', 'title_ar': 'مهمة الأول'}));
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('مهمة الثاني'), findsOneWidget);
    expect(find.textContaining('مهمة الأول'), findsNothing);
  });

  testWidgets('the ask entry stays compact at 200% English on a 320dp phone',
      (tester) async {
    // Item 12: a fixed-width CTA beside the body left the body a sliver, and
    // it wrapped one word per line into a card taller than the screen.
    await pumpHome(tester,
        locale: const Locale('en'), textScale: 2.0, phone: const Size(320, 640));
    final cta = find.text('Ask your question');
    await tester.scrollUntilVisible(cta, 200,
        scrollable: find.byType(Scrollable).first);
    expect(tester.takeException(), isNull);
    final card = find.ancestor(of: cta, matching: find.byType(InkWell)).first;
    expect(tester.getSize(card).height, lessThan(320));
    // And the body reads as text, not as a column of single words.
    final body = find.textContaining('Tell Al-Murabbi');
    expect(tester.getSize(body).width, greaterThan(160));
  });

  testWidgets('habit_streak_3 fires without the stats row being scrolled to',
      (tester) async {
    // Item 14: the event was fired from HomeStatsRow, which since the stats
    // moved below the divider is built only when a parent scrolls down.
    await pumpHome(tester,
        phone: const Size(360, 640),
        progress: {
          'child_id': 1,
          'lessons': [],
          'streak_days': 3,
          'daily_login_streak': 3,
          'last_completed_at': null,
        });
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(HomeStatsRow), findsNothing); // never built
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool('tg.analytics.once.habit_streak_3'), isTrue);
  });
}

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? day;
  Map<String, dynamic>? progress;

  /// When set, fetchChildDay answers each child only when the test says so.
  Map<int, Completer<Map<String, dynamic>>>? pendingDays;

  @override
  Future<Map<String, dynamic>> getChildProgress(int childId,
          {String? pathId}) async =>
      progress ?? {'child_id': childId, 'lessons': []};

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
    final pending = pendingDays;
    if (pending != null) {
      return (pending[childId] = Completer<Map<String, dynamic>>()).future;
    }
    final d = day;
    if (d == null) throw const TgApiError(503, 'offline');
    return d;
  }
}
