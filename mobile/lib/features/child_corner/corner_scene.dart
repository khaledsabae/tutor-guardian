/// The corner's paper: a sky, two cut hills and a valley, and the cards that
/// stand in it — «ورق مقصوص» (assets/svg/STYLE.md) drawn in code, with flat
/// colours from [CornerPaper] and solid offset shadows, never a blur or a
/// gradient. Nothing here moves.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_palette.dart';

/// The band where the sky meets the valley: the far hill, the near hill, and
/// — over the far hill — a gold sun by day or three gold stars by night.
class CornerHills extends StatelessWidget {
  const CornerHills({super.key, this.height = 64});

  final double height;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ExcludeSemantics(
      child: SizedBox(
        height: height,
        width: double.infinity,
        child: CustomPaint(
          painter: CornerHillsPainter(
            paper: c.corner,
            gold: c.paperGold,
            night: c.isDark,
            rtl: Directionality.of(context) == TextDirection.rtl,
          ),
        ),
      ),
    );
  }
}

class CornerHillsPainter extends CustomPainter {
  const CornerHillsPainter({
    required this.paper,
    required this.gold,
    required this.night,
    required this.rtl,
  });

  final CornerPaper paper;
  final Color gold;
  final bool night;

  /// The sun and the far hill's crest sit on the reading side's far end.
  final bool rtl;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final fill = Paint()..isAntiAlias = true;
    canvas.drawRect(Offset.zero & size, fill..color = paper.sky);

    // Mirror once, so both reading directions get the same picture with the
    // light on the side the eye ends on.
    canvas.save();
    if (rtl) {
      canvas.translate(w, 0);
      canvas.scale(-1, 1);
    }

    if (night) {
      for (final (x, y, r) in [
        (.78, .22, 4.0),
        (.9, .48, 2.6),
        (.64, .5, 2.2),
      ]) {
        _star(canvas, Offset(w * x, h * y), r, fill..color = gold);
      }
    } else {
      final sun = Offset(w * .82, h * .5);
      canvas.drawCircle(sun, h * .3, fill..color = gold);
    }

    // The far hill rises toward the end; the near one toward the start. Each
    // hill is laid over its own solid shadow, shifted down and along.
    final far = Path()
      ..moveTo(0, h * .78)
      ..cubicTo(w * .3, h * .62, w * .55, h * .5, w * .78, h * .44)
      ..cubicTo(w * .9, h * .4, w, h * .46, w, h * .5)
      ..lineTo(w, h)
      ..lineTo(0, h)
      ..close();
    canvas.drawPath(far, fill..color = paper.hillFar);

    final near = Path()
      ..moveTo(0, h * .58)
      ..cubicTo(w * .18, h * .5, w * .36, h * .62, w * .55, h * .78)
      ..cubicTo(w * .72, h * .9, w * .88, h * .88, w, h * .84)
      ..lineTo(w, h)
      ..lineTo(0, h)
      ..close();
    canvas.drawPath(near.shift(const Offset(4, 5)), fill..color = paper.ground);
    canvas.drawPath(near, fill..color = paper.hillNear);

    // The valley's lip, so the cards below stand on ground, not on the hill.
    canvas.drawRect(Rect.fromLTWH(0, h - 6, w, 6), fill..color = paper.ground);
    canvas.restore();
  }

  /// The eight-point star from STYLE.md, small.
  void _star(Canvas canvas, Offset c, double r, Paint paint) {
    final path = Path();
    for (var i = 0; i < 16; i++) {
      final a = math.pi / 8 * i - math.pi / 2;
      final rr = i.isEven ? r : r * .45;
      final p = c + Offset(math.cos(a) * rr, math.sin(a) * rr);
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    canvas.drawPath(path..close(), paint);
  }

  @override
  bool shouldRepaint(CornerHillsPainter old) =>
      old.paper != paper ||
      old.gold != gold ||
      old.night != night ||
      old.rtl != rtl;
}

/// A card cut from paper: flat [CornerPaper.card], rounded, with its solid
/// shadow offset down and to the side. Tappable when [onTap] is given — the
/// whole card is the target, at least the child theme's 56 dp tall.
class CornerPaperCard extends StatelessWidget {
  const CornerPaperCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(16),
    this.semanticLabel,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final paper = context.colors.corner;
    final radius = BorderRadius.circular(22);
    Widget card = Container(
      decoration: BoxDecoration(
        borderRadius: radius,
        boxShadow: [
          BoxShadow(color: paper.cardShadow, offset: const Offset(4, 5)),
        ],
      ),
      child: Material(
        color: paper.card,
        borderRadius: radius,
        child: InkWell(
          borderRadius: radius,
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 56),
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
    if (onTap != null) {
      card = Semantics(button: true, label: semanticLabel, child: card);
    }
    return card;
  }
}

/// A gold paper button — the corner's one way forward on each step.
class CornerGoldButton extends StatelessWidget {
  const CornerGoldButton({
    super.key,
    required this.label,
    required this.onPressed,
  });

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return FilledButton(
      onPressed: onPressed,
      style: FilledButton.styleFrom(
        backgroundColor: c.paperGold,
        foregroundColor: c.corner.onGold,
        minimumSize: const Size(120, 56),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        textStyle: Theme.of(
          context,
        ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
      ),
      child: Text(label, textAlign: TextAlign.center),
    );
  }
}
