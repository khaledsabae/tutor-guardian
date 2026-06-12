import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

/// Rounded gradient card with a soft colored shadow and ink ripple.
/// The visual building block for path cards, headers and CTAs.
class GradientCard extends StatelessWidget {
  final Gradient gradient;
  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? shadowColor;

  const GradientCard({
    super.key,
    required this.gradient,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(20),
    this.radius = Dt.rCard,
    this.shadowColor,
  });

  @override
  Widget build(BuildContext context) {
    final shadowBase =
        shadowColor ?? (gradient is LinearGradient
            ? (gradient as LinearGradient).colors.first
            : Dt.primary);
    return Container(
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(radius),
        boxShadow: Dt.softShadow(shadowBase),
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(radius),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          splashColor: Colors.white.withValues(alpha: .12),
          highlightColor: Colors.white.withValues(alpha: .06),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}
