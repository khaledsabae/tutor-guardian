/// Exclusive badges store — spend coins to unlock cosmetic badges that
/// then appear in the achievements screen. Fully on-device.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import 'coins_providers.dart';

/// id, emoji, title, price
const exclusiveBadges = <(String, String, String, int)>[
  ('gold_star', '🌟', 'النجمة الذهبية', 100),
  ('crown', '👑', 'تاج المربي', 200),
  ('diamond', '💎', 'ماسة التميّز', 300),
  ('rocket', '🚀', 'رائد التعلّم', 150),
  ('rainbow', '🌈', 'قوس قزح', 120),
  ('trophy_gold', '🏆', 'الكأس الذهبي', 250),
];

class ExclusiveBadgesScreen extends ConsumerWidget {
  const ExclusiveBadgesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final coins = ref.watch(coinsProvider);
    final ownedAsync = ref.watch(ownedBadgesProvider);
    final owned = ownedAsync.maybeWhen(data: (s) => s, orElse: () => <String>{});

    return Scaffold(
      appBar: AppBar(
        title: const Text('شارات حصرية 🏅'),
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text('🪙 ${coins.balance}',
                  style: const TextStyle(
                      fontWeight: FontWeight.w800, color: Dt.accentDeep)),
            ),
          ),
        ],
      ),
      body: GridView.count(
        crossAxisCount: 2,
        padding: const EdgeInsets.all(16),
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.82,
        children: [
          for (final (id, emoji, title, price) in exclusiveBadges)
            _BadgeCard(
              id: id,
              emoji: emoji,
              title: title,
              price: price,
              owned: owned.contains(id),
              canAfford: coins.balance >= price,
              onBuy: () async {
                final ok =
                    await ref.read(coinsProvider.notifier).buyBadge(id, price);
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(ok
                          ? 'تهانينا! فتحت «$title» 🎉'
                          : 'رصيدك لا يكفي.'),
                    ),
                  );
                }
              },
            ),
        ],
      ),
    );
  }
}

class _BadgeCard extends StatelessWidget {
  const _BadgeCard({
    required this.id,
    required this.emoji,
    required this.title,
    required this.price,
    required this.owned,
    required this.canAfford,
    required this.onBuy,
  });
  final String id;
  final String emoji;
  final String title;
  final int price;
  final bool owned;
  final bool canAfford;
  final VoidCallback onBuy;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: owned ? Dt.accentGradient : null,
        color: owned ? null : AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: owned ? Dt.softShadow(Dt.accent) : Dt.cardShadow,
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Opacity(
            opacity: owned ? 1 : 0.85,
            child: Text(emoji, style: const TextStyle(fontSize: 44)),
          ),
          const SizedBox(height: 8),
          Text(
            title,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontWeight: FontWeight.w800,
              color: owned ? Colors.white : AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          if (owned)
            const Text('مملوكة ✓',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700))
          else
            GestureDetector(
              onTap: canAfford ? onBuy : null,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: canAfford ? Dt.accent : Dt.track,
                  borderRadius: BorderRadius.circular(Dt.rChip),
                ),
                child: Text(
                  '🪙 $price',
                  style: TextStyle(
                    color: canAfford ? Colors.white : Dt.inkSoft,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
        ],
      ),
    ).animate().scale(
          begin: const Offset(.9, .9),
          duration: Dt.base,
          curve: Curves.easeOutBack,
        );
  }
}
