/// «اسأل المربّي» — the second of the three «اليوم» blocks.
///
/// The coach tip leads it because the tip is what starts conversations: 28% of
/// questions to the assistant begin from a tapped tip. The tip hides itself
/// while loading and on any failure, so the block also carries a plain "ask"
/// entry that is always there — a slow network must never leave the block
/// without an action.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../program/widgets/coach_tip_card.dart';
import 'today_section.dart';

class TodayAskBlock extends StatelessWidget {
  const TodayAskBlock({super.key, required this.childName, required this.onAsk});

  /// The active child's name, or null before one is chosen.
  final String? childName;

  /// Switches to the assistant tab. The tip pre-fills a question first (see
  /// [CoachTipCard]); the compose entry opens it empty.
  final VoidCallback onAsk;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final name = childName;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TodaySectionHeader(emoji: '💬', title: l10n.todayAskTitle),
        CoachTipCard(
          padding: const EdgeInsets.only(bottom: 10),
          onAsk: () {
            unawaited(Analytics.todayBlockTapped('ask', 'tip'));
            onAsk();
          },
        ),
        Material(
          color: Dt.surface,
          borderRadius: BorderRadius.circular(Dt.rCard),
          child: InkWell(
            borderRadius: BorderRadius.circular(Dt.rCard),
            onTap: () {
              unawaited(Analytics.todayBlockTapped('ask', 'compose'));
              onAsk();
            },
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Icon(Icons.chat_bubble_outline_rounded,
                      color: AppTheme.primary, size: 22),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      name == null
                          ? l10n.todayAskBodyNoName
                          : l10n.todayAskBody(name),
                      style: TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 13,
                        height: 1.5,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    l10n.todayAskCta,
                    style: TextStyle(
                      color: AppTheme.primary,
                      fontWeight: FontWeight.w800,
                      fontSize: 13,
                    ),
                  ),
                  Icon(Icons.arrow_forward, color: AppTheme.primary, size: 16),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
