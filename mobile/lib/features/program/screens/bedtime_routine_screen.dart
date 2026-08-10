import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/app_config.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../coins/coins_providers.dart';
import '../data/story_models.dart';
import '../services/bedtime_audio_service.dart';
import '../../../widgets/ui/night_sky.dart';

class BedtimeRoutineScreen extends ConsumerStatefulWidget {
  final Story story;

  const BedtimeRoutineScreen({super.key, required this.story});

  @override
  ConsumerState<BedtimeRoutineScreen> createState() => _BedtimeRoutineScreenState();
}

class _DhikrItem {
  final String text;
  final String translation;
  final int count;

  const _DhikrItem({
    required this.text,
    required this.translation,
    required this.count,
  });
}

class _StarParticle {
  final double x;
  final double y;
  final Key key;

  const _StarParticle(this.x, this.y, this.key);
}

class _BedtimeRoutineScreenState extends ConsumerState<BedtimeRoutineScreen> {
  final List<_DhikrItem> _adhkar = const [
    _DhikrItem(
      text: 'بِاسْمِكَ رَبِّي وَضَعْتُ جَنْبِي، وَبِكَ أَرْفَعُهُ',
      translation: 'مرة واحدة',
      count: 1,
    ),
    _DhikrItem(
      text: 'اللَّهُمَّ قِنِي عَذَابَكَ يَوْمَ تَبْعَثُ عِبَادَكَ',
      translation: '٣ مرات',
      count: 3,
    ),
    _DhikrItem(
      text: 'بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا',
      translation: 'مرة واحدة',
      count: 1,
    ),
  ];

  int _currentIndex = 0;
  late int _remainingCount;
  bool _finished = false;
  final List<_StarParticle> _starParticles = [];
  @override
  void initState() {
    super.initState();
    _remainingCount = _adhkar[0].count;
    _initAudio();
    StoryWakeLock.keepAwake();
  }

  Future<void> _initAudio() async {
    if (BedtimeAudioService.instance.isPlaying) {
      return;
    }
    await BedtimeAudioService.instance.initialize(
      assetPath: 'assets/audio/nature_ambient.mp3',
      initialVolume: 0.18,
    );
    await BedtimeAudioService.instance.play();
  }

  @override
  void dispose() {
    StoryWakeLock.allowSleep();
    super.dispose();
  }

  void _onTapDhikr(TapUpDetails details) {
    if (_finished) return;

    // Add star particle at tap position
    final localPos = details.localPosition;
    setState(() {
      _starParticles.add(_StarParticle(localPos.dx, localPos.dy, UniqueKey()));
      _remainingCount--;
    });

    // Cleanup particle after animation
    Future.delayed(const Duration(milliseconds: 1000), () {
      if (mounted) {
        setState(() {
          if (_starParticles.isNotEmpty) {
            _starParticles.removeAt(0);
          }
        });
      }
    });

    if (_remainingCount <= 0) {
      // Transition to next dhikr or finish
      Future.delayed(const Duration(milliseconds: 600), () {
        if (!mounted) return;
        if (_currentIndex < _adhkar.length - 1) {
          setState(() {
            _currentIndex++;
            _remainingCount = _adhkar[_currentIndex].count;
          });
        } else {
          setState(() {
            _finished = true;
          });
          // Award 5 coins to the child
          ref.read(coinsProvider.notifier).earn(5);
        }
      });
    }
  }

  void _startStory() {
    Navigator.of(context).pushReplacement(
      AppRoutes.storyReader(widget.story),
    );
  }

  @override
  Widget build(BuildContext context) {
    final themeColor = Color(
      int.tryParse(widget.story.themeColor) ?? 0xFF0D9488,
    );

    return Scaffold(
      backgroundColor: const Color(0xFF0B3B3B),
      body: Stack(
        children: [
          // Background night visual
          Positioned.fill(
            child: widget.story.hasVideo
                ? Container(color: const Color(0xFF0B3B3B))
                : (widget.story.coverImage.startsWith('docs/')
                    ? Image.network(
                        '${AppConfig.apiBaseUrl}/${widget.story.coverImage}',
                        fit: BoxFit.cover,
                        opacity: const AlwaysStoppedAnimation(0.2),
                        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                      )
                    : Image.asset(
                        widget.story.coverImage,
                        fit: BoxFit.cover,
                        opacity: const AlwaysStoppedAnimation(0.2),
                        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                      )),
          ),
          Positioned.fill(
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    const Color(0xFF0B3B3B).withValues(alpha: 0.8),
                    const Color(0xFF0B3B3B).withValues(alpha: 0.95),
                  ],
                ),
              ),
            ),
          ),
          const Positioned.fill(child: TwinklingStars()),
          const Positioned.fill(child: FloatingFireflies()),

          SafeArea(
            child: Column(
              children: [
                const SizedBox(height: 12),
                // Top close button
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    children: [
                      _RoundButton(
                        icon: Icons.close,
                        onTap: () => Navigator.of(context).pop(),
                      ),
                      const Spacer(),
                      Text(
                        AppLocalizations.of(context).bedtimeStories,
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const Spacer(),
                      const SizedBox(width: 44),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // Adhkar content card
                Expanded(
                  child: Center(
                    child: SingleChildScrollView(
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 500),
                        transitionBuilder: (child, animation) {
                          return FadeTransition(
                            opacity: animation,
                            child: ScaleTransition(
                              scale: Tween<double>(begin: 0.95, end: 1.0)
                                  .animate(animation),
                              child: child,
                            ),
                          );
                        },
                        child: _finished
                            ? _buildCompletionCard(themeColor)
                            : _buildDhikrCard(themeColor),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDhikrCard(Color themeColor) {
    final dhikr = _adhkar[_currentIndex];
    final progress = (_currentIndex) / _adhkar.length;

    return Container(
      key: ValueKey(_currentIndex),
      margin: const EdgeInsets.symmetric(horizontal: 24),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: const Color(0xFFFDFBF6),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Step progress indicator
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                AppLocalizations.of(context).bedtimeAdhkarCounter(_currentIndex + 1, _adhkar.length),
                style: TextStyle(
                  color: themeColor,
                  fontWeight: FontWeight.w800,
                  fontSize: 14,
                ),
              ),
              Text(
                dhikr.translation,
                style: const TextStyle(
                  color: Color(0xFF7D7D7D),
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: progress,
            backgroundColor: Colors.grey.withValues(alpha: 0.15),
            valueColor: AlwaysStoppedAnimation(themeColor),
            minHeight: 6,
          ),
          const SizedBox(height: 32),

          // Interactive tap-to-count zone
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapUp: _onTapDhikr,
            child: Container(
              width: double.infinity,
              constraints: const BoxConstraints(minHeight: 180),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Directionality(
                    textDirection: TextDirection.rtl,
                    child: Text(
                      dhikr.text,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        height: 1.85,
                        color: Color(0xFF2D2D2D),
                      ),
                    ),
                  ),
                  // Render tap star particles inside this card
                  ..._starParticles.map((star) {
                    return Positioned(
                      left: star.x - 20,
                      top: star.y - 20,
                      child: const Text(
                        '⭐',
                        style: TextStyle(fontSize: 28),
                      )
                          .animate()
                          .fadeOut(delay: 400.ms, duration: 400.ms)
                          .slideY(begin: 0, end: -3, duration: 700.ms)
                          .scale(
                            begin: const Offset(1.0, 1.0),
                            end: const Offset(0.3, 0.3),
                            duration: 700.ms,
                          ),
                    );
                  }),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Counter button indicator
          AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            decoration: BoxDecoration(
              color: themeColor,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.touch_app, color: Colors.white, size: 20),
                const SizedBox(width: 8),
                Text(
                  AppLocalizations.of(context).bedtimeTapToRepeat(_remainingCount),
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompletionCard(Color themeColor) {
    return Container(
      key: const ValueKey('finished'),
      margin: const EdgeInsets.symmetric(horizontal: 24),
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: const Color(0xFFFDFBF6),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.35),
            blurRadius: 24,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            '🪙',
            style: TextStyle(fontSize: 72),
          )
              .animate(onPlay: (c) => c.repeat())
              .scaleXY(begin: 0.9, end: 1.1, duration: 1000.ms)
              .then()
              .scaleXY(begin: 1.1, end: 0.9, duration: 1000.ms),
          const SizedBox(height: 20),
          Text(
            AppLocalizations.of(context).lessonCelebrationTitle,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: themeColor,
              fontSize: 24,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            AppLocalizations.of(context).bedtimeStoriesDesc,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFF4A4A4A),
              fontSize: 16,
              height: 1.6,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 28),
          FilledButton.icon(
            onPressed: _startStory,
            icon: const Icon(Icons.menu_book),
            label: Text(
              AppLocalizations.of(context).startLearning,
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            style: FilledButton.styleFrom(
              backgroundColor: themeColor,
              padding: const EdgeInsets.symmetric(
                horizontal: 32,
                vertical: 16,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({
    required this.icon,
    required this.onTap,
  });

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.14),
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
            color: Colors.white,
            size: 20,
          ),
        ),
      ),
    );
  }
}
