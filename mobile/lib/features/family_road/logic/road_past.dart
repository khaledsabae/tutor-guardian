/// «ما أضأتموه» — what is behind «أنتم هنا» on «درب {الاسم}», and where
/// «أنتم هنا» itself stands.
///
/// Only what was done: this week's lit days (`/api/family/week`), the lit
/// weeks of the last eight and the running «أسابيع مضيئة» total, and the
/// paths whose every lesson is done («اكتمل البدر»). An unlit day or week is
/// never drawn — an unlit week is not a missed one — and there are no
/// numbers to compare with anyone, only the family's own.
library;

import '../../lanterns/data/family_week.dart';
import '../../program/data/models.dart';
import '../../program/data/progress_models.dart';

/// Where the active child is in the curriculum: the path to resume (most
/// recently touched, not finished) and how many of its lessons are done.
({CurriculumPath path, int done})? resumePath(
  List<CurriculumPath> paths,
  ChildProgressBundle? bundle,
) {
  if (bundle == null || paths.isEmpty) return null;
  for (final lesson in bundle.lessons.reversed) {
    final match = paths.where((p) => p.id == lesson.pathId);
    if (match.isEmpty) continue;
    final p = match.first;
    final done = _doneIn(p, bundle);
    if (done < p.lessonIds.length) return (path: p, done: done);
  }
  return null;
}

/// The next path to begin: the first in the server's order that the child
/// has not touched and that is not the one being resumed.
CurriculumPath? nextPath(
  List<CurriculumPath> paths,
  ChildProgressBundle? bundle,
) {
  final touched = {for (final l in bundle?.lessons ?? const []) l.pathId};
  final resume = resumePath(paths, bundle)?.path.id;
  for (final p in paths) {
    if (p.id == resume || touched.contains(p.id) || p.lessonIds.isEmpty) {
      continue;
    }
    return p;
  }
  return null;
}

/// Paths with every lesson done, most recently finished first.
List<CurriculumPath> fullMoons(
  List<CurriculumPath> paths,
  ChildProgressBundle? bundle,
) {
  if (bundle == null) return const [];
  final done = [
    for (final p in paths)
      if (p.lessonIds.isNotEmpty && _doneIn(p, bundle) >= p.lessonIds.length)
        (p, _lastDone(p, bundle)),
  ]..sort((a, b) => b.$2.compareTo(a.$2));
  return [for (final (p, _) in done) p];
}

int _doneIn(CurriculumPath p, ChildProgressBundle b) => b.lessons
    .where((l) => l.pathId == p.id && l.status == ProgressStatus.completed)
    .length;

String _lastDone(CurriculumPath p, ChildProgressBundle b) {
  var last = '';
  for (final l in b.lessons) {
    if (l.pathId == p.id && (l.completedAt ?? '').compareTo(last) > 0) {
      last = l.completedAt!;
    }
  }
  return last;
}

class RoadPast {
  const RoadPast({
    this.weekLanterns = 0,
    this.earlierLitWeeks = 0,
    this.litWeeksTotal = 0,
    this.fullMoonTitles = const [],
  });

  /// This week's lit days (0–7).
  final int weekLanterns;

  /// Lit weeks among the seven before this one — drawn as lit lanterns only.
  final int earlierLitWeeks;

  /// «أسابيع مضيئة» since the start; never resets.
  final int litWeeksTotal;

  /// «اكتمل البدر»: finished paths, most recent first.
  final List<String> fullMoonTitles;

  /// Nothing done yet: the road begins at «أنتم هنا», with no lantern
  /// waiting below it.
  bool get isEmpty =>
      weekLanterns == 0 &&
      earlierLitWeeks == 0 &&
      litWeeksTotal == 0 &&
      fullMoonTitles.isEmpty;

  /// Whether the «since the start» line has anything to add to the rows
  /// above it (this week alone is already shown).
  bool get showsTotal =>
      litWeeksTotal > (weekLanterns > 0 ? 1 : 0) || earlierLitWeeks > 0;

  factory RoadPast.from(FamilyWeek? week, List<CurriculumPath> moons) {
    final earlier = week == null || week.last8.isEmpty
        ? 0
        : week.last8
              .take(week.last8.length - 1)
              .where((w) => w.lit)
              .length;
    return RoadPast(
      weekLanterns: week?.lanterns ?? 0,
      earlierLitWeeks: earlier,
      litWeeksTotal: week?.litWeeksTotal ?? 0,
      fullMoonTitles: [for (final p in moons) p.title],
    );
  }
}
