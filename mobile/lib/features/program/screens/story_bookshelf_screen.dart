/// The story shelf — «ورق مقصوص» (2026-10, docs/STORIES_AUDIT.md).
///
/// Every cover is drawn in the app from the story's own scene pieces, so the
/// shelf opens with pictures and no network: the old covers were 1024² PNGs
/// and 2–3.7 MB looping videos fetched per book, and five of the nineteen
/// stories had no picture on the server at all (404) — those showed an emoji.
///
/// Cards size to their content (title, age) rather than to a fixed box, so
/// the system's 200% text grows the card instead of spilling out of it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../core/haptics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/error_retry_view.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';
import '../../screen_off/narration_store.dart';
import '../../stories/living/story_cover.dart';
import '../../stories/scene/story_scene.dart' show StorySceneView;
import '../../stories/scene/story_scene_catalog.dart';
import '../data/story_models.dart';
import 'package:almorabbi/widgets/ui/loading_view.dart';

/// The shelf's age filters.
enum StoryShelfFilter { all, young, older }

/// Whether [story] belongs under [filter]. Ranges overlap on purpose: a
/// 4–7 story is right for both a four-year-old and a seven-year-old.
bool storyMatchesFilter(Story story, StoryShelfFilter filter) {
  if (filter == StoryShelfFilter.all) return true;
  final range = ageRangeOf(story.ageGroup);
  if (range == null) return true; // unlabelled: never hidden
  return switch (filter) {
    StoryShelfFilter.young => range.min <= 4,
    StoryShelfFilter.older => range.max >= 7,
    StoryShelfFilter.all => true,
  };
}

class StoryBookshelfScreen extends ConsumerWidget {
  const StoryBookshelfScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final storiesAsync = ref.watch(storiesProvider);
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: context.colors.background,
      appBar: AppBar(title: Text(l10n.bedtimeStories)),
      body: storiesAsync.when(
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: LoadingView(count: 3, itemHeight: 220),
        ),
        error: (e, _) => EmptyState(
          emoji: '⚠️',
          title: l10n.storyLoadError,
          subtitle: userFacingError(context, e).body,
        ),
        data: (stories) => stories.isEmpty
            ? EmptyState(
                emoji: '📚',
                title: l10n.storyEmpty,
                subtitle: l10n.storyEmptyDesc,
              )
            : StoryShelf(stories: stories),
      ),
    );
  }
}

class StoryShelf extends StatefulWidget {
  const StoryShelf({super.key, required this.stories});
  final List<Story> stories;

  @override
  State<StoryShelf> createState() => _StoryShelfState();
}

class _StoryShelfState extends State<StoryShelf> {
  StoryShelfFilter _filter = StoryShelfFilter.all;

  /// Narration keys with a parent's recording still on disk — read once on
  /// open, not per card (`find` touches the filesystem).
  Set<String> _narrated = const {};

  @override
  void initState() {
    super.initState();
    _loadNarrations();
  }

  Future<void> _loadNarrations() async {
    try {
      final keys = await NarrationStore.instance.available();
      if (mounted) setState(() => _narrated = keys);
    } catch (_) {
      // No store: no marks.
    }
  }

  Future<void> _listenInParentVoice(Story story) async {
    final found = await NarrationStore.instance.find(narrationKeyFor(story.id));
    if (found == null || !mounted) return;
    await Navigator.of(
      context,
    ).push(AppRoutes.screenOffPlayer(title: story.title, source: found.path));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final visible = [
      for (final s in widget.stories)
        if (storyMatchesFilter(s, _filter)) s,
    ];
    return LayoutBuilder(
      builder: (context, box) {
        final textScale = MediaQuery.textScalerOf(context).scale(1);
        final columns = box.maxWidth >= 600 ? 3 : (textScale > 1.5 ? 1 : 2);
        const gap = 14.0;
        final cardWidth = (box.maxWidth - 32 - gap * (columns - 1)) / columns;
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
          children: [
            Row(
              children: [
                const NoorPresence(size: 48, face: NoorFaceState.night),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    l10n.bedtimeStoriesDesc,
                    style: TextStyle(
                      color: colors.textSecondary,
                      fontSize: 14.5,
                      height: 1.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final f in StoryShelfFilter.values)
                  ChoiceChip(
                    label: Text(switch (f) {
                      StoryShelfFilter.all => l10n.storyFilterAll(
                        widget.stories.length,
                      ),
                      StoryShelfFilter.young => l10n.storyFilterYoung,
                      StoryShelfFilter.older => l10n.storyFilterOlder,
                    }),
                    selected: _filter == f,
                    onSelected: (_) {
                      Haptics.selection();
                      setState(() => _filter = f);
                    },
                  ),
              ],
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: gap,
              runSpacing: gap + 4,
              children: [
                for (final story in visible)
                  SizedBox(
                    width: cardWidth,
                    child: StoryBookCard(
                      story: story,
                      hasParentRecording: _narrated.contains(
                        narrationKeyFor(story.id),
                      ),
                      onOpen: () => Navigator.of(
                        context,
                      ).push(AppRoutes.storyReader(story)),
                      onListen: () => _listenInParentVoice(story),
                    ),
                  ),
              ],
            ),
          ],
        );
      },
    );
  }
}

/// One book on the shelf: its drawn cover, its title, its ages.
class StoryBookCard extends StatelessWidget {
  const StoryBookCard({
    super.key,
    required this.story,
    required this.onOpen,
    this.hasParentRecording = false,
    this.onListen,
  });

  final Story story;
  final VoidCallback onOpen;
  final bool hasParentRecording;
  final VoidCallback? onListen;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final l10n = AppLocalizations.of(context);
    return Semantics(
      button: true,
      label: story.title,
      hint: l10n.storyTapToOpen,
      excludeSemantics: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(color: colors.paperShadow, offset: const Offset(4, 5)),
          ],
        ),
        child: Material(
          color: colors.surface,
          borderRadius: BorderRadius.circular(20),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onOpen,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Stack(
                  children: [
                    Hero(
                      tag: 'story-cover-${story.id}',
                      child: StoryCoverPicture(
                        storyId: story.id,
                        fallback: StorySceneView(
                          scene: coverSceneFor(story.id),
                          animate: false,
                        ),
                      ),
                    ),
                    if (hasParentRecording)
                      PositionedDirectional(
                        top: 6,
                        end: 6,
                        child: Material(
                          color: colors.paperEmerald,
                          shape: const CircleBorder(),
                          child: IconButton(
                            tooltip: l10n.storyListenInParentVoice,
                            visualDensity: VisualDensity.compact,
                            icon: Icon(
                              Icons.record_voice_over_rounded,
                              color: colors.paperIvory,
                              size: 18,
                            ),
                            onPressed: onListen,
                          ),
                        ),
                      ),
                  ],
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ContentDirectionality(
                        languageCode: story.language,
                        text: story.title,
                        child: Text(
                          story.title,
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: colors.ink,
                            fontSize: 15.5,
                            height: 1.35,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      if (story.ageGroup != null) ...[
                        const SizedBox(height: 6),
                        ContentDirectionality(
                          languageCode: story.language,
                          text: story.ageGroup!,
                          child: Text(
                            story.ageGroup!,
                            style: TextStyle(
                              color: colors.textSecondary,
                              fontSize: 12.5,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
