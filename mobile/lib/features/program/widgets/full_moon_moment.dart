/// «اكتمل البدر» (NOOR_WAL_QANADIL_PLAN, phase 4): the moment a path is
/// finished. Noor's crescent fills to a full moon in 1.2 s — an emerald
/// shadow slides off the ivory disc — and Noor's happy face shows in its
/// middle at the end. Under reduce-motion the full moon is there at once,
/// still.
///
/// Cut in the «ورق مقصوص» set (assets/svg/STYLE.md): the art's emerald card,
/// flat palette colours, a solid offset paper shadow, no gradient, no blur.
/// No confetti and no promise of reward in the words — the family finished
/// something, and the moment says only that.
///
/// The path screen decides *when* (a path going from not-all to all lessons
/// done, once per path on this device); this file only draws and words it.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/haptics.dart';
import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';

/// How long the crescent takes to fill.
const kFullMoonDuration = Duration(milliseconds: 1200);

/// SharedPreferences key: the ids of the paths whose full moon this device
/// has shown — once per path, never again for the same one.
const kFullMoonShownKey = 'noor.full_moon.v1';


// The paper (assets/svg/STYLE.md).
const _kCard = Color(0xFF0F6B5C);
const _kCardShadow = Color(0xFF094A40);
const _kUnlit = Color(0xFF12806D);
const _kStarDecor = Color(0xFF13806C);
const _kIvory = Color(0xFFFBF1DE);
const _kInk = Color(0xFF0F3D36);
const _kCoral = Color(0xFFF4A492);
const _kGold = Color(0xFFF7C548);

/// Shows the moment over the path screen, with a success haptic.
Future<void> showFullMoonMoment(
  BuildContext context, {
  required String pathTitle,
  required VoidCallback onShare,
}) {
  unawaited(Haptics.success());
  return showDialog<void>(
    context: context,
    builder: (_) => FullMoonMoment(pathTitle: pathTitle, onShare: onShare),
  );
}

class FullMoonMoment extends StatefulWidget {
  const FullMoonMoment({
    super.key,
    required this.pathTitle,
    required this.onShare,
  });

  final String pathTitle;
  final VoidCallback onShare;

  @override
  State<FullMoonMoment> createState() => FullMoonMomentState();
}

class FullMoonMomentState extends State<FullMoonMoment>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fill = AnimationController(
    vsync: this,
    duration: kFullMoonDuration,
  );
  bool _started = false;

  /// How full the moon is, 0 (Noor's crescent) → 1 (full, with the face).
  @visibleForTesting
  double get fill => _fill.value;

  /// Whether the crescent is still filling — pins the reduce-motion contract.
  @visibleForTesting
  bool get filling => _fill.isAnimating;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (reduceMotion(context)) {
      // Still: the full moon, face and all, from the first frame.
      _fill
        ..stop()
        ..value = 1;
    } else if (!_started) {
      _fill.forward();
    }
    _started = true;
  }

  @override
  void dispose() {
    _fill.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final width = MediaQuery.sizeOf(context).width;
    final moon = math.min(184.0, width * .48);
    return Dialog(
      key: const ValueKey('full_moon_moment'),
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
      shadowColor: Colors.transparent,
      elevation: 0,
      insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      child: Container(
        decoration: BoxDecoration(
          // The art's own card: emerald in both themes, like Noor's window.
          color: _kCard,
          borderRadius: BorderRadius.circular(28),
          boxShadow: const [
            BoxShadow(color: _kCardShadow, offset: Offset(4, 5)),
          ],
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ExcludeSemantics(
                child: AnimatedBuilder(
                  animation: _fill,
                  builder: (context, _) => CustomPaint(
                    key: const ValueKey('full_moon_art'),
                    size: Size.square(moon),
                    painter: FullMoonPainter(progress: _fill.value),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Semantics(
                header: true,
                child: Text(
                  l10n.pathFullMoonTitle,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: _kIvory,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    height: 1.35,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                l10n.pathFullMoonBody(widget.pathTitle),
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: _kIvory.withValues(alpha: .92),
                  fontSize: 15,
                  height: 1.6,
                ),
              ),
              const SizedBox(height: 18),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  key: const ValueKey('full_moon_share'),
                  style: FilledButton.styleFrom(
                    backgroundColor: _kGold,
                    foregroundColor: _kInk,
                    minimumSize: const Size(0, 48),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  onPressed: widget.onShare,
                  icon: const Icon(Icons.ios_share_rounded, size: 20),
                  label: Text(
                    l10n.pathFullMoonShare,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ),
              const SizedBox(height: 4),
              TextButton(
                key: const ValueKey('full_moon_close'),
                style: TextButton.styleFrom(
                  foregroundColor: _kIvory,
                  minimumSize: const Size(0, 48),
                ),
                onPressed: () => Navigator.of(context).pop(),
                child: Text(l10n.close),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The crescent filling to a full moon, on the 240 art grid of
/// assets/svg/STYLE.md: Noor's crescent is the moon disc (r 62.4) less the cut
/// disc (r 52.8, up and to the right). The cut slides off along that
/// diagonal; what it uncovers is lit ivory, what it still covers is the unlit
/// emerald side. Noor's happy face comes in over the last quarter.
class FullMoonPainter extends CustomPainter {
  FullMoonPainter({required this.progress});

  /// 0 → crescent, 1 → full moon with the face.
  final double progress;

  static const _c = Offset(120, 122);
  static const _r = 62.4;
  static const _cutR = 52.8;

  /// Noor's cut, relative to the moon's centre (STYLE.md: (156,108) − (120,132)).
  static const _cutAt = Offset(36, -24);

  /// Decorative eight-point stars on the card, away from the moon.
  static const _decor = <(double, double, double)>[
    (32, 44, 6),
    (210, 40, 5),
    (214, 178, 4.5),
    (28, 200, 4),
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.shortestSide / 240;
    canvas
      ..save()
      ..translate((size.width - 240 * s) / 2, (size.height - 240 * s) / 2)
      ..scale(s);

    for (final (x, y, r) in _decor) {
      canvas.drawPath(_star8(Offset(x, y), r), Paint()..color = _kStarDecor);
    }

    final t = Curves.easeInOutCubic.transform(progress.clamp(0.0, 1.0));
    final disc = Path()..addOval(Rect.fromCircle(center: _c, radius: _r));

    // The paper shadow of the whole disc, then the unlit side.
    canvas
      ..drawPath(disc.shift(const Offset(5, 6)), Paint()..color = _kCardShadow)
      ..drawPath(disc, Paint()..color = _kUnlit);

    // The lit part: the disc less the cut, which slides off until it clears.
    final dir = _cutAt / _cutAt.distance;
    final clear = _r + _cutR + 2 - _cutAt.distance;
    final cutC = _c + _cutAt + dir * (clear * t);
    final lit = t >= 1
        ? disc
        : Path.combine(
            PathOperation.difference,
            disc,
            Path()..addOval(Rect.fromCircle(center: cutC, radius: _cutR)),
          );
    canvas.drawPath(lit, Paint()..color = _kIvory);

    final face = ((progress - .72) / .28).clamp(0.0, 1.0);
    if (face > 0) _face(canvas, face);

    canvas.restore();
  }

  /// Noor's happy face, centred: closed smiling eyes, coral cheeks, a smile —
  /// the reference strokes of STYLE.md moved to the middle of the disc.
  void _face(Canvas canvas, double a) {
    final ink = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = 3.4
      ..color = _kInk.withValues(alpha: a);
    final x = _c.dx, y = _c.dy;
    canvas
      ..drawPath(
        Path()
          ..moveTo(x - 25, y + 2)
          ..quadraticBezierTo(x - 18, y - 6, x - 11, y + 2),
        ink,
      )
      ..drawPath(
        Path()
          ..moveTo(x + 11, y + 2)
          ..quadraticBezierTo(x + 18, y - 6, x + 25, y + 2),
        ink,
      );
    final cheek = Paint()..color = _kCoral.withValues(alpha: a);
    canvas
      ..drawCircle(Offset(x - 30, y + 15), 5.4, cheek)
      ..drawCircle(Offset(x + 30, y + 15), 5.4, cheek)
      ..drawPath(
        Path()
          ..moveTo(x - 9, y + 16)
          ..quadraticBezierTo(x, y + 25, x + 9, y + 16),
        ink..strokeWidth = 3.2,
      );
    // Two small lit stars beside the full moon.
    final gold = Paint()..color = _kGold.withValues(alpha: a);
    canvas
      ..drawPath(_sparkle(const Offset(196, 92), 7), gold)
      ..drawPath(_sparkle(const Offset(46, 150), 5.5), gold);
  }

  /// An eight-point star (STYLE.md's decoration).
  static Path _star8(Offset c, double r) {
    final p = Path();
    for (var i = 0; i < 16; i++) {
      final rr = i.isEven ? r : r * .55;
      final a = i * math.pi / 8 - math.pi / 2;
      final pt = c + Offset(math.cos(a) * rr, math.sin(a) * rr);
      if (i == 0) {
        p.moveTo(pt.dx, pt.dy);
      } else {
        p.lineTo(pt.dx, pt.dy);
      }
    }
    return p..close();
  }

  /// A four-point lit star, cut like the sky's.
  static Path _sparkle(Offset c, double r) {
    final k = r * .1;
    return Path()
      ..moveTo(c.dx, c.dy - r)
      ..quadraticBezierTo(c.dx + k, c.dy - k, c.dx + r, c.dy)
      ..quadraticBezierTo(c.dx + k, c.dy + k, c.dx, c.dy + r)
      ..quadraticBezierTo(c.dx - k, c.dy + k, c.dx - r, c.dy)
      ..quadraticBezierTo(c.dx - k, c.dy - k, c.dx, c.dy - r)
      ..close();
  }

  @override
  bool shouldRepaint(FullMoonPainter old) => old.progress != progress;
}
