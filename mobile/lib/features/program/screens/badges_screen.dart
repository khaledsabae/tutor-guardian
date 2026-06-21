import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../../share/share_service.dart';
import '../../share/shareable_moment_card.dart';
import '../data/badges.dart';
import '../providers/progress_providers.dart';

/// Achievements screen (P1 #4) — shows earned + locked badges derived
/// from the active child's progress. Calm, non-competitive encouragement.
class BadgesScreen extends ConsumerWidget {
  const BadgesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final childId = ref.watch(activeChildIdProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('إنجازاتي')),
      body: childId == null
          ? const EmptyState(
              emoji: '🏅',
              title: 'اختر طفلاً أولاً',
              subtitle: 'اختر طفلاً لعرض إنجازاته.',
            )
          : ref.watch(childProgressProvider(childId)).when(
                loading: () => const SingleChildScrollView(
                  physics: NeverScrollableScrollPhysics(),
                  child: SkeletonList(count: 3, itemHeight: 150),
                ),
                // Badges are encouragement — on error just show them all locked.
                error: (_, __) => _BadgesGrid(badges: computeBadges(null)),
                data: (bundle) =>
                    _BadgesGrid(badges: computeBadges(bundle)),
              ),
    );
  }
}

class _BadgesGrid extends StatelessWidget {
  final List<AchievementBadge> badges;
  const _BadgesGrid({required this.badges});

  @override
  Widget build(BuildContext context) {
    final earned = earnedCount(badges);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Semantics(
            label: 'حصلت على $earned من ${badges.length} إنجازات',
            child: Text(
              'حصلت على $earned من ${badges.length}',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: AppTheme.primary,
                  ),
            ),
          ),
        ),
        Expanded(
          child: GridView.count(
            crossAxisCount: 2,
            padding: const EdgeInsets.all(16),
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 0.95,
            children: [
              for (var i = 0; i < badges.length; i++)
                // "Unlock pop" — earned badges spring in, staggered.
                _BadgeTile(badge: badges[i])
                    .animate(delay: (80 * (i % Dt.maxStaggeredItems)).ms)
                    .scale(
                      begin: const Offset(.5, .5),
                      duration: Dt.base,
                      curve: Curves.easeOutBack,
                    )
                    .fadeIn(duration: Dt.fast),
            ],
          ),
        ),
      ],
    );
  }
}

class _BadgeTile extends StatelessWidget {
  final AchievementBadge badge;
  const _BadgeTile({required this.badge});

  Future<void> _share() async {
    await ShareService.shareMomentCard(
      fileTag: 'badge_${badge.id}',
      message: 'ما شاء الله 🌟 وصلت لإنجاز «${badge.title}» في رحلتي '
          'التربوية مع «المربّي» 🤍',
      card: ShareableMomentCard(
        emoji: badge.emoji,
        eyebrow: 'إنجاز جديد',
        headline: badge.title,
        body: badge.description,
        icon: Icons.emoji_events_outlined,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final earned = badge.earned;
    return Semantics(
      label: '${badge.title}. ${badge.description}. '
          '${earned ? "تم الحصول عليه — اضغط للمشاركة" : "لم يُفتح بعد"}',
      child: GestureDetector(
        onTap: earned ? _share : null,
        child: Container(
        decoration: BoxDecoration(
          gradient: earned ? Dt.accentGradient : null,
          color: earned ? null : AppTheme.surfaceAlt,
          borderRadius: BorderRadius.circular(20),
          boxShadow: earned ? Dt.softShadow(Dt.accent) : null,
        ),
        padding: const EdgeInsets.all(14),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Opacity(
              opacity: earned ? 1.0 : 0.4,
              child: Text(earned ? badge.emoji : '🔒',
                  style: const TextStyle(fontSize: 40)),
            ),
            const SizedBox(height: 10),
            Text(
              badge.title,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontWeight: FontWeight.w800,
                color: earned ? Colors.white : AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              badge.description,
              textAlign: TextAlign.center,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 12,
                color: earned
                    ? Colors.white.withValues(alpha: .9)
                    : AppTheme.textMuted,
              ),
            ),
          ],
        ),
      ),
      ),
    );
  }
}

