/// The Android notification channels this app sends on.
///
/// The backend has been setting `channel_id` on every push it sends for a
/// year, and the app never created a single channel. On Android 8+ a channel
/// id that does not exist is not an error — the system quietly files the
/// notification under the app's default channel instead. So every push, from
/// the marketing re-engagement nudge to the internet-licence safety alert,
/// landed in one undifferentiated bucket that a parent can only turn fully on
/// or fully off.
///
/// That is a real problem rather than a tidiness one. The safety alert exists
/// precisely so a parent who has muted marketing still hears that their child
/// met a grooming situation tonight — and until these channels exist, muting
/// one mutes the other. The server-side split shipped working and had nothing
/// to land on.
///
/// Channels are created once and are then owned by the OS: importance and
/// sound become the user's to change, and re-creating a channel with the same
/// id cannot override what they chose. That is why the ids here are treated
/// as a wire format, like the analytics screen names — renaming one creates a
/// second channel and silently resets whatever the user had configured.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Re-engagement, digests, product news. The default for everything that is
/// not urgent, and the one a parent is most likely to silence.
///
/// Must stay byte-identical to `push_sender.DEFAULT_CHANNEL`.
const kChannelReengagement = 'almorabbi_reengagement';

/// Child-safety alerts. One kind of message only: a situation in the internet
/// licence that a parent should hear about tonight rather than tomorrow.
///
/// Must stay byte-identical to `license_alert.SAFETY_CHANNEL`.
const kChannelSafety = 'almorabbi_safety';

/// Create both channels. Safe to call on every launch — the OS treats a
/// repeat create for an existing id as a no-op and keeps the user's settings.
Future<void> ensureNotificationChannels() async {
  if (defaultTargetPlatform != TargetPlatform.android) return;

  final android = FlutterLocalNotificationsPlugin()
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
  if (android == null) return;

  await android.createNotificationChannel(const AndroidNotificationChannel(
    kChannelReengagement,
    'تذكيرات ومستجدّات',
    description: 'تذكيرات ومهام تنتظر تأكيدك وأخبار التطبيق.',
    importance: Importance.defaultImportance,
  ));

  // Higher importance than the channel above, and named so the row in Android
  // settings reads as something a parent would think twice about silencing.
  await android.createNotificationChannel(const AndroidNotificationChannel(
    kChannelSafety,
    'تنبيهات سلامة الطفل',
    description:
        'موقف في رخصة الإنترنت يستحق أن تتحدث مع ابنك فيه اليوم. '
        'نادر جدًا — وهو الوحيد الذي يصلك حتى لو أسكتّ الباقي.',
    importance: Importance.high,
  ));
}
