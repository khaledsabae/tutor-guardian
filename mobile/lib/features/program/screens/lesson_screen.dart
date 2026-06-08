/// Lesson screen — reads a single lesson, renders:
///
///   1. Hero (title + estimated minutes + warning chips)
///   2. Summary (long-form description)
///   3. Try-this (the actionable bit)
///   4. Reflection prompts (numbered list)
///   5. Reference list (from the lesson's `unit_ids` — we render
///      a placeholder card; the real KB RAG preview is Phase 5+)
///
/// Phase 4 intentionally does NOT chat-with-RAG. The lesson is
/// read-only. The "Ask the assistant" button in the AppBar opens the
/// main chat in the Home tab.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../data/models.dart';
import '../providers/program_providers.dart';

class LessonScreen extends ConsumerWidget {
  const LessonScreen({
    super.key,
    required this.lessonId,
    required this.ageGroup,
  });

  final String lessonId;
  final String ageGroup;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncLesson = ref.watch(lessonProvider(lessonId));
    return Scaffold(
      appBar: AppBar(
        title: Text(
          asyncLesson.maybeWhen(
            data: (l) => l.title,
            orElse: () => 'الدرس',
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: asyncLesson.when(
        data: (lesson) => _Body(lesson: lesson, ageGroup: ageGroup),
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
                Text('تعذّر تحميل الدرس.\n$err',
                    textAlign: TextAlign.center),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () => ref.invalidate(lessonProvider(lessonId)),
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

class _Body extends StatelessWidget {
  const _Body({required this.lesson, required this.ageGroup});
  final CurriculumLesson lesson;
  final String ageGroup;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        _Hero(lesson: lesson, ageGroup: ageGroup),
        const SizedBox(height: 16),
        _Section(
          icon: Icons.short_text,
          title: 'الملخص',
          body: lesson.summary,
        ),
        const SizedBox(height: 16),
        _Section(
          icon: Icons.lightbulb_outline,
          title: 'جرّب هذا',
          body: lesson.tryThis,
          accent: AppTheme.primary,
        ),
        if (lesson.reflectionPrompts.isNotEmpty) ...[
          const SizedBox(height: 16),
          _ReflectionCard(prompts: lesson.reflectionPrompts),
        ],
        const SizedBox(height: 16),
        _UnitIdsCard(lesson: lesson),
        if (lesson.needsProfessionalFollowup) ...[
          const SizedBox(height: 16),
          _WarningCard(
            text: 'هذا الدرس يحتوي على توجيهات تستحق المتابعة مع متخصص. '
                'لا تتردد في استشارة طبيب أو أخصائي تنموي إذا شعرت بالحاجة.',
          ),
        ],
      ],
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.lesson, required this.ageGroup});
  final CurriculumLesson lesson;
  final String ageGroup;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.primary,
        borderRadius: BorderRadius.circular(14),
      ),
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
                  'الدرس ${lesson.order}',
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
                  '${lesson.estimatedMinutes} دقائق',
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
            lesson.title,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 22,
              fontWeight: FontWeight.w700,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.icon,
    required this.title,
    required this.body,
    this.accent = AppTheme.textPrimary,
  });
  final IconData icon;
  final String title;
  final String body;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: accent, size: 18),
              const SizedBox(width: 6),
              Text(
                title,
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w700, color: accent),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            body,
            style: Theme.of(context)
                .textTheme
                .bodyLarge
                ?.copyWith(height: 1.6),
          ),
        ],
      ),
    );
  }
}

class _ReflectionCard extends StatelessWidget {
  const _ReflectionCard({required this.prompts});
  final List<String> prompts;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.warningBg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.psychology_alt_outlined,
                  color: AppTheme.warningFg, size: 18),
              SizedBox(width: 6),
              Text(
                'أسئلة للتأمل',
                style: TextStyle(
                  color: AppTheme.warningFg,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (var i = 0; i < prompts.length; i++) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${i + 1}.',
                    style: const TextStyle(
                      color: AppTheme.warningFg,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      prompts[i],
                      style: const TextStyle(
                        color: AppTheme.warningFg,
                        height: 1.55,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _UnitIdsCard extends StatelessWidget {
  const _UnitIdsCard({required this.lesson});
  final CurriculumLesson lesson;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          const Icon(Icons.source_outlined,
              size: 16, color: AppTheme.textSecondary),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              'مرتبط بـ ${lesson.unitIds.length} وحدات من قاعدة المعرفة',
              style: const TextStyle(color: AppTheme.textSecondary),
            ),
          ),
        ],
      ),
    );
  }
}

class _WarningCard extends StatelessWidget {
  const _WarningCard({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.dangerBg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.medical_services_outlined,
              color: AppTheme.dangerFg, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: AppTheme.dangerFg,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
