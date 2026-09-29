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
library;

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
  }

  static Future<void> setEnabled(bool value) async {
    _enabled = value;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefKey, value);
    } catch (_) {}
  }

  static Future<void> _run(Future<void> Function() pulse) =>
      _enabled ? pulse() : Future.value();

  /// A choice was made: a tab, a chip, a message sent.
  static Future<void> selection() => _run(HapticFeedback.selectionClick);

  /// Something was saved or earned: a habit logged, a lesson completed.
  static Future<void> success() => _run(HapticFeedback.lightImpact);

  /// The action did not go through and needs attention.
  static Future<void> warning() => _run(HapticFeedback.mediumImpact);

  /// A deliberate, rare emphasis: a tasbeeh round complete, a game error.
  static Future<void> strong() => _run(HapticFeedback.heavyImpact);
}
