/// Riverpod providers for the curriculum program layer (Phase 4).
///
/// Hierarchy:
///
///   tgClientProvider        ── (existing)  global, from chat_notifier
///       │
///       ▼
///   programRepositoryProvider        ── Provider<ProgramRepository>
///       │
///       ├──► pathsListProvider       ── AsyncNotifierProvider<...>
///       │       args: (ageGroup, domain) — null = "all"
///       │
///       ├──► pathDetailProvider      ── FutureProvider.family(...)
///       │       key: (pathId, includeLessons)
///       │
///       ├──► lessonProvider          ── FutureProvider.family(...)
///       │       key: lessonId
///       │
///       └──► dailyTipProvider        ── AsyncNotifierProvider<...>
///               args: (ageGroup, timeOfDay)
///
/// Screens use `ref.watch(...)` to subscribe; they use
/// `ref.read(...).notifier.refresh()` to force a re-fetch on pull-to-refresh.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../state/chat_notifier.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/models.dart';
import '../data/program_repository.dart';

/// The repository itself — overridable in tests so we can stub the
/// network layer without a real [TgClient].
final programRepositoryProvider = Provider<ProgramRepository>((ref) {
  final client = ref.watch(tgClientProvider);
  return ProgramRepository(client);
});

// ── pathsListProvider ────────────────────────────────────────────────────

class PathsListArgs {
  final String? ageGroup;
  final String? domain;
  const PathsListArgs({this.ageGroup, this.domain});

  @override
  bool operator ==(Object other) =>
      other is PathsListArgs &&
      other.ageGroup == ageGroup &&
      other.domain == domain;

  @override
  int get hashCode => Object.hash(ageGroup, domain);
}

class PathsListNotifier
    extends AutoDisposeFamilyAsyncNotifier<PathListEnvelope, PathsListArgs> {
  @override
  Future<PathListEnvelope> build(PathsListArgs arg) {
    final repo = ref.watch(programRepositoryProvider);
    return repo.listPaths(ageGroup: arg.ageGroup, domain: arg.domain);
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() {
      final repo = ref.read(programRepositoryProvider);
      return repo.listPaths(ageGroup: arg.ageGroup, domain: arg.domain);
    });
  }
}

final pathsListProvider = AsyncNotifierProvider.autoDispose.family<
    PathsListNotifier, PathListEnvelope, PathsListArgs>(
  PathsListNotifier.new,
);

// ── pathDetailProvider ───────────────────────────────────────────────────

class PathDetailArgs {
  final String pathId;
  final bool includeLessons;
  const PathDetailArgs({required this.pathId, this.includeLessons = true});

  @override
  bool operator ==(Object other) =>
      other is PathDetailArgs &&
      other.pathId == pathId &&
      other.includeLessons == includeLessons;

  @override
  int get hashCode => Object.hash(pathId, includeLessons);
}

final pathDetailProvider =
    FutureProvider.autoDispose.family<PathDetail, PathDetailArgs>((ref, args) {
  final repo = ref.watch(programRepositoryProvider);
  return repo.getPathDetail(args.pathId, includeLessons: args.includeLessons);
});

// ── lessonProvider ───────────────────────────────────────────────────────

final lessonProvider = FutureProvider.autoDispose
    .family<CurriculumLesson, String>((ref, lessonId) {
  final repo = ref.watch(programRepositoryProvider);
  return repo.getLesson(lessonId);
});

// ── dailyTipProvider ─────────────────────────────────────────────────────

class DailyTipArgs {
  final String ageGroup;
  final String? timeOfDay;
  const DailyTipArgs({required this.ageGroup, this.timeOfDay});

  @override
  bool operator ==(Object other) =>
      other is DailyTipArgs &&
      other.ageGroup == ageGroup &&
      other.timeOfDay == timeOfDay;

  @override
  int get hashCode => Object.hash(ageGroup, timeOfDay);
}

class DailyTipNotifier
    extends AutoDisposeFamilyAsyncNotifier<DailyTip, DailyTipArgs> {
  @override
  Future<DailyTip> build(DailyTipArgs arg) {
    final repo = ref.watch(programRepositoryProvider);
    return repo.getDailyTip(ageGroup: arg.ageGroup, timeOfDay: arg.timeOfDay);
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() {
      final repo = ref.read(programRepositoryProvider);
      return repo.getDailyTip(ageGroup: arg.ageGroup, timeOfDay: arg.timeOfDay);
    });
  }
}

final dailyTipProvider = AsyncNotifierProvider.autoDispose.family<
    DailyTipNotifier, DailyTip, DailyTipArgs>(
  DailyTipNotifier.new,
);

/// A user-visible "selected age group" preference.
///
/// Derived from the active child's profile (falls back to `4-6` before
/// onboarding completes). Watching [activeChildProfileProvider] means a
/// create/switch-child automatically resets this to the new child's age
/// group — paths and daily tips follow the right child on cold boot too.
final selectedAgeGroupProvider = StateProvider<String>((ref) {
  final child = ref.watch(activeChildProfileProvider);
  return child?.ageGroup ?? '4-6';
});
