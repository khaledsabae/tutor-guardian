/// «نور يتذكّر» — Noor's one line at the top of «اليوم».
///
/// Replaces the static greeting row. Shows Noor, a salutation for the time
/// of day, and one sentence chosen by [pickLine] from real data, ending in at
/// most three small chips. A close button hides the line for today.
///
/// When there is no line (no child yet, the server's kill switch, the device
/// memory not read yet) it renders [fallback] — the old greeting row — so the
/// screen never shows a gap or a spinner where the greeting was.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/haptics.dart';
import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../child_memory/data/memory_models.dart';
import '../../child_memory/providers/memory_providers.dart';
import '../../child_memory/widgets/followup_sheet.dart';
import '../../lanterns/providers/lantern_providers.dart';
import '../../lanterns/widgets/friday_harvest.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/providers/program_providers.dart';
import '../../program/providers/settings_providers.dart';
import '../../programs/providers/programs_providers.dart';
import '../../shell/root_tab.dart';
import '../logic/companion_brain.dart';
import '../providers/companion_providers.dart';
import 'noor_face.dart';
import 'noor_presence.dart';

class NoorTodayHeader extends ConsumerStatefulWidget {
  const NoorTodayHeader({super.key, required this.fallback});

  /// What to show when Noor has nothing to say (the plain greeting row).
  final Widget fallback;

  @override
  ConsumerState<NoorTodayHeader> createState() => _NoorTodayHeaderState();
}

class _NoorTodayHeaderState extends ConsumerState<NoorTodayHeader> {
  /// The line already logged as shown in this widget's life.
  String? _logged;

  /// After a local-only promise is answered: the thanks to show in place.
  ({String outcome, String kind})? _thanks;

  void _onShown(CompanionLine line) {
    if (_logged == line.key) return;
    _logged = line.key;
    unawaited(Analytics.companionShown(line.kind.name));
    final mem = ref.read(companionMemoryProvider.notifier);
    if (line.isQuestion) unawaited(mem.markQuestionShown(line.key));
    if (line.onceOnly) {
      // Held first, recorded second: the line stays for this open and
      // never comes back on the next.
      ref
          .read(heldOnceLinesProvider.notifier)
          .update((held) => {...held, line.key});
      unawaited(mem.markSeen(line.key));
    }
  }

  @override
  Widget build(BuildContext context) {
    final line = ref.watch(companionLineProvider);
    if (line == null && _thanks == null) return widget.fallback;

    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final now = DateTime.now();
    final reduce = reduceMotion(context);

    if (line != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _onShown(line);
      });
    }

    final thanks = _thanks;
    final text = thanks != null
        ? _thanksText(l10n, thanks.outcome, line?.name)
        : _lineText(l10n, line!);
    final mood = thanks != null
        ? (thanks.outcome == FollowupOutcome.worked
              ? CompanionMood.happy
              : CompanionMood.calm)
        : line!.mood;

    Widget bubble = Container(
      padding: const EdgeInsetsDirectional.fromSTEB(14, 10, 6, 12),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: colors.primary.withValues(alpha: .18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  _hello(l10n, now),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: colors.ink,
                  ),
                ),
              ),
              if (thanks == null &&
                  line!.kind != CompanionKind.greeting &&
                  line.kind != CompanionKind.firstDay)
                SizedBox(
                  width: 32,
                  height: 32,
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    tooltip: l10n.noorDismiss,
                    iconSize: 18,
                    icon: Icon(
                      Icons.close_rounded,
                      color: colors.textSecondary,
                    ),
                    onPressed: () => _dismiss(line),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsetsDirectional.only(end: 8),
            child: Text(
              text,
              maxLines: 5,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: colors.textSecondary,
                height: 1.5,
              ),
            ),
          ),
          if (thanks != null &&
              thanks.outcome == FollowupOutcome.didntWork) ...[
            const SizedBox(height: 8),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: _Chip(
                label: l10n.noorChipAskAlternative,
                primary: true,
                onTap: () => _askAlternative(l10n, line?.name),
              ),
            ),
          ] else if (thanks == null && line!.actions.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final (i, a) in line.actions.indexed)
                  _Chip(
                    label: _actionLabel(l10n, a),
                    primary: i == 0,
                    onTap: () => _act(line, a),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
    if (!reduce) {
      bubble = bubble
          .animate(key: ValueKey(thanks?.outcome ?? line!.key))
          .fadeIn(duration: Dt.base)
          .slideY(begin: .06, end: 0, duration: Dt.base, curve: Curves.easeOut);
    }

    return Semantics(
      container: true,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          NoorPresence(size: 56, face: _face(mood)),
          const SizedBox(width: 10),
          Expanded(child: bubble),
        ],
      ),
    );
  }

  // ── copy ─────────────────────────────────────────────────────────────

  String _hello(AppLocalizations l10n, DateTime now) => switch (slotOf(now)) {
    TimeSlot.dawn => l10n.noorHelloDawn,
    TimeSlot.morning => l10n.noorHelloMorning,
    TimeSlot.noon => l10n.noorHelloNoon,
    TimeSlot.evening => l10n.noorHelloEvening,
    TimeSlot.night => l10n.noorHelloNight,
  };

  String _lineText(AppLocalizations l10n, CompanionLine line) {
    final name = line.name ?? l10n.noorYourChild;
    final step = line.step ?? '';
    return switch (line.kind) {
      CompanionKind.missionsWaiting =>
        (line.count ?? 0) > 1
            ? l10n.noorMissionsMany(line.count!)
            : l10n.noorMissionsOne(name),
      CompanionKind.promiseDue => l10n.noorPromiseDue(name, step),
      CompanionKind.followupDue => l10n.noorFollowupDue(name, step),
      CompanionKind.ramadanCountdown => switch (line.ramadanDays) {
        30 => l10n.noorRamadan30(name),
        14 => l10n.noorRamadan14,
        7 => l10n.noorRamadan7(name),
        _ => l10n.noorRamadan1,
      },
      CompanionKind.ramadanStart => l10n.noorRamadanStart(name),
      CompanionKind.seasonStart => switch (line.season) {
        'rajab' => l10n.noorSeasonRajab,
        'shaban' => l10n.noorSeasonShaban,
        _ => l10n.noorSeasonDhulHijjah,
      },
      CompanionKind.mondayPlan => l10n.noorMondayPlan(name),
      CompanionKind.prayerAdvance => l10n.noorPrayerAdvance(name),
      CompanionKind.prayerInvite => l10n.noorPrayerInvite(name),
      CompanionKind.milestoneDue => l10n.noorMilestoneDue(name),
      CompanionKind.birthMonthAsk => l10n.noorBirthMonthAsk(name),
      CompanionKind.fridayHarvest => l10n.noorFridayHarvest,
      CompanionKind.firstDay => l10n.noorFirstDay(name),
      CompanionKind.greeting => _greetingText(l10n, line, name),
    };
  }

  String _greetingText(AppLocalizations l10n, CompanionLine line, String name) {
    final v = line.variant;
    return switch (slotOf(DateTime.now())) {
      TimeSlot.dawn => [
        l10n.noorLineDawn1(name),
        l10n.noorLineDawn2(name),
        l10n.noorLineDawn3,
        l10n.noorLineDawn4(name),
      ][v - 1],
      TimeSlot.morning => [
        l10n.noorLineMorning1(name),
        l10n.noorLineMorning2,
        l10n.noorLineMorning3(name),
        l10n.noorLineMorning4(name),
      ][v - 1],
      TimeSlot.noon => [
        l10n.noorLineNoon1(name),
        l10n.noorLineNoon2(name),
        l10n.noorLineNoon3,
        l10n.noorLineNoon4,
      ][v - 1],
      TimeSlot.evening => [
        l10n.noorLineEvening1(name),
        l10n.noorLineEvening2(name),
        l10n.noorLineEvening3(name),
        l10n.noorLineEvening4(name),
      ][v - 1],
      TimeSlot.night => [
        l10n.noorLineNight1(name),
        l10n.noorLineNight2,
        l10n.noorLineNight3,
        l10n.noorLineNight4(name),
      ][v - 1],
    };
  }

  String _thanksText(AppLocalizations l10n, String outcome, String? name) =>
      switch (outcome) {
        FollowupOutcome.worked => l10n.noorThanksWorked(
          name ?? l10n.noorYourChild,
        ),
        FollowupOutcome.didntWork => l10n.noorThanksDidntWork,
        _ => l10n.noorThanksDidntTry,
      };

  String _actionLabel(AppLocalizations l10n, CompanionAction a) => switch (a) {
    CompanionAction.confirmMissions => l10n.noorChipConfirm,
    CompanionAction.outcomeWorked => l10n.followupWorked,
    CompanionAction.outcomeDidntWork => l10n.followupDidntWork,
    CompanionAction.outcomeDidntTry => l10n.followupDidntTry,
    CompanionAction.openRamadan => l10n.noorChipRamadan,
    CompanionAction.openPrayerJourney => l10n.noorChipPrayerJourney,
    CompanionAction.openChildJourney => l10n.noorChipChildJourney,
    CompanionAction.editChild => l10n.noorChipAddBirthMonth,
    CompanionAction.openHarvest => l10n.noorChipHarvest,
    CompanionAction.openFamilyRoad => l10n.noorChipFamilyRoad,
  };

  NoorFaceState _face(CompanionMood m) => switch (m) {
    CompanionMood.calm => NoorFaceState.calm,
    CompanionMood.awake => NoorFaceState.awake,
    CompanionMood.happy => NoorFaceState.happy,
    CompanionMood.night => NoorFaceState.night,
  };

  // ── actions ──────────────────────────────────────────────────────────

  void _dismiss(CompanionLine line) {
    Haptics.selection();
    unawaited(Analytics.companionReply(line.kind.name, 'dismiss'));
    unawaited(
      ref.read(companionMemoryProvider.notifier).hideForToday(line.key),
    );
  }

  Future<void> _act(CompanionLine line, CompanionAction a) async {
    Haptics.selection();
    unawaited(Analytics.companionReply(line.kind.name, a.name));
    final outcome = switch (a) {
      CompanionAction.outcomeWorked => FollowupOutcome.worked,
      CompanionAction.outcomeDidntWork => FollowupOutcome.didntWork,
      CompanionAction.outcomeDidntTry => FollowupOutcome.didntTry,
      _ => null,
    };
    switch (a) {
      case CompanionAction.confirmMissions:
        await Navigator.of(context).push(AppRoutes.pendingMissions());
        ref.invalidate(missionsWaitingProvider);
      case CompanionAction.openRamadan:
        final child = ref.read(activeChildProfileProvider);
        if (child != null) {
          await Navigator.of(context).push(AppRoutes.ramadan(child.id));
        }
      case CompanionAction.openPrayerJourney:
        final child = ref.read(activeChildProfileProvider);
        if (child != null) {
          await Navigator.of(context).push(AppRoutes.prayerJourney(child.id));
          ref.invalidate(programsOverviewProvider);
        }
      case CompanionAction.openChildJourney:
        final child = ref.read(activeChildProfileProvider);
        if (child != null) {
          await Navigator.of(context).push(
            AppRoutes.childJourney(
              childId: child.id,
              childName: child.name,
              ageGroup: child.ageGroup,
            ),
          );
          ref.invalidate(programsOverviewProvider);
        }
      case CompanionAction.editChild:
        final active = ref.read(activeChildProfileProvider);
        final full = ref
            .read(childrenListProvider)
            .valueOrNull
            ?.children
            .where((c) => c.id == active?.id)
            .firstOrNull;
        if (full != null) {
          await Navigator.of(context).push(AppRoutes.editChild(full));
          ref.invalidate(programsOverviewProvider);
          ref.invalidate(childrenListProvider);
        }
      case CompanionAction.openFamilyRoad:
        await Navigator.of(context).push(AppRoutes.familyRoad(from: 'noor'));
      case CompanionAction.openHarvest:
        final week = ref.read(familyWeekProvider).valueOrNull;
        if (week != null) {
          unawaited(Analytics.harvestOpened('noor'));
          await showFridayHarvest(context, week);
        }
      case _:
        if (outcome != null) await _answer(line, outcome);
    }
  }

  /// A promise or follow-up answered from Noor's line. With a server
  /// follow-up behind it, the follow-up sheet takes over (it saves to memory
  /// and thanks per outcome); a promise the server never got is answered
  /// on the device and thanked right here.
  Future<void> _answer(CompanionLine line, String outcome) async {
    final mem = ref.read(companionMemoryProvider.notifier);
    final followupId = line.followup?.id ?? line.promise?.followupId;
    if (followupId != null) {
      await showFollowupSheet(
        context,
        followupId: followupId,
        source: 'noor',
        preselected: outcome,
      );
      if (!mounted) return;
      ref.invalidate(dueFollowupsProvider);
      // Close the promise only if the sheet actually answered it.
      try {
        final view = await ref
            .read(memoryRepositoryProvider)
            .followup(followupId);
        if (view.followup.status != 'pending') {
          await mem.answerByFollowup(
            followupId,
            view.followup.outcome ?? outcome,
          );
          if (line.promise != null) {
            unawaited(
              Analytics.promiseChecked(
                view.followup.outcome ?? outcome,
                linked: true,
              ),
            );
          }
        }
      } catch (_) {
        // Unknown — the line simply comes back next time.
      }
      return;
    }
    final p = line.promise;
    if (p == null) return;
    await mem.answer(p.id, outcome);
    unawaited(Analytics.promiseChecked(outcome, linked: false));
    if (outcome == FollowupOutcome.worked) Haptics.success();
    if (mounted) {
      setState(() => _thanks = (outcome: outcome, kind: line.kind.name));
    }
  }

  void _askAlternative(AppLocalizations l10n, String? name) {
    final step = ref
        .read(companionMemoryProvider)
        .valueOrNull
        ?.promises
        .where((p) => p.outcome == FollowupOutcome.didntWork)
        .map((p) => p.step)
        .lastOrNull;
    if (step != null) {
      ref.read(pendingChatQuestionProvider.notifier).state = l10n
          .followupAskAlternativePrefill(step, name ?? l10n.noorYourChild);
    }
    ref.read(rootTabRequestProvider.notifier).state = RootTab.assistant;
    setState(() => _thanks = null);
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.onTap, this.primary = false});

  final String label;
  final VoidCallback onTap;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Material(
      color: primary ? colors.primary : colors.surfaceAlt,
      borderRadius: BorderRadius.circular(Dt.rChip),
      child: InkWell(
        borderRadius: BorderRadius.circular(Dt.rChip),
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 40),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w700,
                color: primary ? colors.onPrimary : colors.ink,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
