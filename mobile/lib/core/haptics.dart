/// Semantic haptics — call sites say *what happened*, not which motor pulse.
///
/// Haptics were ten direct `HapticFeedback.*` calls in six files (games,
/// tasbeeh, the tab bar), and none on the actions a parent or child repeats
/// every day. Every call now goes through here, so the "Haptic feedback"
/// switch in Settings (UX_UI_ROADMAP E5) silences all of them at once.
///
/// The map (UX_UI_ROADMAP §4.2): selection for a tab, chip or send; success
/// for a habit logged, a lesson completed, a mission confirmed, a milestone;
/// warning for a failed action or a wrong PIN; never on scroll, keystrokes or
/// streaming tokens.
///
/// Sound rides on the same helpers (core/sound_fx.dart), so every place that
/// already buzzes for a choice or an achievement also gets its soft sound,
/// and the one switch governs both: selection → a tiny tick, success → a
/// water drop. warning and strong stay silent — a wrong answer or a wrong PIN
/// gets a buzz, not a noise. The helpers are only called from what a person
/// does; a pulse that fires on its own (the daily gift landing on Home)
/// passes `sound: false`.
library;

import 'dart:async';

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'sound_fx.dart';

abstract final class Haptics {
  static const _prefKey = 'haptics_enabled';

  static bool _enabled = true;

  /// Whether haptics are on. Defaults to on until [load] says otherwise.
  static bool get enabled => _enabled;

  /// Read the saved preference. Called once at startup; a failure leaves the
  /// default, because a missing preference store is not a reason to go quiet.
  static Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _enabled = prefs.getBool(_prefKey) ?? true;
    } catch (_) {}
    SoundFx.switchOn = _enabled;
  }

  /// The one switch: vibration and sound together («الأصوات والاهتزاز»).
  static Future<void> setEnabled(bool value) async {
    _enabled = value;
    SoundFx.switchOn = value;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKey, value);
    } catch (_) {}
  }

  static Future<void> _run(
    Future<void> Function() pulse, [
    Future<void> Function()? sound,
  ]) {
    if (!_enabled) return Future.value();
    // Never awaited: the sound must not hold up the pulse or the caller, and
    // SoundFx swallows its own failures.
    if (sound != null) unawaited(sound());
    return pulse();
  }

  /// A choice was made: a tab, a chip, a message sent.
  /// [sound] false keeps the vibration and drops the tick — for surfaces
  /// that should stay quiet, like the tasbeeh counter (dhikr is not a game).
  static Future<void> selection({bool sound = true}) =>
      _run(HapticFeedback.selectionClick, sound ? SoundFx.select : null);

  /// Something was saved or earned: a habit logged, a lesson completed.
  ///
  /// [sound] false keeps the pulse and drops the water drop — for a moment
  /// the app arrives at by itself, like the daily gift landing on Home.
  static Future<void> success({bool sound = true}) => _run(
        HapticFeedback.lightImpact,
        sound ? SoundFx.success : null,
      );

  /// The action did not go through and needs attention.
  static Future<void> warning() => _run(HapticFeedback.mediumImpact);

  /// A deliberate, rare emphasis: a tasbeeh round complete, a game error.
  static Future<void> strong() => _run(HapticFeedback.heavyImpact);
}
