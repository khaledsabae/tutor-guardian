import 'package:flutter/material.dart';

/// Integer that counts up from 0 to [value] on first build.
class CountUpText extends StatelessWidget {
  final int value;
  final TextStyle? style;
  final String suffix;
  final Duration duration;

  const CountUpText(
    this.value, {
    super.key,
    this.style,
    this.suffix = '',
    this.duration = const Duration(milliseconds: 800),
  });

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<int>(
      tween: IntTween(begin: 0, end: value),
      duration: duration,
      curve: Curves.easeOutCubic,
      builder: (context, animated, _) =>
          Text('$animated$suffix', style: style),
    );
  }
}
