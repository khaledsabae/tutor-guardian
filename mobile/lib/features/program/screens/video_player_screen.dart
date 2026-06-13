import 'dart:async';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../../../theme/app_theme.dart';

class VideoPlayerScreen extends StatefulWidget {
  final String? url;
  final String title;

  const VideoPlayerScreen({
    super.key,
    required this.url,
    required this.title,
  });

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  VideoPlayerController? _controller;
  bool _ready = false;
  String? _errorMessage;
  bool _showControls = true;
  Timer? _controlsTimer;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final url = widget.url;
    if (url == null || url.isEmpty) {
      setState(() {
        _errorMessage = 'الفيديو غير متاح حالياً. سيتاح قريباً بإذن الله.';
        _ready = true;
      });
      return;
    }

    try {
      final uri = Uri.parse(url);
      _controller = VideoPlayerController.networkUrl(uri);
      await _controller!.initialize();
      _controller!.addListener(_onControllerUpdate);
      setState(() {
        _ready = true;
      });
      _startControlsTimer();
    } catch (e) {
      setState(() {
        _errorMessage = 'تعذّر تحميل الفيديو. تأكد من اتصالك بالإنترنت.';
        _ready = true;
      });
    }
  }

  void _onControllerUpdate() {
    if (mounted) {
      setState(() {});
    }
  }

  void _startControlsTimer() {
    _controlsTimer?.cancel();
    _controlsTimer = Timer(const Duration(seconds: 4), () {
      if (mounted && (_controller?.value.isPlaying ?? false)) {
        setState(() {
          _showControls = false;
        });
      }
    });
  }

  void _toggleControls() {
    setState(() {
      _showControls = !_showControls;
    });
    if (_showControls) {
      _startControlsTimer();
    }
  }

  @override
  void dispose() {
    _controlsTimer?.cancel();
    _controller?.removeListener(_onControllerUpdate);
    _controller?.dispose();
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
    setState(() {});
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
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        title: Text(
          widget.title,
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
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
                      if (_controller != null && _controller!.value.isInitialized)
                        Center(
                          child: AspectRatio(
                            aspectRatio: _controller!.value.aspectRatio,
                            child: VideoPlayer(_controller!),
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
                              
                              // Play/Pause Center Button
                              Center(
                                child: IconButton(
                                  iconSize: 72,
                                  icon: Icon(
                                    _controller != null && _controller!.value.isPlaying
                                        ? Icons.pause_circle_filled
                                        : Icons.play_circle_filled,
                                    color: Colors.white,
                                  ),
                                  onPressed: _togglePlay,
                                ),
                              ),

                              // Bottom bar controls
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
                                        Colors.black.withValues(alpha: 0.8),
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
                                            trackHeight: 4.0,
                                            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8.0),
                                            overlayShape: const RoundSliderOverlayShape(overlayRadius: 16.0),
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
                                      // Time indicators
                                      if (_controller != null)
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            Text(
                                              _formatDuration(_controller!.value.position),
                                              style: const TextStyle(color: Colors.white, fontSize: 13),
                                            ),
                                            Text(
                                              _formatDuration(_controller!.value.duration),
                                              style: const TextStyle(color: Colors.white, fontSize: 13),
                                            ),
                                          ],
                                        ),
                                    ],
                                  ),
                                ),
                              )
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
