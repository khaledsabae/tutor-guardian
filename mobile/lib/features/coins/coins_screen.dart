/// Coins screen — balance, daily claim, and how-to-earn. The reward
/// currency's "spend" side ships later (redeemables), so this screen
/// focuses on the earning loop, honestly labelled.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/ui/bouncy_button.dart';
import '../../widgets/ui/count_up_text.dart';
import 'coins_providers.dart';
import 'coins_service.dart';
import 'story_screen.dart';
import 'exclusive_badges_screen.dart';

class CoinsScreen extends ConsumerWidget {
  const CoinsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final coins = ref.watch(coinsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('عملاتي 🪙')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Balance hero
          Container(
            padding: const EdgeInsets.symmetric(vertical: 28),
            decoration: BoxDecoration(
              gradient: Dt.accentGradient,
              borderRadius: BorderRadius.circular(Dt.rCard),
              boxShadow: Dt.softShadow(Dt.accent),
            ),
            child: Column(
              children: [
                const Text('🪙', style: TextStyle(fontSize: 52)),
                const SizedBox(height: 8),
                CountUpText(
                  coins.balance,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 40,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  'عملة',
                  style: TextStyle(color: Colors.white.withValues(alpha: .9)),
                ),
                if (coins.dailyStreak > 0) ...[
                  const SizedBox(height: 6),
                  Text(
                    '🔥 سلسلة دخول ${coins.dailyStreak} يوم',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 20),
          // Daily claim
          if (!coins.claimedToday)
            BouncyButton(
              label: 'احصل على مكافأة اليوم 🎁',
              color: Dt.primary,
              onTap: () async {
                final reward =
                    await ref.read(coinsProvider.notifier).claimDaily();
                if (context.mounted && reward > 0) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('+$reward عملة! 🪙')),
                  );
                }
              },
            )
          else
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(Dt.rButton),
                boxShadow: Dt.cardShadow,
              ),
              child: const Row(
                children: [
                  Icon(Icons.check_circle, color: AppTheme.success),
                  SizedBox(width: 8),
                  Text('تم استلام مكافأة اليوم — عُد غداً!',
                      style: TextStyle(fontWeight: FontWeight.w700)),
                ],
              ),
            ),
          const SizedBox(height: 24),
          Text(
            'كيف تكسب العملات؟',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          const _EarnRow(
            emoji: '📅',
            title: 'تسجيل الدخول اليومي',
            detail: '+${CoinsService.dailyBase} عملة كل يوم، وتزيد مع السلسلة',
          ),
          const _EarnRow(
            emoji: '🏅',
            title: 'فتح إنجاز جديد',
            detail: '+${CoinsService.badgeReward} عملة لكل شارة',
          ),
          const SizedBox(height: 24),
          Text(
            'استبدل عملاتك 🎁',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          _RedeemRow(
            emoji: '📖',
            title: 'قصة مخصصة لطفلك',
            detail: 'قصة قصيرة بطلها طفلك تعلّم قيمة تختارها',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const StoryScreen()),
            ),
          ),
          _RedeemRow(
            emoji: '🏅',
            title: 'شارات حصرية',
            detail: 'افتح شارات مميزة بعملاتك',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ExclusiveBadgesScreen()),
            ),
          ),
        ].animate(interval: 60.ms).fadeIn(duration: Dt.base).slideY(begin: .05),
      ),
    );
  }
}

class _RedeemRow extends StatelessWidget {
  const _RedeemRow({
    required this.emoji,
    required this.title,
    required this.detail,
    required this.onTap,
  });
  final String emoji;
  final String title;
  final String detail;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFF3EEFE),
          borderRadius: BorderRadius.circular(Dt.rButton),
        ),
        child: Row(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 26)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          color: Color(0xFF6D28D9))),
                  Text(detail,
                      style: const TextStyle(
                          color: Color(0xFF7C6BA8), fontSize: 13)),
                ],
              ),
            ),
            const Icon(Icons.chevron_left, color: Color(0xFF6D28D9)),
          ],
        ),
      ),
    );
  }
}

class _EarnRow extends StatelessWidget {
  const _EarnRow(
      {required this.emoji, required this.title, required this.detail});
  final String emoji;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(Dt.rButton),
        boxShadow: Dt.cardShadow,
      ),
      child: Row(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 26)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                Text(detail,
                    style: const TextStyle(
                        color: AppTheme.textSecondary, fontSize: 13)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
