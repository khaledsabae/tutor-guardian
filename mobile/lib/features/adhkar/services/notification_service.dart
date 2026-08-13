/// Notification Service — one daily local notification, on-device.
///
/// It used to be three: adhkar at 06:00 and 19:00, plus a Qur'an wird reminder
/// at 17:00 — on top of two server pushes, so five a day. Measured over the
/// first two weeks: 37,393 FCM notifications to 1,567 users, 2.5% opened, 68%
/// dismissed. (Those figures are FCM-only; GA4's notification_* events come
/// from the FCM SDK, so the three local ones were never in them — the
/// unmeasured half was the larger one.)
///
/// A notification dismissed 68% of the time teaches people to ignore the app,
/// and some of them to switch notifications off entirely — which also severs
/// the feedback-reply channel.
///
/// The wird was retired rather than the adhkar for two reasons: it was one
/// fixed string repeated 365×/year, and its off switch was never wired to
/// anything, so it could not be silenced. See [_purgeRetiredSlots].
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../main.dart';
import '../data/family_adhkar.dart';


class NotificationService {
  NotificationService._();
  static final NotificationService instance = NotificationService._();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static const _kEnabled = 'tg.adhkar_notifications_enabled';
  static const _kDailyHour = 'tg.adhkar_daily_hour';

  // _kMorningHour / _kEveningHour / _kWirdHour removed 2026-08-13: there is one
  // slot now. None of the three had a UI writer, so no install had customised
  // them.
  //
  // _kNextMorningIndex / _kNextEveningIndex removed 2026-08-13. Both were read
  // as a rotation seed and never written — `git log -S"setInt(_kNextMorningIndex"`
  // is empty across the whole history — so they were 0 on every install and the
  // seed was a no-op. Nothing to migrate.

  static const _dailyBaseId = 1000;
  static const _daysToSchedule = 14;

  /// Cancel-only. Nothing schedules these any more — see [_purgeRetiredSlots].
  static const _retiredEveningBaseId = 2000;
  static const _retiredWirdId = 3000;
  static const _kRetiredSlotsPurged = 'tg.notif.retired_slots_purged_v2';

  /// The wird reminder used to be scheduled with no payload at all, so
  /// `_handleNotificationTap` returned on its first line and tapping
  /// «حان وقت وردك اليومي» did nothing — the one notification whose text
  /// makes an explicit promise about where it leads.
  static const _wirdPayload = 'wird';

  bool _initialized = false;
  String? pendingPayload;

  /// Call once at app startup.
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    tz.initializeTimeZones();

    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidInit);
    await _plugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: (response) {
        _handleNotificationTap(response.payload);
      },
    );

    final prefs = await SharedPreferences.getInstance();
    await _purgeRetiredSlots(prefs);
    final enabled = prefs.getBool(_kEnabled) ?? true;
    if (enabled) {
      // Android 13+ shows nothing without the runtime permission.
      await _requestPermission();
      await scheduleDaily(prefs: prefs);
    }

    // Check if cold-started from notification
    final details = await _plugin.getNotificationAppLaunchDetails();
    if (details != null && details.didNotificationLaunchApp) {
      pendingPayload = details.notificationResponse?.payload;
    }
  }

  /// Cancels every notification id this app used to schedule and no longer does.
  ///
  /// Not defensive housekeeping — without it the change does not reach anyone
  /// who already has the app. `AndroidManifest.xml` registers
  /// flutter_local_notifications' `ScheduledNotificationBootReceiver` for
  /// `MY_PACKAGE_REPLACED`, so after an update the plugin re-registers its
  /// whole pending queue from its own store, without Dart running. Installing
  /// this build over the old one clears nothing: the evening series (2000+i)
  /// keeps firing for up to 14 more days, and the wird (3000) was scheduled
  /// with `matchDateTimeComponents: DateTimeComponents.time` — a daily repeat
  /// with no end date — so it fires forever.
  ///
  /// Runs before the [_kEnabled] branch on purpose: the wird was gated by a
  /// separate pref that `setEnabled(false)` never touched, so a user who had
  /// already switched adhkar off still has 3000 queued and would otherwise
  /// never reach any cancel path.
  ///
  /// One-shot: once cancelled the plugin drops them from its store and nothing
  /// recreates them. The flag is written only after every cancel resolves, so a
  /// process killed mid-purge retries on the next launch. Delete this method
  /// and the two `_retired*` constants once v1.0.39 is the floor.
  Future<void> _purgeRetiredSlots(SharedPreferences prefs) async {
    if (prefs.getBool(_kRetiredSlotsPurged) == true) return;
    // 30, not _daysToSchedule: older builds may have queued further out.
    for (int i = 0; i < 30; i++) {
      await _plugin.cancel(_retiredEveningBaseId + i);
    }
    await _plugin.cancel(_retiredWirdId);
    await prefs.setBool(_kRetiredSlotsPurged, true);
  }

  void processPendingTap() {
    if (pendingPayload != null) {
      _handleNotificationTap(pendingPayload);
      pendingPayload = null;
    }
  }

  void _handleNotificationTap(String? payload) {
    if (payload == null) return;

    // These emitted no events at all until 2026-08-11, so every notification
    // number we had was FCM-only while the larger, on-device share sat
    // unmeasured underneath it.
    //
    // The scheduler for 'wird' was removed 2026-08-13 (one local notification a
    // day now). This branch stays because notifications already in the tray at
    // update time still carry the payload, and because it is how the tail is
    // watched: local_notification_open(slot='wird') should reach zero within a
    // couple of days of rollout. Delete the branch then.
    if (payload == _wirdPayload) {
      unawaited(Analytics.localNotificationOpen('wird'));
      // It says "carry on from where you stopped". So carry them there.
      final context = appNavigatorKey.currentContext;
      if (context != null) {
        Navigator.of(context).push(AppRoutes.quran());
      }
      return;
    }

    if (payload.startsWith('adhkar_')) {
      unawaited(Analytics.localNotificationOpen('adhkar'));
      final idx = int.tryParse(payload.substring(7));
      if (idx != null && idx >= 0 && idx < familyAdhkar.length) {
        final content = familyAdhkar[idx];
        _showTipDialog(content);
      }
    }
  }

  /// Bounded: the retry below used to recurse forever at 500ms. A navigator
  /// that never materialises — the app being killed mid-launch, a cold start
  /// that fails before the first frame — meant a timer chain running for the
  /// life of the process, holding this content and firing twice a second
  /// against nothing. Ten attempts is five seconds; if the UI is not up by
  /// then it is not coming.
  static const _maxDialogRetries = 10;

  void _showTipDialog(ParentingContent content, {int attempt = 0}) {
    final context = appNavigatorKey.currentContext;
    if (context == null) {
      if (attempt >= _maxDialogRetries) return;
      Future.delayed(
        const Duration(milliseconds: 500),
        () => _showTipDialog(content, attempt: attempt + 1),
      );
      return;
    }

    showDialog(
      context: context,
      builder: (context) {
        return Directionality(
          textDirection: TextDirection.rtl,
          child: AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            title: Row(
              children: [
                Text(
                  content.kind == 'hadith'
                      ? '🕌 حديث شريف'
                      : content.kind == 'verse'
                          ? '📖 آية كريمة'
                          : '💡 نصيحة اليوم',
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 18,
                    color: Color(0xFF0F172A),
                  ),
                ),
              ],
            ),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    content.text,
                    style: const TextStyle(
                      fontSize: 15,
                      height: 1.6,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF334155),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF1F5F9),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      content.source,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF64748B),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text(
                  'حسناً',
                  style: TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 14,
                    color: Color(0xFF10B981),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // scheduleWirdReminder() / setWirdEnabled() / isWirdEnabled() removed
  // 2026-08-13, when the local notifications went from three a day to one.
  //
  // The wird was the one retired because it was the one that could not be
  // switched off: setWirdEnabled and isWirdEnabled had no caller anywhere in
  // lib/ — the single notifications row in settings drives setEnabled, which
  // cancelled 1000..1029 and 2000..2029 and never touched 3000. So a user who
  // turned «إشعارات أذكار الأسرة» off kept receiving «حان وقت وردك اليومي»
  // daily, forever, on the same channel. It was also scheduled with
  // matchDateTimeComponents: DateTimeComponents.time, i.e. an unbounded repeat
  // of one fixed string, against the adhkar slot's 281-item rotation.
  //
  // The tap handler for payload 'wird' is deliberately still in
  // _handleNotificationTap; see the note there.

  Future<bool> _requestPermission() async {
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android == null) return true;
    return await android.requestNotificationsPermission() ?? false;
  }

  /// Schedule one parenting-content notification a day for the next
  /// [_daysToSchedule] days.
  Future<void> scheduleDaily({SharedPreferences? prefs}) async {
    prefs ??= await SharedPreferences.getInstance();
    final hour = prefs.getInt(_kDailyHour) ?? 6;
    if (familyAdhkar.isEmpty) return;

    // 30, not _daysToSchedule: older builds queued out to 30.
    for (int i = 0; i < 30; i++) {
      await _plugin.cancel(_dailyBaseId + i);
    }

    final now = tz.TZDateTime.now(tz.local);

    // Rotation is anchored to the calendar day, not to a stored counter.
    // The counter version read the index but never wrote it back, so every
    // reschedule restarted at the same place and only the first 14 items of
    // each pool were ever delivered — 96% of the items were unreachable.
    // Day-anchoring also means opening the app ten times in a day changes
    // nothing, and each day maps to exactly one item.
    //
    // The pool is now the whole list rather than two kind-filtered slices. The
    // union of the old pools was also 281, but a 'tip' could only ever arrive
    // in the evening and a 'verse' only in the morning; with one slot, either
    // filter would have made a whole kind unreachable. A full walk is 281 days,
    // up from 157 and 139.
    final epochDay = DateTime(now.year, now.month, now.day)
        .difference(DateTime.utc(2020, 1, 1))
        .inDays;

    // Compute the first slot once. Adding dayOffset to "today at H" and then
    // pushing day 0 to tomorrow when H has passed made day 0 and day 1 land on
    // the same instant — two notifications tomorrow.
    var base = tz.TZDateTime(tz.local, now.year, now.month, now.day, hour);
    if (base.isBefore(now)) base = base.add(const Duration(days: 1));

    for (int dayOffset = 0; dayOffset < _daysToSchedule; dayOffset++) {
      final idx = (epochDay + dayOffset) % familyAdhkar.length;
      await _scheduleSpecific(
        id: _dailyBaseId + dayOffset,
        scheduledDate: base.add(Duration(days: dayOffset)),
        title: _titleFor(familyAdhkar[idx]),
        content: familyAdhkar[idx],
        contentIndex: idx,
      );
    }
  }

  /// The slot no longer says morning or evening, so the title says what the
  /// item *is*. Mirrors the headers used by the in-app dialog.
  String _titleFor(ParentingContent content) => switch (content.kind) {
        'hadith' => '🕌 حديث شريف — المربي الذكي',
        'verse' => '📖 آية كريمة — المربي الذكي',
        _ => '💡 نصيحة اليوم — المربي الذكي',
      };

  Future<void> _scheduleSpecific({
    required int id,
    required tz.TZDateTime scheduledDate,
    required String title,
    required ParentingContent content,
    required int contentIndex,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'parenting_content_channel',
      'تذكيرات تربوية',
      channelDescription: 'آيات وأحاديث ونصائح تربوية يومية',
      importance: Importance.high,
      priority: Priority.high,
      styleInformation: BigTextStyleInformation(''),
    );

    final body = '${content.text}\n— ${content.source}';
    await _plugin.zonedSchedule(
      id,
      title,
      body,
      scheduledDate,
      const NotificationDetails(android: androidDetails),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      // The caller already knows the index. indexOf was an O(n) identity scan,
      // and two byte-identical const entries canonicalise to one object, so it
      // could address the payload at the wrong item.
      payload: 'adhkar_$contentIndex',
    );
  }

  /// Toggle notifications on/off.
  Future<void> setEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kEnabled, enabled);
    unawaited(Analytics.notificationPrefChanged('adhkar', enabled));
    if (enabled) {
      await _requestPermission();
      await scheduleDaily(prefs: prefs);
    } else {
      for (int i = 0; i < 30; i++) {
        await _plugin.cancel(_dailyBaseId + i);
      }
    }
  }

  /// Whether notifications are currently enabled.
  Future<bool> isEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_kEnabled) ?? true;
  }

  /// Cancel all scheduled notifications.
  Future<void> cancelAll() async {
    await _plugin.cancelAll();
  }
}
