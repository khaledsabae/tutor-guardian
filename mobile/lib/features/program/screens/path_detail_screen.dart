/// Path detail screen — shows the full path description + the lessons
/// as «درب المسار» (a zigzag of stations on a paper road under a paper sky),
/// then a "start" button.
///
/// Reads [pathDetailProvider] (with `?include=lessons`). Each lesson
/// is a tappable station that navigates to [LessonScreen]. The
/// active child's completion ratio (via [pathProgressMapProvider])
/// drives both the header progress bar and the stations: a finished lesson
/// is a lit lantern, Noor waits on the next one, the road between two
/// finished lessons is gold. When the last lesson is finished from here,
/// «اكتمل البدر» shows once for the path ([showFullMoonMoment]).
library;


import 'dart:async';

import 'package:flutter/foundation.dart' show listEquals;
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';


import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/animated_progress_bar.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/error_retry_view.dart';
import '../../reflections/widgets/reflection_note_badge.dart';
import '../data/models.dart';
import '../data/progress_models.dart';
import '../providers/program_providers.dart';
import '../providers/progress_providers.dart';
import 'lesson_screen.dart';
import '../../../config/app_config.dart';
import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../share/share_service.dart';
import '../../share/shareable_moment_card.dart';
import 'package:almorabbi/core/motion.dart';
import 'package:almorabbi/widgets/ui/loading_view.dart';
import '../../../widgets/ui/art_image.dart';
import '../../../widgets/ui/brand_glyph.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';
import '../../home/widgets/sky_band.dart';
import '../../home/widgets/today_road.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../widgets/full_moon_moment.dart';



/// Domain → header illustration: the «ورق مقصوص» domain scenes, each its own
/// emerald card. Curriculum domain `medical` maps to the `health` art.
String? _domainIllustration(String domain) {
  const map = {
    'islamic_parenting': 'domain_islamic_parenting',
    'aqeedah': 'domain_aqeedah',
    'development': 'domain_development',
    'cyber': 'domain_cyber',
    'medical': 'domain_health',
  };
  final name = map[domain];
  return name == null ? null : 'assets/svg/art/$name.svg';
}

class PathDetailScreen extends ConsumerWidget {
  const PathDetailScreen({
    super.key,
    required this.pathId,
    required this.ageGroup,
  });

  final String pathId;
  final String ageGroup;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final args = PathDetailArgs(pathId: pathId, includeLessons: true);
    final asyncDetail = ref.watch(pathDetailProvider(args));

    return Scaffold(
      appBar: AppBar(
        title: Text(
          asyncDetail.maybeWhen(
            data: (d) => d.path.title,
            orElse: () => AppLocalizations.of(context).pathDetailTitle,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: asyncDetail.when(
        data: (detail) => _Body(
          detail: detail,
          ageGroup: ageGroup,
          childId: ref.watch(activeChildIdProvider),
        ),
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: LoadingView(count: 3, itemHeight: 160),
        ),
        error: (err, _) => EmptyState(
          emoji: '📡',
          title: AppLocalizations.of(context).pathsError,
          subtitle: userFacingError(context, err).body,
          actionLabel: AppLocalizations.of(context).retry,
          onAction: () => ref.invalidate(pathDetailProvider(args)),
        ),
      ),
    );
  }
}

class _Body extends ConsumerStatefulWidget {
  const _Body({
    required this.detail,
    required this.ageGroup,
    required this.childId,
  });
  final PathDetail detail;
  final String ageGroup;
  final int? childId;

  @override
  ConsumerState<_Body> createState() => _BodyState();
}

class _BodyState extends ConsumerState<_Body> {
  /// A path just went from not-all to all lessons done while this screen was
  /// open. «اكتمل البدر» waits for the screen to be on top again — the parent
  /// is usually still inside the last lesson when the progress arrives.
  bool _moonDue = false;

  PathDetail get detail => widget.detail;

  bool _allDone(PathProgressMap? m) =>
      m != null &&
      detail.lessons.isNotEmpty &&
      detail.lessons
          .every((l) => m.statusFor(l.id) == ProgressStatus.completed);

  void _onProgress(
    AsyncValue<PathProgressMap>? prev,
    AsyncValue<PathProgressMap> next,
  ) {
    // Only a change seen here counts: a path opened already finished has no
    // «before» on this screen, and stays quiet.
    final before = prev?.valueOrNull;
    final after = next.valueOrNull;
    if (before == null || after == null) return;
    if (!_allDone(before) && _allDone(after)) {
      _moonDue = true;
      unawaited(_maybeShowMoon());
    }
  }

  /// Shows the full moon if one is due, this screen is on top, and this
  /// path has not had its moon on this device before.
  Future<void> _maybeShowMoon() async {
    if (!_moonDue || !mounted) return;
    if (ModalRoute.of(context)?.isCurrent == false) return;
    _moonDue = false;
    final path = detail.path;
    final prefs = await ref.read(sharedPreferencesProvider.future);
    final shown = prefs.getStringList(kFullMoonShownKey) ?? const <String>[];
    if (shown.contains(path.id)) return;
    await prefs.setStringList(kFullMoonShownKey, [...shown, path.id]);
    if (!mounted) return;
    await showFullMoonMoment(
      context,
      pathTitle: path.title,
      onShare: () => _sharePathCompletion(context, path),
    );
  }

  Future<void> _openLesson(String lessonId) async {
    await Navigator.of(context).push(
      AppRoutes.lesson(lessonId, widget.ageGroup, childId: widget.childId),
    );
    // Back from the lesson: the moon, if finishing it finished the path.
    unawaited(_maybeShowMoon());
  }

  @override
  Widget build(BuildContext context) {
    final path = detail.path;
    final childId = widget.childId;
    final total = detail.lessons.length;
    // Drive the progress map from the active child.
    final progressArgs = childId == null
        ? null
        : PathProgressArgs(
            childId: childId,
            pathId: path.id,
            totalLessonsInPath: total,
          );
    if (progressArgs != null) {
      ref.listen<AsyncValue<PathProgressMap>>(
        pathProgressMapProvider(progressArgs),
        _onProgress,
      );
    }
    final asyncProgress = progressArgs == null
        ? null
        : ref.watch(pathProgressMapProvider(progressArgs));
    final progressMap = asyncProgress?.maybeWhen(
      data: (m) => m,
      orElse: () => null,
    );
    final style = styleFor(path.domain);
    final statuses = [
      for (final l in detail.lessons)
        progressMap?.statusFor(l.id) ?? ProgressStatus.notStarted,
    ];
    // Noor waits on the first lesson not yet finished — not while the
    // child's progress is still on its way (she would hop on arrival).
    final firstOpen = statuses.indexWhere((s) => s != ProgressStatus.completed);
    final noorAt = childId != null && progressMap == null ? null : firstOpen;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        _Header(
          path: path,
          childId: childId,
          style: style,
          progress: progressMap,
        ),
        const SizedBox(height: 16),
        if (_domainIllustration(path.domain) != null) ...[
          // A square card: full width would be a screen of art above the
          // lessons, so it is held to a header's height.
          ArtImage(_domainIllustration(path.domain)!, height: 180),
          const SizedBox(height: 16),
        ],
        // Prominent video preview for the whole unit (the path's intro video).
        if (path.videoMp4 != null) ...[
          _PathVideoCard(
            title: path.title,
            style: style,
            onTap: () {
              final raw = path.videoMp4!;
              final url = raw.startsWith('http')
                  ? raw
                  : '${AppConfig.apiBaseUrl}/$raw';
              Navigator.push(
                context,
                AppRoutes.video(
                  url,
                  AppLocalizations.of(context).pathDetailVideoUnit(path.title),
                ),
              );
            },
          ),
          const SizedBox(height: 20),
        ],
        if (path.primaryReference != null) ...[
          _ReferenceCard(ref: path.primaryReference!),
          const SizedBox(height: 20),
        ],
        Text(
          AppLocalizations.of(context).pathDetailLessons(detail.lessons.length),
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        if (detail.lessons.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: EmptyState(
              emoji: '📭',
              title: AppLocalizations.of(context).pathDetailEmpty,
            ),
          )
        else ...[
          // The sky the road comes down from — the same paper sky of the hour
          // as on «اليوم». Decoration only: no words on it.
          const ExcludeSemantics(
            child: SkyBand(
              key: ValueKey('path_trail_sky'),
              child: SizedBox(width: double.infinity, height: 6),
            ),
          ),
          _Trail(
            lessons: detail.lessons,
            statuses: statuses,
            noorAt: noorAt,
            onTap: (i) => _openLesson(detail.lessons[i].id),
          ),
        ],
        const SizedBox(height: 16),
        // The primary button was hard-wired to `lessons.first` no matter what
        // the parent had already done, so finishing lesson 1 and coming back
        // the next day meant pressing «ابدأ المسار» and being dropped straight
        // back into the lesson just completed — onto a CTA already greyed out
        // reading «أتممت هذا الدرس». The only way forward was to spot the right
        // row in the trail below. Everything needed to do better —
        // `progressMap`, `statusFor` — was already in scope, ten lines up.
        Builder(builder: (context) {
          CurriculumLesson? next;
          for (final l in detail.lessons) {
            final s = progressMap?.statusFor(l.id) ?? ProgressStatus.notStarted;
            if (s != ProgressStatus.completed) {
              next = l;
              break;
            }
          }
          // Every lesson done: the button replays the path from the top, which
          // is a deliberate choice rather than a dead end.
          next ??= detail.lessons.isEmpty ? null : detail.lessons.first;
          final resuming = (progressMap?.completedCount ?? 0) > 0;
          return BouncyButton(
            label: resuming
                ? AppLocalizations.of(context).pathDetailContinue
                : AppLocalizations.of(context).pathDetailStart,
            color: style.base,
            icon: const Icon(Icons.play_arrow, color: Colors.white),
            onTap: next == null ? null : () => _openLesson(next!.id),
          );
        }),
        if (progressMap != null && progressMap.completedCount == total) ...[
          const SizedBox(height: 12),
          BouncyButton(
            label: AppLocalizations.of(context).pathDetailShare,
            color: Dt.surface,
            icon: Icon(Icons.share, color: AppTheme.primary),
            onTap: () => _sharePathCompletion(context, detail.path),
          ),
        ],
      ],
    );
  }

  void _sharePathCompletion(BuildContext context, CurriculumPath path) {
    Analytics.shareMoment('path');
    final share = pathCompletionShare(AppLocalizations.of(context),
        title: path.title, description: path.description);
    ShareService.shareMomentCard(
      fileTag: 'path_${path.id}',
      message: share.message,
      card: share.card,
    );
  }
}

/// A finished path, as the parent shares it. The path's [title] and
/// [description] are content and travel as the server sent them.
MomentShare pathCompletionShare(
  AppLocalizations l10n, {
  required String title,
  required String description,
}) =>
    (
      message: l10n.sharePathCompleteMessage(title),
      card: ShareableMomentCard(
        emoji: '🌟',
        eyebrow: l10n.sharePathCompleteEyebrow,
        headline: title,
        body: description,
      ),
    );

class _Header extends ConsumerWidget {
  const _Header({
    required this.path,
    required this.childId,
    required this.style,
    required this.progress,
  });
  final CurriculumPath path;
  final int? childId;
  final DomainStyle style;
  final PathProgressMap? progress;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncBundle =
        childId == null ? null : ref.watch(childProgressProvider(childId!));
    final streak = asyncBundle?.maybeWhen(
          data: (b) => b.streakDays,
          orElse: () => 0,
        ) ??
        0;
    final percent = progress == null ? null : (progress!.fraction * 100).round();
    return Hero(
      tag: 'path-${path.id}',
      child: Container(
        decoration: BoxDecoration(
          gradient: style.gradient,
          borderRadius: BorderRadius.circular(Dt.rCard),
          boxShadow: Dt.softShadow(style.base),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(Dt.rCard),
          child: Stack(
            children: [
              // Big translucent emoji watermark.
              PositionedDirectional(
                start: -16,
                bottom: -24,
                child: Opacity(
                  opacity: .15,
                  child: Text(
                    style.emoji,
                    style: const TextStyle(fontSize: 130),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // The age band belongs to the child; the lessons below
                        // it are addressed to the parent. Say so on the badge
                        // rather than leaving the reader to infer it.
                        //
                        // Age and domain stay two badges here. Combining them,
                        // as the list card does, overflowed this header into
                        // three wrapped lines on a real screen — caught on an
                        // emulator, invisible to every test.
                        //
                        // The two wrap under each other rather than push the
                        // streak chip off the card at large text (200%).
                        Expanded(
                          child: Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            children: [
                              _Badge(
                                text: AppLocalizations.of(context)
                                    .pathAudienceAge(path.ageLabel(
                                        AppLocalizations.of(context))),
                              ),
                              _Badge(
                                text: path.domainLabel(
                                    AppLocalizations.of(context)),
                              ),
                            ],
                          ),
                        ),
                        if (childId != null) ...[
                          const SizedBox(width: 8),
                          StreakChip(streakDays: streak, dark: true),
                        ],
                      ],
                    ),

                    const SizedBox(height: 14),
                    Text(
                      path.title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        height: 1.3,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      path.description,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.92),
                        height: 1.55,
                      ),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        _Badge(text: AppLocalizations.of(context).pathDetailDays(path.estimatedDays)),
                        const SizedBox(width: 8),
                        _Badge(text: AppLocalizations.of(context).pathDetailLessonsCount(path.lessonIds.length)),
                        if (path.videoMp4 != null) ...[
                          const SizedBox(width: 8),
                          _ClickableBadge(
                            text: AppLocalizations.of(context).pathDetailVideoIntro,
                            onTap: () {
                              final raw = path.videoMp4!;
                              final url = raw.startsWith('http')
                                  ? raw
                                  : '${AppConfig.apiBaseUrl}/$raw';
                              Navigator.push(
                                context,
                                AppRoutes.video(
                                  url,
                                  AppLocalizations.of(context)
                                      .pathDetailVideoIntroTitle(path.title),
                                ),
                              );
                            },
                          ),
                        ],
                      ],
                    ),
                    if (progress != null && percent != null) ...[
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: AnimatedProgressBar(
                              value: progress!.fraction,
                              // onPrimary, not Dt.surface: the bar sits on the
                              // domain gradient, and surface turns dark (and
                              // invisible) in the dark theme.
                              color: context.colors.onPrimary,
                              trackColor:
                                  Colors.white.withValues(alpha: .25),
                              height: 12,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Text(
                            '${progress!.completedCount}/${progress!.totalLessonsInPath} ($percent%)',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ],
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

class _Badge extends StatelessWidget {
  const _Badge({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(Dt.rChip),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _ClickableBadge extends StatelessWidget {
  const _ClickableBadge({required this.text, required this.onTap});
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.18),
      borderRadius: BorderRadius.circular(Dt.rChip),
      child: InkWell(
        borderRadius: BorderRadius.circular(Dt.rChip),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          child: Text(
            text,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }
}

/// Streak chip — "X يوم متتالي" — the device's consecutive-day completion
/// streak, said quietly: no flame and no warm badge colours. The lanterns on
/// the road are the app's language of progress now (NOOR_WAL_QANADIL_PLAN),
/// so this chip only states the fact, and says nothing at zero — the old
/// «ابدأ سلسلتك اليوم» nudge was a push, not a fact. When [dark] is true the
/// chip sits on a coloured background (the header card).
class StreakChip extends StatelessWidget {
  const StreakChip({
    super.key,
    required this.streakDays,
    this.dark = false,
  });
  final int streakDays;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    if (streakDays <= 0) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: dark
            ? Colors.white.withValues(alpha: 0.18)
            : context.colors.surfaceAlt,
        borderRadius: BorderRadius.circular(Dt.rChip),
      ),
      child: Text(
        '$streakDays ${_daysLabel(AppLocalizations.of(context), streakDays)}',
        style: TextStyle(
          color: dark ? Colors.white : context.colors.textSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  static String _daysLabel(AppLocalizations l10n, int n) {
    // Arabic grammatical agreement for "يوم" (day).
    if (n == 1) return l10n.pathDetailStreakDay1;
    if (n == 2) return l10n.pathDetailStreakDay2;
    if (n >= 3 && n <= 10) return l10n.pathDetailStreakDaysFew;
    return l10n.pathDetailStreakDaysMany;
  }
}

class _ReferenceCard extends StatelessWidget {
  const _ReferenceCard({required this.ref});
  final PathReference ref;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.warningBg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('📖', style: TextStyle(fontSize: 22)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _refTypeLabel(context, ref.type),
                  style: TextStyle(
                    color: AppTheme.warningFg,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  ref.info,
                  style: TextStyle(
                    color: AppTheme.warningFg,
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

  static String _refTypeLabel(BuildContext context, String wire) {
    final l10n = AppLocalizations.of(context);
    switch (wire) {
      case 'كتاب_تربوي':
        return l10n.pathDetailRefMain;
      case 'حديث':
        return l10n.pathDetailRefHadith;
      case 'بحث_علمي':
        return l10n.pathDetailRefResearch;
      case 'مقال_تنموي':
        return l10n.pathDetailRefDevArticle;
      default:
        return wire;
    }
  }
}

// ── «درب المسار»: the lessons as stations on one paper road ──────────────
//
// The road is cut from the paper of «درب اليوم» ([RoadRailPainter.paintStrip]):
// a flat strip with an offset shadow, gold where it was walked. A finished
// lesson is a lit lantern; Noor waits, small, on the next one; the rest are
// quiet paper. The zigzag and the row height are the trail's old geometry.

const double _kTrailRowHeight = 120;
const double _kNodeSize = 72;
const double _kNodeInset = 36; // node-center distance from row edge
const double _kStationSize = 64;

/// The trail: one road painted under all the rows, then the rows.
class _Trail extends StatelessWidget {
  const _Trail({
    required this.lessons,
    required this.statuses,
    required this.noorAt,
    required this.onTap,
  });

  final List<CurriculumLesson> lessons;
  final List<ProgressStatus> statuses;

  /// The station Noor stands on; null for none (every lesson finished, or
  /// the progress still loading).
  final int? noorAt;
  final void Function(int index) onTap;

  @override
  Widget build(BuildContext context) {
    bool done(int i) => statuses[i] == ProgressStatus.completed;
    return Stack(
      children: [
        Positioned.fill(
          child: CustomPaint(
            key: const ValueKey('path_trail_road'),
            painter: PathTrailPainter(
              walked: [
                for (var i = 0; i < lessons.length; i++)
                  // Into the first station once it is finished; after that,
                  // only the road between two finished lessons is walked.
                  i == 0 ? done(0) : done(i - 1) && done(i),
              ],
              paper: RoadRailPainter.paperFor(Theme.of(context).brightness),
              textDirection: Directionality.of(context),
            ),
          ),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (var i = 0; i < lessons.length; i++)
              _TrailRow(
                index: i,
                lesson: lessons[i],
                status: statuses[i],
                noorHere: i == noorAt,
                onTap: () => onTap(i),
              ),
          ],
        ),
      ],
    );
  }
}

class _TrailRow extends StatelessWidget {
  const _TrailRow({
    required this.index,
    required this.lesson,
    required this.status,
    required this.noorHere,
    required this.onTap,
  });

  final int index;
  final CurriculumLesson lesson;
  final ProgressStatus status;
  final bool noorHere;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final alignEnd = index.isOdd; // zigzag
    final node = _LessonNode(
      index: index,
      lesson: lesson,
      status: status,
      noorHere: noorHere,
      alignEnd: alignEnd,
      onTap: onTap,
    );
    return Semantics(
      button: true,
      label: AppLocalizations.of(context).pathDetailTrailLesson(
          index + 1, progressStatusLabel(status), lesson.title),
      onTap: onTap,
      excludeSemantics: true,
      child: SizedBox(
        height: _kTrailRowHeight,
        child: Align(
          alignment: alignEnd
              ? AlignmentDirectional.centerEnd
              : AlignmentDirectional.centerStart,
          child: Padding(
            padding: const EdgeInsetsDirectional.only(start: 12, end: 12),
            child: node,
          ),
        ),
      ),
    );
  }
}

class _LessonNode extends StatelessWidget {
  const _LessonNode({
    required this.index,
    required this.lesson,
    required this.status,
    required this.noorHere,
    required this.alignEnd,
    required this.onTap,
  });

  final int index;
  final CurriculumLesson lesson;
  final ProgressStatus status;
  final bool noorHere;
  final bool alignEnd; // the station must hug the row edge for the road
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Widget station;
    if (status == ProgressStatus.completed) {
      station = _LanternStation(key: ValueKey('trail_lantern_$index'));
    } else if (noorHere) {
      // Gentle two-pulse on appear, then static (performance budget) — and
      // Noor herself rests too: a list of lessons is no place for a loop.
      station = SizedBox.square(
        key: ValueKey('trail_noor_$index'),
        dimension: _kNodeSize,
        child: const Center(
          child: TickerMode(
            enabled: false,
            child: NoorPresence(size: 52, face: NoorFaceState.awake),
          ),
        ),
      )
          .animate(onPlay: loopUnlessReduced(context, count: 2))
          .scale(
            begin: const Offset(1, 1),
            end: const Offset(1.06, 1.06),
            duration: 600.ms,
            curve: Curves.easeInOut,
          )
          .then()
          .scale(
            begin: const Offset(1.06, 1.06),
            end: const Offset(1, 1),
            duration: 600.ms,
            curve: Curves.easeInOut,
          );
    } else {
      station = _PaperStation(
        key: ValueKey('trail_paper_$index'),
        started: status == ProgressStatus.inProgress,
      );
    }

    final info = Expanded(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment:
            alignEnd ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Text(
            lesson.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            textAlign: alignEnd ? TextAlign.end : TextAlign.start,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 3),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                AppLocalizations.of(context).pathDetailMinutes(lesson.estimatedMinutes),
                style: TextStyle(
                  fontSize: 11,
                  color: AppTheme.textMuted,
                ),
              ),
              if (lesson.needsProfessionalFollowup)
                _FlagChip(
                  text: AppLocalizations.of(context).pathDetailFollowup,
                  color: AppTheme.dangerFg,
                  bg: AppTheme.dangerBg,
                ),
              // Phase 8-C — "ملاحظة" badge if the user has a
              // reflection on this lesson.
              ReflectionNoteBadge(lessonId: lesson.id),
            ],
          ),
        ],
      ),
    );

    final node = SizedBox.square(
      dimension: _kNodeSize,
      child: Center(child: station),
    );

    // The station hugs the row edge so the road painter's node-center math
    // holds for both zigzag sides.
    return BouncyTap(
      onTap: onTap,
      child: SizedBox(
        width: 200,
        child: Row(
          children: alignEnd
              ? [info, const SizedBox(width: 10), node]
              : [node, const SizedBox(width: 10), info],
        ),
      ),
    );
  }
}

/// A cut-paper drop under a station: flat, offset, no blur (STYLE.md).
const _kStationShadow = [
  BoxShadow(color: Color(0x330F3D36), offset: Offset(2, 3)),
];

/// A finished lesson: a lit lantern on a disc of its own light.
class _LanternStation extends StatelessWidget {
  const _LanternStation({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: _kStationSize,
      height: _kStationSize,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        color: RoadRailPainter.gold,
        boxShadow: _kStationShadow,
      ),
      child: const BrandGlyph(BrandIcon.lantern, size: 40),
    );
  }
}

/// A lesson not reached yet: quiet paper, its book glyph muted until begun.
class _PaperStation extends StatelessWidget {
  const _PaperStation({super.key, required this.started});

  final bool started;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: _kStationSize,
      height: _kStationSize,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: dark ? _kPaperDark : _kPaperLight,
        border: started
            ? Border.all(color: RoadRailPainter.gold, width: 2.5)
            : dark
                ? null
                : Border.all(color: _kPaperEdge, width: 1.5),
        boxShadow: _kStationShadow,
      ),
      child: BrandGlyph(
        BrandIcon.openBook,
        size: 30,
        color: started ? null : context.colors.textSecondary,
      ),
    );
  }
}

// The station paper (assets/svg/STYLE.md), the same sheets as «اليوم».
const _kPaperLight = Color(0xFFFBF1DE);
const _kPaperEdge = Color(0xFFD9C7A7);
const _kPaperDark = Color(0xFF1F4A43);

/// The road under «درب المسار»: down from the sky to the first station, then
/// a soft curve from each station to the next on the zigzag. [walked] has one
/// entry per stretch — the way into station i — and is gold only between two
/// finished lessons (and into the first, once it is finished).
class PathTrailPainter extends CustomPainter {
  PathTrailPainter({
    required this.walked,
    required this.paper,
    required this.textDirection,
  });

  final List<bool> walked;
  final Color paper;
  final TextDirection textDirection;

  /// The strip is wider than «اليوم»'s: the stations here are 64, not 28.
  static const width = 10.0;

  Offset _station(int i, double w) {
    // "start"/"end" are directional; resolve to pixels.
    final logicalEnd =
        textDirection == TextDirection.rtl ? !i.isOdd : i.isOdd;
    const inset = 12 + _kNodeInset;
    return Offset(
      logicalEnd ? w - inset : inset,
      i * _kTrailRowHeight + _kTrailRowHeight / 2,
    );
  }

  @override
  void paint(Canvas canvas, Size size) {
    for (var i = 0; i < walked.length; i++) {
      final to = _station(i, size.width);
      final Path path;
      if (i == 0) {
        path = Path()
          ..moveTo(to.dx, 0)
          ..lineTo(to.dx, to.dy);
      } else {
        final from = _station(i - 1, size.width);
        final dy = to.dy - from.dy;
        path = Path()
          ..moveTo(from.dx, from.dy)
          ..cubicTo(
            from.dx,
            from.dy + dy * .7,
            to.dx,
            to.dy - dy * .7,
            to.dx,
            to.dy,
          );
      }
      RoadRailPainter.paintStrip(
        canvas,
        path,
        walked: walked[i],
        paper: paper,
        width: width,
      );
    }
  }

  @override
  bool shouldRepaint(PathTrailPainter old) =>
      !listEquals(old.walked, walked) ||
      old.paper != paper ||
      old.textDirection != textDirection;
}

class _FlagChip extends StatelessWidget {
  const _FlagChip({required this.text, required this.color, required this.bg});
  final String text;
  final Color color;
  final Color bg;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style:
            TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// Prominent, tappable video preview shown at the top of a unit (path).
class _PathVideoCard extends StatelessWidget {
  const _PathVideoCard({
    required this.title,
    required this.style,
    required this.onTap,
  });

  final String title;
  final DomainStyle style;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return BouncyTap(
      onTap: onTap,
      child: Container(
        height: 150,
        width: double.infinity,
        decoration: BoxDecoration(
          gradient: style.gradient,
          borderRadius: BorderRadius.circular(Dt.rCard),
          boxShadow: Dt.softShadow(style.base),
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            Positioned(
              right: -8,
              bottom: -18,
              child: Text(
                '🎬',
                style: TextStyle(
                  fontSize: 120,
                  color: Colors.white.withValues(alpha: .12),
                ),
              ),
            ),
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: .94), // audit-ok: play button over a video thumbnail — the ground is the frame, not the theme
                    shape: BoxShape.circle,
                    boxShadow: Dt.softShadow(Colors.black, alpha: .15),
                  ),
                  child: Icon(Icons.play_arrow_rounded,
                      size: 46, color: style.base),
                ),
                const SizedBox(height: 10),
                Text(
                  AppLocalizations.of(context).pathDetailVideoIntro,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
