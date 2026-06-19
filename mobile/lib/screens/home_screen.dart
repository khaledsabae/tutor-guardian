/// Home tab — "اليوم". Pure composition over existing providers:
///
///   * Greeting + active child chip
///   * Stats row: 🔥 streak / 📚 completed lessons / 🏅 badges
///   * "Continue your journey" card (first path with an in-progress
///     lesson, falls back to a "start your first path" nudge)
///   * Daily tip card (moved here from the chat tab)
///
/// No new business logic — everything reads providers that already
/// power PathsScreen / PathDetailScreen / BadgesScreen.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/onboarding/providers/onboarding_providers.dart';
import '../features/program/data/badges.dart';
import '../features/program/data/models.dart';
import '../features/program/data/progress_models.dart';
import '../features/program/providers/program_providers.dart';
import '../features/program/providers/progress_providers.dart';
import '../features/program/screens/badges_screen.dart';
import '../features/program/screens/path_detail_screen.dart';
import '../features/program/screens/search_screen.dart';
import '../features/program/screens/settings_screen.dart';
import '../features/feedback/feedback_screen.dart';
import '../features/program/widgets/active_child_chip.dart';
import '../features/program/widgets/coach_tip_card.dart';
import '../features/journey/widgets/child_journey_card.dart';
import '../features/coins/coins_providers.dart';
import '../features/coins/coins_screen.dart';
import '../features/program/screens/quiz_game_screen.dart';
import '../theme/app_theme.dart';
import '../theme/design_tokens.dart';
import '../widgets/ui/animated_progress_bar.dart';
import '../widgets/ui/bouncy_button.dart';
import '../widgets/ui/count_up_text.dart';
import '../widgets/ui/emoji_hero.dart';
import '../widgets/ui/noor_mascot.dart';
import '../widgets/ui/stat_chip.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key, required this.onGoToTab});

  /// Switches the root scaffold tab.
  /// Indices: 0 = اليوم, 1 = مساراتي, 2 = الورد (Quran), 3 = المساعد (chat).
  final ValueChanged<int> onGoToTab;

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
    final coins = ref.watch(coinsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('اليوم ☀️'),
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
            child: Center(
              child: GestureDetector(
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const CoinsScreen()),
                ),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: Dt.accent.withValues(alpha: .15),
                    borderRadius: BorderRadius.circular(Dt.rChip),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('🪙', style: TextStyle(fontSize: 15)),
                      const SizedBox(width: 4),
                      Text(
                        '${coins.balance}',
                        style: const TextStyle(
                          color: Dt.accentDeep,
                          fontWeight: FontWeight.w800,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 10, horizontal: 4),
            child: Center(child: ActiveChildChip()),
          ),
          IconButton(
            tooltip: 'شاركنا رأيك',
            icon: const Icon(Icons.feedback, color: Dt.accent),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const FeedbackScreen()),
            ),
          ),
          IconButton(
            tooltip: 'بحث',
            icon: const Icon(Icons.search),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SearchScreen()),
            ),
          ),
          IconButton(
            tooltip: 'الإعدادات',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          Row(
            children: [
              const NoorMascot(size: 56)
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
                      ? 'السلام عليكم'
                      : 'السلام عليكم\nرحلة ${profile.name} مستمرة',
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
          _StatsRow(bundle: bundle),
          const SizedBox(height: 14),
          // Feedback nudge — extra-visible during the testing phase.
          Material(
            color: Dt.accent.withValues(alpha: .12),
            borderRadius: BorderRadius.circular(Dt.rCard),
            child: InkWell(
              borderRadius: BorderRadius.circular(Dt.rCard),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const FeedbackScreen()),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                child: Row(
                  children: [
                    const Text('💬', style: TextStyle(fontSize: 22)),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Text(
                        'رأيك يهمنا! شاركنا أي ملاحظة أو مشكلة — كتابةً أو صوتاً.',
                        style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
                      ),
                    ),
                    Icon(Icons.arrow_back_ios_new, size: 14, color: Dt.accent),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 20),
          _ContinueJourneyCard(
            bundle: bundle,
            ageGroup: ageGroup,
            onStartFirstPath: () => onGoToTab(1),
          ),
          const SizedBox(height: 20),
          CoachTipCard(onAsk: () => onGoToTab(3)),
          const SizedBox(height: 20),
          const ChildJourneyCard(),
          const SizedBox(height: 20),
          _QuizCard(),
          const SizedBox(height: 20),
          _AskAssistantCard(onTap: () => onGoToTab(3)),
        ],
      ),
    );
  }
}

class _StatsRow extends ConsumerWidget {
  const _StatsRow({required this.bundle});
  final ChildProgressBundle? bundle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final completed = bundle?.lessons
            .where((l) => l.status == ProgressStatus.completed)
            .length ??
        0;
    final streak = bundle?.streakDays ?? 0;
    final badges = computeBadges(bundle);
    final earned = earnedCount(badges);

    return Row(
      children: [
        Expanded(
          child: StatChip(
            emoji: '🔥',
            value: CountUpText(streak),
            label: 'أيام متتالية',
            color: Dt.accent,
            pulse: streak > 0,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: StatChip(
            emoji: '📚',
            value: CountUpText(completed),
            label: 'درس مكتمل',
            color: Dt.primary,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: StatChip(
            emoji: '🏅',
            value: CountUpText(earned),
            label: 'إنجازات',
            color: const Color(0xFF8B5CF6),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const BadgesScreen()),
            ),
          ),
        ),
      ],
    );
  }
}

class _ContinueJourneyCard extends ConsumerWidget {
  const _ContinueJourneyCard({
    required this.bundle,
    required this.ageGroup,
    required this.onStartFirstPath,
  });
  final ChildProgressBundle? bundle;
  final String ageGroup;
  final VoidCallback onStartFirstPath;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncPaths =
        ref.watch(pathsListProvider(PathsListArgs(ageGroup: ageGroup)));
    final paths = asyncPaths.maybeWhen(
      data: (env) => env.paths,
      orElse: () => const <CurriculumPath>[],
    );

    // The path to resume: most recently touched non-completed path.
    CurriculumPath? resume;
    int done = 0;
    if (bundle != null && paths.isNotEmpty) {
      for (final lesson in bundle!.lessons.reversed) {
        final match =
            paths.where((p) => p.id == lesson.pathId).toList();
        if (match.isEmpty) continue;
        final p = match.first;
        final completedInPath = bundle!.lessons
            .where((l) =>
                l.pathId == p.id && l.status == ProgressStatus.completed)
            .length;
        if (completedInPath < p.lessonIds.length) {
          resume = p;
          done = completedInPath;
          break;
        }
      }
    }

    if (resume == null) {
      // Nudge: no in-progress path yet.
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: Dt.primaryGradient,
          borderRadius: BorderRadius.circular(Dt.rCard),
          boxShadow: Dt.softShadow(Dt.primary),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                EmojiHero(emoji: '🚀', size: 48),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'ابدأ مسارك الأول',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              'اختر رحلة تربوية قصيرة مصممة لعمر طفلك وابدأ اليوم.',
              style: TextStyle(
                color: Colors.white.withValues(alpha: .92),
                height: 1.5,
              ),
            ),
            const SizedBox(height: 14),
            BouncyButton(
              label: 'استعرض المسارات',
              color: Dt.accent,
              onTap: onStartFirstPath,
            ),
          ],
        ),
      ).animate().fadeIn(duration: Dt.base).slideY(begin: .06);
    }

    final style = styleFor(resume.domain);
    final total = resume.lessonIds.length;
    final fraction = total == 0 ? 0.0 : done / total;
    final remaining = total - done;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: style.gradient,
        borderRadius: BorderRadius.circular(Dt.rCard),
        boxShadow: Dt.softShadow(style.base),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              EmojiHero(emoji: style.emoji, size: 48),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'أكمل رحلتك',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: .85),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      resume.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: AnimatedProgressBar(
                  value: fraction,
                  color: Colors.white,
                  trackColor: Colors.white.withValues(alpha: .25),
                  height: 12,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '$done/$total',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            remaining == 1 ? '🏆 درس واحد باقٍ!' : '🏆 $remaining دروس باقية',
            style: TextStyle(
              color: Colors.white.withValues(alpha: .9),
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          BouncyButton(
            label: 'متابعة',
            color: Colors.white.withValues(alpha: .22),
            edgeColor: Colors.white.withValues(alpha: .35),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => PathDetailScreen(
                  pathId: resume!.id,
                  ageGroup: ageGroup,
                ),
              ),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: Dt.base).slideY(begin: .06);
  }
}

class _QuizCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return BouncyTap(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const QuizGameScreen()),
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF6A1B9A), Color(0xFF8E24AA)],
          ),
          borderRadius: BorderRadius.circular(Dt.rCard),
          boxShadow: Dt.softShadow(const Color(0xFF6A1B9A)),
        ),
        child: const Row(
          children: [
            EmojiHero(
              emoji: '🧠',
              size: 48,
              background: Color(0x33FFFFFF),
            ),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'اختبر معلوماتك التربوية',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                      color: Colors.white,
                    ),
                  ),
                  SizedBox(height: 2),
                  Text(
                    '10 أسئلة سريعة • تعلّم وأنت تلعب',
                    style: TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                ],
              ),
            ),
            Icon(Icons.play_arrow_rounded, color: Colors.white70, size: 28),
          ],
        ),
      ),
    );
  }
}

class _AskAssistantCard extends StatelessWidget {
  const _AskAssistantCard({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return BouncyTap(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(Dt.rCard),
          boxShadow: Dt.cardShadow,
        ),
        child: const Row(
          children: [
            EmojiHero(
              emoji: '💬',
              size: 48,
              background: Color(0x1A0D9488),
            ),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'عندك سؤال تربوي؟',
                    style:
                        TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
                  ),
                  SizedBox(height: 2),
                  Text(
                    'اسأل المربي الذكي الآن',
                    style: TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_left, color: AppTheme.textMuted),
          ],
        ),
      ),
    );
  }
}
