/// Referral service — the mobile half of the Phase 0.2 growth loop.
///
/// On first run it reads the Google Play Install Referrer (free attribution,
/// no deprecated Dynamic Links) and, if the install arrived via someone's
/// `ref_<code>`, claims it on the backend and credits the new parent. It also
/// fetches this device's own code + invited-count and reconciles the
/// referrer's coin rewards client-side (the coins ledger is on-device).
///
/// [cachedCode] is read by [ShareService] so every shared moment card carries
/// the inviter's code — turning the existing share surfaces into attributed
/// install drivers.
library;

import 'package:play_install_referrer/play_install_referrer.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../api/tg_client.dart';
import '../../core/analytics.dart';
import '../coins/coins_service.dart';

class ReferralInfo {
  const ReferralInfo({
    required this.code,
    required this.invitedCount,
    required this.shareUrl,
  });
  final String code;
  final int invitedCount;
  final String shareUrl;
}

enum ClaimOutcome { success, alreadyClaimed, invalid, error }

class ReferralService {
  ReferralService._();
  static final ReferralService instance = ReferralService._();

  final TgClient _client = TgClient();

  /// This device's referral code once fetched — read by ShareService so
  /// shared cards carry attribution. Null until [refresh] runs.
  static String? cachedCode;

  static const _kReferrerChecked = 'referral.referrer_checked';
  static const _kClaimed = 'referral.claimed';

  static final RegExp _codeRe = RegExp(r'REF_([A-Z0-9]{4,16})');

  /// Run once ever, on first launch: read the Play install referrer and claim
  /// the code it carried. No-op if already checked, not installed via Play, or
  /// no ref code present. Never throws.
  Future<void> captureAndClaimOnFirstRun() async {
    final p = await SharedPreferences.getInstance();
    if (p.getBool(_kReferrerChecked) ?? false) return;
    await p.setBool(_kReferrerChecked, true); // attempt exactly once
    try {
      final details = await PlayInstallReferrer.installReferrer;
      final raw = (details.installReferrer ?? '').toUpperCase();
      final match = _codeRe.firstMatch(raw);
      if (match != null) {
        await claimManual(match.group(1)!);
      }
    } catch (_) {
      // not a Play install / referrer unavailable — ignore silently
    }
  }

  /// Claim a referral code (from install referrer or pasted by the user).
  /// Credits the new parent's welcome bonus exactly once.
  Future<ClaimOutcome> claimManual(String code) async {
    final outcome = await _claim(code);
    await Analytics.referralClaimed(outcome.name);
    return outcome;
  }

  Future<ClaimOutcome> _claim(String code) async {
    final p = await SharedPreferences.getInstance();
    if (p.getBool(_kClaimed) ?? false) return ClaimOutcome.alreadyClaimed;
    try {
      final res = await _client.claimReferral(code.trim().toUpperCase());
      if (res['ok'] == true) {
        await p.setBool(_kClaimed, true);
        await CoinsService.instance.creditBadges(const ['referral_welcome']);
        return ClaimOutcome.success;
      }
      if (res['already_claimed'] == true) {
        await p.setBool(_kClaimed, true);
        return ClaimOutcome.alreadyClaimed;
      }
      return ClaimOutcome.invalid;
    } catch (_) {
      return ClaimOutcome.error;
    }
  }

  /// Fetch this device's code + invited-count, cache the code, and credit the
  /// referrer one badge-reward per successful invite (idempotent).
  Future<ReferralInfo?> refresh() async {
    try {
      final m = await _client.getReferral();
      final code = (m['code'] as String?) ?? '';
      final invited = (m['invited_count'] as num?)?.toInt() ?? 0;
      cachedCode = code.isNotEmpty ? code : null;
      if (invited > 0) {
        await CoinsService.instance.creditBadges(
          [for (var i = 1; i <= invited; i++) 'referral_invite_$i'],
        );
      }
      return ReferralInfo(
        code: code,
        invitedCount: invited,
        shareUrl: (m['share_url'] as String?) ?? '',
      );
    } catch (_) {
      return null;
    }
  }
}
