/// «ادعُ صديقًا» — the dedicated referral surface (Phase 0.2).
///
/// Framed as «صدقة جارية / دلالة على خير», not a marketing pitch. Shows the
/// parent's referral code + how many parents they've already brought, a big
/// WhatsApp-first share button, and a manual code-entry box for parents who
/// heard about the app but didn't install through a link.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/analytics.dart';
import '../../theme/app_theme.dart';
import '../share/share_service.dart';
import '../share/shareable_moment_card.dart';
import 'referral_service.dart';

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
      final ok = await ShareService.shareMomentCard(
        fileTag: 'invite_${info.code}',
        referralCode: info.code,
        message: 'جرّب «المربّي» معايا 🤍 — تطبيق تربية إسلامي ذكي، '
            'مجاني تمامًا بلا إعلانات. دلالة على الخير صدقة 🌿',
        card: const ShareableMomentCard(
          emoji: '🤍',
          eyebrow: 'دعوة لوجه الله',
          headline: 'جرّب «المربّي» معايا',
          body: 'تطبيق تربية إسلامي ذكي يجاوبك بثقة — مجاني بلا إعلانات.\n'
              '«الدالُّ على الخير كفاعله»',
          icon: Icons.favorite_outline,
        ),
      );
      if (!ok && mounted) {
        // Fallback: plain text share if image capture/share sheet fails.
        await ShareService.shareWhatsApp(
          'جرّب «المربّي» معايا 🤍 — تطبيق تربية إسلامي ذكي، '
          'مجاني تمامًا بلا إعلانات. دلالة على الخير صدقة 🌿',
          referralCode: info.code,
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تعذّر المشاركة: $e')),
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
    final msg = switch (outcome) {
      ClaimOutcome.success => 'تمّت إضافة الكود — جزى الله صديقك خيرًا 🤍 (+مكافأة)',
      ClaimOutcome.alreadyClaimed => 'سبق استخدام كود إحالة على هذا الجهاز.',
      ClaimOutcome.invalid => 'كود غير صالح، تأكّد منه.',
      ClaimOutcome.error => 'تعذّر الاتصال، حاول لاحقًا.',
    };
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    if (outcome == ClaimOutcome.success) _codeCtrl.clear();
  }

  @override
  Widget build(BuildContext context) {
    final info = _info;
    return Scaffold(
      appBar: AppBar(title: const Text('ادعُ صديقًا 🤍')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'دلالتك صديقًا على «المربّي» صدقة جارية — كل ما ينفع به '
                    'طفله في ميزان حسناتك بإذن الله 🌿',
                    style: TextStyle(fontSize: 15, height: 1.7),
                  ),
                  const SizedBox(height: 24),
                  if (info != null) _codeCard(info),
                  const SizedBox(height: 24),
                  FilledButton.icon(
                    onPressed: info == null || _sharing ? null : _share,
                    icon: const Icon(Icons.share),
                    label: Text(_sharing ? 'جاري التحضير…' : 'شارك الدعوة'),
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      backgroundColor: AppTheme.primary,
                    ),
                  ),
                  const SizedBox(height: 32),
                  const Divider(),
                  const SizedBox(height: 12),
                  const Text('عندك كود من صديق؟',
                      style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _codeCtrl,
                          textCapitalization: TextCapitalization.characters,
                          decoration: const InputDecoration(
                            hintText: 'مثال: SMDYVE',
                            border: OutlineInputBorder(),
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                          onPressed: _claim, child: const Text('تفعيل')),
                    ],
                  ),
                ],
              ),
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
          const Text('كود الإحالة الخاص بك',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: () {
              Clipboard.setData(ClipboardData(text: info.code));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('تم نسخ الكود')),
              );
            },
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  info.code,
                  style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 4,
                    color: AppTheme.primary,
                  ),
                ),
                const SizedBox(width: 8),
                const Icon(Icons.copy, size: 18, color: AppTheme.primary),
              ],
            ),
          ),
          if (info.invitedCount > 0) ...[
            const SizedBox(height: 12),
            Text(
              'دعوت ${info.invitedCount} — جزاك الله خيرًا 🤍',
              style: const TextStyle(
                  fontWeight: FontWeight.w600, color: AppTheme.primary),
            ),
          ],
        ],
      ),
    );
  }
}
