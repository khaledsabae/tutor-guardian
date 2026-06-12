// Phase 4 widget tests — program layer (paths/lessons/daily tip).
//
// Strategy: we don't hit the real network. We override
// [tgClientProvider] with a `_FakeTgClient` whose HTTP methods return
// canned JSON shaped exactly like the backend responses, then assert
// the UI renders the expected widgets (titles, counts, error state).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/program_repository.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/program/screens/lesson_screen.dart';
import 'package:almorabbi/features/program/screens/path_detail_screen.dart';
import 'package:almorabbi/features/program/screens/paths_screen.dart';
import 'package:almorabbi/main.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  group('ProgramRepository', () {
    test('listPaths() parses backend envelope', () async {
      final fake = _FakeTgClient();
      fake.pathsListJson = {
        'count': 1,
        'paths': [_pathJson(id: 'path_4-6_islamic_parenting_adab')],
      };
      final repo = ProgramRepository(fake);
      final result = await repo.listPaths(ageGroup: '4-6');
      expect(result.count, 1);
      expect(result.paths.first.id, 'path_4-6_islamic_parenting_adab');
      expect(result.paths.first.ageGroup, '4-6');
      expect(result.paths.first.lessonIds.length, 3);
    });

    test('getPathDetail() with includeLessons returns PathDetail', () async {
      final fake = _FakeTgClient();
      // API returns path fields at the ROOT level (flat) with a
      // `lessons` array — no "path" wrapper key (see commit 7d056fc).
      fake.pathDetailJson = {
        ..._pathJson(id: 'path_4-6_islamic_parenting_adab'),
        'lessons': [
          _lessonJson(id: 'lesson_4-6_islamic_parenting_adab_01', order: 1),
        ],
      };
      final repo = ProgramRepository(fake);
      final detail = await repo.getPathDetail(
        'path_4-6_islamic_parenting_adab',
      );
      expect(detail.path.id, 'path_4-6_islamic_parenting_adab');
      expect(detail.lessons.length, 1);
      expect(detail.lessons.first.order, 1);
    });

    test('getLesson() parses single lesson', () async {
      final fake = _FakeTgClient();
      fake.lessonJson = _lessonJson(
        id: 'lesson_4-6_islamic_parenting_adab_01',
        order: 1,
        withWarning: true,
      );
      final repo = ProgramRepository(fake);
      final lesson = await repo.getLesson(
        'lesson_4-6_islamic_parenting_adab_01',
      );
      expect(lesson.title, 'الرفق: قيمة تربوية قبل أسلوب');
      expect(lesson.needsProfessionalFollowup, isTrue);
    });

    test('getDailyTip() parses tip', () async {
      final fake = _FakeTgClient();
      fake.dailyTipJson = _tipJson(id: 'tip_4-6_001');
      final repo = ProgramRepository(fake);
      final tip = await repo.getDailyTip(ageGroup: '4-6');
      expect(tip.id, 'tip_4-6_001');
      expect(tip.timeOfDay, 'morning');
    });
    });

    group('Program widgets', () {
    testWidgets('PathsScreen shows cards from fake list', (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.pathsListJson = {
        'count': 2,
        'paths': [
          _pathJson(
            id: 'path_4-6_islamic_parenting_adab',
            title: 'تأسيس الآداب الإسلامية',
          ),
          _pathJson(
            id: 'path_4-6_development_positive_parenting',
            title: 'التربية الإيجابية',
          ),
        ],
      };

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      await storage.markOnboardingCompleted();

      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 1;
      addTearDown(container.dispose);

      // Set a larger viewport to avoid AppBar overflow
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: PathsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('مساراتي'), findsWidgets); // AppBar title
      expect(find.text('تأسيس الآداب الإسلامية'), findsOneWidget);
      expect(find.text('التربية الإيجابية'), findsOneWidget);
      // Days pill on the path cards (emoji-prefixed in the redesign)
      expect(find.textContaining('14 يوم'), findsWidgets);
      // Accessibility (P1 #5): each path card exposes one coherent button
      // semantics node labelled with its title for screen readers.
      expect(
        find.bySemanticsLabel(RegExp('مسار: تأسيس الآداب الإسلامية')),
        findsOneWidget,
      );
    });

    testWidgets('PathsScreen shows error state on failure', (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.throwOnPathsList = true;

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      await storage.markOnboardingCompleted();

      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 1;
      addTearDown(container.dispose);

      // Set a larger viewport
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: PathsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('إعادة المحاولة'), findsOneWidget);
    });

    testWidgets('LessonScreen renders try_this, summary, reflection prompts',
        (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.lessonJson = _lessonJson(
        id: 'lesson_4-6_islamic_parenting_adab_01',
        order: 1,
        summary: 'ملخص تجريبي للدرس.',
        tryThis: 'جرّب هذا النص في أسبوعك.',
        reflectionPrompts: ['سؤال 1؟', 'سؤال 2؟'],
        withWarning: true,
      );

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      await storage.markOnboardingCompleted();

      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 1;
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LessonScreen(
              lessonId: 'lesson_4-6_islamic_parenting_adab_01',
              ageGroup: '4-6',
              childId: 1,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('الملخص'), findsOneWidget);
      expect(find.text('جرّب هذا'), findsOneWidget);
      expect(find.text('ملخص تجريبي للدرس.'), findsOneWidget);
      expect(find.text('جرّب هذا النص في أسبوعك.'), findsOneWidget);
      expect(find.text('سؤال 1؟'), findsOneWidget);
      expect(find.text('سؤال 2؟'), findsOneWidget);
      // needs_professional_followup is NOT set on this lesson
      expect(find.textContaining('متابعة متخصصة'), findsNothing);
    });

    testWidgets('LessonScreen shows interactive content section when assets are present',
        (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.lessonJson = _lessonJson(
        id: 'lesson_4-6_islamic_parenting_adab_01',
        order: 1,
      );
      fake.lessonAssetsJson = {
        'podcast_mp3': 'docs/lesson_01_podcast.mp3',
        'video_mp4': 'docs/lesson_videos/video.mp4',
        'flashcards': [
          {'id': 'fc-1', 'item_count': 10}
        ],
        'quizzes': [
          {'id': 'qz-1', 'item_count': 5}
        ]
      };

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      await storage.markOnboardingCompleted();

      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 1;
      addTearDown(container.dispose);
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LessonScreen(
              lessonId: 'lesson_4-6_islamic_parenting_adab_01',
              ageGroup: '4-6',
              childId: 1,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('محتوى تفاعلي'), findsOneWidget);
      expect(find.textContaining('استمع للبودكاست'), findsOneWidget);
      expect(find.textContaining('شاهد الفيديو'), findsOneWidget);
      expect(find.textContaining('فلاش كاردز (10 بطاقة)'), findsOneWidget);
      expect(find.textContaining('اختبر نفسك (5 سؤال)'), findsOneWidget);

      // Tap on podcast and verify the real player screen opens
      // (replaces the Phase-4 "شاشة مؤقتة" placeholder).
      await tester.tap(find.textContaining('استمع للبودكاست'));
      // Pump a few frames so the navigator can finish pushing the
      // new route. We don't pumpAndSettle because just_audio's
      // MethodChannel never resolves in the host VM.
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      // The player screen's AppBar shows the title.
      expect(find.text('🎧 البودكاست'), findsOneWidget);
    });

    testWidgets('LessonScreen does not show interactive content when no assets are present',
        (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.lessonJson = _lessonJson(
        id: 'lesson_4-6_islamic_parenting_adab_01',
        order: 1,
      );
      fake.lessonAssetsJson = null; // will throw 404/error

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      await storage.markOnboardingCompleted();

      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 1;
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LessonScreen(
              lessonId: 'lesson_4-6_islamic_parenting_adab_01',
              ageGroup: '4-6',
              childId: 1,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('محتوى تفاعلي'), findsNothing);
    });

    testWidgets('PathDetailScreen lists lessons, navigate to lesson screen',
        (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.pathDetailJson = {
        ..._pathJson(id: 'path_4-6_islamic_parenting_adab'),
        'lessons': [
          _lessonJson(
            id: 'lesson_4-6_islamic_parenting_adab_01',
            order: 1,
            title: 'الرفق',
          ),
          _lessonJson(
            id: 'lesson_4-6_islamic_parenting_adab_02',
            order: 2,
            title: 'اللعب النبوي',
          ),
        ],
      };

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      await storage.markOnboardingCompleted();

      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 1;
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: PathDetailScreen(
              pathId: 'path_4-6_islamic_parenting_adab',
              ageGroup: '4-6',
            ),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('الرفق'), findsOneWidget);
      expect(find.text('اللعب النبوي'), findsOneWidget);
      expect(find.text('الدروس (2)'), findsOneWidget);
      // Tap the first lesson - set lessonJson BEFORE tapping so the navigation gets the data
      fake.lessonJson = _lessonJson(
        id: 'lesson_4-6_islamic_parenting_adab_01',
        order: 1,
        title: 'الرفق',
      );
      await tester.tap(find.text('الرفق'));
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));
      // The lesson screen should appear with the lesson loaded
      expect(find.text('الملخص'), findsOneWidget);
    });

    testWidgets('RootScaffold NavigationBar switches tabs', (WidgetTester tester) async {
      // Use a fake that works for paths list but throws elsewhere
      final fake = _FakeTgClient();
      fake.pathsListJson = {
        'count': 2,
        'paths': [
          _pathJson(
            id: 'path_4-6_islamic_parenting_adab',
            title: 'تأسيس الآداب الإسلامية',
          ),
          _pathJson(
            id: 'path_4-6_development_positive_parenting',
            title: 'التربية الإيجابية',
          ),
        ],
      };

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      await storage.markOnboardingCompleted();

      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      await container.read(sharedPreferencesProvider.future);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const TutorGuardianApp(),
        ),
      );
      // Pump multiple times to let the boot sequence complete
      for (int i = 0; i < 80; i++) {
        await tester.pump(const Duration(milliseconds: 500));
        if (find.byType(NavigationBar).evaluate().isNotEmpty) break;
      }
      await tester.pump(const Duration(milliseconds: 1000));
      await tester.pump(const Duration(milliseconds: 1000));

      // Tab 0 (المساعد) is the default
      await tester.pump(const Duration(milliseconds: 1000));
      await tester.pump(const Duration(milliseconds: 1000));
      await tester.pump(const Duration(milliseconds: 1000));
      await tester.pump(const Duration(milliseconds: 1000));

      // Check NavigationBar exists and has 3 destinations
      // (اليوم / مساراتي / المساعد — tab 0 "اليوم" is the default)
      expect(find.byType(NavigationBar), findsOneWidget);
      final navBar = tester.widget<NavigationBar>(find.byType(NavigationBar));
      expect(navBar.destinations.length, 3);

      // Destination labels render
      expect(find.byWidgetPredicate((widget) =>
        widget is Text && widget.data != null && widget.data!.contains('المساعد')
      ), findsWidgets);
      expect(find.text('مساراتي'), findsOneWidget);

      // Actually switch to the مساراتي (paths) tab. IndexedStack keeps the
      // non-active tab offstage, so its content isn't findable until selected.
      await tester.tap(find.text('مساراتي'));
      for (int i = 0; i < 12; i++) {
        await tester.pump(const Duration(milliseconds: 300));
        if (find.text('تأسيس الآداب الإسلامية').evaluate().isNotEmpty) break;
      }

      // Should now show the PathsScreen content
      expect(find.text('تأسيس الآداب الإسلامية'), findsOneWidget);
    });
  });
}

// ── Fake TgClient ─────────────────────────────────────────────────────────

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? pathsListJson;
  Map<String, dynamic>? pathDetailJson;
  Map<String, dynamic>? lessonJson;
  Map<String, dynamic>? dailyTipJson;
  Map<String, dynamic>? lessonAssetsJson;
  bool throwOnPathsList = false;

  @override
  Future<Map<String, dynamic>> getPathsList({
    String? ageGroup,
    String? domain,
  }) async {
    if (throwOnPathsList) {
      throw const TgApiError(500, 'fake-error');
    }
    return pathsListJson ?? {'count': 0, 'paths': []};
  }

  @override
  Future<Map<String, dynamic>> getPathDetail(
    String pathId, {
    bool includeLessons = false,
  }) async {
    // Flat shape — path fields at root + lessons array (commit 7d056fc).
    return pathDetailJson ?? {..._pathJson(id: pathId), 'lessons': []};
  }

  @override
  Future<Map<String, dynamic>> getLesson(String lessonId) async {
    return lessonJson ?? _lessonJson(id: lessonId, order: 1);
  }

  @override
  Future<Map<String, dynamic>> getLessonAssets(String lessonId, {String? lang}) async {
    if (lessonAssetsJson != null) return lessonAssetsJson!;
    throw const TgApiError(404, 'not-found');
  }

  @override
  Future<Map<String, dynamic>> getDailyTip({
    required String ageGroup,
    String? timeOfDay,
  }) async {
    return dailyTipJson ?? _tipJson(id: 'tip_${ageGroup}_000');
  }
}

// ── JSON fixtures (mirror backend response shapes exactly) ────────────────

Map<String, dynamic> _pathJson({
  required String id,
  String title = 'تأسيس الآداب الإسلامية والضمير الأخلاقي (4-6 سنوات)',
}) {
  return {
    'id': id,
    'title': title,
    'age_group': '4-6',
    'domain': 'islamic_parenting',
    'description': 'رحلة تربوية لمدة 14 يوماً لتأسيس القيم الأخلاقية.',
    'lesson_ids': [
      'lesson_4-6_islamic_parenting_adab_01',
      'lesson_4-6_islamic_parenting_adab_02',
      'lesson_4-6_islamic_parenting_adab_03',
    ],
    'estimated_days': 14,
    'pedagogical_framework': 'prophetic_7_7_7',
    'primary_reference': {
      'type': 'كتاب_تربوي',
      'info': 'ابن القيم الجوزية، تحفة المودود',
    },
    'prerequisites': [],
    'is_published': true,
    'version': '1.0.0',
  };
}

Map<String, dynamic> _lessonJson({
  required String id,
  required int order,
  String title = 'الرفق: قيمة تربوية قبل أسلوب',
  String summary = 'في مرحلة ما قبل العمليات يبدأ الطفل بتمييز الصوت الحنون.',
  String tryThis = 'هذا الأسبوع: اختر وقتاً يومياً واحداً تتحدث فيه مع طفلك بصوت هادئ.',
  List<String>? reflectionPrompts,
  bool withWarning = false,
}) {
  return {
    'id': id,
    'path_id': 'path_4-6_islamic_parenting_adab',
    'title': title,
    'age_group': '4-6',
    'domain': 'islamic_parenting',
    'unit_ids': ['0bd76d3c-548a-46ed-b17b-78874741662a'],
    'summary': summary,
    'try_this': tryThis,
    'order': order,
    'estimated_minutes': 5,
    'reflection_prompts': reflectionPrompts ?? [],
    'warning_flags': withWarning ? ['needs_professional_followup'] : [],
    'is_published': true,
    'version': '1.0.0',
  };
}

Map<String, dynamic> _tipJson({required String id}) {
  return {
    'id': id,
    'age_group': '4-6',
    'domain': 'islamic_parenting',
    'text': 'ابدأ يومك بابتسامة.',
    'unit_id': '0bd76d3c-548a-46ed-b17b-78874741662a',
    'day_of_week': 0,
    'time_of_day': 'morning',
    'tags': ['رفق', 'صباح'],
    'is_published': true,
    'version': '1.0.0',
  };
}

// ── Fake TgClient ─────────────────────────────────────────────────────────
