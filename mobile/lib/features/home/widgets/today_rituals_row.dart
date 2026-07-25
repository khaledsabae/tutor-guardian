/// The two daily rituals — Qur'an and the routine/habit tracker — that used to
/// be bottom-nav tabs. They sit directly under the primary action because they
/// are recurring habits, not one-off destinations like the shortcuts grid.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';
import '../../routine/screens/daily_routine_screen.dart' show habitTabLabel;

class TodayRitualsRow extends StatelessWidget {
  const TodayRitualsRow({super.key, required this.ageGroup});

  /// The active child's age group — decides whether the second tile reads
  /// "routine" (babies) or "habit balance" (older children).
  final String ageGroup;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Row(
      children: [
        Expanded(
          child: _RitualTile(
            emoji: '📗',
            label: l10n.holyQuran,
            analyticsId: 'ritual_quran',
            route: AppRoutes.quran,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _RitualTile(
            emoji: '📊',
            label: habitTabLabel(ageGroup, l10n),
            analyticsId: 'ritual_routine',
            route: AppRoutes.dailyRoutine,
          ),
        ),
      ],
    );
  }
}

class _RitualTile extends StatelessWidget {
  const _RitualTile({
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
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
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
