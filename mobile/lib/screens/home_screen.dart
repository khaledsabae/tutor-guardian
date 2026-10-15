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
/// The weekly-plan and follow-up cards go between ① and ② (see the comment
/// there). The family-programs card (Ramadan, the Prayer Journey, milestones)
/// goes right under ③ — a card, not a fourth stop, and absent unless the
/// server serves the programs. Nothing that used to be here was removed from the app: the rest sits
/// below the divider, and every destination in it is also in «المزيد». The
/// games banner was the only card dropped from this screen — it duplicated the
/// games tile two rows below it and the games group in the hub.
///
/// No new business logic — everything reads providers that already
/// power PathsScreen / PathDetailScreen / BadgesScreen.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/app_localizations.dart';

import '../features/companion/providers/companion_providers.dart';
import '../features/companion/widgets/noor_today_header.dart';
import '../features/home/greeting.dart';
import '../features/companion/widgets/noor_presence.dart';
import '../features/home/widgets/daily_gift_moment.dart';
import '../features/home/widgets/home_app_bar.dart';
import '../features/home/widgets/home_community_note.dart';
import '../features/home/widgets/home_shortcuts_grid.dart';
import '../features/home/widgets/home_stats_row.dart';
import '../features/home/widgets/today_focus_card.dart';
import '../features/home/widgets/today_ask_block.dart';
import '../features/home/widgets/today_child_block.dart';
import '../features/home/widgets/today_loop_cards.dart';
import '../features/home/widgets/today_rituals_row.dart';
import '../features/family_road/providers/family_road_providers.dart';
import '../features/family_road/widgets/horizon_strip.dart';
import '../features/home/widgets/sky_band.dart';
import '../features/home/widgets/today_road.dart';
import '../features/home/widgets/today_section.dart';
import '../features/lanterns/widgets/week_lantern_string.dart';
import '../features/onboarding/providers/onboarding_providers.dart';
import '../features/program/data/badges.dart';
import '../features/program/providers/program_providers.dart';
import '../features/program/data/progress_models.dart';
import '../features/program/providers/progress_providers.dart';
import '../features/programs/data/programs_models.dart';
import '../features/programs/providers/programs_providers.dart';
import '../features/programs/widgets/eid_moment.dart';
import '../features/programs/widgets/programs_home_card.dart';
import '../features/referral/pride_invite_card.dart';
import '../features/journey/widgets/child_journey_card.dart';
import '../features/coins/coins_providers.dart';
import '../features/shell/root_tab.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../theme/design_tokens.dart';
import '../widgets/ui/brand_glyph.dart';
import '../features/whats_new/widgets/whats_new_card.dart';

import '../core/analytics.dart';
import '../core/app_routes.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key, required this.onGoToTab, this.focusCardKey});

  /// Switches the root scaffold tab. Always pass a [RootTab] constant — a
  /// hard-coded index here is how both assistant buttons ended up opening the
  /// infant routine tracker.
  final ValueChanged<int> onGoToTab;

  /// Attached to [TodayFocusCard] so the first-run tour can measure it.
  final Key? focusCardKey;

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  @override
  void initState() {
    super.initState();
    // «هدية اليوم والشارات» — the daily claim and the badge credits used to
    // run in an addPostFrameCallback inside build: every rebuild re-ran them,
    // and both rewards happened with no one looking. A manual listener
    // outside build runs when the active child's progress *changes* (and
    // once up front) — the claim lands at the moment something was earned,
    // and neither a rebuild nor a tab switch can re-fire it.
    ref.listenManual<AsyncValue<ChildProgressBundle>?>(
      activeChildProgressProvider,
      (_, next) => _claimDailyRewards(next?.valueOrNull),
      fireImmediately: true,
    );
  }

  void _claimDailyRewards(ChildProgressBundle? bundle) {
    if (!mounted) return;
    final notifier = ref.read(coinsProvider.notifier);
    unawaited(notifier.claimDaily());
    final earnedBadgeIds = computeBadges(
      bundle,
    ).where((b) => b.earned).map((b) => b.id).toList();
    if (earnedBadgeIds.isNotEmpty) {
      // Idempotent per badge id: passing every earned badge each time is how
      // a badge that did not fit under the day's ceiling gets paid later.
      unawaited(notifier.creditBadges(earnedBadgeIds));
    }
    // Here, not in HomeStatsRow: since the stats moved below the divider
    // the row is built only when scrolled near, and the funnel event fired
    // only for parents who scrolled. Once per install either way.
    final lessonStreak = bundle?.streakDays ?? 0;
    if (lessonStreak >= 3) {
      unawaited(Analytics.habitStreak3(lessonStreak));
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = ref.watch(activeChildProfileProvider);
    final ageGroup = ref.watch(selectedAgeGroupProvider);
    final bundle = ref
        .watch(activeChildProgressProvider)
        ?.maybeWhen(data: (b) => b, orElse: () => null);
    final coins = ref.watch(coinsProvider);
    final gift = ref.watch(dailyGiftProvider).valueOrNull;

    final l10n = AppLocalizations.of(context);
    final noorOn = ref.watch(noorHeaderEnabledProvider);
    final inRamadan =
        ref.watch(programsOverviewProvider).valueOrNull?.ramadan.state ==
        RamadanState.ramadan;
    final stops = ref.watch(todayStopsProvider);
    // «سماوات المواسم» and «على الأفق» (عالم الأسرة): the season's paper
    // touch in the sky, and the nearest gate of the family road on its hills.
    final season = ref.watch(skySeasonProvider);
    final horizon = ref.watch(horizonStripGateProvider);
    // At large text the strip wraps and would push ①'s button below the fold
    // (CI run 38754954265, 200% on a 411dp phone) — the button that took
    // lesson_opened/child_added from 39% to 54% wins: the strip then waits
    // under the road instead of on the hills.
    final largeText = MediaQuery.textScalerOf(context).scale(10) > 13;
    final stripOnHills = horizon != null && !largeText;
    // Time-aware, and honest on day one («النصوص»): the hour picks صباح/مساء,
    // and a first-day streak (≤1) drops the «مستمرة» — nothing has continued
    // yet.
    final greeting = profile == null
        ? l10n.greetingPeace
        : greetingFor(
            l10n,
            profile.name,
            DateTime.now(),
            firstDay: coins.dailyStreak <= 1,
          );
    final greetingRow = Row(
      children: [
        // «نور» as a presence beside the greeting (جولة الحرفة):
        // the drawn face in its breathing moon window, not a loose
        // square illustration.
        const NoorPresence(size: 56)
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
            // Time-aware, and honest on day one («النصوص»): the hour
            // picks صباح/مساء, and a first-day streak (≤1) drops the
            // «مستمرة» — nothing has continued yet.
            greeting,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w600,
              height: 1.4,
            ),
          ).animate().fadeIn(duration: Dt.base),
        ),
      ],
    );

    // ① خطوة اليوم
    final stepStop = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TodaySectionHeader(
          icon: BrandIcon.lightDot,
          title: profile == null
              ? l10n.todayStepTitleNoName
              : l10n.todayStepTitle(profile.name),
        ),
        TodayFocusCard(
          key: widget.focusCardKey,
          bundle: bundle,
          ageGroup: ageGroup,
          onStartFirstPath: () => widget.onGoToTab(RootTab.learn),
        ),
        // «المتابعة» then «خطة الأسبوع» (plan §1.2, §1.3), between ① and ②:
        // the weekly plan is the week-sized version of today's step, and a
        // follow-up is time-sensitive — but neither goes above ①, the card
        // that took lesson_opened/child_added from 39% to 54%. Each hides
        // itself while loading, on any failure, and on an older server, and
        // logs today_block_tapped('loop', <action>).
        TodayLoopCards(
          profile: profile,
          hideFollowup: ref.watch(companionHostsFollowupProvider),
        ),
        // «قناديل الأسبوع» (phase 3): the week's lit lanterns, last in ① —
        // under the step and its weekly loop, never above the ① button.
        // Nothing at all on a server without lanterns or on any failure.
        if (profile != null) const WeekLanternString(),
      ],
    );
    // ② اسأل المربّي
    final askStop = TodayAskBlock(
      childName: profile?.name,
      onAsk: () => widget.onGoToTab(RootTab.assistant),
    );
    // ③ مهمة الطفل
    final missionStop = TodayChildBlock(profile: profile);
    final missionIcon =
        profile != null && !kMissionBands.contains(profile.ageGroup)
        ? BrandIcon.sprig
        : BrandIcon.path;

    final today = Scaffold(
      appBar: const HomeAppBar(),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          // «نور يتذكّر» (phase 2): Noor's one line for this open — a
          // promise to ask back, a mission waiting, the time of day — under
          // the sky of the hour (SkyBand). The old greeting row stays as the
          // fallback (no child yet); with the server's NOOR_HEADER_ENABLED
          // kill switch off there is no sky and no road either.
          if (noorOn)
            SkyBand(
              // In the month itself (plan phase 5) the maghrib and night
              // skies hang a quiet lantern string — the server's state, so
              // the family's own sighting decides the first night too.
              ramadan: inRamadan,
              season: season,
              footer: stripOnHills ? HorizonStrip(gate: horizon) : null,
              child: NoorTodayHeader(fallback: _SkyGreeting(text: greeting)),
            )
          else
            NoorTodayHeader(fallback: greetingRow),
          const SizedBox(height: 12),
          // «هدية اليوم» — once a day it lands as a moment; afterwards it
          // stays as a quiet line (جولة الحرفة, item 2).
          if (gift != null && gift > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: DailyGiftMoment(gift: gift),
            ),
          // Whose day this is — and the one-tap way to change it. Under the
          // sky Noor already says the name and the app bar's chip switches
          // child, so the banner would only repeat them (plan phase 2).
          if (!noorOn) _ActiveChildBanner(profile: profile),
          const SizedBox(height: 20),

          // «درب اليوم» (phase 2): the three stops as stations on one road.
          // Same blocks, same order; the road only frames them.
          if (noorOn) ...[
            TodayRoad(
              stops: [
                RoadStop(
                  icon: BrandIcon.lightDot,
                  reached: stops.step,
                  child: stepStop,
                ),
                RoadStop(
                  icon: BrandIcon.speechBubble,
                  reached: stops.ask,
                  child: askStop,
                ),
                RoadStop(
                  icon: missionIcon,
                  reached: stops.mission,
                  child: missionStop,
                ),
              ],
            ),
            const SizedBox(height: 28),
          ] else ...[
            stepStop,
            const SizedBox(height: 24),
            askStop,
            const SizedBox(height: 24),
            missionStop,
            const SizedBox(height: 28),
          ],

          // «برامج الأسرة» (plan phase 2: Ramadan, the Prayer Journey,
          // milestones) — below the three blocks, never between them. A card,
          // not a fourth numbered stop, so it has no section header. It renders
          // nothing while loading, on any failure, and on a server without the
          // programs (`GET /api/programs` → 404).
          if (noorOn && horizon != null && !stripOnHills)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: HorizonStrip(gate: horizon),
            ),
          const ProgramsHomeCard(),

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
    // «عيدكم مبارك» (plan phase 5): on the first open of Eid, once a year, a
    // quiet moment over Today. The gate draws nothing itself.
    return EidMomentGate(child: today);
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
                  // The child's chosen avatar, or the drawn crescent —
                  // a data emoji is content; the fallback is brand art.
                  child: profile?.avatarEmoji != null
                      ? Text(
                          profile!.avatarEmoji!,
                          style: const TextStyle(fontSize: 20),
                        )
                      : BrandGlyph(
                          BrandIcon.crescent,
                          size: 20,
                          color: AppTheme.primary,
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
                                horizontal: 6,
                                vertical: 2,
                              ),
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

/// The plain greeting, set on the sky: Noor's window and the words in a paper
/// bubble, like Noor's own line — never text straight on the sky.
class _SkyGreeting extends StatelessWidget {
  const _SkyGreeting({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const NoorPresence(size: 56),
        const SizedBox(width: 10),
        Expanded(
          child: Container(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            decoration: BoxDecoration(
              color: colors.surface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: colors.primary.withValues(alpha: .18)),
            ),
            child: Text(
              text,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: colors.ink,
                fontWeight: FontWeight.w700,
                height: 1.4,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
