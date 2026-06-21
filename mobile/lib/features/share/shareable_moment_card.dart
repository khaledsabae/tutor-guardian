/// Generic shareable "moment" card — the viral surface for every
/// emotional moment in the app (milestones, badges, quiz wins, path
/// completion, Quran memorization, weekly progress).
///
/// A square 1080×1080 card rendered off-screen via [ScreenshotController]
/// and shared as a PNG. Generalizes the original [ShareableTipCard] so the
/// app's highest-emotion moments all become reverent, branded, shareable
/// artifacts that carry an install CTA — the core of the zero-budget
/// WhatsApp growth loop. Framed as «تذكير/نصيحة», never as a marketing pitch.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../theme/app_theme.dart';
import '../referral/referral_service.dart';
import 'share_service.dart';

class ShareableMomentCard extends StatelessWidget {
  const ShareableMomentCard({
    super.key,
    required this.emoji,
    required this.eyebrow,
    required this.headline,
    this.body,
    this.icon = Icons.auto_awesome,
  });

  /// Big emoji at the top (e.g. 🤍 🌟 🕌 📖) — carries the emotional tone.
  final String emoji;

  /// Small label above the headline (e.g. «إنجاز جديد» / «تذكير» / «ما شاء الله»).
  final String eyebrow;

  /// The hero line (e.g. «أتمّ محمد أول صلاة» / «حفظ سورة الإخلاص»).
  final String headline;

  /// Optional supporting text (a dua, a tip, an encouragement).
  final String? body;

  /// Footer brand icon.
  final IconData icon;

  static const Size size = Size(1080, 1080);

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size.width,
      height: size.height,
      child: RepaintBoundary(
        child: Container(
          width: size.width,
          height: size.height,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
              colors: [
                AppTheme.primary.withValues(alpha: 0.08),
                AppTheme.surface,
              ],
            ),
            borderRadius: BorderRadius.circular(24),
          ),
          child: Stack(
            children: [
              Positioned.fill(
                child: CustomPaint(painter: _PatternPainter()),
              ),
              Padding(
                padding: const EdgeInsets.all(64),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(emoji, style: const TextStyle(fontSize: 120)),
                    const SizedBox(height: 24),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Text(
                        eyebrow,
                        style: GoogleFonts.cairo(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primary,
                        ),
                      ),
                    ),
                    const SizedBox(height: 32),
                    Text(
                      headline,
                      textAlign: TextAlign.center,
                      style: GoogleFonts.cairo(
                        fontSize: 46,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.textPrimary,
                        height: 1.35,
                      ),
                    ),
                    if (body != null && body!.trim().isNotEmpty) ...[
                      const SizedBox(height: 28),
                      Flexible(
                        child: SingleChildScrollView(
                          child: Text(
                            body!,
                            textAlign: TextAlign.center,
                            style: GoogleFonts.cairo(
                              fontSize: 26,
                              fontWeight: FontWeight.w500,
                              color: AppTheme.textSecondary,
                              height: 1.6,
                            ),
                          ),
                        ),
                      ),
                    ],
                    const Spacer(),
                    _brandFooter(),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _brandFooter() {
    return Column(
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [AppTheme.primary, AppTheme.accent],
            ),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: Colors.white, size: 32),
        ),
        const SizedBox(height: 14),
        Text(
          'المربّي — شريكك في رحلة التربية',
          style: GoogleFonts.cairo(
            fontSize: 24,
            fontWeight: FontWeight.w700,
            color: AppTheme.primary,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '📲 مجانًا لوجه الله — امسح الكود أو ابحث: «المربّي»',
          textAlign: TextAlign.center,
          style: GoogleFonts.cairo(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.primary,
          ),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.primary.withValues(alpha: 0.15)),
          ),
          child: QrImageView(
            data: ShareService.installUrlFor(
              referralCode: ReferralService.cachedCode,
            ),
            size: 116,
            gapless: true,
            eyeStyle: const QrEyeStyle(
              eyeShape: QrEyeShape.square,
              color: AppTheme.primary,
            ),
            dataModuleStyle: const QrDataModuleStyle(
              dataModuleShape: QrDataModuleShape.square,
              color: AppTheme.primary,
            ),
          ),
        ),
      ],
    );
  }
}

class _PatternPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppTheme.primary.withValues(alpha: 0.03)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    const spacing = 80.0;
    const radius = 40.0;
    for (double x = -radius; x < size.width + radius; x += spacing) {
      for (double y = -radius; y < size.height + radius; y += spacing) {
        canvas.drawCircle(Offset(x, y), radius, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
