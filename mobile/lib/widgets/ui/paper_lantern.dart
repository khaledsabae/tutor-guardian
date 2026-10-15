/// A paper-cut lantern («ورق مقصوص», STYLE.md 2026-10-14), drawn in code.
///
/// The shape is the reference icon `icons/lantern.svg` on its 48×48 grid —
/// ring, cap, framed pane and foot, each with its solid paper shadow offset
/// (+1.5, +2) — so no SVG renderer is needed and the colours come from the
/// live palette ([AppPalette.paperIvory] and friends).
///
/// Unlit, it is plain quiet paper: the same ivory pane, the same frame. It is
/// never greyed, faded or crossed — an unlit lantern is not a missed one
/// (NOOR_WAL_QANADIL_PLAN, fixed rules). Lit, a gold flame stands in the pane
/// and two flat paper discs glow behind it; the change is one short fade,
/// none at all under reduced motion, and nothing loops.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/motion.dart';
import '../../theme/app_colors.dart';

class PaperLantern extends StatelessWidget {
  const PaperLantern({
    super.key,
    required this.lit,
    this.height = 40,
    this.lightDuration = const Duration(milliseconds: 420),
  });

  /// Whether the flame burns.
  final bool lit;

  /// The lantern's height; it is three quarters as wide.
  final double height;

  /// How long the flame takes to rise when [lit] turns on (the week's
  /// lanterns on «اليوم» light in 350ms). Ignored under reduced motion.
  final Duration lightDuration;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ExcludeSemantics(
      child: TweenAnimationBuilder<double>(
        tween: Tween(end: lit ? 1 : 0),
        duration: reduceMotion(context) ? Duration.zero : lightDuration,
        curve: Curves.easeOutCubic,
        builder: (context, glow, _) => SizedBox(
          width: height * .75,
          height: height,
          child: CustomPaint(
            painter: PaperLanternPainter(
              glow: glow,
              paper: c.paperIvory,
              frame: c.paperEmerald,
              shadow: c.paperShadow,
              flame: c.paperGold,
            ),
          ),
        ),
      ),
    );
  }
}

/// Paints the lantern; [glow] runs 0 (unlit) → 1 (lit).
class PaperLanternPainter extends CustomPainter {
  const PaperLanternPainter({
    required this.glow,
    required this.paper,
    required this.frame,
    required this.shadow,
    required this.flame,
  });

  final double glow;
  final Color paper;
  final Color frame;
  final Color shadow;
  final Color flame;

  static const double _grid = 48;

  @override
  void paint(Canvas canvas, Size size) {
    final scale = size.height / _grid;
    if (scale <= 0) return;
    canvas.save();
    // Centre the 48-wide grid in a box three quarters as wide.
    canvas.translate((size.width - _grid * scale) / 2, 0);
    canvas.scale(scale);
    // The reference group's own offset, which centres lantern and shadow.
    canvas.translate(-.8, -.2);

    // The light behind the paper: two flat discs, no blur (paper, not glass).
    if (glow > 0) {
      canvas.drawCircle(
        const Offset(24, 27),
        17.5 * (.8 + .2 * glow),
        Paint()..color = flame.withValues(alpha: .2 * glow),
      );
      canvas.drawCircle(
        const Offset(24, 27),
        13 * (.8 + .2 * glow),
        Paint()..color = flame.withValues(alpha: .32 * glow),
      );
    }

    canvas.save();
    canvas.translate(1.5, 2);
    _frame(canvas, shadow);
    canvas.restore();
    _frame(canvas, frame);

    canvas.drawPath(_body, Paint()..color = paper);
    if (glow > 0) {
      canvas.save();
      // The flame rises from the pane's floor as it lights.
      final s = .55 + .45 * glow;
      canvas.translate(24, 33.6);
      canvas.scale(s);
      canvas.translate(-24, -33.6);
      canvas.drawPath(
        _flame,
        Paint()..color = flame.withValues(alpha: math.min(1, glow * 1.4)),
      );
      canvas.restore();
    }
    canvas.restore();
  }

  /// Ring, cap, pane frame and foot, all in one colour — drawn once as the
  /// shadow, offset, and once as the paper itself.
  void _frame(Canvas canvas, Color color) {
    final stroke = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round;
    final fill = Paint()..color = color;
    canvas.drawCircle(const Offset(24, 7.5), 2.6, stroke..strokeWidth = 2.2);
    canvas.drawPath(_cap, fill);
    canvas.drawPath(_cap, stroke..strokeWidth = 2);
    canvas.drawPath(_body, fill);
    canvas.drawPath(_body, stroke..strokeWidth = 5);
    canvas.drawPath(_foot, fill);
    canvas.drawPath(_foot, stroke..strokeWidth = 2);
  }

  static final Path _cap = Path()
    ..moveTo(14.5, 17.5)
    ..cubicTo(14.5, 13.5, 20, 12.5, 24, 9.5)
    ..cubicTo(28, 12.5, 33.5, 13.5, 33.5, 17.5)
    ..close();

  static final Path _body = Path()
    ..moveTo(16, 19.5)
    ..lineTo(32, 19.5)
    ..lineTo(35, 27)
    ..lineTo(31, 35)
    ..lineTo(17, 35)
    ..lineTo(13, 27)
    ..close();

  static final Path _foot = Path()
    ..moveTo(18, 37)
    ..lineTo(30, 37)
    ..lineTo(28, 41.5)
    ..lineTo(20, 41.5)
    ..close();

  static final Path _flame = Path()
    ..moveTo(24, 20.8)
    ..cubicTo(28, 24.6, 28.6, 27.2, 28.6, 29)
    ..arcToPoint(const Offset(19.4, 29), radius: const Radius.circular(4.6))
    ..cubicTo(19.4, 27.2, 20, 24.6, 24, 20.8)
    ..close();

  @override
  bool shouldRepaint(PaperLanternPainter old) =>
      old.glow != glow ||
      old.paper != paper ||
      old.frame != frame ||
      old.shadow != shadow ||
      old.flame != flame;
}
