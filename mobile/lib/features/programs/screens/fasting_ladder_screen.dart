/// «سلّم الصيام» — one child's fasting ladder, with the safety guidance always
/// on screen (`GET /api/children/{id}/ramadan/fasting`).
///
/// Order is safety first: the urgent signs and what to do come before any
/// step, then when to stop, then who sees a doctor before starting. A step
/// down is never recorded anywhere; a day not practised is not recorded at
/// all; a reached weekly cap reads as "tomorrow is a rest day", never as a
/// score. "Reached puberty" is a quiet toggle at the bottom: puberty, not age,
/// makes fasting obligatory, and it moves the child to the 13-15 ladder.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../state/chat_notifier.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/loading_view.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';
import '../widgets/ramadan_widgets.dart';

class FastingLadderScreen extends ConsumerWidget {
  const FastingLadderScreen({super.key, required this.childId});
  final int childId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final ladder = ref.watch(fastingLadderProvider(childId));
    return Scaffold(
      appBar: AppBar(
        title: Text(
          ladder.valueOrNull?.guidance?.title ?? l10n.ramadanFastingTitle,
        ),
      ),
      body: ladder.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) => ProgramErrorView(
          error: e,
          onRetry: () => ref.invalidate(fastingLadderProvider(childId)),
        ),
        data: (l) => _LadderBody(childId: childId, ladder: l),
      ),
    );
  }
}

class _LadderBody extends ConsumerStatefulWidget {
  const _LadderBody({required this.childId, required this.ladder});
  final int childId;
  final FastingLadder ladder;

  @override
  ConsumerState<_LadderBody> createState() => _LadderBodyState();
}

class _LadderBodyState extends ConsumerState<_LadderBody> {
  String? _busyStep;
  bool _busy = false;

  String get _name =>
      programChildProfile(ref, widget.childId)?.name ??
      AppLocalizations.of(context).childFallbackName;

  Future<void> _setStep(FastingStep step) async {
    final l10n = AppLocalizations.of(context);
    final container = programsContainerOf(context);
    setState(() => _busyStep = step.key);
    try {
      final json = await ref
          .read(tgClientProvider)
          .updateFasting(widget.childId, stepKey: step.key);
      _refresh(container); // even if the parent already left this screen
      if (!mounted) return;
      final climbed = json['climbed'] == true;
      unawaited(
        Analytics.programAction('ramadan', climbed ? 'step_up' : 'step_set'),
      );
      showProgramSnack(
        context,
        climbed ? l10n.fastingClimbed : l10n.fastingStepSaved,
      );
    } catch (e) {
      if (mounted) showProgramSnack(context, programChangeError(l10n, e));
    } finally {
      if (mounted) setState(() => _busyStep = null);
    }
  }

  Future<void> _setPuberty(bool value) async {
    final l10n = AppLocalizations.of(context);
    final container = programsContainerOf(context);
    setState(() => _busy = true);
    try {
      await ref
          .read(tgClientProvider)
          .updateFasting(widget.childId, reachedPuberty: value);
      _refresh(container);
      if (!mounted) return;
      unawaited(
        Analytics.programAction(
          'ramadan',
          value ? 'puberty_on' : 'puberty_off',
        ),
      );
      showProgramSnack(context, l10n.programsSaved);
    } catch (e) {
      if (mounted) showProgramSnack(context, programChangeError(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _refresh(ProviderContainer container) {
    container.invalidate(fastingLadderProvider(widget.childId));
    container.invalidate(ramadanTodayProvider(widget.childId));
    refreshProgramsSummary(container);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final ladder = widget.ladder;
    final g = ladder.guidance;
    final current = ladder.currentStep?.key;
    final canSet =
        ladder.state != RamadanState.offSeason && ladder.season != null;

    return RefreshIndicator(
      onRefresh: () =>
          ref.refresh(fastingLadderProvider(widget.childId).future),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          // ── Safety first ──
          if (g != null && (g.urgentSigns.isNotEmpty || g.urgentAction != null))
            ProgramSection(
              key: const ValueKey('fasting_urgent'),
              tone: SectionTone.danger,
              emoji: '🚨',
              title: l10n.fastingUrgentTitle,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ProgramBullets(g.urgentSigns),
                  if (g.urgentAction != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      l10n.fastingUrgentWhatToDo,
                      style: TextStyle(
                        color: c.dangerFg,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    ContentText(
                      g.urgentAction!,
                      style: TextStyle(
                        color: c.ink,
                        fontWeight: FontWeight.w700,
                        height: 1.6,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          if (g != null && (g.stopSigns.isNotEmpty || g.stopAction != null))
            ProgramSection(
              tone: SectionTone.warning,
              emoji: '✋',
              title: l10n.fastingStopTitle,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ProgramBullets(g.stopSigns),
                  if (g.stopAction != null) ...[
                    const SizedBox(height: 6),
                    ContentText(
                      g.stopAction!,
                      style: TextStyle(
                        color: c.ink,
                        fontWeight: FontWeight.w700,
                        height: 1.6,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          if (g != null && g.doctorFirst.isNotEmpty)
            ProgramSection(
              emoji: '🩺',
              title: l10n.fastingDoctorFirst,
              child: ProgramBullets(g.doctorFirst),
            ),

          // ── The ladder ──
          ProgramSection(
            emoji: '🪜',
            title: l10n.fastingSteps(_name),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (ladder.summary != null) ...[
                  ContentText(ladder.summary!),
                  const SizedBox(height: 10),
                ],
                for (final step in ladder.steps)
                  _StepTile(
                    step: step,
                    current: step.key == current,
                    busy: _busyStep == step.key,
                    onSet:
                        canSet &&
                            step.eligible &&
                            step.key != current &&
                            _busyStep == null
                        ? () => _setStep(step)
                        : null,
                  ),
                if (!canSet)
                  Text(
                    l10n.programsErrorNotInSeason,
                    style: TextStyle(
                      color: c.textSecondary,
                      fontSize: 12.5,
                      height: 1.5,
                    ),
                  ),
              ],
            ),
          ),
          if (ladder.canPractise)
            FastingSummaryCard(
              childId: widget.childId,
              childName: _name,
              inMonth: true,
              fasting: FastingSummary(
                ladderBand: ladder.ladderBand,
                fasts: ladder.fasts,
                reachedPuberty: ladder.reachedPuberty,
                currentStep: ladder.currentStep,
                practisedToday: ladder.practisedToday,
                practisedThisWeek: ladder.practisedThisWeek,
                restSuggested: ladder.restSuggested,
              ),
            ),

          if (g != null && g.principles.isNotEmpty)
            ProgramSection(
              emoji: '🤍',
              title: l10n.fastingPrinciples,
              child: ProgramBullets(g.principles),
            ),
          if (g != null && g.tips.isNotEmpty)
            ProgramSection(
              emoji: '💡',
              title: l10n.fastingTips,
              child: ProgramBullets(g.tips),
            ),
          if (g != null && g.evidence.isNotEmpty)
            ProgramSection(
              title: l10n.programsEvidenceTitle,
              child: EvidenceCards(g.evidence),
            ),

          // ── Puberty: quiet, at the bottom ──
          if (canSet)
            ProgramSection(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SwitchListTile.adaptive(
                    key: const ValueKey('fasting_puberty'),
                    contentPadding: EdgeInsets.zero,
                    title: Text(l10n.fastingPuberty(_name)),
                    value: ladder.reachedPuberty,
                    onChanged: _busy ? null : _setPuberty,
                  ),
                  Text(
                    l10n.fastingPubertyHint,
                    style: TextStyle(
                      color: c.textSecondary,
                      fontSize: 12.5,
                      height: 1.55,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _StepTile extends StatelessWidget {
  const _StepTile({
    required this.step,
    required this.current,
    required this.busy,
    this.onSet,
  });
  final FastingStep step;
  final bool current;
  final bool busy;
  final VoidCallback? onSet;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return Container(
      key: ValueKey('fasting_step_${step.key}'),
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: current ? c.primary.withValues(alpha: .10) : c.surfaceAlt,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: current ? c.primary : c.track),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: ContentText(
                  step.label,
                  style: TextStyle(
                    color: c.ink,
                    fontWeight: FontWeight.w800,
                    height: 1.4,
                  ),
                ),
              ),
              if (current) CountBadge(l10n.fastingCurrent),
            ],
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if (step.approxHours != null)
                CountBadge(l10n.fastingHours(step.approxHours!)),
              if (step.maxDaysPerWeek != null)
                CountBadge(l10n.fastingMaxDays(step.maxDaysPerWeek!)),
              if (step.minAgeYears != null && step.minAgeYears! > 0)
                CountBadge(l10n.fastingFromAge(step.minAgeYears!)),
            ],
          ),
          if (step.text != null) ...[
            const SizedBox(height: 8),
            ContentText(step.text!),
          ],
          if (step.advanceWhen != null) ...[
            const SizedBox(height: 6),
            Text(
              l10n.fastingAdvanceWhen,
              style: TextStyle(
                color: c.textSecondary,
                fontWeight: FontWeight.w700,
                fontSize: 12.5,
              ),
            ),
            ContentText(
              step.advanceWhen!,
              style: TextStyle(
                color: c.textSecondary,
                fontSize: 13,
                height: 1.5,
              ),
            ),
          ],
          if (!step.eligible) ...[
            const SizedBox(height: 6),
            Text(
              l10n.fastingNotYetForAge,
              style: TextStyle(color: c.textSecondary, fontSize: 12.5),
            ),
          ] else if ((!current && onSet != null) || busy) ...[
            const SizedBox(height: 8),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: FilledButton.tonal(
                onPressed: busy ? null : onSet,
                child: Text(l10n.fastingSetStep),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
