// Phase 7 widget + repository tests — settings flow.
//
// Strategy:
//   1. Pure-Dart tests for SettingsRepository wrappers.
//   2. Widget tests for SettingsScreen, EditChildScreen, ResetDialog.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/data/settings_repository.dart';
import 'package:almorabbi/features/program/screens/edit_child_screen.dart';
import 'package:almorabbi/features/program/screens/settings_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  // ── SettingsRepository (pure-Dart) ──────────────────────────────────────

  group('SettingsRepository', () {
    test('listChildren decodes the envelope', () async {
      final fake = _FakeTgClient();
      fake.listChildrenJson = {
        'device_id': 'dev-1',
        'count': 1,
        'children': [
          {
            'id': 5,
            'name': 'سارة',
            'age_group': '4-6',
            'gender': 'female',
            'avatar_emoji': '👧',
            'created_at': '2026-06-08T10:00:00',
            'updated_at': '2026-06-08T10:00:00',
          }
        ],
      };
      final repo = SettingsRepository(fake);
      final envelope = await repo.listChildren();
      expect(envelope.count, 1);
      expect(envelope.children.first.name, 'سارة');
      expect(envelope.children.first.ageGroup, '4-6');
    });

    test('updateChild decodes the child response', () async {
      final fake = _FakeTgClient();
      fake.updateChildJson = {
        'id': 5,
        'name': 'ليلى',
        'age_group': '7-9',
        'gender': null,
        'avatar_emoji': '🧒',
        'created_at': '2026-06-08T10:00:00',
        'updated_at': '2026-06-08T11:00:00',
      };
      final repo = SettingsRepository(fake);
      final child = await repo.updateChild(
        childId: 5,
        name: 'ليلى',
        ageGroup: '7-9',
        avatarEmoji: '🧒',
      );
      expect(child.name, 'ليلى');
      expect(child.ageGroup, '7-9');
    });

    test('resetProgress returns the deleted count', () async {
      final fake = _FakeTgClient();
      fake.resetProgressJson = {
        'child_id': 5,
        'device_id': 'dev-1',
        'deleted': 7,
        'reset_at': '2026-06-08T11:00:00Z',
      };
      final repo = SettingsRepository(fake);
      final n = await repo.resetProgress(5);
      expect(n, 7);
    });
  });

  // ── SettingsScreen renders ────────────────────────────────────────────

  group('SettingsScreen', () {
    testWidgets('renders child header + settings rows', (tester) async {
      final fake = _FakeTgClient();
      fake.listChildrenJson = {
        'count': 1,
        'children': [_childJson(id: 5, name: 'سارة', ageGroup: '4-6')],
      };
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.setActiveChild(id: 5, name: 'سارة', ageGroup: '4-6');

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
          child: const MaterialApp(home: SettingsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('الإعدادات'), findsOneWidget);
      expect(find.text('سارة'), findsOneWidget);
      expect(find.text('تعديل معلومات الطفل'), findsOneWidget);
      expect(find.text('إعادة تعيين التقدّم'), findsOneWidget);
      expect(find.text('سياسة الخصوصية'), findsOneWidget);
    });

    testWidgets('error state with retry', (tester) async {
      final fake = _FakeTgClient();
      fake.listChildrenJson = null; // forces throw
      fake.throwOnList = true;

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
          child: const MaterialApp(home: SettingsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('إعادة المحاولة'), findsOneWidget);
    });
  });

  // ── EditChildScreen ───────────────────────────────────────────────────

  group('EditChildScreen', () {
    testWidgets('pre-fills fields from the child argument', (tester) async {
      final fake = _FakeTgClient();
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tgClientProvider.overrideWithValue(fake),
            sharedPreferencesProvider.overrideWith((_) async => prefs),
          ],
          child: MaterialApp(
            home: EditChildScreen(
              child: ChildProfile.fromJson(_childJson(
                id: 5,
                name: 'سارة',
                ageGroup: '4-6',
              )),
            ),
          ),
        ),
      );
      await tester.pump();

      // The name field should have the existing name.
      final nameField = find.widgetWithText(TextFormField, 'سارة');
      expect(nameField, findsOneWidget);

      // Age chips: 4-6 should be selected.
      final ageChip = find.widgetWithText(ChoiceChip, '4–6 سنوات');
      expect(ageChip, findsOneWidget);

      // Save button.
      expect(find.text('حفظ'), findsOneWidget);
    });

    testWidgets('rejects empty name', (tester) async {
      final fake = _FakeTgClient();
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tgClientProvider.overrideWithValue(fake),
            sharedPreferencesProvider.overrideWith((_) async => prefs),
          ],
          child: MaterialApp(
            home: EditChildScreen(
              child: ChildProfile.fromJson(_childJson(
                id: 5,
                name: 'سارة',
                ageGroup: '4-6',
              )),
            ),
          ),
        ),
      );
      await tester.pump();

      // Clear the name field
      await tester.enterText(
          find.widgetWithText(TextFormField, 'سارة'), '');
      await tester.tap(find.text('حفظ'));
      await tester.pump();

      expect(find.text('الاسم مطلوب'), findsOneWidget);
    });
  });
}

// ── Fixtures ─────────────────────────────────────────────────────────────

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? listChildrenJson;
  Map<String, dynamic>? updateChildJson;
  Map<String, dynamic>? resetProgressJson;
  bool throwOnList = false;

  @override
  Future<Map<String, dynamic>> listChildren() async {
    if (throwOnList) {
      throw Exception('network down');
    }
    return listChildrenJson ?? {'count': 0, 'children': []};
  }

  @override
  Future<Map<String, dynamic>> updateChild({
    required int childId,
    String? name,
    String? ageGroup,
    String? gender,
    String? avatarEmoji,
  }) async {
    return updateChildJson ?? _childJson(id: childId, name: name ?? '?');
  }

  @override
  Future<Map<String, dynamic>> resetChildProgress(int childId) async {
    return resetProgressJson ??
        {'child_id': childId, 'deleted': 0, 'reset_at': '2026-06-08T11:00:00Z'};
  }
}

Map<String, dynamic> _childJson({
  required int id,
  String name = 'سارة',
  String ageGroup = '4-6',
  String? gender,
  String? avatarEmoji,
}) {
  return {
    'id': id,
    'name': name,
    'age_group': ageGroup,
    'gender': gender,
    'avatar_emoji': avatarEmoji,
    'created_at': '2026-06-08T10:00:00',
    'updated_at': '2026-06-08T10:00:00',
  };
}
