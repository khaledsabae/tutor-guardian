import 'package:flutter/material.dart';

/// Squircle tile with a big emoji on a tinted background — the app's
/// illustration system (no image assets needed).
class EmojiHero extends StatelessWidget {
  final String emoji;
  final double size;
  final Color background;
  final double radius;

  const EmojiHero({
    super.key,
    required this.emoji,
    this.size = 56,
    this.background = const Color(0x33FFFFFF),
    this.radius = 18,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(radius),
      ),
      child: Text(emoji, style: TextStyle(fontSize: size * .55)),
    );
  }
}
