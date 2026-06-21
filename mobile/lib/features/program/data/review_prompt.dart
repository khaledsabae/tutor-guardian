import 'package:flutter/material.dart';
import 'package:in_app_review/in_app_review.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Gentle, one-time "rate the app" prompt — shown only AFTER a few positive
/// moments (e.g. logging a milestone), never on first use, and never twice.
/// This is the "prompt after a positive experience" the tester report asked for.
class ReviewPrompt {
  static const _kCount = 'review.positive_actions';
  static const _kAsked = 'review.asked';
  static const _threshold = 2; // ask after the 2nd positive moment, not the 1st

  /// Native in-app review sheet (no app exit → higher completion), falling
  /// back to the store listing if the API isn't available on the device.
  static Future<void> _requestReview() async {
    final inAppReview = InAppReview.instance;
    try {
      if (await inAppReview.isAvailable()) {
        await inAppReview.requestReview();
        return;
      }
    } catch (_) {
      // fall through to store listing
    }
    await inAppReview.openStoreListing(
      appStoreId: 'com.alsaba.almorabbi',
    );
  }

  /// Records a positive moment; once [_threshold] have accrued (and we haven't
  /// asked before) shows the rating prompt exactly once.
  static Future<void> maybeAsk(BuildContext context) async {
    final p = await SharedPreferences.getInstance();
    if (p.getBool(_kAsked) ?? false) return;
    final count = (p.getInt(_kCount) ?? 0) + 1;
    await p.setInt(_kCount, count);
    if (count < _threshold) return;
    await p.setBool(_kAsked, true);

    if (!context.mounted) return;
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('هل أعجبك «المربّي»؟ 🌟'),
        content: const Text(
          'تقييمك على المتجر يساعد آباءً غيرك يجدون التطبيق — '
          'وفي ميزان حسناتك إن شاء الله.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('لاحقًا'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('قيّم الآن'),
          ),
        ],
      ),
    );
    if (yes == true) await _requestReview();
  }
}
