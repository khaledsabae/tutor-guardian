/// Invariants for the first-run guided tour.
///
/// The load-bearing one is the first group: the tour is a full-screen veil
/// that swallows taps, so if it ever ran under `flutter test` it would break
/// every widget test that touches the nav bar — starting with
/// `program_widget_test.dart`.
///
/// Version 3 («نور والقناديل», phase 2) is one mark on Today's ① card, and
/// tapping it opens the lesson; «تخطّي» stays (e2e/flows/common/skip_tour.yaml
/// taps it). It runs once, and only for parents who never finished version 2.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/app_routes.dart' show Screens;
import 'package:almorabbi/features/home/widgets/today_focus_card.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/tour/tour_controller.dart';
import 'package:almorabbi/features/tour/tour_overlay.dart';
import 'package:almorabbi/features/tour/tour_step.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart' show tgClientProvider;

void main() {
  group('test guard', () {
    test('the tour is suppressed under FLUTTER_TEST', () {
      expect(kTourEnabled, isFalse,
          reason: 'a live veil would eat taps in every widget test');
    });
  });

  group('OnboardingStorage.tourVersion', () {
    late OnboardingStorage storage;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      storage = OnboardingStorage(await SharedPreferences.getInstance());
    });

    test('starts at 0 and records the version it was shown at', () async {
      expect(storage.tourVersion, 0);
      await storage.markTourSeen(kTourVersion);
      expect(storage.tourVersion, kTourVersion);
    });

    test('rewinds to 0 so settings can replay it', () async {
      await storage.markTourSeen(kTourVersion);
      await storage.markTourSeen(0);
      expect(storage.tourVersion, 0);
      expect(storage.tourVersion < kTourVersion, isTrue);
    });

    test('is an int, not a bool — a later version can re-trigger', () async {
      await storage.markTourSeen(1);
      expect(storage.tourVersion < 2, isTrue,
          reason: 'bumping kTourVersion must re-arm the tour');
    });
  });

  group('who sees version 3', () {
    test('it is version 3', () => expect(kTourVersion, 3));

    test('never toured, or rewound by the replay row: yes', () {
      expect(tourIsDue(0), isTrue);
    });

    test('finished version 1 (before the rewrite): yes', () {
      expect(tourIsDue(1), isTrue);
    });

    test('finished version 2: no — it already ended on ①', () {
      expect(tourIsDue(2), isFalse);
    });

    test('finished version 3: no — once is enough', () {
      expect(tourIsDue(kTourVersion), isFalse);
    });

    test('the shell asks tourIsDue, and waits for Today', () {
      final source =
          File('lib/features/shell/root_scaffold.dart').readAsStringSync();
      expect(source, contains('tourIsDue(ref.read(tourVersionProvider))'));
      expect(source, contains('if (_index != RootTab.today) return;'));
      expect(source, isNot(contains('>= kTourVersion')),
          reason: 'a bare version compare would re-show it to v2 parents');
    });
  });

  group('steps', () {
    final focusKey = GlobalKey();
    var opened = 0;
    final steps = buildTourSteps(focusKey: focusKey, onOpen: () => opened++);

    // Both shipped locales: a key can exist in Arabic and be missing in
    // English, and the tour is the first thing a new user sees.
    final locales = {
      'ar': lookupAppLocalizations(const Locale('ar')),
      'en': lookupAppLocalizations(const Locale('en')),
    };

    test('one mark, on the ① card, that opens it', () {
      expect(steps, hasLength(1));
      expect(steps.single.key, same(focusKey));
      steps.single.onTargetTap!();
      expect(opened, 1);
    });

    test('its copy resolves in every locale', () {
      for (final entry in locales.entries) {
        final step = steps.single;
        expect(step.title!(entry.value), isNotEmpty, reason: entry.key);
        expect(step.caption(entry.value), isNotEmpty, reason: entry.key);
        expect(step.actionLabel!(entry.value), isNotEmpty, reason: entry.key);
      }
      final ar = locales['ar']!;
      expect(ar.tourStartHereTitle, 'ابدأ من هنا');
      expect(ar.tourStartHereBody, 'درس قصير لعمر طفلك');
    });

    test('the action labels resolve in every locale', () {
      for (final l in locales.values) {
        expect(l.tourNext, isNotEmpty);
        expect(l.tourSkip, isNotEmpty);
        expect(l.tourDone, isNotEmpty);
        expect(l.tourReplay, isNotEmpty);
      }
    });

    test('version 2\'s five captions are gone from both locales', () {
      for (final file in ['lib/l10n/app_ar.arb', 'lib/l10n/app_en.arb']) {
        final arb = File(file).readAsStringSync();
        for (final key in ['tourTodayTitle', 'tourLearnBody', 'tourFocusBody']) {
          expect(arb, isNot(contains('"$key"')), reason: '$file: $key');
        }
      }
    });
  });

  group('the version-3 mark on ①', () {
    late SharedPreferences prefs;
    late List<String?> pushed;
    late GlobalKey focusKey;
    late ValueNotifier<double> above;

    /// Today in miniature: something above ① that can grow (the gift line,
    /// the child banner), then the real ① card on a first lesson, and a
    /// button standing in for the shell's post-frame start.
    Future<void> pumpToday(WidgetTester tester) async {
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
      pushed = [];
      focusKey = GlobalKey();
      above = ValueNotifier(40);
      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(_FirstLessonClient()),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      await tester.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          navigatorObservers: [_PushLog(pushed)],
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: child!,
          ),
          home: Consumer(
            builder: (context, ref, _) => Scaffold(
              body: ListView(
                children: [
                  ValueListenableBuilder<double>(
                    valueListenable: above,
                    builder: (_, h, _) => SizedBox(height: h),
                  ),
                  TodayFocusCard(
                    key: focusKey,
                    bundle: null,
                    ageGroup: '7-9',
                    onStartFirstPath: () => pushed.add('browse'),
                  ),
                  TextButton(
                    onPressed: () => showTour(
                      context,
                      ref,
                      buildTourSteps(
                        focusKey: focusKey,
                        onOpen: () =>
                            ref.read(todayFocusOpenProvider.notifier).state++,
                      ),
                    ),
                    child: const Text('start-tour'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('ابدأ هذا الدرس'), findsOneWidget,
          reason: 'the card offers the first lesson');
      await tester.tap(find.text('start-tour'));
      await tester.pumpAndSettle();
    }

    /// Unmounts everything a pushed lesson screen may have started.
    Future<void> finish(WidgetTester tester) async {
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 2));
    }

    int stored() => prefs.getInt(OnboardingStorage.keyTourVersion) ?? 0;

    testWidgets('shows the copy and «تخطّي», and no meter for one step',
        (tester) async {
      await pumpToday(tester);
      expect(find.text('ابدأ من هنا'), findsOneWidget);
      expect(find.text('درس قصير لعمر طفلك'), findsOneWidget);
      expect(find.text('تخطّي'), findsOneWidget);
      expect(find.text('ابدأ'), findsOneWidget);
      expect(find.byType(FractionallySizedBox), findsNothing,
          reason: 'a meter that starts full measures nothing');
      await tester.tap(find.text('تخطّي'));
      await tester.pumpAndSettle();
      await finish(tester);
    });

    testWidgets('tapping the card under the mark opens the lesson',
        (tester) async {
      await pumpToday(tester);
      await tester.tapAt(tester.getCenter(find.byKey(focusKey)));
      await tester.pumpAndSettle();
      expect(pushed, [Screens.lesson]);
      expect(find.text('ابدأ من هنا'), findsNothing, reason: 'the tour ended');
      expect(stored(), kTourVersion);
      expect(tourIsDue(stored()), isFalse, reason: 'shown once');
      await finish(tester);
    });

    testWidgets('its «ابدأ» button opens the lesson too', (tester) async {
      await pumpToday(tester);
      await tester.tap(find.text('ابدأ'));
      await tester.pumpAndSettle();
      expect(pushed, [Screens.lesson]);
      expect(tourIsDue(stored()), isFalse);
      await finish(tester);
    });

    testWidgets('«تخطّي» ends it without opening anything', (tester) async {
      await pumpToday(tester);
      await tester.tap(find.text('تخطّي'));
      await tester.pumpAndSettle();
      expect(pushed, isEmpty);
      expect(find.text('ابدأ من هنا'), findsNothing);
      expect(tourIsDue(stored()), isFalse, reason: 'skipping counts as seen');
      await finish(tester);
    });

    testWidgets('the mark follows ① when Today fills in above it',
        (tester) async {
      await pumpToday(tester);
      final before = tester.getCenter(find.byKey(focusKey));
      above.value = 160; // e.g. the gift line arrives after the tour is up
      await tester.pumpAndSettle();
      final after = tester.getCenter(find.byKey(focusKey));
      expect(after.dy, greaterThan(before.dy + 100));
      // A hole left at the old spot would hand this tap to the veil, which
      // only closes the tour.
      await tester.tapAt(after);
      await tester.pumpAndSettle();
      expect(pushed, [Screens.lesson]);
      await finish(tester);
    });
  });

  group('TourController', () {
    test('walks every step, then reports the end exactly once', () {
      final c = TourController();
      expect(c.state.active, isFalse);

      c.start(5);
      expect(c.state.active, isTrue);
      expect(c.state.index, 0);
      expect(c.state.isLast, isFalse);

      for (var i = 0; i < 4; i++) {
        expect(c.next(), isFalse, reason: 'step $i is not the end');
        expect(c.state.index, i + 1);
      }

      expect(c.state.isLast, isTrue);
      expect(c.next(), isTrue, reason: 'the fifth "next" completes the tour');
      expect(c.state.active, isFalse);
      // Idempotent: a stray tap after the last one must not re-report.
      expect(c.next(), isFalse);
    });

    test('stop() ends the tour wherever it is', () {
      final c = TourController()..start(5);
      c.next();
      c.stop();
      expect(c.state.active, isFalse);
      expect(c.next(), isFalse);
    });

    test('start() ignores an empty step list', () {
      final c = TourController()..start(0);
      expect(c.state.active, isFalse);
    });
  });
}

/// The ① card's first-run state: no progress, one path, a first lesson.
class _FirstLessonClient extends TgClient {
  @override
  Future<Map<String, dynamic>> getChildProgress(int childId,
          {String? pathId}) async =>
      {'child_id': childId, 'lessons': []};

  @override
  Future<Map<String, dynamic>> getPathsList(
          {String? ageGroup, String? domain}) async =>
      {
        'paths': [
          {
            'id': 'p1',
            'title': 'مسار الصلاة',
            'age_group': '7-9',
            'domain': 'worship',
            'lesson_ids': ['l1', 'l2'],
          },
        ],
        'count': 1,
      };

  @override
  Future<Map<String, dynamic>> getNextLesson(String ageGroup,
          {int? childId}) async =>
      {
        'lesson_id': 'l1',
        'path_id': 'p1',
        'path_title': 'مسار الصلاة',
        'title': 'أسماء الصلاة',
        'order': 1,
        'resumed': false,
      };
}

class _PushLog extends NavigatorObserver {
  _PushLog(this.names);

  final List<String?> names;

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    // The home route is not a push anyone made.
    if (previousRoute != null) names.add(route.settings.name);
  }
}
