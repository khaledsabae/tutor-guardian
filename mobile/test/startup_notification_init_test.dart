// Play vitals: 9.35% slow cold starts. Notification setup (the time-zone
// database, the plugin, 14 days of reminders) moved from before `runApp` to
// after the first frame, so its callers can now race it. init() is therefore
// one shared run: concurrent callers wait on the same work, and a failed run
// does not stick — the next call tries again.

import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/adhkar/services/notification_service.dart';

const _channel = MethodChannel('dexterous.com/flutter/local_notifications');
const _timezone = MethodChannel('flutter_timezone');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // The host VM is not Android; register the Android side the app runs on.
  AndroidFlutterLocalNotificationsPlugin.registerWith();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('concurrent callers share one run, and a failure is retried', () async {
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    var initializeCalls = 0;
    var failNext = true;
    messenger.setMockMethodCallHandler(_channel, (call) async {
      if (call.method == 'initialize') {
        initializeCalls++;
        if (failNext) {
          failNext = false;
          throw PlatformException(code: 'boom');
        }
        return true;
      }
      return null;
    });
    messenger.setMockMethodCallHandler(_timezone, (_) async => 'Africa/Cairo');
    addTearDown(() {
      messenger.setMockMethodCallHandler(_channel, null);
      messenger.setMockMethodCallHandler(_timezone, null);
    });

    final service = NotificationService.instance;
    final a = service.init();
    final b = service.init();
    expect(identical(a, b), isTrue);
    await expectLater(a, throwsA(isA<PlatformException>()));
    expect(initializeCalls, 1);

    // The failed run was dropped, so this is a fresh attempt, not the old error.
    await service.init();
    expect(initializeCalls, 2);
    // …and once it has succeeded, it is done.
    await service.init();
    expect(initializeCalls, 2);
  });
}
