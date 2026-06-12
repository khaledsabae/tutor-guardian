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
  final Color color;
  final Color? edgeColor;
  final Widget? icon;
  final bool expanded;

  const BouncyButton({
    super.key,
    required this.label,
    this.onTap,
    this.color = Dt.primary,
    this.edgeColor,
    this.icon,
    this.expanded = true,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    final fill = enabled ? color : Dt.track;
    final edge = enabled
        ? (edgeColor ?? Color.lerp(color, Colors.black, .25)!)
        : const Color(0xFFD8D0C2);
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
                color: enabled ? Colors.white : Dt.inkSoft,
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
