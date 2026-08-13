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

import 'engagement_signal.dart';

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

  // The methods below also raise [EngagementSignal] — see its doc for why.
  // In short: TgNavObserver could only tell "found a way onward" from "found
  // nothing", so finishing a task on a leaf screen and hitting a wall scored
  // identically. Marking them here rather than at each screen keeps it to one
  // line and leaves the feature code untouched.

  /// A lesson was marked completed.
  static Future<void> lessonCompleted(String lessonId) {
    EngagementSignal.mark();
    return _log('lesson_completed', {'lesson_id': lessonId});
  }

  /// A completion tap whose progress write failed — the user meant to finish
  /// the lesson but nothing was recorded.
  ///
  /// Kept as its own event rather than folded into [lessonCompleted] so that
  /// series keeps meaning "completed *and* persisted" and stays comparable
  /// across the whole history. Without this the failures are invisible: the
  /// PATCH is a single shot with no retry, so a bad network turns a finished
  /// lesson into a snackbar and completion reads low for a reason nobody can
  /// see in the numbers.
  static Future<void> lessonCompleteFailed(String lessonId) =>
      _log('lesson_complete_failed', {'lesson_id': lessonId});

  /// A habit was checked in for today.
  static Future<void> habitCheckIn(String status) {
    EngagementSignal.mark();
    return _log('habit_check_in', {'status': status});
  }

  /// The child's habit streak reached 3+ days (one-shot funnel milestone).
  static Future<void> habitStreak3(int streakDays) =>
      _logOnce('habit_streak_3', {'streak_days': streakDays});

  /// A story was successfully generated.
  static Future<void> storyGenerated(String theme) {
    EngagementSignal.mark();
    return _log('story_generated', {'theme': theme});
  }

  /// The Quran/werd tab was selected.
  static Future<void> quranOpened() {
    EngagementSignal.mark();
    return _log('quran_opened');
  }

  // ── Games ────────────────────────────────────────────────────────────────
  //
  // gameStarted() removed 2026-08-13. One event covered two different things.
  // It fired from the games index on tapping a card — level: 0, meaning "opened
  // the level-select lobby" — and again from the shell with the real level when
  // a level actually began. Entering from a lesson skips the index, so that
  // path fired once and the index path fired twice for the same play. The
  // counts were inflated and not comparable across entry points, and `level: 0`
  // is not a level. That is how «4 games, 5,856 sessions, 5.9 per player»
  // became the strongest engagement number in the app.
  //
  // `game_started` history is NOT comparable to either event below. Do not join
  // the series; treat 2026-08-13 as the start of the games numbers.
  //
  // GA4: `entry_point`, `stars` and `completed` are new params and must be
  // registered as custom dimensions (and `score` as a custom metric) in
  // Admin → Custom definitions. An unregistered param is collected but reads
  // empty in every report, and registration is NOT retroactive — the dimension
  // is blank for every event logged before the day it was created.

  /// A game was opened — its level-select screen appeared.
  ///
  /// [entryPoint] is a `GameSources.*` constant. Deliberately does NOT raise
  /// [EngagementSignal]: opening a screen is not an accomplishment, and marking
  /// here would make the level-select screen permanently immune to
  /// `dead_end_v2` — which is exactly the case worth being able to see.
  static Future<void> gameOpened(String gameId, String entryPoint) =>
      _log('game_opened', {'game_id': gameId, 'entry_point': entryPoint});

  /// A level actually started. This is the number "how many games were played".
  static Future<void> gameLevelStarted(
      String gameId, int level, String entryPoint) {
    EngagementSignal.mark();
    return _log('game_level_started',
        {'game_id': gameId, 'level': level, 'entry_point': entryPoint});
  }

  /// A level ended, win or lose. Until now the result was computed, persisted
  /// and credited to coins without ever being logged, so starts were
  /// measurable and outcomes were not.
  ///
  /// [completed] is sent as a string because a raw bool param is dropped —
  /// see [notificationPrefChanged].
  static Future<void> gameCompleted({
    required String gameId,
    required int level,
    required bool completed,
    required int stars,
    required int score,
    required String entryPoint,
  }) {
    EngagementSignal.mark();
    return _log('game_completed', {
      'game_id': gameId,
      'level': level,
      'completed': completed ? 'true' : 'false',
      'stars': stars,
      'score': score,
      'entry_point': entryPoint,
    });
  }

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
  ///
  /// Sent as a string, not a bool: firebase_analytics asserts every parameter
  /// is String or num, so a raw bool throws in debug (swallowed by [_log]'s
  /// catch, taking the whole event with it) and is dropped in release. This
  /// event has therefore never carried its only parameter. Same workaround as
  /// [notificationPrefChanged]. Values before 2026-08-13 are empty.
  static Future<void> pushPermission(bool granted) =>
      _log('push_permission', {'granted': granted ? 'true' : 'false'});

  /// Server accepted a push-token registration.
  static Future<void> pushTokenRegistered() => _log('push_token_registered');

  /// A push notification was received while the app is in foreground.
  static Future<void> pushReceived(String type) =>
      _log('push_received', {'type': type});

  /// Push notification was tapped (background or terminated).
  static Future<void> pushTapped(String type) =>
      _log('push_tapped', {'type': type});

  /// An on-device notification was tapped — adhkar or the Qur'an wird.
  ///
  /// Separate from [pushTapped] because these come from a different system
  /// entirely: three a day, scheduled locally, no server involved. They had
  /// no instrumentation at all, so every notification figure we had described
  /// FCM only while the larger, unmeasured half sat underneath it.
  static Future<void> localNotificationOpen(String slot) =>
      _log('local_notification_open', {'slot': slot});

  /// A notification preference was changed. [slot] is which one, [enabled] the
  /// new state — the only signal that says whether the volume is welcome.
  static Future<void> notificationPrefChanged(String slot, bool enabled) =>
      _log('notification_pref_changed',
          {'slot': slot, 'granted': enabled ? 'true' : 'false'});

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
  ///
  /// Two calls on purpose:
  ///
  /// 1. `logScreenView` writes the reserved `firebase_screen` params, which is
  ///    the only thing that fills GA4's `unifiedScreenName`. Passing the name
  ///    as a plain `screen` param under the reserved `screen_view` event left
  ///    65,848 of 66,772 views reported as `(not set)` — every built-in screen
  ///    report was blank, and our custom events collided with the SDK's own
  ///    auto-collected `screen_view` in the same bucket.
  /// 2. A non-reserved event keeps `nav_depth`, which no built-in event
  ///    carries and which is what makes a bounce readable.
  static Future<void> screenView(String screen, int depth) async {
    try {
      await _fa.logScreenView(screenName: screen, screenClass: screen);
    } catch (_) {}
    await _log('tg_screen_view', {'screen': screen, 'nav_depth': depth});
  }

  /// Opened and backed straight out again — the user looked and left.
  /// [from] is the screen they came from, which is where the misleading
  /// affordance lives.
  static Future<void> screenBounce(String screen, int dwellMs, String from) =>
      _log('screen_bounce',
          {'screen': screen, 'dwell_ms': dwellMs, 'from': from});

  /// Stayed a while, did nothing that counted, and backed out — the screen
  /// offered nothing actionable.
  ///
  /// Emitted as `dead_end_v2`, not `dead_end`. The old event fired whenever a
  /// screen pushed no named route, so every leaf screen in the app qualified
  /// and 66% of users looked lost. Reusing the name would average two
  /// different definitions into one unreadable series; the old one stops here
  /// and its history stays interpretable as what it actually measured.
  static Future<void> deadEnd(String screen, int dwellMs) =>
      _log('dead_end_v2', {'screen': screen, 'dwell_ms': dwellMs});

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

  // hubOpened() removed 2026-08-11. It was called from HubScreen.initState,
  // but RootScaffold's IndexedStack mounts every child at once, so it fired on
  // cold start for every user rather than on first reveal. Use `tab_selected`
  // filtered to tab='tab_more' instead.

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
