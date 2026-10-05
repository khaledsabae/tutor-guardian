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

import '../../l10n/content_direction.dart';
import '../../l10n/l10n_global.dart';
import '../../theme/app_theme.dart';
import '../referral/referral_service.dart';
import 'share_service.dart';
import '../../theme/design_tokens.dart';

/// One moment as a parent shares it: the line that travels with the image,
/// and the card the image is captured from.
///
/// Each surface builds its moment with a plain function of the app's strings
/// and the content (e.g. `coachTipShare`), so a test can read every word that
/// would leave the phone, in each language, without the share plugin.
typedef MomentShare = ({String message, ShareableMomentCard card});

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
    // The capture tree reads left to right whatever the language, so the card
    // sets its own direction: the app's, for the app's words — the label and
    // the footer — and for the headline and body, which can be content in
    // another language (a path's title, a parent's note), the direction of
    // their own letters.
    final appDirection = directionOfLanguage(AppL10n.current.localeName);
    TextDirection ownDirection(String text) =>
        ContentDirectionality.resolve(text: text, fallback: appDirection);
    return Directionality(
      textDirection: appDirection,
      child: ShareCardFrame(
        // Deterministic, flex-free layout. ScreenshotController's
        // captureFromWidget renders in a detached tree that mishandles
        // Expanded/Flexible/Spacer/SingleChildScrollView (per its own
        // docs), which previously starved/clipped the [body]. Plain
        // Text with a maxLines guard renders reliably; [ShareService]
        // pins the canvas to 1080×1080 so this always fits.
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 116)),
            const SizedBox(height: 22),
            ShareCardEyebrow(eyebrow),
            const SizedBox(height: 28),
            Text(
              headline,
              textAlign: TextAlign.center,
              textDirection: ownDirection(headline),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.cairo(
                fontSize: 44,
                fontWeight: FontWeight.w800,
                color: AppTheme.textPrimary,
                height: 1.3,
              ),
            ),
            if (body != null && body!.trim().isNotEmpty) ...[
              const SizedBox(height: 26),
              Text(
                body!,
                textAlign: TextAlign.center,
                textDirection: ownDirection(body!),
                maxLines: 6,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.cairo(
                  fontSize: 30,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                  height: 1.55,
                ),
              ),
            ],
            const SizedBox(height: 40),
            ShareCardBrandFooter(icon: icon),
          ],
        ),
      ),
    );
  }
}

/// The 1080×1080 branded ground every shared card sits on: the generated
/// background art, a soft overlay so text stays readable, 64px of padding.
///
/// Shared so a new kind of card (the «رمضان عائلتنا» recap) carries exactly
/// the same frame and QR as every other moment, rather than a near-copy.
class ShareCardFrame extends StatelessWidget {
  const ShareCardFrame({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    const size = ShareableMomentCard.size;
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
              // Unified brand background — logo-centric decorative frame
              // (crescent + book + sprout + star) generated via Recraft V3.
              Positioned.fill(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: Image.asset(
                    'assets/images/generated/share_bg_celebration.webp',
                    fit: BoxFit.cover,
                    errorBuilder: (_, _, _) => CustomPaint(
                      painter: _PatternPainter(),
                      size: size,
                    ),
                  ),
                ),
              ),
              // Soft gradient overlay so text stays readable on the art.
              Positioned.fill(
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        AppTheme.surface.withValues(alpha: 0.25),
                        AppTheme.surface.withValues(alpha: 0.82),
                      ],
                      stops: const [0.0, 0.65],
                    ),
                  ),
                ),
              ),
              // The content gets the whole card less the padding, so a
              // Column in it is as wide as the card and centres each line on
              // the card's centre. Left to the Stack's defaults — loose,
              // top-start — it was only as wide as its widest line and sat at
              // the start edge whenever no line wrapped.
              Positioned.fill(
                child: Padding(
                  padding: const EdgeInsets.all(64),
                  child: child,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The small label above a card's headline.
class ShareCardEyebrow extends StatelessWidget {
  const ShareCardEyebrow(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
      decoration: BoxDecoration(
        color: AppTheme.primary.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Text(
        text,
        style: GoogleFonts.cairo(
          fontSize: 22,
          fontWeight: FontWeight.w700,
          color: AppTheme.primary,
        ),
      ),
    );
  }
}

/// Brand line, install CTA and the QR — the attributed install driver every
/// shared card carries.
class ShareCardBrandFooter extends StatelessWidget {
  const ShareCardBrandFooter({super.key, this.icon = Icons.auto_awesome, this.qrSize = 116});

  final IconData icon;
  final double qrSize;

  @override
  Widget build(BuildContext context) {
    // Cards are captured off-tree, where there is no Localizations ancestor —
    // AppLocalizations.of would throw and the error box would be shared. The
    // app keeps AppL10n.current in step with its language.
    final l10n = AppL10n.current;
    // Its words are the app's, so is their direction — not the capture
    // tree's, which is always left to right, nor the content's above it
    // (the Ramadan card reads in its headline's direction).
    return Directionality(
      textDirection: directionOfLanguage(l10n.localeName),
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
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
            l10n.shareCardBrandLine,
            style: GoogleFonts.cairo(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: AppTheme.primary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.shareCardInstallHint,
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
              color: Dt.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.primary.withValues(alpha: 0.15)),
            ),
            child: QrImageView(
              data: ShareService.installUrlFor(
                referralCode: ReferralService.cachedCode,
              ),
              size: qrSize,
              gapless: true,
              eyeStyle: QrEyeStyle(
                eyeShape: QrEyeShape.square,
                color: AppTheme.primary,
              ),
              dataModuleStyle: QrDataModuleStyle(
                dataModuleShape: QrDataModuleShape.square,
                color: AppTheme.primary,
              ),
            ),
          ),
        ],
      ),
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
