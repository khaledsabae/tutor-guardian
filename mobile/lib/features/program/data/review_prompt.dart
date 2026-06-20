import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

/// Gentle, one-time "rate the app" prompt — shown only AFTER a few positive
/// moments (e.g. logging a milestone), never on first use, and never twice.
/// This is the "prompt after a positive experience" the tester report asked for.
class ReviewPrompt {
  static const _kCount = 'review.positive_actions';
  static const _kAsked = 'review.asked';
  static const _threshold = 2; // ask after the 2nd positive moment, not the 1st

  static Future<void> _openStore() async {
    final market = Uri.parse('market://details?id=com.alsaba.almorabbi');
    final web = Uri.parse(
        'https://play.google.com/store/apps/details?id=com.alsaba.almorabbi');
    if (await canLaunchUrl(market)) {
      await launchUrl(market, mode: LaunchMode.externalApplication);
    } else {
      await launchUrl(web, mode: LaunchMode.externalApplication);
    }
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
    if (yes == true) await _openStore();
  }
}
