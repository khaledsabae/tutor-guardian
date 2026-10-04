/// The «ادعم المربّي» entry at the foot of «المزيد».
///
/// Not a [HubItem]: hub items are always shown, and this one must not exist
/// unless the server flag is on AND the store returned products. Last in the
/// hub, and soft — an offer to the parents who want it, never an ask in the
/// way of the ones who came for something else.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/analytics.dart';
import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import 'support_providers.dart';

class SupportHubCard extends ConsumerWidget {
  const SupportHubCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!ref.watch(supportVisibleProvider)) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    return Material(
      color: Dt.surface,
      borderRadius: BorderRadius.circular(Dt.rCard),
      child: InkWell(
        borderRadius: BorderRadius.circular(Dt.rCard),
        onTap: () {
          unawaited(Analytics.hubItemTapped('support', 'support'));
          Navigator.of(context).push(AppRoutes.support());
        },
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(Dt.rCard),
            border: Border.all(color: AppTheme.primary.withValues(alpha: .25)),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.supportHubTitle,
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 15,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      l10n.supportHubBody,
                      style: TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: AppTheme.primary),
            ],
          ),
        ),
      ),
    );
  }
}
