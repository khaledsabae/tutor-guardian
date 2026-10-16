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
import 'package:almorabbi/features/companion/data/companion_store.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/features/home/widgets/home_stats_row.dart';
import 'package:almorabbi/features/family_road/screens/family_road_screen.dart';
import 'package:almorabbi/features/family_road/widgets/horizon_strip.dart';
import 'package:almorabbi/features/home/widgets/sky_band.dart';
import 'package:almorabbi/features/home/widgets/today_focus_card.dart';
import 'package:almorabbi/features/home/widgets/today_road.dart';
import 'package:almorabbi/main.dart' show appConfigProvider;
import 'package:almorabbi/widgets/ui/brand_glyph.dart';
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

import 'lantern_fakes.dart';
import 'programs_support.dart' show programsJson;

void main() {
  tearDown(() => AppPalette.current = AppPalette.light);

  Future<List<int>> pumpHome(
    WidgetTester tester, {
    String? ageGroup = '7-9',
    String childName = 'سارة',
    Map<String, dynamic>? day,
    Map<String, dynamic>? progress,
    Map<String, dynamic>? week,
    Locale locale = const Locale('ar'),
    bool dark = false,
    double textScale = 1.0,
    Size phone = const Size(360, 800),
    List<String> stops = const [],
    bool noorOn = true,
    Map<String, dynamic>? programs,
    Map<String, dynamic>? appConfig,
  }) async {
    tester.view.physicalSize = phone * 3.0;
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);

    final fake = _FakeTgClient()
      ..day = day
      ..progress = progress
      ..week = week
      ..programs = programs;
    SharedPreferences.setMockInitialValues({
      if (ageGroup != null) ...{
        OnboardingStorage.keyActiveChildId: 1,
        OnboardingStorage.keyActiveChildName: childName,
        OnboardingStorage.keyActiveChildAgeGroup: ageGroup,
      },
      OnboardingStorage.keyOnboardingCompleted: true,
    });
    final prefs = await SharedPreferences.getInstance();
    for (final stop in stops) {
      await CompanionStore(prefs).markStop(stop);
    }
    final container = ProviderContainer(
      overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
        if (!noorOn || appConfig != null)
          appConfigProvider.overrideWith(
            (_) async => {
              if (!noorOn) 'noor_header_enabled': false,
              ...?appConfig,
            },
          ),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);
    if (ageGroup != null) {
      container.read(activeChildIdProvider.notifier).state = 1;
    }

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
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(textScale)),
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
    testWidgets(
      'Today actions have localized button semantics (${locale.languageCode})',
      (t) async {
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
          expect(
            childData.label,
            locale.languageCode == 'ar'
                ? 'الطفل الحالي: سارة، اضغط للتبديل'
                : 'Current child: سارة, tap to switch',
          );
          expect(childData.flagsCollection.isButton, isTrue);
          expect(t.getSize(child).height, greaterThanOrEqualTo(48));
          expect(t.getSize(child).width, greaterThanOrEqualTo(48));
        } finally {
          semantics.dispose();
        }
      },
    );
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
    await tester.scrollUntilVisible(
      divider,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(topOf(tester, mission), lessThan(topOf(tester, divider)));
  });

  testWidgets('«درب اليوم»: the stops stand on one road under the sky', (
    tester,
  ) async {
    await pumpHome(tester);
    expect(find.byType(SkyBand), findsOneWidget);
    expect(find.byType(TodayRoad), findsOneWidget);
    // The stations carry the stop glyphs: the headers drop their own.
    for (final h in tester.widgetList<TodaySectionHeader>(
      find.byType(TodaySectionHeader),
    )) {
      expect(
        find.descendant(
          of: find.byWidget(h),
          matching: find.byType(BrandGlyph),
        ),
        findsNothing,
      );
    }
    // Nothing reached yet: Noor waits on ①, beside its header.
    final road = find.byType(TodayRoad);
    final noor = find.descendant(of: road, matching: find.byType(NoorPresence));
    expect(noor, findsOneWidget);
    final stepTop = topOf(tester, find.text('خطوة اليوم مع سارة'));
    expect((topOf(tester, noor) - stepTop).abs(), lessThan(24));
    expect(
      find.descendant(
        of: find.byType(TodayRoad),
        matching: find.byIcon(Icons.check_rounded),
      ),
      findsNothing,
    );
  });

  testWidgets('a lesson done today lights ① and Noor moves on to ②', (
    tester,
  ) async {
    await pumpHome(tester, stops: ['step:1', 'mission:2']);
    expect(
      find.descendant(
        of: find.byType(TodayRoad),
        matching: find.byIcon(Icons.check_rounded),
      ),
      findsOneWidget,
    );
    final noor = find.descendant(
      of: find.byType(TodayRoad),
      matching: find.byType(NoorPresence),
    );
    final askTop = topOf(tester, find.text('اسأل المربّي'));
    expect((topOf(tester, noor) - askTop).abs(), lessThan(24));
  });

  // «نور والقناديل» phase 5: the month itself hangs the lanterns in the sky
  // over Noor; before it, at Eid, and on a server without the programs the
  // sky is the plain sky of the hour.
  for (final dark in [false, true]) {
    testWidgets('in Ramadan the sky over Noor takes the lantern skin '
        '(${dark ? 'dark' : 'light'})', (tester) async {
      bool skin() => tester.widget<SkyBand>(find.byType(SkyBand)).ramadan;
      await pumpHome(tester, dark: dark, programs: programsJson());
      expect(skin(), isTrue);
      for (final state in ['upcoming', 'eid', 'after', 'off_season']) {
        await tester.pumpWidget(const SizedBox());
        await pumpHome(
          tester,
          dark: dark,
          programs: programsJson(state: state, day: null),
        );
        expect(skin(), isFalse, reason: state);
        // Eid has its own moment; close it so the next pump starts clean.
        final close = find.byKey(const ValueKey('eid_moment_close'));
        if (close.evaluate().isNotEmpty) {
          await tester.tap(close);
          await tester.pump(const Duration(milliseconds: 400));
        }
      }
      await tester.pumpWidget(const SizedBox());
      await pumpHome(tester, dark: dark);
      expect(skin(), isFalse, reason: 'no programs on this server');
    });
  }

  testWidgets('the first nights of Ramadan: Noor says «هلّ هلال رمضان»', (
    tester,
  ) async {
    await pumpHome(tester, programs: programsJson(day: 1));
    expect(find.textContaining('هلّ هلال رمضان'), findsOneWidget);
    expect(find.text('برنامج رمضان'), findsOneWidget);
    // Mid-month the server says day 15: no crescent line.
    await tester.pumpWidget(const SizedBox());
    await pumpHome(tester, programs: programsJson(day: 15));
    expect(find.textContaining('هلّ هلال رمضان'), findsNothing);
  });

  testWidgets('Eid: «عيدكم مبارك» opens over Today once', (tester) async {
    await pumpHome(tester, programs: programsJson(state: 'eid', day: null));
    expect(find.text('عيدكم مبارك'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('eid_moment_close')));
    // Today breathes (Noor), so it never settles: wait out the dialog.
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('عيدكم مبارك'), findsNothing);
    expect(find.text('خطوة اليوم مع سارة'), findsOneWidget);
  });

  group('«على الأفق» (عالم الأسرة)', () {
    Map<String, dynamic> upcoming() => programsJson(
      state: 'upcoming',
      day: null,
      daysUntil: 116,
      due: 0,
    );

    testWidgets('the strip names the nearest dated gate on the hills', (
      tester,
    ) async {
      await pumpHome(tester, programs: upcoming());
      final strip = find.byType(HorizonStrip);
      expect(strip, findsOneWidget);
      expect(
        find.descendant(of: find.byType(SkyBand), matching: strip),
        findsOneWidget,
      );
      expect(find.textContaining('رمضان بعد 116 يومًا'), findsOneWidget);
      expect(find.textContaining('على الأفق'), findsOneWidget);
    });

    testWidgets('its tap target is the strip itself, not the sky', (
      tester,
    ) async {
      // Run 38754954265: the strip's node spanned the whole sky band, so a
      // tap on its centre (what Maestro and TalkBack do) landed on Noor's
      // bubble and opened nothing.
      final semantics = tester.ensureSemantics();
      try {
        await pumpHome(tester, programs: upcoming());
        final node = tester.getSemantics(
          find.bySemanticsLabel(RegExp('على الأفق')),
        );
        final strip = tester.getRect(find.byType(HorizonStrip));
        final rect = node.transform == null
            ? node.rect
            : MatrixUtils.transformRect(node.transform!, node.rect);
        expect(rect.height, lessThanOrEqualTo(strip.height + 1));
      } finally {
        semantics.dispose();
      }
    });

    testWidgets('a tap opens «درب {الاسم}»', (tester) async {
      await pumpHome(tester, programs: upcoming());
      await tester.tap(find.byType(HorizonStrip));
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(FamilyRoadScreen), findsOneWidget);
      expect(find.text('درب سارة'), findsOneWidget);
    });

    testWidgets('the server can hide it', (tester) async {
      await pumpHome(
        tester,
        programs: upcoming(),
        appConfig: {'horizon_strip_enabled': false},
      );
      expect(find.byType(HorizonStrip), findsNothing);
      expect(find.byType(SkyBand), findsOneWidget);
    });

    testWidgets('no dated gate (an older server), no strip', (tester) async {
      await pumpHome(tester);
      expect(find.byType(HorizonStrip), findsNothing);
    });

    testWidgets('① keeps its place under it — 360dp', (tester) async {
      await pumpHome(tester, programs: upcoming(), phone: const Size(360, 800));
      expect(find.byType(HorizonStrip), findsOneWidget);
      // The strip lies on the hills, inside the sky (the band grows by less
      // than the strip — sky_band_test), and ① follows the sky.
      final sky = tester.getRect(find.byType(SkyBand));
      final strip = tester.getRect(find.byType(HorizonStrip));
      expect(strip.bottom, lessThanOrEqualTo(sky.bottom));
      final step = tester.getTopLeft(find.byType(TodayFocusCard)).dy;
      expect(step, greaterThan(sky.bottom));
      expect(step, lessThan(800 - 200));
    });

    for (final size in const [Size(411, 914), Size(360, 800)]) {
      testWidgets('200% text: ①\'s button stays on the first screen, the '
          'strip waits under the road — ${size.width.toInt()}dp', (
        tester,
      ) async {
        // CI run 38754954265: on the hills the strip wrapped to two lines at
        // 200% and pushed ①'s button below a 411×914 phone's fold.
        await pumpHome(
          tester,
          programs: upcoming(),
          textScale: 2.0,
          phone: size,
        );
        expect(tester.takeException(), isNull);
        expect(
          find.descendant(
            of: find.byType(SkyBand),
            matching: find.byType(HorizonStrip),
          ),
          findsNothing,
        );
        // Nothing new stands above ①: the band keeps its own height (the
        // test font is wider than Cairo, so the fold itself is pinned on the
        // device by fresh/01's ① assertion, which this protects).
        final sky = tester.getRect(find.byType(SkyBand));
        final step = tester.getRect(find.byType(TodayFocusCard));
        expect(step.top, greaterThan(sky.bottom));
        await tester.scrollUntilVisible(
          find.byType(HorizonStrip),
          300,
          scrollable: find.byType(Scrollable).first,
        );
        expect(
          tester.getRect(find.byType(HorizonStrip)).top,
          greaterThan(tester.getRect(find.byType(TodayFocusCard)).bottom),
        );
      });
    }

    testWidgets('in a season the sky takes its touch', (tester) async {
      await pumpHome(
        tester,
        programs: {
          ...upcoming(),
          'hijri_season': {'month': 'rajab', 'day': 5, 'hijri_year': 1448},
        },
      );
      final painter =
          tester
                  .widget<CustomPaint>(
                    find.descendant(
                      of: find.byType(SkyBand),
                      matching: find.byType(CustomPaint),
                    ).first,
                  )
                  .painter!
              as SkyPainter;
      expect(painter.season, isNotNull);
    });
  });

  testWidgets('kill switch off: no sky and no road, the plain blocks stay', (
    tester,
  ) async {
    await pumpHome(tester, noorOn: false);
    expect(find.byType(SkyBand), findsNothing);
    expect(find.byType(TodayRoad), findsNothing);
    expect(find.byType(TodaySectionHeader), findsNWidgets(3));
    expect(find.text('خطوة اليوم مع سارة'), findsOneWidget);
    expect(find.text('اضغط للتبديل أو إضافة طفل آخر'), findsOneWidget);
  });

  testWidgets('the ask entry is there even when the tip cannot load', (
    tester,
  ) async {
    final tabs = await pumpHome(tester);
    // The fake has no coach tip — the tip card hides itself — and the block
    // must still offer a way to ask.
    await tester.tap(find.text('اكتب سؤالك'));
    expect(tabs, [RootTab.assistant]);
  });

  testWidgets('a mission band with no mission yet is invited to open one', (
    tester,
  ) async {
    await pumpHome(tester, ageGroup: '7-9');
    expect(find.text('افتح مهمة اليوم'), findsOneWidget);
  });

  testWidgets('a mission the child already opened shows the day instead', (
    tester,
  ) async {
    await pumpHome(
      tester,
      ageGroup: '7-9',
      day: {
        'child_id': 1,
        'child_name': 'سارة',
        'screen': {'counted_seconds': 0, 'budget_seconds': 1800},
        'listening': {'counted_seconds': 0, 'budget_seconds': 3600},
        'mission': {'status': 'assigned', 'title_ar': 'صيّاد الأخضر'},
      },
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.textContaining('صيّاد الأخضر'), findsOneWidget);
    expect(find.text('افتح مهمة اليوم'), findsNothing);
  });

  testWidgets(
    'a band with no mission bank gets the day tracker, not a mission',
    (tester) async {
      await pumpHome(tester, ageGroup: '2-3');
      expect(find.text('يوم سارة'), findsOneWidget);
      expect(find.text('سجّل الآن'), findsOneWidget);
      expect(find.text('افتح مهمة اليوم'), findsNothing);
    },
  );

  testWidgets('no child yet: the blocks speak generically and ask for one', (
    tester,
  ) async {
    await pumpHome(tester, ageGroup: null);
    expect(find.text('خطوة اليوم مع طفلك'), findsOneWidget);
    expect(find.text('مهمة الطفل اليوم'), findsOneWidget);
    expect(find.text('أضف طفلك'), findsOneWidget);
  });

  testWidgets('English, dark, 200% text: lays out without overflow', (
    tester,
  ) async {
    await pumpHome(
      tester,
      locale: const Locale('en'),
      dark: true,
      textScale: 2.0,
      // The week's lanterns are drawn at this scale too (phase 3).
      week: familyWeekJson(
        acts: [
          act('lesson', 0, title: 'Sleep and focus'),
          act('question', 1),
          act('mission', 2, title: 'Green hunter'),
        ],
      ),
    );
    expect(tester.takeException(), isNull);
    expect(find.text("Today's step with سارة"), findsOneWidget);
    // Further down at this scale; scroll to each and check it built cleanly.
    for (final text in [
      'Ask Al-Murabbi',
      'Ask your question',
      "سارة's mission today",
      "Open today's mission",
      "Your week's lanterns",
      'More for today',
      // Below the divider: the stats chips overflowed here at 200% before
      // they moved off a fixed-aspect grid. «أسابيع مضيئة» took the login
      // streak's place (phase 3).
      'Lit weeks',
      'Educational Games',
    ]) {
      await tester.scrollUntilVisible(
        find.text(text),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pump();
      expect(tester.takeException(), isNull, reason: text);
      expect(find.text(text), findsOneWidget);
    }
  });

  testWidgets('English, dark: no Arabic script anywhere on the screen', (
    tester,
  ) async {
    // E2E run 37203122941 (English, dark) showed Arabic on «اليوم»: the switch
    // hint and the games card were literals in home_screen.dart. The hint
    // moved to the ARB files and the card went with the three-block cut; this
    // pins the whole screen so the next literal is caught here, not on a
    // device. The child gets a Latin name — a parent's Arabic name is no leak.
    await pumpHome(
      tester,
      locale: const Locale('en'),
      dark: true,
      childName: 'Sara',
    );
    // Under the sky the child banner gives way to Noor and the app bar chip
    // (its hint is pinned by the kill-switch test below).
    expect(find.text('Tap to switch or add another child'), findsNothing);

    // The list builds lazily: walk it to the end, reading every text on the way.
    final seen = <String>{};
    final position = tester
        .state<ScrollableState>(find.byType(Scrollable).first)
        .position;
    for (var step = 0; ; step++) {
      for (final rich in tester.widgetList<RichText>(
        find.byType(RichText, skipOffstage: false),
      )) {
        seen.add(rich.text.toPlainText());
      }
      if (position.pixels >= position.maxScrollExtent) break;
      expect(step, lessThan(100), reason: 'the list never ended');
      position.jumpTo(
        math.min(position.pixels + 300, position.maxScrollExtent),
      );
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
      isEmpty,
    );
    final arabic = RegExp(
      r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufefc]',
    );
    expect(seen.where(arabic.hasMatch).toList(), isEmpty);
  });

  Map<String, dynamic> dayWith({
    required int childId,
    int screenSeconds = 0,
    Map<String, dynamic>? mission,
  }) => {
    'child_id': childId,
    'child_name': 'سارة',
    'screen': {'counted_seconds': screenSeconds, 'budget_seconds': 1800},
    'listening': {'counted_seconds': 0, 'budget_seconds': 3600},
    'mission': mission,
  };

  testWidgets('minutes on the screen are not a mission: the hand-over stays', (
    tester,
  ) async {
    // Item 10: twenty minutes of screen and no mission used to show only the
    // minutes, hiding the one thing the block exists to offer.
    await pumpHome(
      tester,
      ageGroup: '7-9',
      day: dayWith(childId: 1, screenSeconds: 1200),
    );
    await tester.pump(const Duration(milliseconds: 100));
    await tester.scrollUntilVisible(
      find.text('افتح مهمة اليوم'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('افتح مهمة اليوم'), findsOneWidget);
    expect(find.textContaining('20 دقيقة شاشة من 30'), findsOneWidget);
  });

  testWidgets(
    'a young band with minutes keeps its summary and no mission CTA',
    (tester) async {
      await pumpHome(
        tester,
        ageGroup: '2-3',
        day: dayWith(childId: 1, screenSeconds: 600),
      );
      await tester.pump(const Duration(milliseconds: 100));
      await tester.scrollUntilVisible(
        find.textContaining('10 دقيقة شاشة'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('افتح مهمة اليوم'), findsNothing);
    },
  );

  testWidgets('switching child mid-load never shows the older child\'s day', (
    tester,
  ) async {
    // Item 16: the slower, older answer used to overwrite the newer child's.
    final fake = _FakeTgClient()..pendingDays = {};
    final container = ProviderContainer(
      overrides: [tgClientProvider.overrideWithValue(fake)],
    );
    addTearDown(container.dispose);
    container.read(activeChildIdProvider.notifier).state = 1;
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const Scaffold(body: ChildDayCard(whenEmpty: Text('EMPTY'))),
        ),
      ),
    );
    await tester.pump();
    expect(fake.pendingDays!.keys, [1]);

    container.read(activeChildIdProvider.notifier).state = 2;
    await tester.pump();
    await tester.pump();
    expect(fake.pendingDays!.keys, [1, 2]);

    fake.pendingDays![2]!.complete(
      dayWith(
        childId: 2,
        mission: {'status': 'assigned', 'title_ar': 'مهمة الثاني'},
      ),
    );
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('مهمة الثاني'), findsOneWidget);

    fake.pendingDays![1]!.complete(
      dayWith(
        childId: 1,
        mission: {'status': 'assigned', 'title_ar': 'مهمة الأول'},
      ),
    );
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('مهمة الثاني'), findsOneWidget);
    expect(find.textContaining('مهمة الأول'), findsNothing);
  });

  testWidgets('the ask entry stays compact at 200% English on a 320dp phone', (
    tester,
  ) async {
    // Item 12: a fixed-width CTA beside the body left the body a sliver, and
    // it wrapped one word per line into a card taller than the screen.
    await pumpHome(
      tester,
      locale: const Locale('en'),
      textScale: 2.0,
      phone: const Size(320, 640),
    );
    final cta = find.text('Ask your question');
    await tester.scrollUntilVisible(
      cta,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(tester.takeException(), isNull);
    final card = find.ancestor(of: cta, matching: find.byType(InkWell)).first;
    expect(tester.getSize(card).height, lessThan(320));
    // And the body reads as text, not as a column of single words.
    final body = find.textContaining('Tell Al-Murabbi');
    expect(tester.getSize(body).width, greaterThan(160));
  });

  testWidgets('habit_streak_3 fires without the stats row being scrolled to', (
    tester,
  ) async {
    // Item 14: the event was fired from HomeStatsRow, which since the stats
    // moved below the divider is built only when a parent scrolls down.
    await pumpHome(
      tester,
      phone: const Size(360, 640),
      progress: {
        'child_id': 1,
        'lessons': [],
        'streak_days': 3,
        'daily_login_streak': 3,
        'last_completed_at': null,
      },
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(HomeStatsRow), findsNothing); // never built
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool('tg.analytics.once.habit_streak_3'), isTrue);
  });
}

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? day;
  Map<String, dynamic>? progress;

  /// `/api/programs`; null answers like a server without the programs.
  Map<String, dynamic>? programs;

  @override
  Future<Map<String, dynamic>> fetchPrograms() async =>
      programs ?? (throw const TgApiError(404, 'Not Found'));

  /// `/api/family/week`; null answers like a server without lanterns.
  Map<String, dynamic>? week;

  @override
  Future<Map<String, dynamic>> fetchFamilyWeek(
    int tzOffsetMinutes, {
    String? lang,
  }) async => week ?? (throw const TgApiError(404, 'Not Found'));

  /// When set, fetchChildDay answers each child only when the test says so.
  Map<int, Completer<Map<String, dynamic>>>? pendingDays;

  @override
  Future<Map<String, dynamic>> getChildProgress(
    int childId, {
    String? pathId,
  }) async => progress ?? {'child_id': childId, 'lessons': []};

  // Everything else the screen reads fails fast, the way an unreachable
  // server does — the blocks must still render and still end in an action.
  @override
  Future<Map<String, dynamic>> getPathsList({
    String? ageGroup,
    String? domain,
  }) async => throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getNextLesson(
    String ageGroup, {
    int? childId,
  }) async => throw const TgApiError(503, 'offline');

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
