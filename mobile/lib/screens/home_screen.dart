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
import '../features/parent_day/child_day_card.dart';
import '../features/whats_new/widgets/whats_new_card.dart';

import '../core/app_routes.dart';

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
          const SizedBox(height: 12),
          // Prominent Child Profile Switcher
          _ActiveChildBanner(profile: profile),
          const SizedBox(height: 16),
          // Above the focus card only in the sense of being read first; it
          // renders nothing at all except in the one launch after an update,
          // so on every other day the focus card is still the top of the page.
          const WhatsNewCard(),
          TodayFocusCard(
            key: focusCardKey,
            bundle: bundle,
            ageGroup: ageGroup,
            onStartFirstPath: () => onGoToTab(RootTab.learn),
          ),
          const SizedBox(height: 16),
          // Featured Games & Interactive Quizzes Quick Launch Strip
          const _QuickGamesCard(),
          const SizedBox(height: 16),
          TodayRitualsRow(ageGroup: ageGroup),
          const SizedBox(height: 16),
          HomeStatsRow(bundle: bundle),
          const SizedBox(height: 16),
          // The child's day. Plan item 2.4 puts this in the «اليوم» tab; what
          // shipped was a button on the routine screen, two taps deeper and
          // down a path a parent takes only when already intending to look.
          // The card hides itself when there is nothing to say, so a family
          // not using the child surface never sees it.
          const ChildDayCard(),
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

class _ActiveChildBanner extends StatelessWidget {
  const _ActiveChildBanner({required this.profile});

  final ActiveChildProfile? profile;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final l10n = AppLocalizations.of(context);

    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF131F1C) : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : AppTheme.primary.withValues(alpha: 0.12),
          width: 1,
        ),
        boxShadow: Dt.cardShadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => Navigator.of(context).push(AppRoutes.childrenList()),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    profile?.avatarEmoji ?? '👶',
                    style: const TextStyle(fontSize: 20),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              profile != null
                                  ? profile!.name
                                  : l10n.activeChildLabel,
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 14,
                                color: AppTheme.textPrimary,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (profile != null) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppTheme.accent.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                profile!.ageGroup,
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.accent,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        profile != null
                            ? 'اضغط للتبديل أو إضافة طفل آخر'
                            : 'اضغط لاختيار أو إضافة طفل لمتابعة مساره',
                        style: TextStyle(
                          fontSize: 11,
                          color: AppTheme.textMuted,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                Icon(
                  Icons.swap_horiz_rounded,
                  color: AppTheme.primary,
                  size: 22,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _QuickGamesCard extends StatelessWidget {
  const _QuickGamesCard();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isDark
              ? [const Color(0xFF131F1C), const Color(0xFF1C2D29)]
              : [const Color(0xFF0F766E), const Color(0xFF044E46)],
          begin: AlignmentDirectional.topStart,
          end: AlignmentDirectional.bottomEnd,
        ),
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF0F766E).withValues(alpha: 0.22),
            blurRadius: 14,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: () => Navigator.of(context).push(AppRoutes.games()),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(9),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.16),
                    shape: BoxShape.circle,
                  ),
                  child: const Text('🎮', style: TextStyle(fontSize: 22)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      Text(
                        'الألعاب والمسابقات التعليمية',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'ألعاب تفاعلية ومسابقات قيم وتربية لطفلك',
                        style: TextStyle(
                          color: Color(0xFFCCFBF1),
                          fontSize: 11.5,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF59E0B),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text(
                    'العب الآن',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
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
