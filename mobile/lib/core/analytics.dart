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

  /// A pride-moment invite surface was shown / tapped. [source] = streak /
  /// story_end — measures whether asking at the right moment (§6.4) beats
  /// the passive settings/coins entry points.
  static Future<void> prideInviteShown(String source) =>
      _log('pride_invite_shown', {'source': source});

  static Future<void> prideInviteTapped(String source) =>
      _log('pride_invite_tapped', {'source': source});

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

  // ── Navigation & "lostness" ──────────────────────────────────────────────
  // Multiple users reported getting lost inside the app. These events exist to
  // locate *where*, rather than guessing. All screen identifiers must come from
  // `Screens.*` in core/app_routes.dart — free-text names would blow up
  // Firebase's event cardinality and make the funnels unusable.
  //
  // Most of these are emitted centrally by `TgNavObserver`; only the tab and
  // hub events are called by hand, because switching an IndexedStack index is
  // not a route change and so is invisible to a NavigatorObserver.

  /// A screen was pushed. [depth] is the resulting navigation-stack depth.
  static Future<void> screenView(String screen, int depth) =>
      _log('screen_view', {'screen': screen, 'nav_depth': depth});

  /// Opened and backed straight out again — the user looked and left.
  /// [from] is the screen they came from, which is where the misleading
  /// affordance lives.
  static Future<void> screenBounce(String screen, int dwellMs, String from) =>
      _log('screen_bounce',
          {'screen': screen, 'dwell_ms': dwellMs, 'from': from});

  /// Stayed a while but never navigated onward before backing out — the screen
  /// offered nothing actionable. The highest-signal event in this set.
  static Future<void> deadEnd(String screen, int dwellMs) =>
      _log('dead_end', {'screen': screen, 'dwell_ms': dwellMs});

  /// On screen but not touching anything — reading, or stuck. Sampled.
  static Future<void> idleDwell(String screen, int dwellMs) =>
      _log('idle_dwell', {'screen': screen, 'dwell_ms': dwellMs});

  /// Back-hammered from a deep stack to the root, usually meaning "get me out".
  static Future<void> backToRoot(int fromDepth) =>
      _log('nav_back_to_root', {'from_depth': fromDepth});

  /// A bottom-navigation destination was selected.
  static Future<void> tabSelected(String tab) =>
      _log('tab_selected', {'tab': tab});

  /// Rapid back-and-forth between tabs — hunting for something.
  /// [pattern] is the recent tab sequence, e.g. "tab_today>tab_more>tab_today".
  static Future<void> tabThrash(int switches, int windowMs, String pattern) =>
      _log('tab_thrash',
          {'switches': switches, 'window_ms': windowMs, 'pattern': pattern});

  // ── Restructure validation ───────────────────────────────────────────────

  /// A card on the rebuilt home screen was tapped — tells us whether the new
  /// visual hierarchy actually directs attention where it was meant to.
  static Future<void> homeCardTapped(String card) =>
      _log('home_card_tapped', {'card': card});

  /// The «المزيد» hub was opened.
  static Future<void> hubOpened() => _log('hub_opened');

  /// An entry inside the hub was tapped. If one group takes nearly all the
  /// taps, the grouping is wrong.
  static Future<void> hubItemTapped(String group, String item) =>
      _log('hub_item_tapped', {'group': group, 'item': item});

  /// A search returned nothing. Only the query *length* is recorded — never
  /// the query itself, which can contain a child's name.
  static Future<void> searchNoResult(int queryLen) =>
      _log('search_no_result', {'query_len': queryLen});

  /// The help sheet was opened, from [fromScreen].
  static Future<void> helpOpened(String fromScreen) =>
      _log('help_opened', {'screen': fromScreen});

  /// An "أين أجد…؟" intent was tapped. Cheapest possible lostness probe: it
  /// reports what people cannot find, in their own words, without a survey.
  static Future<void> helpIntentTapped(String intent) =>
      _log('help_intent_tapped', {'intent': intent});

  // ── Guided tour ──────────────────────────────────────────────────────────

  /// [action] = next / back / skip.
  static Future<void> tourStep(int step, String action) =>
      _log('tour_step', {'step': step, 'action': action});

  static Future<void> tourCompleted() => _logOnce('tour_completed');

  static Future<void> tourSkipped(int atStep) =>
      _logOnce('tour_skipped', {'at_step': atStep});

  /// Catch-all user property setter (best-effort).
  static Future<void> setAnalyticsUserProperty(String name, String value) async {
    try {
      await _fa.setUserProperty(name: name, value: value);
    } catch (_) { /* ignore */ }
  }
}
