/// Community social-proof card (Phase 3) — «X أب يربّون بثقة معنا».
///
/// Fetches the public aggregate stats once and shows a warm, non-numeric-heavy
/// line that gives the "you're part of something" feeling. Hides itself while
/// loading, on error, or when the numbers are still too small to be persuasive
/// (so we never show weak/anti social proof early on).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/referral/community_providers.dart';
import '../../theme/app_theme.dart';
import '../../l10n/app_localizations.dart';

class CommunityProofCard extends ConsumerWidget {
  const CommunityProofCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Shared with Home's quieter line, so the two surfaces cannot disagree
    // about the count or fetch it twice. The card treatment stays here: this
    // screen is *about* inviting, so the line has earned its box.
    final f = ref.watch(communityFamiliesProvider).valueOrNull;
    if (f == null) {
      return const SizedBox.shrink();
    }
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppTheme.primary.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.primary.withValues(alpha: 0.15)),
      ),
      child: Row(
        children: [
          const Text('🤍', style: TextStyle(fontSize: 22)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              AppLocalizations.of(context).communityProof(f),
              style: TextStyle(
                color: AppTheme.primary,
                fontWeight: FontWeight.w700,
                fontSize: 13.5,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
