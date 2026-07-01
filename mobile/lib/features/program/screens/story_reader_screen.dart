import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:just_audio/just_audio.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../data/story_models.dart';

class StoryReaderScreen extends StatefulWidget {
  final Story story;

  const StoryReaderScreen({super.key, required this.story});

  @override
  State<StoryReaderScreen> createState() => _StoryReaderScreenState();
}

class _StoryReaderScreenState extends State<StoryReaderScreen> {
  final PageController _pageController = PageController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  int _currentPage = 0;
  bool _audioMuted = false;

  @override
  void initState() {
    super.initState();
    _initAudio();
  }

  Future<void> _initAudio() async {
    try {
      await _audioPlayer.setAsset('assets/audio/nature_ambient.mp3');
      await _audioPlayer.setLoopMode(LoopMode.one);
      await _audioPlayer.setVolume(0.25); // Calm background level
      await _audioPlayer.play();
    } catch (e) {
      debugPrint('Error playing background audio: $e');
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    _audioPlayer.dispose();
    super.dispose();
  }

  void _nextPage() {
    if (_currentPage < widget.story.pages.length - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  void _prevPage() {
    if (_currentPage > 0) {
      _pageController.previousPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  void _toggleAudio() {
    setState(() {
      _audioMuted = !_audioMuted;
      if (_audioMuted) {
        _audioPlayer.pause();
      } else {
        _audioPlayer.play();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final themeColor = Color(
      int.tryParse(widget.story.themeColor) ?? 0xFF0D9488,
    );
    final totalPages = widget.story.pages.length;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.story.title),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: Icon(
              _audioMuted ? Icons.volume_off_rounded : Icons.volume_up_rounded,
              color: themeColor,
            ),
            onPressed: _toggleAudio,
            tooltip: 'صوت الطبيعة في الخلفية',
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Linear Progress Indicator
            LinearProgressIndicator(
              value: (_currentPage + 1) / totalPages,
              color: themeColor,
              backgroundColor: themeColor.withValues(alpha: .15),
              minHeight: 6,
            ),
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                onPageChanged: (page) {
                  setState(() {
                    _currentPage = page;
                  });
                },
                itemCount: totalPages,
                itemBuilder: (context, index) {
                  final page = widget.story.pages[index];
                  return Column(
                    children: [
                      // Page Illustration Image (Top half)
                      Expanded(
                        flex: 5,
                        child: Container(
                          margin: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                          decoration: BoxDecoration(
                            color: themeColor.withValues(alpha: .08),
                            borderRadius: BorderRadius.circular(24),
                            border: Border.all(
                              color: themeColor.withValues(alpha: .15),
                              width: 2,
                            ),
                          ),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(22),
                            child: Image.asset(
                              page.image,
                              fit: BoxFit.cover,
                              errorBuilder: (context, error, stackTrace) {
                                // Fallback beautifully if asset not yet generated/added.
                                return Container(
                                  color: themeColor.withValues(alpha: .05),
                                  padding: const EdgeInsets.all(24),
                                  child: Center(
                                    child: Column(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        Text(
                                          widget.story.id == 'hope_sprout' ? '🌱' : '🐱',
                                          style: const TextStyle(fontSize: 64),
                                        ).animate(onPlay: (c) => c.repeat()).shake(
                                              duration: const Duration(seconds: 2),
                                            ),
                                        const SizedBox(height: 16),
                                        Text(
                                          'الصفحة ${index + 1}',
                                          style: TextStyle(
                                            fontSize: 16,
                                            fontWeight: FontWeight.w700,
                                            color: themeColor,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        ),
                      ),
                      // Story Narrative Text (Bottom half)
                      Expanded(
                        flex: 4,
                        child: Container(
                          width: double.infinity,
                          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          padding: const EdgeInsets.all(24),
                          decoration: BoxDecoration(
                            color: AppTheme.surface,
                            borderRadius: BorderRadius.circular(24),
                            boxShadow: Dt.cardShadow,
                            border: Border.all(
                              color: Colors.transparent,
                              width: 0,
                            ),
                          ),
                          child: SingleChildScrollView(
                            child: Directionality(
                              textDirection: TextDirection.rtl,
                              child: Text(
                                page.text,
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w600,
                                  height: 1.7,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
            // Bottom Controls Bar
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Previous Button
                  Opacity(
                    opacity: _currentPage > 0 ? 1.0 : 0.0,
                    child: IgnorePointer(
                      ignoring: _currentPage == 0,
                      child: IconButton.filledTonal(
                        onPressed: _prevPage,
                        icon: const Icon(Icons.arrow_back_rounded),
                        style: IconButton.styleFrom(
                          padding: const EdgeInsets.all(14),
                          foregroundColor: themeColor,
                          backgroundColor: themeColor.withValues(alpha: .1),
                        ),
                      ),
                    ),
                  ),
                  // Page Indicator text
                  Text(
                    '${_currentPage + 1} / $totalPages',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: themeColor,
                    ),
                  ),
                  // Next / Done Button
                  _currentPage == totalPages - 1
                      ? FilledButton.icon(
                          onPressed: () {
                            Navigator.of(context).pop();
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: const Directionality(
                                  textDirection: TextDirection.rtl,
                                  child: Text('أحسنت! تمت قراءة القصة بنجاح 🎉'),
                                ),
                                backgroundColor: themeColor,
                              ),
                            );
                          },
                          icon: const Icon(Icons.check_circle_outline_rounded),
                          label: const Text('أنهيت القصة'),
                          style: FilledButton.styleFrom(
                            backgroundColor: themeColor,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 20,
                              vertical: 14,
                            ),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                        )
                      : IconButton.filled(
                          onPressed: _nextPage,
                          icon: const Icon(Icons.arrow_forward_rounded),
                          style: IconButton.styleFrom(
                            padding: const EdgeInsets.all(14),
                            backgroundColor: themeColor,
                            foregroundColor: Colors.white,
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
