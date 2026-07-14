import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';

import '../../../config/app_config.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../data/story_models.dart';
import 'story_reader_screen.dart';

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
              title: 'تعذر تحميل القصص',
              subtitle: e.toString(),
            ),
            data: (stories) {
              if (stories.isEmpty) {
                return const EmptyState(
                  emoji: '📚',
                  title: 'لا توجد قصص حالياً',
                  subtitle: 'انتظرونا، سنضيف قصصاً جديدة قريباً!',
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
  final List<VideoPlayerController?> _videoControllers = [];

  @override
  void initState() {
    super.initState();
    _controller = PageController(viewportFraction: 0.55);
    _controller.addListener(_onScroll);
    _initVideos();
  }

  void _initVideos() {
    for (final story in widget.stories) {
      if (story.hasVideo) {
        late final VideoPlayerController controller;
        final file = story.videoFile!;
        if (file.startsWith('docs/')) {
          controller = VideoPlayerController.networkUrl(
            Uri.parse('${AppConfig.apiBaseUrl}/$file'),
          )
            ..setLooping(true)
            ..setVolume(0)
            ..initialize().then((_) {
              if (mounted) setState(() {});
              controller.play();
            });
        } else {
          controller = VideoPlayerController.asset(file)
            ..setLooping(true)
            ..setVolume(0)
            ..initialize().then((_) {
              if (mounted) setState(() {});
              controller.play();
            });
        }
        _videoControllers.add(controller);
      } else {
        _videoControllers.add(null);
      }
    }
  }

  void _onScroll() {
    setState(() => _currentPage = _controller.page ?? 0);
    // Only the centered book plays its cover video.
    final centered = (_currentPage + 0.5).floor();
    for (var i = 0; i < _videoControllers.length; i++) {
      final vc = _videoControllers[i];
      if (vc == null || !vc.value.isInitialized) continue;
      if (i == centered && vc.value.isPlaying == false) {
        vc.play();
      } else if (i != centered && vc.value.isPlaying) {
        vc.pause();
      }
    }
  }

  @override
  void dispose() {
    _controller.removeListener(_onScroll);
    _controller.dispose();
    for (final vc in _videoControllers) {
      vc?.dispose();
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
          'حكايات قبل النوم 🌙',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w800,
                fontSize: 26,
              ),
        ).animate().fadeIn(duration: Dt.slow).slideY(begin: -0.1),
        const SizedBox(height: 8),
        const Text(
          'قصص قصيرة وهادئة تجهّز طفلك للنوم',
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
              const Positioned.fill(child: _TwinklingStars()),
              PageView.builder(
                controller: _controller,
                itemCount: widget.stories.length,
                physics: const BouncingScrollPhysics(),
                itemBuilder: (context, index) {
                  final story = widget.stories[index];
                  final distance = (_currentPage - index).abs();
                  final scale = 1 - (distance * 0.18).clamp(0.0, 0.45);
                  final angle = (index - _currentPage) * 0.18;
                  final videoController = index < _videoControllers.length
                      ? _videoControllers[index]
                      : null;
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
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => StoryReaderScreen(story: story),
      ),
    );
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
                                  story.id == 'noor_clean' ? '🌳' : '🎁',
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
                                  story.id == 'noor_clean' ? '🌳' : '🎁',
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
                    'اضغط لفتح القصة',
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

class _TwinklingStars extends StatefulWidget {
  const _TwinklingStars();

  @override
  State<_TwinklingStars> createState() => _TwinklingStarsState();
}

class _TwinklingStarsState extends State<_TwinklingStars>
    with TickerProviderStateMixin {
  late final List<_Star> _stars;

  @override
  void initState() {
    super.initState();
    final rng = Random();
    _stars = List.generate(
      55,
      (_) => _Star(
        x: rng.nextDouble(),
        y: rng.nextDouble(),
        size: 1.2 + rng.nextDouble() * 2.2,
        delay: rng.nextDouble() * 3,
        duration: 2 + rng.nextDouble() * 2,
        vsync: this,
      ),
    );
  }

  @override
  void dispose() {
    for (final star in _stars) {
      star.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: _stars
          .map(
            (s) => Positioned(
              left: s.x * MediaQuery.of(context).size.width,
              top: s.y * MediaQuery.of(context).size.height * 0.85,
              child: FadeTransition(
                opacity: s.animation,
                child: Container(
                  width: s.size,
                  height: s.size,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(s.size / 2),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.white.withValues(alpha: 0.6),
                        blurRadius: s.size * 1.5,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _Star {
  final double x;
  final double y;
  final double size;
  final double delay;
  final double duration;
  late final AnimationController _controller;
  late final Animation<double> animation;

  _Star({
    required this.x,
    required this.y,
    required this.size,
    required this.delay,
    required this.duration,
    required TickerProvider vsync,
  }) {
    _controller = AnimationController(
      vsync: vsync,
      duration: Duration(milliseconds: (duration * 1000).round()),
    );
    animation = Tween<double>(begin: 0.15, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    Future.delayed(Duration(milliseconds: (delay * 1000).round()), () {
      if (_controller.isAnimating || _controller.isCompleted) return;
      _controller.repeat(reverse: true);
    });
  }

  void dispose() => _controller.dispose();
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
