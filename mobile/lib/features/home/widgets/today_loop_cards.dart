/// The weekly loop on «اليوم», between ① and ② (plan §1.2–§1.3): the
/// follow-up first (it is time-sensitive), then the week's plan.
///
/// Neither card has a section header — the screen promises three stops above
/// the divider, and these are part of ①'s rhythm, not a fourth stop. Each card
/// hides itself while loading, on any failure, and on a server that predates
/// it, so on today's production server this renders nothing at all.
library;

import 'package:flutter/material.dart';

import '../../child_memory/widgets/today_followup_card.dart';
import '../../child_memory/widgets/today_weekly_plan_card.dart';
import '../../onboarding/providers/onboarding_providers.dart';

class TodayLoopCards extends StatelessWidget {
  const TodayLoopCards({super.key, required this.profile});

  /// The active child, or null before one is chosen (then: nothing).
  final ActiveChildProfile? profile;

  @override
  Widget build(BuildContext context) {
    final child = profile;
    if (child == null) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TodayFollowupCard(activeChildId: child.id),
        TodayWeeklyPlanCard(
          childId: child.id,
          childName: child.name,
          ageGroup: child.ageGroup,
        ),
      ],
    );
  }
}
