/// «برامج الأسرة» — every family program, per child (`GET /api/programs`).
///
/// One family-wide Ramadan card (the calendar is the family's), then one card
/// per child: their part in Ramadan, their Prayer Journey, their milestones.
/// The API returns child ids only; names come from the device's child list.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/loading_view.dart';
import '../../program/providers/progress_providers.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';
import '../widgets/programs_text.dart';

class ProgramsScreen extends ConsumerWidget {
  const ProgramsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final overview = ref.watch(programsOverviewProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.programsTitle)),
      body: overview.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) => ProgramErrorView(
          error: e,
          onRetry: () => ref.invalidate(programsOverviewProvider),
        ),
        data: (o) => o == null
            ? ProgramNote(emoji: '🌙', text: l10n.programsUnavailable)
            : RefreshIndicator(
                onRefresh: () => ref.refresh(programsOverviewProvider.future),
                child: _ProgramsList(overview: o),
              ),
      ),
    );
  }
}

class _ProgramsList extends ConsumerWidget {
  const _ProgramsList({required this.overview});
  final ProgramsOverview overview;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final activeId = ref.watch(activeChildIdProvider);
    final children = [...overview.children]
      ..sort(
        (a, b) =>
            (a.childId == activeId ? 0 : 1) - (b.childId == activeId ? 0 : 1),
      );
    final ramadanChild = children.isEmpty ? null : children.first.childId;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        Text(
          l10n.programsIntro,
          style: TextStyle(color: c.textSecondary, fontSize: 14, height: 1.6),
        ),
        const SizedBox(height: 16),
        if (overview.ramadan.isActive && ramadanChild != null)
          _RamadanFamilyCard(ramadan: overview.ramadan, childId: ramadanChild),
        if (children.isEmpty)
          ProgramNote(
            emoji: '👨‍👩‍👧',
            text: l10n.programsNoChildren,
            action: l10n.addChild,
            onAction: () => Navigator.of(context).push(AppRoutes.addChild()),
          ),
        for (final child in children)
          _ChildProgramsCard(child: child, ramadan: overview.ramadan),
      ],
    );
  }
}

/// The family's calendar: one card, whoever's part you open.
class _RamadanFamilyCard extends StatelessWidget {
  const _RamadanFamilyCard({required this.ramadan, required this.childId});
  final RamadanOverview ramadan;
  final int childId;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final line = ramadanStatusLine(context, ramadan);
    final season = ramadan.season;
    return ProgramSection(
      title: l10n.programsRamadanTitle,
      emoji: '🌙',
      tone: SectionTone.highlight,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (line != null)
            ContentText(
              line,
              style: TextStyle(
                color: context.colors.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
            ),
          if (ramadan.state == RamadanState.upcoming && season != null) ...[
            const SizedBox(height: 4),
            Text(
              season.isEstimate
                  ? l10n.ramadanStartsOnEstimate(
                      programDate(context, season.startsOn),
                    )
                  : l10n.ramadanStartsOn(programDate(context, season.startsOn)),
              style: TextStyle(
                color: context.colors.textSecondary,
                fontSize: 13,
                height: 1.5,
              ),
            ),
          ],
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.tonal(
                onPressed: () {
                  unawaited(Analytics.programAction('ramadan', 'open'));
                  Navigator.of(context).push(AppRoutes.ramadan(childId));
                },
                child: Text(l10n.programsOpenRamadan),
              ),
              if (ramadan.recapAvailable)
                OutlinedButton(
                  onPressed: () {
                    unawaited(Analytics.programAction('ramadan', 'recap'));
                    Navigator.of(context).push(AppRoutes.ramadanRecap());
                  },
                  child: Text(l10n.ramadanRecapOpen),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ChildProgramsCard extends ConsumerWidget {
  const _ChildProgramsCard({required this.child, required this.ramadan});
  final ChildPrograms child;
  final RamadanOverview ramadan;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final profile = programChildProfile(ref, child.childId);
    final name = profile?.name ?? l10n.childFallbackName;
    final prayer = child.prayer;
    final showPrayer = prayer.eligibleTrack != null || prayer.enrolled;

    return ProgramSection(
      emoji: profile?.avatarEmoji ?? '🧒',
      title: name,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (ramadan.isActive)
            ProgramLinkRow(
              emoji: '🌙',
              label: l10n.programsRamadanRole(name),
              subtitle: ramadanStatusLine(context, ramadan),
              onTap: () {
                unawaited(Analytics.programAction('ramadan', 'open'));
                Navigator.of(context).push(AppRoutes.ramadan(child.childId));
              },
            ),
          if (showPrayer)
            ProgramLinkRow(
              emoji: '🕌',
              label: l10n.programsPrayerTitle,
              subtitle: prayerStatusLine(l10n, prayer),
              badge: prayer.pendingConfirmations > 0
                  ? '${prayer.pendingConfirmations}'
                  : null,
              onTap: () {
                unawaited(Analytics.programAction('prayer', 'open'));
                Navigator.of(
                  context,
                ).push(AppRoutes.prayerJourney(child.childId));
              },
            ),
          if (child.milestonesServed)
            ProgramLinkRow(
              emoji: '🧭',
              label: l10n.programsMilestonesTitle,
              subtitle: child.milestonesDue > 0
                  ? l10n.programsMilestonesDue(child.milestonesDue)
                  : (child.needsBirthMonth
                        ? l10n.programsMilestonesAddBirthMonth(name)
                        : l10n.programsMilestonesBrowse),
              badge: child.milestonesDue > 0 ? '${child.milestonesDue}' : null,
              onTap: () {
                unawaited(Analytics.programAction('milestones', 'open'));
                Navigator.of(context).push(AppRoutes.milestones(child.childId));
              },
            ),
          if (!showPrayer && !ramadan.isActive)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                l10n.programsRamadanOffSeason,
                style: TextStyle(
                  color: c.textSecondary,
                  fontSize: 12.5,
                  height: 1.5,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
