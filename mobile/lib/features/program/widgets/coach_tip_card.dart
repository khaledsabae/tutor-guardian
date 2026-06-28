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
import '../../share/share_service.dart';
import '../../share/shareable_moment_card.dart';
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
            // Seed the assistant with a concrete question about *this* tip so
            // switching tabs lands the parent in a relevant conversation,
            // not a blank chat. ChatScreen picks this up and auto-sends it.
            ref.read(pendingChatQuestionProvider.notifier).state =
                'بخصوص نصيحة اليوم: «${tip.text}»\n\n'
                'ازاي أقدر أطبّقها مع ${profile.name} بشكل عملي؟';
            onAsk?.call();
          },
          // Render the tip as a reverent, branded 1080×1080 card and open the
          // share sheet — turns the daily tip into a صدقة جارية growth surface.
          // The shared artifact stays child-agnostic for privacy.
          onShare: () => ShareService.shareMomentCard(
            fileTag: 'coachtip_${tip.id}',
            message: 'نصيحة اليوم في تربية أبنائنا 🌱\n\n${tip.text}\n\n'
                'انشرها تكن صدقة جارية لكل أب وأم:',
            card: ShareableMomentCard(
              emoji: '🌱',
              eyebrow: 'نصيحة اليوم',
              headline: 'وقفة في تربية أبنائنا',
              body: tip.text,
              icon: Icons.lightbulb_outline,
            ),
          ),
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
    required this.onShare,
  });

  final String text;
  final String childName;
  final VoidCallback onTap;
  final VoidCallback onShare;

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
                      'نصيحة اليوم لـ $childName',
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
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        // Share pill — own tap target so it doesn't trigger
                        // the card's "ask" onTap.
                        _ShareButton(onTap: onShare),
                        const Spacer(),
                        const Text(
                          'اسأل المربّي عن ده',
                          style: TextStyle(
                            color: Color(0xFF8A5A0F),
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(width: 4),
                        const Icon(Icons.arrow_back,
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

/// Small "شير" pill inside the coach card. Has its own [InkWell] so tapping it
/// shares the tip instead of bubbling up to the card's "ask the coach" action.
class _ShareButton extends StatelessWidget {
  const _ShareButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.55),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFF8A5A0F), width: 1),
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.ios_share, color: Color(0xFF8A5A0F), size: 15),
              SizedBox(width: 5),
              Text(
                'شارك النصيحة',
                style: TextStyle(
                  color: Color(0xFF8A5A0F),
                  fontWeight: FontWeight.w700,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
