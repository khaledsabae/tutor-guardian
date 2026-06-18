/// «رحلة الطفل» — Home entry card (Phase 1).
///
/// Modeled on [CoachTipCard]: self-hides until the active child is loaded
/// (and when [kJourneyEnabled] is off). Tapping opens the child's journey
/// timeline. Shows a live count of logged milestones as a gentle nudge.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/design_tokens.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../providers/journey_providers.dart';
import '../screens/child_journey_screen.dart';

class ChildJourneyCard extends ConsumerWidget {
  const ChildJourneyCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!kJourneyEnabled) return const SizedBox.shrink();
    final profile = ref.watch(activeChildProfileProvider);
    if (profile == null) return const SizedBox.shrink();

    final count = ref.watch(childJourneyProvider(profile.id)).maybeWhen(
          data: (m) => m.length,
          orElse: () => 0,
        );

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ChildJourneyScreen(
              childId: profile.id,
              childName: profile.name,
              ageGroup: profile.ageGroup,
            ),
          ),
        ),
        borderRadius: BorderRadius.circular(Dt.rCard),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
              colors: [Color(0xFF7E57C2), Color(0xFF9575CD)],
            ),
            borderRadius: BorderRadius.circular(Dt.rCard),
            boxShadow: Dt.softShadow(const Color(0xFF7E57C2)),
          ),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Text('🌟', style: TextStyle(fontSize: 26)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'رحلة ${profile.name}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      count == 0
                          ? 'سجّل محطات نموّه الإيمانية واحتفظ بها'
                          : '$count محطة في رحلته — أضف المزيد',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: .9),
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_left, color: Colors.white70),
            ],
          ),
        ),
      ),
    );
  }
}
