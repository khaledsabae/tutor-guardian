/// A quiet closing line on Home: «X أب وأمّ يربّون بثقة معنا — لست وحدك».
///
/// This used to be a tinted, bordered card on Home and was dropped when the
/// screen was rebuilt around one primary action, because a filled block that
/// competes with the day's task is exactly what made the old Home tiring to
/// look at.
///
/// It comes back as type, not as a card: no fill, no border, secondary colour,
/// last in the list. A parent who has finished reading their day sees it; a
/// parent who is working through their task never has to look past it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../referral/community_providers.dart';

class HomeCommunityNote extends ConsumerWidget {
  const HomeCommunityNote({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Loading, error and too-small-to-show all arrive as null, and all mean the
    // same thing here: say nothing at all.
    final families = ref.watch(communityFamiliesProvider).valueOrNull;
    if (families == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 28, bottom: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(
            Icons.favorite_rounded,
            size: 14,
            color: AppTheme.primary.withValues(alpha: .45),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              AppLocalizations.of(context).communityProof(families),
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 12.5,
                fontWeight: FontWeight.w500,
                height: 1.6,
              ),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: Dt.slow, delay: Dt.base);
  }
}
