/// Stats: flame login streak / open-book completed lessons / medal badges /
/// coin balance — drawn brand glyphs (جولة الحرفة), not emoji.
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

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/brand_glyph.dart';
import '../../../widgets/ui/count_up_text.dart';
import '../../../widgets/ui/stat_chip.dart';
import '../../../widgets/ui/two_column_rows.dart';
import '../../coins/coins_providers.dart';
import '../../program/data/badges.dart';
import '../../program/data/progress_models.dart';

class HomeStatsRow extends ConsumerWidget {
  const HomeStatsRow({super.key, required this.bundle});
  final ChildProgressBundle? bundle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final completed =
        bundle?.lessons
            .where((l) => l.status == ProgressStatus.completed)
            .length ??
        0;
    final streak = bundle?.dailyLoginStreak ?? 0;
    final badges = computeBadges(bundle);
    final earned = earnedCount(badges);
    final coins = ref.watch(coinsProvider);

    // Not GridView.count — see TwoColumnRows for the overflow that caused.
    return TwoColumnRows(
      children: [
        StatChip(
          icon: BrandGlyph(BrandIcon.flame, color: context.colors.accent),
          value: CountUpText(streak),
          label: l10n.consecutiveDays,
          color: Dt.accent,
          pulse: streak > 0,
        ),
        StatChip(
          icon: BrandGlyph(BrandIcon.openBook, color: context.colors.primary),
          value: CountUpText(completed),
          label: l10n.completedLesson,
          color: Dt.primary,
        ),
        StatChip(
          icon: BrandGlyph(BrandIcon.medal, color: context.violetText),
          value: CountUpText(earned),
          label: l10n.achievements,
          color: const Color(0xFF8B5CF6),
          onTap: () => Navigator.of(context).push(AppRoutes.badges()),
        ),
        StatChip(
          icon: BrandGlyph(BrandIcon.coin, color: context.colors.accent),
          value: CountUpText(coins.balance),
          label: l10n.coins,
          color: Dt.accent,
          onTap: () => Navigator.of(context).push(AppRoutes.coins()),
        ),
      ],
    );
  }
}
