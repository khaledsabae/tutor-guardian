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
import '../../../widgets/ui/brand_glyph.dart';
import 'today_section.dart';

class TodayAskBlock extends StatelessWidget {
  const TodayAskBlock({
    super.key,
    required this.childName,
    required this.onAsk,
  });

  /// The active child's name, or null before one is chosen.
  final String? childName;

  /// Switches to the assistant tab. The tip pre-fills a question first (see
  /// [CoachTipCard]); the compose entry opens it empty.
  final VoidCallback onAsk;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final name = childName;
    final body = name == null
        ? l10n.todayAskBodyNoName
        : l10n.todayAskBody(name);
    void ask() {
      unawaited(Analytics.todayBlockTapped('ask', 'compose'));
      onAsk();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TodaySectionHeader(
          icon: BrandIcon.speechBubble,
          title: l10n.todayAskTitle,
        ),
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
          child: Semantics(
            container: true,
            button: true,
            label: l10n.todayAskCta,
            hint: body,
            onTap: ask,
            excludeSemantics: true,
            child: InkWell(
              excludeFromSemantics: true,
              borderRadius: BorderRadius.circular(Dt.rCard),
              onTap: ask,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: _ComposeRow(body: body, cta: l10n.todayAskCta),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// The compose entry's body and call to action.
///
/// Side by side when there is room; the call to action drops under the body
/// when there is not. At 200% text on a 320dp phone a fixed-width "Ask your
/// question" beside the body left the body a sliver of width, and it wrapped
/// one word to a line into a card taller than the screen.
class _ComposeRow extends StatelessWidget {
  const _ComposeRow({required this.body, required this.cta});

  final String body;
  final String cta;

  @override
  Widget build(BuildContext context) {
    final bodyText = Text(
      body,
      style: TextStyle(
        color: AppTheme.textSecondary,
        fontSize: 13,
        height: 1.5,
      ),
    );
    final action = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Flexible(
          child: Text(
            cta,
            style: TextStyle(
              color: AppTheme.primary,
              fontWeight: FontWeight.w800,
              fontSize: 13,
            ),
          ),
        ),
        Icon(Icons.arrow_forward, color: AppTheme.primary, size: 16),
      ],
    );
    final icon = Icon(
      Icons.chat_bubble_outline_rounded,
      color: AppTheme.primary,
      size: 22,
    );

    return LayoutBuilder(
      builder: (context, constraints) {
        final scale = MediaQuery.textScalerOf(context).scale(1);
        final stacked = scale > 1.3 || constraints.maxWidth < 300;
        if (!stacked) {
          return Row(
            children: [
              icon,
              const SizedBox(width: 12),
              Expanded(child: bodyText),
              const SizedBox(width: 8),
              // Capped, not flexed: a Flexible beside the Expanded body would
              // take half the row however short the label is.
              ConstrainedBox(
                constraints: BoxConstraints(
                  maxWidth: constraints.maxWidth * 0.4,
                ),
                child: action,
              ),
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                icon,
                const SizedBox(width: 12),
                Expanded(child: bodyText),
              ],
            ),
            const SizedBox(height: 8),
            Align(alignment: AlignmentDirectional.centerEnd, child: action),
          ],
        );
      },
    );
  }
}
