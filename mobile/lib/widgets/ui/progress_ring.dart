import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

/// Animated circular progress ring with a center slot (emoji or %).
class ProgressRing extends StatelessWidget {
  final double value; // 0..1
  final double size;
  final double strokeWidth;
  final Color color;
  final Color trackColor;
  final Widget? center;

  const ProgressRing({
    super.key,
    required this.value,
    this.size = 48,
    this.strokeWidth = 8,
    this.color = Dt.primary,
    this.trackColor = Dt.track,
    this.center,
  });

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.clamp(0.0, 1.0)),
      duration: Dt.slow,
      curve: Curves.easeOutCubic,
      builder: (context, animated, _) {
        return SizedBox(
          width: size,
          height: size,
          child: Stack(
            alignment: Alignment.center,
            children: [
              CustomPaint(
                size: Size.square(size),
                painter: _RingPainter(
                  value: animated,
                  color: color,
                  trackColor: trackColor,
                  strokeWidth: strokeWidth,
                ),
              ),
              if (center != null) center!,
            ],
          ),
        );
      },
    );
  }
}

class _RingPainter extends CustomPainter {
  final double value;
  final Color color;
  final Color trackColor;
  final double strokeWidth;

  _RingPainter({
    required this.value,
    required this.color,
    required this.trackColor,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = (size.shortestSide - strokeWidth) / 2;
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..color = trackColor;
    final fill = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawCircle(center, radius, track);
    if (value > 0) {
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        -math.pi / 2,
        2 * math.pi * value,
        false,
        fill,
      );
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.value != value || old.color != color;
}
