/// Stats: 🔥 login streak / 📚 completed lessons / 🏅 badges / 🪙 coins.
///
/// The coin balance used to be an AppBar chip; it lives here because the
/// AppBar was carrying five actions and none of them read as important.
///
/// Laid out 2×2 rather than 4-across. On a 360dp phone — the common case for
/// this audience — four chips in one row leave roughly 24dp of text width
/// each, which ellipsizes the *numbers*, not just the labels. Two columns give
/// each chip ~150dp, and the grid echoes the shortcuts grid further down the
/// screen so the two read as one system.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/count_up_text.dart';
import '../../../widgets/ui/stat_chip.dart';
import '../../coins/coins_providers.dart';
import '../../program/data/badges.dart';
import '../../program/data/progress_models.dart';

class HomeStatsRow extends ConsumerWidget {
  const HomeStatsRow({super.key, required this.bundle});
  final ChildProgressBundle? bundle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final completed = bundle?.lessons
            .where((l) => l.status == ProgressStatus.completed)
            .length ??
        0;
    final streak = bundle?.dailyLoginStreak ?? 0;
    if ((bundle?.streakDays ?? 0) >= 3) {
      unawaited(Analytics.habitStreak3(bundle!.streakDays));
    }
    final badges = computeBadges(bundle);
    final earned = earnedCount(badges);
    final coins = ref.watch(coinsProvider);

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      childAspectRatio: 3.2,
      children: [
        StatChip(
          emoji: '🔥',
          value: CountUpText(streak),
          label: l10n.consecutiveDays,
          color: Dt.accent,
          pulse: streak > 0,
        ),
        StatChip(
          emoji: '📚',
          value: CountUpText(completed),
          label: l10n.completedLesson,
          color: Dt.primary,
        ),
        StatChip(
          emoji: '🏅',
          value: CountUpText(earned),
          label: l10n.achievements,
          color: const Color(0xFF8B5CF6),
          onTap: () => Navigator.of(context).push(AppRoutes.badges()),
        ),
        StatChip(
          emoji: '🪙',
          value: CountUpText(coins.balance),
          label: l10n.coins,
          color: Dt.accent,
          onTap: () => Navigator.of(context).push(AppRoutes.coins()),
        ),
      ],
    );
  }
}
