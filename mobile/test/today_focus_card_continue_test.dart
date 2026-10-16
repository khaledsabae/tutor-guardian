/// «واصل مسارك» → «متابعة» opens the lesson that is due, not the path overview.
///
/// Khaled on 1.0.73: the card read «أوّل ما يعرفه قلبه: الله», 2/4, «2 دروس
/// باقية», and «متابعة» opened the path detail page — one more screen
/// between the parent and the lesson the card had just counted down to. Due
/// = the first lesson of the path, in curriculum order, the child has not
/// completed: the rule of the path's own «واصل المسار» button and of the
/// server's /next-lesson.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/analytics.dart';
import 'package:almorabbi/core/app_routes.dart';
import 'package:almorabbi/features/home/widgets/today_focus_card.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/models.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/screens/lesson_screen.dart';
import 'package:almorabbi/features/program/screens/path_detail_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart' show tgClientProvider;

const _pathTitle = 'أوّل ما يعرفه قلبه: الله (2-3 سنوات)';
const _lessons = ['l1', 'l2', 'l3', 'l4'];

class _FakeClient extends TgClient {
  @override
  Future<Map<String, dynamic>> getPathsList({
    String? ageGroup,
    String? domain,
  }) async => {
    'count': 1,
    'paths': [
      {
        'id': 'p1',
        'title': _pathTitle,
        'age_group': '2-3',
        'domain': 'aqeedah',
        'lesson_ids': _lessons,
      },
    ],
  };

  @override
  Future<Map<String, dynamic>> getNextLesson(
    String ageGroup, {
    int? childId,
  }) async => {
    'lesson_id': 'l1',
    'path_id': 'p1',
    'path_title': _pathTitle,
    'title': 'الدرس الأول',
    'order': 1,
    'resumed': false,
  };
}

class _PushLog extends NavigatorObserver {
  final routes = <Route<dynamic>>[];

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    // The home route is not a push anyone made.
    if (previousRoute != null) routes.add(route);
  }
}

LessonProgress _row(String id, ProgressStatus status, {String path = 'p1'}) =>
    LessonProgress(lessonId: id, pathId: path, status: status);

const _done = ProgressStatus.completed;

Future<_PushLog> _pumpCard(
  WidgetTester tester,
  List<LessonProgress> rows,
) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(
    overrides: [
      tgClientProvider.overrideWithValue(_FakeClient()),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ],
  );
  addTearDown(container.dispose);
  final log = _PushLog();
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        navigatorObservers: [log],
        home: Scaffold(
          body: SingleChildScrollView(
            child: TodayFocusCard(
              bundle: ChildProgressBundle(childId: 7, lessons: rows),
              ageGroup: '2-3',
              onStartFirstPath: () {},
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
  return log;
}

/// The screen the one pushed route would build — read off the route itself,
/// so the assertion is the destination and its arguments, not a label.
Widget _pushed(WidgetTester tester, _PushLog log) {
  expect(log.routes, hasLength(1), reason: 'exactly one screen was opened');
  final route = log.routes.single as MaterialPageRoute<dynamic>;
  return route.builder(tester.element(find.byType(TodayFocusCard)));
}

Future<LessonScreen> _tapContinueExpectLesson(
  WidgetTester tester,
  _PushLog log,
) async {
  await tester.tap(find.text('متابعة'));
  expect(log.routes.single.settings.name, Screens.lesson);
  final screen = _pushed(tester, log);
  expect(screen, isA<LessonScreen>());
  return screen as LessonScreen;
}

void main() {
  final events = <(String, Map<String, Object>?)>[];
  setUp(() {
    events.clear();
    Analytics.debugSink = (name, params) => events.add((name, params));
  });
  tearDown(() => Analytics.debugSink = null);

  testWidgets('2 of 4 done in order: «متابعة» opens lesson 3', (tester) async {
    final log = await _pumpCard(tester, [
      _row('l1', _done),
      _row('l2', _done),
    ]);
    expect(find.text(_pathTitle), findsOneWidget);
    expect(find.text('2/4'), findsOneWidget);

    final lesson = await _tapContinueExpectLesson(tester, log);
    expect(lesson.lessonId, 'l3');
    expect(lesson.ageGroup, '2-3');
    expect(lesson.childId, 7, reason: 'progress is saved for this child');
    // Same event and action as before, plus the lesson it landed on.
    expect(events.last.$1, 'today_block_tapped');
    expect(events.last.$2, {
      'block': 'step',
      'action': 'continue',
      'lesson_id': 'l3',
    });
  });

  testWidgets('done out of order (1 and 3): opens 2, the first gap', (
    tester,
  ) async {
    final log = await _pumpCard(tester, [
      _row('l1', _done),
      _row('l3', _done),
      // A half-read later lesson does not jump the queue.
      _row('l4', ProgressStatus.inProgress),
    ]);
    expect(find.text('2/4'), findsOneWidget);

    final lesson = await _tapContinueExpectLesson(tester, log);
    expect(lesson.lessonId, 'l2');
  });

  testWidgets('a stale completed id not in the path neither counts nor opens', (
    tester,
  ) async {
    final log = await _pumpCard(tester, [
      _row('l1', _done),
      // Removed from the path in a curriculum edit; its row survived.
      _row('l_removed', _done),
      // A duplicate row for the same lesson.
      _row('l1', _done),
    ]);
    expect(
      find.text('1/4'),
      findsOneWidget,
      reason: 'only lessons the path lists count toward «done»',
    );
    expect(find.text('2/4'), findsNothing);
    expect(find.text('3/4'), findsNothing);

    final lesson = await _tapContinueExpectLesson(tester, log);
    expect(lesson.lessonId, 'l2');
  });

  testWidgets('stale rows cannot make an unfinished path read as finished', (
    tester,
  ) async {
    // Three listed lessons done + one stale row = four completed rows for a
    // four-lesson path. Counted by path id alone, that path was "complete"
    // and the card dropped it; it still has l4 to read.
    final log = await _pumpCard(tester, [
      _row('l1', _done),
      _row('l2', _done),
      _row('l3', _done),
      _row('l_removed', _done),
    ]);
    expect(find.text('3/4'), findsOneWidget);

    final lesson = await _tapContinueExpectLesson(tester, log);
    expect(lesson.lessonId, 'l4');
  });

  testWidgets('«عرض المسار» still opens the path overview', (tester) async {
    final log = await _pumpCard(tester, [_row('l1', _done)]);

    await tester.tap(find.text('عرض المسار'));
    expect(log.routes.single.settings.name, Screens.pathDetail);
    final screen = _pushed(tester, log);
    expect(screen, isA<PathDetailScreen>());
    expect((screen as PathDetailScreen).pathId, 'p1');
    expect(events.last.$2, {'block': 'step', 'action': 'path_overview'});
  });

  group('the fallback to the path overview', () {
    CurriculumPath path(List<String> ids) => CurriculumPath.fromJson({
      'id': 'p1',
      'title': _pathTitle,
      'age_group': '2-3',
      'domain': 'aqeedah',
      'lesson_ids': ids,
    });
    ChildProgressBundle bundle(List<LessonProgress> rows) =>
        ChildProgressBundle(childId: 7, lessons: rows);

    test('all done ⇒ no due lesson ⇒ «متابعة» opens path detail', () {
      final rows = [for (final id in _lessons) _row(id, _done)];
      expect(dueLessonIdIn(path(_lessons), bundle(rows)), isNull);
    });

    test('a path that lists no lessons ⇒ path detail', () {
      expect(dueLessonIdIn(path(const []), bundle(const [])), isNull);
    });

    test('progress not loaded ⇒ path detail, not lesson 1 by guess', () {
      expect(dueLessonIdIn(path(_lessons), null), isNull);
    });

    test('a completion recorded under another path does not count here', () {
      final rows = [_row('l1', _done, path: 'p_other')];
      expect(dueLessonIdIn(path(_lessons), bundle(rows)), 'l1');
    });

    testWidgets(
      'all done: the card does not offer «متابعة» on a finished path',
      (tester) async {
        final log = await _pumpCard(tester, [
          for (final id in _lessons) _row(id, _done),
        ]);
        // The finished path is not "continued": the card falls through to
        // the server's next lesson, and nothing was pushed by building it.
        expect(find.text('متابعة'), findsNothing);
        expect(find.text('4/4'), findsNothing);
        expect(log.routes, isEmpty);
      },
    );
  });
}
