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

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/celebration_overlay.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../../reflections/widgets/reflection_note_card.dart';
import '../data/review_prompt.dart';
import '../data/models.dart';
import '../data/progress_models.dart';
import '../models/lesson_assets.dart';
import '../providers/lesson_assets_provider.dart';
import '../providers/favorites_provider.dart';
import '../widgets/next_step_sheet.dart';
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
  bool _loggedOpen = false; // analytics fires once, independently of progress

  /// The child this lesson is being read for.
  ///
  /// [LessonScreen.childId] arrives null from every entry point except the
  /// path detail screen — notification deep links (deep_link_handler.dart) and
  /// the favourites list both passed null. A null child hides the completion
  /// button entirely, so those lessons could be read but never finished, and
  /// the screen never explained why. Resolving the active child here fixes all
  /// callers at once and immunises the ones added later.
  ///
  /// `ref.read`, because this is only reached from event handlers; `build`
  /// watches the provider directly so it still rebuilds on a child switch.
  int? get _childId => widget.childId ?? ref.read(activeChildIdProvider);

  Future<void> _markComplete() async {
    final childId = _childId;
    if (childId == null) return;
    // Read before the awaits — reaching for a provider across an async gap on
    // a widget that may have been disposed is how this screen would crash.
    final tryThis = ref
            .read(lessonProvider(widget.lessonId))
            .valueOrNull
            ?.tryThis
            .trim() ??
        '';
    setState(() => _marking = true);
    try {
      await ref.read(markLessonProgressProvider(widget.lessonId).notifier)
          .markProgress(ProgressStatus.completed, childId: childId);
      unawaited(Analytics.lessonCompleted(widget.lessonId));
      if (mounted) {
        // Confetti celebration, then return to path detail so the
        // progress bar refreshes immediately (same auto-pop contract
        // the snackbar+delay version had).
        await showCelebration(
          context,
          emoji: '🎉',
          imageAsset: 'assets/images/generated/mascot_celebrate.webp',
          title: AppLocalizations.of(context).lessonCelebrationTitle,
          message: AppLocalizations.of(context).lessonCelebrationMsg,
        );
        // «كيفية تنفيذ القيمة» — the complaint this answers. The lesson's
        // `try_this` is a single doable action, and it was buried as section 4
        // of 7 mid-scroll. Surface it at the moment the parent has just
        // finished reading and is asking "so what do I do?".
        var committed = false;
        if (mounted && tryThis.isNotEmpty) {
          committed = await showNextStepSheet(context, tryThis: tryThis);
        }
        // Finishing a lesson is the strongest positive moment in the app, and
        // until now it recorded none: ReviewPrompt was reachable only from the
        // child journey screen, so the store had 4 reviews from 3,252 users.
        // ReviewPrompt keeps its own gate — twice before it asks, once ever.
        // Skipped when the parent just committed to a step: interrupting them
        // between "I'll do it" and doing it spends the moment on the wrong
        // thing. The threshold stays at 2 — with 4 reviews from 3,252 users,
        // raising it would cost more than the interruption does.
        if (mounted && !committed) await ReviewPrompt.maybeAsk(context);
        if (mounted) Navigator.of(context).pop();
      }
    } catch (e) {
      // 13eea10 decoupled lesson_opened from the progress write and unhid the
      // completion button, but left this path behind the same network call:
      // a failed PATCH still produced no event at all, so every tap lost to a
      // bad connection looked identical to never tapping. Log the miss.
      unawaited(Analytics.lessonCompleteFailed(widget.lessonId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppLocalizations.of(context).lessonErrorMarking(e.toString())),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _marking = false);
    }
  }

  Future<void> _markInProgress() async {
    final childId = _childId;
    if (childId == null) return;
    try {
      await ref.read(markLessonProgressProvider(widget.lessonId).notifier)
          .markProgress(ProgressStatus.inProgress, childId: childId);
    } catch (_) {
      // Silent — the in_progress marker is best-effort.
    }
  }

  ProgressStatus _statusOf(String lessonId, int? childId) {
    if (childId == null) return ProgressStatus.notStarted;
    final asyncBundle = ref.watch(childProgressProvider(childId));
    return asyncBundle.maybeWhen(
          data: (b) => b.forLesson(lessonId)?.status,
          orElse: () => null,
        ) ??
        ProgressStatus.notStarted;
  }

  @override
  Widget build(BuildContext context) {
    final asyncLesson = ref.watch(lessonProvider(widget.lessonId));
    // Watched, not read, so switching the active child refreshes the status.
    final childId = widget.childId ?? ref.watch(activeChildIdProvider);
    // Deep links carry no age band, so fall back to the selected child's.
    final ageGroup = widget.ageGroup.isEmpty
        ? ref.watch(selectedAgeGroupProvider)
        : widget.ageGroup;
    final status = _statusOf(widget.lessonId, childId);
    final showCta = childId != null && asyncLesson.hasValue;
    // No child at all means onboarding never finished. Say so, instead of
    // rendering a lesson with no way to finish it and no explanation.
    final showAddChild = childId == null && asyncLesson.hasValue;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          asyncLesson.maybeWhen(
            data: (l) => l.title,
            orElse: () => AppLocalizations.of(context).lessonTitle,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      // Sticky CTA — always reachable without scrolling to the bottom.
      bottomNavigationBar: showAddChild
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: BouncyButton(
                  label: AppLocalizations.of(context).addChild,
                  color: Dt.accent,
                  onTap: () => Navigator.of(context).push(AppRoutes.addChild()),
                ),
              ),
            )
          : !showCta
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: BouncyButton(
                  label: status == ProgressStatus.completed
                      ? AppLocalizations.of(context).lessonCompleted
                      : (_marking ? AppLocalizations.of(context).lessonMarking : AppLocalizations.of(context).lessonMarkComplete),
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
          // The lesson is on screen — that is the whole event. It used to be
          // logged alongside the progress write below, so it inherited both of
          // that write's guards: no child, or a progress bundle that failed to
          // load (offline), meant the lesson rendered and counted as never
          // opened. lesson_opened at 31% of child_added is therefore a floor,
          // not a measurement.
          if (!_loggedOpen) {
            _loggedOpen = true;
            unawaited(Analytics.lessonOpened(widget.lessonId));
          }

          // The progress write keeps both guards, and they are load-bearing:
          // waiting for the bundle is what stops a re-opened COMPLETED lesson
          // being downgraded to in_progress, which was silently zeroing path
          // progress on the server.
          final bundleReady = childId == null ||
              ref.watch(childProgressProvider(childId)).hasValue;
          if (childId != null && !_markedInProgress && bundleReady) {
            _markedInProgress = true;
            if (status != ProgressStatus.completed) {
              _markInProgress();
            }
          }
          return _Body(
            lesson: lesson,
            ageGroup: ageGroup,
            childId: childId,
            status: status,
          );
        },
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: SkeletonList(count: 4, itemHeight: 130),
        ),
        error: (err, _) => EmptyState(
          emoji: '📡',
          title: AppLocalizations.of(context).lessonErrorLoading,
          subtitle: '$err',
          actionLabel: AppLocalizations.of(context).retry,
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
          emoji: '📖',
          title: AppLocalizations.of(context).lessonSummary,
          body: lesson.summary,
        ),
        const SizedBox(height: 16),
        _Section(
          emoji: '💡',
          title: AppLocalizations.of(context).lessonTryThis,
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
          _WarningCard(
            text: AppLocalizations.of(context).lessonWarningFollowup,
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
          AppLocalizations.of(context).lessonStatusCompleted,
          AppTheme.success,
          const Color(0xFFD4EDDA),
        ),
      ProgressStatus.inProgress => (
          Icons.play_circle_outline,
          AppLocalizations.of(context).lessonStatusInProgress,
          AppTheme.primary,
          AppTheme.surfaceAlt,
        ),
      ProgressStatus.notStarted => (
          Icons.circle_outlined,
          AppLocalizations.of(context).lessonStatusNotStarted,
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
                      _HeroBadge(text: AppLocalizations.of(context).lessonNumberBadge(lesson.order)),
                      const SizedBox(width: 8),
                      _HeroBadge(text: AppLocalizations.of(context).lessonMinutesBadge(lesson.estimatedMinutes)),
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
                        tooltip: isFav ? AppLocalizations.of(context).lessonFavRemove : AppLocalizations.of(context).lessonFavAdd,
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
    this.accent,
    this.background,
  });
  final String emoji;
  final String title;
  final String body;
  final Color? accent;
  final Color? background;

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
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context)
                      .textTheme
                      .titleSmall
                      ?.copyWith(fontWeight: FontWeight.w800, color: accent),
                ),
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
          Row(
            children: [
              const Text('🧠', style: TextStyle(fontSize: 20)),
              const SizedBox(width: 8),
              Text(
                AppLocalizations.of(context).lessonReflections,
                style: const TextStyle(
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
          Icon(Icons.source_outlined,
              size: 16, color: AppTheme.textSecondary),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              AppLocalizations.of(context).lessonUnitRefs(lesson.unitIds.length),
              style: TextStyle(color: AppTheme.textSecondary),
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
          Icon(Icons.medical_services_outlined,
              color: AppTheme.dangerFg, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
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
              label: AppLocalizations.of(context).lessonListenPodcast,
              onPressed: () {
                Navigator.push(
                  context,
                  AppRoutes.podcast(
                    url,
                    AppLocalizations.of(context).lessonPodcastTitle,
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
                  AppRoutes.video(
                    url,
                    AppLocalizations.of(context).lessonWatchVideo,
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
              label: AppLocalizations.of(context).lessonFlashcards(flashcardsCount),
              onPressed: () {
                Navigator.push(context, AppRoutes.flashcards(deckIds));
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
              label: AppLocalizations.of(context).lessonQuiz(quizzesCount),
              onPressed: () {
                Navigator.push(context, AppRoutes.quiz(quizIds));
              },
            ),
          );
        }

        // ── Visual assets: infographic / report / data-table ──
        if (assets.infographic != null) {
          final raw = assets.infographic!;
          final url =
              raw.startsWith('http') ? raw : '${AppConfig.apiBaseUrl}/$raw';
          buttons.add(_AssetButton(
            icon: Icons.image,
            label: AppLocalizations.of(context).lessonInfographic,
            onPressed: () => Navigator.push(
              context,
              AppRoutes.infographic(url),
            ),
          ));
        }

        if (assets.report != null) {
          final raw = assets.report!;
          final url =
              raw.startsWith('http') ? raw : '${AppConfig.apiBaseUrl}/$raw';
          buttons.add(_AssetButton(
            icon: Icons.description,
            label: AppLocalizations.of(context).lessonReport,
            onPressed: () => Navigator.push(
              context,
              AppRoutes.report(url),
            ),
          ));
        }

        if (assets.dataTable != null) {
          final raw = assets.dataTable!;
          final url =
              raw.startsWith('http') ? raw : '${AppConfig.apiBaseUrl}/$raw';
          buttons.add(_AssetButton(
            icon: Icons.table_chart,
            label: AppLocalizations.of(context).lessonDataTable,
            onPressed: () => Navigator.push(
              context,
              AppRoutes.dataTable(url),
            ),
          ));
        }

        } // end assets != null

        // ── Game button — domain-based, ALWAYS available (even with no assets) ──
        if (domain == 'cyber') {
          buttons.add(
            _AssetButton(
              icon: Icons.videogame_asset,
              label: AppLocalizations.of(context).lessonPlayCyber,
              onPressed: () => Navigator.push(
                context,
                AppRoutes.gameDataDefender(source: GameSources.lesson),
              ),
            ),
          );
        } else if (domain == 'medical') {
          buttons.add(
            _AssetButton(
              icon: Icons.videogame_asset_rounded,
              label: AppLocalizations.of(context).lessonPlayMedical,
              onPressed: () => Navigator.push(
                context,
                AppRoutes.gameHealthyHero(source: GameSources.lesson),
              ),
            ),
          );
        } else if (domain == 'islamic_parenting' || domain == 'aqeedah' || domain == 'islamic') {
          buttons.add(
            _AssetButton(
              icon: Icons.nature_people,
              label: AppLocalizations.of(context).lessonPlayIslamic,
              onPressed: () => Navigator.push(
                context,
                AppRoutes.gameTreeOfDeeds(source: GameSources.lesson),
              ),
            ),
          );
        } else if (domain == 'development') {
          buttons.add(
            _AssetButton(
              icon: Icons.psychology,
              label: AppLocalizations.of(context).lessonPlayDev,
              onPressed: () => Navigator.push(
                context,
                AppRoutes.gameEmotionMaze(source: GameSources.lesson),
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
                Expanded(
                  child: Text(
                    AppLocalizations.of(context).lessonStartInteractive,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              AppLocalizations.of(context).lessonInteractiveHint,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textMuted,
                  ),
            ),
            // Asking for English and getting Arabic audio is expected while
            // English media is still being produced — but silence about it
            // reads as a defect, and did: «بعض الدروس بالانجليزية رغم اني
            // نزلت التطبيق بالعربي». The server has always said which
            // language each medium came back in; nothing displayed it.
            if (assets != null && assets.servedInAnotherLanguage) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: AppTheme.warningBg,
                  borderRadius: BorderRadius.circular(Dt.rButton),
                ),
                child: Text(
                  AppLocalizations.of(context).lessonMediaOtherLanguage,
                  style: TextStyle(
                    fontSize: 12.5,
                    height: 1.45,
                    color: AppTheme.warningFg,
                  ),
                ),
              ),
            ],
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
      error: (_, _) => const SizedBox.shrink(),
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
            PositionedDirectional(
              start: 16,
              bottom: 12,
              child: Text(
                AppLocalizations.of(context).lessonVideoTitle,
                style: const TextStyle(
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
            Icon(Icons.chevron_left, color: AppTheme.textMuted),
          ],
        ),
      ),
    );
  }
}

