/// Cosmetic badges — earned, not bought.
///
/// This was a store: six badges at 100–300 coins each. Selling cosmetics for
/// a currency the app itself mints is the second half of the loop the story
/// paywall was the first half of, and the coin now has exactly one sink — a
/// covenant a parent hands over in the real world. So the prices are gone and
/// the buy button with them.
///
/// Badges anyone already bought stay theirs. Reclaiming them to make a point
/// about extrinsic motivation would be its own kind of rude, and they cost
/// real effort to save for.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import 'coins_providers.dart';

/// id, emoji, title
const exclusiveBadges = <(String, String, String)>[
  ('gold_star', '🌟', 'النجمة الذهبية'),
  ('crown', '👑', 'تاج المربي'),
  ('diamond', '💎', 'ماسة التميّز'),
  ('rocket', '🚀', 'رائد التعلّم'),
  ('rainbow', '🌈', 'قوس قزح'),
  ('trophy_gold', '🏆', 'الكأس الذهبي'),
];

class ExclusiveBadgesScreen extends ConsumerWidget {
  const ExclusiveBadgesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final ownedAsync = ref.watch(ownedBadgesProvider);
    final owned = ownedAsync.maybeWhen(data: (s) => s, orElse: () => <String>{});

    return Scaffold(
      appBar: AppBar(title: Text(l10n.coinsRedeemBadges)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            l10n.exclusiveBadgesIntro,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.6),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton(
              onPressed: () => Navigator.push(context, AppRoutes.covenant()),
              child: Text(l10n.exclusiveBadgesToCovenant),
            ),
          ),
          const SizedBox(height: 8),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 0.82,
            children: [
              for (final (id, emoji, title) in exclusiveBadges)
                _BadgeCard(
                  emoji: emoji,
                  title: title,
                  owned: owned.contains(id),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _BadgeCard extends StatelessWidget {
  const _BadgeCard({
    required this.emoji,
    required this.title,
    required this.owned,
  });

  final String emoji;
  final String title;
  final bool owned;

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
          Text(
            owned
                ? AppLocalizations.of(context).exclusiveBadgeOwned
                : AppLocalizations.of(context).exclusiveBadgeLocked,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: owned ? Colors.white : Dt.inkSoft,
              fontWeight: FontWeight.w700,
              fontSize: 12,
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
