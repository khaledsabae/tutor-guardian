/// Lesson screen — reads a single lesson, renders:
///
///   1. Hero (title + estimated minutes + warning chips)
///   2. Status chip (Phase 5 — driven by [activeChildIdProvider] +
///      [childProgressProvider])
///   3. Summary (long-form description)
///   4. Try-this (the actionable bit)
///   5. Reflection prompts (numbered list)
///   6. Reference list (from the lesson's `unit_ids` — we render
///      a placeholder card; the real KB RAG preview is Phase 5+)
///   7. "ملاحظاتي" card (Phase 8-C — local-only reflection notes)
///   8. "Mark complete" button (Phase 5 — PATCHes
///      `/api/program/lessons/{id}/progress` and invalidates the
///      active child's progress bundle so [PathDetailScreen] refreshes)
///
/// Phase 4 intentionally does NOT chat-with-RAG. The lesson is
/// read-only. The "Ask the assistant" button in the AppBar opens the
/// main chat in the Home tab.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../reflections/widgets/reflection_note_card.dart';
import '../data/models.dart';
import '../data/progress_models.dart';
import '../models/lesson_assets.dart';
import '../providers/lesson_assets_provider.dart';
import '../providers/favorites_provider.dart';
import 'flashcards_screen.dart';
import 'quiz_screen.dart';
import 'podcast_player_screen.dart';
import '../../../config/app_config.dart';
import '../providers/program_providers.dart';
import '../providers/progress_providers.dart';

class LessonScreen extends ConsumerStatefulWidget {
  const LessonScreen({
    super.key,
    required this.lessonId,
    required this.ageGroup,
    this.childId,
  });

  final String lessonId;
  final String ageGroup;
  final int? childId;

  @override
  ConsumerState<LessonScreen> createState() => _LessonScreenState();
}

class _LessonScreenState extends ConsumerState<LessonScreen> {
  bool _marking = false;

  Future<void> _markComplete() async {
    if (widget.childId == null) return;
    setState(() => _marking = true);
    try {
      await ref.read(markLessonProgressProvider(widget.lessonId).notifier)
          .markProgress(ProgressStatus.completed, childId: widget.childId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('تم تسجيل إكمال الدرس. ما شاء الله!'),
            duration: Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر تسجيل الإكمال: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _marking = false);
    }
  }

  Future<void> _markInProgress() async {
    if (widget.childId == null) return;
    try {
      await ref.read(markLessonProgressProvider(widget.lessonId).notifier)
          .markProgress(ProgressStatus.inProgress, childId: widget.childId);
    } catch (_) {
      // Silent — the in_progress marker is best-effort.
    }
  }

  @override
  Widget build(BuildContext context) {
    final asyncLesson = ref.watch(lessonProvider(widget.lessonId));
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
        data: (lesson) {
          // Fire-and-forget "in progress" the first time the user
          // opens this lesson (best-effort — silent on failure).
          if (widget.childId != null) _markInProgress();
          return _Body(
            lesson: lesson,
            ageGroup: widget.ageGroup,
            childId: widget.childId,
            marking: _marking,
            onMarkComplete: widget.childId == null ? null : _markComplete,
          );
        },
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
                  onPressed: () =>
                      ref.invalidate(lessonProvider(widget.lessonId)),
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
    required this.lesson,
    required this.ageGroup,
    required this.childId,
    required this.marking,
    required this.onMarkComplete,
  });
  final CurriculumLesson lesson;
  final String ageGroup;
  final int? childId;
  final bool marking;
  final VoidCallback? onMarkComplete;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Re-derive the status from the active child.
    final asyncBundle =
        childId == null ? null : ref.watch(childProgressProvider(childId!));
    final status = asyncBundle?.maybeWhen(
          data: (b) => b.forLesson(lesson.id)?.status ??
              ProgressStatus.notStarted,
          orElse: () => ProgressStatus.notStarted,
        ) ??
        ProgressStatus.notStarted;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        _Hero(lesson: lesson, ageGroup: ageGroup),
        if (childId != null) ...[
          const SizedBox(height: 12),
          _StatusChip(status: status),
        ],
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
        _InteractiveAssetsSection(lessonId: lesson.id),
        const SizedBox(height: 16),
        ReflectionNoteCard(lessonId: lesson.id),
        if (lesson.needsProfessionalFollowup) ...[
          const SizedBox(height: 16),
          const _WarningCard(
            text: 'هذا الدرس يحتوي على توجيهات تستحق المتابعة مع متخصص. '
                'لا تتردد في استشارة طبيب أو أخصائي تنموي إذا شعرت بالحاجة.',
          ),
        ],
        if (onMarkComplete != null) ...[
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: (status == ProgressStatus.completed || marking)
                ? null
                : onMarkComplete,
            icon: status == ProgressStatus.completed
                ? const Icon(Icons.check)
                : (marking
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.check_circle_outline)),
            label: Text(
              status == ProgressStatus.completed
                  ? 'مكتمل'
                  : 'أتممت هذا الدرس',
            ),
            style: ElevatedButton.styleFrom(
              minimumSize: const Size.fromHeight(50),
              backgroundColor: status == ProgressStatus.completed
                  ? AppTheme.success
                  : null,
            ),
          ),
        ],
      ],
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});
  final ProgressStatus status;

  @override
  Widget build(BuildContext context) {
    final (icon, label, color, bg) = switch (status) {
      ProgressStatus.completed => (
          Icons.check_circle,
          'مكتمل',
          AppTheme.success,
          const Color(0xFFD4EDDA),
        ),
      ProgressStatus.inProgress => (
          Icons.play_circle_outline,
          'قيد التنفيذ',
          AppTheme.primary,
          AppTheme.surfaceAlt,
        ),
      ProgressStatus.notStarted => (
          Icons.circle_outlined,
          'لم يبدأ بعد',
          AppTheme.textSecondary,
          AppTheme.surfaceAlt,
        ),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _Hero extends ConsumerWidget {
  const _Hero({required this.lesson, required this.ageGroup});
  final CurriculumLesson lesson;
  final String ageGroup;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isFav = ref.watch(favoritesProvider)['lessons']
            ?.contains(lesson.id) ?? false;
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
              const Spacer(),
              IconButton(
                onPressed: () {
                  ref.read(favoritesProvider.notifier).toggleLesson(lesson.id);
                },
                icon: Icon(
                  isFav ? Icons.favorite : Icons.favorite_border,
                  color: isFav ? Colors.redAccent : Colors.white,
                  size: 22,
                ),
                tooltip: isFav ? 'إزالة من المفضلة' : 'إضافة للمفضلة',
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
          const Row(
            children: [
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

class _InteractiveAssetsSection extends ConsumerWidget {
  final String lessonId;
  const _InteractiveAssetsSection({required this.lessonId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assetsAsync = ref.watch(lessonAssetsProvider(lessonId));

    return assetsAsync.when(
      data: (LessonAssets? assets) {
        if (assets == null) return const SizedBox.shrink();

        final buttons = <Widget>[];

        if (assets.podcastMp3 != null) {
          // The backend returns either a full URL or a relative path
          // (e.g. "docs/lesson_01_podcast.mp3" — pre-R2 era). We accept
          // both: full URLs pass through, relative paths are joined
          // against [AppConfig.apiBaseUrl]. Until the R2 migration
          // lands, the relative path will 404 in production and the
          // player shows a friendly "not yet available" message.
          final raw = assets.podcastMp3!;
          final url = raw.startsWith('http://') || raw.startsWith('https://')
              ? raw
              : '${AppConfig.apiBaseUrl}/$raw';
          buttons.add(
            _AssetButton(
              icon: Icons.headset,
              label: '🎧 استمع للبودكاست',
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => PodcastPlayerScreen(
                      url: url,
                      title: '🎧 البودكاست',
                    ),
                  ),
                );
              },
            ),
          );
        }

        if (assets.videoMp4 != null) {
          buttons.add(
            _AssetButton(
              icon: Icons.play_circle_outline,
              label: '🎥 شاهد الفيديو',
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => const AssetPlaceholderScreen(
                      title: 'الفيديو',
                    ),
                  ),
                );
              },
            ),
          );
        }

        final flashcardsCount = assets.flashcards.fold<int>(
          0,
          (sum, item) {
            final map = item as Map<String, dynamic>?;
            return sum + ((map?['item_count'] as num?)?.toInt() ?? 0);
          },
        );
        if (flashcardsCount > 0) {
          final deckIds = assets.flashcards
              .map((item) => (item as Map<String, dynamic>?)?['id'] as String?)
              .whereType<String>()
              .toList();
          buttons.add(
            _AssetButton(
              icon: Icons.style,
              label: '📇 فلاش كاردز ($flashcardsCount بطاقة)',
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => FlashcardsScreen(deckIds: deckIds),
                  ),
                );
              },
            ),
          );
        }

        final quizzesCount = assets.quizzes.fold<int>(
          0,
          (sum, item) {
            final map = item as Map<String, dynamic>?;
            return sum + ((map?['item_count'] as num?)?.toInt() ?? 0);
          },
        );
        if (quizzesCount > 0) {
          final quizIds = assets.quizzes
              .map((item) => (item as Map<String, dynamic>?)?['id'] as String?)
              .whereType<String>()
              .toList();
          buttons.add(
            _AssetButton(
              icon: Icons.quiz,
              label: '❓ اختبر نفسك ($quizzesCount سؤال)',
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => QuizScreen(quizIds: quizIds),
                  ),
                );
              },
            ),
          );
        }

        if (buttons.isEmpty) return const SizedBox.shrink();

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 16),
            Text(
              'محتوى تفاعلي',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            ...buttons.map((btn) => Padding(
                  padding: const EdgeInsets.only(bottom: 8.0),
                  child: btn,
                )),
          ],
        );
      },
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 16.0),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

class _AssetButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onPressed;

  const _AssetButton({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      key: Key('btn_${label.split(" ").last}'),
      onPressed: onPressed,
      icon: Icon(icon, size: 20),
      label: Text(label),
      style: ElevatedButton.styleFrom(
        minimumSize: const Size.fromHeight(48),
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 16),
      ),
    );
  }
}

class AssetPlaceholderScreen extends StatelessWidget {
  final String title;
  const AssetPlaceholderScreen({super.key, required this.title});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
      ),
      body: Center(
        child: Text(
          'شاشة مؤقتة لـ $title',
          style: Theme.of(context).textTheme.titleLarge,
        ),
      ),
    );
  }
}

