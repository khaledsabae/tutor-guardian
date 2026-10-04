/// «رمضان العائلة» for one child (`GET /api/children/{id}/ramadan/today`).
///
/// What the screen shows follows the family's calendar:
///   upcoming  the countdown, how to get ready, each child's fasting step
///   ramadan   today's card (challenge, the child's part, the note, the Quran
///             portion, tonight's story, the family's «تمّ»), the fasting
///             step, and every other day of the month
///   eid       the day's activities and the «رمضان عائلتنا» card
///   after     the four bridge weeks and the habits worth keeping
///   off_season a short goodbye, and last season's card if there is one
/// The family challenge and the marks are the family's; the part, the fasting
/// step and the ladder are the child's — the switcher on top changes child.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/loading_view.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';
import '../widgets/ramadan_widgets.dart';

class RamadanScreen extends ConsumerStatefulWidget {
  const RamadanScreen({super.key, required this.childId});
  final int childId;

  @override
  ConsumerState<RamadanScreen> createState() => _RamadanScreenState();
}

class _RamadanScreenState extends ConsumerState<RamadanScreen> {
  late int _childId = widget.childId;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final today = ref.watch(ramadanTodayProvider(_childId));
    final data = today.valueOrNull;
    final season = data?.season;
    final canSet = season != null && data!.state != RamadanState.offSeason;

    return Scaffold(
      appBar: AppBar(
        title: Text(data?.title ?? l10n.programsRamadanTitle),
        actions: [
          if (canSet)
            IconButton(
              tooltip: l10n.ramadanSettingsTitle,
              icon: const Icon(Icons.nightlight_round_outlined),
              onPressed: () => showRamadanSettingsSheet(context, season),
            ),
        ],
      ),
      body: today.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) => ProgramErrorView(
          error: e,
          onRetry: () => ref.invalidate(ramadanTodayProvider(_childId)),
        ),
        data: (t) => RefreshIndicator(
          onRefresh: () => ref.refresh(ramadanTodayProvider(_childId).future),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            physics: const AlwaysScrollableScrollPhysics(),
            children: [
              _ChildSwitcher(
                selected: _childId,
                onSelected: (id) => setState(() => _childId = id),
              ),
              if (t.subtitle != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: ContentText(
                    t.subtitle!,
                    style: TextStyle(
                      color: context.colors.textSecondary,
                      height: 1.5,
                    ),
                  ),
                ),
              ..._stateBody(context, t),
              if (t.bandsText != null) _WhoSeesWhat(text: t.bandsText!),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _stateBody(BuildContext context, RamadanToday t) {
    final l10n = AppLocalizations.of(context);
    final name =
        programChildProfile(ref, _childId)?.name ?? l10n.childFallbackName;
    final fasting = t.fasting;
    final fastingCard = fasting == null
        ? null
        : FastingSummaryCard(
            childId: _childId,
            childName: name,
            fasting: fasting,
            inMonth: t.state == RamadanState.ramadan,
          );
    switch (t.state) {
      case RamadanState.upcoming:
        return [
          _UpcomingHeader(today: t),
          if (t.kickoff != null) _KickoffCard(kickoff: t.kickoff!),
          ?fastingCard,
        ];
      case RamadanState.ramadan:
        final content = t.content;
        return [
          if (content != null)
            RamadanDayCard(
              childId: _childId,
              childName: name,
              content: content,
              marks: t.marks,
              markable: t.marks != null,
            ),
          if (t.day == 29) _EidTomorrowCard(season: t.season),
          ?fastingCard,
          if (t.season != null)
            _DayStrip(childId: _childId, season: t.season!, today: t.day),
          _RecapLink(soFar: true),
        ];
      case RamadanState.eid:
        return [
          if (t.eid != null) _EidCard(eid: t.eid!, childName: name),
          _RecapLink(soFar: false, prominent: true),
          if (t.season != null)
            _DayStrip(childId: _childId, season: t.season!, today: null),
        ];
      case RamadanState.after:
        return [
          if (t.after != null) _AfterCard(after: t.after!, childId: _childId),
          if (t.recapAvailable) _RecapLink(soFar: false),
          if (t.season != null)
            _DayStrip(childId: _childId, season: t.season!, today: null),
        ];
      case RamadanState.offSeason:
        return [
          ProgramNote(emoji: '🌙', text: l10n.ramadanOffSeasonBody),
          if (t.recapAvailable) _RecapLink(soFar: false),
        ];
    }
  }
}

/// Chips to move between the family's children (the day's part is per child).
class _ChildSwitcher extends ConsumerWidget {
  const _ChildSwitcher({required this.selected, required this.onSelected});
  final int selected;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ids =
        ref
            .watch(programsOverviewProvider)
            .valueOrNull
            ?.children
            .map((c) => c.childId)
            .toList() ??
        const <int>[];
    if (ids.length < 2) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final id in ids)
            ChoiceChip(
              label: Text(
                programChildProfile(ref, id)?.name ?? l10n.childFallbackName,
              ),
              selected: id == selected,
              onSelected: (_) => onSelected(id),
            ),
        ],
      ),
    );
  }
}

class _UpcomingHeader extends StatelessWidget {
  const _UpcomingHeader({required this.today});
  final RamadanToday today;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final season = today.season;
    final days = today.daysUntilStart;
    return ProgramSection(
      tone: SectionTone.highlight,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const ExcludeSemantics(
            child: Text('🌙', style: TextStyle(fontSize: 40)),
          ),
          if (days != null)
            Text(
              l10n.ramadanCountdown(days),
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
                color: c.ink,
              ),
            ),
          if (season != null) ...[
            const SizedBox(height: 4),
            Text(
              season.isEstimate
                  ? l10n.ramadanStartsOnEstimate(
                      programDate(context, season.startsOn),
                    )
                  : l10n.ramadanStartsOn(programDate(context, season.startsOn)),
              style: TextStyle(color: c.textSecondary, height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}

class _KickoffCard extends StatelessWidget {
  const _KickoffCard({required this.kickoff});
  final RamadanKickoff kickoff;

  @override
  Widget build(BuildContext context) {
    return ProgramSection(
      title: kickoff.title,
      emoji: '📝',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (kickoff.text != null) ...[
            ContentText(kickoff.text!),
            const SizedBox(height: 10),
          ],
          ProgramBullets(kickoff.setupSteps, numbered: true),
        ],
      ),
    );
  }
}

/// Day 29, from the afternoon: if Eid was announced for tomorrow, the family
/// sets the month to 29 days so the program reaches Eid with them.
class _EidTomorrowCard extends ConsumerWidget {
  const _EidTomorrowCard({required this.season});
  final RamadanSeason? season;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = ref.watch(programsClockProvider)();
    final s = season;
    if (s == null || s.days != 30 || now.hour < 15) {
      return const SizedBox.shrink();
    }
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      title: l10n.ramadanEidTomorrowTitle,
      emoji: '🌙',
      tone: SectionTone.highlight,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            l10n.ramadanEidTomorrowBody,
            style: TextStyle(color: context.colors.ink, height: 1.6),
          ),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton(
              onPressed: () => showRamadanSettingsSheet(context, s),
              child: Text(l10n.ramadanSettingsTitle),
            ),
          ),
        ],
      ),
    );
  }
}

/// Every day of the month — tomorrow may need something bought today, and
/// yesterday's «تمّ» may have been forgotten. No day is marked as missed.
class _DayStrip extends StatelessWidget {
  const _DayStrip({
    required this.childId,
    required this.season,
    required this.today,
  });
  final int childId;
  final RamadanSeason season;
  final int? today;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      title: l10n.ramadanOtherDays,
      emoji: '🗓️',
      child: Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          for (var d = 1; d <= season.days; d++)
            ChoiceChip(
              key: ValueKey('ramadan_day_$d'),
              label: Text('$d'),
              selected: d == today,
              onSelected: (_) {
                unawaited(Analytics.programAction('ramadan', 'day'));
                Navigator.of(context).push(AppRoutes.ramadanDay(childId, d));
              },
            ),
        ],
      ),
    );
  }
}

class _RecapLink extends StatelessWidget {
  const _RecapLink({required this.soFar, this.prominent = false});
  final bool soFar;
  final bool prominent;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      tone: prominent ? SectionTone.highlight : SectionTone.plain,
      child: ProgramLinkRow(
        emoji: '🤍',
        label: soFar ? l10n.ramadanSoFar : l10n.ramadanRecapOpen,
        onTap: () {
          unawaited(Analytics.programAction('ramadan', 'recap'));
          Navigator.of(context).push(AppRoutes.ramadanRecap());
        },
      ),
    );
  }
}

class _EidCard extends StatelessWidget {
  const _EidCard({required this.eid, required this.childName});
  final RamadanEid eid;
  final String childName;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ProgramSection(
          title: eid.title,
          emoji: '🎉',
          tone: SectionTone.highlight,
          child: ProgramBullets(eid.activities),
        ),
        if (eid.variant != null)
          ProgramSection(
            title: l10n.ramadanChildPart(childName),
            emoji: '🧒',
            child: ContentText(eid.variant!.text),
          ),
        if (eid.parentNote != null)
          ProgramSection(
            title: l10n.ramadanParentNote,
            emoji: '💬',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ContentText(eid.parentNote!.text),
                EvidenceCards(eid.parentNote!.evidence),
              ],
            ),
          ),
        if (!eid.quran.isEmpty)
          ProgramSection(
            title: l10n.ramadanWirdTitle,
            emoji: '📗',
            child: RamadanQuranBlock(quran: eid.quran),
          ),
        if (eid.evidence.isNotEmpty && eid.parentNote == null)
          ProgramSection(
            title: l10n.programsEvidenceTitle,
            child: EvidenceCards(eid.evidence),
          ),
      ],
    );
  }
}

class _AfterCard extends StatelessWidget {
  const _AfterCard({required this.after, required this.childId});
  final RamadanAfter after;
  final int childId;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final week = after.week;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ProgramSection(
          title: after.title,
          emoji: '🌱',
          tone: SectionTone.highlight,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (after.text != null) ContentText(after.text!),
              EvidenceCards(after.evidence),
            ],
          ),
        ),
        if (week != null)
          ProgramSection(
            title: l10n.ramadanAfterThisWeek,
            emoji: '📌',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ContentText(
                  week.title,
                  style: TextStyle(
                    color: c.ink,
                    fontWeight: FontWeight.w800,
                    height: 1.5,
                  ),
                ),
                if (week.text != null) ...[
                  const SizedBox(height: 4),
                  ContentText(week.text!),
                ],
              ],
            ),
          ),
        if (after.keepHabits.isNotEmpty)
          ProgramSection(
            title: l10n.ramadanAfterHabits,
            emoji: '🔁',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final h in after.keepHabits)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ContentText(
                          h.title,
                          style: TextStyle(
                            color: c.ink,
                            fontWeight: FontWeight.w700,
                            height: 1.5,
                          ),
                        ),
                        if (h.text != null) ContentText(h.text!),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        if (after.weeks.length > 1)
          ProgramSection(
            title: l10n.ramadanAfterWeeks,
            emoji: '🗓️',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final w in after.weeks)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ContentText(
                          w.title,
                          style: TextStyle(
                            color: c.ink,
                            fontWeight: FontWeight.w700,
                            height: 1.5,
                          ),
                        ),
                        if (w.text != null) ContentText(w.text!),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        if (!after.links.isEmpty)
          ProgramSection(
            title: l10n.ramadanAfterLinks,
            emoji: '➡️',
            child: ProgramLinksList(links: after.links, childId: childId),
          ),
      ],
    );
  }
}

class _WhoSeesWhat extends StatelessWidget {
  const _WhoSeesWhat({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: EdgeInsets.zero,
          childrenPadding: const EdgeInsets.only(bottom: 8),
          title: Text(
            l10n.ramadanWhoSeesWhat,
            style: TextStyle(
              color: context.colors.ink,
              fontWeight: FontWeight.w700,
            ),
          ),
          children: [ContentText(text)],
        ),
      ),
    );
  }
}
