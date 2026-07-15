/// Push service — Phase 1.1 re-engagement loop.
///
/// Requests notification permission, gets the FCM token, and uploads it to
/// the backend so the server can send re-engagement pushes (streak at risk,
/// new content, win-back). Best-effort and never throws.
library;

import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../../api/tg_client.dart';
import '../../core/analytics.dart';

class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  Future<void> registerToken() async {
    try {
      // Register the top-level background handler BEFORE any other FCM call.
      // This is required for data messages to wake the app while terminated.
      FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

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

      // Handle notification taps (terminated / background).
      FirebaseMessaging.instance.getInitialMessage().then(_handleTap);
      FirebaseMessaging.onMessageOpenedApp.listen(_handleTap);

      // Listen to token refreshes and keep the backend in sync.
      _messaging.onTokenRefresh.listen(
        (newToken) async {
          try {
            await TgClient().ensureSession();
            await TgClient().registerPushToken(newToken, platform: 'android');
          } catch (_) {
            // best-effort
          }
        },
        onError: (_) { /* ignore */ },
      );
    } catch (_) {
      // FCM not available on this device/build — ignore silently.
    }
  }

  /// Route notification taps to the deep-link handler if the payload
  /// contains a `link` field (e.g., `/go?tab=routine`).
  Future<void> _handleTap(RemoteMessage? message) async {
    if (message == null) return;
    final link = message.data['link'] as String?;
    if (link == null || link.isEmpty) return;
    // Best-effort: analytics + deep-link dispatch.
    try {
      await Analytics.pushTapped(message.data['type'] ?? 'unknown');
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
