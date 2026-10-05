/// Ending the app so that the next open is a fresh launch — and telling
/// Android's backup that the app's data changed.
///
/// Used once: after an account deletion (MOBILE_API §10), when everything on
/// the phone was cleared and nothing of the deleted account may survive in
/// memory. `SystemNavigator.pop()` is not that: on Android 12+ Back on a root
/// task only moves it to the back (PR #36 review, item 1) — the engine and
/// its Dart isolate live on, and reopening shows the same screens with the
/// same in-memory state. `MainActivity.finishAndRemoveTask()` destroys the
/// activity and the engine it created, so the next open runs `main()` anew.
library;

import 'dart:io' show exit;

import 'package:flutter/services.dart';

/// Must match `APP_CHANNEL` in android/app/src/main/kotlin/…/MainActivity.kt.
const MethodChannel appChannel = MethodChannel('almorabbi/app');

/// Close the app for a fresh start. When the native side cannot (iOS, a build
/// without the channel, an error), the process exits instead — the one other
/// way to be sure no Dart state survives.
Future<void> closeAppForFreshStart({
  MethodChannel channel = appChannel,
  void Function(int code) exitProcess = exit,
  Duration timeout = const Duration(seconds: 3),
}) async {
  try {
    // Bounded: a reply that never comes must not leave the parent on a page
    // whose only button does nothing.
    final done = await channel
        .invokeMethod<bool>('finishAndRemoveTask')
        .timeout(timeout);
    if (done == true) return;
  } catch (_) {
    // Fall through to the exit below.
  }
  exitProcess(0);
}

/// Ask Android for a new backup of the app's data (`BackupManager
/// .dataChanged()`), after the phone was cleared of a deleted account: the
/// copy in the parent's Google Drive still holds it, and a restore would
/// bring its device id, cached children and chat copy back. Best effort, and
/// bounded — iOS and builds without the channel do nothing.
Future<void> notifyBackupDataChanged({
  MethodChannel channel = appChannel,
  Duration timeout = const Duration(seconds: 3),
}) async {
  try {
    await channel.invokeMethod<bool>('backupDataChanged').timeout(timeout);
  } catch (_) {}
}
