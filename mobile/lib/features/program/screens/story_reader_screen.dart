import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:video_player/video_player.dart';

import '../../../config/app_config.dart';
import '../data/story_models.dart';
import '../services/bedtime_audio_service.dart';

/// Immersive bedtime story reader: looping ambient video background,
/// smooth page-view navigation, parallax illustration, soft text, and a
/// gentle sleep-mode dimmer. No TTS — the parent reads to the child.
class StoryReaderScreen extends StatefulWidget {
  final Story story;

  const StoryReaderScreen({super.key, required this.story});

  @override
  State<StoryReaderScreen> createState() => _StoryReaderScreenState();
}

class _StoryReaderScreenState extends State<StoryReaderScreen> {
  late final PageController _pageController;
  VideoPlayerController? _bgVideoController;

  int _currentPage = 0;
  bool _audioMuted = false;
  bool _sleepMode = false;
  bool _audioReady = false;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
    _pageController.addListener(_onPageChanged);
    _initAudio();
    _initBackgroundVideo();
    StoryWakeLock.keepAwake();
  }

  void _onPageChanged() {
    final page = _pageController.page?.round() ?? 0;
    if (page != _currentPage) {
      setState(() => _currentPage = page);
    }
  }

  Future<void> _initAudio() async {
    await BedtimeAudioService.instance.initialize(
      assetPath: 'assets/audio/nature_ambient.mp3',
      initialVolume: 0.18,
    );
    await BedtimeAudioService.instance.play();
    if (mounted) setState(() => _audioReady = true);
  }

  Future<void> _initBackgroundVideo() async {
    try {
      if (widget.story.hasVideo) {
        _bgVideoController = VideoPlayerController.networkUrl(
          Uri.parse('${AppConfig.apiBaseUrl}/docs/stories/night_loop.mp4'),
        );
        await _bgVideoController!.initialize();
        await _bgVideoController!.setLooping(true);
        await _bgVideoController!.setVolume(0);
        await _bgVideoController!.play();
        if (mounted) setState(() {});
      }
    } catch (e) {
      debugPrint('Background video error: $e');
    }
  }

  @override
  void dispose() {
    _pageController.removeListener(_onPageChanged);
    _pageController.dispose();
    BedtimeAudioService.instance.dimForSleep();
    _bgVideoController?.dispose();
    StoryWakeLock.allowSleep();
    super.dispose();
  }

  void _nextPage() {
    final lastPage = widget.story.pages.length;
    if (_currentPage < lastPage) {
      _pageController.animateToPage(
        _currentPage + 1,
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOut,
      );
    }
  }

  void _prevPage() {
    if (_currentPage > 0) {
      _pageController.animateToPage(
        _currentPage - 1,
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOut,
      );
    }
  }

  void _toggleAudio() {
    setState(() {
      _audioMuted = !_audioMuted;
      _audioMuted
          ? BedtimeAudioService.instance.pause()
          : BedtimeAudioService.instance.play();
    });
  }

  void _toggleSleepMode() {
    setState(() => _sleepMode = !_sleepMode);
    if (_sleepMode) {
      BedtimeAudioService.instance.dimForSleep();
    } else {
      BedtimeAudioService.instance.setVolume(0.18);
    }
  }

  @override
  Widget build(BuildContext context) {
    final themeColor = Color(
      int.tryParse(widget.story.themeColor) ?? 0xFF0D9488,
    );
    final totalPages = widget.story.pages.length;
    final pageCount = totalPages + 1; // +1 for end card.

    return Scaffold(
      backgroundColor: const Color(0xFF0B3B3B),
      body: Stack(
        children: [
          // Ambient looping video or static illustration.
          Positioned.fill(
            child: widget.story.hasVideo &&
                    _bgVideoController != null &&
                    _bgVideoController!.value.isInitialized
                ? VideoPlayer(_bgVideoController!)
                : (widget.story.coverImage.startsWith('docs/')
                    ? Image.network(
                        '${AppConfig.apiBaseUrl}/${widget.story.coverImage}',
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                      )
                    : Image.asset(
                        widget.story.coverImage,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                      )),
          ),
          // Dark scrim so text always readable.
          Positioned.fill(
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    const Color(0xFF0B3B3B).withValues(alpha: 0.70),
                    const Color(0xFF0B3B3B).withValues(alpha: 0.88),
                    const Color(0xFF0B3B3B).withValues(alpha: 0.95),
                  ],
                ),
              ),
            ),
          ),
          // Sleep-mode overlay.
          AnimatedOpacity(
            opacity: _sleepMode ? 0.55 : 0,
            duration: const Duration(seconds: 2),
            child: Container(color: const Color(0xFF001F1F)),
          ),
          // Page reader.
          SafeArea(
            child: Column(
              children: [
                const SizedBox(height: 12),
                // Top bar.
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    children: [
                      _RoundButton(
                        icon: Icons.arrow_back,
                        onTap: () => Navigator.of(context).pop(),
                      ),
                      const Spacer(),
                      _RoundButton(
                        icon: _audioMuted ? Icons.volume_off : Icons.volume_up,
                        onTap: _audioReady ? _toggleAudio : null,
                      ),
                      const SizedBox(width: 10),
                      _RoundButton(
                        icon: Icons.brightness_2,
                        filled: _sleepMode,
                        onTap: _toggleSleepMode,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                // Progress.
                LinearProgressIndicator(
                  value: (_currentPage + 1) / pageCount,
                  backgroundColor: Colors.white.withValues(alpha: 0.15),
                  valueColor: AlwaysStoppedAnimation(themeColor),
                  minHeight: 4,
                ).animate().scaleX(),
                const SizedBox(height: 16),
                // Story pages.
                Expanded(
                  child: PageView(
                    controller: _pageController,
                    physics: const BouncingScrollPhysics(),
                    children: [
                      ...widget.story.pages.map(
                        (page) => _StoryPage(
                          page: page,
                          themeColor: themeColor,
                          allPages: widget.story.pages,
                        ),
                      ),
                      _buildEndCard(themeColor),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                // Bottom controls.
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _RoundButton(
                        icon: Icons.arrow_back_ios,
                        onTap: _currentPage > 0 ? _prevPage : null,
                      ),
                      Text(
                        '${min(_currentPage + 1, pageCount)} / $pageCount',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      _RoundButton(
                        icon: Icons.arrow_forward_ios,
                        onTap: _currentPage < pageCount - 1
                            ? _nextPage
                            : null,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEndCard(Color themeColor) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: const Color(0xFFFDFBF6),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text(
            '🌟',
            style: TextStyle(fontSize: 72),
          )
              .animate(onPlay: (c) => c.repeat())
              .scaleXY(begin: 0.9, end: 1.1, duration: 1200.ms)
              .then()
              .scaleXY(begin: 1.1, end: 0.9, duration: 1200.ms),
          const SizedBox(height: 20),
          Text(
            'أحسنت يا بطل!',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: themeColor,
              fontSize: 24,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            'استرخِ الآن واغمض عينيك، فالأحلام الجميلة تنتظرك.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFF4A4A4A),
              fontSize: 16,
              height: 1.6,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.check),
            label: const Text('أغلق القصة'),
            style: FilledButton.styleFrom(
              backgroundColor: themeColor,
              padding: const EdgeInsets.symmetric(
                horizontal: 28,
                vertical: 14,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StoryPage extends StatelessWidget {
  const _StoryPage({
    required this.page,
    required this.themeColor,
    required this.allPages,
  });

  final StoryPage page;
  final Color themeColor;
  final List<StoryPage> allPages;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12),
      child: Column(
        children: [
          // Parallax illustration card.
          Expanded(
            flex: 5,
            child: _ParallaxImage(
              image: page.image,
              themeColor: themeColor,
              emoji: allPages.firstWhere((p) => p.pageNumber == 1).image.contains('hope')
                  ? '🌱'
                  : '🐱',
            ),
          ),
          const SizedBox(height: 12),
          // Text card with a subtle "page paper" texture.
          Expanded(
            flex: 4,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: const Color(0xFFFDFBF6),
                borderRadius: BorderRadius.circular(26),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.2),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: SingleChildScrollView(
                child: Directionality(
                  textDirection: TextDirection.rtl,
                  child: Text(
                    page.text,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      height: 1.85,
                      color: Color(0xFF2D2D2D),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ParallaxImage extends StatelessWidget {
  const _ParallaxImage({
    required this.image,
    required this.themeColor,
    required this.emoji,
  });
  final String image;
  final Color themeColor;
  final String emoji;

  @override
  Widget build(BuildContext context) {
    return Hero(
      tag: 'story-illustration-$image',
      child: Container(
        decoration: BoxDecoration(
          color: themeColor.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(28),
          boxShadow: [
            BoxShadow(
              color: themeColor.withValues(alpha: 0.25),
              blurRadius: 20,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(28),
          child: Stack(
            fit: StackFit.expand,
            children: [
              image.startsWith('docs/')
                  ? Image.network(
                      '${AppConfig.apiBaseUrl}/$image',
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Center(
                        child: Text(
                          emoji,
                          style: const TextStyle(fontSize: 120),
                        ),
                      ),
                    )
                  : Image.asset(
                      image,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Center(
                        child: Text(
                          emoji,
                          style: const TextStyle(fontSize: 120),
                        ),
                      ),
                    ),
              // Soft vignette around the illustration.
              Container(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    colors: [
                      Colors.transparent,
                      Colors.black.withValues(alpha: 0.22),
                    ],
                    stops: const [0.75, 1.0],
                    radius: 1.1,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({
    required this.icon,
    required this.onTap,
    this.filled = false,
  });

  final IconData icon;
  final VoidCallback? onTap;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: filled
          ? const Color(0xFFE0D5C1)
          : Colors.white.withValues(alpha: 0.14),
      borderRadius: BorderRadius.circular(30),
      child: InkWell(
        borderRadius: BorderRadius.circular(30),
        onTap: onTap,
        child: Container(
          width: 44,
          height: 44,
          alignment: Alignment.center,
          child: Icon(
            icon,
            color: filled ? const Color(0xFF0B3B3B) : Colors.white,
            size: 20,
          ),
        ),
      ),
    );
  }
}
