/// Clearing the phone after its account was deleted (MOBILE_API §10).
///
/// The server has erased the account; this erases what the phone kept:
/// cached children and preferences, the chat copy, voice recordings and
/// exports in the app's documents, the cache (which also holds the device-id
/// claim of the device-twin fix), scheduled reminders, the Google sign-in and
/// the push token. The device id and the session were already replaced by
/// `TgClient.deleteAccount` the moment the server answered, before anything
/// else could run.
///
/// Every step is best-effort and independent: one that fails (a plugin
/// missing on this phone) must not keep the others from running.
library;

import 'dart:io';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../adhkar/services/notification_service.dart';
import '../../identity/identity_service.dart';

/// Preferences that survive: they say nothing about the family and keep the
/// fresh start usable — the language and theme the parent chose, the update
/// gate, the brand-new device id's backup, and the install's one-shot analytics
/// markers (they name no one, and resetting them would count this phone as a
/// brand-new install in every funnel).
@visibleForTesting
const Set<String> keptPreferenceKeys = {
  'tg.ui_language',
  'tg.theme_mode',
  'cached_minimum_build_number',
  'tg_device_id_backup',
};

@visibleForTesting
const List<String> keptPreferencePrefixes = ['tg.analytics.once.'];

/// Clear [prefs] except [keptPreferenceKeys] / [keptPreferencePrefixes].
@visibleForTesting
Future<void> clearPreferencesForFreshStart(SharedPreferences prefs) async {
  final keep = <String, Object>{};
  for (final key in prefs.getKeys()) {
    final kept = keptPreferenceKeys.contains(key) ||
        keptPreferencePrefixes.any(key.startsWith);
    final value = prefs.get(key);
    if (kept && value != null) keep[key] = value;
  }
  await prefs.clear();
  for (final e in keep.entries) {
    final v = e.value;
    if (v is String) {
      await prefs.setString(e.key, v);
    } else if (v is bool) {
      await prefs.setBool(e.key, v);
    } else if (v is int) {
      await prefs.setInt(e.key, v);
    } else if (v is double) {
      await prefs.setDouble(e.key, v);
    } else if (v is List<String>) {
      await prefs.setStringList(e.key, v);
    }
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

/// Clear the phone after the server deleted the account.
Future<void> wipeLocalDataAfterAccountDeletion() async {
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
}
