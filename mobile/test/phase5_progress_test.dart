// Phase 5 widget + repository tests — children + progress.
//
// Same pattern as program_widget_test.dart: override tgClientProvider
// with a fake that returns canned JSON. We don't run the real auth
// middleware; the child/progress endpoints are exercised via the
// `ProgressRepository` directly and via UI screens with a fake.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/data/progress_repository.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/program/screens/lesson_screen.dart';
import 'package:almorabbi/features/program/screens/path_detail_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  group('ProgressRepository', () {
    test('createChild() parses backend response', () async {
      final fake = _FakeTgClient();
      fake.createChildJson = {
        'id': 1,
        'name': 'سارة',
        'age_group': '4-6',
        'gender': 'female',
        'avatar_emoji': '👧',
        'created_at': '2026-06-08T12:00:00',
        'updated_at': '2026-06-08T12:00:00',
      };
      final repo = ProgressRepository(fake);
      final child = await repo.createChild(
        name: 'سارة',
        ageGroup: '4-6',
        avatarEmoji: '👧',
      );
      expect(child.id, 1);
      expect(child.name, 'سارة');
      expect(child.ageGroup, '4-6');
      expect(child.avatarEmoji, '👧');
    });

    test('getChildProgress() returns bundle with statuses', () async {
      final fake = _FakeTgClient();
      fake.childProgressJson = {
        'child_id': 7,
        'device_id': 'dev-1',
        'lessons': [
          {
            'lesson_id': 'lesson_a',
            'path_id': 'path_1',
            'status': 'completed',
            'started_at': '2026-06-01T00:00:00Z',
            'completed_at': '2026-06-01T00:10:00Z',
            'updated_at': '2026-06-01T00:10:00Z',
          },
          {
            'lesson_id': 'lesson_b',
            'path_id': 'path_1',
            'status': 'in_progress',
            'started_at': '2026-06-02T00:00:00Z',
            'completed_at': null,
            'updated_at': '2026-06-02T00:00:00Z',
          },
        ],
        'fetched_at': '2026-06-08T12:00:00Z',
      };
      final repo = ProgressRepository(fake);
      final bundle = await repo.getChildProgress(7);
      expect(bundle.childId, 7);
      expect(bundle.lessons.length, 2);
      expect(bundle.forLesson('lesson_a')!.status, ProgressStatus.completed);
      expect(bundle.forLesson('lesson_b')!.status, ProgressStatus.inProgress);
      expect(bundle.forLesson('lesson_missing'), isNull);
      expect(bundle.completedCount, 1);
    });

    test('patchLessonProgress() returns LessonProgress', () async {
      final fake = _FakeTgClient();
      fake.lessonProgressJson = {
        'lesson_id': 'lesson_x',
        'path_id': 'path_x',
        'status': 'completed',
        'started_at': '2026-06-08T00:00:00Z',
        'completed_at': '2026-06-08T00:05:00Z',
        'updated_at': '2026-06-08T00:05:00Z',
      };
      final repo = ProgressRepository(fake);
      final lp = await repo.patchLessonProgress(
        lessonId: 'lesson_x',
        status: ProgressStatus.completed,
      );
      expect(lp.status, ProgressStatus.completed);
      expect(lp.lessonId, 'lesson_x');
    });
  });

  group('Progress models', () {
    test('progressStatusToWire encodes all 3 statuses', () {
      expect(progressStatusToWire(ProgressStatus.notStarted), 'not_started');
      expect(progressStatusToWire(ProgressStatus.inProgress), 'in_progress');
      expect(progressStatusToWire(ProgressStatus.completed), 'completed');
    });

    test('progressStatusLabel round-trips', () {
      expect(progressStatusLabel(ProgressStatus.notStarted), 'لم يبدأ');
      expect(progressStatusLabel(ProgressStatus.inProgress), 'قيد التنفيذ');
      expect(progressStatusLabel(ProgressStatus.completed), 'مكتمل');
    });
  });

  group('Progress widgets', () {
    // Helper to scroll to a widget in a ListView
    Future<void> scrollToFind(WidgetTester tester, String text) async {
      final visibleChip = find.text('ولد');
      if (visibleChip.evaluate().isNotEmpty) {
        await tester.drag(find.byType(ListView), const Offset(0, -500));
        await tester.pumpAndSettle();
      }
      if (find.text(text).evaluate().isEmpty) {
        await tester.drag(find.byType(ListView), const Offset(0, -500));
        await tester.pumpAndSettle();
      }
    }

    testWidgets('PathDetailScreen shows progress bar when child active',
        (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.pathDetailJson = {
        'path': _pathJson(),
        'lessons': [
          _lessonJson(id: 'lesson_4-6_islamic_parenting_adab_01', order: 1),
          _lessonJson(id: 'lesson_4-6_islamic_parenting_adab_02', order: 2),
        ],
      };
      fake.childProgressJson = {
        'child_id': 1,
        'lessons': [
          {
            'lesson_id': 'lesson_4-6_islamic_parenting_adab_01',
            'path_id': 'path_4-6_islamic_parenting_adab',
            'status': 'completed',
            'started_at': '2026-06-08T00:00:00Z',
            'completed_at': '2026-06-08T00:05:00Z',
            'updated_at': '2026-06-08T00:05:00Z',
          },
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
      await tester.pumpAndSettle();

      // Progress strip present
      expect(find.text('تقدّم المسار'), findsOneWidget);
      // 1 / 2 (50%)
      expect(find.textContaining('1 / 2'), findsOneWidget);
      // First lesson tile shows "مكتمل" label
      expect(find.text('مكتمل'), findsWidgets);
    });

    testWidgets('LessonScreen shows mark-complete button + status chip',
        (WidgetTester tester) async {
      final fake = _FakeTgClient();
      fake.lessonJson = _lessonJson(
        id: 'lesson_4-6_islamic_parenting_adab_01',
        order: 1,
      );
      fake.childProgressJson = {
        'child_id': 1,
        'lessons': [],
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
            home: LessonScreen(
              lessonId: 'lesson_4-6_islamic_parenting_adab_01',
              ageGroup: '4-6',
              childId: 1,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.pumpAndSettle();

      // Check status chip "لم يبدأ بعد" BEFORE scrolling
      expect(find.text('لم يبدأ بعد'), findsOneWidget);

      // Scroll to reveal the mark-complete button at the bottom
      await scrollToFind(tester, 'أتممت');

      // Mark complete button present
      expect(find.text('أتممت هذا الدرس'), findsOneWidget);
    });
  });
}

// ── Fake TgClient (Phase 5 subset) ────────────────────────────────────────

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? createChildJson;
  Map<String, dynamic>? childProgressJson;
  Map<String, dynamic>? lessonProgressJson;
  Map<String, dynamic>? lessonJson;
  Map<String, dynamic>? pathDetailJson;

  @override
  Future<Map<String, dynamic>> createChild({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
  }) async =>
      createChildJson ?? {};

  @override
  Future<Map<String, dynamic>> getChildProgress(
    int childId, {
    String? pathId,
  }) async =>
      childProgressJson ?? {'child_id': childId, 'lessons': []};

  @override
  Future<Map<String, dynamic>> patchLessonProgress({
    required String lessonId,
    required String status,
  }) async =>
      lessonProgressJson ??
      {
        'lesson_id': lessonId,
        'path_id': 'path_x',
        'status': status,
        'started_at': null,
        'completed_at': null,
        'updated_at': '2026-06-08T12:00:00Z',
      };

  @override
  Future<Map<String, dynamic>> getPathDetail(
    String pathId, {
    bool includeLessons = false,
  }) async =>
      pathDetailJson ?? {'path': _pathJson(id: pathId), 'lessons': []};

  @override
  Future<Map<String, dynamic>> getLesson(String lessonId) async =>
      lessonJson ?? _lessonJson(id: lessonId, order: 1);
}

// ── JSON fixtures ────────────────────────────────────────────────────────

Map<String, dynamic> _pathJson({String id = 'path_4-6_islamic_parenting_adab'}) {
  return {
    'id': id,
    'title': 'تأسيس الآداب الإسلامية والضمير الأخلاقي (4-6 سنوات)',
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
}) {
  return {
    'id': id,
    'path_id': 'path_4-6_islamic_parenting_adab',
    'title': 'الرفق: قيمة تربوية قبل أسلوب',
    'age_group': '4-6',
    'domain': 'islamic_parenting',
    'unit_ids': ['0bd76d3c-548a-46ed-b17b-78874741662a'],
    'summary': 'في مرحلة ما قبل العمليات يبدأ الطفل بتمييز الصوت الحنون.',
    'try_this': 'هذا الأسبوع: اختر وقتاً يومياً واحداً تتحدث فيه مع طفلك بصوت هادئ.',
    'order': order,
    'estimated_minutes': 5,
    'reflection_prompts': [],
    'warning_flags': [],
    'is_published': true,
    'version': '1.0.0',
  };
}
