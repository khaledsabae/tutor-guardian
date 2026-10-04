/// The proactive milestones — school entry, the age of discernment, the first
/// prayer lessons at seven, first fasting, puberty, the first phone…
/// (`GET /api/children/{id}/milestones`).
///
/// Every text here is for the parent; none of it is ever shown in child mode.
/// Without a birth month there is no timing and no reminder: the cards still
/// appear for the child's age band (the "library"), under a prompt to add the
/// month. A gender-specific card (puberty) is replaced by a prompt to complete
/// the profile until the gender is known.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/loading_view.dart';
import '../../program/providers/settings_providers.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';

class MilestonesScreen extends ConsumerWidget {
  const MilestonesScreen({super.key, required this.childId});
  final int childId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final list = ref.watch(milestonesProvider(childId));
    final child = programChildProfile(ref, childId);
    final name = child?.name ?? l10n.childFallbackName;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.milestonesTitle(name))),
      body: list.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) => ProgramErrorView(
          error: e,
          onRetry: () => ref.invalidate(milestonesProvider(childId)),
        ),
        data: (m) => RefreshIndicator(
          onRefresh: () => ref.refresh(milestonesProvider(childId).future),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            physics: const AlwaysScrollableScrollPhysics(),
            children: [
              if (m.needsBirthMonth)
                _CompleteProfile(
                  key: const ValueKey('milestones_needs_birth_month'),
                  childId: childId,
                  text: l10n.milestonesNeedsBirthMonth(name),
                ),
              if (m.needsGender)
                _CompleteProfile(
                  key: const ValueKey('milestones_needs_gender'),
                  childId: childId,
                  text: l10n.milestonesNeedsGender(name),
                ),
              if (m.due.isNotEmpty) ...[
                _Heading(l10n.milestonesDue),
                for (final x in m.due)
                  _MilestoneTile(
                    childId: childId,
                    milestone: x,
                    highlight: true,
                  ),
              ],
              if (m.upcoming.isNotEmpty) ...[
                _Heading(l10n.milestonesUpcoming),
                for (final x in m.upcoming)
                  _MilestoneTile(childId: childId, milestone: x),
              ],
              if (m.library.isNotEmpty) ...[
                _Heading(l10n.milestonesLibrary(name)),
                for (final x in m.library)
                  _MilestoneTile(childId: childId, milestone: x),
              ],
              if (m.past.isNotEmpty) ...[
                _Heading(l10n.milestonesPast),
                for (final x in m.past)
                  _MilestoneTile(childId: childId, milestone: x),
              ],
              if (m.isEmpty)
                ProgramNote(emoji: '🧭', text: l10n.milestonesEmpty),
              if (m.alertPolicy != null)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: ContentText(
                    m.alertPolicy!,
                    style: TextStyle(
                      color: context.colors.textSecondary,
                      fontSize: 12.5,
                      height: 1.55,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Heading extends StatelessWidget {
  const _Heading(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 8, 4, 8),
    child: Semantics(
      header: true,
      child: Text(
        text,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w800,
          color: context.colors.textSecondary,
        ),
      ),
    ),
  );
}

/// "Add the birth month" / "set the gender" — opens the child's profile.
class _CompleteProfile extends ConsumerWidget {
  const _CompleteProfile({
    super.key,
    required this.childId,
    required this.text,
  });
  final int childId;
  final String text;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final profile = programChildProfile(ref, childId)?.profile;
    return ProgramSection(
      tone: SectionTone.highlight,
      emoji: '🎂',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(text, style: TextStyle(color: context.colors.ink, height: 1.6)),
          if (profile != null)
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton(
                onPressed: () async {
                  unawaited(
                    Analytics.programAction('milestones', 'complete_profile'),
                  );
                  final container = programsContainerOf(context);
                  final saved = await Navigator.of(
                    context,
                  ).push(AppRoutes.editChild(profile));
                  if (saved == true) {
                    container.invalidate(milestonesProvider(childId));
                    container.invalidate(childrenListProvider);
                    refreshProgramsSummary(container);
                  }
                },
                child: Text(l10n.milestonesCompleteProfile),
              ),
            ),
        ],
      ),
    );
  }
}

class _MilestoneTile extends StatelessWidget {
  const _MilestoneTile({
    required this.childId,
    required this.milestone,
    this.highlight = false,
  });
  final int childId;
  final Milestone milestone;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final due = milestone.dueOn;
    return ProgramSection(
      tone: highlight ? SectionTone.highlight : SectionTone.plain,
      child: ProgramLinkRow(
        emoji: milestone.medical ? '🩺' : '🧭',
        label: milestone.title,
        subtitle: [
          if (milestone.alertBody != null) milestone.alertBody!,
          if (due != null) l10n.milestonesDueOn(programDate(context, due)),
        ].join('\n'),
        onTap: () {
          unawaited(Analytics.programAction('milestones', 'detail'));
          Navigator.of(
            context,
          ).push(AppRoutes.milestoneDetail(childId, milestone.key));
        },
      ),
    );
  }
}

/// One milestone: its 3–5 cards, the red flags (visible, for medical ones),
/// and where to go next. Also the landing screen of the milestone push.
class MilestoneDetailScreen extends ConsumerStatefulWidget {
  const MilestoneDetailScreen({
    super.key,
    required this.childId,
    required this.milestoneKey,
  });
  final int childId;
  final String milestoneKey;

  @override
  ConsumerState<MilestoneDetailScreen> createState() =>
      _MilestoneDetailScreenState();
}

class _MilestoneDetailScreenState extends ConsumerState<MilestoneDetailScreen> {
  bool _redirected = false;

  /// Not this child's card (other gender, unknown key, a stale push): open
  /// the list instead of an error. A child that is not on this device opens
  /// the programs overview.
  void _fallBack(Object error) {
    if (_redirected || error is! TgApiError || error.statusCode != 404) return;
    _redirected = true;
    final route = error.code == 'child_not_found'
        ? AppRoutes.programs()
        : AppRoutes.milestones(widget.childId);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) Navigator.of(context).pushReplacement(route);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final key = (widget.childId, widget.milestoneKey);
    final detail = ref.watch(milestoneDetailProvider(key));
    final name =
        programChildProfile(ref, widget.childId)?.name ??
        l10n.childFallbackName;
    return Scaffold(
      appBar: AppBar(
        title: Text(detail.valueOrNull?.title ?? l10n.programsMilestonesTitle),
      ),
      body: detail.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) {
          _fallBack(e);
          return ProgramErrorView(
            error: e,
            onRetry: () => ref.invalidate(milestoneDetailProvider(key)),
          );
        },
        data: (m) => _MilestoneBody(
          milestone: m,
          childId: widget.childId,
          childName: name,
        ),
      ),
    );
  }
}

class _MilestoneBody extends StatelessWidget {
  const _MilestoneBody({
    required this.milestone,
    required this.childId,
    required this.childName,
  });
  final Milestone milestone;
  final int childId;
  final String childName;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final m = milestone;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      children: [
        if (m.alertTitle != null || m.alertBody != null)
          ProgramSection(
            tone: SectionTone.highlight,
            emoji: m.medical ? '🩺' : '🧭',
            title: m.alertTitle,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (m.alertBody != null) ContentText(m.alertBody!),
                if (m.dueOn != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    l10n.milestonesDueOn(programDate(context, m.dueOn!)),
                    style: TextStyle(color: c.textSecondary, fontSize: 13),
                  ),
                ],
              ],
            ),
          ),
        for (final card in m.cards)
          ProgramSection(title: card.title, child: ContentText(card.body)),
        if (m.redFlags.isNotEmpty)
          ProgramSection(
            key: const ValueKey('milestone_red_flags'),
            tone: SectionTone.danger,
            emoji: '🚩',
            title: l10n.milestonesRedFlags,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ProgramBullets(m.redFlags),
                if (m.medical)
                  Text(
                    l10n.milestonesMedicalNote,
                    style: TextStyle(color: c.ink, fontSize: 12.5, height: 1.5),
                  ),
              ],
            ),
          ),
        if (m.quran.isNotEmpty)
          ProgramSection(
            emoji: '📗',
            title: l10n.programsVerses,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [for (final q in m.quran) QuranPassage(reference: q)],
            ),
          ),
        if (m.evidence.isNotEmpty)
          ProgramSection(
            title: l10n.programsEvidenceTitle,
            child: EvidenceCards(m.evidence),
          ),
        if (!m.links.isEmpty)
          ProgramSection(
            emoji: '➡️',
            title: l10n.milestonesLinks,
            child: ProgramLinksList(
              links: m.links,
              childId: childId,
              childName: childName,
            ),
          ),
      ],
    );
  }
}
