import 'package:wakelock_plus/wakelock_plus.dart';

/// Keeps the device awake while a story or the bedtime adhkar is open, then
/// lets it sleep again.
///
/// This file used to hold `BedtimeAudioService` too — a looping «nature
/// ambient» track (3 MB) started under every story at 45% volume and only
/// dimmed, never stopped, on the way out, so it kept playing on the shelf.
/// Khaled's standing rule is no music and no ambient bed under the app's
/// content; the only sound a story makes now is a soft paper turn
/// (`SoundFx.page`). Removed 2026-10 with the track itself.
class StoryWakeLock {
  // A screen that cannot hold the wake lock (no plugin: tests, a platform
  // without it) still reads; the failure must not escape as an unhandled
  // async error from initState/dispose, which call these unawaited.
  static Future<void> keepAwake() async {
    try {
      await WakelockPlus.enable();
    } catch (_) {}
  }

  static Future<void> allowSleep() async {
    try {
      await WakelockPlus.disable();
    } catch (_) {}
  }
}
