/// Secondary destinations, compressed into a 2×2 grid.
///
/// These were four full-width cards competing head-on with the primary action.
/// The tile styling deliberately mirrors the hub's `_HubTile` so the home and
/// «المزيد» tabs read as one system.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';

class HomeShortcutsGrid extends StatelessWidget {
  const HomeShortcutsGrid({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 2.9,
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      children: [
        _ShortcutTile(
          emoji: '🌙',
          label: l10n.bedtimeStories,
          analyticsId: 'shortcut_stories',
          route: AppRoutes.storyBookshelf,
        ),
        _ShortcutTile(
          emoji: '❓',
          label: l10n.quizzes,
          analyticsId: 'shortcut_quiz',
          route: AppRoutes.quizGame,
        ),
        _ShortcutTile(
          emoji: '🧠',
          label: l10n.hubInsights,
          analyticsId: 'shortcut_insights',
          route: AppRoutes.parentingInsights,
        ),
        _ShortcutTile(
          emoji: '⭐',
          label: l10n.favoritesTitle,
          analyticsId: 'shortcut_favorites',
          route: AppRoutes.favorites,
        ),
      ],
    );
  }
}

class _ShortcutTile extends StatelessWidget {
  const _ShortcutTile({
    required this.emoji,
    required this.label,
    required this.analyticsId,
    required this.route,
  });

  final String emoji;
  final String label;
  final String analyticsId;
  final Route<void> Function() route;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(Dt.rCard),
      child: InkWell(
        borderRadius: BorderRadius.circular(Dt.rCard),
        onTap: () {
          unawaited(Analytics.homeCardTapped(analyticsId));
          Navigator.of(context).push(route());
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Text(emoji, style: const TextStyle(fontSize: 20)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
