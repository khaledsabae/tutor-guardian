/// The two doors of «باب التسليم», drawn in the «ورق مقصوص» style.
///
/// Two ivory paper leaves with a mashrabiya window cut into each, meeting
/// under one arch. They swing apart from their outer hinges and reveal what
/// is behind them — the child's name and «دورك الآن» on the emerald ground.
///
/// The colours are the style guide's (`STYLE.md`, chosen 2026-10-14), fixed in
/// both themes the way an illustration's are: this is a picture of two paper
/// doors, not a surface that should follow light or dark.
///
/// Layout is physical, not directional: the left leaf hinges on the left in
/// Arabic and in English alike. The doors are symmetric, so nothing reads
/// backwards in either direction, and nothing mirrors twice.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

/// The «ورق مقصوص» palette, exactly as the style guide lists it.
abstract final class PaperCut {
  static const emerald = Color(0xFF0F6B5C);
  static const hill = Color(0xFF12806D);
  static const hillDeep = Color(0xFF0D6A5A);
  static const shadowOnEmerald = Color(0xFF094A40);
  static const starOnEmerald = Color(0xFF13806C);
  static const ivory = Color(0xFFFBF1DE);
  static const ivoryDeep = Color(0xFFEADBC0);
  static const shadowOnIvory = Color(0xFFD9C7A7);
  static const gold = Color(0xFFF7C548);
}

class HandoverDoors extends StatefulWidget {
  const HandoverDoors({
    super.key,
    required this.progress,
    required this.reduceMotion,
    required this.reveal,
  });

  /// 0 — closed; 1 — fully open.
  final Animation<double> progress;

  /// Under the system's "remove animations", the doors do not move: they fade
  /// out while what is behind them fades in.
  final bool reduceMotion;

  /// What the doors open onto.
  final Widget reveal;

  /// How far a leaf swings before it is gone — short of edge-on, where a
  /// perspective transform turns a panel into a sliver of noise.
  static const maxSwing = math.pi * 0.46;

  @override
  State<HandoverDoors> createState() => _HandoverDoorsState();
}

class _HandoverDoorsState extends State<HandoverDoors> {
  late CurvedAnimation _eased;
  late CurvedAnimation _revealOpacity;

  @override
  void initState() {
    super.initState();
    _curve();
  }

  @override
  void didUpdateWidget(covariant HandoverDoors oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.progress != widget.progress ||
        oldWidget.reduceMotion != widget.reduceMotion) {
      _eased.dispose();
      _revealOpacity.dispose();
      _curve();
    }
  }

  void _curve() {
    _eased = CurvedAnimation(
        parent: widget.progress, curve: Curves.easeInOutCubic);
    // The reveal comes up once the leaves have parted enough to show it; at
    // rest it is invisible, so nothing peeks through the seam.
    _revealOpacity = CurvedAnimation(
      parent: widget.progress,
      curve: widget.reduceMotion
          ? Curves.linear
          : const Interval(0.3, 0.85, curve: Curves.easeOut),
    );
  }

  @override
  void dispose() {
    _eased.dispose();
    _revealOpacity.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = widget.reduceMotion;
    return Stack(
      fit: StackFit.expand,
      children: [
        const ExcludeSemantics(child: CustomPaint(painter: _GroundPainter())),
        FadeTransition(
          opacity: _revealOpacity,
          child: Center(child: widget.reveal),
        ),
        ExcludeSemantics(
          child: LayoutBuilder(
            builder: (context, box) {
              final half = box.maxWidth / 2;
              return AnimatedBuilder(
                animation: _eased,
                builder: (context, _) {
                  final t = _eased.value;
                  if (t >= 1) return const SizedBox.shrink();
                  final angle = reduceMotion ? 0.0 : t * HandoverDoors.maxSwing;
                  // Moving: the leaves fade only in the last stretch, as they
                  // turn edge-on. Still: the fade is the whole transition.
                  final opacity = reduceMotion
                      ? 1 - t
                      : (1 - ((t - 0.8) / 0.2)).clamp(0.0, 1.0);
                  return Opacity(
                    opacity: opacity,
                    child: Stack(
                      children: [
                        Positioned(
                          left: 0,
                          top: 0,
                          bottom: 0,
                          width: half,
                          child: _leaf(angle, mirror: false),
                        ),
                        Positioned(
                          right: 0,
                          top: 0,
                          bottom: 0,
                          width: half,
                          child: _leaf(angle, mirror: true),
                        ),
                      ],
                    ),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _leaf(double angle, {required bool mirror}) {
    final painted = CustomPaint(
      painter: _DoorLeafPainter(mirror: mirror),
      size: Size.infinite,
    );
    if (angle == 0) return painted;
    // Each leaf turns on its outer hinge and swings away from the viewer —
    // its free edge recedes, so the perspective only ever shrinks it.
    return Transform(
      alignment: mirror ? Alignment.centerRight : Alignment.centerLeft,
      transform: Matrix4.identity()
        ..setEntry(3, 2, 0.0011)
        ..rotateY(mirror ? angle : -angle),
      child: painted,
    );
  }
}

/// An eight-pointed star — the one ornament the style guide allows.
Path eightPointStar(Offset centre, double outer, {double inner = 0.55}) {
  final path = Path();
  for (var i = 0; i < 16; i++) {
    final r = i.isEven ? outer : outer * inner;
    final a = -math.pi / 2 + i * math.pi / 8;
    final p = centre + Offset(math.cos(a) * r, math.sin(a) * r);
    if (i == 0) {
      path.moveTo(p.dx, p.dy);
    } else {
      path.lineTo(p.dx, p.dy);
    }
  }
  return path..close();
}

/// The emerald wall the doors are set in: a few stars, and three hills of
/// paper at the bottom.
class _GroundPainter extends CustomPainter {
  const _GroundPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    canvas.drawRect(Offset.zero & size, Paint()..color = PaperCut.emerald);

    final star = Paint()..color = PaperCut.starOnEmerald;
    final s = math.min(w, h) / 240;
    for (final (x, y, r) in const [
      (0.18, 0.14, 7.0),
      (0.82, 0.22, 5.0),
      (0.70, 0.08, 4.0),
      (0.26, 0.30, 4.0),
    ]) {
      canvas.drawPath(eightPointStar(Offset(w * x, h * y), r * s), star);
    }

    void hill(double base, double crest, Color colour, {bool flip = false}) {
      final path = Path()
        ..moveTo(0, h * base)
        ..cubicTo(
          w * (flip ? 0.6 : 0.25), h * crest,
          w * (flip ? 0.85 : 0.5), h * (crest + 0.06),
          w, h * (base - 0.02),
        )
        ..lineTo(w, h)
        ..lineTo(0, h)
        ..close();
      canvas.drawPath(path, Paint()..color = colour);
    }

    hill(0.86, 0.78, PaperCut.hill);
    hill(0.92, 0.86, PaperCut.hillDeep, flip: true);
    hill(0.97, 0.93, PaperCut.shadowOnEmerald);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// One leaf. Drawn as the left one; [mirror] flips it into the right.
///
/// Local coordinates: the hinge is at x = 0 and the meeting edge at x = w.
class _DoorLeafPainter extends CustomPainter {
  const _DoorLeafPainter({required this.mirror});

  final bool mirror;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    if (w <= 0 || h <= 0) return;
    if (mirror) {
      canvas
        ..translate(w, 0)
        ..scale(-1, 1);
    }
    // One style-guide unit: the pair is read as a 240-wide card.
    final s = math.min(w * 2, h) / 240;
    // Paper shadows fall down and to the right on screen, whichever leaf this
    // is — so in the flipped leaf the local x offset is reversed.
    final sx = mirror ? -1.0 : 1.0;
    Offset shadow(double dx, double dy) => Offset(dx * s * sx, dy * s);

    // The leaf.
    final margin = 6 * s;
    final leaf = RRect.fromRectAndCorners(
      Rect.fromLTRB(margin, margin, w - 0.6 * s, h - margin),
      topLeft: Radius.circular(10 * s),
      bottomLeft: Radius.circular(10 * s),
    );
    canvas
      ..drawRRect(leaf.shift(shadow(4, 5)),
          Paint()..color = PaperCut.shadowOnEmerald)
      ..drawRRect(leaf, Paint()..color = PaperCut.ivory);

    // The window: half of one arch, its crown at the meeting edge.
    final xa = margin + 12 * s;
    final xb = w - 7 * s;
    final yTop = margin + 14 * s;
    final rise = math.min((xb - xa) * 0.9, h * 0.16);
    final yBottom = h * 0.62;
    final window = Path()
      ..moveTo(xa, yBottom)
      ..lineTo(xa, yTop + rise)
      ..cubicTo(xa, yTop + rise * 0.35, xb - (xb - xa) * 0.4, yTop, xb, yTop)
      ..lineTo(xb, yBottom)
      ..close();
    canvas
      ..drawPath(window.shift(shadow(1.5, 2)),
          Paint()..color = PaperCut.shadowOnIvory)
      ..drawPath(window, Paint()..color = PaperCut.ivoryDeep);

    // The lattice: a star cut into every cell, a diamond at every crossing.
    canvas
      ..save()
      ..clipPath(window);
    final hole = Paint()..color = PaperCut.shadowOnEmerald;
    final cell = (xb - xa) / 3;
    for (var y = yTop + cell / 2; y < yBottom + cell; y += cell) {
      for (var x = xa + cell / 2; x < xb + cell; x += cell) {
        canvas.drawPath(eightPointStar(Offset(x, y), cell * 0.3), hole);
        final d = cell * 0.11;
        final cx = x + cell / 2, cy = y + cell / 2;
        canvas.drawPath(
          Path()
            ..moveTo(cx, cy - d)
            ..lineTo(cx + d, cy)
            ..lineTo(cx, cy + d)
            ..lineTo(cx - d, cy)
            ..close(),
          hole,
        );
      }
    }
    canvas.restore();

    // The lower panel.
    final panel = RRect.fromRectAndRadius(
      Rect.fromLTRB(xa, h * 0.68, xb, h - margin - 12 * s),
      Radius.circular(4 * s),
    );
    if (panel.height > 0) {
      canvas
        ..drawRRect(panel.shift(shadow(1.5, 2)),
            Paint()..color = PaperCut.shadowOnIvory)
        ..drawRRect(panel, Paint()..color = PaperCut.ivoryDeep);
    }

    // The handle, at the meeting edge: the only gold on the door.
    final knob = Offset(w - 3.5 * s, h * 0.65);
    canvas
      ..drawCircle(knob + shadow(1.5, 2), 3.4 * s,
          Paint()..color = PaperCut.shadowOnIvory)
      ..drawCircle(knob, 3.4 * s, Paint()..color = PaperCut.gold);
  }

  @override
  bool shouldRepaint(covariant _DoorLeafPainter oldDelegate) =>
      oldDelegate.mirror != mirror;
}

/// The small gold star above the child's name once the doors are open.
class PaperStar extends StatelessWidget {
  const PaperStar({super.key, this.size = 40});

  final double size;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
        child: CustomPaint(
          size: Size.square(size),
          painter: const _PaperStarPainter(),
        ),
      );
}

class _PaperStarPainter extends CustomPainter {
  const _PaperStarPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final r = size.shortestSide / 2 * 0.86;
    final c = size.center(Offset.zero);
    canvas
      ..drawPath(eightPointStar(c + Offset(r * 0.08, r * 0.1), r),
          Paint()..color = PaperCut.shadowOnEmerald)
      ..drawPath(eightPointStar(c, r), Paint()..color = PaperCut.gold);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
