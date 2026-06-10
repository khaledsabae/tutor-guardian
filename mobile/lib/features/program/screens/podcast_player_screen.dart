/// Podcast player — P0.1 (third placeholder to be replaced).
///
/// Loads a remote MP3 URL, plays it via `just_audio`, and exposes a
/// minimal transport: play/pause, seek (drag the progress bar), and
/// speed selector (1x / 1.25x / 1.5x / 1.75x / 2x).
///
/// The URL is passed in by the caller (e.g. the lesson-assets
/// metadata) and is allowed to be null — a null/empty URL is treated
/// as "asset not yet available" and shows a friendly Arabic message
/// instead of crashing.
///
/// Spec note: `audio_service` background playback is **out of scope**
/// for this milestone. Just foreground playback.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';

import '../../../theme/app_theme.dart';

class PodcastPlayerScreen extends StatefulWidget {
  final String? url;
  final String title;

  const PodcastPlayerScreen({
    super.key,
    required this.url,
    required this.title,
  });

  @override
  State<PodcastPlayerScreen> createState() => _PodcastPlayerScreenState();
}

class _PodcastPlayerScreenState extends State<PodcastPlayerScreen> {
  late final AudioPlayer _player = AudioPlayer();
  StreamSubscription<PlayerState>? _stateSub;
  bool _ready = false;
  String? _errorMessage;

  // Speed options surfaced in the UI. Indexed by [_speedIndex].
  static const _speeds = <double>[1.0, 1.25, 1.5, 1.75, 2.0];
  int _speedIndex = 0;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final url = widget.url;
    if (url == null || url.isEmpty) {
      setState(() {
        _errorMessage = 'البودكاست غير متاح حالياً. سيتاح قريباً بإذن الله.';
        _ready = true;
      });
      return;
    }

    _stateSub = _player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        // Auto-pause at the end so the UI doesn't flicker.
        _player.pause();
      }
      if (mounted) setState(() {});
    });

    try {
      await _player.setUrl(url);
      await _player.setSpeed(_speeds[_speedIndex]);
      setState(() => _ready = true);
    } catch (e) {
      setState(() {
        _errorMessage = 'تعذّر تحميل البودكاست. تأكد من اتصالك بالإنترنت.';
        _ready = true;
      });
    }
  }

  @override
  void dispose() {
    _stateSub?.cancel();
    _player.dispose();
    super.dispose();
  }

  void _togglePlay() {
    if (_player.playing) {
      _player.pause();
    } else {
      _player.play();
    }
  }

  Future<void> _cycleSpeed() async {
    _speedIndex = (_speedIndex + 1) % _speeds.length;
    await _player.setSpeed(_speeds[_speedIndex]);
    if (mounted) setState(() {});
  }

  Future<void> _seekRelative(Duration delta) async {
    final pos = _player.position;
    final dur = _player.duration ?? Duration.zero;
    final target = pos + delta;
    final clamped = target < Duration.zero
        ? Duration.zero
        : (target > dur ? dur : target);
    await _player.seek(clamped);
  }

  String _formatDuration(Duration d) {
    final m = d.inMinutes.toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: !_ready
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? _ErrorState(message: _errorMessage!)
              : _PlayerView(
                  player: _player,
                  currentSpeed: _speeds[_speedIndex],
                  formatDuration: _formatDuration,
                  onTogglePlay: _togglePlay,
                  onCycleSpeed: _cycleSpeed,
                  onSeekRelative: _seekRelative,
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
            const Icon(Icons.headset_off,
                size: 64, color: AppTheme.textSecondary),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppTheme.textSecondary,
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

class _PlayerView extends StatelessWidget {
  final AudioPlayer player;
  final double currentSpeed;
  final String Function(Duration) formatDuration;
  final VoidCallback onTogglePlay;
  final VoidCallback onCycleSpeed;
  final Future<void> Function(Duration) onSeekRelative;

  const _PlayerView({
    required this.player,
    required this.currentSpeed,
    required this.formatDuration,
    required this.onTogglePlay,
    required this.onCycleSpeed,
    required this.onSeekRelative,
  });

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<Duration>(
      stream: player.positionStream,
      builder: (context, posSnap) {
        final pos = posSnap.data ?? Duration.zero;
        final dur = player.duration ?? Duration.zero;
        return StreamBuilder<PlayerState>(
          stream: player.playerStateStream,
          builder: (context, stateSnap) {
            final isPlaying = stateSnap.data?.playing ?? false;
            return Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Hero icon
                  Container(
                    width: 140,
                    height: 140,
                    alignment: Alignment.center,
                    decoration: const BoxDecoration(
                      color: AppTheme.primary,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      isPlaying
                          ? Icons.graphic_eq
                          : Icons.headset,
                      size: 70,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 24),
                  // Position / duration
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          formatDuration(pos),
                          style: const TextStyle(
                            color: AppTheme.textSecondary,
                            fontFeatures: [FontFeature.tabularFigures()],
                          ),
                        ),
                        Text(
                          formatDuration(dur),
                          style: const TextStyle(
                            color: AppTheme.textSecondary,
                            fontFeatures: [FontFeature.tabularFigures()],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 4),
                  // Seek bar
                  SliderTheme(
                    data: SliderTheme.of(context).copyWith(
                      activeTrackColor: AppTheme.primary,
                      inactiveTrackColor: AppTheme.surfaceAlt,
                      thumbColor: AppTheme.primary,
                      overlayColor: AppTheme.primary.withValues(alpha: 0.15),
                    ),
                    child: Slider(
                      min: 0.0,
                      max: dur.inMilliseconds.toDouble().clamp(1.0, 1e18),
                      value: pos.inMilliseconds
                          .toDouble()
                          .clamp(0.0, dur.inMilliseconds.toDouble().clamp(1.0, 1e18)),
                      onChanged: dur == Duration.zero
                          ? null
                          : (v) => player.seek(
                                Duration(milliseconds: v.toInt()),
                              ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Transport controls
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      IconButton(
                        key: const Key('podcast_rewind_button'),
                        iconSize: 36,
                        onPressed: dur == Duration.zero
                            ? null
                            : () => onSeekRelative(const Duration(seconds: -15)),
                        icon: const Icon(Icons.replay_10),
                        color: AppTheme.textPrimary,
                      ),
                      const SizedBox(width: 12),
                      _PlayPauseButton(
                        isPlaying: isPlaying,
                        onPressed: onTogglePlay,
                      ),
                      const SizedBox(width: 12),
                      IconButton(
                        key: const Key('podcast_forward_button'),
                        iconSize: 36,
                        onPressed: dur == Duration.zero
                            ? null
                            : () => onSeekRelative(const Duration(seconds: 30)),
                        icon: const Icon(Icons.forward_30),
                        color: AppTheme.textPrimary,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Speed selector
                  Center(
                    child: TextButton.icon(
                      key: const Key('podcast_speed_button'),
                      onPressed: onCycleSpeed,
                      icon: const Icon(Icons.speed),
                      label: Text('السرعة: $currentSpeed×'),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

class _PlayPauseButton extends StatelessWidget {
  final bool isPlaying;
  final VoidCallback onPressed;
  const _PlayPauseButton({required this.isPlaying, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppTheme.primary,
      shape: const CircleBorder(),
      elevation: 2,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onPressed,
        child: SizedBox(
          width: 72,
          height: 72,
          child: Icon(
            isPlaying ? Icons.pause : Icons.play_arrow,
            size: 44,
            color: Colors.white,
          ),
        ),
      ),
    );
  }
}
