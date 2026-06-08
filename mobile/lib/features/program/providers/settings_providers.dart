/// Phase 7 providers — children list, update, and progress reset.
///
/// Hierarchy:
///   tgClientProvider           ── (existing, in progress_providers)
///   progressRepositoryProvider ── (existing, in progress_providers)
///       │
///       ▼
///   settingsRepositoryProvider   ── Provider<SettingsRepository>
///       │
///       ├── childrenListProvider       ── AsyncNotifier (manual refresh)
///       ├── updateChildProvider        ── AsyncNotifier
///       └── resetProgressProvider      ── AsyncNotifier
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/chat_notifier.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/progress_models.dart';
import '../data/settings_repository.dart';
import 'progress_providers.dart';

final settingsRepositoryProvider = Provider<SettingsRepository>((ref) {
  return SettingsRepository(ref.watch(tgClientProvider));
});

/// Fetch + cache the list of children owned by the current device.
/// Manual refresh: `ref.invalidate(childrenListProvider)`.
class ChildrenListNotifier
    extends AutoDisposeAsyncNotifier<ChildListEnvelope> {
  @override
  Future<ChildListEnvelope> build() async {
    final repo = ref.read(settingsRepositoryProvider);
    return repo.listChildren();
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(settingsRepositoryProvider);
      return repo.listChildren();
    });
  }
}

final childrenListProvider = AsyncNotifierProvider.autoDispose<
    ChildrenListNotifier, ChildListEnvelope>(ChildrenListNotifier.new);

/// Update the active child. After success:
///   * invalidates [childrenListProvider] so the list re-fetches
///   * re-hydrates [OnboardingStorage] with the new values
class UpdateChildNotifier extends AutoDisposeAsyncNotifier<ChildProfile?> {
  @override
  Future<ChildProfile?> build() async => null;

  Future<ChildProfile> call({
    required int childId,
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
  }) async {
    state = const AsyncValue.loading();
    try {
      final repo = ref.read(settingsRepositoryProvider);
      final child = await repo.updateChild(
        childId: childId,
        name: name,
        ageGroup: ageGroup,
        gender: gender,
        avatarEmoji: avatarEmoji,
      );
      // If we just changed the active child, sync the on-disk profile
      // so the rest of the app (DailyTipCard, path detail) refetches
      // with the new age_group.
      final activeId = ref.read(activeChildIdProvider);
      if (activeId == childId) {
        await ref.read(onboardingStorageProvider).setActiveChild(
              id: child.id,
              name: child.name,
              ageGroup: child.ageGroup,
            );
        // The on-disk provider we declared as Provider — let
        // consumers know to re-read.
        ref.invalidate(activeChildProfileProvider);
      }
      // Re-hydrate the on-disk list.
      ref.invalidate(childrenListProvider);
      state = AsyncValue.data(child);
      return child;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }
}

final updateChildProvider = AsyncNotifierProvider.autoDispose<
    UpdateChildNotifier, ChildProfile?>(UpdateChildNotifier.new);

/// Reset all `lesson_progress` rows for a child. After success:
///   * invalidates the child's progress provider so StreakChip and
///     ProgressIndicator refresh
class ResetProgressNotifier extends AutoDisposeAsyncNotifier<int?> {
  @override
  Future<int?> build() async => null;

  Future<int> call(int childId) async {
    state = const AsyncValue.loading();
    try {
      final repo = ref.read(settingsRepositoryProvider);
      final deleted = await repo.resetProgress(childId);
      // The progress provider for this child is keyed by childId;
      // invalidating it forces re-fetch and StreakChip/ProgressIndicator
      // snap to 0.
      ref.invalidate(childProgressProvider(childId));
      state = AsyncValue.data(deleted);
      return deleted;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }
}

final resetProgressProvider = AsyncNotifierProvider.autoDispose<
    ResetProgressNotifier, int?>(ResetProgressNotifier.new);
