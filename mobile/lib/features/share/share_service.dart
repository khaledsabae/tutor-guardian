/// Central share helper — the one place that turns any widget into a
/// shared PNG with a reverent, pre-filled «تذكير» message and an install
/// link. Every viral surface in the app routes through here so the message
/// framing, install CTA, and (later) referral attribution stay consistent.
///
/// WhatsApp is surfaced first by the OS share sheet in Arabic markets; we
/// don't hard-bind to it (an image can't be pre-attached to a wa.me link),
/// but the pre-filled text + install URL travel with the image to whatever
/// app the parent picks.
library;

import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:screenshot/screenshot.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/analytics.dart';
import '../referral/referral_service.dart';

class ShareService {
  /// Shared links point at the public web landing (Phase 2), not directly at
  /// Play: it renders an Open Graph preview in WhatsApp, gives a content taste,
  /// works on iOS/desktop, and its install button forwards `ref` to the Play
  /// Install Referrer for free attribution (no deprecated Dynamic Links).
  static const String installUrl = 'https://tg-api.alsaba.cloud/go';

  /// Build the share/install URL, optionally carrying a referral code.
  static String installUrlFor({String? referralCode}) =>
      referralCode == null || referralCode.isEmpty
          ? installUrl
          : '$installUrl?ref=$referralCode';

  /// Open WhatsApp directly with a pre-filled text + install link.
  /// Falls back to the system share sheet if WhatsApp is not installed.
  static Future<bool> shareWhatsApp(String message, {String? referralCode}) async {
    referralCode ??= ReferralService.cachedCode;
    final buffer = StringBuffer()
      ..write(message)
      ..write('\n\n📲 «المربّي» مجانًا لوجه الله:\n')
      ..write(installUrlFor(referralCode: referralCode));
    final text = buffer.toString();
    final uri = Uri.parse('https://wa.me/?text=\${Uri.encodeComponent(text)}');
    if (await canLaunchUrl(uri)) {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
    final result = await Share.share(text);
    return result.status == ShareResultStatus.success;
  }

  /// Capture [card] to a PNG and open the share sheet with a reverent,
  /// pre-filled message plus the install link.
  ///
  /// [message] is the human line (e.g. «ما شاء الله، أتمّ محمد أول صلاة 🤍»);
  /// the install CTA is appended automatically so callers never forget it.
  static Future<bool> shareMomentCard({
    required Widget card,
    required String message,
    required String fileTag,
    String? referralCode,
  }) async {
    try {
      // Default to this device's referral code so every shared moment is an
      // attributed install driver (Phase 0.2), with no caller wiring needed.
      referralCode ??= ReferralService.cachedCode;
      final image = await ScreenshotController()
          .captureFromWidget(card, pixelRatio: 2.0);
      final dir = await Directory.systemTemp.createTemp('tg_share_');
      final file = File('${dir.path}/$fileTag.png');
      await file.writeAsBytes(image);

      final text = '$message\n\n📲 «المربّي» مجانًا لوجه الله:\n'
          '${installUrlFor(referralCode: referralCode)}';

      final result = await Share.shareXFiles([XFile(file.path)], text: text);
      final ok = result.status == ShareResultStatus.success;
      if (ok) {
        // fileTag like "milestone_<id>" / "quran_<n>" / "invite_<code>".
        await Analytics.shareMoment(fileTag.split('_').first);
      }
      return ok;
    } catch (_) {
      return false;
    }
  }
}