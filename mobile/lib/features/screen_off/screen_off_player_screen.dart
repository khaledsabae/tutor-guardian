/// Listening with the screen dark.
///
/// This is the mode that resolves the product's central tension. Screen time
/// is visual exposure; audio with the display off is not screen time by that
/// definition, so a child can have forty-five minutes of Qur'an, adhkar, or a
/// story in their parent's voice while spending none of their screen budget.
/// The server agrees — `screen_off` bills the audio ledger, not the screen one.
///
/// Everything visible here is designed to be not worth looking at:
///
/// **Black, and covering everything.** Not a dimmed player — a black surface
/// with an AbsorbPointer over it. A player with a scrubber and album art is a
/// screen, and a child will watch it.
///
/// **No wakelock.** The rest of the app keeps the display awake for video.
/// Here the opposite is wanted: the screen should go to sleep and stay there.
///
/// **Exit is a two-second press.** A tap is an accident — a phone in a pocket
/// or a hand brushing the glass would end a story. Two seconds is deliberate
/// and a five-year-old can still do it.
///
/// **One faint mark: «بابا بيشوف».** Rule 6 of the constitution — the child
/// knows their parent sees this, and is told so rather than surveilled.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';

import '../routine/providers/child_mode_providers.dart';

/// How long a press must be held to leave.
const kScreenOffExitHold = Duration(seconds: 2);

class ScreenOffPlayerScreen extends ConsumerStatefulWidget {
  const ScreenOffPlayerScreen({
    super.key,
    required this.title,
    required this.source,
  });

  final String title;

  /// A file path for a parent's recording, or a URL for a reciter.
  final String source;

  @override
  ConsumerState<ScreenOffPlayerScreen> createState() =>
      _ScreenOffPlayerScreenState();
}

class _ScreenOffPlayerScreenState extends ConsumerState<ScreenOffPlayerScreen> {
  final AudioPlayer _player = AudioPlayer();
  Timer? _holdTimer;
  bool _holding = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    // The system bars are part of "not worth looking at".
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _open();
  }

  Future<void> _open() async {
    try {
      if (widget.source.startsWith('http')) {
        await _player.setUrl(widget.source);
      } else {
        await _player.setFilePath(widget.source);
      }
      await _player.play();
    } catch (e) {
      // A missing recording must not become a red screen in front of a child.
      // The dark surface stays; the parent finds out from the library.
      if (mounted) setState(() => _error = e.toString());
    }
  }

  void _startHold() {
    setState(() => _holding = true);
    _holdTimer = Timer(kScreenOffExitHold, _leave);
  }

  void _cancelHold() {
    _holdTimer?.cancel();
    if (mounted) setState(() => _holding = false);
  }

  Future<void> _leave() async {
    _holdTimer?.cancel();
    await _player.stop();
    if (!mounted) return;
    await ref.read(childModeProvider.notifier).endSession(reason: 'completed');
    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _holdTimer?.cancel();
    _player.dispose();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onLongPressStart: (_) => _startHold(),
        onLongPressEnd: (_) => _cancelHold(),
        onLongPressCancel: _cancelHold,
        child: Stack(
          children: [
            // Swallows every tap, drag and swipe that is not the exit press.
            const Positioned.fill(
              child: AbsorbPointer(child: SizedBox.expand()),
            ),
            Positioned(
              bottom: 28,
              left: 0,
              right: 0,
              child: Column(
                children: [
                  if (_holding)
                    const Text('استمر…',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Color(0x66FFFFFF), fontSize: 12)),
                  const SizedBox(height: 10),
                  const Text(
                    'بابا بيشوف',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Color(0x33FFFFFF), fontSize: 10),
                  ),
                ],
              ),
            ),
            if (_error != null)
              const Positioned(
                top: 40,
                left: 0,
                right: 0,
                child: Text('…',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Color(0x22FFFFFF))),
              ),
          ],
        ),
      ),
    );
  }
}
