/// «الألعاب التعليمية» — one place to hand a child something to play.
///
/// When the `game` budget for the day is spent, the catalogue does not
/// disappear and no dialog blocks the tap: the cards stay where they were and
/// go quiet. Plan item 1.4/4 asks for exactly that — "locked gently" — and the
/// reason is rule 3 of the constitution. An abrupt cut teaches a child that
/// the screen is taken away; a card that is visibly resting until tomorrow
/// teaches that time ran out, which is a fact about the day rather than a
/// punishment.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../../routine/providers/child_mode_providers.dart';
import '../games_catalog.dart';

class GamesScreen extends ConsumerWidget {
  const GamesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final childMode = ref.watch(childModeProvider);

    // Only locked for a child inside a session. A parent browsing the
    // catalogue on their own phone is not spending anyone's budget, and the
    // server would not stop them either.
    final remaining = childMode.remainingSeconds;
    final spent = childMode.active && remaining != null && remaining <= 0;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.educationalGames)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          if (spent)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(
                l10n.gamesBudgetSpent,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          for (final game in kGames)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _GameCard(game: game, locked: spent),
            ),
        ],
      ),
    );
  }
}

class _GameCard extends StatelessWidget {
  const _GameCard({required this.game, this.locked = false});

  final GameEntry game;
  final bool locked;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Opacity(
      opacity: locked ? .45 : 1,
      child: Material(
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
          //
          // A locked card is not disabled with a grey ripple and a snackbar —
          // it simply does not respond. Nothing to argue with.
          onTap: locked
              ? null
              : () => Navigator.of(context).push(
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
                if (locked)
                  Icon(Icons.bedtime_outlined,
                      size: 20, color: Theme.of(context).colorScheme.outline)
                else
                  const DirectionalChevron(size: 22),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
