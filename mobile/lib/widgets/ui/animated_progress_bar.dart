import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

/// Chunky rounded progress bar with an animated fill and a subtle
/// top "shine" strip — Duolingo style.
class AnimatedProgressBar extends StatelessWidget {
  final double value; // 0..1
  final Gradient? gradient;
  final Color? color;
  final double height;
  final Color trackColor;

  const AnimatedProgressBar({
    super.key,
    required this.value,
    this.gradient,
    this.color,
    this.height = 14,
    this.trackColor = Dt.track,
  });

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(height);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.clamp(0.0, 1.0)),
      duration: Dt.slow,
      curve: Curves.easeOutCubic,
      builder: (context, animated, _) {
        return ClipRRect(
          borderRadius: radius,
          child: Container(
            height: height,
            color: trackColor,
            alignment: AlignmentDirectional.centerStart,
            child: FractionallySizedBox(
              widthFactor: animated,
              heightFactor: 1,
              child: Container(
                decoration: BoxDecoration(
                  color: gradient == null ? (color ?? Dt.primary) : null,
                  gradient: gradient,
                  borderRadius: radius,
                ),
                child: animated > 0.05
                    ? Align(
                        alignment: Alignment.topCenter,
                        child: Padding(
                          padding: EdgeInsets.symmetric(
                            horizontal: height / 2,
                            vertical: height * .18,
                          ),
                          child: Container(
                            height: height * .22,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: .3),
                              borderRadius: BorderRadius.circular(height),
                            ),
                          ),
                        ),
                      )
                    : null,
              ),
            ),
          ),
        );
      },
    );
  }
}
