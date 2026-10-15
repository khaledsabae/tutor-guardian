// «اكتمل البدر» and «درب المسار» (NOOR_WAL_QANADIL_PLAN, phase 4).
//
// The full moon is a moment, so it must be rare and earned: it rises when a
// path goes from not-all to all lessons done *on this screen* (the parent
// coming back from the last lesson), once per path on the device — never on
// opening a path finished long ago. It is still under reduce-motion, and its
// share button sends the existing path card.
//
// The road: gold only between two finished lessons, a lit lantern on each
// finished lesson, Noor on the next one, quiet paper elsewhere.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/features/home/widgets/sky_band.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/program/screens/lesson_screen.dart';
import 'package:almorabbi/features/program/screens/path_detail_screen.dart';
import 'package:almorabbi/features/program/widgets/full_moon_moment.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';
import 'package:almorabbi/state/chat_notifier.dart';

import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/theme/app_theme.dart';

const _pathId = 'path_4-6_islamic_parenting_adab';
const _pathTitle = 'تأسيس الآداب';

String _lessonId(int i) => 'lesson_4-6_islamic_parenting_adab_0${i + 1}';

class _FakeClient extends TgClient {
  _FakeClient({required this.lessons, Set<int> done = const {}, Map<int, String> started = const {}})
      : _done = {...done},
        _started = {...started};

  final int lessons;
  Set<int> _done;
  final Map<int, String> _started;

  /// What the server will say about the child's progress from the next fetch.
  set done(Set<int> d) => _done = {...d};

  @override
  Future<Map<String, dynamic>> getPathDetail(String pathId, {bool includeLessons = false}) async => {
        'id': _pathId,
        'title': _pathTitle,
        'age_group': '4-6',
        'domain': 'islamic_parenting',
        'description': 'رحلة تربوية قصيرة.',
        'lesson_ids': [for (var i = 0; i < lessons; i++) _lessonId(i)],
        'estimated_days': 7,
        'pedagogical_framework': 'prophetic_7_7_7',
        'prerequisites': [],
        'is_published': true,
        'version': '1.0.0',
        'lessons': [for (var i = 0; i < lessons; i++) _lesson(i)],
      };

  @override
  Future<Map<String, dynamic>> getLesson(String lessonId) async =>
      _lesson(int.parse(lessonId.substring(lessonId.length - 1)) - 1);

  @override
  Future<Map<String, dynamic>> getChildProgress(int childId, {String? pathId}) async => {
        'child_id': childId,
        'lessons': [
          for (final i in _done)
            {
              'lesson_id': _lessonId(i),
              'path_id': _pathId,
              'status': 'completed',
              'started_at': '2026-10-01T00:00:00Z',
              'completed_at': '2026-10-01T00:05:00Z',
              'updated_at': '2026-10-01T00:05:00Z',
            },
          for (final e in _started.entries)
            if (!_done.contains(e.key))
              {
                'lesson_id': _lessonId(e.key),
                'path_id': _pathId,
                'status': e.value,
                'started_at': '2026-10-01T00:00:00Z',
                'completed_at': null,
                'updated_at': '2026-10-01T00:05:00Z',
              },
        ],
        'streak_days': 3,
      };

  Map<String, dynamic> _lesson(int i) => {
        'id': _lessonId(i),
        'path_id': _pathId,
        'title': 'درس رقم ${i + 1}',
        'age_group': '4-6',
        'domain': 'islamic_parenting',
        'unit_ids': <String>[],
        'summary': 'ملخص قصير.',
        'try_this': 'جرّب هذا.',
        'order': i + 1,
        'estimated_minutes': 5,
        'reflection_prompts': <String>[],
        'warning_flags': <String>[],
        'is_published': true,
        'version': '1.0.0',
      };
}

class _Pumped {
  _Pumped(this.container, this.nav, this.prefs);
  final ProviderContainer container;
  final GlobalKey<NavigatorState> nav;
  final SharedPreferences prefs;
}

Future<_Pumped> _pumpPath(
  WidgetTester tester,
  _FakeClient client, {
  Locale locale = const Locale('ar'),
  bool dark = false,
  double textScale = 1,
  bool reduceMotion = false,
  Map<String, Object> prefs = const {},
}) async {
  tester.view.physicalSize = const Size(400, 860) * 3.0;
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({...prefs});
  final sp = await SharedPreferences.getInstance();
  await OnboardingStorage(sp).setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(client),
    sharedPreferencesProvider.overrideWith((_) async => sp),
  ]);
  addTearDown(container.dispose);
  await container.read(sharedPreferencesProvider.future);
  container.read(activeChildIdProvider.notifier).state = 1;
  if (dark) {
    AppPalette.current = AppPalette.dark;
    addTearDown(() => AppPalette.current = AppPalette.light);
  }
  final nav = GlobalKey<NavigatorState>();
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      navigatorKey: nav,
      locale: locale,
      theme: dark ? AppTheme.dark() : AppTheme.light(),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) {
        AppL10n.current = AppLocalizations.of(context);
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(textScale),
            disableAnimations: reduceMotion,
          ),
          child: child!,
        );
      },
      home: const PathDetailScreen(pathId: _pathId, ageGroup: '4-6'),
    ),
  ));
  await _frames(tester);
  return _Pumped(container, nav, sp);
}

Future<void> _frames(WidgetTester tester, [int n = 8]) async {
  for (var i = 0; i < n; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

Finder get _scrollable => find
    .descendant(of: find.byType(ListView), matching: find.byType(Scrollable))
    .first;

/// The parent opens [lesson] from the trail, finishes it inside (the lesson
/// screen's own invalidation, done here by hand), and comes back.
Future<void> _finishFromHere(
  WidgetTester tester,
  _Pumped p,
  _FakeClient client, {
  required int lesson,
  required Set<int> doneAfter,
}) async {
  final row = find.text('درس رقم ${lesson + 1}');
  await tester.scrollUntilVisible(row, 200, scrollable: _scrollable);
  await tester.tap(row);
  await _frames(tester);
  expect(find.byType(LessonScreen), findsOneWidget);
  client.done = doneAfter;
  p.container.invalidate(childProgressProvider(1));
  await _frames(tester);
  // Still inside the lesson: nothing rises over it.
  expect(find.byKey(const ValueKey('full_moon_moment')), findsNothing);
  p.nav.currentState!.pop();
  await _frames(tester, 12);
}

List<MethodCall> _recordHaptics(WidgetTester tester) {
  final calls = <MethodCall>[];
  tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
    calls.add(call);
    return null;
  });
  addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
  return calls;
}

void main() {
  group('«اكتمل البدر»', () {
    testWidgets('rises once, when the last lesson is finished from this screen', (tester) async {
      final haptics = _recordHaptics(tester);
      final client = _FakeClient(lessons: 2, done: {0});
      final p = await _pumpPath(tester, client);
      expect(find.byKey(const ValueKey('full_moon_moment')), findsNothing);

      await _finishFromHere(tester, p, client, lesson: 1, doneAfter: {0, 1});

      expect(find.byKey(const ValueKey('full_moon_moment')), findsOneWidget);
      expect(find.text('اكتمل البدر'), findsOneWidget);
      expect(find.text('أتممتم «$_pathTitle» كاملًا، درسًا بعد درس.'), findsOneWidget);
      expect(
        haptics.where((c) => c.method == 'HapticFeedback.vibrate' && c.arguments == 'HapticFeedbackType.lightImpact'),
        hasLength(1),
      );
      expect(p.prefs.getStringList(kFullMoonShownKey), [_pathId]);

      await tester.tap(find.byKey(const ValueKey('full_moon_close')));
      await _frames(tester);
      expect(find.byKey(const ValueKey('full_moon_moment')), findsNothing);

      // The same path finished again (progress reset and redone): not twice.
      client.done = {0};
      p.container.invalidate(childProgressProvider(1));
      await _frames(tester);
      await _finishFromHere(tester, p, client, lesson: 1, doneAfter: {0, 1});
      expect(find.byKey(const ValueKey('full_moon_moment')), findsNothing);
    });

    testWidgets('a path opened already finished stays quiet', (tester) async {
      final client = _FakeClient(lessons: 2, done: {0, 1});
      final p = await _pumpPath(tester, client);
      // A refresh that changes nothing changes nothing.
      p.container.invalidate(childProgressProvider(1));
      await _frames(tester);
      expect(find.byKey(const ValueKey('full_moon_moment')), findsNothing);
      expect(p.prefs.getStringList(kFullMoonShownKey), isNull);
    });

    testWidgets('finishing a lesson that is not the last one is no moment', (tester) async {
      final client = _FakeClient(lessons: 3, done: {0});
      final p = await _pumpPath(tester, client);
      await _finishFromHere(tester, p, client, lesson: 1, doneAfter: {0, 1});
      expect(find.byKey(const ValueKey('full_moon_moment')), findsNothing);
    });

    testWidgets('its share button sends the path card', (tester) async {
      final sent = <Map<Object?, Object?>>[];
      const channel = MethodChannel('dev.fluttercommunity.plus/share');
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, (call) async {
        sent.add(call.arguments as Map<Object?, Object?>);
        return null;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, null));

      final client = _FakeClient(lessons: 1);
      final p = await _pumpPath(tester, client);
      await _finishFromHere(tester, p, client, lesson: 0, doneAfter: {0});
      expect(find.byKey(const ValueKey('full_moon_share')), findsOneWidget);

      await tester.runAsync(() async {
        await tester.tap(find.byKey(const ValueKey('full_moon_share')));
        for (var i = 0; i < 100 && sent.isEmpty; i++) {
          await Future<void>.delayed(const Duration(milliseconds: 50));
        }
      });
      await _frames(tester);
      expect(sent, hasLength(1));
      expect(sent.single['text'] as String, contains(_pathTitle));
      final image = File((sent.single['paths']! as List).single as String);
      addTearDown(() => image.parent.deleteSync(recursive: true));
      expect(image.path, endsWith('path_$_pathId.png'));
      expect(image.lengthSync(), greaterThan(0));

    });

    testWidgets('fills in 1.2 s, then rests full', (tester) async {
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: FullMoonMoment(pathTitle: _pathTitle, onShare: () {})),
      ));
      final s = tester.state<FullMoonMomentState>(find.byType(FullMoonMoment));
      expect(s.fill, lessThan(.1));
      expect(s.filling, isTrue);
      await tester.pump(const Duration(milliseconds: 600));
      expect(s.fill, inExclusiveRange(.1, 1));
      await tester.pump(const Duration(milliseconds: 700));
      expect(s.fill, 1);
      expect(s.filling, isFalse);
    });

    testWidgets('under reduce-motion it is the still full moon from the first frame', (tester) async {
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: child!,
        ),
        home: Scaffold(body: FullMoonMoment(pathTitle: _pathTitle, onShare: () {})),
      ));
      final s = tester.state<FullMoonMomentState>(find.byType(FullMoonMoment));
      expect(s.fill, 1);
      expect(s.filling, isFalse);
      final art = tester.widget<CustomPaint>(find.byKey(const ValueKey('full_moon_art')));
      expect((art.painter! as FullMoonPainter).progress, 1);
    });

    for (final dark in [false, true]) {
      testWidgets('200% text${dark ? ', dark' : ''}: no overflow, every word on the card', (tester) async {
        final client = _FakeClient(lessons: 1);
        final p = await _pumpPath(tester, client, dark: dark, textScale: 2, reduceMotion: true);
        await _finishFromHere(tester, p, client, lesson: 0, doneAfter: {0});
        expect(find.byKey(const ValueKey('full_moon_moment')), findsOneWidget);
        await tester.scrollUntilVisible(find.byKey(const ValueKey('full_moon_close')), 100,
            scrollable: find.descendant(of: find.byType(FullMoonMoment), matching: find.byType(Scrollable)));
        expect(tester.takeException(), isNull);
      });
    }
  });

  group('«درب المسار»', () {
    PathTrailPainter road(WidgetTester tester) =>
        tester.widget<CustomPaint>(find.byKey(const ValueKey('path_trail_road'))).painter! as PathTrailPainter;

    testWidgets('gold only between two finished lessons; lanterns on them; Noor on the next', (tester) async {
      final client = _FakeClient(lessons: 4, done: {0, 1}, started: {3: 'in_progress'});
      await _pumpPath(tester, client);
      await tester.scrollUntilVisible(find.byKey(const ValueKey('trail_paper_3')), 200, scrollable: _scrollable);

      expect(road(tester).walked, [true, true, false, false]);
      expect(find.byKey(const ValueKey('trail_lantern_0')), findsOneWidget);
      expect(find.byKey(const ValueKey('trail_lantern_1')), findsOneWidget);
      expect(find.byKey(const ValueKey('trail_noor_2')), findsOneWidget);
      expect(find.byKey(const ValueKey('trail_paper_3')), findsOneWidget);
      // One small Noor on the road, and she rests (a list is no place for a loop).
      final noor = tester.state<NoorPresenceState>(find.byType(NoorPresence));
      expect(noor.haloLooping, isFalse);
    });

    testWidgets('a gap breaks the gold: a lesson finished after an open one is lit, the road to it is not',
        (tester) async {
      final client = _FakeClient(lessons: 3, done: {0, 2});
      await _pumpPath(tester, client);
      await tester.scrollUntilVisible(find.byKey(const ValueKey('trail_lantern_2')), 200, scrollable: _scrollable);
      expect(road(tester).walked, [true, false, false]);
      expect(find.byKey(const ValueKey('trail_noor_1')), findsOneWidget);
      expect(find.byKey(const ValueKey('trail_lantern_2')), findsOneWidget);
    });

    testWidgets('all finished: every station a lantern, the whole road gold, no Noor', (tester) async {
      final client = _FakeClient(lessons: 3, done: {0, 1, 2});
      await _pumpPath(tester, client);
      expect(road(tester).walked, [true, true, true]);
      expect(find.byType(NoorPresence), findsNothing);
    });

    testWidgets('nothing started: paper road, Noor on the first lesson, a quiet sky above, no words on it',
        (tester) async {
      final client = _FakeClient(lessons: 2);
      await _pumpPath(tester, client);
      expect(road(tester).walked, [false, false]);
      await tester.scrollUntilVisible(find.byKey(const ValueKey('trail_noor_0')), 200, scrollable: _scrollable);
      expect(find.byKey(const ValueKey('trail_noor_0')), findsOneWidget);
      final sky = find.byKey(const ValueKey('path_trail_sky'));
      expect(sky, findsOneWidget);
      expect(find.descendant(of: sky, matching: find.byType(Text)), findsNothing);
      expect(tester.widget<SkyBand>(sky), isA<SkyBand>());
    });

    testWidgets('the streak chip is quiet: no flame anywhere on the screen', (tester) async {
      await _pumpPath(tester, _FakeClient(lessons: 2, done: {0}));
      expect(find.text('3 أيام متتالية'), findsOneWidget);
      expect(find.textContaining('🔥'), findsNothing);
    });

    for (final dark in [false, true]) {
      testWidgets('200% text${dark ? ', dark' : ''}: the whole trail builds without overflow', (tester) async {
        await _pumpPath(tester, _FakeClient(lessons: 4, done: {0}, started: {2: 'in_progress'}),
            dark: dark, textScale: 2);
        await tester.scrollUntilVisible(find.byKey(const ValueKey('trail_paper_3')), 200, scrollable: _scrollable);
        expect(tester.takeException(), isNull);
      });
    }
  });
}
