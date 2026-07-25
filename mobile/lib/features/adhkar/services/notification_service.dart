/// Notification Service — Daily family adhkar push notifications.
///
/// Schedules two daily local notifications (morning + evening) with
/// authentic Hadith about family, parenting, and children.
/// No server needed — runs entirely on-device.
library;

import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

import '../../../main.dart';
import '../data/family_adhkar.dart';


class NotificationService {
  NotificationService._();
  static final NotificationService instance = NotificationService._();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static const _kEnabled = 'tg.adhkar_notifications_enabled';
  static const _kMorningHour = 'tg.adhkar_morning_hour';
  static const _kEveningHour = 'tg.adhkar_evening_hour';
  static const _kWirdEnabled = 'tg.wird_reminder_enabled';
  static const _kWirdHour = 'tg.wird_reminder_hour';
  static const _kNextMorningIndex = 'tg.adhkar_next_morning';
  static const _kNextEveningIndex = 'tg.adhkar_next_evening';

  static const _morningBaseId = 1000;
  static const _eveningBaseId = 2000;
  static const _wirdId = 3000;
  static const _daysToSchedule = 14;

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
    final enabled = prefs.getBool(_kEnabled) ?? true;
    final wird = prefs.getBool(_kWirdEnabled) ?? true;
    if (enabled || wird) {
      // Android 13+ shows nothing without the runtime permission.
      await _requestPermission();
    }
    if (enabled) await scheduleDaily(prefs: prefs);
    if (wird) await scheduleWirdReminder(prefs: prefs);

    // Check if cold-started from notification
    final details = await _plugin.getNotificationAppLaunchDetails();
    if (details != null && details.didNotificationLaunchApp) {
      pendingPayload = details.notificationResponse?.payload;
    }
  }

  void processPendingTap() {
    if (pendingPayload != null) {
      _handleNotificationTap(pendingPayload);
      pendingPayload = null;
    }
  }

  void _handleNotificationTap(String? payload) {
    if (payload == null) return;
    if (payload.startsWith('adhkar_')) {
      final idx = int.tryParse(payload.substring(7));
      if (idx != null && idx >= 0 && idx < familyAdhkar.length) {
        final content = familyAdhkar[idx];
        _showTipDialog(content);
      }
    }
  }

  void _showTipDialog(ParentingContent content) {
    final context = appNavigatorKey.currentContext;
    if (context == null) {
      // Retry in a bit if context isn't ready
      Future.delayed(const Duration(milliseconds: 500), () => _showTipDialog(content));
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

  /// Daily reminder to read the Qur'an wird (default 5 PM).
  Future<void> scheduleWirdReminder({SharedPreferences? prefs}) async {
    prefs ??= await SharedPreferences.getInstance();
    final hour = prefs.getInt(_kWirdHour) ?? 17;
    await _plugin.cancel(_wirdId);
    
    final now = tz.TZDateTime.now(tz.local);
    var scheduled = tz.TZDateTime(tz.local, now.year, now.month, now.day, hour);
    if (scheduled.isBefore(now)) {
      scheduled = scheduled.add(const Duration(days: 1));
    }

    const androidDetails = AndroidNotificationDetails(
      'parenting_content_channel',
      'تذكيرات تربوية',
      channelDescription: 'آيات وأحاديث ونصائح تربوية يومية',
      importance: Importance.high,
      priority: Priority.high,
      styleInformation: BigTextStyleInformation(''),
    );

    await _plugin.zonedSchedule(
      _wirdId,
      '📖 ورد اليوم — المربي الذكي',
      'حان وقت وردك اليومي من القرآن الكريم. تابع من حيث توقفت 🌿',
      scheduled,
      const NotificationDetails(android: androidDetails),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time,
    );
  }

  Future<void> setWirdEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kWirdEnabled, enabled);
    if (enabled) {
      await _requestPermission();
      await scheduleWirdReminder(prefs: prefs);
    } else {
      await _plugin.cancel(_wirdId);
    }
  }

  Future<bool> isWirdEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_kWirdEnabled) ?? true;
  }

  Future<bool> _requestPermission() async {
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android == null) return true;
    return await android.requestNotificationsPermission() ?? false;
  }

  /// Schedule morning + evening parenting-content notifications for the next [_daysToSchedule] days.
  Future<void> scheduleDaily({SharedPreferences? prefs}) async {
    prefs ??= await SharedPreferences.getInstance();
    final morningHour = prefs.getInt(_kMorningHour) ?? 6;
    final eveningHour = prefs.getInt(_kEveningHour) ?? 19;

    final morningCandidates = familyAdhkar
        .asMap()
        .entries
        .where((e) => e.value.kind == 'hadith' || e.value.kind == 'verse')
        .map((e) => e.key)
        .toList();

    final eveningCandidates = familyAdhkar
        .asMap()
        .entries
        .where((e) => e.value.kind == 'hadith' || e.value.kind == 'tip')
        .map((e) => e.key)
        .toList();

    if (morningCandidates.isEmpty || eveningCandidates.isEmpty) return;

    // Seed only — kept so existing installs don't jump position.
    final morningSeed = prefs.getInt(_kNextMorningIndex) ?? 0;
    final eveningSeed = prefs.getInt(_kNextEveningIndex) ?? 0;

    // Cancel existing scheduled slots up to 30 days
    for (int i = 0; i < 30; i++) {
      await _plugin.cancel(_morningBaseId + i);
      await _plugin.cancel(_eveningBaseId + i);
    }

    final now = tz.TZDateTime.now(tz.local);

    // Rotation is anchored to the calendar day, not to a stored counter.
    // The counter version read the index but never wrote it back, so every
    // reschedule restarted at the same place and only the first 14 items of
    // each pool were ever delivered — 96% of the 731 items were unreachable.
    // Day-anchoring also means opening the app ten times in a day changes
    // nothing, and each day maps to exactly one item.
    final epochDay = DateTime(now.year, now.month, now.day)
        .difference(DateTime.utc(2020, 1, 1))
        .inDays;

    // Compute each series' first slot once. Adding dayOffset to "today at H"
    // and then pushing day 0 to tomorrow when H has passed made day 0 and
    // day 1 land on the same instant — two morning notifications tomorrow.
    var mBase = tz.TZDateTime(tz.local, now.year, now.month, now.day, morningHour);
    if (mBase.isBefore(now)) mBase = mBase.add(const Duration(days: 1));
    var eBase = tz.TZDateTime(tz.local, now.year, now.month, now.day, eveningHour);
    if (eBase.isBefore(now)) eBase = eBase.add(const Duration(days: 1));

    for (int dayOffset = 0; dayOffset < _daysToSchedule; dayOffset++) {
      final mIdx = morningCandidates[
          (morningSeed + epochDay + dayOffset) % morningCandidates.length];
      final eIdx = eveningCandidates[
          (eveningSeed + epochDay + dayOffset) % eveningCandidates.length];

      final morningContent = familyAdhkar[mIdx];
      final eveningContent = familyAdhkar[eIdx];

      final mDate = mBase.add(Duration(days: dayOffset));
      final eDate = eBase.add(Duration(days: dayOffset));

      await _scheduleSpecific(
        id: _morningBaseId + dayOffset,
        scheduledDate: mDate,
        title: '🌅 نصيحة تربوية — المربي الذكي',
        content: morningContent,
      );

      await _scheduleSpecific(
        id: _eveningBaseId + dayOffset,
        scheduledDate: eDate,
        title: '🌙 تذكير تربوي — المربي الذكي',
        content: eveningContent,
      );
    }
  }

  Future<void> _scheduleSpecific({
    required int id,
    required tz.TZDateTime scheduledDate,
    required String title,
    required ParentingContent content,
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
      payload: 'adhkar_${familyAdhkar.indexOf(content)}',
    );
  }

  /// Toggle notifications on/off.
  Future<void> setEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kEnabled, enabled);
    if (enabled) {
      await _requestPermission();
      await scheduleDaily(prefs: prefs);
    } else {
      for (int i = 0; i < 30; i++) {
        await _plugin.cancel(_morningBaseId + i);
        await _plugin.cancel(_eveningBaseId + i);
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
