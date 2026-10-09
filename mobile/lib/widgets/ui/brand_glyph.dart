/// BrandGlyph — the app's icon set, drawn in code («جولة الحرفة», item 1).
///
/// No emoji as graphics: a colored Noto emoji is a foreign illustration
/// style slamming into a night-sky, crescent, thin-line-plant identity, and
/// it renders differently on every vendor. Every glyph here is a
/// [CustomPainter] stroked in the app's thin-line language — the same
/// `max(1.2, ~3.5%)` round-capped strokes the Noor halo and the bedtime
/// sky use — so an icon is brand-colored in both palettes and identical on
/// every device.
///
/// Drawn on a 24×24 design grid and scaled to [BrandGlyph.size]; the stroke
/// scales with it. Static by design: no animation, no repeat.
library;

import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

/// The icon catalogue. Grows here, never as a new ad-hoc painter elsewhere.
enum BrandIcon {
  /// The brand mark — a thin crescent, opening toward the top-right.
  crescent,

  /// Full moon with craters (bedtime surfaces).
  fullMoon,

  /// Eight-point sparkle star.
  star,

  /// Ramadan fanous: ring, cap, glass body, flame, foot.
  lantern,

  /// Open book with a centre spine (lessons, library).
  openBook,

  /// A stem with paired leaves (growth, review, living things).
  sprig,

  /// Envelope (invites, share).
  envelope,

  /// Gift box with lid, ribbon and bow (rewards).
  gift,

  /// Speech bubble with tail (chat, questions).
  speechBubble,

  /// A winding trail from a start dot to a lit destination (paths).
  path,

  /// Pointed Islamic arch door with sill and handle (gates, milestones).
  door,

  /// A lit dot with rays — a small light (tips, ideas in the abstract).
  lightDot,

  /// Drawn coin: two concentric circles (currency). Readable at 16px.
  coin,

  /// Globe: circle, meridian and equator (language, world).
  globe,

  /// Flame (login streak).
  flame,

  /// Medal with ribbons (badges, achievements).
  medal,
}

/// One thin-line brand icon.
///
/// ```dart
/// BrandGlyph(BrandIcon.gift, size: 24)
/// ```
///
/// The colour defaults to [AppPalette.primary] through `context.colors`, so
/// the glyph follows the live palette in light and dark. Pass [color] to
/// take another role (`context.colors.accent` for the gold coin, etc.).
///
/// Glyphs are decorative by default — the text next to one carries the
/// meaning. Give a [semanticLabel] only when the glyph is the meaning.
class BrandGlyph extends StatelessWidget {
  const BrandGlyph(
    this.icon, {
    super.key,
    this.size = 24,
    this.color,
    this.semanticLabel,
  });

  final BrandIcon icon;

  /// Logical pixels; the design grid is 24 and everything scales linearly.
  final double size;

  final Color? color;

  /// When null (the default) the glyph paints with no semantics node of its
  /// own, exactly like the emoji `Text`s it replaces did not carry a label.
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final resolved = color ?? context.colors.primary;
    Widget glyph = SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _BrandGlyphPainter(
          icon,
          resolved,
          strokeWidth: _strokeFor(size),
        ),
      ),
    );
    if (semanticLabel != null) {
      glyph = Semantics(label: semanticLabel, child: glyph);
    }
    return glyph;
  }

  /// The thin-line weight: ~6% of the glyph, floored so a 16px coin keeps
  /// its two circles distinct instead of fusing.
  static double _strokeFor(double size) => math.max(1.15, size * 0.062);
}

/// Squircle tile with a brand glyph — the drawn successor to [EmojiHero],
/// for the hero spots on coloured gradient cards.
class GlyphHero extends StatelessWidget {
  const GlyphHero(
    this.icon, {
    super.key,
    this.size = 56,
    this.color,
    this.background = const Color(0x33FFFFFF),
    this.radius = 18,
  });

  final BrandIcon icon;
  final double size;

  /// Glyph colour; defaults to `onPrimary` — heroes sit on brand gradients.
  final Color? color;
  final Color background;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(radius),
      ),
      child: BrandGlyph(
        icon,
        size: size * .62,
        color: color ?? context.colors.onPrimary,
      ),
    );
  }
}

class _BrandGlyphPainter extends CustomPainter {
  _BrandGlyphPainter(this.icon, this.color, {required this.strokeWidth});

  final BrandIcon icon;
  final Color color;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final scale = size.shortestSide / 24;
    if (scale <= 0) return;
    canvas.save();
    canvas.scale(scale);
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth / scale
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..color = color;
    final dot = Paint()..color = color; // filled accents

    switch (icon) {
      case BrandIcon.crescent:
        canvas.drawPath(_crescent(), paint);
      case BrandIcon.fullMoon:
        canvas.drawCircle(const Offset(12, 12), 8.3, paint);
        canvas.drawCircle(const Offset(9.4, 10.2), 1.7, paint);
        canvas.drawCircle(const Offset(14.6, 14.2), 1.1, paint);
      case BrandIcon.star:
        canvas.drawPath(_sparkle(), paint);
      case BrandIcon.lantern:
        canvas.drawCircle(const Offset(12, 3.1), 1.0, paint); // ring
        canvas.drawPath(_lanternCap(), paint);
        canvas.drawPath(_lanternBody(), paint);
        canvas.drawCircle(const Offset(12, 11.9), 1.7, paint); // flame
        canvas.drawLine(
          const Offset(9.7, 18.4),
          const Offset(14.3, 18.4),
          paint,
        ); // foot
      case BrandIcon.openBook:
        canvas.drawLine(const Offset(12, 6.2), const Offset(12, 18.6), paint);
        canvas.drawPath(_bookHalf(mirror: false), paint);
        canvas.drawPath(_bookHalf(mirror: true), paint);
      case BrandIcon.sprig:
        canvas.drawPath(_sprigStem(), paint);
        for (final leaf in _sprigLeaves()) {
          canvas.drawPath(leaf, paint);
        }
      case BrandIcon.envelope:
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            const Rect.fromLTRB(4.2, 5.6, 19.8, 18.2),
            const Radius.circular(1.6),
          ),
          paint,
        );
        canvas.drawPath(_envelopeFlap(), paint);
      case BrandIcon.gift:
        canvas.drawRect(const Rect.fromLTRB(5.4, 10.4, 18.6, 19.4), paint);
        canvas.drawRect(const Rect.fromLTRB(4.2, 7.4, 19.8, 10.4), paint);
        canvas.drawLine(const Offset(12, 7.4), const Offset(12, 19.4), paint);
        canvas.drawCircle(const Offset(9.7, 5.7), 1.5, paint); // bow loops
        canvas.drawCircle(const Offset(14.3, 5.7), 1.5, paint);
      case BrandIcon.speechBubble:
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            const Rect.fromLTRB(3.8, 4.4, 20.2, 15.4),
            const Radius.circular(3.2),
          ),
          paint,
        );
        canvas.drawPath(_bubbleTail(), paint);
      case BrandIcon.path:
        canvas.drawPath(_trail(), paint);
        canvas.drawCircle(const Offset(7.9, 20.6), 1.2, dot); // start
        canvas.drawCircle(const Offset(17.2, 5.1), 1.7, paint); // destination
        canvas.drawCircle(const Offset(17.2, 5.1), 0.6, dot);
      case BrandIcon.door:
        canvas.drawPath(_arch(), paint);
        canvas.drawLine(
          const Offset(3.8, 20.8),
          const Offset(20.2, 20.8),
          paint,
        );
        canvas.drawCircle(const Offset(15.3, 14.2), 0.9, dot); // handle
      case BrandIcon.lightDot:
        canvas.drawCircle(const Offset(12, 12), 2.6, dot);
        for (var i = 0; i < 8; i++) {
          final a = i * math.pi / 4;
          canvas.drawLine(
            Offset(12 + math.cos(a) * 4.6, 12 + math.sin(a) * 4.6),
            Offset(12 + math.cos(a) * 7.2, 12 + math.sin(a) * 7.2),
            paint,
          );
        }
      case BrandIcon.coin:
        // Two circles only: at 16px anything finer fuses into a blob.
        canvas.drawCircle(const Offset(12, 12), 8.1, paint);
        canvas.drawCircle(const Offset(12, 12), 5.9, paint);
      case BrandIcon.globe:
        canvas.drawCircle(const Offset(12, 12), 8.3, paint);
        canvas.drawOval(const Rect.fromLTRB(8.3, 3.7, 15.7, 20.3), paint);
        canvas.drawLine(const Offset(3.9, 12), const Offset(20.1, 12), paint);
      case BrandIcon.flame:
        canvas.drawPath(_flameOuter(), paint);
        canvas.drawPath(_flameInner(), paint);
      case BrandIcon.medal:
        canvas.drawCircle(const Offset(12, 10.2), 5.2, paint);
        canvas.drawCircle(const Offset(12, 10.2), 2.8, paint);
        canvas.drawPath(_medalRibbon(mirror: false), paint);
        canvas.drawPath(_medalRibbon(mirror: true), paint);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _BrandGlyphPainter old) =>
      old.icon != icon || old.color != color || old.strokeWidth != strokeWidth;
}

// ── Paths, all on the 24×24 grid ──────────────────────────────────────────

/// Crescent as the difference of two circles: the stroked outline of the
/// combined path is exactly the thin crescent edge, both sides of it.
Path _crescent() {
  final outer = Path()..addOval(const Rect.fromLTRB(2.9, 3.4, 19.9, 20.4));
  final bite = Path()..addOval(const Rect.fromLTRB(8.7, 1.6, 23.3, 16.2));
  return ui.Path.combine(ui.PathOperation.difference, outer, bite);
}

Path _sparkle() => Path()
  ..moveTo(12, 2.8)
  ..lineTo(14.0, 10.0)
  ..lineTo(21.2, 12)
  ..lineTo(14.0, 14.0)
  ..lineTo(12, 21.2)
  ..lineTo(10.0, 14.0)
  ..lineTo(2.8, 12)
  ..lineTo(10.0, 10.0)
  ..close();

Path _lanternCap() => Path()
  ..moveTo(9.6, 5.2)
  ..lineTo(14.4, 5.2)
  ..lineTo(13.5, 7.1)
  ..lineTo(10.5, 7.1)
  ..close();

Path _lanternBody() => Path()
  ..moveTo(9.3, 7.1)
  ..quadraticBezierTo(6.4, 11.8, 9.3, 16.3)
  ..lineTo(14.7, 16.3)
  ..quadraticBezierTo(17.6, 11.8, 14.7, 7.1)
  ..close();

Path _bookHalf({required bool mirror}) {
  double x(double v) => mirror ? 24 - v : v;
  return Path()
    ..moveTo(x(12), 6.2)
    ..quadraticBezierTo(x(8.4), 4.2, x(4.2), 5.2)
    ..lineTo(x(4.2), 17.4)
    ..quadraticBezierTo(x(8.4), 16.4, x(12), 18.6);
}

Path _sprigStem() => Path()
  ..moveTo(12, 20.8)
  ..quadraticBezierTo(10.9, 15.2, 12.5, 9.4)
  ..quadraticBezierTo(13.3, 6.6, 12, 3.4);

/// Almond leaves: out along one curve, back along another.
Path _leaf(Offset base, Offset tip, Offset outCtrl, Offset backCtrl) => Path()
  ..moveTo(base.dx, base.dy)
  ..quadraticBezierTo(outCtrl.dx, outCtrl.dy, tip.dx, tip.dy)
  ..quadraticBezierTo(backCtrl.dx, backCtrl.dy, base.dx, base.dy)
  ..close();

List<Path> _sprigLeaves() => [
  _leaf(
    const Offset(11.7, 16.6),
    const Offset(7.4, 14.4),
    const Offset(8.6, 17.2),
    const Offset(7.2, 15.4),
  ),
  _leaf(
    const Offset(12.1, 13.4),
    const Offset(16.6, 11.2),
    const Offset(15.4, 14.0),
    const Offset(16.8, 12.2),
  ),
  _leaf(
    const Offset(12.4, 10.2),
    const Offset(8.2, 8.0),
    const Offset(9.4, 10.8),
    const Offset(8.0, 9.0),
  ),
  _leaf(
    const Offset(12.6, 7.2),
    const Offset(16.4, 4.4),
    const Offset(15.6, 7.6),
    const Offset(16.6, 5.6),
  ),
];

Path _envelopeFlap() => Path()
  ..moveTo(4.9, 7.0)
  ..lineTo(12, 13.2)
  ..lineTo(19.1, 7.0);

Path _bubbleTail() => Path()
  ..moveTo(8.7, 15.2)
  ..lineTo(7.7, 19.3)
  ..lineTo(11.9, 15.4);

Path _trail() => Path()
  ..moveTo(7.9, 20.6)
  ..quadraticBezierTo(15.2, 17.6, 13.0, 12.4)
  ..quadraticBezierTo(10.9, 7.6, 17.2, 5.1);

Path _arch() => Path()
  ..moveTo(5.8, 20.8)
  ..lineTo(5.8, 11.2)
  ..quadraticBezierTo(5.8, 6.4, 12, 3.7)
  ..quadraticBezierTo(18.2, 6.4, 18.2, 11.2)
  ..lineTo(18.2, 20.8);

Path _flameOuter() => Path()
  ..moveTo(12, 3.1)
  ..cubicTo(16.2, 8.0, 16.9, 11.5, 15.3, 14.5)
  ..quadraticBezierTo(15.6, 18.3, 12, 18.5)
  ..quadraticBezierTo(8.4, 18.3, 8.7, 14.5)
  ..cubicTo(7.1, 11.5, 7.8, 8.0, 12, 3.1)
  ..close();

Path _flameInner() => Path()
  ..moveTo(10.0, 14.4)
  ..quadraticBezierTo(12, 16.6, 14.0, 14.4);

Path _medalRibbon({required bool mirror}) {
  double x(double v) => mirror ? 24 - v : v;
  return Path()
    ..moveTo(x(9.3), 14.7)
    ..lineTo(x(6.8), 20.8)
    ..lineTo(x(10.4), 18.7)
    ..close();
}
