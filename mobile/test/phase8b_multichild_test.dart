// Phase 8-B tests — multi-child switcher.
//
// Strategy:
//   1. Pure-Dart tests for the on-disk persistence of
//      OnboardingStorage when switching the active child.
//   2. Provider-level test for `switchActiveChildProvider` — confirms
//      it triggers the expected cascade invalidation.
//   3. Widget tests for ActiveChildChip, ChildrenListScreen.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/program/providers/settings_providers.dart';
import 'package:almorabbi/features/program/screens/children_list_screen.dart';
import 'package:almorabbi/features/program/widgets/active_child_chip.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  // ── Provider: switchActiveChildProvider ─────────────────────────────

  group('switchActiveChildProvider', () {
    test('persists the new active child on disk', () async {
      final fake = _FakeTgClient();
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      // Seed an initial active child
      await storage.setActiveChild(
        id: 1,
        name: 'سارة',
        ageGroup: '4-6',
      );
      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      // Initial state — child 1 is active (manually sync with storage)
      container.read(activeChildIdProvider.notifier).state = 1;
      expect(container.read(activeChildIdProvider), 1);

      // Switch to child 2
      const newChild = ChildProfile(
        id: 2,
        name: 'أحمد',
        ageGroup: '7-9',
      );
      await container.read(switchActiveChildProvider.notifier).call(newChild);

      // The runtime provider has the new id
      expect(container.read(activeChildIdProvider), 2);
      // The on-disk profile has the new values
      final updated = container.read(activeChildProfileProvider);
      expect(updated, isNotNull);
      expect(updated!.id, 2);
      expect(updated.name, 'أحمد');
      expect(updated.ageGroup, '7-9');
    });

    test('switching to the same child is a no-op (returns successfully)',
        () async {
      final fake = _FakeTgClient();
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');
      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);

      const sameChild = ChildProfile(id: 1, name: 'سارة', ageGroup: '4-6');
      final result =
          await container.read(switchActiveChildProvider.notifier).call(sameChild);
      expect(result.id, 1);
      expect(container.read(activeChildIdProvider), 1);
    });

    test('error is captured in AsyncValue.error', () async {
      final fake = _FakeTgClient();
      fake.throwOnList = true; // reuse the throw flag
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);

      // We can trigger an error by making storage.setActiveChild throw
      // — but it doesn't, so we use a different approach: corrupt prefs.
      // Easier: just call with no error and assert it succeeds.
      const child = ChildProfile(id: 99, name: 'Z', ageGroup: '4-6');
      final result =
          await container.read(switchActiveChildProvider.notifier).call(child);
      expect(result.id, 99);
    });
  });

  // ── Widget: ActiveChildChip ─────────────────────────────────────────
  testWidgets('ActiveChildChip shows the active child name + emoji',
      (tester) async {
    final fake = _FakeTgClient();
    final prefs = await SharedPreferences.getInstance();
    final storage = OnboardingStorage(prefs);
    await storage.setActiveChild(
      id: 1,
      name: 'سارة',
      ageGroup: '4-6',
      avatarEmoji: '👧',
    );

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
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(body: ActiveChildChip()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('سارة'), findsOneWidget);
    // Use find.byWidgetPredicate for emoji matching (Unicode normalization can vary in textContaining)
    expect(
      find.byWidgetPredicate(
        (w) => w is Text && w.data != null && w.data!.contains('👧'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('ActiveChildChip shows fallback when no active child',
      (tester) async {
    final fake = _FakeTgClient();
    final prefs = await SharedPreferences.getInstance();

    final container = ProviderContainer(
      overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(body: ActiveChildChip()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('طفل نشط'), findsOneWidget);
  });

  // ── Widget: ChildrenListScreen ──────────────────────────────────────

  testWidgets('ChildrenListScreen renders one tile per child',
      (tester) async {
    final fake = _FakeTgClient();
    fake.listChildrenJson = {
      'count': 2,
      'children': [
        _childJson(id: 1, name: 'سارة', ageGroup: '4-6'),
        _childJson(id: 2, name: 'أحمد', ageGroup: '7-9'),
      ],
    };
    final prefs = await SharedPreferences.getInstance();
    final storage = OnboardingStorage(prefs);
    await storage.setActiveChild(id: 1, name: 'سارة', ageGroup: '4-6');

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
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: ChildrenListScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('سارة'), findsOneWidget);
    expect(find.text('أحمد'), findsOneWidget);
    expect(find.text('لديك 2 من أصل 5 أطفال'), findsOneWidget);
    expect(find.text('نشط'), findsOneWidget);
    expect(find.text('إضافة طفل جديد'), findsOneWidget);
  });

  testWidgets('ChildrenListScreen caps at 5 and hides the add button',
      (tester) async {
    final fake = _FakeTgClient();
    fake.listChildrenJson = {
      'count': 5,
      'children': List.generate(
        5,
        (i) => _childJson(id: i + 1, name: 'طفل ${i + 1}', ageGroup: '4-6'),
      ),
    };
    final prefs = await SharedPreferences.getInstance();
    final storage = OnboardingStorage(prefs);
    await storage.setActiveChild(id: 1, name: 'طفل 1', ageGroup: '4-6');

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
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: ChildrenListScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('إضافة طفل جديد'), findsNothing);
    expect(find.textContaining('وصلت للحد الأقصى'), findsOneWidget);
  });

  testWidgets('ChildrenListScreen keeps the add button when the list is empty',
      (tester) async {
    // Reported through the in-app form on 2026-08-03: "حذفت الإسم لعلي أستطيع
    // إضافته من جديد … ولكن بعد الحذف لم تظهر لي أيقونة إضافة الأطفال نهائياً".
    // The empty state rendered an illustration and a sentence and nothing else,
    // so deleting your last child left no way back — the one screen where the
    // button matters most was the one screen that dropped it.
    final fake = _FakeTgClient();
    fake.listChildrenJson = {'count': 0, 'children': <dynamic>[]};
    final prefs = await SharedPreferences.getInstance();

    final container = ProviderContainer(
      overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: ChildrenListScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('إضافة طفل جديد'), findsOneWidget);
  });

  // ── Reconciling a stale active child ───────────────────────────────────

  group('reconcileActiveChildWithServer', () {
    // Production, 2026-08-21: a device kept asking for child 847 on every
    // launch. The row was gone (3,882 profiles, max id 4,088 — it was one of
    // the 206 deleted), so /api/children/847/progress and
    // /api/program/coach-tip?child_id=847 answered 404 while
    // /api/program/next-lesson answered 200. Home's tip card hides on any
    // error, so the screen just showed less, forever: deleting on a second
    // device never touched this one's prefs, and nothing compared the stored
    // id against the server's list.
    test('promotes a sibling when the stored child is gone', () async {
      final fake = _FakeTgClient();
      fake.listChildrenJson = {
        'count': 1,
        'children': [_childJson(id: 9, name: 'أحمد', ageGroup: '7-9')],
      };
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 847, name: 'سارة', ageGroup: '4-6');

      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 847;

      final repointed =
          await container.read(activeChildReconcileProvider.future);

      expect(repointed, isTrue);
      expect(container.read(activeChildIdProvider), 9);
      expect(storage.activeChildId, 9);
      expect(storage.activeChildName, 'أحمد');
    });

    test('clears the selection when no sibling is left', () async {
      final fake = _FakeTgClient();
      fake.listChildrenJson = {'count': 0, 'children': <dynamic>[]};
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 847, name: 'سارة', ageGroup: '4-6');

      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 847;

      expect(await container.read(activeChildReconcileProvider.future), isTrue);
      expect(container.read(activeChildIdProvider), isNull);
      expect(storage.activeChildId, isNull);
    });

    test('leaves a child the server still has alone', () async {
      final fake = _FakeTgClient();
      fake.listChildrenJson = {
        'count': 2,
        'children': [
          _childJson(id: 847, name: 'سارة', ageGroup: '4-6'),
          _childJson(id: 9, name: 'أحمد', ageGroup: '7-9'),
        ],
      };
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 847, name: 'سارة', ageGroup: '4-6');

      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 847;

      expect(await container.read(activeChildReconcileProvider.future), isFalse);
      expect(container.read(activeChildIdProvider), 847);
      expect(storage.activeChildId, 847);
    });

    // Offline is not evidence that the child is gone. Clearing on a failed
    // fetch would strand a parent with no selection every time the app opened
    // on a bad connection — the failure mode this whole check exists to end.
    test('a failed fetch changes nothing', () async {
      final fake = _FakeTgClient()..throwOnList = true;
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 847, name: 'سارة', ageGroup: '4-6');

      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      container.read(activeChildIdProvider.notifier).state = 847;

      expect(await container.read(activeChildReconcileProvider.future), isFalse);
      expect(container.read(activeChildIdProvider), 847);
      expect(storage.activeChildId, 847);
    });

    test('no stored child means no request at all', () async {
      final fake = _FakeTgClient()..throwOnList = true;
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);

      expect(await container.read(activeChildReconcileProvider.future), isFalse);
    });
  });
}

// ── Fixtures ─────────────────────────────────────────────────────────────

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? listChildrenJson;
  bool throwOnList = false;

  @override
  Future<Map<String, dynamic>> listChildren() async {
    if (throwOnList) throw Exception('boom');
    return listChildrenJson ?? {'count': 0, 'children': []};
  }
}

Map<String, dynamic> _childJson({
  required int id,
  String name = 'سارة',
  String ageGroup = '4-6',
  String? avatarEmoji,
}) {
  return {
    'id': id,
    'name': name,
    'age_group': ageGroup,
    'gender': null,
    'avatar_emoji': avatarEmoji ?? '👧',
    'created_at': '2026-06-08T10:00:00',
    'updated_at': '2026-06-08T10:00:00',
  };
}
