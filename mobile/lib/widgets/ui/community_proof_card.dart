/// Community social-proof card (Phase 3) — «X أب يربّون بثقة معنا».
///
/// Fetches the public aggregate stats once and shows a warm, non-numeric-heavy
/// line that gives the "you're part of something" feeling. Hides itself while
/// loading, on error, or when the numbers are still too small to be persuasive
/// (so we never show weak/anti social proof early on).
library;

import 'package:flutter/material.dart';

import '../../api/tg_client.dart';
import '../../theme/app_theme.dart';

class CommunityProofCard extends StatefulWidget {
  const CommunityProofCard({super.key});

  /// Only surface once the community is large enough to be persuasive.
  static const int _minFamilies = 10;

  @override
  State<CommunityProofCard> createState() => _CommunityProofCardState();
}

class _CommunityProofCardState extends State<CommunityProofCard> {
  int? _families;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final s = await TgClient().getCommunityStats();
      final f = (s['families'] as num?)?.toInt() ?? 0;
      if (mounted) setState(() => _families = f);
    } catch (_) {
      // stay hidden on any failure
    }
  }

  @override
  Widget build(BuildContext context) {
    final f = _families;
    if (f == null || f < CommunityProofCard._minFamilies) {
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
              '$f أبٍ وأمٍّ يربّون بثقة مع «المربّي» — لست وحدك في الرحلة',
              style: const TextStyle(
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
