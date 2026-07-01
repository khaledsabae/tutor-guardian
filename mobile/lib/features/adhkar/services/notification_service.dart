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

  static const _morningId = 1001;
  static const _eveningId = 1002;
  static const _wirdId = 1003;

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
    await _scheduleOne(
      id: _wirdId,
      hour: hour,
      title: '📖 ورد اليوم — المربي الذكي',
      bodyOverride: 'حان وقت وردك اليومي من القرآن الكريم. تابع من حيث توقفت 🌿',
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

  /// Schedule morning + evening parenting-content notifications.
  Future<void> scheduleDaily({SharedPreferences? prefs}) async {
    prefs ??= await SharedPreferences.getInstance();
    final morningHour = prefs.getInt(_kMorningHour) ?? 6;
    final eveningHour = prefs.getInt(_kEveningHour) ?? 19;

    // Morning: hadith or verse (inspirational). Evening: hadith or tip (practical).
    final morning = _pickSequentialContent(prefs, allowedKinds: {'hadith', 'verse'}, prefKey: _kNextMorningIndex);
    final evening = _pickSequentialContent(prefs, allowedKinds: {'hadith', 'tip'}, prefKey: _kNextEveningIndex);

    // Cancel existing before re-scheduling.
    await _plugin.cancel(_morningId);
    await _plugin.cancel(_eveningId);

    await _scheduleOne(
      id: _morningId,
      hour: morningHour,
      content: morning,
      title: '🌅 نصيحة تربوية — المربي الذكي',
    );

    await _scheduleOne(
      id: _eveningId,
      hour: eveningHour,
      content: evening,
      title: '🌙 تذكير تربوي — المربي الذكي',
    );
  }

  /// Pick an item of [allowedKinds] sequentially to avoid any repetition until all are shown.
  ParentingContent _pickSequentialContent(SharedPreferences prefs, {required Set<String> allowedKinds, required String prefKey}) {
    final candidates = familyAdhkar
        .asMap()
        .entries
        .where((e) => allowedKinds.contains(e.value.kind))
        .map((e) => e.key)
        .toList();

    int currentIndex = prefs.getInt(prefKey) ?? 0;
    if (currentIndex >= candidates.length) {
      currentIndex = 0; // Reset once we've gone through all
    }

    final selectedIdx = candidates[currentIndex];

    // Increment index for the next time
    prefs.setInt(prefKey, currentIndex + 1);

    return familyAdhkar[selectedIdx];
  }

  Future<void> _scheduleOne({
    required int id,
    required int hour,
    required String title,
    ParentingContent? content,
    String? bodyOverride,
  }) async {
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

    final body =
        bodyOverride ?? '${content?.text ?? ''}\n— ${content?.source ?? ''}';
    await _plugin.zonedSchedule(
      id,
      title,
      body,
      scheduled,
      const NotificationDetails(android: androidDetails),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time,
      payload: content != null ? 'adhkar_${familyAdhkar.indexOf(content)}' : null,
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
