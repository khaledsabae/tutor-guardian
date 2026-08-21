/// The reminder schedule must survive the permission prompt failing.
///
/// Found by running 1.0.51 on an emulator, not by a test — which is the point
/// of writing one now. `NotificationService.init()` runs before `runApp()`, and
/// it used to ask for the Android 13+ runtime permission from there. The plugin
/// resolves that request against the attached Activity, and before the first
/// frame there is none, so the platform side threw:
///
///     NullPointerException: Attempt to invoke virtual method
///     'int android.content.Context.checkPermission(...)' on a null object
///
/// The throw came back through the method channel and out of `init()`, taking
/// `scheduleDaily` with it. Effect on a fresh install: `dumpsys alarm` held
/// **zero** alarms for the package, POST_NOTIFICATIONS was never requested, and
/// the daily adhkar reminder — the app's one recurring reason to come back —
/// simply did not exist. Nothing logged it as a failure.
library;

import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/adhkar/data/family_adhkar.dart';
import 'package:almorabbi/features/adhkar/services/notification_service.dart';

const _channel = MethodChannel('dexterous.com/flutter/local_notifications');

/// Every method the plugin was asked for, in order.
final List<String> calls = <String>[];

/// Set to make the permission request throw the way the Activity-less call did.
bool permissionThrows = false;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    await FamilyAdhkar.load();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_channel, (call) async {
      calls.add(call.method);
      if (call.method == 'requestNotificationsPermission') {
        if (permissionThrows) {
          throw PlatformException(
            code: 'error',
            message: "Attempt to invoke virtual method "
                "'int android.content.Context.checkPermission(java.lang.String, "
                "int, int)' on a null object reference",
          );
        }
        return true;
      }
      if (call.method == 'getNotificationAppLaunchDetails') {
        return <String, dynamic>{'notificationLaunchedApp': false};
      }
      if (call.method == 'pendingNotificationRequests') return <dynamic>[];
      return null;
    });
  });

  // Source, not behaviour, and deliberately so — the same shape as the test
  // that reads `mission_digest` to keep a second send channel from appearing.
  // `init()` cannot run on the host: `_plugin.initialize` resolves the Android
  // implementation, which no registrant has set. So the invariant is pinned
  // where it is legible instead: whatever else `init()` does, it must not ask
  // for the permission, because it runs before `runApp` and there is no
  // Activity to ask through.
  test('init does not ask for the permission', () {
    final source = File(
      'lib/features/adhkar/services/notification_service.dart',
    ).readAsStringSync();
    final init = source.substring(
      source.indexOf('Future<void> init() async {'),
      source.indexOf('/// Cancels every notification id'),
    );

    expect(init.contains('_requestPermission'), isFalse,
        reason: 'init() runs before runApp; asking there threw inside the '
            'plugin and took scheduleDaily down with it');
    expect(init.contains('scheduleDaily'), isTrue,
        reason: 'a fresh install must still queue its reminders');
  });

  // The prompt must not sit behind a network call. `_postLaunchGrowthLoop`
  // returns early when `ensureSession()` throws, so a first launch with no
  // signal reached neither the token registration nor the ask that used to
  // live inside it — leaving fourteen days of reminders scheduled against a
  // permission nobody was ever asked for, with no later launch retrying.
  test('the permission is asked for outside the session-gated loop', () {
    final main = File('lib/main.dart').readAsStringSync();
    final loop = main.substring(main.indexOf('Future<void> _postLaunchGrowthLoop'));

    expect(loop.contains('requestNotificationPermission'), isFalse,
        reason: 'the loop returns early with no session; the ask cannot live '
            'there');
    expect(
      main.substring(0, main.indexOf('Future<void> _postLaunchGrowthLoop'))
          .contains('requestNotificationPermission'),
      isTrue,
      reason: 'something before the loop must still raise the prompt',
    );
  });

  // No Android registrant runs in a host test, so
  // `resolvePlatformSpecificImplementation` throws a LateInitializationError
  // here — a different throw from the device's NullPointerException, at the
  // same call site, which is exactly what the guard has to survive. What this
  // cannot check is the granted/denied answer itself; that needs the device,
  // and it is why 1.0.51 was installed on an emulator before this was written.
  test('a permission request that throws does not escape', () async {
    permissionThrows = true;

    expect(await NotificationService.instance.ensurePermission(), isFalse);
  });

  test('ensurePermission stays quiet when reminders are switched off',
      () async {
    // Asking a user who has turned reminders off for permission to send them is
    // a prompt with nothing behind it.
    SharedPreferences.setMockInitialValues(
        {'tg.adhkar_notifications_enabled': false});
    calls.clear();

    expect(await NotificationService.instance.ensurePermission(), isFalse);
    expect(calls, isEmpty);
  });
}
