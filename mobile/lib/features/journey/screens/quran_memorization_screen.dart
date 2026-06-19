/// «رحلة الطفل» — Quran memorization checklist (Phase 4).
///
/// A per-child list of the 114 surahs the parent can mark as memorized.
/// Memorizing the FIRST surah auto-logs the «حفظ أول سورة» spiritual
/// milestone (celebrated + rewarded once via the coins ledger). Local-only.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/celebration_overlay.dart';
import '../../coins/coins_providers.dart';
import '../../quran/models/surah_names.dart';
import '../data/journey_milestones.dart';
import '../providers/journey_providers.dart';

class QuranMemorizationScreen extends ConsumerWidget {
  const QuranMemorizationScreen({
    super.key,
    required this.childId,
    required this.childName,
  });

  final int childId;
  final String childName;

  Future<void> _toggle(
    BuildContext context,
    WidgetRef ref,
    int surah,
  ) async {
    final wasFirst =
        await ref.read(memorizedSurahsProvider(childId).notifier).toggle(surah);
    if (!wasFirst) return;

    // First surah ever → log the spiritual milestone + celebrate once.
    final m = spiritualMilestones.firstWhere((x) => x.key == 'first_surah');
    await ref.read(childJourneyProvider(childId).notifier).log(
          key: m.key,
          title: m.title,
          emoji: m.emoji,
          note: 'بدأ بسورة ${surahNames[surah - 1]}',
        );
    await ref
        .read(coinsProvider.notifier)
        .creditBadges([journeyRewardId(childId, m.key)]);
    if (context.mounted) {
      await showCelebration(
        context,
        emoji: '📖',
        imageAsset: milestoneBadgeAsset('first_surah'),
        title: 'ما شاء الله!',
        message: '$childName حفظ أول سورة — سورة ${surahNames[surah - 1]} 🌟',
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final memorized = ref.watch(memorizedSurahsProvider(childId)).maybeWhen(
          data: (s) => s,
          orElse: () => const <int>{},
        );
    return Scaffold(
      appBar: AppBar(title: Text('حفظ القرآن — $childName')),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF2E7D32), Color(0xFF43A047)],
              ),
              borderRadius: BorderRadius.circular(Dt.rCard),
              boxShadow: Dt.softShadow(const Color(0xFF2E7D32)),
            ),
            child: Row(
              children: [
                const Text('📖', style: TextStyle(fontSize: 36)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'حفظ ${memorized.length} من 114 سورة',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'علّم السور التي أتمّها — نحتفل بكل خطوة',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: .92),
                          fontSize: 12.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: surahNames.length,
              itemBuilder: (context, i) {
                final surah = i + 1;
                final done = memorized.contains(surah);
                return ListTile(
                  onTap: () => _toggle(context, ref, surah),
                  leading: Container(
                    width: 34,
                    height: 34,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: done
                          ? const Color(0xFF2E7D32).withValues(alpha: 0.12)
                          : AppTheme.surfaceAlt,
                      borderRadius: BorderRadius.circular(17),
                    ),
                    child: Text(
                      '$surah',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: done
                            ? const Color(0xFF2E7D32)
                            : AppTheme.textSecondary,
                      ),
                    ),
                  ),
                  title: Text(
                    'سورة ${surahNames[i]}',
                    style: TextStyle(
                      fontWeight: done ? FontWeight.w700 : FontWeight.w500,
                      color: done ? AppTheme.textPrimary : AppTheme.textSecondary,
                    ),
                  ),
                  trailing: Icon(
                    done ? Icons.check_circle : Icons.radio_button_unchecked,
                    color: done ? const Color(0xFF2E7D32) : AppTheme.textMuted,
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
