/// Shareable daily tip card — P1 launch item #2 (mobile-only).
///
/// A beautiful, square card (1080×1080 logical) that renders
/// the daily tip text with the app name and branding, designed
/// to be captured as a PNG via [ScreenshotController] and shared
/// via [share_plus].
///
/// The card uses the app's brand colors (AppTheme.primary = 0xFF1A5F7A)
/// and Arabic-friendly Cairo typography.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../theme/app_theme.dart';
import '../data/models.dart';

/// A shareable daily tip card widget.
///
/// This widget is designed to be rendered off-screen via
/// [ScreenshotController] and then shared as a PNG image.
/// It should NOT be used directly in the visible UI — use
/// [DailyTipCard] for that.
class ShareableTipCard extends StatelessWidget {
  const ShareableTipCard({
    super.key,
    required this.tip,
    required this.childName,
  });

  final DailyTip tip;
  final String childName;

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
            boxShadow: [
              BoxShadow(
                color: AppTheme.primary.withValues(alpha: 0.15),
                blurRadius: 40,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Stack(
            children: [
              _buildPattern(),
              Padding(
                padding: const EdgeInsets.all(48),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Container(
                      width: 88,
                      height: 88,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [AppTheme.primary, AppTheme.accent],
                        ),
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: AppTheme.primary.withValues(alpha: 0.3),
                            blurRadius: 16,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: const Icon(Icons.wb_sunny_outlined, color: Colors.white, size: 40),
                    ),
                    const SizedBox(height: 28),
                    Text(
                      'نصيحة اليوم لـ $childName',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.cairo(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.primary,
                        height: 1.3,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        tip.timeOfDayLabel,
                        style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.primary),
                      ),
                    ),
                    const SizedBox(height: 36),
                    Flexible(
                      child: SingleChildScrollView(
                        child: Text(
                          tip.text,
                          textAlign: TextAlign.center,
                          style: GoogleFonts.cairo(fontSize: 24, fontWeight: FontWeight.w500, color: AppTheme.textPrimary, height: 1.6),
                        ),
                      ),
                    ),
                    const SizedBox(height: 48),
                    Column(
                      children: [
                        Container(
                          width: 56,
                          height: 56,
                          decoration: const BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [AppTheme.primary, AppTheme.accent],
                            ),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.psychology_outlined, color: Colors.white, size: 28),
                        ),
                        const SizedBox(height: 16),
                        Text('المربي الذكي', style: GoogleFonts.cairo(fontSize: 22, fontWeight: FontWeight.w700, color: AppTheme.primary)),
                        const SizedBox(height: 4),
                        Text('شريكك في رحلة التربية', style: GoogleFonts.cairo(fontSize: 14, fontWeight: FontWeight.w400, color: AppTheme.textSecondary)),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPattern() {
    return Positioned.fill(
      child: CustomPaint(painter: _ShareCardPatternPainter()),
    );
  }
}

class _ShareCardPatternPainter extends CustomPainter {
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
