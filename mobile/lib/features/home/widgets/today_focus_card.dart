/// The home tab's single primary action: resume the path the child is
/// actually in the middle of, or — when there is none — the nudge that starts
/// the first one. It leads the screen because it is the only card that knows
/// what the parent should do next.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/animated_progress_bar.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/brand_glyph.dart';
import '../../../widgets/ui/emoji_hero.dart';
import '../../program/data/models.dart';
import '../../program/data/progress_models.dart';
import '../../program/providers/program_providers.dart';
import '../../program/providers/progress_providers.dart';

/// Raised to make the card do what its own primary button does.
///
/// The first-run tour's mark (tour v3) is a stand-in for this card: «ابدأ من
/// هنا», and tapping it must start, not dismiss. Only the card knows what its
/// button means right now — the first lesson, browsing while that loads, or
/// continuing a path — so the tour asks the card instead of guessing.
final todayFocusOpenProvider = StateProvider<int>((_) => 0);

/// The lessons of [path] this child has completed — only ids the path still
/// lists. A progress row for a lesson since removed from the path (or a
/// duplicate row) used to count toward «2/4», so the bar could run ahead of
/// the path and a path with one lesson left could read as finished.
Set<String> completedLessonIdsIn(
  CurriculumPath path,
  ChildProgressBundle? bundle,
) {
  if (bundle == null) return const {};
  final listed = path.lessonIds.toSet();
  return {
    for (final l in bundle.lessons)
      if (l.pathId == path.id &&
          l.status == ProgressStatus.completed &&
          listed.contains(l.lessonId))
        l.lessonId,
  };
}

/// The lesson «متابعة» opens: the first lesson of [path], in curriculum
/// order, this child has not completed. An `inProgress` lesson is simply
/// "not completed", so a half-read lesson wins only when it is also the
/// earliest open one — a later lesson opened out of order does not jump the
/// queue. This is the rule the path's own «واصل المسار» button uses
/// (path_detail_screen.dart) and the server's `/next-lesson` applies to the
/// starter path, so the card, the path and the server agree on "next".
///
/// `null` when there is nothing to open — progress not loaded yet, a path
/// that lists no lessons, or every lesson done — and the caller falls back
/// to the path overview rather than to nothing.
String? dueLessonIdIn(CurriculumPath path, ChildProgressBundle? bundle) {
  if (bundle == null) return null;
  final completed = completedLessonIdsIn(path, bundle);
  for (final id in path.lessonIds) {
    if (!completed.contains(id)) return id;
  }
  return null;
}

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
    // Every branch below names its primary action once and hands it both to
    // its button and to [todayFocusOpenProvider].
    void primary(VoidCallback action) =>
        ref.listen<int>(todayFocusOpenProvider, (_, _) => action());
    void browse() {
      Analytics.todayBlockTapped('step', 'browse');
      onStartFirstPath();
    }

    final asyncPaths = ref.watch(
      pathsListProvider(PathsListArgs(ageGroup: ageGroup)),
    );
    final paths = asyncPaths.maybeWhen(
      data: (env) => env.paths,
      orElse: () => const <CurriculumPath>[],
    );

    // The path to resume: most recently touched non-completed path.
    CurriculumPath? resume;
    int done = 0;
    if (bundle != null && paths.isNotEmpty) {
      for (final lesson in bundle!.lessons.reversed) {
        final match = paths.where((p) => p.id == lesson.pathId).toList();
        if (match.isEmpty) continue;
        final p = match.first;
        final completed = completedLessonIdsIn(p, bundle);
        // Counted against the path's own list, so «done» never exceeds what
        // the bar can show and a stale row cannot finish a path early.
        final completedInPath = p.lessonIds.where(completed.contains).length;
        if (completedInPath < p.lessonIds.length) {
          resume = p;
          done = completedInPath;
          break;
        }
      }
    }

    if (resume == null) {
      // First run. This used to be a "browse" button that switched to the
      // Learn tab and dropped the parent into a filterable list of 39 paths —
      // four taps between finishing onboarding and reading a single line of
      // the curriculum. 86% of installs add a child; 31% ever open a lesson.
      // So: ask the server which lesson to open, and open it.
      final childId = ref.watch(activeChildIdProvider);
      final asyncNext = ref.watch(
        nextLessonProvider(
          NextLessonArgs(ageGroup: ageGroup, childId: childId),
        ),
      );
      // Only the happy path changes. While loading, or if the endpoint is
      // missing (older backend) or unreachable, the original browse nudge
      // stands — a slow network must never leave this card with no action.
      final next = asyncNext.valueOrNull;

      // `resumed` (never read until now): the child has already completed
      // lessons in the starter path — in fact the endpoint only says so when
      // every lesson of it is done, and hands back its last lesson. Offering
      // that lesson again under «ابدأ هذا الدرس» told a parent who had
      // finished the path that they were at its beginning («أعطال اتلقت في
      // الطريق»). The card says what happened, and points at what is next.
      if (next != null && next.resumed) {
        primary(browse);
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
                  // A finished path earns its medal — drawn, not an emoji
                  // (جولة الحرفة).
                  const GlyphHero(BrandIcon.medal, size: 48),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      l10n.focusPathDoneTitle,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        height: 1.3,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                l10n.focusPathDoneDesc,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: .92),
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 14),
              BouncyButton(
                label: l10n.browsePaths,
                color: Dt.accent,
                onTap: browse,
              ),
            ],
          ),
        ).animate().fadeIn(duration: Dt.base).slideY(begin: .06);
      }

      final VoidCallback start = next == null
          ? browse
          : () {
              Analytics.homeCardTapped('focus_first_lesson');
              Analytics.todayBlockTapped('step', 'first_lesson');
              Navigator.of(context).push(
                AppRoutes.lesson(next.lessonId, ageGroup, childId: childId),
              );
            };
      primary(start);
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
                // Starting the journey lights the lantern — the drawn
                // successor of the 🚀 this card carried (جولة الحرفة).
                const GlyphHero(BrandIcon.lantern, size: 48),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    next?.title ?? l10n.startFirstPath,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              next == null
                  ? l10n.startFirstPathDesc
                  : l10n.startFirstLessonDesc,
              style: TextStyle(
                color: Colors.white.withValues(alpha: .92),
                height: 1.5,
              ),
            ),
            const SizedBox(height: 14),
            BouncyButton(
              label: next == null ? l10n.browsePaths : l10n.startThisLesson,
              color: Dt.accent,
              onTap: start,
            ),
            // Browsing stays reachable — demoted, not removed.
            if (next != null)
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton(
                  onPressed: browse,
                  child: Text(
                    l10n.browsePaths,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: .92),
                      decoration: TextDecoration.underline,
                      decorationColor: Colors.white.withValues(alpha: .6),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ).animate().fadeIn(duration: Dt.base).slideY(begin: .06);
    }

    final path = resume;
    // «متابعة» used to push the path overview, so a parent who tapped
    // "continue" landed on a list and had to find the lesson again (1.0.73,
    // Khaled's phone). It now opens the lesson that is due. The child is the
    // bundle's: the due lesson was worked out from that child's progress.
    final due = dueLessonIdIn(path, bundle);
    final childId = bundle?.childId;
    void openOverview() {
      Analytics.todayBlockTapped('step', 'path_overview');
      Navigator.of(context).push(AppRoutes.pathDetail(path.id, ageGroup));
    }

    void continuePath() {
      Analytics.todayBlockTapped('step', 'continue', lessonId: due);
      Navigator.of(context).push(
        due == null
            // Nothing left to open (or nothing known yet): the overview,
            // never a dead button.
            ? AppRoutes.pathDetail(path.id, ageGroup)
            : AppRoutes.lesson(due, ageGroup, childId: childId),
      );
    }

    primary(continuePath);
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
                  // onPrimary, not Dt.surface: the bar sits on a coloured
                  // gradient, and Dt.surface is a near-black ink in dark
                  // mode — the fill disappeared into the card («أعطال اتلقت
                  // في الطريق»).
                  color: context.colors.onPrimary,
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
            remaining == 1
                ? l10n.lessonsRemaining_one
                : l10n.lessonsRemaining_other(remaining),
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
            onTap: continuePath,
          ),
          // The overview stays one tap away — demoted, not removed.
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton(
              onPressed: openOverview,
              child: Text(
                l10n.focusViewPath,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: .92),
                  decoration: TextDecoration.underline,
                  decorationColor: Colors.white.withValues(alpha: .6),
                ),
              ),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: Dt.base).slideY(begin: .06);
  }
}
