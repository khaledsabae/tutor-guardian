/// Generic shareable "moment" card — the viral surface for every
/// emotional moment in the app (milestones, badges, quiz wins, path
/// completion, Quran memorization, weekly progress).
///
/// A square 1080×1080 card rendered off-screen via [ScreenshotController]
/// and shared as a PNG. Generalizes the original daily-tip share card so the
/// app's highest-emotion moments all become reverent, branded, shareable
/// artifacts that carry an install CTA — the core of the zero-budget
/// WhatsApp growth loop. Framed as «تذكير/نصيحة», never as a marketing pitch.
library;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
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
  });

  /// Big emoji at the top (e.g. 🤍 🌟 🕌 📖) — carries the emotional tone.
  final String emoji;

  /// Small label above the headline (e.g. «إنجاز جديد» / «تذكير» / «ما شاء الله»).
  final String eyebrow;

  /// The hero line (e.g. «أتمّ محمد أول صلاة» / «حفظ سورة الإخلاص»).
  final String headline;

  /// Optional supporting text (a dua, a tip, an encouragement).
  final String? body;

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
            const ShareCardBrandFooter(),
          ],
        ),
      ),
    );
  }
}

/// The share cards' background art.
const kShareCardBackground = 'assets/svg/art/share_bg_celebration.svg';

/// The 1080×1080 branded ground every shared card sits on: the background
/// art, a soft overlay so text stays readable, 64px of padding.
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
              // The «ورق مقصوص» ground: emerald sky, stars, hills with
              // sprouts (assets/svg/art/share_bg_celebration.svg, 360×640,
              // cropped to the square). SvgPicture parses asynchronously; the
              // capture (ShareService → captureFromWidget) re-renders until
              // nothing is dirty, so the PNG is taken after it arrives —
              // test/share_card_layout_test.dart checks the pixels.
              Positioned.fill(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: SvgPicture.asset(
                    kShareCardBackground,
                    fit: BoxFit.cover,
                    excludeFromSemantics: true,
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

/// Noor, the brand line, the install hint and the QR — the attributed install
/// driver every shared card carries (1.0.74: «نور والقناديل»).
///
/// Noor rises behind a strip of paper hills, as on the app icon (C «الطبقات»,
/// docs/brand/icon/icon_c_hills.svg). The QR still carries the install link
/// with the sharer's own referral code.
class ShareCardBrandFooter extends StatelessWidget {
  const ShareCardBrandFooter({super.key, this.qrSize = 116});

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
          const ShareCardNoorStrip(),
          const SizedBox(height: 12),
          Text(
            l10n.shareCardBrandLine,
            textAlign: TextAlign.center,
            style: GoogleFonts.cairo(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: PaperCut.ink,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            l10n.shareCardInstallHint,
            textAlign: TextAlign.center,
            style: GoogleFonts.cairo(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: PaperCut.emerald,
            ),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Dt.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: PaperCut.emerald.withValues(alpha: 0.25)),
              boxShadow: const [
                BoxShadow(color: PaperCut.ivoryShadow, offset: Offset(3, 4)),
              ],
            ),
            child: QrImageView(
              data: ShareService.installUrlFor(
                referralCode: ReferralService.cachedCode,
              ),
              size: qrSize,
              gapless: true,
              eyeStyle: const QrEyeStyle(
                eyeShape: QrEyeShape.square,
                color: PaperCut.shadow,
              ),
              dataModuleStyle: const QrDataModuleStyle(
                dataModuleShape: QrDataModuleShape.square,
                color: PaperCut.shadow,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The «ورق مقصوص» palette the footer is cut from (assets/svg/STYLE.md).
abstract final class PaperCut {
  static const emerald = Color(0xFF0F6B5C);
  static const hill = Color(0xFF12806D);
  static const hillFar = Color(0xFF0D6A5A);
  static const shadow = Color(0xFF094A40);
  static const deco = Color(0xFF13806C);
  static const ivoryShadow = Color(0xFFEADBC0);
  static const ink = Color(0xFF0F3D36);
}

/// Noor rising behind three paper hills on an emerald sheet — the footer's
/// mark, in place of the old gradient circle and icon.
///
/// Drawn in the order the paper is stacked: the sheet, the far hill, Noor,
/// then the two near hills over Noor's lower edge. Noor is an SVG and parses
/// asynchronously; the capture re-renders until nothing is dirty, so it is in
/// the PNG (test/share_card_layout_test.dart reads the pixels).
class ShareCardNoorStrip extends StatelessWidget {
  const ShareCardNoorStrip({super.key});

  static const Size size = Size(320, 92);
  static const _noor = 'assets/svg/noor/noor_happy.svg';

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size.width + 6,
      height: size.height + 7,
      child: Stack(
        children: [
          // The sheet's paper shadow: a solid offset copy, never a blur.
          Positioned(
            left: 6,
            top: 7,
            child: Container(
              width: size.width,
              height: size.height,
              decoration: BoxDecoration(
                color: PaperCut.shadow,
                borderRadius: BorderRadius.circular(24),
              ),
            ),
          ),
          Positioned(
            left: 0,
            top: 0,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(24),
              child: SizedBox.fromSize(
                size: size,
                child: Stack(
                  children: [
                    const Positioned.fill(child: ColoredBox(color: PaperCut.emerald)),
                    Positioned.fill(
                      child: CustomPaint(painter: _PaperHillsPainter(front: false)),
                    ),
                    // In its 240 box the crescent spans x 50–178, y 69–195:
                    // at 160 px that is x 33–119, y 46–130. Centre the
                    // crescent, not the box, and let the near hills cover
                    // its lower half, as on the app icon.
                    Positioned(
                      left: size.width / 2 - 76,
                      top: -38,
                      width: 160,
                      height: 160,
                      child: SvgPicture.asset(
                        _noor,
                        excludeFromSemantics: true,
                        errorBuilder: (_, _, _) => const SizedBox.shrink(),
                      ),
                    ),
                    Positioned.fill(
                      child: CustomPaint(painter: _PaperHillsPainter(front: true)),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The hills of icon C, scaled to the strip: one far hill behind Noor
/// ([front] false), two near ones in front of it — each over its own shadow.
class _PaperHillsPainter extends CustomPainter {
  _PaperHillsPainter({required this.front});

  final bool front;

  Path _hill(Size s, double base, double amp, double phase) {
    final w = s.width;
    return Path()
      ..moveTo(0, base + amp * phase)
      ..cubicTo(w * .25, base - amp, w * .45, base - amp * .4, w * .62, base)
      ..cubicTo(w * .78, base + amp * .6, w * .9, base - amp * .2, w, base - amp * phase)
      ..lineTo(w, s.height)
      ..lineTo(0, s.height)
      ..close();
  }

  void _layer(Canvas canvas, Path path, Color color) {
    canvas.drawPath(path.shift(const Offset(0, 4)), Paint()..color = PaperCut.shadow);
    canvas.drawPath(path, Paint()..color = color);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final h = size.height;
    if (!front) {
      // Two small stars of the set on the sheet, then the far hill.
      final star = Paint()..color = PaperCut.deco;
      for (final c in [Offset(size.width * .12, h * .28), Offset(size.width * .86, h * .22)]) {
        canvas.drawCircle(c, 3.2, star);
      }
      _layer(canvas, _hill(size, h * .56, 7, .6), PaperCut.hill);
      return;
    }
    _layer(canvas, _hill(size, h * .74, 6, -.4), PaperCut.hillFar);
    _layer(canvas, _hill(size, h * .9, 4, .3), PaperCut.shadow);
  }

  @override
  bool shouldRepaint(covariant _PaperHillsPainter old) => old.front != front;
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
