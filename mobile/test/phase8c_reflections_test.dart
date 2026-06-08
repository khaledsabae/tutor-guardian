// Phase 8-C tests — reflection notes (local-only).
//
// Strategy:
//   1. Pure-Dart tests for ReflectionStorage (round-trip).
//   2. Provider tests for save/upsert/delete.
//   3. Widget tests for the card and the badge.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/reflections/data/reflection_storage.dart';
import 'package:almorabbi/features/reflections/providers/reflections_providers.dart';
import 'package:almorabbi/features/reflections/widgets/reflection_note_badge.dart';
import 'package:almorabbi/features/reflections/widgets/reflection_note_card.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  // ── ReflectionStorage (pure-Dart round-trip) ─────────────────────────

  group('ReflectionStorage', () {
    test('loadAll returns empty map when nothing stored', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = ReflectionStorage(prefs);
      expect(storage.loadAll(), isEmpty);
    });

    test('upsert + loadAll round-trip preserves text + timestamps',
        () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = ReflectionStorage(prefs);
      final entry = ReflectionEntry(
        lessonId: 'lesson_a',
        text: 'كان الدرس رائعاً',
        createdAt: DateTime.utc(2026, 6, 8, 10),
        updatedAt: DateTime.utc(2026, 6, 8, 10),
      );
      await storage.upsert(entry);

      final loaded = storage.loadAll();
      expect(loaded['lesson_a']?.text, 'كان الدرس رائعاً');
      expect(loaded['lesson_a']?.createdAt, DateTime.utc(2026, 6, 8, 10));
    });

    test('upsert overwrites the existing entry', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = ReflectionStorage(prefs);
      await storage.upsert(ReflectionEntry(
        lessonId: 'l',
        text: 'v1',
        createdAt: DateTime.utc(2026, 1, 1),
        updatedAt: DateTime.utc(2026, 1, 1),
      ));
      await storage.upsert(ReflectionEntry(
        lessonId: 'l',
        text: 'v2',
        createdAt: DateTime.utc(2026, 1, 1),
        updatedAt: DateTime.utc(2026, 1, 2),
      ));
      expect(storage.loadAll()['l']?.text, 'v2');
    });

    test('delete removes the entry', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = ReflectionStorage(prefs);
      await storage.upsert(ReflectionEntry(
        lessonId: 'l',
        text: 'x',
        createdAt: DateTime.utc(2026, 1, 1),
        updatedAt: DateTime.utc(2026, 1, 1),
      ));
      await storage.delete('l');
      expect(storage.loadAll(), isEmpty);
    });

    test('delete is a no-op when the key is absent', () async {
      final prefs = await SharedPreferences.getInstance();
      final storage = ReflectionStorage(prefs);
      await storage.delete('not_there'); // no throw
    });

    test('corrupted JSON does not crash loadAll', () async {
      final prefs = await SharedPreferences.getInstance();
      // Manually inject garbage
      await prefs.setString('tg.reflections.v1', '{not valid json');
      final storage = ReflectionStorage(prefs);
      expect(storage.loadAll(), isEmpty);
    });
  });

  // ── Provider: save + delete ──────────────────────────────────────────

  group('reflectionsMapProvider', () {
    test('save() inserts a new entry', () async {
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);

      final entry = await container
          .read(reflectionsMapProvider.notifier)
          .save('lesson_a', 'الملاحظة الأولى');

      expect(entry.text, 'الملاحظة الأولى');
      expect(container.read(reflectionsMapProvider).value?['lesson_a']?.text,
          'الملاحظة الأولى');
    });

    test('save() on existing lesson preserves createdAt', () async {
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);

      final first = await container
          .read(reflectionsMapProvider.notifier)
          .save('l', 'v1');
      final firstCreated = first.createdAt;

      // Wait a tick so updatedAt differs.
      await Future.delayed(const Duration(milliseconds: 10));
      final second = await container
          .read(reflectionsMapProvider.notifier)
          .save('l', 'v2');

      expect(second.text, 'v2');
      expect(second.createdAt, firstCreated); // unchanged
      expect(second.updatedAt.isAfter(firstUpdatedAt(first)), isTrue);
    });

    test('delete() removes the entry', () async {
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ],
      );
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      await container
          .read(reflectionsMapProvider.notifier)
          .save('l', 'x');
      await container
          .read(reflectionsMapProvider.notifier)
          .delete('l');
      expect(container.read(lessonReflectionProvider('l')), isNull);
    });
  });

  // ── Widget: ReflectionNoteCard ──────────────────────────────────────

  testWidgets('ReflectionNoteCard shows empty state when no note',
      (tester) async {
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: Scaffold(body: ReflectionNoteCard(lessonId: 'l')),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('ملاحظاتي'), findsOneWidget);
    expect(find.text('أضف ملاحظة'), findsOneWidget);
  });

  testWidgets('ReflectionNoteCard shows the saved note + edit/delete',
      (tester) async {
    final prefs = await SharedPreferences.getInstance();
    final storage = ReflectionStorage(prefs);
    await storage.upsert(ReflectionEntry(
      lessonId: 'l',
      text: 'كان الدرس رائعاً',
      createdAt: DateTime.utc(2026, 6, 8),
      updatedAt: DateTime.utc(2026, 6, 8),
    ));

    final container = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: Scaffold(body: ReflectionNoteCard(lessonId: 'l')),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('كان الدرس رائعاً'), findsOneWidget);
    expect(find.text('تعديل'), findsOneWidget);
    expect(find.text('حذف'), findsOneWidget);
  });

  // ── Widget: ReflectionNoteBadge ─────────────────────────────────────

  testWidgets('ReflectionNoteBadge is invisible when no note',
      (tester) async {
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: Scaffold(body: ReflectionNoteBadge(lessonId: 'l')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('ملاحظة'), findsNothing);
  });

  testWidgets('ReflectionNoteBadge shows "ملاحظة" when a note exists',
      (tester) async {
    final prefs = await SharedPreferences.getInstance();
    final storage = ReflectionStorage(prefs);
    await storage.upsert(ReflectionEntry(
      lessonId: 'l',
      text: 'x',
      createdAt: DateTime.utc(2026, 6, 8),
      updatedAt: DateTime.utc(2026, 6, 8),
    ));

    final container = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: Scaffold(body: ReflectionNoteBadge(lessonId: 'l')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('ملاحظة'), findsOneWidget);
  });
}

// Local helper for the timestamp comparison.
DateTime firstUpdatedAt(ReflectionEntry e) => e.updatedAt;
