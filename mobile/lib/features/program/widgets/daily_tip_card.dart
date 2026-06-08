/// Daily Tip card — small surface that surfaces the day's parenting
/// tip on top of the chat. Driven by [dailyTipProvider] filtered by
/// the active child's age group (from [activeChildProfileProvider]).
///
/// If the child profile isn't loaded yet (post-onboarding race), the
/// card gracefully hides itself rather than show a loading skeleton
/// that competes with the chat for attention.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/models.dart';
import '../providers/program_providers.dart';

class DailyTipCard extends ConsumerWidget {
  const DailyTipCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(activeChildProfileProvider);
    if (profile == null) {
      return const SizedBox.shrink();
    }
    final args = DailyTipArgs(ageGroup: profile.ageGroup);
    final asyncTip = ref.watch(dailyTipProvider(args));
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: asyncTip.when(
        data: (tip) => _Card(tip: tip, childName: profile.name),
        loading: () => const SizedBox.shrink(),
        error: (_, __) => const SizedBox.shrink(),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.tip, required this.childName});
  final DailyTip tip;
  final String childName;

  @override
  Widget build(BuildContext context) {
    return Container(
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
            child: const Icon(Icons.wb_sunny_outlined,
                color: Color(0xFF8A5A0F), size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      'نصيحة اليوم لـ $childName',
                      style: const TextStyle(
                        color: Color(0xFF8A5A0F),
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.4),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        tip.timeOfDayLabel,
                        style: const TextStyle(
                          color: Color(0xFF8A5A0F),
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  tip.text,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 13,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
