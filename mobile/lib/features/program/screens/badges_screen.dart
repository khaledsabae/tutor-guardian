import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
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
          ? const _Hint(text: 'اختر طفلاً أولاً لعرض الإنجازات.')
          : ref.watch(childProgressProvider(childId)).when(
                loading: () =>
                    const Center(child: CircularProgressIndicator()),
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
            children: [for (final b in badges) _BadgeTile(badge: b)],
          ),
        ),
      ],
    );
  }
}

class _BadgeTile extends StatelessWidget {
  final AchievementBadge badge;
  const _BadgeTile({required this.badge});

  @override
  Widget build(BuildContext context) {
    final earned = badge.earned;
    return Semantics(
      label: '${badge.title}. ${badge.description}. '
          '${earned ? "تم الحصول عليه" : "لم يُفتح بعد"}',
      child: Opacity(
        opacity: earned ? 1.0 : 0.45,
        child: Container(
          decoration: BoxDecoration(
            color: earned ? Colors.white : AppTheme.surfaceAlt,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: earned ? AppTheme.primary : Colors.transparent,
              width: earned ? 1.5 : 0,
            ),
            boxShadow: earned
                ? [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.05),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ]
                : null,
          ),
          padding: const EdgeInsets.all(14),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(earned ? badge.emoji : '🔒',
                  style: const TextStyle(fontSize: 40)),
              const SizedBox(height: 10),
              Text(
                badge.title,
                textAlign: TextAlign.center,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 4),
              Text(
                badge.description,
                textAlign: TextAlign.center,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                    fontSize: 12, color: AppTheme.textSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Hint extends StatelessWidget {
  final String text;
  const _Hint({required this.text});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Text(text,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppTheme.textMuted)),
      ),
    );
  }
}
