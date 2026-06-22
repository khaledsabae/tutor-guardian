/// Path detail screen — shows the full path description + the lessons
/// rendered as a Duolingo-style zigzag trail, then a "start" button.
///
/// Reads [pathDetailProvider] (with `?include=lessons`). Each lesson
/// is a tappable trail node that navigates to [LessonScreen]. The
/// active child's completion ratio (via [pathProgressMapProvider])
/// drives both the header progress bar and the node states.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/animated_progress_bar.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../../reflections/widgets/reflection_note_badge.dart';
import '../data/models.dart';
import '../data/progress_models.dart';
import '../providers/program_providers.dart';
import '../providers/progress_providers.dart';
import 'lesson_screen.dart';
import 'video_player_screen.dart';
import '../../../config/app_config.dart';

/// Domain → header illustration (solid cream-bg JPGs that blend with the
/// page background). Curriculum domain `medical` maps to the `health` art.
String? _domainIllustration(String domain) {
  const map = {
    'islamic_parenting': 'domain_islamic_parenting',
    'development': 'domain_development',
    'cyber': 'domain_cyber',
    'medical': 'domain_health',
  };
  final name = map[domain];
  return name == null ? null : 'assets/images/generated/$name.webp';
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
            orElse: () => 'تفاصيل المسار',
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
          child: SkeletonList(count: 3, itemHeight: 160),
        ),
        error: (err, _) => EmptyState(
          emoji: '📡',
          title: 'تعذّر تحميل المسار',
          subtitle: '$err',
          actionLabel: 'إعادة المحاولة',
          onAction: () => ref.invalidate(pathDetailProvider(args)),
        ),
      ),
    );
  }
}

class _Body extends ConsumerWidget {
  const _Body({
    required this.detail,
    required this.ageGroup,
    required this.childId,
  });
  final PathDetail detail;
  final String ageGroup;
  final int? childId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final path = detail.path;
    final total = detail.lessons.length;
    // Drive the progress map from the active child.
    final progressArgs = childId == null
        ? null
        : PathProgressArgs(
            childId: childId!,
            pathId: path.id,
            totalLessonsInPath: total,
          );
    final asyncProgress = progressArgs == null
        ? null
        : ref.watch(pathProgressMapProvider(progressArgs));
    final progressMap = asyncProgress?.maybeWhen(
      data: (m) => m,
      orElse: () => null,
    );
    final style = styleFor(path.domain);

    void openLesson(String lessonId) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => LessonScreen(
            lessonId: lessonId,
            ageGroup: ageGroup,
            childId: childId,
          ),
        ),
      );
    }

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
          Image.asset(
            _domainIllustration(path.domain)!,
            fit: BoxFit.contain,
            errorBuilder: (_, __, ___) => const SizedBox.shrink(),
          ),
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
                MaterialPageRoute(
                  builder: (_) => VideoPlayerScreen(
                    url: url,
                    title: '🎥 فيديو الوحدة: ${path.title}',
                  ),
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
          'الدروس (${detail.lessons.length})',
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 4),
        if (detail.lessons.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: EmptyState(
              emoji: '📭',
              title: 'لا توجد دروس في هذا المسار بعد',
            ),
          )
        else
          for (var i = 0; i < detail.lessons.length; i++)
            _TrailRow(
              index: i,
              lesson: detail.lessons[i],
              style: style,
              status: progressMap?.statusFor(detail.lessons[i].id) ??
                  ProgressStatus.notStarted,
              prevStatus: i == 0
                  ? null
                  : progressMap?.statusFor(detail.lessons[i - 1].id) ??
                      ProgressStatus.notStarted,
              onTap: () => openLesson(detail.lessons[i].id),
            ),
        const SizedBox(height: 16),
        BouncyButton(
          label: 'ابدأ المسار',
          color: style.base,
          icon: const Icon(Icons.play_arrow, color: Colors.white),
          onTap: detail.lessons.isEmpty
              ? null
              : () => openLesson(detail.lessons.first.id),
        ),
      ],
    );
  }
}

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
                      children: [
                        _Badge(text: path.ageLabel),
                        const SizedBox(width: 8),
                        _Badge(text: path.domainLabel),
                        const Spacer(),
                        if (childId != null)
                          StreakChip(streakDays: streak, dark: true),
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
                        _Badge(text: '⏱️ ${path.estimatedDays} يوم'),
                        const SizedBox(width: 8),
                        _Badge(text: '📚 ${path.lessonIds.length} دروس'),
                        if (path.videoMp4 != null) ...[
                          const SizedBox(width: 8),
                          _ClickableBadge(
                            text: '🎥 فيديو تعريفي',
                            onTap: () {
                              final raw = path.videoMp4!;
                              final url = raw.startsWith('http')
                                  ? raw
                                  : '${AppConfig.apiBaseUrl}/$raw';
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (context) => VideoPlayerScreen(
                                    url: url,
                                    title: '🎥 فيديو تعريفي لـ ${path.title}',
                                  ),
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
                              color: Colors.white,
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

/// Streak chip — "🔥 X يوم متتالي" — surfaces the device's
/// consecutive-day completion streak. When [dark] is true the chip
/// is meant to be placed on a coloured background (header card).
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
    if (streakDays <= 0) {
      // Empty state — don't show a "0-day streak" chip (it would
      // feel punitive). A short nudge is friendlier.
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: dark
              ? Colors.white.withValues(alpha: 0.18)
              : AppTheme.surfaceAlt,
          borderRadius: BorderRadius.circular(Dt.rChip),
        ),
        child: Text(
          '🔥 ابدأ سلسلتك اليوم',
          style: TextStyle(
            color: dark ? Colors.white : AppTheme.textSecondary,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: dark
            ? Colors.white.withValues(alpha: 0.20)
            : const Color(0xFFFFE9C7),
        borderRadius: BorderRadius.circular(Dt.rChip),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('🔥', style: TextStyle(fontSize: 14)),
          const SizedBox(width: 4),
          Text(
            '$streakDays ${_daysLabel(streakDays)}',
            style: TextStyle(
              color: dark ? Colors.white : const Color(0xFF8A5A0F),
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  static String _daysLabel(int n) {
    // Arabic grammatical agreement for "يوم" (day).
    if (n == 1) return 'يوم متتالي';
    if (n == 2) return 'يومان متتاليان';
    if (n >= 3 && n <= 10) return 'أيام متتالية';
    return 'يوم متتالٍ';
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
                  _refTypeLabel(ref.type),
                  style: const TextStyle(
                    color: AppTheme.warningFg,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  ref.info,
                  style: const TextStyle(
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

  static String _refTypeLabel(String wire) {
    switch (wire) {
      case 'كتاب_تربوي':
        return 'مرجع رئيسي';
      case 'حديث':
        return 'حديث';
      case 'بحث_علمي':
        return 'بحث علمي';
      case 'مقال_تنموي':
        return 'مقال تنموي';
      default:
        return wire;
    }
  }
}

// ── Duolingo-style zigzag trail ──────────────────────────────────────────

const double _kTrailRowHeight = 120;
const double _kNodeSize = 72;
const double _kNodeInset = 36; // node-center distance from row edge

class _TrailRow extends StatelessWidget {
  const _TrailRow({
    required this.index,
    required this.lesson,
    required this.status,
    required this.prevStatus,
    required this.style,
    required this.onTap,
  });

  final int index;
  final CurriculumLesson lesson;
  final ProgressStatus status;
  final ProgressStatus? prevStatus; // null for the first row
  final DomainStyle style;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final alignEnd = index.isOdd; // zigzag
    final node = _LessonNode(
      lesson: lesson,
      status: status,
      style: style,
      order: index + 1,
      alignEnd: alignEnd,
      onTap: onTap,
    );
    return Semantics(
      button: true,
      label:
          'الدرس ${index + 1}: ${lesson.title}. ${progressStatusLabel(status)}',
      onTap: onTap,
      excludeSemantics: true,
      child: SizedBox(
        height: _kTrailRowHeight,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            if (index > 0)
              Positioned.fill(
                child: CustomPaint(
                  painter: _ConnectorPainter(
                    fromEnd: (index - 1).isOdd,
                    toEnd: alignEnd,
                    color: prevStatus == ProgressStatus.completed
                        ? style.base
                        : const Color(0xFFD8D0C2),
                    dashed: prevStatus != ProgressStatus.completed,
                    textDirection: Directionality.of(context),
                  ),
                ),
              ),
            Align(
              alignment: alignEnd
                  ? AlignmentDirectional.centerEnd
                  : AlignmentDirectional.centerStart,
              child: Padding(
                padding: const EdgeInsetsDirectional.only(start: 12, end: 12),
                child: node,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LessonNode extends StatelessWidget {
  const _LessonNode({
    required this.lesson,
    required this.status,
    required this.style,
    required this.order,
    required this.alignEnd,
    required this.onTap,
  });

  final CurriculumLesson lesson;
  final ProgressStatus status;
  final DomainStyle style;
  final int order;
  final bool alignEnd; // circle must hug the row edge for the connector
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Widget circle;
    switch (status) {
      case ProgressStatus.completed:
        circle = Container(
          width: _kNodeSize,
          height: _kNodeSize,
          decoration: BoxDecoration(
            gradient: style.gradient,
            shape: BoxShape.circle,
            boxShadow: Dt.softShadow(style.base),
          ),
          child: const Icon(Icons.check_rounded,
              color: Colors.white, size: 36),
        );
      case ProgressStatus.inProgress:
        // Gentle two-pulse on appear, then static (performance budget).
        circle = Container(
          width: _kNodeSize,
          height: _kNodeSize,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: style.base, width: 4),
            boxShadow: Dt.softShadow(style.base, alpha: .2),
          ),
          child: Icon(Icons.play_arrow_rounded, color: style.base, size: 36),
        )
            .animate(onPlay: (c) => c.repeat(count: 2))
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
      case ProgressStatus.notStarted:
        // Available (not locked): white circle with the domain-colored ring
        // so every lesson reads as openable, not a greyed-out locked step.
        circle = Container(
          width: _kNodeSize,
          height: _kNodeSize,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: style.base.withValues(alpha: .55), width: 3),
            boxShadow: Dt.softShadow(style.base, alpha: .15),
          ),
          child: const Center(
            child: Text('📖', style: TextStyle(fontSize: 28)),
          ),
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
                '⏱️ ${lesson.estimatedMinutes} د',
                style: const TextStyle(
                  fontSize: 11,
                  color: AppTheme.textMuted,
                ),
              ),
              if (lesson.needsProfessionalFollowup)
                const _FlagChip(
                  text: 'متابعة متخصصة',
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

    // The circle hugs the row edge so the connector painter's
    // node-center math holds for both zigzag sides.
    return BouncyTap(
      onTap: onTap,
      child: SizedBox(
        width: 200,
        child: Row(
          children: alignEnd
              ? [info, const SizedBox(width: 10), circle]
              : [circle, const SizedBox(width: 10), info],
        ),
      ),
    );
  }
}

/// Curved connector between two consecutive trail nodes. Solid in the
/// domain color when the previous lesson is completed; dashed grey
/// otherwise. Mirrors correctly under RTL via [textDirection].
class _ConnectorPainter extends CustomPainter {
  final bool fromEnd;
  final bool toEnd;
  final Color color;
  final bool dashed;
  final TextDirection textDirection;

  _ConnectorPainter({
    required this.fromEnd,
    required this.toEnd,
    required this.color,
    required this.dashed,
    required this.textDirection,
  });

  double _x(bool end, double width) {
    // "start"/"end" are directional; resolve to pixels.
    final logicalEnd = textDirection == TextDirection.rtl ? !end : end;
    const inset = 12 + _kNodeInset;
    return logicalEnd ? width - inset : inset;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final xFrom = _x(fromEnd, size.width);
    final xTo = _x(toEnd, size.width);
    final yCenter = size.height / 2;
    // From just below the previous node to just above this node.
    final from = Offset(xFrom, yCenter - _kTrailRowHeight + _kNodeSize / 2 + 6);
    final to = Offset(xTo, yCenter - _kNodeSize / 2 - 6);

    final path = Path()
      ..moveTo(from.dx, from.dy)
      ..cubicTo(
        from.dx,
        from.dy + (to.dy - from.dy) * .7,
        to.dx,
        to.dy - (to.dy - from.dy) * .7,
        to.dx,
        to.dy,
      );

    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..color = color;

    if (!dashed) {
      canvas.drawPath(path, paint);
      return;
    }
    // Dashed: walk the path metrics in 8px-on / 7px-off segments.
    for (final metric in path.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final next = (distance + 8).clamp(0.0, metric.length);
        canvas.drawPath(metric.extractPath(distance, next), paint);
        distance = next + 7;
      }
    }
  }

  @override
  bool shouldRepaint(_ConnectorPainter old) =>
      old.color != color ||
      old.dashed != dashed ||
      old.fromEnd != fromEnd ||
      old.toEnd != toEnd ||
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
                    color: Colors.white.withValues(alpha: .94),
                    shape: BoxShape.circle,
                    boxShadow: Dt.softShadow(Colors.black, alpha: .15),
                  ),
                  child: Icon(Icons.play_arrow_rounded,
                      size: 46, color: style.base),
                ),
                const SizedBox(height: 10),
                const Text(
                  '🎥 شاهد فيديو الوحدة',
                  style: TextStyle(
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
