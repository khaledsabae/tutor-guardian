/// Riverpod providers for Phase 5 (children + lesson progress).
///
/// Hierarchy:
///   tgClientProvider (existing)
///       │
///       ▼
///   progressRepositoryProvider   ── Provider<ProgressRepository>
///       │
///       ├──► activeChildIdProvider       (StateProvider<int?>) — null = no
///       │                                                   child selected
///       │
///       ├──► childProgressProvider       (FutureProvider.family(...)
///       │                                key: childId — re-fetches on
///       │                                invalidation after a PATCH)
///       │
│       ├──► pathProgressMapProvider     (derived — exposes a Map<lessonId,
│       │                                ProgressStatus> for the current
│       │                                child, optionally filtered by path)
│       │
│       └──► markLessonProgressProvider  (AsyncNotifier — PATCH + invalidate
│                                        childProgressProvider on success)
///
/// The `activeChildId` lives in-memory for now (Phase 5+ persists it).
library;

import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter/widgets.dart' show WidgetRef;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../data/progress_models.dart';
import '../data/progress_repository.dart';

final progressRepositoryProvider = Provider<ProgressRepository>((ref) {
  final client = ref.watch(tgClientProvider);
  return ProgressRepository(client);
});

/// The currently-selected child for the device. Phase 5 lets the user
/// create a child once (via the `PathsScreen` "add child" flow) and
/// pins that id in a session provider. For now this is hard-coded
/// to "the first/most-recent child" — a list-children endpoint is
/// the obvious Phase 5+ addition.
final activeChildIdProvider = StateProvider<int?>((_) => null);

/// Raw progress bundle for a child.
final childProgressProvider = FutureProvider.autoDispose
    .family<ChildProgressBundle, int>((ref, childId) {
  final repo = ref.watch(progressRepositoryProvider);
  return repo.getChildProgress(childId);
});

/// Derived: lesson-id → ProgressStatus for a given child + path.
/// This is what the PathDetailScreen consumes.
class PathProgressMap {
  final int childId;
  final String? pathId; // null = all lessons for the child
  final Map<String, ProgressStatus> byLesson;
  final int totalLessonsInPath; // supplied by the UI; not in the bundle

  const PathProgressMap({
    required this.childId,
    required this.pathId,
    required this.byLesson,
    required this.totalLessonsInPath,
  });

  int get completedCount => byLesson.values
      .where((s) => s == ProgressStatus.completed)
      .length;
  int get inProgressCount => byLesson.values
      .where((s) => s == ProgressStatus.inProgress)
      .length;
  double get fraction {
    if (totalLessonsInPath == 0) return 0.0;
    return completedCount / totalLessonsInPath;
  }

  ProgressStatus statusFor(String lessonId) =>
      byLesson[lessonId] ?? ProgressStatus.notStarted;
}

class PathProgressArgs {
  final int childId;
  final String? pathId;
  final int totalLessonsInPath;
  const PathProgressArgs({
    required this.childId,
    required this.totalLessonsInPath,
    this.pathId,
  });

  @override
  bool operator ==(Object other) =>
      other is PathProgressArgs &&
      other.childId == childId &&
      other.pathId == pathId &&
      other.totalLessonsInPath == totalLessonsInPath;

  @override
  int get hashCode => Object.hash(childId, pathId, totalLessonsInPath);
}

final pathProgressMapProvider = FutureProvider.autoDispose
    .family<PathProgressMap, PathProgressArgs>((ref, args) async {
  final bundle = await ref.watch(childProgressProvider(args.childId).future);
  final filtered = args.pathId == null
      ? bundle.lessons
      : bundle.lessons.where((l) => l.pathId == args.pathId).toList();
  final map = <String, ProgressStatus>{};
  for (final l in filtered) {
    map[l.lessonId] = l.status;
  }
  return PathProgressMap(
    childId: args.childId,
    pathId: args.pathId,
    byLesson: map,
    totalLessonsInPath: args.totalLessonsInPath,
  );
});

/// PATCH a single lesson's progress and re-fetch the bundle so the
/// PathDetailScreen's ProgressIndicator updates without a manual
/// refresh.
class MarkLessonProgressNotifier
    extends AutoDisposeFamilyAsyncNotifier<LessonProgress, String> {
  @override
  Future<LessonProgress> build(String lessonId) async {
    // The notifier holds the *most recent* response; it does not
    // perform a network call on build. The PATCH happens via
    // [markProgress] below.
    throw UnimplementedError('Use markProgress() instead.');
  }

  Future<LessonProgress> markProgress(
    ProgressStatus status, {
    int? childId,
  }) async {
    final repo = ref.read(progressRepositoryProvider);
    final updated = await repo.patchLessonProgress(
      lessonId: arg,
      status: status,
    );
    // Invalidate the affected child bundle so any PathProgressMap
    // re-derives with the new status. The chat screen continues to
    // work — autoDispose handles re-subscription on the next watch.
    final targetChild = childId ?? ref.read(activeChildIdProvider);
    if (targetChild != null) {
      ref.invalidate(childProgressProvider(targetChild));
    }
    state = AsyncValue.data(updated);
    return updated;
  }
}

final markLessonProgressProvider = AsyncNotifierProvider.autoDispose
    .family<MarkLessonProgressNotifier, LessonProgress, String>(
  MarkLessonProgressNotifier.new,
);

/// Create a child (POST). On success, sets [activeChildIdProvider] to
/// the new id so subsequent screens pick it up.
class CreateChildNotifier
    extends AutoDisposeAsyncNotifier<ChildProfile?> {
  @override
  Future<ChildProfile?> build() async => null;

  Future<ChildProfile> create({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
  }) async {
    state = const AsyncValue.loading();
    try {
      final repo = ref.read(progressRepositoryProvider);
      final child = await repo.createChild(
        name: name,
        ageGroup: ageGroup,
        gender: gender,
        avatarEmoji: avatarEmoji,
      );
      // Wire up the new child as active on both runtime + disk.
      await _setActiveAndPersist(ref, child);
      state = AsyncValue.data(child);
      return child;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }
}

/// Shared helper: persist the active child on disk + push the id into
/// the runtime provider + invalidate everything that depends on the
/// child id (progress, tips, paths filtered by age_group).
///
/// Used by both CreateChild (POST) and SwitchActiveChild (local-only).
@visibleForTesting
Future<void> setActiveChildAndPersist(
    WidgetRef ref, ChildProfile child) async {
  await _setActiveAndPersist(ref, child);
}

Future<void> _setActiveAndPersist(WidgetRef ref, ChildProfile child) async {
  final storage = ref.read(onboardingStorageProvider);
  await storage.setActiveChild(
    id: child.id,
    name: child.name,
    ageGroup: child.ageGroup,
  );
  ref.read(activeChildIdProvider.notifier).state = child.id;
  ref.invalidate(activeChildProfileProvider);
  // The cascade — every provider keyed by child id or age_group must
  // re-fetch. Paths list re-fetches when selectedAgeGroupProvider
  // changes (which is derived from the new profile).
  ref.invalidate(childProgressProvider);
  // childProgressProvider is a family, so invalidate(childId) is the
  // targeted way; childProgressProvider alone invalidates all families.
  // The dailyTipProvider is keyed by DailyTipArgs(ageGroup) — since
  // the age_group may differ, drop the whole cache.
  ref.invalidate(dailyTipProvider);
  ref.invalidate(pathsListProvider);
}

final createChildProvider = AsyncNotifierProvider.autoDispose<
    CreateChildNotifier, ChildProfile?>(CreateChildNotifier.new);

/// Phase 8-B — switch the active child. This is a *local* operation
/// (the backend doesn't track "which child is active" for the device —
/// the device does). The child MUST already exist on the server (it
/// was returned from listChildren/createChild).
class SwitchActiveChildNotifier
    extends AutoDisposeAsyncNotifier<ChildProfile?> {
  @override
  Future<ChildProfile?> build() async => null;

  Future<ChildProfile> call(ChildProfile child) async {
    state = const AsyncValue.loading();
    try {
      await setActiveChildAndPersist(ref, child);
      state = AsyncValue.data(child);
      return child;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }
}

final switchActiveChildProvider = AsyncNotifierProvider.autoDispose<
    SwitchActiveChildNotifier, ChildProfile?>(SwitchActiveChildNotifier.new);

// Phase 7 settings providers live in `settings_providers.dart` (in
// the same directory). They re-use [progressRepositoryProvider] and
// [tgClientProvider] defined above.
