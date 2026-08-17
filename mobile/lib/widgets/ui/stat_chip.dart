import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../theme/design_tokens.dart';

/// Pill chip with an emoji + value + label, on a tinted background.
/// Used for 🔥 streak / 📚 lessons / 🏅 badges stats.
class StatChip extends StatelessWidget {
  final String emoji;
  final Widget value;
  final String label;
  /// Null means the live accent colour.
  final Color? color;
  final VoidCallback? onTap;
  final bool pulse;

  const StatChip({
    super.key,
    required this.emoji,
    required this.value,
    required this.label,
    this.color,
    this.onTap,
    this.pulse = false,
  });

  @override
  Widget build(BuildContext context) {
    Widget chip = Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Color.lerp(color ?? Dt.accent, Dt.surface, .85),
        borderRadius: BorderRadius.circular(Dt.rChip),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 20)),
          const SizedBox(width: 6),
          // Flexible + ellipsis: four chips share one row, so on narrow
          // phones the label must give way rather than overflow the pill.
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                DefaultTextStyle(
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: Color.lerp(color, Colors.black, .35),
                  ),
                  child: value,
                ),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 11, color: Dt.inkSoft),
                ),
              ],
            ),
          ),
        ],
      ),
    );
    if (pulse) {
      // Single appear-pop; never an infinite loop (performance budget).
      chip = chip
          .animate()
          .scale(
            begin: const Offset(.8, .8),
            duration: Dt.base,
            curve: Curves.easeOutBack,
          )
          .fadeIn(duration: Dt.fast);
    }
    if (onTap != null) {
      chip = GestureDetector(onTap: onTap, child: chip);
    }
    return chip;
  }
}
