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

import '../../onboarding/providers/onboarding_providers.dart';
import '../data/journey_store.dart';

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
