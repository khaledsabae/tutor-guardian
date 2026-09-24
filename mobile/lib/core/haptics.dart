/// Semantic haptics — call sites say *what happened*, not which motor pulse.
///
/// Haptics were ten direct `HapticFeedback.*` calls in six files (games,
/// tasbeeh, the tab bar), and none on the actions a parent or child repeats
/// every day. Routing new calls through here keeps one vocabulary and gives a
/// single place to honour a future "reduce haptics" setting (UX_UI_ROADMAP.md).
library;

import 'package:flutter/services.dart';

abstract final class Haptics {
  /// A choice was made: a tab, a chip, a message sent.
  static Future<void> selection() => HapticFeedback.selectionClick();

  /// Something was saved or earned: a habit logged, a lesson completed.
  static Future<void> success() => HapticFeedback.lightImpact();

  /// The action did not go through and needs attention.
  static Future<void> warning() => HapticFeedback.mediumImpact();
}
