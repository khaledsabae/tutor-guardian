/// Phase 7 providers — children list, update, and progress reset.
///
/// Hierarchy:
///   tgClientProvider           ── (existing, in progress_providers)
///   progressRepositoryProvider ── (existing, in progress_providers)
///       │
///       ▼
///   settingsRepositoryProvider   ── `Provider<SettingsRepository>`
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
import 'program_providers.dart';
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

/// Delete a child profile entirely. After success, invalidates
/// [childrenListProvider] so the list re-fetches without the removed child.
class DeleteChildNotifier extends AutoDisposeAsyncNotifier<bool?> {
  @override
  Future<bool?> build() async => null;

  Future<bool> call(int childId) async {
    state = const AsyncValue.loading();
    try {
      final repo = ref.read(settingsRepositoryProvider);
      final ok = await repo.deleteChild(childId);
      ref.invalidate(childrenListProvider);
      if (ok) await _repointActiveChild(childId);
      state = AsyncValue.data(ok);
      return ok;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      rethrow;
    }
  }

  /// Move the "active child" off a child that no longer exists.
  ///
  /// Deleting the active child used to remove it from the list and leave every
  /// other surface pointing at the dead id: the home greeting and the app-bar
  /// chip kept showing the deleted child's name, `selectedAgeGroupProvider`
  /// kept deriving from its stored profile, and `childProgressProvider` kept
  /// re-fetching an id the server no longer had. It self-healed only if the
  /// user happened to add or switch a child afterwards.
  ///
  /// `OnboardingStorage.clearActiveChild()` existed for exactly this and was
  /// called from nowhere in `lib/`.
  ///
  /// Promoting a sibling is preferred over clearing, because clearing leaves a
  /// parent who still has children looking at an app with no child selected.
  Future<void> _repointActiveChild(int deletedId) =>
      repointActiveChildAwayFrom(ref, deletedId);
}

final deleteChildProvider = AsyncNotifierProvider.autoDispose<
    DeleteChildNotifier, bool?>(DeleteChildNotifier.new);

/// Move the active child off [staleId], promoting a sibling when there is one.
///
/// Shared by the delete flow and by [reconcileActiveChildWithServer]; the
/// caller is responsible for making sure [childrenListProvider] will not answer
/// from a cache that still contains [staleId].
Future<void> repointActiveChildAwayFrom(Ref ref, int staleId) async {
  final storage = ref.read(onboardingStorageProvider);
  final wasActive = ref.read(activeChildIdProvider) == staleId ||
      storage.activeChildId == staleId;
  if (!wasActive) return;

  try {
    final envelope = await ref.read(childrenListProvider.future);
    for (final child in envelope.children) {
      if (child.id == staleId) continue;
      // Reuses the full cascade (persist + invalidate progress, tip, paths)
      // rather than repeating it here.
      await ref.read(switchActiveChildProvider.notifier)(child);
      return;
    }
  } catch (_) {
    // The re-fetch failing must not strand the app on a deleted child, so
    // fall through and clear. Worst case the user picks a child again.
  }

  await storage.clearActiveChild();
  ref.read(activeChildIdProvider.notifier).state = null;
  ref.invalidate(activeChildProfileProvider);
  ref.invalidate(childProgressProvider);
  ref.invalidate(dailyTipProvider);
  ref.invalidate(pathsListProvider);
}

/// Heal an active child id the server no longer has.
///
/// `_repointActiveChild` covers deletion *on this device*. It cannot cover a
/// child removed from a second device on the same identity, a profile deleted
/// server-side, or a restore that brought the prefs back without the row — and
/// nothing else ever compared the stored id against the server's list. In
/// production a device spent days asking for child 847, which no longer
/// existed: `/api/children/847/progress` and `/api/program/coach-tip` answered
/// 404 on every launch, so Home's «نصيحة اليوم» card hid itself (it hides on
/// any error) and progress never loaded. The device could not recover on its
/// own — only adding or switching a child would have fixed it.
///
/// Returns true when the stored child was gone and the app was repointed.
///
/// A failed fetch is left alone deliberately: offline is not evidence that the
/// child is gone, and clearing on a timeout would strand a parent with no
/// selection every time they opened the app on a bad connection.
Future<bool> reconcileActiveChildWithServer(Ref ref) async {
  final storedId = ref.read(onboardingStorageProvider).activeChildId;
  if (storedId == null) return false;
  final ChildListEnvelope envelope;
  try {
    // refresh, not read: a cache that predates the deletion still lists the
    // stale child, and would make this check pass on exactly the launch it
    // exists to catch.
    envelope = await ref.refresh(childrenListProvider.future);
  } catch (_) {
    return false;
  }
  if (envelope.children.any((c) => c.id == storedId)) return false;
  await repointActiveChildAwayFrom(ref, storedId);
  return true;
}

/// Runs [reconcileActiveChildWithServer] once per app launch.
///
/// Deliberately not autoDispose: the check costs one request and must not
/// re-run every time a screen that reads it is rebuilt.
final activeChildReconcileProvider = FutureProvider<bool>((ref) {
  return reconcileActiveChildWithServer(ref);
});
