/// Soft interface sounds — «أصوات ناعمة بلا موسيقى».
///
/// Five short sounds, synthesised by `ops/tools/gen_sfx.py` (filtered noise, a
/// soft click, a breath of air, one water drop, a page): no instrument, no
/// melody, no bell. They live in `assets/audio/sfx/` and are each a few KB.
///
/// **They never take the stage from recitation.** The players here use
/// audioplayers' low-latency mode (Android SoundPool) with an audio context
/// that requests **no audio focus** (`AndroidAudioFocus.none`) and declares
/// the stream as UI sonification. Requesting focus is how one player makes
/// another pause or duck; not requesting it means a Qur'an recitation, a
/// podcast or a story already playing through just_audio carries on exactly
/// as it was, with the tick mixed over it. Nothing here goes through
/// just_audio, which owns focus for the long-form audio.
///
/// **They follow a person, never a clock.** The only callers are the
/// [Haptics] helpers (themselves called from taps, sends, logs and answers)
/// plus explicit user-action sites. A haptic that fires on its own — the
/// daily gift landing on Home, a quiz timer running out — passes
/// `sound: false` or maps to a helper with no sound.
///
/// **One switch.** The preference belongs to [Haptics] (`haptics_enabled`,
/// shown in Settings as «الأصوات والاهتزاز»); Haptics mirrors it into
/// [SoundFx.switchOn] when it loads and when it changes.
///
/// **Silent where silence is the point:** while the child surface is open
/// (child mode) and during screen-off listening. See [SoundPolicy].
///
/// **Never in the way.** Until [SoundFx.init] runs (once, from `main`, after
/// the first frame is requested) every call is a no-op; a player that fails
/// to load or play is swallowed. Nothing here throws and nothing is awaited
/// on a UI path.
library;

import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';

/// The five sounds, named for what they mean rather than how they sound.
enum Sfx {
  /// A soft click: a plain press.
  tap,

  /// A tiny tick: a choice made — a tab, a chip, a message sent.
  select,

  /// One water drop: something saved or earned.
  success,

  /// A soft swell of air: a light being lit.
  lantern,

  /// A paper rustle: a page turned.
  page;

  /// Path under `assets/`, the prefix audioplayers' AudioCache adds itself.
  String get asset => 'audio/sfx/$name.wav';
}

/// Whether an interface sound may play right now.
///
/// Pure on purpose: the rules are the part worth testing, and testing them
/// should not need a speaker.
abstract final class SoundPolicy {
  static bool allows({
    required bool switchOn,
    required bool childMode,
    required bool screenOff,
  }) =>
      switchOn && !childMode && !screenOff;
}

/// What actually makes the noise. [AudioplayersSfxBackend] in the app; a fake
/// in tests.
abstract interface class SfxBackend {
  /// Load every sound once so the first play is not a file read.
  Future<void> preload(List<Sfx> sounds);

  /// Play one sound from the start, cutting any earlier play of the same one.
  Future<void> play(Sfx sound);
}

abstract final class SoundFx {
  static SfxBackend? _backend;
  static Future<void>? _initializing;

  /// The Settings switch, mirrored here by [Haptics]. Defaults to on, like
  /// haptics, until the saved preference says otherwise.
  static bool switchOn = true;

  /// Whether the child surface is open. Set by the app root from
  /// `childModeProvider`.
  static bool childMode = false;

  static int _screenOffHolds = 0;

  /// Whether a screen-off listening session is open.
  static bool get screenOff => _screenOffHolds > 0;

  /// The screen-off player opened. Counted, not toggled, so a second player
  /// stacked on the first cannot unmute the app by closing.
  static void screenOffBegan() => _screenOffHolds++;

  /// The screen-off player closed.
  static void screenOffEnded() {
    if (_screenOffHolds > 0) _screenOffHolds--;
  }

  /// Whether a sound would play right now.
  static bool get allowed => SoundPolicy.allows(
        switchOn: switchOn,
        childMode: childMode,
        screenOff: screenOff,
      );

  /// Load the sounds. Called once from `main`, unawaited; safe to call again.
  ///
  /// Android only for now. On iOS audioplayers drives the one shared
  /// AVAudioSession — it sets the category app-wide and deactivates the
  /// session when its own players stop, which would stop a recitation playing
  /// through just_audio. The app does not ship on iOS today; when it does,
  /// that needs its own answer rather than this one by default.
  static Future<void> init({SfxBackend? backend}) =>
      _initializing ??= _init(backend);

  static Future<void> _init(SfxBackend? backend) async {
    final chosen = backend ??
        (!kIsWeb && defaultTargetPlatform == TargetPlatform.android
            ? AudioplayersSfxBackend()
            : null);
    if (chosen == null) return;
    // In place before the loading finishes: a sound that is ready plays, one
    // that is not yet is skipped by the backend — no waiting on the slowest.
    _backend = chosen;
    try {
      await chosen.preload(Sfx.values);
    } catch (_) {
      // No sounds is a fine way for this app to be.
      if (identical(_backend, chosen)) _backend = null;
    }
  }

  static Future<void> tap() => _play(Sfx.tap);
  static Future<void> select() => _play(Sfx.select);
  static Future<void> success() => _play(Sfx.success);
  static Future<void> lantern() => _play(Sfx.lantern);
  static Future<void> page() => _play(Sfx.page);

  static Future<void> _play(Sfx sound) async {
    final backend = _backend;
    if (backend == null || !allowed) return;
    try {
      await backend.play(sound);
    } catch (_) {
      // A dropped tick is not worth an error.
    }
  }

  /// Back to the state before [init]: no backend, switch on, nothing muted.
  @visibleForTesting
  static void debugReset() {
    _backend = null;
    _initializing = null;
    switchOn = true;
    childMode = false;
    _screenOffHolds = 0;
  }
}

/// One low-latency player per sound, each loaded once.
class AudioplayersSfxBackend implements SfxBackend {
  final Map<Sfx, AudioPlayer> _players = {};

  /// No focus, sonification usage: mix over whatever is playing, never pause
  /// or duck it. Android maps this usage to the system-sounds stream, so the
  /// ticks also follow the system volume and silent mode rather than the
  /// media volume a recitation uses.
  static final AudioContext audioContext = AudioContext(
    android: const AudioContextAndroid(
      isSpeakerphoneOn: false,
      stayAwake: false,
      contentType: AndroidContentType.sonification,
      usageType: AndroidUsageType.assistanceSonification,
      audioFocus: AndroidAudioFocus.none,
    ),
  );

  @override
  Future<void> preload(List<Sfx> sounds) async {
    await Future.wait(sounds.map(_load));
    if (_players.isEmpty) throw StateError('no sound effect loaded');
  }

  Future<void> _load(Sfx sound) async {
    try {
      final player = AudioPlayer(playerId: 'sfx_${sound.name}')
        // SoundPool reports no completion, so the default frame-driven
        // position poll would ask for a position every frame for ever.
        ..positionUpdater = null;
      await player.setAudioContext(audioContext);
      await player.setPlayerMode(PlayerMode.lowLatency);
      await player.setReleaseMode(ReleaseMode.stop);
      await player.setSource(AssetSource(sound.asset));
      _players[sound] = player;
    } catch (_) {
      // This one stays silent; the others still load.
    }
  }

  @override
  Future<void> play(Sfx sound) async {
    final player = _players[sound];
    if (player == null) return;
    // SoundPool never reports a sound as finished, so the player still
    // thinks it is playing and a bare resume() would be ignored. stop()
    // rewinds; resume() starts a fresh stream.
    await player.stop();
    await player.resume();
  }
}
