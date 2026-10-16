// «درب {الاسم}» (عالم الأسرة) on a phone: it opens on the horizon, Noor
// stands on «أنتم هنا», only what was done is lit below it, every gate
// goes somewhere, and it lays out in both languages, both themes and at
// 200% text on 360dp — still under reduced motion.
import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/analytics.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/features/family_road/screens/family_road_screen.dart';
import 'package:almorabbi/features/home/widgets/sky_band.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/theme/app_theme.dart';
import 'package:almorabbi/widgets/ui/paper_lantern.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'lantern_fakes.dart';

const _child = 12;

Map<String, dynamic> _programs({
  String state = 'upcoming',
  int? daysUntil = 116,
  int months = 80,
  String basis = 'birth_month',
  int due = 0,
  List<String> needs = const [],
  Map<String, dynamic>? season,
}) => {
  'date': '2026-10-15',
  'server_features': <String>[],
  'unavailable': <String>[],
  'ramadan': {
    'state': state,
    'season': {
      'hijri_year': 1448,
      'starts_on': '2027-02-08',
      'days': 30,
      'eid_on': '2027-03-10',
      'start_source': 'estimate',
      'days_confirmed': false,
      'shift_days': 0,
    },
    'day': null,
    'days_until_start': daysUntil,
    'after_week': null,
    'recap_available': false,
  },
  'hijri_season': season,
  'children': [
    {
      'child_id': _child,
      'age': {
        'basis': basis,
        'band': '4-6',
        'months': basis == 'birth_month' ? months : null,
        'years': basis == 'birth_month' ? months ~/ 12 : null,
      },
      'ramadan': {'variant_band': '4-6'},
      'prayer_journey': {
        'eligible_track': 'preparation',
        'enrolled': false,
        'track': null,
        'stage': null,
        'advance_suggested': false,
        'can_graduate': false,
        'pending_confirmations': 0,
      },
      'milestones': {'due': due, 'needs_profile': needs},
    },
  ],
};

Map<String, dynamic> _path(String id, String title, int lessons) => {
  'id': id,
  'title': title,
  'age_group': '4-6',
  'domain': 'islamic_parenting',
  'description': '',
  'lesson_ids': [for (var i = 0; i < lessons; i++) '$id-$i'],
  'estimated_days': 5,
};

class _Fake extends TgClient {
  _Fake() : super.forTesting(baseUrl: 'http://fake.invalid');

  bool english = false;
  Map<String, dynamic>? programs = _programs();
  Map<String, dynamic>? week;
  List<Map<String, dynamic>> lessons = const [];

  @override
  Future<Map<String, dynamic>> fetchPrograms() async =>
      programs ?? (throw const TgApiError(404, 'Not Found'));

  @override
  Future<Map<String, dynamic>> fetchMilestones(int childId) async => {
    'child_id': childId,
    'age': {'basis': 'birth_month', 'band': '4-6', 'months': 80, 'years': 6},
    'needs_profile': <String>[],
    'due': <Object>[],
    'upcoming': [
      {
        'key': 'school_entry',
        'state': 'upcoming',
        'due_on': '2027-09-01',
        'title': english ? 'Starting school' : 'دخول المدرسة',
        'cards': <Object>[],
      },
    ],
    'library': <Object>[],
    'past': <Object>[],
  };

  @override
  Future<Map<String, dynamic>> fetchFamilyWeek(
    int tzOffsetMinutes, {
    String? lang,
  }) async => week ?? (throw const TgApiError(404, 'Not Found'));

  @override
  Future<Map<String, dynamic>> getPathsList({
    String? ageGroup,
    String? domain,
  }) async => {
    'count': 3,
    'paths': [
      _path('anger', english ? 'Anger and stubbornness' : 'الغضب والعناد', 5),
      _path('honesty', english ? 'Honesty' : 'الصدق', 2),
      _path('sleep', english ? 'Sleep' : 'النوم', 4),
    ],
  };

  @override
  Future<Map<String, dynamic>> getChildProgress(
    int childId, {
    String? pathId,
  }) async => {'child_id': childId, 'lessons': lessons};
}

List<Map<String, dynamic>> _someProgress() => [
  for (var i = 0; i < 2; i++)
    {
      'lesson_id': 'honesty-$i',
      'path_id': 'honesty',
      'status': 'completed',
      'completed_at': '2026-10-0${i + 1}T10:00:00Z',
    },
  for (var i = 0; i < 2; i++)
    {
      'lesson_id': 'anger-$i',
      'path_id': 'anger',
      'status': 'completed',
      'completed_at': '2026-10-1${i + 1}T10:00:00Z',
    },
];

class _Routes extends NavigatorObserver {
  final pushed = <String?>[];
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) =>
      pushed.add(route.settings.name);
}

Future<_Routes> _pump(
  WidgetTester tester, {
  _Fake? fake,
  Locale locale = const Locale('ar'),
  bool dark = false,
  double textScale = 1,
  bool reduceMotion = false,
  Size phone = const Size(360, 640),
  String name = 'سارة',
}) async {
  tester.view.physicalSize = phone * 3.0;
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);
  addTearDown(() => AppPalette.current = AppPalette.light);
  SharedPreferences.setMockInitialValues({
    OnboardingStorage.keyActiveChildId: _child,
    OnboardingStorage.keyActiveChildName: name,
    OnboardingStorage.keyActiveChildAgeGroup: '4-6',
    OnboardingStorage.keyOnboardingCompleted: true,
  });
  final prefs = await SharedPreferences.getInstance();
  final client = fake ?? _Fake();
  final container = ProviderContainer(
    overrides: [
      tgClientProvider.overrideWithValue(client),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ],
  );
  addTearDown(container.dispose);
  await container.read(sharedPreferencesProvider.future);
  container.read(activeChildIdProvider.notifier).state = _child;
  if (dark) AppPalette.current = AppPalette.dark;
  final routes = _Routes();
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: locale,
        theme: dark ? AppTheme.dark() : AppTheme.light(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        navigatorObservers: [routes],
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(textScale),
            disableAnimations: reduceMotion,
          ),
          child: child!,
        ),
        home: FamilyRoadScreen(
          from: 'test',
          now: DateTime(2026, 10, 15, 21),
        ),
      ),
    ),
  );
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 300));
  }
  return routes;
}

double _top(WidgetTester t, Finder f) => t.getTopLeft(f).dy;

void main() {
  final logged = <(String, Map<String, Object>?)>[];
  setUp(() {
    logged.clear();
    Analytics.debugSink = (n, p) => logged.add((n, p));
  });
  tearDown(() => Analytics.debugSink = null);

  testWidgets('it opens on the horizon, farthest gate first, and logs it', (
    tester,
  ) async {
    await _pump(tester);
    expect(find.text('درب سارة'), findsOneWidget);
    expect(
      logged.where((e) => e.$1 == 'family_road_opened').single.$2,
      {'from': 'test'},
    );
    final horizon = find.byKey(const Key('road-horizon'));
    final here = find.byKey(const Key('road-here'));
    expect(horizon, findsOneWidget);
    // The first screen shows the horizon, not the past.
    expect(_top(tester, horizon), lessThan(640));
    // Next path (nearest), seven (4 months), Ramadan (116 days), school
    // (Sep 2027): drawn farthest first, down to «أنتم هنا».
    final order = [
      'gate-milestone',
      'gate-ramadan',
      'gate-age_seven',
      'gate-next_path',
    ];
    for (var i = 0; i < order.length - 1; i++) {
      expect(
        _top(tester, find.byKey(ValueKey(order[i]))),
        lessThan(_top(tester, find.byKey(ValueKey(order[i + 1])))),
        reason: '${order[i]} above ${order[i + 1]}',
      );
    }
    // The road comes down from the sky of the hour, with no words on it.
    expect(find.byType(SkyBand), findsOneWidget);
    expect(
      _top(tester, find.byKey(ValueKey(order.last))),
      lessThan(_top(tester, here)),
    );
    expect(find.textContaining('رمضان بعد 116 يومًا'), findsOneWidget);
    expect(find.textContaining('سنّ السابعة بعد 4 أشهر'), findsOneWidget);
    // Noor stands on «أنتم هنا».
    expect(
      find.descendant(of: here, matching: find.byType(NoorPresence)),
      findsOneWidget,
    );
  });

  testWidgets('a family that has done nothing yet: no lantern waits below', (
    tester,
  ) async {
    await _pump(tester);
    expect(find.byKey(const Key('road-lit')), findsNothing);
    expect(find.byKey(const Key('road-start')), findsNothing);
    expect(find.byType(PaperLantern, skipOffstage: false), findsNothing);
    expect(find.text('كل خطوة تربوية تضيء قنديلًا على هذا الدرب.'), findsOneWidget);
  });

  testWidgets('what was done is lit — and only that', (tester) async {
    final fake = _Fake()
      ..lessons = _someProgress()
      ..week = familyWeekJson(
        acts: [act('lesson', 0), act('question', 1), act('lesson', 3)],
        litWeeksTotal: 6,
      );
    await _pump(tester, fake: fake);
    // «أنتم هنا»: the path being resumed, positively.
    expect(find.text('في «الغضب والعناد»: أتممتم 2 من 5'), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('road-start')));
    await tester.pump();
    final lanterns = tester
        .widgetList<PaperLantern>(find.byType(PaperLantern, skipOffstage: false))
        .toList();
    // Three lit days this week + three lit earlier weeks; never an unlit one.
    expect(lanterns.where((l) => l.lit), hasLength(3 + 3 + 2));
    expect(lanterns.where((l) => !l.lit), isEmpty);
    expect(find.text('اكتمل البدر: «الصدق»'), findsOneWidget);
    expect(find.text('6 أسبوعًا مضيئًا منذ البداية').evaluate().isNotEmpty ||
        find.text('6 أسابيع مضيئة منذ البداية').evaluate().isNotEmpty, isTrue);
    for (final word in ['فاتك', 'فاتت', 'ضيّعت', 'ضاع', 'متأخر']) {
      expect(find.textContaining(word), findsNothing, reason: word);
    }
  });

  testWidgets('a gate goes to its one act and is measured', (tester) async {
    final routes = await _pump(tester);
    await tester.tap(find.text('برنامج رمضان'));
    await tester.pump();
    expect(routes.pushed.last, 'ramadan');
    expect(
      logged.where((e) => e.$1 == 'horizon_gate_tapped').single.$2,
      {'gate': 'ramadan'},
    );
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('tg.horizon.tap_gate'), 'ramadan');
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('the next path gate opens that path', (tester) async {
    final routes = await _pump(tester);
    await tester.ensureVisible(find.text('افتح المسار'));
    await tester.pump();
    await tester.tap(find.text('افتح المسار'));
    await tester.pump();
    expect(routes.pushed.last, 'path_detail');
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 2));
  });

  testWidgets('without a birth month the dated gates wait for it', (
    tester,
  ) async {
    final fake = _Fake()
      ..programs = _programs(basis: 'age_group', needs: ['birth_month']);
    await _pump(tester, fake: fake);
    expect(find.byKey(const ValueKey('gate-age_seven')), findsNothing);
    expect(find.byKey(const ValueKey('gate-birth_month')), findsOneWidget);
    expect(find.text('مواعيد سارة القادمة'), findsOneWidget);
  });

  testWidgets('reduced motion: nothing moves', (tester) async {
    await _pump(tester, reduceMotion: true);
    expect(find.byType(Animate), findsNothing);
    final noor = tester.state<NoorPresenceState>(find.byType(NoorPresence));
    expect(noor.haloLooping, isFalse);
  });

  testWidgets('on opening Noor hops in once — and then rests', (tester) async {
    await _pump(tester);
    expect(find.byType(Animate), findsWidgets);
    await tester.pump(const Duration(seconds: 3));
    expect(tester.hasRunningAnimations, isTrue, reason: 'Noor breathes');
  });

  for (final locale in const [Locale('ar'), Locale('en')]) {
    for (final dark in [false, true]) {
      for (final scale in [1.0, 2.0]) {
        testWidgets('lays out: ${locale.languageCode}, '
            '${dark ? 'dark' : 'light'}, ${scale}x text, 360dp', (
          tester,
        ) async {
          final fake = _Fake()
            ..english = locale.languageCode == 'en'
            ..lessons = _someProgress()
            ..week = familyWeekJson(
              acts: [act('lesson', 0), act('question', 1)],
              litWeeksTotal: 4,
            );
          await _pump(
            tester,
            fake: fake,
            locale: locale,
            dark: dark,
            textScale: scale,
            name: locale.languageCode == 'en' ? 'Sara' : 'سارة',
          );
          expect(tester.takeException(), isNull);
          final seen = <String>{};
          final list = find.byKey(const Key('family-road-list'));
          for (var i = 0; i < 40; i++) {
            for (final r in tester.widgetList<RichText>(find.byType(RichText))) {
              seen.add(r.text.toPlainText());
            }
            final pos = tester
                .state<ScrollableState>(
                  find.descendant(of: list, matching: find.byType(Scrollable)),
                )
                .position;
            if (pos.pixels >= pos.maxScrollExtent) break;
            await tester.drag(list, const Offset(0, -300));
            await tester.pump(const Duration(milliseconds: 300));
            expect(tester.takeException(), isNull);
          }
          expect(seen.any((t) => t.contains('Sara') || t.contains('سارة')), isTrue);
          if (locale.languageCode == 'en') {
            final arabic = RegExp(r'[؀-ۿ]');
            expect(
              seen.where(arabic.hasMatch).toList(),
              isEmpty,
              reason: 'Arabic on the English road',
            );
          }
        });
      }
    }
  }
}
