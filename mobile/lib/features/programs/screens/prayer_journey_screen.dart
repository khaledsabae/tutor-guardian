/// «رحلة الصلاة» — the parent's view (`GET /api/children/{id}/prayer-journey`).
///
/// The family loop the plan is built on: the parent starts the journey, the
/// child records the day's prayer task in child mode, the parent confirms in
/// the evening (the existing missions screen) and the coins feed a covenant —
/// a real reward handed over off the screen.
///
/// Nothing here is punitive. Moving on is the parent's call (suggested when a
/// stage's weeks are up, never gated on counts), going back is silent to the
/// child, counts only go up, and "per week" is a suggestion, not a target to
/// fall short of.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../state/chat_notifier.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/celebration_overlay.dart';
import '../../../widgets/ui/loading_view.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';
import '../widgets/programs_text.dart';

class PrayerJourneyScreen extends ConsumerWidget {
  const PrayerJourneyScreen({super.key, required this.childId});
  final int childId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final journey = ref.watch(prayerJourneyProvider(childId));
    return Scaffold(
      appBar: AppBar(
        title: Text(journey.valueOrNull?.title ?? l10n.programsPrayerTitle),
      ),
      body: journey.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) => ProgramErrorView(
          error: e,
          onRetry: () => ref.invalidate(prayerJourneyProvider(childId)),
        ),
        data: (j) => _JourneyBody(journey: j),
      ),
    );
  }
}

class _JourneyBody extends ConsumerStatefulWidget {
  const _JourneyBody({required this.journey});
  final PrayerJourney journey;

  @override
  ConsumerState<_JourneyBody> createState() => _JourneyBodyState();
}

class _JourneyBodyState extends ConsumerState<_JourneyBody> {
  bool _busy = false;

  PrayerJourney get j => widget.journey;
  int get _childId => j.childId;
  String get _name =>
      programChildProfile(ref, _childId)?.name ??
      AppLocalizations.of(context).childFallbackName;

  /// Runs a change, shows the refusal in words if there is one, and refreshes
  /// every summary that shows this child's journey.
  Future<PrayerJourney?> _change(
    Future<Map<String, dynamic>> Function() send,
    String action,
  ) async {
    if (_busy) return null;
    final l10n = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      final next = PrayerJourney.fromJson(await send());
      unawaited(Analytics.programAction('prayer', action));
      ref.invalidate(prayerJourneyProvider(_childId));
      refreshProgramsSummary(ref);
      return next;
    } catch (e) {
      // A stale screen or a double tap (MOBILE_API §11.4.4–5): the change
      // already happened, or the stage moved under us — show the truth.
      if (e is TgApiError && (e.code == 'stage_changed' || e.code == 'already_graduated')) {
        ref.invalidate(prayerJourneyProvider(_childId));
        refreshProgramsSummary(ref);
        return null;
      }
      if (mounted) showProgramSnack(context, programChangeError(l10n, e));
      return null;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _enrol({
    PrayerTrack? track,
    int? startStage,
    bool restart = false,
  }) async {
    await _change(
      () => ref
          .read(tgClientProvider)
          .enrolPrayerJourney(
            _childId,
            track: track?.wire,
            startStage: startStage,
            restart: restart,
          ),
      'enrol_${(track ?? j.eligibleTrack)?.wire ?? 'default'}',
    );
  }

  Future<void> _chooseStageAndEnrol({required bool restart}) async {
    final stage = await _pickStage(
      AppLocalizations.of(context).prayerChooseStage,
      [for (final s in j.stages) s.stage],
    );
    if (stage == null) return;
    await _enrol(
      track: PrayerTrack.journey,
      startStage: stage,
      restart: restart,
    );
  }

  Future<int?> _pickStage(String title, List<int> stages) {
    final l10n = AppLocalizations.of(context);
    return showDialog<int>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text(title),
        children: [
          for (final n in stages)
            SimpleDialogOption(
              onPressed: () => Navigator.of(ctx).pop(n),
              child: Text(
                '${l10n.prayerStageN(n)}${_stageTitle(n) == null ? '' : ' — ${_stageTitle(n)}'}',
              ),
            ),
        ],
      ),
    );
  }

  String? _stageTitle(int n) {
    for (final s in j.stages) {
      if (s.stage == n) return s.title;
    }
    return null;
  }

  Future<void> _setStage(int stage, String action) async {
    await _change(
      () => ref.read(tgClientProvider).setPrayerJourneyStage(_childId, stage),
      action,
    );
  }

  Future<void> _goBack() async {
    final current = j.enrolment?.stage ?? 1;
    final stage = await _pickStage(
      AppLocalizations.of(context).prayerBackToStage,
      [for (var n = 1; n < current; n++) n],
    );
    if (stage != null) await _setStage(stage, 'stage_back');
  }

  Future<void> _graduate() async {
    final next = await _change(
      () => ref.read(tgClientProvider).graduatePrayerJourney(_childId),
      'graduate',
    );
    if (next == null || !mounted) return;
    final l10n = AppLocalizations.of(context);
    final g = next.graduation;
    await showCelebration(
      context,
      emoji: '🎓',
      title: g.title ?? l10n.prayerGraduatedTitle,
      message: g.certificateText ?? l10n.prayerGraduatedTitle,
    );
  }

  Future<void> _stop() async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        content: Text(l10n.prayerStopConfirm(_name)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.prayerStop),
          ),
        ],
      ),
    );
    if (ok == true) {
      await _change(
        () => ref.read(tgClientProvider).stopPrayerJourney(_childId),
        'stop',
      );
    }
  }

  Future<void> _openPending() async {
    unawaited(Analytics.programAction('prayer', 'confirm_open'));
    await Navigator.of(context).push(AppRoutes.pendingMissions());
    if (!mounted) return;
    ref.invalidate(prayerJourneyProvider(_childId));
    refreshProgramsSummary(ref);
  }

  /// The child surface policy keys on the profile's age group, not on the
  /// birth month: a profile still set to 4-6 is refused the habit surface even
  /// when the month already makes the child seven. Unknown (list not loaded)
  /// is given the benefit of the doubt — the lock screen explains a refusal.
  bool get _habitSurfaceAllowed {
    final band = programChildProfile(ref, _childId)?.profile?.ageGroup;
    return band == null || const {'7-9', '10-12', '13-15', '16-18'}.contains(band);
  }

  void _handOver() {
    unawaited(Analytics.programAction('prayer', 'hand_over'));
    Navigator.of(context).push(
      AppRoutes.childModeLock<void>(
        childId: _childId,
        childName: _name,
        // The habit surface carries the prayer card in child mode; every band
        // with a prayer task (7+) is allowed it.
        surface: 'habit',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final enrolment = j.enrolment;
    final children = <Widget>[
      if (j.subtitle != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: ContentText(
            j.subtitle!,
            style: TextStyle(color: context.colors.textSecondary, height: 1.5),
          ),
        ),
    ];

    if (enrolment == null) {
      children.addAll(_notEnrolled(context));
    } else {
      children.addAll(switch (enrolment.track) {
        PrayerTrack.journey => _journey(context, enrolment),
        PrayerTrack.ownership => _ownership(context),
        PrayerTrack.preparation => _preparation(context),
      });
    }
    children.addAll(_about(context));

    return RefreshIndicator(
      onRefresh: () => ref.refresh(prayerJourneyProvider(_childId).future),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          ...children,
          if (enrolment != null) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (enrolment.track == PrayerTrack.journey &&
                    (enrolment.stage ?? 1) > 1)
                  OutlinedButton(
                    onPressed: _busy ? null : _goBack,
                    child: Text(l10n.prayerBackToStage),
                  ),
                if (enrolment.track == PrayerTrack.ownership &&
                    j.allowedTracks.contains(PrayerTrack.journey))
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _chooseStageAndEnrol(restart: true),
                    child: Text(l10n.prayerJourneyInstead),
                  ),
                TextButton(
                  key: const ValueKey('prayer_stop'),
                  onPressed: _busy ? null : _stop,
                  child: Text(l10n.prayerStop),
                ),
              ],
            ),
            if (enrolment.track == PrayerTrack.journey &&
                (enrolment.stage ?? 1) > 1)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  l10n.prayerBackHint,
                  style: TextStyle(
                    color: context.colors.textSecondary,
                    fontSize: 12.5,
                    height: 1.5,
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }

  // ── Not started ──────────────────────────────────────────────────────────

  List<Widget> _notEnrolled(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final eligible = j.eligibleTrack;
    if (eligible == null && j.allowedTracks.isEmpty) {
      return [
        ProgramNote(emoji: '🕌', text: l10n.prayerNotForChild(_name)),
        if (j.bandsText != null)
          ProgramSection(child: ContentText(j.bandsText!)),
      ];
    }
    final trackContent = switch (eligible) {
      PrayerTrack.preparation => j.preparation,
      PrayerTrack.ownership => j.ownership,
      _ => null,
    };
    return [
      if (j.graduatedOn != null)
        ProgramSection(
          tone: SectionTone.highlight,
          emoji: '🎓',
          title: l10n.prayerGraduatedOn(programDate(context, j.graduatedOn!)),
          child: j.graduation.certificateText == null
              ? const SizedBox.shrink()
              : ContentText(j.graduation.certificateText!),
        ),
      if (trackContent != null) _trackCard(context, trackContent),
      if (eligible == PrayerTrack.journey || trackContent == null)
        _stagesOutline(context, expanded: true),
      ProgramSection(
        tone: SectionTone.highlight,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            FilledButton(
              key: const ValueKey('prayer_enrol'),
              onPressed: _busy ? null : () => _enrol(),
              child: Text(
                l10n.prayerStartTrack(
                  trackContent?.title ??
                      j.title ??
                      prayerTrackName(l10n, eligible),
                ),
              ),
            ),
            if (eligible == PrayerTrack.ownership &&
                j.allowedTracks.contains(PrayerTrack.journey)) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: _busy
                    ? null
                    : () => _chooseStageAndEnrol(restart: false),
                child: Text(l10n.prayerJourneyInstead),
              ),
            ],
            if (j.bandsText != null) ...[
              const SizedBox(height: 10),
              ContentText(
                j.bandsText!,
                style: TextStyle(
                  color: c.textSecondary,
                  fontSize: 12.5,
                  height: 1.55,
                ),
              ),
            ],
          ],
        ),
      ),
    ];
  }

  // ── The twelve weeks ─────────────────────────────────────────────────────

  List<Widget> _journey(BuildContext context, PrayerEnrolment enrolment) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final stage = j.stage;
    final adv = j.advancement;
    final total = j.stages.isEmpty ? 6 : j.stages.length;
    final stageNo = enrolment.stage ?? stage?.stage ?? 1;
    return [
      ProgramSection(
        tone: SectionTone.highlight,
        emoji: '🕌',
        title: l10n.prayerStageOf(stageNo, total),
        trailing: enrolment.week == null
            ? null
            : CountBadge(l10n.prayerWeekN(enrolment.week!)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (stage != null)
              ContentText(
                stage.title,
                style: TextStyle(
                  color: c.ink,
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                  height: 1.45,
                ),
              ),
            if (stage?.goal != null) ...[
              const SizedBox(height: 4),
              ContentText(stage!.goal!),
            ],
            if (stage?.journeyMilestoneKey != null)
              ProgramLinkRow(
                emoji: '📔',
                label: l10n.prayerRecordInJourney(_name),
                onTap: () => Navigator.of(context).push(
                  AppRoutes.childJourney(childId: _childId, childName: _name),
                ),
              ),
          ],
        ),
      ),
      if (adv != null && adv.canGraduate)
        ProgramSection(
          tone: SectionTone.highlight,
          emoji: '🎓',
          title: j.graduation.title ?? l10n.prayerGraduatedTitle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (j.graduation.text != null) ContentText(j.graduation.text!),
              const SizedBox(height: 8),
              FilledButton(
                key: const ValueKey('prayer_graduate'),
                onPressed: _busy ? null : _graduate,
                child: Text(l10n.prayerGraduateButton),
              ),
            ],
          ),
        )
      else if (adv != null && adv.advanceSuggested && adv.nextStage != null)
        ProgramSection(
          tone: SectionTone.highlight,
          emoji: '🌱',
          title: l10n.prayerAdvanceTitle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                l10n.prayerAdvanceBody(adv.nextStage!, _name),
                style: TextStyle(color: c.ink, height: 1.6),
              ),
              const SizedBox(height: 8),
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: FilledButton.tonal(
                  key: const ValueKey('prayer_advance'),
                  onPressed: _busy
                      ? null
                      : () => _setStage(adv.nextStage!, 'stage_next'),
                  child: Text(l10n.prayerAdvanceButton(adv.nextStage!)),
                ),
              ),
            ],
          ),
        ),
      ..._tasksAndConfirm(context),
      if (j.coinsConfirmedInStage != null || stage?.covenant != null)
        _covenantCard(
          context,
          stage?.covenant,
          j.coinsConfirmedInStage ?? 0,
          j.covenantTarget,
        ),
      if (stage != null) ..._stageGuide(context, stage),
      _stagesOutline(context, expanded: false),
    ];
  }

  List<Widget> _ownership(BuildContext context) {
    final own = j.ownership;
    return [
      if (own != null) _trackCard(context, own),
      ..._tasksAndConfirm(context),
      if (own != null) ..._stageGuide(context, own),
    ];
  }

  List<Widget> _preparation(BuildContext context) {
    final prep = j.preparation;
    return [if (prep != null) _trackCard(context, prep)];
  }

  // ── Pieces ───────────────────────────────────────────────────────────────

  Widget _trackCard(BuildContext context, PrayerStage track) {
    final c = context.colors;
    return ProgramSection(
      tone: SectionTone.highlight,
      emoji: '🕌',
      title: track.title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (track.goal != null)
            ContentText(
              track.goal!,
              style: TextStyle(
                color: c.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
            ),
          if (track.text != null) ...[
            const SizedBox(height: 6),
            ContentText(track.text!),
          ],
          EvidenceCards(track.evidence),
          for (final a in track.activities) ...[
            const SizedBox(height: 10),
            ContentText(
              a.title,
              style: TextStyle(
                color: c.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
            ),
            if (a.text != null) ContentText(a.text!),
          ],
          if (track.lessonIds.isNotEmpty || track.pathIds.isNotEmpty) ...[
            const SizedBox(height: 8),
            ProgramLinksList(
              links: ProgramLinks(
                lessonIds: track.lessonIds,
                pathIds: track.pathIds,
              ),
              childId: _childId,
              childName: _name,
            ),
          ],
        ],
      ),
    );
  }

  List<Widget> _tasksAndConfirm(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return [
      if (j.pendingConfirmations > 0)
        ProgramSection(
          key: const ValueKey('prayer_pending'),
          tone: SectionTone.warning,
          emoji: '🌙',
          title: l10n.programsPrayerPending(j.pendingConfirmations),
          child: Align(
            alignment: AlignmentDirectional.centerStart,
            child: FilledButton(
              onPressed: _openPending,
              child: Text(l10n.prayerConfirmNow),
            ),
          ),
        ),
      if (j.tasks.isNotEmpty)
        ProgramSection(
          emoji: '✅',
          title: l10n.prayerTasksTitle(_name),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final t in j.tasks) _TaskTile(task: t),
              const SizedBox(height: 4),
              if (_habitSurfaceAllowed)
                FilledButton.tonalIcon(
                  key: const ValueKey('prayer_hand_over'),
                  onPressed: _handOver,
                  icon: const Icon(Icons.child_care_outlined),
                  label: Text(l10n.prayerHandOver(_name)),
                )
              else
                Text(
                  l10n.prayerHandOverNeedsBand(_name),
                  key: const ValueKey('prayer_hand_over_needs_band'),
                  style: TextStyle(color: c.textSecondary, height: 1.55),
                ),
              if (j.rewardPolicy != null) ...[
                const SizedBox(height: 8),
                ContentText(
                  j.rewardPolicy!,
                  style: TextStyle(
                    color: c.textSecondary,
                    fontSize: 12.5,
                    height: 1.55,
                  ),
                ),
              ],
            ],
          ),
        ),
    ];
  }

  Widget _covenantCard(
    BuildContext context,
    PrayerCovenant? covenant,
    int coins,
    int? target,
  ) {
    final l10n = AppLocalizations.of(context);
    final goal = target ?? covenant?.coinsTarget;
    return ProgramSection(
      emoji: '📜',
      title: l10n.prayerCovenantTitle,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (goal != null)
            Text(
              l10n.prayerCovenantProgress(coins, goal),
              style: TextStyle(
                color: context.colors.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
            ),
          if (covenant != null && covenant.examples.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              l10n.prayerCovenantExamples,
              style: TextStyle(
                color: context.colors.textSecondary,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 4),
            ProgramBullets(covenant.examples),
          ],
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton(
              onPressed: () => Navigator.of(context).push(AppRoutes.covenant()),
              child: Text(l10n.prayerSetCovenant),
            ),
          ),
        ],
      ),
    );
  }

  /// The parent's guide for a stage (or the ownership track): what to do,
  /// what to say, how to confirm, and what to do when it is hard going.
  List<Widget> _stageGuide(BuildContext context, PrayerStage stage) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return [
      if (stage.parentAssignments.isNotEmpty)
        ProgramSection(
          emoji: '👣',
          title: l10n.prayerYourPart,
          child: ProgramBullets(stage.parentAssignments),
        ),
      if (stage.encouragement.isNotEmpty)
        ProgramSection(
          emoji: '💬',
          title: l10n.prayerSayToChild(_name),
          child: ProgramBullets(stage.encouragement, marker: '❝'),
        ),
      if (stage.confirmation != null)
        ProgramSection(
          emoji: '🌙',
          title: l10n.prayerHowToConfirm,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (stage.confirmation!.how != null)
                ContentText(stage.confirmation!.how!),
              if (stage.confirmation!.countsWhen != null) ...[
                const SizedBox(height: 6),
                ContentText(
                  stage.confirmation!.countsWhen!,
                  style: TextStyle(color: c.textSecondary, height: 1.55),
                ),
              ],
            ],
          ),
        ),
      if (stage.ifStruggling != null)
        ProgramSection(
          child: Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(bottom: 8),
              title: Text(
                '🤲 ${l10n.prayerIfStruggling}',
                style: TextStyle(color: c.ink, fontWeight: FontWeight.w700),
              ),
              children: [ContentText(stage.ifStruggling!)],
            ),
          ),
        ),
      if (stage.quran.isNotEmpty)
        ProgramSection(
          emoji: '📗',
          title: l10n.programsVerses,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [for (final q in stage.quran) QuranPassage(reference: q)],
          ),
        ),
      if (stage.evidence.isNotEmpty)
        ProgramSection(
          title: l10n.programsEvidenceTitle,
          child: EvidenceCards(stage.evidence),
        ),
      if (stage.lessonIds.isNotEmpty || stage.pathIds.isNotEmpty)
        ProgramSection(
          emoji: '📘',
          title: l10n.prayerLessons,
          child: ProgramLinksList(
            links: ProgramLinks(
              lessonIds: stage.lessonIds,
              pathIds: stage.pathIds,
            ),
            childId: _childId,
            childName: _name,
          ),
        ),
    ];
  }

  Widget _stagesOutline(BuildContext context, {required bool expanded}) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    if (j.stages.isEmpty) return const SizedBox.shrink();
    final current = j.enrolment?.track == PrayerTrack.journey
        ? j.enrolment?.stage
        : null;
    return ProgramSection(
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: expanded,
          tilePadding: EdgeInsets.zero,
          title: Text(
            '🗺️ ${l10n.prayerStagesTitle}',
            style: TextStyle(color: c.ink, fontWeight: FontWeight.w800),
          ),
          children: [
            for (final s in j.stages)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CountBadge('${s.stage}', accent: s.stage == current),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          ContentText(
                            s.title,
                            style: TextStyle(
                              color: c.ink,
                              fontWeight: FontWeight.w700,
                              height: 1.45,
                            ),
                          ),
                          if (s.weekFrom != null && s.weekTo != null)
                            Text(
                              l10n.prayerStageWeeks(s.weekFrom!, s.weekTo!),
                              style: TextStyle(
                                color: c.textSecondary,
                                fontSize: 12.5,
                              ),
                            ),
                          if (s.goal != null) ContentText(s.goal!),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// What the journey stands on — always reachable, folded once it started.
  List<Widget> _about(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final basis = j.basis;
    if (basis == null && j.principles.isEmpty) return const [];
    return [
      ProgramSection(
        child: Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            initiallyExpanded: !j.enrolled,
            tilePadding: EdgeInsets.zero,
            title: Text(
              '📚 ${l10n.prayerBasis}',
              style: TextStyle(color: c.ink, fontWeight: FontWeight.w800),
            ),
            children: [
              if (basis != null) ...[
                ContentText(basis.text),
                EvidenceCards(basis.evidence),
              ],
              if (j.principles.isNotEmpty) ...[
                const SizedBox(height: 12),
                Align(
                  alignment: AlignmentDirectional.centerStart,
                  child: Text(
                    l10n.prayerPrinciples,
                    style: TextStyle(color: c.ink, fontWeight: FontWeight.w800),
                  ),
                ),
                const SizedBox(height: 6),
                ProgramBullets(j.principles),
              ],
            ],
          ),
        ),
      ),
    ];
  }
}

class _TaskTile extends StatelessWidget {
  const _TaskTile({required this.task});
  final PrayerTask task;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: c.surfaceAlt,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ContentText(
            task.title,
            style: TextStyle(
              color: c.ink,
              fontWeight: FontWeight.w800,
              height: 1.45,
            ),
          ),
          if (task.instruction != null) ...[
            const SizedBox(height: 4),
            ContentText(
              task.instruction!,
              style: TextStyle(color: c.textSecondary, height: 1.55),
            ),
          ],
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if (task.today.recorded > 0)
                CountBadge(l10n.prayerTaskToday(task.today.recorded)),
              if (task.thisWeek.recorded > 0)
                CountBadge(l10n.prayerTaskThisWeek(task.thisWeek.recorded)),
              if (task.perWeek != null)
                CountBadge(l10n.prayerTaskGoal(task.perWeek!)),
              if (task.coins > 0)
                CountBadge(
                  '🪙 ${l10n.programsCoins(task.coins)}',
                  accent: true,
                ),
            ],
          ),
        ],
      ),
    );
  }
}
