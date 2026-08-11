/// Home tab — "اليوم". Pure composition over existing providers.
///
/// Ordering is the point of this screen: the primary action ([TodayFocusCard])
/// comes first, then the daily rituals, then stats, then the secondary
/// destinations. It used to be nine equally-weighted full-width cards with the
/// primary action buried fifth, which gave the eye nothing to follow.
///
/// No new business logic — everything reads providers that already
/// power PathsScreen / PathDetailScreen / BadgesScreen.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/app_localizations.dart';

import '../features/home/widgets/home_app_bar.dart';
import '../features/home/widgets/home_community_note.dart';
import '../features/home/widgets/home_shortcuts_grid.dart';
import '../features/home/widgets/home_stats_row.dart';
import '../features/home/widgets/today_focus_card.dart';
import '../features/home/widgets/today_rituals_row.dart';
import '../features/onboarding/providers/onboarding_providers.dart';
import '../features/program/data/badges.dart';
import '../features/program/providers/program_providers.dart';
import '../features/program/providers/progress_providers.dart';
import '../features/referral/pride_invite_card.dart';
import '../features/program/widgets/coach_tip_card.dart';
import '../features/journey/widgets/child_journey_card.dart';
import '../features/coins/coins_providers.dart';
import '../features/shell/root_tab.dart';
import '../theme/app_theme.dart';
import '../theme/design_tokens.dart';
import '../widgets/ui/noor_mascot.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key, required this.onGoToTab, this.focusCardKey});

  /// Switches the root scaffold tab. Always pass a [RootTab] constant — a
  /// hard-coded index here is how both assistant buttons ended up opening the
  /// infant routine tracker.
  final ValueChanged<int> onGoToTab;

  /// Attached to [TodayFocusCard] so the first-run tour can measure it.
  final Key? focusCardKey;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(activeChildProfileProvider);
    final childId = ref.watch(activeChildIdProvider);
    final ageGroup = ref.watch(selectedAgeGroupProvider);
    final asyncBundle =
        childId == null ? null : ref.watch(childProgressProvider(childId));
    final bundle = asyncBundle?.maybeWhen(
      data: (b) => b,
      orElse: () => null,
    );

    // One-shot per build pass: claim the daily login reward + credit any
    // newly-unlocked badges. Both are idempotent (once/day, once/badge).
    final earnedBadgeIds = computeBadges(bundle)
        .where((b) => b.earned)
        .map((b) => b.id)
        .toList();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(coinsProvider.notifier).claimDaily();
      if (earnedBadgeIds.isNotEmpty) {
        ref.read(coinsProvider.notifier).creditBadges(earnedBadgeIds);
      }
    });

    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: const HomeAppBar(),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          Row(
            children: [
              const NoorMascot(size: 44)
                  .animate()
                  .fadeIn(duration: Dt.slow)
                  .scale(
                    begin: const Offset(.7, .7),
                    curve: Curves.easeOutBack,
                    duration: Dt.slow,
                  ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  profile == null
                      ? l10n.greetingPeace
                      : l10n.greetingWithName(profile.name),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: AppTheme.textSecondary,
                        fontWeight: FontWeight.w600,
                        height: 1.4,
                      ),
                ).animate().fadeIn(duration: Dt.base),
              ),
            ],
          ),
          const SizedBox(height: 16),
          TodayFocusCard(
            key: focusCardKey,
            bundle: bundle,
            ageGroup: ageGroup,
            onStartFirstPath: () => onGoToTab(RootTab.learn),
          ),
          const SizedBox(height: 16),
          TodayRitualsRow(ageGroup: ageGroup),
          const SizedBox(height: 16),
          HomeStatsRow(bundle: bundle),
          const SizedBox(height: 20),
          CoachTipCard(onAsk: () => onGoToTab(RootTab.assistant)),
          const SizedBox(height: 20),
          const HomeShortcutsGrid(),
          const SizedBox(height: 20),
          const ChildJourneyCard(),
          const SizedBox(height: 20),
          // §6.4 — the referral ask fires only at a pride moment (≥7-day
          // streak), once per 7-day tier. Last, so it never outranks the
          // parent's own next step.
          PrideInviteCard(streakDays: bundle?.dailyLoginStreak ?? 0),
          // Type, not a card, and last: a closing "you're not alone" that the
          // eye reaches only after the day's work.
          const HomeCommunityNote(),
        ],
      ),
    );
  }
}
