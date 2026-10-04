/// The scaffolding of the «اليوم» tab: a titled block, and the divider below
/// the three primary blocks.
///
/// The tab was cut to three blocks (2026-10) because «مش عارف أبدأ منين» was
/// the first complaint parents wrote. Each block is introduced by a plain title
/// so the eye has exactly three stops before the divider; everything else is
/// below it or in «المزيد».
library;

import 'package:flutter/material.dart';

import '../../../theme/app_theme.dart';

/// A numbered stop on the page — title above the block's own card.
class TodaySectionHeader extends StatelessWidget {
  const TodaySectionHeader({super.key, required this.emoji, required this.title});

  final String emoji;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(4, 0, 4, 10),
      child: Semantics(
        header: true,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(
              child: Text(emoji, style: const TextStyle(fontSize: 18)),
            ),
            const SizedBox(width: 8),
            // Expanded + no maxLines: at 200% text a child's name must wrap,
            // not ellipsize away the only word that says whose step it is.
            Expanded(
              child: Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                      color: AppTheme.textPrimary,
                      height: 1.3,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The line between the day's three blocks and everything else.
class TodayMoreDivider extends StatelessWidget {
  const TodayMoreDivider({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.textMuted;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        children: [
          Expanded(child: Divider(color: color.withValues(alpha: .35))),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10),
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ),
          Expanded(child: Divider(color: color.withValues(alpha: .35))),
        ],
      ),
    );
  }
}
