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
import 'notification_channels.dart';

/// FCM requires the background handler to be a TOP-LEVEL entry-point
/// function (it runs in a separate isolate while the app is terminated).
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
}

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  Future<void> registerToken() async {
    try {
      // Belt and braces: main() already does this on a path with no network
      // in it, and a repeat create is a no-op that preserves whatever the
      // user has configured. Kept here so a future refactor that drops one
      // call site does not silently take the channels with it.
      await ensureNotificationChannels();

      // Register the top-level background handler BEFORE any other FCM call.
      // This is required for data messages to wake the app while terminated.
      FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

      // Android defaults to authorized; iOS requires explicit permission.
      // For Android we still call it safely.
      final settings = await _messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );
      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        await Analytics.pushPermission(false);
        return;
      }
      await Analytics.pushPermission(true);

      String? token;
      if (defaultTargetPlatform == TargetPlatform.android) {
        token = await _messaging.getToken();
      } else {
        token = await _messaging.getAPNSToken();
        token ??= await _messaging.getToken();
      }
      if (token == null || token.isEmpty) return;

      await TgClient().ensureSession();
      await TgClient().registerPushToken(token, platform: 'android');
      await Analytics.pushTokenRegistered();

      // Listen to token refreshes and keep the backend in sync.
      _messaging.onTokenRefresh.listen(
        (newToken) async {
          try {
            await TgClient().ensureSession();
            await TgClient().registerPushToken(newToken, platform: 'android');
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
    FirebaseMessaging.onMessage.listen((message) {
      Analytics.pushReceived(message.data['type'] ?? 'unknown');
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
