/// «الألعاب التعليمية» — one place to hand a child something to play.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';
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
        onTap: () {
          unawaited(Analytics.gameStarted(game.id, 0));
          Navigator.of(context).push(game.route());
        },
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
              const Icon(Icons.chevron_left, color: Dt.inkSoft),
            ],
          ),
        ),
      ),
    );
  }
}
