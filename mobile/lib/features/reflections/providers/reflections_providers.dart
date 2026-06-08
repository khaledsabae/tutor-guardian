/// Phase 8-C providers — reflection notes (local-only).
///
/// Hierarchy:
///   sharedPreferencesProvider        (existing, in onboarding_providers)
///       │
///       ▼
///   reflectionStorageProvider       (Provider<ReflectionStorage>)
///       │
///       ├── reflectionsMapProvider  (AsyncNotifier<Map<lessonId, entry>>)
///       │     │
///       │     ▼
///       │     lessonReflectionProvider  (Provider.family<ReflectionEntry?,
///       │                                lessonId>)
///       │
///       ├── saveReflectionProvider   (AsyncNotifier — upsert)
///       └── deleteReflectionProvider (AsyncNotifier — delete)
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../onboarding/providers/onboarding_providers.dart';
import '../data/reflection_storage.dart';

final reflectionStorageProvider = Provider<ReflectionStorage>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).requireValue;
  return ReflectionStorage(prefs);
});

/// In-memory map of all reflections, keyed by lesson_id.
class ReflectionsMapNotifier
    extends AsyncNotifier<Map<String, ReflectionEntry>> {
  @override
  Future<Map<String, ReflectionEntry>> build() async {
    final storage = ref.read(reflectionStorageProvider);
    return storage.loadAll();
  }

  Future<ReflectionEntry> save(
    String lessonId,
    String text,
  ) async {
    final storage = ref.read(reflectionStorageProvider);
    final now = DateTime.now();
    final existing = state.value?[lessonId];
    final entry = existing == null
        ? ReflectionEntry(
            lessonId: lessonId,
            text: text,
            createdAt: now,
            updatedAt: now,
          )
        : existing.copyWith(text: text, updatedAt: now);
    await storage.upsert(entry);
    final next = {...?state.value, entry.lessonId: entry};
    state = AsyncValue.data(next);
    return entry;
  }

  Future<void> delete(String lessonId) async {
    final storage = ref.read(reflectionStorageProvider);
    await storage.delete(lessonId);
    final next = {...?state.value}..remove(lessonId);
    state = AsyncValue.data(next);
  }
}

final reflectionsMapProvider = AsyncNotifierProvider<ReflectionsMapNotifier,
    Map<String, ReflectionEntry>>(ReflectionsMapNotifier.new);

/// Convenience: the reflection for a single lesson, or `null` if the
/// user hasn't written one yet.
final lessonReflectionProvider =
    Provider.family<ReflectionEntry?, String>((ref, lessonId) {
  final map = ref.watch(reflectionsMapProvider);
  return map.value?[lessonId];
});
