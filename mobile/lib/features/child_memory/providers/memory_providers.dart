/// Riverpod wiring for «المربّي يعرف ابنك».
///
///   tgClientProvider ─► memoryRepositoryProvider
///                         ├─ memorySettingsProvider     (switch; null = no memory on this server)
///                         ├─ childMemoryProvider(id)    (facts — needs a proven session)
///                         ├─ dueFollowupsProvider       (Today card — never starts a proof)
///                         └─ weeklyPlanProvider(key)    (Today card — no proof needed)
///   deviceProofServiceProvider ─► deviceProofStateProvider («نتأكّد أن هذا هاتفك…»)
///
/// Everything that needs a proof also watches the proof's success counter,
/// so a proof landing in the background brings the data in without a
/// screen having to ask again.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/chat_notifier.dart' show tgClientProvider;
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/providers/settings_providers.dart';
import '../data/memory_models.dart';
import '../data/memory_repository.dart';
import '../data/placeholder_names.dart';
import '../device_proof/device_proof_service.dart';

final memoryRepositoryProvider = Provider<MemoryRepository>(
    (ref) => MemoryRepository(ref.watch(tgClientProvider)));

/// The app-wide proof service. Tests override it with one over a fake client.
final deviceProofServiceProvider =
    Provider<DeviceProofService>((ref) => DeviceProofService.instance);

/// The proof's live state, for the screens that wait on it.
final deviceProofStateProvider = Provider.autoDispose<ProofState>((ref) {
  final service = ref.watch(deviceProofServiceProvider);
  void onChange() => ref.invalidateSelf();
  service.state.addListener(onChange);
  ref.onDispose(() => service.state.removeListener(onChange));
  return service.state.value;
});

int _provenEpoch(Ref ref) =>
    ref.watch(deviceProofStateProvider.select((s) => s.provenEpoch));

/// The memory switch, or null when there is nothing to show: a server
/// without memory (the entry points hide) or a failed read.
final memorySettingsProvider =
    FutureProvider.autoDispose<MemorySettings?>((ref) async {
  _provenEpoch(ref);
  try {
    return await ref.watch(memoryRepositoryProvider).settings();
  } catch (_) {
    return null;
  }
});

/// What the assistant knows about one child. Errors are the screen's to
/// explain (proof failure, pause, older server), so they are not swallowed.
final childMemoryProvider =
    FutureProvider.autoDispose.family<ChildMemory, int>((ref, childId) async {
  return ref.watch(memoryRepositoryProvider).facts(childId);
});

/// Follow-ups due now, every child, oldest first. Empty on anything the
/// Today card cannot show — it hides itself then.
final dueFollowupsProvider =
    FutureProvider.autoDispose<List<Followup>>((ref) async {
  _provenEpoch(ref);
  return await ref.watch(memoryRepositoryProvider).dueFollowups() ??
      const <Followup>[];
});

/// Every child profile on this device, for the sibling placeholders
/// («الطفل أ»…). Empty until the list has loaded — the text then simply keeps
/// its placeholders.
final familyMembersProvider = Provider.autoDispose<List<FamilyMember>>((ref) {
  final list = ref.watch(childrenListProvider).valueOrNull?.children;
  if (list == null) return const [];
  return [for (final c in list) FamilyMember(id: c.id, name: c.name)];
});

/// A child's name: the active child's from disk at once, any other once the
/// list has loaded; null when unknown.
final childNameProvider =
    Provider.autoDispose.family<String?, int>((ref, childId) {
  ActiveChildProfile? active;
  try {
    active = ref.watch(activeChildProfileProvider);
  } catch (_) {
    // Preferences not loaded yet: fall through to the list.
  }
  if (active != null && active.id == childId) return active.name;
  for (final m in ref.watch(familyMembersProvider)) {
    if (m.id == childId) return m.name;
  }
  return null;
});

/// Which plan: the child, and the language the parent reads.
typedef WeeklyPlanKey = ({int childId, String lang});

/// This week's plan for a child, or null (older server, failure, no plan).
///
/// A proof landing refetches it: the server keeps a separate plan for a
/// session that may use memory (`personal` is part of its cache key).
final weeklyPlanProvider = FutureProvider.autoDispose
    .family<WeeklyPlan?, WeeklyPlanKey>((ref, key) async {
  _provenEpoch(ref);
  return ref
      .watch(memoryRepositoryProvider)
      .weeklyPlan(key.childId, lang: key.lang);
});
