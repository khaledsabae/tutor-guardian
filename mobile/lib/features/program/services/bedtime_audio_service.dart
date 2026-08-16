import 'dart:async';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import '../../screen_off/audio_tag.dart';

/// Calm, non-intrusive bedtime ambient audio manager.
///
/// Plays a looping quiet nature sound at a very low volume. Unlike the old
/// heavy forest sound, this is designed to sit in the background while a
/// parent reads or the child reads silently.
class BedtimeAudioService {
  BedtimeAudioService._();
  static final BedtimeAudioService instance = BedtimeAudioService._();

  AudioPlayer? _player;
  bool _initialized = false;
  double _volume = 0.0;

  /// Current playhead position (for progress indicators if needed).
  Duration? get position => _player?.position;

  /// Whether audio is currently audible.
  bool get isPlaying => _player?.playing ?? false;

  /// Volume in the range [0, 1].
  double get volume => _volume;

  /// Prepares the audio engine with the asset at [assetPath].
  /// Does **not** start playback until [play] is called.
  Future<void> initialize({
    required String assetPath,
    double initialVolume = 0.18,
  }) async {
    await dispose();
    _player = AudioPlayer();
    _volume = initialVolume.clamp(0.0, 1.0);
    try {
      await _player!.setAudioSource(AudioSource.asset(
        assetPath,
        tag: audioTag(id: assetPath, title: 'خلفية هادئة'),
      ));
      await _player!.setLoopMode(LoopMode.all);
      await _player!.setVolume(_volume);
      _initialized = true;
    } catch (e) {
      debugPrint('BedtimeAudioService init failed: $e');
      _initialized = false;
    }
  }

  /// Start or resume playback with a gentle fade-in.
  Future<void> play({Duration fadeIn = const Duration(seconds: 2)}) async {
    if (_player == null || !_initialized) return;
    final target = _volume;
    await _player!.setVolume(0.0);
    await _player!.play();
    await _animateVolume(target, fadeIn);
  }

  /// Pause with a gentle fade-out so it never cuts abruptly.
  Future<void> pause({Duration fadeOut = const Duration(seconds: 1)}) async {
    if (_player == null) return;
    await _animateVolume(0.0, fadeOut);
    await _player!.pause();
  }

  /// Set volume immediately or animate to it.
  Future<void> setVolume(double volume, {Duration? animate}) async {
    _volume = volume.clamp(0.0, 1.0);
    if (_player == null) return;
    if (animate != null) {
      await _animateVolume(_volume, animate);
    } else {
      await _player!.setVolume(_volume);
    }
  }

  /// Lower volume for "sleepy" moments (e.g. end of story).
  Future<void> dimForSleep() async {
    await setVolume(0.06, animate: const Duration(seconds: 8));
  }

  Future<void> _animateVolume(double target, Duration duration) async {
    if (_player == null) return;
    final start = _player!.volume;
    const steps = 20;
    final stepDuration = duration ~/ steps;
    for (var i = 1; i <= steps; i++) {
      final t = i / steps;
      final value = start + (target - start) * t;
      await _player!.setVolume(value.clamp(0.0, 1.0));
      await Future.delayed(stepDuration);
    }
  }

  /// Free resources.
  Future<void> dispose() async {
    _initialized = false;
    if (_player != null) {
      await _player!.stop();
      await _player!.dispose();
      _player = null;
    }
  }
}

/// A tiny widget that observes the current route and automatically pauses
/// the bedtime ambient audio when the user leaves the story screens.
class BedtimeAudioRouteObserver extends RouteObserver<PageRoute<void>> {
  @override
  void didPush(Route<void> route, Route<void>? previousRoute) {
    super.didPush(route, previousRoute);
    if (!_isStoryRoute(route)) {
      BedtimeAudioService.instance.pause();
    }
  }

  @override
  void didPop(Route<void> route, Route<void>? previousRoute) {
    super.didPop(route, previousRoute);
    if (!_isStoryRoute(previousRoute)) {
      BedtimeAudioService.instance.pause();
    }
  }

  bool _isStoryRoute(Route<void>? route) {
    final name = route?.settings.name ?? '';
    return name.contains('story') || name.contains('Story');
  }
}

/// A wrapper that keeps the device awake while a story is being read,
/// then allows it to sleep again afterwards.
class StoryWakeLock {
  static Future<void> keepAwake() async {
    await WakelockPlus.enable();
  }

  static Future<void> allowSleep() async {
    await WakelockPlus.disable();
  }
}
