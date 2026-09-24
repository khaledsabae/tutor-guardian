import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

/// Wraps any child with a press-down scale bounce (Duolingo feel).
class BouncyTap extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;

  const BouncyTap({super.key, required this.child, this.onTap});

  @override
  State<BouncyTap> createState() => _BouncyTapState();
}

class _BouncyTapState extends State<BouncyTap> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: widget.onTap == null
          ? null
          : (_) => setState(() => _pressed = true),
      onTapUp: widget.onTap == null
          ? null
          : (_) {
              setState(() => _pressed = false);
              widget.onTap!();
            },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? 0.95 : 1,
        duration: const Duration(milliseconds: 110),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}

/// Chunky pill CTA: solid fill with a darker 4px bottom edge, the
/// signature "pressable" Duolingo button.
class BouncyButton extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  /// Null means the live brand colour.
  final Color? color;
  final Color? edgeColor;
  final Widget? icon;
  final bool expanded;

  const BouncyButton({
    super.key,
    required this.label,
    this.onTap,
    this.color,
    this.edgeColor,
    this.icon,
    this.expanded = true,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    final effectiveColor = color ?? Dt.primary;
    final fill = enabled ? effectiveColor : Dt.track;
    final edge = enabled
        ? (edgeColor ?? Color.lerp(effectiveColor, Colors.black, .25)!)
        : const Color(0xFFD8D0C2);
    final Color textColor;
    if (!enabled) {
      textColor = Dt.inkSoft;
    } else if (effectiveColor == Dt.accent) {
      textColor = Dt.onAccent;
    } else if (effectiveColor == Dt.primary) {
      textColor = Dt.onPrimary;
    } else {
      textColor = effectiveColor.computeLuminance() > 0.5 ? Colors.black87 : Colors.white;
    }
    final content = Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(Dt.rButton),
        border: Border(bottom: BorderSide(color: edge, width: 4)),
      ),
      child: Row(
        mainAxisSize: expanded ? MainAxisSize.max : MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (icon != null) ...[icon!, const SizedBox(width: 8)],
          Flexible(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: textColor,
                fontSize: 16,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
    return BouncyTap(onTap: onTap, child: content);
  }
}
