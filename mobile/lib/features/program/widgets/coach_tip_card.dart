/// Proactive parenting coach card — replaces [DailyTipCard] on Home.
///
/// Fetches a personalized (or gracefully-degraded) coach tip for the active
/// child via [coachTipProvider]. The fetch itself records the "shown" signal
/// server-side (deduped once/day); tapping records engagement and jumps to
/// the assistant via [onAsk]. Hides itself until the active child is loaded.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../providers/program_providers.dart';

class CoachTipCard extends ConsumerWidget {
  const CoachTipCard({super.key, this.onAsk});

  /// Invoked when the parent taps the card (e.g. switch to the chat tab).
  final VoidCallback? onAsk;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(activeChildProfileProvider);
    if (profile == null) {
      return const SizedBox.shrink();
    }
    final asyncTip = ref.watch(coachTipProvider(profile.id));
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: asyncTip.when(
        data: (tip) => _CoachCard(
          text: tip.text,
          childName: profile.name,
          onTap: () {
            // Fire-and-forget engagement log; never block the UX on it.
            ref.read(programRepositoryProvider).recordCoachTipTap(tip.id);
            onAsk?.call();
          },
        ),
        loading: () => const SizedBox.shrink(),
        error: (_, __) => const SizedBox.shrink(),
      ),
    );
  }
}

class _CoachCard extends StatelessWidget {
  const _CoachCard({
    required this.text,
    required this.childName,
    required this.onTap,
  });

  final String text;
  final String childName;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
              colors: [Color(0xFFFFE9C7), Color(0xFFFFD89E)],
            ),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.lightbulb_outline,
                    color: Color(0xFF8A5A0F), size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'مرشد $childName',
                      style: const TextStyle(
                        color: Color(0xFF8A5A0F),
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      text,
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontSize: 13,
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text(
                          'اسأل المربّي عن ده',
                          style: TextStyle(
                            color: Color(0xFF8A5A0F),
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                        SizedBox(width: 4),
                        Icon(Icons.arrow_back,
                            color: Color(0xFF8A5A0F), size: 16),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
