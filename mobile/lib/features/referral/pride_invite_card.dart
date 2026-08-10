/// «ادعُ صديقًا» at pride moments only (§6.4 growth plan).
///
/// The referral ask fires when the parent has something to be proud of —
/// a ≥7-day streak — instead of nagging from a static surface. Framing is
/// «الدلالة على الخير صدقة جارية», consistent with [InviteScreen].
///
/// Frequency rules (persisted in SharedPreferences):
///   * Visible only when `streakDays >= 7`.
///   * Shown once per 7-day tier: dismissing (or tapping) at streak 7–13
///     hides it until the streak reaches 14, then 21, and so on. Tiers are
///     monotonic — after acting at 14, a rebuilt streak stays quiet until
///     it surpasses that tier, so the ask can never become a nag.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/analytics.dart';
import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import 'invite_screen.dart';

class PrideInviteCard extends StatefulWidget {
  const PrideInviteCard({super.key, required this.streakDays});

  final int streakDays;

  /// The streak value at which the card was last acted on (dismissed or
  /// tapped). `-1` (unset) means it has never been shown.
  static const prefsKey = 'prideInvite.lastActedStreak';

  @override
  State<PrideInviteCard> createState() => _PrideInviteCardState();
}

class _PrideInviteCardState extends State<PrideInviteCard> {
  SharedPreferences? _prefs;
  bool _visible = false;
  bool _shownLogged = false;

  @override
  void initState() {
    super.initState();
    _decide();
  }

  @override
  void didUpdateWidget(PrideInviteCard old) {
    super.didUpdateWidget(old);
    if (old.streakDays != widget.streakDays) _decide();
  }

  Future<void> _decide() async {
    final prefs = _prefs ??= await SharedPreferences.getInstance();
    final lastActed = prefs.getInt(PrideInviteCard.prefsKey) ?? -1;
    final visible = widget.streakDays >= 7 &&
        widget.streakDays ~/ 7 > (lastActed < 0 ? 0 : lastActed ~/ 7);
    if (!mounted) return;
    setState(() => _visible = visible);
    if (visible && !_shownLogged) {
      _shownLogged = true;
      unawaited(Analytics.prideInviteShown('streak'));
    }
  }

  Future<void> _act({required bool openInvite}) async {
    final prefs = _prefs ??= await SharedPreferences.getInstance();
    await prefs.setInt(PrideInviteCard.prefsKey, widget.streakDays);
    if (!mounted) return;
    setState(() => _visible = false);
    if (openInvite) {
      unawaited(Analytics.prideInviteTapped('streak'));
      await Navigator.of(context).push(AppRoutes.invite());
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_visible) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    return Container(
      margin: const EdgeInsets.only(top: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Dt.primary.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(Dt.rCard),
        border: Border.all(color: Dt.primary.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('🎉', style: TextStyle(fontSize: 26)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  l10n.prideStreakTitle(widget.streakDays),
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 15,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            l10n.prideStreakBody,
            style: const TextStyle(
              color: AppTheme.textSecondary,
              fontSize: 13.5,
              height: 1.6,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: () => _act(openInvite: true),
                  icon: const Icon(Icons.volunteer_activism, size: 18),
                  label: Text(l10n.prideInviteCta),
                ),
              ),
              const SizedBox(width: 8),
              TextButton(
                onPressed: () => _act(openInvite: false),
                child: Text(
                  l10n.prideLater,
                  style: const TextStyle(color: AppTheme.textMuted),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
