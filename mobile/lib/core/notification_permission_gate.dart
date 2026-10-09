/// One-shot notification permission ask, moved off the launch path to the
/// moment it can be answered "yes" to: right after the FIRST completed
/// lesson (NOOR_WAL_QANADIL_PLAN, Phase 1).
///
/// Asking at launch was a cold permission: nothing had been seen, nothing
/// was at stake, and one deny at the door meant the daily reminders never
/// existed. After a finished lesson the parent has a reason.
///
/// Wiring: [Analytics.lessonCompleted] — the event the lesson flow already
/// emits — calls [maybeAsk], so `lesson_screen.dart` needs no edit. The
/// platform ask itself is injected in `main()` (the composition root),
/// keeping this file free of service imports and directly testable.
///
/// The flag is set BEFORE asking: one moment, one ask — a device that
/// denies is never nagged again (Android 13+ would silently drop the
/// request anyway).
library;

import 'package:shared_preferences/shared_preferences.dart';

abstract final class NotificationPermissionGate {
  static const prefKey = 'tg.notifications.asked_after_first_lesson';

  /// The real platform ask, set once in `main()` (the composition root):
  /// Firebase's request first, the plugin's as the no-Play-Services
  /// fallback — the exact pair the launch path used to run. Null (and
  /// therefore a no-op) in tests, which inject their own.
  static Future<void> Function()? ask;

  /// Called on every lesson completion; does its work exactly once per
  /// install. Never throws — a permission ask must never take the lesson
  /// celebration down with it.
  static Future<void> maybeAsk() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (prefs.getBool(prefKey) == true) return;
      await prefs.setBool(prefKey, true);
      await ask?.call();
    } catch (_) {
      // Best-effort by design.
    }
  }
}
