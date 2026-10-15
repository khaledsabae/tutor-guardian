/// Wiring for «نور يتذكّر»: real data in, one [CompanionLine] out.
///
/// Every source is optional. A failure, an older server or a slow network
/// simply removes that source's candidate lines — the brain then falls back
/// to the time-of-day greeting, so Noor never blocks or breaks «اليوم».
library;

import 'dart:async';
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/clock.dart';
import '../../../main.dart' show appConfigProvider;
import '../../../state/chat_notifier.dart' show tgClientProvider;
import '../../child_memory/data/placeholder_names.dart';
import '../../child_memory/providers/memory_providers.dart';
import '../../coins/coins_providers.dart';
import '../../lanterns/providers/lantern_providers.dart' show familyWeekProvider;
import '../../onboarding/providers/onboarding_providers.dart';
import '../../programs/data/programs_models.dart';
import '../../programs/providers/programs_providers.dart';
import '../data/companion_store.dart';
import '../logic/companion_brain.dart';

/// The server's kill switch (`/api/app-config` → `noor_header_enabled`).
/// Missing (an older server) means on; only an explicit false turns it off.
final noorHeaderEnabledProvider = Provider<bool>((ref) {
  final cfg = ref.watch(appConfigProvider).valueOrNull;
  return cfg?['noor_header_enabled'] != false;
});

/// The device memory, re-read after every write.
class CompanionMemoryNotifier extends AsyncNotifier<CompanionMemory> {
  CompanionStore? _store;

  Future<CompanionStore> _s() async => _store ??= CompanionStore(
    await ref.read(sharedPreferencesProvider.future),
  );

  @override
  Future<CompanionMemory> build() async => (await _s()).read();

  Future<void> _write(Future<void> Function(CompanionStore s) f) async {
    final s = await _s();
    await f(s);
    state = AsyncData(s.read());
  }

  Future<Promise> addPromise({
    required int childId,
    required String step,
    required PromiseSlot slot,
    String? lessonId,
  }) async {
    final s = await _s();
    final p = await s.addPromise(
      childId: childId,
      step: step,
      slot: slot,
      lessonId: lessonId,
    );
    state = AsyncData(s.read());
    return p;
  }

  Future<void> linkFollowup(int promiseId, int followupId) =>
      _write((s) => s.linkFollowup(promiseId, followupId));
  Future<void> answer(int promiseId, String outcome) =>
      _write((s) => s.answer(promiseId, outcome));
  Future<void> answerByFollowup(int followupId, String outcome) =>
      _write((s) => s.answerByFollowup(followupId, outcome));
  Future<void> markSeen(String key) => _write((s) => s.markSeen(key));
  Future<void> markQuestionShown(String key) =>
      _write((s) => s.markQuestionShown(key));
  Future<void> hideForToday(String key) => _write((s) => s.hideForToday(key));
  Future<void> setQuietMode(bool on) => _write((s) => s.setQuietMode(on));
  Future<void> markStop(String key) => _write((s) => s.markStop(key));
}

/// «درب اليوم»: mark a stop reached, fire-and-forget —
/// `markTodayStop(ref.read(companionMemoryProvider.notifier), 'ask')`.
/// Never throws: a lost mark only leaves a station unlit for today.
void markTodayStop(CompanionMemoryNotifier memory, String key) {
  unawaited(memory.markStop(key).catchError((Object _) {}));
}

/// Which of the day's three stops the active child has reached today.
typedef TodayStops = ({bool step, bool ask, bool mission});

final todayStopsProvider = Provider.autoDispose<TodayStops>((ref) {
  final childId = ref.watch(activeChildProfileProvider)?.id;
  final memory = ref.watch(companionMemoryProvider).valueOrNull;
  final stops = memory?.stopsOn(DateTime.now()) ?? const <String>{};
  return (
    step: childId != null && stops.contains('step:$childId'),
    ask: stops.contains('ask'),
    mission: childId != null && stops.contains('mission:$childId'),
  );
});

final companionMemoryProvider =
    AsyncNotifierProvider<CompanionMemoryNotifier, CompanionMemory>(
      CompanionMemoryNotifier.new,
    );

/// Once-only lines (a Ramadan countdown day, Monday's reveal, Friday's
/// harvest) already shown in this run of the app.
///
/// Showing one records it on the device at once, so that it never comes
/// back on a later open. Within this open it has to stay put: the record
/// re-reads the memory, and the line would otherwise give way to the
/// greeting a frame after it appeared — before the parent could read it, let
/// alone tap its chip. The header adds the key here before recording it.
final heldOnceLinesProvider = StateProvider<Set<String>>((ref) => const {});

/// Claimed-but-unconfirmed missions across the family, and — when they all
/// belong to one child — whose. Zero on any failure.
final missionsWaitingProvider =
    FutureProvider.autoDispose<({int count, int? childId})>((ref) async {
      try {
        final items = await ref.watch(tgClientProvider).fetchPendingMissions();
        final ids = {
          for (final i in items)
            if (i['child_id'] is int) i['child_id'] as int,
        };
        return (
          count: items.length,
          childId: ids.length == 1 ? ids.first : null,
        );
      } catch (_) {
        return (count: 0, childId: null);
      }
    });

/// The plan card's language key, so both read the same cached plan: the
/// app's chosen language, else the device's.
String _planLang(Ref ref) {
  final code =
      ref.watch(appLocaleProvider)?.languageCode ??
      PlatformDispatcher.instance.locale.languageCode;
  return code == 'en' ? 'en' : 'ar';
}

/// The name to say, or null while it is still the default «طفلي».
String? _realName(String? name) =>
    name == null || name.trim().isEmpty || isDefaultChildName(name)
    ? null
    : name;

/// Noor's line for this open of «اليوم», or null (no child yet, switched
/// off by the server, or the device memory not read yet).
final companionLineProvider = Provider.autoDispose<CompanionLine?>((ref) {
  if (!ref.watch(noorHeaderEnabledProvider)) return null;
  final profile = ref.watch(activeChildProfileProvider);
  final memory = ref.watch(companionMemoryProvider).valueOrNull;
  if (profile == null || memory == null) return null;
  final held = ref.watch(heldOnceLinesProvider);

  final family = ref.watch(familyMembersProvider);
  final due = ref.watch(dueFollowupsProvider).valueOrNull ?? const [];
  final missions = ref.watch(missionsWaitingProvider).valueOrNull;
  final ramadan = ref.watch(programsOverviewProvider).valueOrNull?.ramadan;
  final coins = ref.watch(coinsProvider);

  String? nameOf(int childId) =>
      _realName(ref.watch(childNameProvider(childId)));

  return pickLine(
    CompanionInputs(
      now: ref.watch(clockProvider)(),
      memory: memory.withoutSeen(held),
      childId: profile.id,
      childName: _realName(profile.name),
      missionsWaiting: missions?.count ?? 0,
      missionsChildName: missions?.childId == null
          ? null
          : nameOf(missions!.childId!),
      dueFollowups: [
        for (final f in due)
          DueFollowup(
            id: f.id,
            childId: f.childId,
            source: f.source,
            step: renderMemoryText(
              f.strategy,
              childName: ref.watch(childNameProvider(f.childId)),
              family: family,
              subjectId: f.childId,
              lang: f.lang,
            ),
          ),
      ],
      ramadanDaysUntil:
          ramadan != null && ramadan.state == RamadanState.upcoming
          ? ramadan.daysUntilStart
          : null,
      ramadanYear: ramadan?.season?.hijriYear,
      // Monday's line points at the plan card below; it shows only when the
      // card does (a plan this week) — read from the same provider.
      hasWeeklyPlan:
          ref
              .watch(
                weeklyPlanProvider((childId: profile.id, lang: _planLang(ref))),
              )
              .valueOrNull !=
          null,
      // Friday's harvest needs a week with lanterns; none (or an older
      // server) leaves Friday to the greeting.
      weekActs: ref.watch(familyWeekProvider).valueOrNull?.acts.length ?? 0,
      firstDay: coins.dailyStreak <= 1,
    ),
  );
});

/// While Noor hosts a follow-up question, the Today follow-up card hides —
/// the parent is asked once, in one place.
final companionHostsFollowupProvider = Provider.autoDispose<bool>((ref) {
  final line = ref.watch(companionLineProvider);
  return line != null &&
      (line.followup != null || line.promise?.followupId != null);
});
