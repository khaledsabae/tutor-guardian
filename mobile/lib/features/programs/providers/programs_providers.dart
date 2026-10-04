/// Riverpod wiring for the family programs (MOBILE_API §11).
///
///   programsOverviewProvider   GET /api/programs — null when the server has
///                              no programs (404, or 503 program_unavailable).
///                              Every entry point keys off this one answer.
///   programsAvailableProvider  true only once that answer came back with data.
///   ramadanTodayProvider       GET /api/children/{id}/ramadan/today
///   ramadanDayProvider         GET /api/children/{id}/ramadan/days/{day}
///   fastingLadderProvider      GET /api/children/{id}/ramadan/fasting
///   ramadanRecapProvider       GET /api/programs/ramadan/recap
///   prayerJourneyProvider      GET /api/children/{id}/prayer-journey
///   milestonesProvider         GET /api/children/{id}/milestones
///   milestoneDetailProvider    GET /api/children/{id}/milestones/{key}
///
/// Old-server compatibility is the reason the overview returns null instead of
/// throwing on 404: builds stay live for weeks and the server ships on its own
/// schedule, so "the server has no programs" is a normal state — hide the
/// entry points — not an error to show.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../state/chat_notifier.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/data/progress_models.dart';
import '../../program/providers/settings_providers.dart';
import '../data/programs_models.dart';

/// True when [error] means "this server does not offer the programs".
///
/// A 404 without a code is FastAPI's "no such route" — a server older than
/// schema v34. `program_unavailable` (503) is an unpublished program file.
/// `child_not_found` is a 404 too, but it is about the child, not the server.
bool programsUnavailable(Object error) {
  if (error is! TgApiError) return false;
  if (error.code == 'program_unavailable') return true;
  return error.statusCode == 404 && error.code == null;
}

final programsOverviewProvider = FutureProvider<ProgramsOverview?>((ref) async {
  final client = ref.watch(tgClientProvider);
  try {
    return ProgramsOverview.fromJson(await client.fetchPrograms());
  } catch (e) {
    if (programsUnavailable(e)) return null;
    rethrow;
  }
});

/// Whether to show the programs entry points (Home card, «المزيد» tile, the
/// birth-month field). False while loading, on any failure, and on a server
/// without the programs — the entry must never lead to an error screen.
final programsAvailableProvider = Provider<bool>((ref) {
  final overview = ref.watch(programsOverviewProvider).valueOrNull;
  // Answered, and serving at least one program (each stands alone: a server
  // that can read none of the files has nothing to enter).
  return overview != null && overview.anyServed;
});

final ramadanTodayProvider = FutureProvider.autoDispose
    .family<RamadanToday, int>((ref, childId) async {
      final client = ref.watch(tgClientProvider);
      return RamadanToday.fromJson(await client.fetchRamadanToday(childId));
    });

/// Keyed by `(childId, day)`.
final ramadanDayProvider = FutureProvider.autoDispose
    .family<RamadanDayView, (int, int)>((ref, key) async {
      final client = ref.watch(tgClientProvider);
      return RamadanDayView.fromJson(
        await client.fetchRamadanDay(key.$1, key.$2),
      );
    });

final fastingLadderProvider = FutureProvider.autoDispose
    .family<FastingLadder, int>((ref, childId) async {
      final client = ref.watch(tgClientProvider);
      return FastingLadder.fromJson(await client.fetchFastingLadder(childId));
    });

final ramadanRecapProvider = FutureProvider.autoDispose<RamadanRecap>((
  ref,
) async {
  final client = ref.watch(tgClientProvider);
  return RamadanRecap.fromJson(await client.fetchRamadanRecap());
});

final prayerJourneyProvider = FutureProvider.autoDispose
    .family<PrayerJourney, int>((ref, childId) async {
      final client = ref.watch(tgClientProvider);
      return PrayerJourney.fromJson(await client.fetchPrayerJourney(childId));
    });

final milestonesProvider = FutureProvider.autoDispose
    .family<MilestonesList, int>((ref, childId) async {
      final client = ref.watch(tgClientProvider);
      return MilestonesList.fromJson(await client.fetchMilestones(childId));
    });

/// Keyed by `(childId, milestoneKey)`. Throws a 404 `milestone_not_found` when
/// the card is not this child's — the screen falls back to the list then.
final milestoneDetailProvider = FutureProvider.autoDispose
    .family<Milestone, (int, String)>((ref, key) async {
      final client = ref.watch(tgClientProvider);
      final json = await client.fetchMilestone(key.$1, key.$2);
      final milestone = Milestone.fromJson(json['milestone']);
      if (milestone == null) {
        throw const TgApiError(
          404,
          'milestone_not_found',
          code: 'milestone_not_found',
        );
      }
      return milestone;
    });

/// Refresh everything that summarises a child's programs — after a change on
/// one screen the Home card and the programs list must not show the old state.
///
/// Takes the container, captured *before* the request: a screen the parent
/// left mid-request has no usable `ref` when the answer comes back, and the
/// summary must refresh all the same.
void refreshProgramsSummary(ProviderContainer container) {
  container.invalidate(programsOverviewProvider);
}

/// The container to capture before the first await of a change.
ProviderContainer programsContainerOf(BuildContext context) =>
    ProviderScope.containerOf(context, listen: false);

/// A child as the programs screens show them: the API sends ids only.
class ProgramChild {
  const ProgramChild({
    required this.id,
    required this.name,
    this.avatarEmoji,
    this.profile,
  });
  final int id;
  final String name;
  final String? avatarEmoji;

  /// The full server profile, when the child list answered (edit links need it).
  final ChildProfile? profile;
}

/// The device's child [childId], from the child list or the active profile.
/// Null when neither knows the name yet — callers fall back to "your child".
ProgramChild? programChildProfile(WidgetRef ref, int childId) {
  final list = ref.watch(childrenListProvider).valueOrNull;
  for (final c in list?.children ?? const <ChildProfile>[]) {
    if (c.id == childId) {
      return ProgramChild(
        id: c.id,
        name: c.name,
        avatarEmoji: c.avatarEmoji,
        profile: c,
      );
    }
  }
  final active = ref.watch(activeChildProfileProvider);
  if (active != null && active.id == childId) {
    return ProgramChild(
      id: active.id,
      name: active.name,
      avatarEmoji: active.avatarEmoji,
    );
  }
  return null;
}
