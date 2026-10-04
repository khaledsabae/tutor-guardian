/// Push service — Phase 1.1 re-engagement loop.
///
/// Requests notification permission, gets the FCM token, and uploads it to
/// the backend so the server can send re-engagement pushes (streak at risk,
/// new content, win-back). Best-effort and never throws.
library;

import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';

import '../../api/tg_client.dart';
import '../../core/analytics.dart';
import '../../firebase_options.dart';
import '../deeplink/deep_link_handler.dart';
import '../child_memory/device_proof/device_proof_service.dart';
import 'notification_channels.dart';

/// FCM requires the background handler to be a TOP-LEVEL entry-point
/// function (it runs in a separate isolate while the app is terminated).
///
/// That isolate is FCM's, not the app's. A device-proof code is handed to the
/// app's own isolate and nothing else happens here: no session, no keystore,
/// no token registration, no second `main()` — the device-twin bug of PR #29
/// was exactly a second isolate doing the app's startup.
/// (test/device_proof_test.dart pins what this body may call.)
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  if (forwardDeviceProofFromBackground(message.data)) return;
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
}

/// FCM `data.type` of the one-off security notice sent to a phone whose push
/// token was replaced (MOBILE_API §9.0.1).
const String kAccountAlertType = 'account_alert';

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  /// Ask for POST_NOTIFICATIONS. Returns whether the app may notify.
  ///
  /// Split out of [registerToken] because that whole method sits behind
  /// `ensureSession()`, which returns early when the network is down — so a
  /// device whose *first* launch was offline was never asked for notification
  /// permission at all. It has fourteen days of reminders scheduled and no
  /// permission to show any of them, and nothing asks again on a later launch
  /// because the ask lived inside the token registration it never reached.
  ///
  /// This is the only prompt the app raises: POST_NOTIFICATIONS is one OS
  /// permission covering push and local reminders alike, and asking twice is
  /// asking a parent the same question twice.
  /// In-flight request, shared by every caller.
  ///
  /// Two call sites race on a cold start — the post-frame ask in `main()` and
  /// [registerToken] — and the platform answers the second one with
  /// «A request for permissions is already running», which is not a denial but
  /// was being read as one. One future, awaited by both.
  Future<bool>? _permissionRequest;

  /// Ask for POST_NOTIFICATIONS, waiting for an Activity if there is not one yet.
  ///
  /// The Activity is the whole problem. Measured on an emulator: the ask fires
  /// from the post-frame callback at t+0.0s and throws «Unable to detect
  /// current Android Activity»; the plugin fallback throws a NullPointerException
  /// for the same reason; and the Activity becomes available about 1.4s later.
  /// The prompt only ever appeared because [registerToken] happens to ask
  /// again — and that path sits behind `ensureSession()`, so a first launch
  /// without network asked nobody at all while fourteen days of reminders sat
  /// queued and unshowable.
  ///
  /// So: retry, but only on that one condition. A denial is an answer and must
  /// never be retried — re-prompting a parent who said no is how an app gets
  /// its notifications switched off at the OS level.
  Future<bool> requestNotificationPermission() {
    return _permissionRequest ??= _requestNotificationPermission()
      ..whenComplete(() => _permissionRequest = null);
  }

  /// True when [message] is the platform saying "not yet", not the user saying no.
  ///
  /// The distinction is the safety property of this whole change: a denial that
  /// were misread as transient would re-prompt a parent who already said no.
  @visibleForTesting
  static bool isTransientPermissionError(String? message) {
    if (message == null) return false;
    return message.contains('Unable to detect current Android Activity') ||
        message.contains('A request for permissions is already running');
  }

  /// Backoff between attempts. Totals ~7s, which covers the ~1.4s measured on
  /// an emulator with a wide margin for a cold start on a slow device, and
  /// still gives up rather than looping for the life of the process.
  static const _permissionRetryDelays = <Duration>[
    Duration(milliseconds: 400),
    Duration(milliseconds: 800),
    Duration(seconds: 1),
    Duration(seconds: 2),
    Duration(seconds: 3),
  ];

  Future<bool> _requestNotificationPermission() async {
    for (var attempt = 0;; attempt++) {
      try {
        final settings = await _messaging.requestPermission(
          alert: true,
          badge: true,
          sound: true,
          provisional: false,
        );
        // `notDetermined` is not consent. The previous test was
        // `!= denied`, which counted "we never got an answer" as a yes and
        // returned true to `main()` — so the fallback ask never ran either.
        final granted =
            settings.authorizationStatus == AuthorizationStatus.authorized ||
                settings.authorizationStatus == AuthorizationStatus.provisional;
        unawaited(Analytics.pushPermission(granted));
        return granted;
      } on FirebaseException catch (e) {
        if (isTransientPermissionError(e.message) &&
            attempt < _permissionRetryDelays.length) {
          await Future<void>.delayed(_permissionRetryDelays[attempt]);
          continue;
        }
        return false;
      } catch (_) {
        // No Play Services, no Firebase, no answer. The caller falls back to
        // the plugin's own request rather than treating this as a denial.
        return false;
      }
    }
  }

  /// The registration in flight, shared by every caller (launch, a
  /// `no_push_token` answer to a device proof, an `account_alert`).
  Future<void>? _registering;
  StreamSubscription<String>? _refreshSub;
  StreamSubscription<RemoteMessage>? _foregroundSub;

  /// Upload this phone's FCM token (with the build census) to the server.
  ///
  /// On EVERY launch, and whether or not the parent allowed notifications
  /// (MOBILE_API §9.0.1). This used to stop when permission was refused, so a
  /// family that declined notifications had no token and no build number on
  /// the server: the silent device-proof code had nowhere to go — memory,
  /// follow-ups and in-app deletion could never open for them — and the
  /// server's CHILD_MEMORY_MIN_BUILD census never saw their build. A data
  /// message needs no notification permission; refusing notifications still
  /// means no notification is ever shown.
  Future<void> registerToken() {
    final running = _registering;
    if (running != null) return running;
    final run = _registerToken();
    _registering = run;
    run.whenComplete(() {
      if (identical(_registering, run)) _registering = null;
    });
    return run;
  }

  Future<void> _registerToken() async {
    try {
      // Belt and braces: main() already does this on a path with no network
      // in it, and a repeat create is a no-op that preserves whatever the
      // user has configured. Kept here so a future refactor that drops one
      // call site does not silently take the channels with it.
      await ensureNotificationChannels();

      // Register the top-level background handler BEFORE any other FCM call.
      // This is required for data messages to wake the app while terminated.
      FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

      await registerWith(
        // Android defaults to authorized; iOS requires explicit permission.
        // Usually a no-op by now — main() asks after the first frame.
        askPermission: requestNotificationPermission,
        fetchToken: () async {
          if (defaultTargetPlatform == TargetPlatform.android) {
            return _messaging.getToken();
          }
          return await _messaging.getAPNSToken() ?? await _messaging.getToken();
        },
        upload: (token) async {
          await TgClient.shared.ensureSession();
          await TgClient.shared.registerPushToken(token, platform: 'android');
          await Analytics.pushTokenRegistered();
        },
      );

      // Listen to token refreshes and keep the backend in sync — once.
      _refreshSub ??= _messaging.onTokenRefresh.listen(
        (newToken) async {
          try {
            await TgClient.shared.ensureSession();
            await TgClient.shared.registerPushToken(newToken, platform: 'android');
            // A proof belongs to one push token: the new one needs its own
            // (§9.0.1), or answers go without memory until a screen asks.
            unawaited(DeviceProofService.instance.proveIfUseful());
          } catch (e, s) {
            // Not fatal, but not harmless either: the device keeps running with
            // a token the backend no longer knows, so every future reminder
            // silently goes nowhere. Swallowing this made it invisible.
            await FirebaseCrashlytics.instance.recordError(
              e, s,
              reason: 'push token refresh not registered',
              fatal: false,
            );
          }
        },
        onError: (_) { /* ignore */ },
      );
    } catch (_) {
      // FCM not available on this device/build — ignore silently.
    }
  }

  /// The registration's decision, without Firebase: the permission is asked
  /// (and its answer recorded by [requestNotificationPermission]), but it does
  /// not gate the upload. Returns the token uploaded, or null.
  @visibleForTesting
  static Future<String?> registerWith({
    required Future<bool> Function() askPermission,
    required Future<String?> Function() fetchToken,
    required Future<void> Function(String token) upload,
  }) async {
    await askPermission();
    final token = await fetchToken();
    if (token == null || token.isEmpty) return null;
    await upload(token);
    return token;
  }

  /// Wire the device proof (MOBILE_API §9.0.1) to FCM: foreground data
  /// messages reach the proof service here (the background isolate reaches
  /// it through its port), and a `no_push_token` answer re-registers.
  /// Needs no session, so `main()` calls it unconditionally.
  void listenDeviceProof() {
    final proof = DeviceProofService.instance
      ..reRegisterPushToken = registerToken;
    // The background inbox and the client's proof hook first, on their own:
    // they need no Firebase call, and must not be lost if the next one fails.
    try {
      proof.init();
    } catch (_) {}
    try {
      proof.init(
        foregroundMessages: FirebaseMessaging.onMessage.map((m) => m.data),
      );
    } catch (_) {
      // FCM not available on this device/build — no code can arrive.
    }
  }

  /// The security notice (`account_alert`) was received or tapped: this phone
  /// held the account's push token before another phone took it. Registering
  /// this phone's own token again takes the device back at once when this
  /// phone had proven it (§9.0.1) — a warm start would otherwise not
  /// re-register until the next cold launch.
  void _onAccountAlert() => unawaited(registerToken());

  /// Start listening for notification taps.
  ///
  /// Deliberately separate from [registerToken] and called unconditionally
  /// from `main()`. It used to live at the end of that method, behind
  /// `requestPermission`, `ensureSession` and `registerPushToken` — and
  /// `_postLaunchGrowthLoop` skips the whole call when `ensureSession`
  /// throws. So a cold start from a notification tap with no connectivity
  /// lost the navigation entirely: the user tapped, the app opened at home,
  /// and nothing explained why. Tap handling needs no session and no token.
  Future<void> listenTaps() async {
    try {
      FirebaseMessaging.instance.getInitialMessage().then(_handleTap);
      FirebaseMessaging.onMessageOpenedApp.listen(_handleTap);
    } catch (_) {
      // FCM not available on this device/build — ignore silently.
    }
  }

  /// Route notification taps to the deep-link handler.
  ///
  /// `link` is the contract; `route` is accepted only because the cron sent
  /// that key until 2026-08-11 and notifications already queued on devices
  /// still carry it. Drop the fallback once those have aged out.
  Future<void> _handleTap(RemoteMessage? message) async {
    if (message == null) return;
    final type = message.data['type'] ?? 'unknown';

    // Logged before the early return below. When this sat after it, a payload
    // the client could not route registered as no tap at all — which is how
    // 29,194 delivered notifications came to show 810 opens and a tap-through
    // rate that looked like apathy rather than a broken wire.
    try {
      await Analytics.pushTapped(type);
    } catch (_) {
      // ignore
    }

    if (type == kAccountAlertType) _onAccountAlert();

    final link = (message.data['link'] ?? message.data['route']) as String?;
    if (link == null || link.isEmpty) return;
    try {
      await DeepLinkHandler.instance.dispatch(link);
    } catch (_) {
      // ignore
    }
  }

  /// Listen to foreground messages so we can update badge or route the user.
  Future<void> listenForeground() async {
    _foregroundSub ??= FirebaseMessaging.onMessage.listen((message) {
      final type = message.data['type'] ?? 'unknown';
      // A device-proof code is a silent handshake, not a push a parent sees
      // (listenDeviceProof handles it); counting it would inflate push_received.
      if (type == kDeviceProofMessageType) return;
      Analytics.pushReceived(type);
      if (type == kAccountAlertType) _onAccountAlert();
      // UI decisions are left to whichever screen is visible.
    });
  }

  /// For foreground presentation customization (optional).
  Future<void> configureForeground() async {
    try {
      await FirebaseMessaging.instance.setForegroundNotificationPresentationOptions(
        alert: true,
        badge: true,
        sound: true,
      );
    } catch (_) {
      // best-effort
    }
  }
}
