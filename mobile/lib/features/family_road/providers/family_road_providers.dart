/// Wiring for «درب {الاسم}» and the «على الأفق» strip (عالم الأسرة).
///
/// Everything comes from answers the app already asks for — `/api/programs`
/// (age, Ramadan, milestones due, the season), the child's milestones, the
/// paths of the child's age band, the child's progress and `/api/family/week`
/// — and every one of them is optional: a failure or an older server removes
/// its gates or lanterns, never the screen.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../main.dart' show appConfigProvider;
import '../../lanterns/providers/lantern_providers.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/data/models.dart';
import '../../program/data/progress_models.dart';
import '../../program/providers/program_providers.dart';
import '../../program/providers/progress_providers.dart';
import '../../programs/data/programs_models.dart';
import '../../programs/providers/programs_providers.dart';
import '../logic/horizon.dart';
import '../logic/road_past.dart';

/// The server's kill switch for the strip on Today (`/api/app-config` →
/// `horizon_strip_enabled`). Missing (an older server) means on.
final horizonStripEnabledProvider = Provider<bool>((ref) {
  final cfg = ref.watch(appConfigProvider).valueOrNull;
  return cfg?['horizon_strip_enabled'] != false;
});

/// The paths of the active child's band, in the server's order; empty while
/// loading or on any failure.
final roadPathsProvider = Provider.autoDispose<List<CurriculumPath>>((ref) {
  final band = ref.watch(selectedAgeGroupProvider);
  return ref
          .watch(pathsListProvider(PathsListArgs(ageGroup: band)))
          .valueOrNull
          ?.paths ??
      const [];
});

ChildProgressBundle? _bundle(Ref ref) =>
    ref.watch(activeChildProgressProvider)?.valueOrNull;

/// The active child's milestones, or none (no programs, an older server, a
/// failure — the dated gates then come from `/api/programs` alone).
final roadMilestonesProvider = FutureProvider.autoDispose<List<Milestone>>((
  ref,
) async {
  final id = ref.watch(activeChildProfileProvider)?.id;
  final overview = ref.watch(programsOverviewProvider).valueOrNull;
  if (id == null ||
      overview == null ||
      overview.unavailable.contains('milestones')) {
    return const [];
  }
  try {
    final list = await ref.watch(milestonesProvider(id).future);
    return [...list.due, ...list.upcoming];
  } catch (_) {
    return const [];
  }
});

/// The gates ahead for the active child, nearest first.
final horizonGatesProvider = Provider.autoDispose<List<HorizonGate>>((ref) {
  final profile = ref.watch(activeChildProfileProvider);
  if (profile == null) return const [];
  final overview = ref.watch(programsOverviewProvider).valueOrNull;
  final mine = overview?.forChild(profile.id);
  final ramadan = overview?.ramadan;
  final paths = ref.watch(roadPathsProvider);
  final next = nextPath(paths, _bundle(ref));
  final milestones =
      ref.watch(roadMilestonesProvider).valueOrNull ?? const <Milestone>[];
  return horizonGates(
    HorizonInputs(
      today: overview?.date ?? DateTime.now(),
      child: mine == null
          ? const HorizonChild()
          : HorizonChild(
              ageMonths: mine.age.months,
              ageFromBirthMonth: mine.age.fromBirthMonth,
              band: mine.age.band,
              prayerEligible: mine.prayer.eligibleTrack != null,
              milestonesDue: mine.milestonesServed ? mine.milestonesDue : 0,
              needsBirthMonth: mine.milestonesServed && mine.needsBirthMonth,
            ),
      ramadanState: ramadan == null || ramadan.season == null
          ? null
          : switch (ramadan.state) {
              RamadanState.upcoming => 'upcoming',
              RamadanState.ramadan => 'ramadan',
              RamadanState.eid => 'eid',
              RamadanState.after => 'after',
              RamadanState.offSeason => 'off_season',
            },
      ramadanDaysUntil: ramadan?.daysUntilStart,
      ramadanDay: ramadan?.day,
      milestones: [
        for (final m in milestones)
          HorizonMilestone(
            key: m.key,
            title: m.title,
            state: m.state,
            dueOn: m.dueOn,
          ),
      ],
      nextPathId: next?.id,
      nextPathTitle: next?.title,
    ),
  );
});

/// The gate the strip on Today names, or null — then the strip is not there.
final horizonStripGateProvider = Provider.autoDispose<HorizonGate?>((ref) {
  if (!ref.watch(horizonStripEnabledProvider)) return null;
  return stripGate(ref.watch(horizonGatesProvider));
});

/// Where «أنتم هنا» stands: the path being resumed, if any.
final roadHereProvider =
    Provider.autoDispose<({CurriculumPath path, int done})?>((ref) {
      return resumePath(ref.watch(roadPathsProvider), _bundle(ref));
    });

/// What is behind «أنتم هنا».
final roadPastProvider = Provider.autoDispose<RoadPast>((ref) {
  final week = ref.watch(familyWeekProvider).valueOrNull;
  final moons = fullMoons(ref.watch(roadPathsProvider), _bundle(ref));
  return RoadPast.from(week, moons);
});

/// The season the sky marks today (null on a quiet day, an older server).
final skySeasonProvider = Provider<HijriSeasonMonth?>((ref) {
  return ref.watch(programsOverviewProvider).valueOrNull?.hijriSeason?.month;
});
