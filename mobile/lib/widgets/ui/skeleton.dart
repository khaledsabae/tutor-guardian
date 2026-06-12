import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../theme/design_tokens.dart';

/// Shimmering placeholder box used while content loads.
class SkeletonBox extends StatelessWidget {
  final double? width;
  final double height;
  final double radius;

  const SkeletonBox({
    super.key,
    this.width,
    required this.height,
    this.radius = 16,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: const Color(0xFFEDE7DC),
        borderRadius: BorderRadius.circular(radius),
      ),
    );
  }
}

/// A column of shimmering card-shaped skeletons — drop-in replacement
/// for `CircularProgressIndicator` in list loading states.
class SkeletonList extends StatelessWidget {
  final int count;
  final double itemHeight;
  final EdgeInsetsGeometry padding;

  const SkeletonList({
    super.key,
    this.count = 4,
    this.itemHeight = 140,
    this.padding = const EdgeInsets.all(16),
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Column(
        children: [
          for (var i = 0; i < count; i++) ...[
            SkeletonBox(height: itemHeight, radius: Dt.rCard),
            if (i < count - 1) const SizedBox(height: 12),
          ],
        ],
      )
          .animate(onPlay: (c) => c.repeat())
          .shimmer(duration: 1200.ms, color: Colors.white.withValues(alpha: .6)),
    );
  }
}
