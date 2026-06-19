/// «رحلة الطفل» providers — per-child milestone log (local, Phase 1).
///
/// Hierarchy:
///   sharedPreferencesProvider      (existing, onboarding_providers)
///       │
///       ▼
///   journeyStoreProvider           (Provider<JourneyStore>)
///       │
///       ▼
///   childJourneyProvider(childId)  (family AsyncNotifier —
///                                   Map<milestoneKey, MilestoneEntry>)
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/chat_notifier.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/journey_store.dart';
import '../data/memorization_store.dart';

/// Feature flag — Phase 1 «رحلة الطفل». Flip to `false` to hide every
/// entry point (Home card + child-list action) with zero other side
/// effects; the stored data is left untouched.
const bool kJourneyEnabled = true;

final journeyStoreProvider = Provider<JourneyStore>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).requireValue;
  return JourneyStore(prefs);
});

/// All milestones logged for one child, keyed by milestone key.
class ChildJourneyNotifier
    extends FamilyAsyncNotifier<Map<String, MilestoneEntry>, int> {
  @override
  Future<Map<String, MilestoneEntry>> build(int childId) async {
    return ref.read(journeyStoreProvider).loadForChild(childId);
  }

  /// Mark (or update) a milestone for this child. Idempotent on [key] —
  /// re-logging keeps the original [achievedAt] and only updates the note.
  Future<MilestoneEntry> log({
    required String key,
    required String title,
    required String emoji,
    String note = '',
  }) async {
    final store = ref.read(journeyStoreProvider);
    final existing = state.value?[key];
    final entry = MilestoneEntry(
      childId: arg,
      key: key,
      title: title,
      emoji: emoji,
      note: note,
      achievedAt: existing?.achievedAt ?? DateTime.now(),
    );
    await store.upsert(entry);
    state = AsyncValue.data({...?state.value, key: entry});
    return entry;
  }

  Future<void> remove(String key) async {
    await ref.read(journeyStoreProvider).delete(arg, key);
    state = AsyncValue.data({...?state.value}..remove(key));
  }
}

final childJourneyProvider = AsyncNotifierProvider.family<ChildJourneyNotifier,
    Map<String, MilestoneEntry>, int>(ChildJourneyNotifier.new);

/// The active «current challenge» key for a child (null = none), backed by
/// the server. Feeds the proactive coach. Errors degrade to "no challenge".
class ActiveChallengeNotifier extends FamilyAsyncNotifier<String?, int> {
  @override
  Future<String?> build(int childId) async {
    final ch = await ref.read(tgClientProvider).getChallenge(childId);
    return ch?['challenge_key'] as String?;
  }

  Future<void> set(String key, {String? note}) async {
    await ref.read(tgClientProvider).setChallenge(arg, key, note: note);
    state = AsyncValue.data(key);
  }

  Future<void> clear() async {
    await ref.read(tgClientProvider).clearChallenge(arg);
    state = const AsyncValue.data(null);
  }
}

final activeChallengeProvider =
    AsyncNotifierProvider.family<ActiveChallengeNotifier, String?, int>(
  ActiveChallengeNotifier.new,
);

final memorizationStoreProvider = Provider<MemorizationStore>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).requireValue;
  return MemorizationStore(prefs);
});

/// Memorized surah numbers (1..114) for one child.
class MemorizedSurahsNotifier extends FamilyAsyncNotifier<Set<int>, int> {
  @override
  Future<Set<int>> build(int childId) async {
    return ref.read(memorizationStoreProvider).loadForChild(childId);
  }

  /// Toggle a surah's memorized state. Returns true if it is now memorized
  /// AND it is the child's very first — the caller uses this to log the
  /// «حفظ أول سورة» milestone.
  Future<bool> toggle(int surah) async {
    final wasEmpty = (state.value ?? const <int>{}).isEmpty;
    final next = await ref.read(memorizationStoreProvider).toggle(arg, surah);
    state = AsyncValue.data(next);
    return wasEmpty && next.contains(surah);
  }
}

final memorizedSurahsProvider =
    AsyncNotifierProvider.family<MemorizedSurahsNotifier, Set<int>, int>(
  MemorizedSurahsNotifier.new,
);
