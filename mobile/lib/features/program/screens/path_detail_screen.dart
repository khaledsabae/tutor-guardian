/// Path detail screen — shows the full path description + ordered
/// list of lessons, then a "start" or "resume" button.
///
/// Reads [pathDetailProvider] (with `?include=lessons`). Each lesson
/// is rendered as a card that navigates to [LessonScreen]. Phase 5
/// added a [LinearProgressIndicator] that reflects the active child's
/// completion ratio on this path (consumed via
/// [pathProgressMapProvider]).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../data/models.dart';
import '../data/progress_models.dart';
import '../providers/program_providers.dart';
import '../providers/progress_providers.dart';
import 'lesson_screen.dart';

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
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline,
                    size: 56, color: AppTheme.dangerFg),
                const SizedBox(height: 12),
                Text('تعذّر تحميل المسار.\n$err',
                    textAlign: TextAlign.center),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () => ref.invalidate(pathDetailProvider(args)),
                  icon: const Icon(Icons.refresh),
                  label: const Text('إعادة المحاولة'),
                ),
              ],
            ),
          ),
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
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        _Header(path: path),
        if (asyncProgress != null) ...[
          const SizedBox(height: 12),
          _ProgressStrip(asyncProgress: asyncProgress),
        ],
        const SizedBox(height: 20),
        if (path.primaryReference != null) ...[
          _ReferenceCard(ref: path.primaryReference!),
          const SizedBox(height: 20),
        ],
        Text(
          'الدروس (${detail.lessons.length})',
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 8),
        if (detail.lessons.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: Text(
                'لا توجد دروس في هذا المسار بعد.',
                style: Theme.of(context)
                    .textTheme
                    .bodyLarge
                    ?.copyWith(color: AppTheme.textSecondary),
              ),
            ),
          )
        else
          for (final lesson in detail.lessons) ...[
            _LessonTile(
              lesson: lesson,
              status: asyncProgress?.maybeWhen(
                data: (m) => m.statusFor(lesson.id),
                orElse: () => ProgressStatus.notStarted,
              ),
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => LessonScreen(
                      lessonId: lesson.id,
                      ageGroup: ageGroup,
                      childId: childId,
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 8),
          ],
        const SizedBox(height: 16),
        ElevatedButton.icon(
          onPressed: detail.lessons.isEmpty
              ? null
              : () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => LessonScreen(
                        lessonId: detail.lessons.first.id,
                        ageGroup: ageGroup,
                        childId: childId,
                      ),
                    ),
                  );
                },
          icon: const Icon(Icons.play_arrow),
          label: const Text('ابدأ المسار'),
          style: ElevatedButton.styleFrom(
            minimumSize: const Size.fromHeight(50),
          ),
        ),
      ],
    );
  }
}

class _ProgressStrip extends StatelessWidget {
  const _ProgressStrip({required this.asyncProgress});
  final AsyncValue<PathProgressMap> asyncProgress;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: asyncProgress.when(
        data: (m) {
          final percent = (m.fraction * 100).round();
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.bar_chart,
                      size: 16, color: AppTheme.textSecondary),
                  const SizedBox(width: 6),
                  Text(
                    'تقدّم المسار',
                    style: Theme.of(context)
                        .textTheme
                        .titleSmall
                        ?.copyWith(color: AppTheme.textSecondary),
                  ),
                  const Spacer(),
                  Text(
                    '${m.completedCount} / ${m.totalLessonsInPath} ($percent%)',
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: m.fraction,
                  minHeight: 8,
                  backgroundColor: const Color(0xFFE5E7EB),
                  valueColor: const AlwaysStoppedAnimation<Color>(
                    AppTheme.primary,
                  ),
                ),
              ),
              if (m.inProgressCount > 0) ...[
                const SizedBox(height: 6),
                Text(
                  '${m.inProgressCount} درس قيد التنفيذ',
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ],
          );
        },
        loading: () => const SizedBox(
          height: 8,
          child: LinearProgressIndicator(),
        ),
        error: (_, __) => const Text(
          'تعذّر تحميل التقدّم.',
          style: TextStyle(color: AppTheme.dangerFg, fontSize: 12),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.path});
  final CurriculumPath path;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: AppTheme.primary,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    path.ageLabel,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    path.domainLabel,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              path.title,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              path.description,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.9),
                height: 1.55,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Icon(Icons.timelapse,
                    size: 16, color: Colors.white70),
                const SizedBox(width: 4),
                Text(
                  '${path.estimatedDays} يوم',
                  style: const TextStyle(color: Colors.white70),
                ),
                const SizedBox(width: 16),
                const Icon(Icons.menu_book_outlined,
                    size: 16, color: Colors.white70),
                const SizedBox(width: 4),
                Text(
                  '${path.lessonIds.length} دروس',
                  style: const TextStyle(color: Colors.white70),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ReferenceCard extends StatelessWidget {
  const _ReferenceCard({required this.ref});
  final PathReference ref;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: AppTheme.warningBg,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.menu_book, color: AppTheme.warningFg, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _refTypeLabel(ref.type),
                    style: const TextStyle(
                      color: AppTheme.warningFg,
                      fontWeight: FontWeight.w700,
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

class _LessonTile extends StatelessWidget {
  const _LessonTile({
    required this.lesson,
    required this.status,
    required this.onTap,
  });
  final CurriculumLesson lesson;
  final ProgressStatus status;
  final VoidCallback onTap;

  IconData get _statusIcon {
    switch (status) {
      case ProgressStatus.completed:
        return Icons.check_circle;
      case ProgressStatus.inProgress:
        return Icons.play_circle_outline;
      case ProgressStatus.notStarted:
        return Icons.circle_outlined;
    }
  }

  Color get _statusColor {
    switch (status) {
      case ProgressStatus.completed:
        return AppTheme.success;
      case ProgressStatus.inProgress:
        return AppTheme.primary;
      case ProgressStatus.notStarted:
        return AppTheme.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: _statusColor.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(_statusIcon, color: _statusColor, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      lesson.title,
                      style: Theme.of(context)
                          .textTheme
                          .titleSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Text(
                          '${lesson.estimatedMinutes} د',
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(color: AppTheme.textSecondary),
                        ),
                        if (status != ProgressStatus.notStarted) ...[
                          const SizedBox(width: 8),
                          Text(
                            progressStatusLabel(status),
                            style: TextStyle(
                              color: _statusColor,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                        const SizedBox(width: 8),
                        if (lesson.needsProfessionalFollowup)
                          const _FlagChip(
                            text: 'متابعة متخصصة',
                            color: AppTheme.dangerFg,
                            bg: AppTheme.dangerBg,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_left, color: AppTheme.textMuted),
            ],
          ),
        ),
      ),
    );
  }
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
        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600),
      ),
    );
  }
}
