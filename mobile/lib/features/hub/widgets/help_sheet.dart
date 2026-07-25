/// «أين أجد…؟» — a list of the questions people actually get stuck on, each
/// answering itself by navigating straight to the destination.
///
/// A first-run tour only ever helps the *next* cohort; the parents complaining
/// today are already past onboarding. This is the always-available version,
/// and it doubles as the cheapest possible instrumentation: `help_intent_tapped`
/// reports what people cannot find, in their own words, without a survey.
///
/// When one intent dominates the taps, that destination is still buried and
/// belongs somewhere more obvious.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';

class _Intent {
  const _Intent(this.id, this.emoji, this.question, this.route);

  final String id;
  final String emoji;
  final String Function(AppLocalizations l10n) question;
  final Route<void> Function() route;
}

final _intents = <_Intent>[
  _Intent('games', '🎮', (l) => l.helpWhereGames, AppRoutes.games),
  _Intent('stories', '🌙', (l) => l.helpWhereStories,
      AppRoutes.storyBookshelf),
  _Intent('add_child', '👶', (l) => l.helpHowAddChild,
      AppRoutes.childrenList),
  _Intent('quran', '📗', (l) => l.helpWhereQuran, AppRoutes.quran),
  _Intent('progress', '📊', (l) => l.helpWhereProgress,
      AppRoutes.dailyRoutine),
  _Intent('badges', '🏅', (l) => l.helpWhereBadges, AppRoutes.badges),
  _Intent('backup', '☁️', (l) => l.helpHowBackup, AppRoutes.identity),
  _Intent('contact', '💬', (l) => l.helpHowContact, AppRoutes.feedback),
];

/// Opens the help sheet. [fromScreen] is a `Screens.*` constant.
Future<void> showHelpSheet(BuildContext context, String fromScreen) {
  unawaited(Analytics.helpOpened(fromScreen));
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(Dt.rSheet)),
    ),
    builder: (_) => const _HelpSheetBody(),
  );
}

class _HelpSheetBody extends StatelessWidget {
  const _HelpSheetBody();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return SafeArea(
      child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        children: [
          Text(
            l10n.helpTitle,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text(
            l10n.helpSubtitle,
            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 16),
          for (final intent in _intents)
            _IntentRow(
              emoji: intent.emoji,
              label: intent.question(l10n),
              onTap: () {
                unawaited(Analytics.helpIntentTapped(intent.id));
                // Close the sheet first, so back from the destination returns
                // to the screen behind it rather than re-opening the sheet.
                Navigator.of(context).pop();
                Navigator.of(context).push(intent.route());
              },
            ),
        ],
      ),
    );
  }
}

class _IntentRow extends StatelessWidget {
  const _IntentRow({
    required this.emoji,
    required this.label,
    required this.onTap,
  });

  final String emoji;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(Dt.rCard),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14),
          child: Row(
            children: [
              Text(emoji, style: const TextStyle(fontSize: 20)),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const Icon(Icons.chevron_left, size: 18, color: Dt.inkSoft),
            ],
          ),
        ),
      ),
    );
  }
}
