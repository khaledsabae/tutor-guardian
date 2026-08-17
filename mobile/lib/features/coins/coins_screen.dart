/// Coins screen — balance, daily claim, and how-to-earn. The reward
/// currency's "spend" side ships later (redeemables), so this screen
/// focuses on the earning loop, honestly labelled.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/ui/bouncy_button.dart';
import '../../widgets/ui/count_up_text.dart';
import 'coins_providers.dart';
import 'coins_service.dart';

class CoinsScreen extends ConsumerWidget {
  const CoinsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final coins = ref.watch(coinsProvider);
    return Scaffold(
      appBar: AppBar(title: Text(AppLocalizations.of(context).coinsTitle)),
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
                  AppLocalizations.of(context).coinsUnit,
                  style: TextStyle(color: Colors.white.withValues(alpha: .9)),
                ),
                if (coins.dailyStreak > 0) ...[
                  const SizedBox(height: 6),
                  Text(
                    AppLocalizations.of(context).coinsStreak(coins.dailyStreak),
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
              label: AppLocalizations.of(context).coinsDailyClaim,
              color: Dt.primary,
              onTap: () async {
                final reward =
                    await ref.read(coinsProvider.notifier).claimDaily();
                if (context.mounted && reward > 0) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                        content: Text(AppLocalizations.of(context)
                            .coinsRewardSnack(reward))),
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
              child: Row(
                children: [
                  Icon(Icons.check_circle, color: AppTheme.success),
                  const SizedBox(width: 8),
                  Text(AppLocalizations.of(context).coinsDailyDone,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                ],
              ),
            ),
          const SizedBox(height: 24),
          Text(
            AppLocalizations.of(context).coinsEarnHow,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          _EarnRow(
            emoji: '📅',
            title: AppLocalizations.of(context).coinsEarnDaily,
            detail: AppLocalizations.of(context).coinsEarnDailyDesc(CoinsService.dailyBase),
          ),
          _EarnRow(
            emoji: '🏅',
            title: AppLocalizations.of(context).coinsEarnBadge,
            detail: AppLocalizations.of(context).coinsEarnBadgeDesc(CoinsService.badgeReward),
          ),
          _EarnRow(
            emoji: '🤝',
            title: AppLocalizations.of(context).coinsEarnInvite,
            detail: AppLocalizations.of(context).coinsEarnInviteDesc(CoinsService.referralReward),
            onTap: () => Navigator.of(context).push(AppRoutes.invite()),
          ),
          const SizedBox(height: 24),
          Text(
            AppLocalizations.of(context).coinsRedeemTitle,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          _RedeemRow(
            emoji: '📖',
            title: AppLocalizations.of(context).coinsRedeemStory,
            detail: AppLocalizations.of(context).coinsRedeemStoryDesc,
            onTap: () => Navigator.of(context).push(AppRoutes.storyGenerator()),
          ),
          _RedeemRow(
            emoji: '📜',
            title: AppLocalizations.of(context).coinsRedeemCovenant,
            detail: AppLocalizations.of(context).coinsRedeemCovenantDesc,
            onTap: () => Navigator.of(context).push(AppRoutes.covenant()),
          ),
          _RedeemRow(
            emoji: '🏅',
            title: AppLocalizations.of(context).coinsRedeemBadges,
            detail: AppLocalizations.of(context).coinsRedeemBadgesDesc,
            onTap: () =>
                Navigator.of(context).push(AppRoutes.exclusiveBadges()),
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
          color: Dt.surface,
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
  const _EarnRow({
    required this.emoji,
    required this.title,
    required this.detail,
    this.onTap,
  });
  final String emoji;
  final String title;
  final String detail;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final card = Container(
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
                    style: TextStyle(
                        color: AppTheme.textSecondary, fontSize: 13)),
              ],
            ),
          ),
          if (onTap != null)
            Icon(Icons.chevron_left, color: AppTheme.primary),
        ],
      ),
    );

    if (onTap != null) {
      return GestureDetector(
        onTap: onTap,
        child: card,
      );
    }
    return card;
  }
}
