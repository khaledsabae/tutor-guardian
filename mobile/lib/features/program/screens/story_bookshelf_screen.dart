
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';

import '../../../config/app_config.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../data/story_models.dart';
import '../../../widgets/ui/night_sky.dart';

/// A magical bedtime bookshelf: 3D books, twinkling stars, and looping
/// ambient cover videos when available. Replaces the old vertical list card.
class StoryBookshelfScreen extends ConsumerWidget {
  const StoryBookshelfScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final storiesAsync = ref.watch(storiesProvider);

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF0B3B3B), Color(0xFF134E4E), Color(0xFF1F5E5E)],
          ),
        ),
        child: SafeArea(
          child: storiesAsync.when(
            loading: () => const SingleChildScrollView(
              physics: NeverScrollableScrollPhysics(),
              child: SkeletonList(count: 3, itemHeight: 220),
            ),
            error: (e, __) => EmptyState(
              emoji: '⚠️',
              title: AppLocalizations.of(context).storyLoadError,
              subtitle: e.toString(),
            ),
            data: (stories) {
              if (stories.isEmpty) {
                return EmptyState(
                  emoji: '📚',
                  title: AppLocalizations.of(context).storyEmpty,
                  subtitle: AppLocalizations.of(context).storyEmptyDesc,
                );
              }
              return _BookshelfBody(stories: stories);
            },
          ),
        ),
      ),
    );
  }
}

/// Which story indices should hold a live video controller.
///
/// Every story used to get one the moment the shelf opened: with ten stories
/// that is ten concurrent network decoders, each holding a MediaCodec instance
/// and a surface texture, all downloading and looping at once — more than
/// low-end Android devices allow, for books the reader cannot see. Only the
/// centred book and its immediate neighbours are worth keeping warm.
///
/// Pure so the policy can be tested without mounting the shelf, whose shimmer
/// animation never settles.
Set<int> videoWindowFor({
  required int centered,
  required List<Story> stories,
  int radius = 1,
}) {
  return {
    for (var i = centered - radius; i <= centered + radius; i++)
      if (i >= 0 && i < stories.length && stories[i].hasVideo) i,
  };
}

class _BookshelfBody extends StatefulWidget {
  const _BookshelfBody({required this.stories});
  final List<Story> stories;

  @override
  State<_BookshelfBody> createState() => _BookshelfBodyState();
}

class _BookshelfBodyState extends State<_BookshelfBody>
    with SingleTickerProviderStateMixin {
  late final PageController _controller;
  double _currentPage = 0;
  int _centeredPage = 0;
  final Map<int, VideoPlayerController> _videoControllers = {};

  @override
  void initState() {
    super.initState();
    _controller = PageController(viewportFraction: 0.55);
    _controller.addListener(_onScroll);
    _syncVideoWindow(0);
  }

  /// Create controllers inside the window around [centered], drop the rest.
  void _syncVideoWindow(int centered) {
    final wanted = videoWindowFor(centered: centered, stories: widget.stories);

    for (final index in _videoControllers.keys.toList()) {
      if (!wanted.contains(index)) {
        _videoControllers.remove(index)!.dispose();
      }
    }

    for (final index in wanted) {
      if (_videoControllers.containsKey(index)) continue;
      final file = widget.stories[index].videoFile!;
      final controller = file.startsWith('docs/')
          ? VideoPlayerController.networkUrl(
              Uri.parse('${AppConfig.apiBaseUrl}/$file'),
            )
          : VideoPlayerController.asset(file);
      _videoControllers[index] = controller;
      controller
        ..setLooping(true)
        ..setVolume(0)
        ..initialize().then((_) {
          // The window may have moved on, or the screen closed, while this
          // was loading.
          if (!mounted || _videoControllers[index] != controller) return;
          setState(() {});
          if (index == _centeredPage) controller.play();
        }).catchError((_) {
          // A cover video that will not load is cosmetic — the shelf falls
          // back to the cover image. Without this, the failure escapes as an
          // unhandled async error instead of being ignored.
        });
    }
  }

  void _onScroll() {
    final page = _controller.page ?? 0;
    final centered = (page + 0.5).floor();
    final windowMoved = centered != _centeredPage;

    setState(() {
      _currentPage = page;
      _centeredPage = centered;
    });

    if (windowMoved) _syncVideoWindow(centered);

    // Only the centred book plays.
    for (final entry in _videoControllers.entries) {
      final vc = entry.value;
      if (!vc.value.isInitialized) continue;
      if (entry.key == centered && !vc.value.isPlaying) {
        vc.play();
      } else if (entry.key != centered && vc.value.isPlaying) {
        vc.pause();
      }
    }
  }

  @override
  void dispose() {
    _controller.removeListener(_onScroll);
    _controller.dispose();
    for (final vc in _videoControllers.values) {
      vc.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 24),
        Text(
          AppLocalizations.of(context).bedtimeStories,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w800,
                fontSize: 26,
              ),
        ).animate().fadeIn(duration: Dt.slow).slideY(begin: -0.1),
        const SizedBox(height: 8),
        Text(
          AppLocalizations.of(context).bedtimeStoriesDesc,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Color(0xFFE0D5C1),
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ).animate(delay: 150.ms).fadeIn(duration: Dt.base),
        const SizedBox(height: 24),
        Expanded(
          child: Stack(
            children: [
              const Positioned.fill(child: TwinklingStars(count: 55)),
              PageView.builder(
                controller: _controller,
                itemCount: widget.stories.length,
                physics: const BouncingScrollPhysics(),
                itemBuilder: (context, index) {
                  final story = widget.stories[index];
                  final distance = (_currentPage - index).abs();
                  final scale = 1 - (distance * 0.18).clamp(0.0, 0.45);
                  final angle = (index - _currentPage) * 0.18;
                  final videoController = _videoControllers[index];
                  return Center(
                    child: Transform.scale(
                      scale: scale,
                      child: Transform(
                        transform: Matrix4.identity()
                          ..setEntry(3, 2, 0.001)
                          ..rotateY(angle),
                        alignment: Alignment.center,
                        child: _BookCover(
                          story: story,
                          videoController: videoController,
                          onTap: () => _openStory(story),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        _PageDots(count: widget.stories.length, page: _currentPage),
        const SizedBox(height: 32),
      ],
    );
  }

  void _openStory(Story story) {
    Navigator.of(context).push(AppRoutes.bedtimeRoutine(story));
  }
}

class _BookCover extends StatelessWidget {
  const _BookCover({
    required this.story,
    this.videoController,
    required this.onTap,
  });

  final Story story;
  final VideoPlayerController? videoController;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final themeColor = Color(
      int.tryParse(story.themeColor) ?? 0xFF0D9488,
    );

    return Hero(
      tag: 'story-cover-${story.id}',
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 350),
          width: 220,
          height: 320,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                themeColor,
                Color.lerp(themeColor, Colors.black, 0.25)!,
              ],
            ),
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: themeColor.withValues(alpha: 0.45),
                blurRadius: 28,
                offset: const Offset(0, 18),
              ),
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.35),
                blurRadius: 12,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(20),
            child: Stack(
              children: [
                // Spine highlight.
                Positioned(
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: 18,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          Colors.white.withValues(alpha: 0.22),
                          Colors.white.withValues(alpha: 0.0),
                        ],
                      ),
                      borderRadius: const BorderRadius.horizontal(
                        left: Radius.circular(20),
                      ),
                    ),
                  ),
                ),
                // Cover video or illustration.
                if (videoController != null &&
                    videoController!.value.isInitialized)
                  Positioned.fill(
                    child: FittedBox(
                      fit: BoxFit.cover,
                      child: SizedBox(
                        width: videoController!.value.size.width,
                        height: videoController!.value.size.height,
                        child: VideoPlayer(videoController!),
                      ),
                    ),
                  )
                else
                  Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        (story.coverImage.startsWith('docs/')
                            ? Image.network(
                                '${AppConfig.apiBaseUrl}/${story.coverImage}',
                                width: 130,
                                height: 130,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => Text(
                                  story.id == 'hope_sprout' ? '🌱' : 
                                  story.id == 'kitten_kindness' ? '🐱' :
                                  story.id == 'layla_star' ? '⭐' :
                                  story.id == 'saleh_bird' ? '🐦' :
                                  story.id == 'noor_clean' ? '🌳' :
                                  story.id == 'maryam_toys' ? '🎁' :
                                  story.id == 'omar_prayer' ? '🕌' :
                                  story.id == 'khadija_neighbor' ? '🍲' :
                                  story.id == 'abdullah_bismillah' ? '🍇' :
                                  story.id == 'hamza_truth' ? '💬' : '📖',
                                  style: const TextStyle(fontSize: 72),
                                ),
                              )
                            : Image.asset(
                                story.coverImage,
                                width: 130,
                                height: 130,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => Text(
                                  story.id == 'hope_sprout' ? '🌱' : 
                                  story.id == 'kitten_kindness' ? '🐱' :
                                  story.id == 'layla_star' ? '⭐' :
                                  story.id == 'saleh_bird' ? '🐦' :
                                  story.id == 'noor_clean' ? '🌳' :
                                  story.id == 'maryam_toys' ? '🎁' :
                                  story.id == 'omar_prayer' ? '🕌' :
                                  story.id == 'khadija_neighbor' ? '🍲' :
                                  story.id == 'abdullah_bismillah' ? '🍇' :
                                  story.id == 'hamza_truth' ? '💬' : '📖',
                                  style: const TextStyle(fontSize: 72),
                                ),
                              )).animate(onPlay: (c) => c.repeat()).shimmer(
                              duration: const Duration(seconds: 3),
                              color: Colors.white.withValues(alpha: 0.25),
                            ),
                        const SizedBox(height: 18),
                        Text(
                          story.title,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                            height: 1.25,
                          ),
                        ),
                      ],
                    ),
                  ),
                // Soft tap hint.
                Positioned(
                  bottom: 14,
                  left: 0,
                  right: 0,
                  child: Text(
                    AppLocalizations.of(context).storyTapToOpen,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.85),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
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

class _PageDots extends StatelessWidget {
  const _PageDots({required this.count, required this.page});
  final int count;
  final double page;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(count, (i) {
        final active = i == page.round();
        return AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          margin: const EdgeInsets.symmetric(horizontal: 5),
          width: active ? 22 : 8,
          height: 8,
          decoration: BoxDecoration(
            color: active
                ? const Color(0xFFE0D5C1)
                : Colors.white.withValues(alpha: 0.35),
            borderRadius: BorderRadius.circular(4),
          ),
        );
      }),
    );
  }
}
