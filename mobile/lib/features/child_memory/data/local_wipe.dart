/// Clearing the phone after its account was deleted (MOBILE_API §10).
///
/// The server has erased the account; this erases what the phone kept:
/// cached children and preferences, the chat copy, voice recordings and
/// exports in the app's documents, the cache (which also holds the device-id
/// claim of the device-twin fix), scheduled reminders, the Google sign-in and
/// the push token. The device id and the session were already replaced
/// (`TgClient.startOverAfterAccountDeletion`) the moment the server answered,
/// before anything else could run. Last, Android is told the app's data
/// changed, so the next Auto Backup replaces the copy that still holds the
/// deleted account.
///
/// Every step is best-effort and independent: one that fails (a plugin
/// missing on this phone) must not keep the others from running.
library;

import 'dart:io';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../api/tg_client.dart'
    show kAccountDeletionErasedIdKey, kAccountDeletionKey;
import '../../../core/app_closer.dart' show notifyBackupDataChanged;
import '../../adhkar/services/notification_service.dart';
import '../../identity/identity_service.dart';

/// Preferences that survive: they say nothing about the family and keep the
/// fresh start usable — the language and theme the parent chose, the update
/// gate, the brand-new device id's backup, and the install's one-shot analytics
/// markers (they name no one, and resetting them would count this phone as a
/// brand-new install in every funnel).
///
/// The deletion record ([kAccountDeletionKey], with the id it erased) is kept
/// through the clear and removed as the wipe's LAST step: a wipe cut short
/// (the app killed in the middle) is finished by the next launch, not
/// forgotten.
@visibleForTesting
const Set<String> keptPreferenceKeys = {
  'tg.ui_language',
  'tg.theme_mode',
  'cached_minimum_build_number',
  'tg_device_id_backup',
  kAccountDeletionKey,
  kAccountDeletionErasedIdKey,
};

@visibleForTesting
const List<String> keptPreferencePrefixes = ['tg.analytics.once.'];

/// Remove from [prefs] every key but [keptPreferenceKeys] /
/// [keptPreferencePrefixes] — one by one. Not `clear()` and then writing the
/// kept ones back: killed in between, that would lose the deletion record,
/// and with it the next launch's chance to finish this wipe.
@visibleForTesting
Future<void> clearPreferencesForFreshStart(SharedPreferences prefs) async {
  for (final key in prefs.getKeys().toList()) {
    final kept = keptPreferenceKeys.contains(key) ||
        keptPreferencePrefixes.any(key.startsWith);
    if (!kept) await prefs.remove(key);
  }
}

/// Delete what is inside [dir], not [dir] itself.
@visibleForTesting
Future<void> emptyDirectory(Directory dir) async {
  if (!await dir.exists()) return;
  await for (final entity in dir.list(followLinks: false)) {
    try {
      await entity.delete(recursive: true);
    } catch (_) {
      // In use or already gone: the rest still goes.
    }
  }
}

Future<void> _step(Future<void> Function() step) async {
  try {
    await step();
  } catch (_) {}
}

Future<void>? _wiping;

/// Clear the phone after the server deleted the account. Callers that arrive
/// together (the deletion screen, a `410 device_erased`) share one run.
Future<void> wipeLocalDataAfterAccountDeletion() =>
    _wiping ??= _wipe().whenComplete(() => _wiping = null);

Future<void> _wipe() async {
  await _step(() => NotificationService.instance.cancelAll());
  await _step(() => IdentityService.instance.signOutAfterAccountDeletion());
  await _step(() async =>
      clearPreferencesForFreshStart(await SharedPreferences.getInstance()));
  final seen = <String>{};
  for (final dir in [
    getApplicationDocumentsDirectory,
    getApplicationCacheDirectory,
    getTemporaryDirectory,
  ]) {
    await _step(() async {
      final d = await dir();
      if (seen.add(d.path)) await emptyDirectory(d);
    });
  }
  // A new token on the next launch: nothing left that the deleted account's
  // push rows (already erased on the server) could be matched against.
  await _step(() => FirebaseMessaging.instance.deleteToken());
  // Last: the deletion is complete on this phone too.
  await _step(() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(kAccountDeletionErasedIdKey);
    await prefs.remove(kAccountDeletionKey);
  });
  // The phone's Auto Backup still holds the deleted account (its device id,
  // cached children, the chat copy): ask for a new one of what is left.
  await _step(notifyBackupDataChanged);
}
