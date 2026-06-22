/// Growth analytics — thin wrapper over the (previously declared-but-unwired)
/// firebase_analytics so we can actually measure the Phase 0 funnel and the
/// referral K-factor. Every call is best-effort and never throws.
///
/// Funnel we care about:
///   app_open (auto) → onboarding_done → first_value (milestone/lesson) →
///   share_moment → invite_opened → invite_shared → referral_claimed
library;

import 'package:firebase_analytics/firebase_analytics.dart';

class Analytics {
  static FirebaseAnalytics get _fa => FirebaseAnalytics.instance;

  static Future<void> _log(String name, [Map<String, Object>? params]) async {
    try {
      await _fa.logEvent(name: name, parameters: params);
    } catch (_) {
      // analytics must never affect UX
    }
  }

  /// A shareable moment card was successfully shared. [kind] = milestone /
  /// quran / invite / tip, so we can see which surface drives the loop.
  static Future<void> shareMoment(String kind) =>
      _log('share_moment', {'kind': kind});

  /// The «ادعُ صديقًا» screen was opened.
  static Future<void> inviteOpened() => _log('invite_opened');

  /// The invite was shared from the «ادعُ صديقًا» screen.
  static Future<void> inviteShared() => _log('invite_shared');

  /// A referral code was claimed (this device was referred). [outcome] =
  /// success / already / invalid / error — the bottom of the K-factor funnel.
  static Future<void> referralClaimed(String outcome) =>
      _log('referral_claimed', {'outcome': outcome});

  /// A child-journey milestone was logged — a key "first value" signal.
  static Future<void> milestoneLogged() => _log('milestone_logged');

  /// A Google identity was linked — data now survives reinstall.
  static Future<void> identityLinked() => _log('identity_linked');

  /// The user explicitly unlinked their Google identity.
  static Future<void> identityUnlinked() => _log('identity_unlinked');

  /// Push notification permission was granted (or denied). [granted] = true/false.
  static Future<void> pushPermission(bool granted) =>
      _log('push_permission', {'granted': granted});

  /// Server accepted a push-token registration.
  static Future<void> pushTokenRegistered() => _log('push_token_registered');

  /// Catch-all user property setter (best-effort).
  static Future<void> setAnalyticsUserProperty(String name, String value) async {
    try {
      await _fa.setUserProperty(name: name, value: value);
    } catch (_) { /* ignore */ }
  }
}
