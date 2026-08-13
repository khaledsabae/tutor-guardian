/// «الألعاب التعليمية» — one place to hand a child something to play.
library;

import 'package:flutter/material.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../games_catalog.dart';

class GamesScreen extends StatelessWidget {
  const GamesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.educationalGames)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          for (final game in kGames)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _GameCard(game: game),
            ),
        ],
      ),
    );
  }
}

class _GameCard extends StatelessWidget {
  const _GameCard({required this.game});

  final GameEntry game;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(Dt.rCard),
      child: InkWell(
        borderRadius: BorderRadius.circular(Dt.rCard),
        // No analytics call here on purpose. This tap used to log
        // `game_started(level: 0)` — opening the lobby counted as starting a
        // game, so every play entered from this screen was counted twice while
        // a play entered from a lesson counted once. The shell now logs
        // `game_opened` for every entry point, and this tap stays visible as
        // `tg_screen_view` besides.
        onTap: () => Navigator.of(context).push(
          game.route(source: GameSources.index),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
          child: Row(
            children: [
              Container(
                width: 52,
                height: 52,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Dt.primary.withValues(alpha: .10),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(game.emoji, style: const TextStyle(fontSize: 26)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  game.label(l10n),
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ),
              const DirectionalChevron(size: 22),
            ],
          ),
        ),
      ),
    );
  }
}
