/// Growth analytics — thin wrapper over the (previously declared-but-unwired)
/// firebase_analytics so we can actually measure the Phase 0 funnel and the
/// referral K-factor. Every call is best-effort and never throws.
///
/// Funnel we care about:
///   app_open (auto) → onboarding_done → first_value (milestone/lesson) →
///   share_moment → invite_opened → invite_shared → referral_claimed
library;

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:shared_preferences/shared_preferences.dart';

class Analytics {
  static FirebaseAnalytics get _fa => FirebaseAnalytics.instance;

  static Future<void> _log(String name, [Map<String, Object>? params]) async {
    try {
      await _fa.logEvent(name: name, parameters: params);
    } catch (_) {
      // analytics must never affect UX
    }
  }

  /// Log [name] at most once per install (guarded via SharedPreferences).
  /// Used for the one-shot funnel milestones (first_chat, first_lesson…).
  static Future<void> _logOnce(String name, [Map<String, Object>? params]) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = 'tg.analytics.once.$name';
      if (prefs.getBool(key) == true) return;
      await prefs.setBool(key, true);
      await _log(name, params);
    } catch (_) {
      // analytics must never affect UX
    }
  }

  // ── Activation funnel (§4.1 growth plan):
  //    install → onboarding_done → child_added → first_chat OR first_lesson
  //    → day2_return → habit_streak_3 ────────────────────────────────────

  /// Onboarding finished — the user landed in the main app.
  static Future<void> onboardingDone() => _logOnce('onboarding_done');

  /// A child profile was successfully created on the backend.
  static Future<void> childAdded(String ageGroup) =>
      _log('child_added', {'age_group': ageGroup});

  /// A chat message was actually submitted (first one also logs first_chat).
  static Future<void> chatSent() async {
    await _logOnce('first_chat');
    await _log('chat_message_sent');
  }

  /// A lesson's content loaded on screen (first one also logs first_lesson).
  static Future<void> lessonOpened(String lessonId) async {
    await _logOnce('first_lesson');
    await _log('lesson_opened', {'lesson_id': lessonId});
  }

  /// A lesson was marked completed.
  static Future<void> lessonCompleted(String lessonId) =>
      _log('lesson_completed', {'lesson_id': lessonId});

  /// A habit was checked in for today.
  static Future<void> habitCheckIn(String status) =>
      _log('habit_check_in', {'status': status});

  /// The child's habit streak reached 3+ days (one-shot funnel milestone).
  static Future<void> habitStreak3(int streakDays) =>
      _logOnce('habit_streak_3', {'streak_days': streakDays});

  /// A story was successfully generated.
  static Future<void> storyGenerated(String theme) =>
      _log('story_generated', {'theme': theme});

  /// The Quran/werd tab was selected.
  static Future<void> quranOpened() => _log('quran_opened');

  /// An educational game round was started.
  static Future<void> gameStarted(String gameId, int level) =>
      _log('game_started', {'game_id': gameId, 'level': level});

  /// Call on every app start. Records the first-open day and emits a one-shot
  /// day2_return when the app is opened again on the following calendar day.
  static Future<void> appOpened() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      const key = 'tg.analytics.first_open_epoch_day';
      final today = DateTime.now().toUtc().millisecondsSinceEpoch ~/
          Duration.millisecondsPerDay;
      final first = prefs.getInt(key);
      if (first == null) {
        await prefs.setInt(key, today);
        return;
      }
      if (today - first == 1) {
        await _logOnce('day2_return');
      }
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

  /// A push notification was received while the app is in foreground.
  static Future<void> pushReceived(String type) =>
      _log('push_received', {'type': type});

  /// Push notification was tapped (background or terminated).
  static Future<void> pushTapped(String type) =>
      _log('push_tapped', {'type': type});

  /// Catch-all user property setter (best-effort).
  static Future<void> setAnalyticsUserProperty(String name, String value) async {
    try {
      await _fa.setUserProperty(name: name, value: value);
    } catch (_) { /* ignore */ }
  }
}
