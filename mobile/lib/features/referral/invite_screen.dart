/// «أجرك الجاري» — the dedicated referral surface (Phase 0.2, reframed 2026-10).
///
/// Leads with what the parent's sharing has already done — «وصل المربّي إلى
/// N أسرة بسببك» — because the motive this audience acts on is the ongoing
/// reward of guiding a family to good, not the coins. The coins stay, one
/// muted line at the bottom. Below the count: the share button (WhatsApp-first
/// via the share sheet), the parent's code, and a box for entering a friend's
/// code by hand.
///
/// No hadith is quoted here. The share card used to carry «الدالُّ على الخير
/// كفاعله», which is not in al-Bukhari or Muslim; the reward is phrased as a
/// hope («نرجو أن يكون لك مثل أجرها»), never as a citation.
///
/// TODO(hadith-numbering): the closely related «مَن دلَّ على خيرٍ فله مثلُ أجرِ
/// فاعله» IS in Sahih Muslim (1893 in the common Abd al-Baqi numbering), but
/// the pre-commit hadith guard's index numbers Muslim differently (Darussalam)
/// and is being fixed separately. Once the guard accepts Abd al-Baqi numbers,
/// this screen may quote it with book + number — not before.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/analytics.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../widgets/ui/community_proof_card.dart';
import '../coins/coins_service.dart';
import '../share/share_service.dart';
import '../share/shareable_moment_card.dart';
import 'referral_service.dart';
import 'package:almorabbi/widgets/ui/loading_view.dart';

class InviteScreen extends StatefulWidget {
  const InviteScreen({super.key});

  @override
  State<InviteScreen> createState() => _InviteScreenState();
}

class _InviteScreenState extends State<InviteScreen> {
  ReferralInfo? _info;
  bool _loading = true;
  bool _sharing = false;
  final _codeCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    Analytics.inviteOpened();
    _load();
  }

  @override
  void dispose() {
    _codeCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final info = await ReferralService.instance.refresh();
    if (mounted) {
      setState(() {
        _info = info;
        _loading = false;
      });
    }
  }

  Future<void> _share() async {
    final info = _info;
    if (info == null || _sharing) return;
    setState(() => _sharing = true);
    Analytics.inviteShared();
    try {
      final l10n = AppLocalizations.of(context);
      final ok = await ShareService.shareMomentCard(
        fileTag: 'invite_${info.code}',
        referralCode: info.code,
        message: l10n.inviteShareMessage,
        card: ShareableMomentCard(
          emoji: '🤍',
          eyebrow: l10n.inviteCardEyebrow,
          headline: l10n.inviteCardHeadline,
          body: l10n.inviteCardBody,
          icon: Icons.favorite_outline,
        ),
      );
      if (!ok && mounted) {
        // Fallback: plain text share if image capture/share sheet fails.
        await ShareService.shareWhatsApp(
          l10n.inviteShareMessage,
          referralCode: info.code,
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).inviteError)),
        );
      }
    } finally {
      if (mounted) setState(() => _sharing = false);
    }
  }

  Future<void> _claim() async {
    final code = _codeCtrl.text.trim();
    if (code.isEmpty) return;
    final outcome = await ReferralService.instance.claimManual(code);
    if (!mounted) return;
    final l10n = AppLocalizations.of(context);
    final msg = switch (outcome) {
      ClaimOutcome.success => l10n.inviteSuccess,
      ClaimOutcome.alreadyClaimed => l10n.inviteAlreadyClaimed,
      ClaimOutcome.invalid => l10n.inviteInvalidCode,
      ClaimOutcome.error => l10n.inviteError,
    };
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    if (outcome == ClaimOutcome.success) _codeCtrl.clear();
  }

  @override
  Widget build(BuildContext context) {
    final info = _info;
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.inviteReachedTitle)),
      body: _loading
          ? const LoadingView(count: 2, itemHeight: 160)
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // The count leads. Without it (offline) the screen still
                  // works: description, share, code entry.
                  if (info != null) ...[
                    _reachedCard(info),
                    const SizedBox(height: 20),
                  ],
                  Text(
                    l10n.inviteDesc,
                    style: const TextStyle(fontSize: 15, height: 1.7),
                  ),
                  const SizedBox(height: 16),
                  // Social proof persuades someone deciding whether to vouch
                  // for the app — it did nothing on the home screen, where the
                  // reader is already a user. It hides itself until the numbers
                  // are large enough to be persuasive.
                  const CommunityProofCard(),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: info == null || _sharing ? null : _share,
                    icon: const Icon(Icons.share),
                    label: Text(_sharing ? l10n.inviteSharePreparing : l10n.inviteShareBtn),
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      backgroundColor: AppTheme.primary,
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (info != null) _codeCard(info),
                  if (info != null) ...[
                    const SizedBox(height: 12),
                    // What this device actually credits — one badge reward
                    // each side (referral_welcome / referral_invite_N), under
                    // the daily cap — not the server's reward_coins, which
                    // the client has never paid out.
                    Text(
                      l10n.inviteCoinsNote(CoinsService.badgeReward),
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 12, color: AppTheme.textMuted),
                    ),
                  ],
                  const SizedBox(height: 32),
                  const Divider(),
                  const SizedBox(height: 12),
                  Text(l10n.inviteHaveCode,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _codeCtrl,
                          textCapitalization: TextCapitalization.characters,
                          decoration: InputDecoration(
                            hintText: l10n.inviteCodeHint,
                            border: const OutlineInputBorder(),
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                          onPressed: _claim, child: Text(l10n.inviteActivate)),
                    ],
                  ),
                ],
              ),
            ),
    );
  }

  /// «وصل المربّي إلى N أسرة بسببك» — the reason to share, stated as a fact
  /// about what sharing has already done.
  Widget _reachedCard(ReferralInfo info) {
    final l10n = AppLocalizations.of(context);
    final n = info.invitedCount;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.primary.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.primary.withValues(alpha: 0.25)),
      ),
      child: Column(
        children: [
          if (n > 0)
            Text(
              '$n',
              style: TextStyle(
                fontSize: 44,
                fontWeight: FontWeight.w900,
                color: AppTheme.primary,
                height: 1.1,
              ),
            )
          else
            const Text('🌱', style: TextStyle(fontSize: 36)),
          const SizedBox(height: 8),
          Text(
            n > 0 ? l10n.inviteReachedCount(n) : l10n.inviteReachedNone,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: n > 0 ? 17 : 15,
              fontWeight: n > 0 ? FontWeight.w800 : FontWeight.w600,
              color: AppTheme.textPrimary,
              height: 1.6,
            ),
          ),
          if (n > 0) ...[
            const SizedBox(height: 8),
            Text(
              l10n.inviteReachedHint,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.textSecondary,
                height: 1.6,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _codeCard(ReferralInfo info) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primary.withValues(alpha: 0.10),
            AppTheme.primary.withValues(alpha: 0.04),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Text(AppLocalizations.of(context).inviteYourCode,
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 8),
          Semantics(
            button: true,
            hint: AppLocalizations.of(context).a11yCopyCode,
            child: GestureDetector(
            onTap: () {
              Clipboard.setData(ClipboardData(text: info.code));
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(AppLocalizations.of(context).inviteCodeCopied)),
              );
            },
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  info.code,
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 4,
                    color: AppTheme.primary,
                  ),
                ),
                const SizedBox(width: 8),
                Icon(Icons.copy, size: 18, color: AppTheme.primary),
              ],
            ),
          ),
        ),
        ],
      ),
    );
  }
}
