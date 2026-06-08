// Phase 6 widget + unit tests — onboarding flow + streak chip.
//
// Strategy:
//   1. Pure-Dart tests for OnboardingStorage (no widgets).
//   2. Widget tests for OnboardingScreen + AvatarPickerSheet that
//      pump the real screens and assert the expected fields render.
//   3. Widget tests for StreakChip and DailyTipCard.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/onboarding/screens/avatar_picker_sheet.dart';
import 'package:almorabbi/features/onboarding/screens/onboarding_screen.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/program/screens/path_detail_screen.dart';
import 'package:almorabbi/features/program/widgets/daily_tip_card.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  // ── OnboardingStorage (pure-Dart) ──────────────────────────────────────

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('OnboardingStorage', () {
    test('starts in not-completed state', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      expect(storage.onboardingCompleted, isFalse);
      expect(storage.activeChildId, isNull);
      expect(storage.activeChildName, isNull);
    });

    test('markOnboardingCompleted persists across instances', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage1 = OnboardingStorage(prefs);
      await storage1.markOnboardingCompleted();
      await storage1.setActiveChild(
        id: 42,
        name: 'سارة',
        ageGroup: '4-6',
      );

      // Recreate from the same backing prefs.
      final storage2 = OnboardingStorage(prefs);
      expect(storage2.onboardingCompleted, isTrue);
      expect(storage2.activeChildId, 42);
      expect(storage2.activeChildName, 'سارة');
      expect(storage2.activeChildAgeGroup, '4-6');
    });

    test('clearActiveChild wipes only the child fields', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.markOnboardingCompleted();
      await storage.setActiveChild(id: 7, name: 'X', ageGroup: '7-9');
      await storage.clearActiveChild();
      expect(storage.activeChildId, isNull);
      expect(storage.onboardingCompleted, isTrue); // unchanged
    });
  });

  // ── Active child profile provider ─────────────────────────────────────

  group('activeChildProfileProvider', () {
    test('returns null when no child set', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      // Trigger build
      await container.read(sharedPreferencesProvider.future);
      expect(container.read(activeChildProfileProvider), isNull);
    });

    test('returns the profile when one is set', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 9, name: 'ليلى', ageGroup: '4-6');
      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      final p = container.read(activeChildProfileProvider);
      expect(p, isNotNull);
      expect(p!.id, 9);
      expect(p.name, 'ليلى');
      expect(p.ageGroup, '4-6');
    });
  });

  // ── StreakChip (pure widget) ───────────────────────────────────────────

  group('StreakChip', () {
    testWidgets('shows the day count when streak > 0', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: StreakChip(streakDays: 5)),
      ));
      expect(find.text('5'), findsOneWidget);
      expect(find.textContaining('متتالية'), findsOneWidget);
      expect(find.text('🔥'), findsOneWidget);
    });

    testWidgets('shows the nudge when streak = 0', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: StreakChip(streakDays: 0)),
      ));
      expect(find.textContaining('ابدأ سلسلتك'), findsOneWidget);
      // Day count should NOT be rendered when streak is zero.
      expect(find.text('0'), findsNothing);
    });

    testWidgets('singular vs plural Arabic label', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: StreakChip(streakDays: 1)),
      ));
      expect(find.text('1'), findsOneWidget);
      expect(find.textContaining('يوم متتالي'), findsOneWidget);
      // (no "متتالية" because singular)
      expect(find.textContaining('متتالية'), findsNothing);
    });
  });

  // ── Onboarding screen render ───────────────────────────────────────────

  group('OnboardingScreen', () {
    testWidgets('renders all required fields', (tester) async {
      // Override the client with a fake that returns a child.
      final fake = _FakeTgClient();
      fake.createChildJson = {
        'id': 1,
        'name': 'سارة',
        'age_group': '4-6',
        'gender': null,
        'avatar_emoji': '👧',
        'created_at': '2026-06-08T12:00:00',
        'updated_at': '2026-06-08T12:00:00',
      };

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tgClientProvider.overrideWithValue(fake),
            sharedPreferencesProvider.overrideWith((_) async => prefs),
          ],
          child: const MaterialApp(home: OnboardingScreen()),
        ),
      );
      await tester.pump();

      expect(find.text('اسم طفلك'), findsOneWidget);
      expect(find.text('المرحلة العمرية'), findsOneWidget);
      expect(find.text('صورة الطفل (اختياري)'), findsOneWidget);
      expect(find.text('ابدأ الرحلة'), findsOneWidget);
      // Age chips render
      expect(find.text('4–6 سنوات'), findsOneWidget);
      expect(find.text('0–3 سنوات'), findsOneWidget);
    });

    testWidgets('shows validation error when name is empty', (tester) async {
      final fake = _FakeTgClient();
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tgClientProvider.overrideWithValue(fake),
            sharedPreferencesProvider.overrideWith((_) async => prefs),
          ],
          child: const MaterialApp(home: OnboardingScreen()),
        ),
      );
      await tester.pump();

      // Tap submit without entering name or age group
      await tester.tap(find.text('ابدأ الرحلة'));
      await tester.pump();

      // Form validation error
      expect(find.text('الاسم مطلوب'), findsOneWidget);
    });
  });

  // ── Avatar picker sheet ────────────────────────────────────────────────

  testWidgets('AvatarPickerSheet returns the picked emoji', (tester) async {
    String? picked;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => Center(
              child: ElevatedButton(
                onPressed: () async {
                  picked = await showModalBottomSheet<String>(
                    context: context,
                    builder: (_) => const AvatarPickerSheet(initial: null),
                  );
                },
                child: const Text('open'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    // Tap the first emoji in the grid (👧)
    await tester.tap(find.text('👧'));
    await tester.pumpAndSettle();
    expect(picked, '👧');
  });

  // ── DailyTipCard hides when no child ───────────────────────────────────

  testWidgets('DailyTipCard hides when no active child', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final fake = _FakeTgClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
        child: const MaterialApp(
          home: Scaffold(body: DailyTipCard()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byType(DailyTipCard), findsOneWidget);
    expect(find.textContaining('نصيحة'), findsNothing);
  });

  // ── StreakChip rendered via path detail screen ─────────────────────────

  testWidgets('PathDetailScreen header shows streak chip when bundle has streak',
      (tester) async {
    final fake = _FakeTgClient();
    fake.pathDetailJson = {
      'path': _pathJson(),
      'lessons': [
        _lessonJson(id: 'lesson_4-6_islamic_parenting_adab_01', order: 1),
      ],
    };
    fake.childProgressJson = {
      'child_id': 1,
      'lessons': [],
      'streak_days': 7,
      'last_completed_at': '2026-06-08T10:00:00Z',
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
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);
    container.read(activeChildIdProvider.notifier).state = 1;

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

    // Streak chip shows "7 أيام متتالية"
    expect(find.text('7'), findsOneWidget);
    expect(find.textContaining('متتالية'), findsOneWidget);
  });
}

// ── Fixtures ─────────────────────────────────────────────────────────────

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? createChildJson;
  Map<String, dynamic>? childProgressJson;
  Map<String, dynamic>? pathDetailJson;
  Map<String, dynamic>? dailyTipJson;

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
      childProgressJson ??
      {'child_id': childId, 'lessons': [], 'streak_days': 0};

  @override
  Future<Map<String, dynamic>> getPathDetail(
    String pathId, {
    bool includeLessons = false,
  }) async =>
      pathDetailJson ?? {'path': _pathJson(id: pathId), 'lessons': []};

  @override
  Future<Map<String, dynamic>> getDailyTip({
    required String ageGroup,
    String? timeOfDay,
  }) async =>
      dailyTipJson ??
      {
        'id': 'tip_4-6_001',
        'age_group': ageGroup,
        'domain': 'islamic_parenting',
        'text': 'ابدأ يومك بابتسامة.',
        'time_of_day': 'morning',
      };
}

Map<String, dynamic> _pathJson({String id = 'path_4-6_islamic_parenting_adab'}) {
  return {
    'id': id,
    'title': 'تأسيس الآداب الإسلامية',
    'age_group': '4-6',
    'domain': 'islamic_parenting',
    'description': 'رحلة تربوية لمدة 14 يوماً.',
    'lesson_ids': ['lesson_4-6_islamic_parenting_adab_01'],
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
    'title': 'الرفق: قيمة تربوية',
    'age_group': '4-6',
    'domain': 'islamic_parenting',
    'unit_ids': ['0bd76d3c-548a-46ed-b17b-78874741662a'],
    'summary': 'في مرحلة ما قبل العمليات.',
    'try_this': 'هذا الأسبوع: اختر وقتاً.',
    'order': order,
    'estimated_minutes': 5,
    'reflection_prompts': [],
    'warning_flags': [],
    'is_published': true,
    'version': '1.0.0',
  };
}
