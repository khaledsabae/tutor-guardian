/// The one classification this change hangs on.
///
/// The permission ask now retries — but only when the platform said "there is
/// no Activity yet", never when the user said no. Get that wrong in the
/// permissive direction and the app re-prompts a parent who already refused,
/// which is how an app gets its notifications switched off at the OS level and
/// never asked again.
///
/// The strings come from firebase_messaging's Android plugin. They are matched
/// as substrings because the plugin wraps them in a `[firebase_messaging/…]`
/// prefix that is not part of the message body.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/push/push_service.dart';

void main() {
  const transient = [
    'Unable to detect current Android Activity.',
    '[firebase_messaging/unknown] Unable to detect current Android Activity.',
    'A request for permissions is already running, please wait for it to '
        'finish before doing another request.',
  ];

  // Everything here is either an answer or a fault that retrying cannot fix.
  const notTransient = [
    null,
    '',
    'PERMISSION_DENIED',
    'The user denied the notification permission',
    'Default FirebaseApp is not initialized in this process',
    'Missing google_app_id. Firebase Analytics disabled.',
    'java.lang.NullPointerException',
  ];

  test('platform "not yet" messages are retried', () {
    for (final m in transient) {
      expect(PushService.isTransientPermissionError(m), isTrue, reason: m);
    }
  });

  test('anything else is taken as final', () {
    for (final m in notTransient) {
      expect(PushService.isTransientPermissionError(m), isFalse,
          reason: m ?? 'null');
    }
  });

  test('a denial is never mistaken for a missing Activity', () {
    // Stated on its own because it is the failure that matters: retrying this
    // would re-prompt someone who already answered.
    expect(
      PushService.isTransientPermissionError(
          'The user denied the notification permission'),
      isFalse,
    );
    expect(PushService.isTransientPermissionError('denied'), isFalse);
  });

  test('the exact string the emulator produced is matched', () {
    // Copied verbatim from logcat on a Pixel6 emulator, first launch:
    //   TGDIAG fcm requestPermission threw: [firebase_messaging/unknown]
    //   Unable to detect current Android Activity.
    expect(
      PushService.isTransientPermissionError(
          '[firebase_messaging/unknown] Unable to detect current Android '
          'Activity.'),
      isTrue,
    );
  });
}
