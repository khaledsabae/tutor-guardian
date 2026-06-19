import 'package:flutter/material.dart';

import '../data/journey_milestones.dart';

/// Shows a milestone's custom badge illustration when one exists
/// ([milestoneBadgeAsset]), otherwise falls back to its [emoji]. Used in the
/// journey timeline + suggested-milestone tiles so spiritual milestones get
/// rich art while developmental/custom ones keep their emoji.
class MilestoneIcon extends StatelessWidget {
  const MilestoneIcon({
    super.key,
    required this.milestoneKey,
    required this.emoji,
    this.size = 40,
  });

  final String milestoneKey;
  final String emoji;
  final double size;

  @override
  Widget build(BuildContext context) {
    final asset = milestoneBadgeAsset(milestoneKey);
    if (asset == null) {
      return Text(emoji, style: TextStyle(fontSize: size * 0.62));
    }
    return Image.asset(
      asset,
      width: size,
      height: size,
      fit: BoxFit.contain,
      filterQuality: FilterQuality.medium,
      errorBuilder: (_, __, ___) =>
          Text(emoji, style: TextStyle(fontSize: size * 0.62)),
    );
  }
}
