/// Notification Service — Daily family adhkar push notifications.
///
/// Schedules two daily local notifications (morning + evening) with
/// authentic Hadith about family, parenting, and children.
/// No server needed — runs entirely on-device.
library;

import 'dart:math';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

import '../data/family_adhkar.dart';

class NotificationService {
  NotificationService._();
  static final NotificationService instance = NotificationService._();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static const _kEnabled = 'tg.adhkar_notifications_enabled';
  static const _kMorningHour = 'tg.adhkar_morning_hour';
  static const _kEveningHour = 'tg.adhkar_evening_hour';

  static const _morningId = 1001;
  static const _eveningId = 1002;

  bool _initialized = false;

  /// Call once at app startup.
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    tz.initializeTimeZones();

    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidInit);
    await _plugin.initialize(initSettings);

    final prefs = await SharedPreferences.getInstance();
    final enabled = prefs.getBool(_kEnabled) ?? true;
    if (enabled) {
      // Android 13+ shows nothing without the runtime permission.
      await _requestPermission();
      await scheduleDaily(prefs: prefs);
    }
  }

  Future<bool> _requestPermission() async {
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android == null) return true;
    return await android.requestNotificationsPermission() ?? false;
  }

  /// Schedule morning + evening adhkar notifications.
  Future<void> scheduleDaily({SharedPreferences? prefs}) async {
    prefs ??= await SharedPreferences.getInstance();
    final morningHour = prefs.getInt(_kMorningHour) ?? 6;
    final eveningHour = prefs.getInt(_kEveningHour) ?? 19;

    final rng = Random();
    final morningDhikr = familyAdhkar[rng.nextInt(familyAdhkar.length)];
    final eveningDhikr = familyAdhkar[rng.nextInt(familyAdhkar.length)];

    // Cancel existing before re-scheduling.
    await _plugin.cancel(_morningId);
    await _plugin.cancel(_eveningId);

    await _scheduleOne(
      id: _morningId,
      hour: morningHour,
      dhikr: morningDhikr,
      title: '🌅 ذكر الصباح — المربي الذكي',
    );

    await _scheduleOne(
      id: _eveningId,
      hour: eveningHour,
      dhikr: eveningDhikr,
      title: '🌙 ذكر المساء — المربي الذكي',
    );
  }

  Future<void> _scheduleOne({
    required int id,
    required int hour,
    required FamilyDhikr dhikr,
    required String title,
  }) async {
    final now = tz.TZDateTime.now(tz.local);
    var scheduled = tz.TZDateTime(tz.local, now.year, now.month, now.day, hour);
    if (scheduled.isBefore(now)) {
      scheduled = scheduled.add(const Duration(days: 1));
    }

    const androidDetails = AndroidNotificationDetails(
      'adhkar_channel',
      'أذكار الأسرة',
      channelDescription: 'إشعارات يومية بأحاديث عن الأسرة والتربية',
      importance: Importance.high,
      priority: Priority.high,
      styleInformation: BigTextStyleInformation(''),
    );

    await _plugin.zonedSchedule(
      id,
      title,
      '${dhikr.text}\n— ${dhikr.source}',
      scheduled,
      const NotificationDetails(android: androidDetails),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time,
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
      await _plugin.cancel(_morningId);
      await _plugin.cancel(_eveningId);
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
