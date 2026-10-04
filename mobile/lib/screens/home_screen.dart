/// Home tab — "اليوم". Pure composition over existing providers.
///
/// Three blocks, then a divider, then everything else. «مش عارف أبدأ منين»
/// was the first complaint parents wrote, and the screen used to answer it
/// with eleven cards: what's new, today's focus, games, rituals, stats, the
/// child's day, the coach tip, shortcuts, the journey, an invite, a note.
/// Above the divider there are now exactly three stops for the active child:
///
///   ① خطوة اليوم — [TodayFocusCard]: opens the next lesson directly (the
///      change that took lesson_opened/child_added from 39% to 54%).
///   ② اسأل المربّي — [TodayAskBlock]: the coach tip (28% of questions start
///      there) plus an ask entry that is always present.
///   ③ مهمة الطفل — [TodayChildBlock]: today's mission, or the child's day for
///      the bands that have no mission bank.
///
/// [TodayLoopSlot] under ① is reserved for the weekly plan and the follow-up
/// cards. Nothing that used to be here was removed from the app: the rest sits
/// below the divider, and every destination in it is also in «المزيد». The
/// games banner was the only card dropped from this screen — it duplicated the
/// games tile two rows below it and the games group in the hub.
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
import '../features/home/widgets/today_ask_block.dart';
import '../features/home/widgets/today_child_block.dart';
import '../features/home/widgets/today_rituals_row.dart';
import '../features/home/widgets/today_section.dart';
import '../features/onboarding/providers/onboarding_providers.dart';
import '../features/program/data/badges.dart';
import '../features/program/providers/program_providers.dart';
import '../features/program/providers/progress_providers.dart';
import '../features/referral/pride_invite_card.dart';
import '../features/journey/widgets/child_journey_card.dart';
import '../features/coins/coins_providers.dart';
import '../features/shell/root_tab.dart';
import '../theme/app_theme.dart';
import '../theme/design_tokens.dart';
import '../widgets/ui/noor_mascot.dart';
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
          // Whose day this is — and the one-tap way to change it.
          _ActiveChildBanner(profile: profile),
          const SizedBox(height: 20),

          // ① خطوة اليوم
          TodaySectionHeader(
            emoji: '🎯',
            title: profile == null
                ? l10n.todayStepTitleNoName
                : l10n.todayStepTitle(profile.name),
          ),
          TodayFocusCard(
            key: focusCardKey,
            bundle: bundle,
            ageGroup: ageGroup,
            onStartFirstPath: () => onGoToTab(RootTab.learn),
          ),
          // Reserved: «خطة الأسبوع» and «المتابعة». Renders nothing until
          // those cards ship — see TodayLoopSlot for the contract.
          const TodayLoopSlot(),
          const SizedBox(height: 24),

          // ② اسأل المربّي
          TodayAskBlock(
            childName: profile?.name,
            onAsk: () => onGoToTab(RootTab.assistant),
          ),
          const SizedBox(height: 24),

          // ③ مهمة الطفل
          TodayChildBlock(profile: profile),
          const SizedBox(height: 28),

          // ── Everything else. Every destination below is also in «المزيد». ──
          TodayMoreDivider(label: l10n.todayMoreTitle),
          // Renders nothing except in the one launch after an update.
          const WhatsNewCard(),
          TodayRitualsRow(ageGroup: ageGroup),
          const SizedBox(height: 16),
          HomeStatsRow(bundle: bundle),
          const SizedBox(height: 16),
          const HomeShortcutsGrid(),
          const SizedBox(height: 20),
          const ChildJourneyCard(),
          const SizedBox(height: 20),
          // §6.4 — the referral ask fires only at a pride moment (≥7-day
          // streak), once per 7-day tier. Below the divider, so it never
          // outranks the parent's own next step.
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
        color: AppTheme.surface, // was a hand-copied #131F1C / white pair
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
                            ? l10n.todaySwitchChildHint
                            : l10n.todayPickChildHint,
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
