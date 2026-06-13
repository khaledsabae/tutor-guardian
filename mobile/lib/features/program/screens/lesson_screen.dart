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
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/celebration_overlay.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../../reflections/widgets/reflection_note_card.dart';
import '../data/models.dart';
import '../data/progress_models.dart';
import '../models/lesson_assets.dart';
import '../providers/lesson_assets_provider.dart';
import '../providers/favorites_provider.dart';
import 'flashcards_screen.dart';
import 'quiz_screen.dart';
import 'podcast_player_screen.dart';
import 'video_player_screen.dart';
import '../../games/data_defender/game_screen.dart';
import '../../games/healthy_hero/game_screen.dart';
import '../../games/tree_of_deeds/game_screen.dart';
import '../../games/emotion_maze/game_screen.dart';
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
  bool _markedInProgress = false; // guard against re-firing on every rebuild

  Future<void> _markComplete() async {
    if (widget.childId == null) return;
    setState(() => _marking = true);
    try {
      await ref.read(markLessonProgressProvider(widget.lessonId).notifier)
          .markProgress(ProgressStatus.completed, childId: widget.childId);
      if (mounted) {
        // Confetti celebration, then return to path detail so the
        // progress bar refreshes immediately (same auto-pop contract
        // the snackbar+delay version had).
        await showCelebration(
          context,
          emoji: '🎉',
          title: 'ما شاء الله!',
          message: 'تم تسجيل إكمال الدرس',
        );
        if (mounted) Navigator.of(context).pop();
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

  ProgressStatus _statusOf(String lessonId) {
    if (widget.childId == null) return ProgressStatus.notStarted;
    final asyncBundle = ref.watch(childProgressProvider(widget.childId!));
    return asyncBundle.maybeWhen(
          data: (b) => b.forLesson(lessonId)?.status,
          orElse: () => null,
        ) ??
        ProgressStatus.notStarted;
  }

  @override
  Widget build(BuildContext context) {
    final asyncLesson = ref.watch(lessonProvider(widget.lessonId));
    final status = _statusOf(widget.lessonId);
    final showCta = widget.childId != null && asyncLesson.hasValue;
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
      // Sticky CTA — always reachable without scrolling to the bottom.
      bottomNavigationBar: !showCta
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: BouncyButton(
                  label: status == ProgressStatus.completed
                      ? 'مكتمل ✓'
                      : (_marking ? 'جارٍ التسجيل…' : 'أتممت هذا الدرس'),
                  color: status == ProgressStatus.completed
                      ? AppTheme.success
                      : Dt.accent,
                  icon: _marking
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : null,
                  onTap: (status == ProgressStatus.completed || _marking)
                      ? null
                      : _markComplete,
                ),
              ),
            ),
      body: asyncLesson.when(
        data: (lesson) {
          // Fire-and-forget "in progress" exactly once when the lesson
          // data first loads. Guard prevents re-firing on subsequent
          // rebuilds. We wait for the progress bundle so a re-opened
          // COMPLETED lesson is never downgraded back to in_progress
          // (that was silently zeroing the path progress on the server).
          final bundleReady = widget.childId == null ||
              ref.watch(childProgressProvider(widget.childId!)).hasValue;
          if (widget.childId != null && !_markedInProgress && bundleReady) {
            _markedInProgress = true;
            if (status != ProgressStatus.completed) {
              _markInProgress();
            }
          }
          return _Body(
            lesson: lesson,
            ageGroup: widget.ageGroup,
            childId: widget.childId,
            status: status,
          );
        },
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: SkeletonList(count: 4, itemHeight: 130),
        ),
        error: (err, _) => EmptyState(
          emoji: '📡',
          title: 'تعذّر تحميل الدرس',
          subtitle: '$err',
          actionLabel: 'إعادة المحاولة',
          onAction: () => ref.invalidate(lessonProvider(widget.lessonId)),
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
    required this.status,
  });
  final CurriculumLesson lesson;
  final String ageGroup;
  final int? childId;
  final ProgressStatus status;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final style = styleFor(lesson.domain);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        _Hero(lesson: lesson, ageGroup: ageGroup, style: style),
        if (childId != null) ...[
          const SizedBox(height: 12),
          _StatusChip(status: status),
        ],
        // Interactive content first — users were hunting for the
        // podcast/flashcards/quiz buried below the reading material.
        _InteractiveAssetsSection(lessonId: lesson.id, domain: lesson.domain),
        const SizedBox(height: 16),
        _Section(
          emoji: '📝',
          title: 'الملخص',
          body: lesson.summary,
        ),
        const SizedBox(height: 16),
        _Section(
          emoji: '💡',
          title: 'جرّب هذا',
          body: lesson.tryThis,
          accent: Dt.accentDeep,
          background: const Color(0xFFFFF4E0),
        ),
        if (lesson.reflectionPrompts.isNotEmpty) ...[
          const SizedBox(height: 16),
          _ReflectionCard(prompts: lesson.reflectionPrompts),
        ],
        const SizedBox(height: 16),
        ReflectionNoteCard(lessonId: lesson.id),
        const SizedBox(height: 16),
        _UnitIdsCard(lesson: lesson),
        if (lesson.needsProfessionalFollowup) ...[
          const SizedBox(height: 16),
          const _WarningCard(
            text: 'هذا الدرس يحتوي على توجيهات تستحق المتابعة مع متخصص. '
                'لا تتردد في استشارة طبيب أو أخصائي تنموي إذا شعرت بالحاجة.',
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
  const _Hero({
    required this.lesson,
    required this.ageGroup,
    required this.style,
  });
  final CurriculumLesson lesson;
  final String ageGroup;
  final DomainStyle style;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isFav = ref.watch(favoritesProvider)['lessons']
            ?.contains(lesson.id) ?? false;
    return Container(
      decoration: BoxDecoration(
        gradient: style.gradient,
        borderRadius: BorderRadius.circular(Dt.rCard),
        boxShadow: Dt.softShadow(style.base),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(Dt.rCard),
        child: Stack(
          children: [
            PositionedDirectional(
              start: -12,
              bottom: -20,
              child: Opacity(
                opacity: .15,
                child: Text(
                  style.emoji,
                  style: const TextStyle(fontSize: 100),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _HeroBadge(text: 'الدرس ${lesson.order}'),
                      const SizedBox(width: 8),
                      _HeroBadge(text: '⏱️ ${lesson.estimatedMinutes} دقائق'),
                      const Spacer(),
                      IconButton(
                        onPressed: () {
                          ref
                              .read(favoritesProvider.notifier)
                              .toggleLesson(lesson.id);
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
                      fontWeight: FontWeight.w800,
                      height: 1.4,
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
}

class _HeroBadge extends StatelessWidget {
  const _HeroBadge({required this.text});
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
          fontWeight: FontWeight.w700,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.emoji,
    required this.title,
    required this.body,
    this.accent = AppTheme.textPrimary,
    this.background = AppTheme.surface,
  });
  final String emoji;
  final String title;
  final String body;
  final Color accent;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(20),
        boxShadow: background == AppTheme.surface ? Dt.cardShadow : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(emoji, style: const TextStyle(fontSize: 20)),
              const SizedBox(width: 8),
              Text(
                title,
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w800, color: accent),
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
    const violet = Color(0xFF6D28D9);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF3EEFE),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Text('🧠', style: TextStyle(fontSize: 20)),
              SizedBox(width: 8),
              Text(
                'أسئلة للتأمل',
                style: TextStyle(
                  color: violet,
                  fontWeight: FontWeight.w800,
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
                  Container(
                    width: 22,
                    height: 22,
                    alignment: Alignment.center,
                    decoration: const BoxDecoration(
                      color: violet,
                      shape: BoxShape.circle,
                    ),
                    child: Text(
                      '${i + 1}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      prompts[i],
                      style: const TextStyle(
                        color: Color(0xFF44337A),
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
  final String domain;
  const _InteractiveAssetsSection({required this.lessonId, required this.domain});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assetsAsync = ref.watch(lessonAssetsProvider(lessonId));

    return assetsAsync.when(
      data: (LessonAssets? assets) {
        final buttons = <Widget>[];

        // Media buttons only when the lesson actually has assets; the game
        // button below is domain-based and shows even without any assets.
        if (assets != null) {
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
          final raw = assets.videoMp4!;
          final url = raw.startsWith('http')
              ? raw
              : '${AppConfig.apiBaseUrl}/$raw';
          buttons.add(
            _VideoCard(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => VideoPlayerScreen(
                      url: url,
                      title: '🎥 الفيديو التعليمي',
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

        } // end assets != null

        // ── Game button — domain-based, ALWAYS available (even with no assets) ──
        if (domain == 'cyber') {
          buttons.add(
            _AssetButton(
              icon: Icons.videogame_asset,
              label: '🎮 العب وتعلم (حارس البيانات)',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const DataDefenderGameScreen()),
              ),
            ),
          );
        } else if (domain == 'medical') {
          buttons.add(
            _AssetButton(
              icon: Icons.monitor_heart,
              label: '🎮 العب وتعلم (رحلة البطل الصحي)',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const HealthyHeroGameScreen()),
              ),
            ),
          );
        } else if (domain == 'islamic_parenting' || domain == 'islamic') {
          buttons.add(
            _AssetButton(
              icon: Icons.nature_people,
              label: '🎮 العب وتعلم (شجرة الأخلاق)',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const TreeOfDeedsGameScreen()),
              ),
            ),
          );
        } else if (domain == 'development') {
          buttons.add(
            _AssetButton(
              icon: Icons.psychology,
              label: '🎮 العب وتعلم (متاهة المشاعر)',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const EmotionMazeGameScreen()),
              ),
            ),
          );
        }

        if (buttons.isEmpty) return const SizedBox.shrink();

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('🎬', style: TextStyle(fontSize: 20)),
                const SizedBox(width: 8),
                Text(
                  'ابدأ بالمحتوى التفاعلي',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'استمع، شاهد، والعب — ثم اقرأ الملخص بالأسفل',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textMuted,
                  ),
            ),
            const SizedBox(height: 10),
            ...buttons.map((btn) => Padding(
                  padding: const EdgeInsets.only(bottom: 8.0),
                  child: btn,
                )),
          ],
        );
      },
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 24.0),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

/// Prominent video launcher — a tall card with a big play button so the
/// lesson video is impossible to miss (unlike the slim asset rows).
class _VideoCard extends StatelessWidget {
  const _VideoCard({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return BouncyTap(
      onTap: onTap,
      child: Container(
        height: 120,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: AlignmentDirectional.topStart,
            end: AlignmentDirectional.bottomEnd,
            colors: [Color(0xFF1E293B), Color(0xFF0F172A)],
          ),
          borderRadius: BorderRadius.circular(Dt.rCard),
          boxShadow: Dt.cardShadow,
        ),
        child: Stack(
          children: [
            Center(
              child: Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppTheme.primary,
                  shape: BoxShape.circle,
                  boxShadow: Dt.softShadow(AppTheme.primary),
                ),
                child: const Icon(Icons.play_arrow,
                    color: Colors.white, size: 38),
              ),
            ),
            const PositionedDirectional(
              start: 16,
              bottom: 12,
              child: Text(
                '🎥 شاهد الفيديو التعليمي',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 15,
                ),
              ),
            ),
          ],
        ),
      ),
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
    // Key format kept stable — emulator drive-through scripts and
    // widget tests look these up by label suffix.
    return BouncyTap(
      key: Key('btn_${label.split(" ").last}'),
      onTap: onPressed,
      child: Container(
        height: 56,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(Dt.rButton),
          boxShadow: Dt.cardShadow,
        ),
        child: Row(
          children: [
            Icon(icon, size: 22, color: Dt.primary),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                ),
              ),
            ),
            const Icon(Icons.chevron_left, color: AppTheme.textMuted),
          ],
        ),
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

