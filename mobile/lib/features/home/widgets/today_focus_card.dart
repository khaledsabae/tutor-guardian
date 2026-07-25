/// The home tab's single primary action: resume the path the child is
/// actually in the middle of, or — when there is none — the nudge that starts
/// the first one. It leads the screen because it is the only card that knows
/// what the parent should do next.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/animated_progress_bar.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/emoji_hero.dart';
import '../../program/data/models.dart';
import '../../program/data/progress_models.dart';
import '../../program/providers/program_providers.dart';

class TodayFocusCard extends ConsumerWidget {
  const TodayFocusCard({
    super.key,
    required this.bundle,
    required this.ageGroup,
    required this.onStartFirstPath,
  });
  final ChildProgressBundle? bundle;
  final String ageGroup;
  final VoidCallback onStartFirstPath;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final asyncPaths =
        ref.watch(pathsListProvider(PathsListArgs(ageGroup: ageGroup)));
    final paths = asyncPaths.maybeWhen(
      data: (env) => env.paths,
      orElse: () => const <CurriculumPath>[],
    );

    // The path to resume: most recently touched non-completed path.
    CurriculumPath? resume;
    int done = 0;
    if (bundle != null && paths.isNotEmpty) {
      for (final lesson in bundle!.lessons.reversed) {
        final match =
            paths.where((p) => p.id == lesson.pathId).toList();
        if (match.isEmpty) continue;
        final p = match.first;
        final completedInPath = bundle!.lessons
            .where((l) =>
                l.pathId == p.id && l.status == ProgressStatus.completed)
            .length;
        if (completedInPath < p.lessonIds.length) {
          resume = p;
          done = completedInPath;
          break;
        }
      }
    }

    if (resume == null) {
      // Nudge: no in-progress path yet.
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: Dt.primaryGradient,
          borderRadius: BorderRadius.circular(Dt.rCard),
          boxShadow: Dt.softShadow(Dt.primary),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const EmojiHero(emoji: '🚀', size: 48),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    l10n.startFirstPath,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              l10n.startFirstPathDesc,
              style: TextStyle(
                color: Colors.white.withValues(alpha: .92),
                height: 1.5,
              ),
            ),
            const SizedBox(height: 14),
            BouncyButton(
              label: l10n.browsePaths,
              color: Dt.accent,
              onTap: onStartFirstPath,
            ),
          ],
        ),
      ).animate().fadeIn(duration: Dt.base).slideY(begin: .06);
    }

    final style = styleFor(resume.domain);
    final total = resume.lessonIds.length;
    final fraction = total == 0 ? 0.0 : done / total;
    final remaining = total - done;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: style.gradient,
        borderRadius: BorderRadius.circular(Dt.rCard),
        boxShadow: Dt.softShadow(style.base),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              EmojiHero(emoji: style.emoji, size: 48),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.continueJourney,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: .85),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      resume.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: AnimatedProgressBar(
                  value: fraction,
                  color: Colors.white,
                  trackColor: Colors.white.withValues(alpha: .25),
                  height: 12,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '$done/$total',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            remaining == 1 ? l10n.lessonsRemaining_one : l10n.lessonsRemaining_other(remaining),
            style: TextStyle(
              color: Colors.white.withValues(alpha: .9),
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          BouncyButton(
            label: l10n.continueBtn,
            color: Colors.white.withValues(alpha: .22),
            edgeColor: Colors.white.withValues(alpha: .35),
            onTap: () => Navigator.of(context).push(
              AppRoutes.pathDetail(resume!.id, ageGroup),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: Dt.base).slideY(begin: .06);
  }
}
