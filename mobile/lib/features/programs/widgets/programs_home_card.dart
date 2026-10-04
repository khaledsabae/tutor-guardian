/// The «برامج الأسرة» entry on «اليوم» — below the three blocks, never above.
///
/// A card, not a fourth numbered stop: the three blocks stay the page's three
/// stops (they answered «مش عارف أبدأ منين»). Like every other optional card
/// on Today it renders nothing while loading, on any failure, and on a server
/// without the programs (`GET /api/programs` → 404) — it can only ever add a
/// way in, never an error.
///
/// What it says is about the active child: the family's Ramadan day, where the
/// child is on the Prayer Journey, and a milestone that is due. Each line opens
/// its program; the card itself opens the programs list.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../providers/programs_providers.dart';
import 'programs_text.dart';

class ProgramsHomeCard extends ConsumerStatefulWidget {
  const ProgramsHomeCard({super.key});

  @override
  ConsumerState<ProgramsHomeCard> createState() => _ProgramsHomeCardState();
}

class _ProgramsHomeCardState extends ConsumerState<ProgramsHomeCard>
    with WidgetsBindingObserver {
  DateTime _fetchedOn = DateTime.now();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  /// Today is a long-lived tab. Coming back on another day (the Ramadan day
  /// turns at the family's midnight), or after a failed fetch, asks again.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) return;
    final now = DateTime.now();
    final newDay =
        now.day != _fetchedOn.day || now.difference(_fetchedOn).inHours >= 24;
    if (newDay || ref.read(programsOverviewProvider).hasError) {
      _fetchedOn = now;
      ref.invalidate(programsOverviewProvider);
    }
  }

  void _open(Route<void> route, String program) {
    unawaited(Analytics.todayBlockTapped('programs', program));
    Navigator.of(context).push(route);
  }

  @override
  Widget build(BuildContext context) {
    final overview = ref.watch(programsOverviewProvider).valueOrNull;
    if (overview == null) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final profile = ref.watch(activeChildProfileProvider);
    final child =
        overview.forChild(profile?.id) ??
        (overview.children.isEmpty ? null : overview.children.first);
    final name = (profile != null && profile.id == child?.childId)
        ? profile.name
        : (programChildProfile(ref, child?.childId ?? -1)?.name ??
              l10n.childFallbackName);

    final lines = <_Line>[];
    final ramadanLine = ramadanStatusLine(context, overview.ramadan);
    if (child != null && overview.ramadan.isActive && ramadanLine != null) {
      lines.add(
        _Line(
          '🌙',
          ramadanLine,
          () => _open(AppRoutes.ramadan(child.childId), 'ramadan'),
        ),
      );
    }
    final prayer = child?.prayer;
    if (child != null &&
        prayer != null &&
        (prayer.eligibleTrack != null || prayer.enrolled)) {
      lines.add(
        _Line(
          '🕌',
          prayer.enrolled
              ? '${l10n.programsPrayerTitle}: ${prayerStatusLine(l10n, prayer)}'
              : l10n.programsPrayerStartWith(name),
          () => _open(AppRoutes.prayerJourney(child.childId), 'prayer'),
        ),
      );
    }
    if (child != null && (child.milestonesDue > 0 || child.needsBirthMonth)) {
      lines.add(
        _Line(
          '🧭',
          child.milestonesDue > 0
              ? l10n.programsMilestonesDueFor(child.milestonesDue, name)
              : l10n.programsMilestonesAddBirthMonth(name),
          () => _open(AppRoutes.milestones(child.childId), 'milestones'),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Material(
        key: const ValueKey('programs_home_card'),
        color: c.surface,
        borderRadius: BorderRadius.circular(Dt.rCard),
        child: InkWell(
          borderRadius: BorderRadius.circular(Dt.rCard),
          onTap: () => _open(AppRoutes.programs(), 'open'),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const ExcludeSemantics(
                      child: Text('✨', style: TextStyle(fontSize: 20)),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        l10n.programsTitle,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: c.ink,
                        ),
                      ),
                    ),
                    const DirectionalChevron(),
                  ],
                ),
                const SizedBox(height: 8),
                if (lines.isEmpty)
                  Text(
                    l10n.programsHomeIntro,
                    style: TextStyle(
                      color: c.textSecondary,
                      fontSize: 13.5,
                      height: 1.55,
                    ),
                  )
                else
                  for (final line in lines.take(3))
                    InkWell(
                      borderRadius: BorderRadius.circular(10),
                      onTap: line.onTap,
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(
                          minHeight: Dt.minTouch,
                        ),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Row(
                            children: [
                              ExcludeSemantics(
                                child: Text(
                                  line.emoji,
                                  style: const TextStyle(fontSize: 18),
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  line.text,
                                  style: TextStyle(
                                    color: c.ink,
                                    fontSize: 14,
                                    height: 1.5,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Line {
  const _Line(this.emoji, this.text, this.onTap);
  final String emoji;
  final String text;
  final VoidCallback onTap;
}
