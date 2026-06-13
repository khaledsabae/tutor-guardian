/// Video Player Screen — improved with better controls visibility and thumbnail support
library;

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';

import '../../../theme/app_theme.dart';

class VideoPlayerScreen extends StatefulWidget {
  final String? url;
  final String title;
  final String? thumbnailUrl; // Optional thumbnail for preview

  const VideoPlayerScreen({
    super.key,
    required this.url,
    required this.title,
    this.thumbnailUrl,
  });

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  VideoPlayerController? _controller;
  bool _ready = false;
  String? _errorMessage;
  bool _showControls = true;
  bool _landscape = false;
  Timer? _controlsTimer;
  bool _isDisposed = false;

  Future<void> _toggleOrientation() async {
    if (!mounted) return;
    _landscape = !_landscape;
    if (_landscape) {
      await SystemChrome.setPreferredOrientations(
        [DeviceOrientation.landscapeLeft, DeviceOrientation.landscapeRight],
      );
      await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    } else {
      await SystemChrome.setPreferredOrientations(
        [DeviceOrientation.portraitUp],
      );
      await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    }
    if (mounted) setState(() {});
  }

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final url = widget.url;
    if (url == null || url.isEmpty) {
      if (mounted) {
        setState(() {
          _errorMessage = 'الفيديو غير متاح حالياً. سيتاح قريباً بإذن الله.';
          _ready = true;
        });
      }
      return;
    }

    try {
      final uri = Uri.parse(url);
      _controller = VideoPlayerController.networkUrl(uri);
      await _controller!.initialize();
      if (!_isDisposed && mounted) {
        _controller!.addListener(_onControllerUpdate);
        setState(() {
          _ready = true;
        });
        _startControlsTimer();
      } else {
        _controller?.dispose();
        _controller = null;
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'تعذّر تحميل الفيديو. تأكد من اتصالك بالإنترنت.';
          _ready = true;
        });
      }
    }
  }

  void _onControllerUpdate() {
    if (mounted && !_isDisposed) {
      setState(() {});
    }
  }

  void _startControlsTimer() {
    _controlsTimer?.cancel();
    _controlsTimer = Timer(const Duration(seconds: 4), () {
      if (mounted && !_isDisposed && (_controller?.value.isPlaying ?? false)) {
        setState(() {
          _showControls = false;
        });
      }
    });
  }

  void _toggleControls() {
    if (!mounted) return;
    setState(() {
      _showControls = !_showControls;
    });
    if (_showControls) {
      _startControlsTimer();
    }
  }

  @override
  void dispose() {
    _isDisposed = true;
    _controlsTimer?.cancel();
    _controller?.removeListener(_onControllerUpdate);
    _controller?.dispose();
    // Always restore portrait + system UI when leaving the player.
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  void _togglePlay() {
    if (_controller == null) return;
    if (_controller!.value.isPlaying) {
      _controller!.pause();
    } else {
      _controller!.play();
    }
    _startControlsTimer();
    if (mounted) setState(() {});
  }

  String _formatDuration(Duration d) {
    final m = d.inMinutes.toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: _landscape
          ? null
          : AppBar(
              backgroundColor: Colors.transparent,
              elevation: 0,
              iconTheme: const IconThemeData(color: Colors.white),
              title: Text(
                widget.title,
                style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.bold),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              actions: [
                if (widget.thumbnailUrl != null)
                  IconButton(
                    tooltip: 'تصغير',
                    icon: const Icon(Icons.fullscreen_exit, color: Colors.white),
                    onPressed: () => Navigator.pop(context),
                  ),
                IconButton(
                  tooltip: 'تدوير الشاشة',
                  icon: const Icon(Icons.screen_rotation, color: Colors.white),
                  onPressed: _controller != null ? _toggleOrientation : null,
                ),
              ],
            ),
      body: !_ready
          ? const Center(child: CircularProgressIndicator(color: Colors.white))
          : _errorMessage != null
              ? _ErrorState(message: _errorMessage!)
              : GestureDetector(
                  onTap: _toggleControls,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Video area with container box
                      Center(
                        child: Container(
                          constraints: BoxConstraints(
                            maxWidth: _landscape ? double.infinity : MediaQuery.of(context).size.width - 32,
                            maxHeight: _landscape ? double.infinity : MediaQuery.of(context).size.height * 0.7,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.5),
                                blurRadius: 24,
                                offset: const Offset(0, 8),
                              ),
                            ],
                            border: Border.all(
                              color: AppTheme.primary.withValues(alpha: 0.5),
                              width: 2,
                            ),
                          ),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: AspectRatio(
                              aspectRatio: _controller?.value.aspectRatio ?? 16/9,
                              child: _controller != null && _controller!.value.isInitialized
                                  ? VideoPlayer(_controller!)
                                  : const Center(child: CircularProgressIndicator(color: Colors.white)),
                            ),
                          ),
                        ),
                      ),

                      // Thumbnail overlay when video is paused/not started
                      if (_controller != null && 
                          !_controller!.value.isPlaying && 
                          _controller!.value.position == Duration.zero &&
                          widget.thumbnailUrl != null)
                        Positioned.fill(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: Image.network(
                              widget.thumbnailUrl!,
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => Container(
                                color: Colors.black,
                                child: const Center(child: Icon(Icons.videocam, size: 64, color: Colors.white54)),
                              ),
                            ),
                          ),
                        ),

                      // Controls Overlay
                      AnimatedOpacity(
                        opacity: _showControls ? 1.0 : 0.0,
                        duration: const Duration(milliseconds: 300),
                        child: IgnorePointer(
                          ignoring: !_showControls,
                          child: Stack(
                            children: [
                              // Dark semi-transparent background
                              Container(
                                color: Colors.black.withValues(alpha: 0.5),
                              ),

                              // Play/Pause Center Button — large, with a
                              // solid circular backdrop so it's clearly visible.
                              Center(
                                child: GestureDetector(
                                  onTap: _togglePlay,
                                  child: Container(
                                    width: 96,
                                    height: 96,
                                    decoration: BoxDecoration(
                                      color: AppTheme.primary
                                          .withValues(alpha: 0.92),
                                      shape: BoxShape.circle,
                                      boxShadow: [
                                        BoxShadow(
                                          color:
                                              Colors.black.withValues(alpha: .4),
                                          blurRadius: 16,
                                        ),
                                      ],
                                    ),
                                    child: Icon(
                                      _controller != null &&
                                              _controller!.value.isPlaying
                                          ? Icons.pause
                                          : Icons.play_arrow,
                                      color: Colors.white,
                                      size: 56,
                                    ),
                                  ),
                                ),
                              ),

                              // Top controls bar
                              Positioned(
                                top: 0,
                                left: 0,
                                right: 0,
                                child: SafeArea(
                                  child: Padding(
                                    padding: const EdgeInsets.all(16),
                                    child: Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        // Title
                                        Flexible(
                                          child: Text(
                                            widget.title,
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontWeight: FontWeight.bold,
                                              fontSize: 16,
                                              shadows: [
                                                Shadow(
                                                  color: Colors.black87,
                                                  blurRadius: 4,
                                                  offset: Offset(0, 2),
                                                ),
                                              ],
                                            ),
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ),
                                        // Rotate + Close buttons
                                        Row(
                                          children: [
                                            IconButton(
                                              tooltip: 'تدوير الشاشة',
                                              icon: const Icon(Icons.screen_rotation,
                                                  color: Colors.white, size: 28),
                                              onPressed: _controller != null
                                                  ? _toggleOrientation
                                                  : null,
                                            ),
                                            IconButton(
                                              tooltip: 'إغلاق',
                                              icon: const Icon(Icons.close,
                                                  color: Colors.white, size: 28),
                                              onPressed: () => Navigator.pop(context),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),

                              // Bottom controls bar
                              Positioned(
                                bottom: 0,
                                left: 0,
                                right: 0,
                                child: Container(
                                  padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(
                                      begin: Alignment.topCenter,
                                      end: Alignment.bottomCenter,
                                      colors: [
                                        Colors.transparent,
                                        Colors.black.withValues(alpha: 0.9),
                                      ],
                                    ),
                                  ),
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      // Progress Slider
                                      if (_controller != null)
                                        SliderTheme(
                                          data: SliderTheme.of(context).copyWith(
                                            activeTrackColor: AppTheme.primary,
                                            inactiveTrackColor: Colors.white.withValues(alpha: 0.3),
                                            thumbColor: AppTheme.primary,
                                            trackHeight: 6.0,
                                            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 10.0),
                                            overlayShape: const RoundSliderOverlayShape(overlayRadius: 20.0),
                                            valueIndicatorColor: AppTheme.primary,
                                            valueIndicatorTextStyle: const TextStyle(
                                              color: Colors.white,
                                              fontSize: 12,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          child: Slider(
                                            min: 0.0,
                                            max: _controller!.value.duration.inMilliseconds.toDouble(),
                                            value: _controller!.value.position.inMilliseconds.toDouble().clamp(
                                                  0.0,
                                                  _controller!.value.duration.inMilliseconds.toDouble(),
                                                ),
                                            onChanged: (value) {
                                              _controller!.seekTo(
                                                Duration(milliseconds: value.toInt()),
                                              );
                                              _startControlsTimer();
                                            },
                                          ),
                                        ),
                                      const SizedBox(height: 8),
                                      // Time indicators + Fullscreen button
                                      if (_controller != null)
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            Text(
                                              _formatDuration(_controller!.value.position),
                                              style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                                            ),
                                            IconButton(
                                              tooltip: 'ملء الشاشة',
                                              icon: const Icon(Icons.fullscreen, color: Colors.white, size: 24),
                                              onPressed: _controller != null ? _toggleOrientation : null,
                                            ),
                                            Text(
                                              _formatDuration(_controller!.value.duration),
                                              style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                                            ),
                                          ],
                                        ),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  const _ErrorState({required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.videocam_off, size: 64, color: Colors.white54),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white70,
                height: 1.6,
                fontSize: 16,
              ),
            ),
          ],
        ),
      ),
    );
  }
}