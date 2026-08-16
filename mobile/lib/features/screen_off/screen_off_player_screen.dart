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
import 'package:just_audio_background/just_audio_background.dart';

import '../../main.dart' show messengerKey;
import '../routine/providers/child_mode_providers.dart';

/// How long a press must be held to leave.
const kScreenOffExitHold = Duration(seconds: 2);

class ScreenOffPlayerScreen extends ConsumerStatefulWidget {
  const ScreenOffPlayerScreen({
    super.key,
    required this.title,
    required this.source,
    this.playlist,
  });

  final String title;

  /// A file path for a parent's recording, or a URL for a reciter.
  final String source;

  /// Optional ordered sources played back to back.
  ///
  /// Recitation is not one file per surah — everyayah serves one file per
  /// *verse*, so playing al-Mulk means thirty requests in sequence. When this
  /// is set, [source] is ignored and used only as the first element's identity.
  final List<String>? playlist;

  @override
  ConsumerState<ScreenOffPlayerScreen> createState() =>
      _ScreenOffPlayerScreenState();
}

class _ScreenOffPlayerScreenState extends ConsumerState<ScreenOffPlayerScreen>
    with WidgetsBindingObserver {
  final AudioPlayer _player = AudioPlayer();
  Timer? _holdTimer;
  bool _holding = false;

  /// The surface that was running when we arrived, so leaving can put it back
  /// rather than ending child mode outright.
  String? _previousSurface;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // The system bars are part of "not worth looking at".
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _open();
  }

  Future<void> _open() async {
    // Move the session to `screen_off` before a single second of audio plays.
    // Listening with the display dark is not screen time by the policy's own
    // definition and bills a separate forty-five-minute ledger — but the
    // player used to open inside whatever session was already running, which
    // was always `habit`. Every story told in the dark was charged to the
    // screen budget it was designed to avoid.
    final childMode = ref.read(childModeProvider);
    if (childMode.active && childMode.sessionId != null) {
      _previousSurface = childMode.surface;
      final ok = await ref
          .read(childModeProvider.notifier)
          .switchSurface('screen_off');
      if (!ok) {
        // The audio ledger is spent, or the band does not allow this surface.
        // Leave quietly rather than play against a session the server refused.
        if (mounted) Navigator.of(context).pop();
        return;
      }
    }

    try {
      // The MediaItem tag is what just_audio_background needs to raise a
      // foreground service and a media notification. Without a tag it throws,
      // and without the service Android silences playback within seconds of
      // the screen going off — which is precisely the situation this whole
      // mode is built for. The package was in pubspec.yaml since sprint 2 and
      // was never initialised or tagged, so background playback had never
      // actually worked.
      final list = widget.playlist;
      if (list != null && list.isNotEmpty) {
        await _player.setAudioSources([
          for (var i = 0; i < list.length; i++)
            AudioSource.uri(Uri.parse(list[i]), tag: _mediaItemFor(list[i], i)),
        ]);
      } else {
        await _player.setAudioSource(
          widget.source.startsWith('http')
              ? AudioSource.uri(Uri.parse(widget.source), tag: _mediaItem)
              : AudioSource.file(widget.source, tag: _mediaItem),
        );
      }
      await _player.play();
    } catch (e) {
      // Leave, and say why.
      //
      // This used to set an error that rendered as a nearly-invisible «…» on
      // the black surface — the reasoning being that a child should not be
      // shown a red error. That reasoning is right and the result was wrong:
      // a missing file, an unreachable reciter and a working player with the
      // volume down all produced exactly the same screen. A black rectangle
      // with «بابا بيشوف» at the bottom and no sound, indefinitely, with no
      // way to tell whether it was broken.
      //
      // A surface that cannot play anything is not a listening surface. Close
      // it, release the session, and let whoever opened it read one line.
      if (!mounted) return;
      await _releaseSurface();
      if (!mounted) return;
      Navigator.of(context).pop();
      messengerKey.currentState?.showSnackBar(
        const SnackBar(content: Text('تعذّر تشغيل الصوت. جرّب مصدرًا تاني.')),
      );
    }
  }

  /// Hand the session back to whatever surface was running before, or end it.
  Future<void> _releaseSurface() async {
    final notifier = ref.read(childModeProvider.notifier);
    final previous = _previousSurface;
    if (previous != null && previous != 'screen_off') {
      await notifier.switchSurface(previous);
    } else if (previous != null) {
      await notifier.endSession(reason: 'completed');
    }
  }

  MediaItem get _mediaItem => _mediaItemFor(widget.source, 0);

  MediaItem _mediaItemFor(String id, int index) => MediaItem(
        // Ids must be distinct across a playlist or the notification and the
        // queue index disagree about which item is playing.
        id: '$id#$index',
        title: widget.title,
        // Deliberately spare. This text appears on the lock screen, where the
        // rule about not making the screen worth looking at still applies.
        artist: 'المربي',
      );

  /// Coming back from the background is the moment the session is most likely
  /// to be stale, so report immediately rather than waiting out the rest of
  /// the interval.
  ///
  /// The heartbeat timer keeps running while the app is backgrounded — the
  /// foreground service above is what keeps the process alive to run it — but
  /// a device that suspended deeply can still miss beats, and the server reaps
  /// a session ninety seconds after the last one. Beating on resume closes
  /// that window; if the session is already gone, the notifier ends the
  /// surface and the widget below pops.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(ref.read(childModeProvider.notifier).beatNow());
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
    // Put the child back on the surface a parent opened for them, on its own
    // budget. Ending the session outright would drop them out of child mode
    // entirely because a story finished — the exit is the long press, not the
    // end of the audio.
    if (_previousSurface == null) {
      await ref.read(childModeProvider.notifier).endSession(reason: 'completed');
    } else {
      await _releaseSurface();
    }
    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _holdTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
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
          ],
        ),
      ),
    );
  }
}
