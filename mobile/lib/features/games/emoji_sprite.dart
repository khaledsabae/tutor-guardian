/// Shared helper to render an emoji glyph as a Flame sprite — gives the
/// mini-games recognizable "graphics" (🦸 🍎 🍬 🌳 ☁️ …) without bundling
/// any image assets.
library;

import 'package:flame/components.dart';
import 'package:flutter/material.dart';

class EmojiComponent extends PositionComponent {
  String emoji;
  EmojiComponent({
    required this.emoji,
    super.position,
    super.size,
    super.anchor,
  });

  late TextPainter _painter;
  String _renderedFor = '';

  void _ensurePainter() {
    if (_renderedFor == emoji && size.x > 0) return;
    _renderedFor = emoji;
    _painter = TextPainter(
      text: TextSpan(
        text: emoji,
        style: TextStyle(fontSize: size.x * 0.95),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
  }

  @override
  void render(Canvas canvas) {
    _ensurePainter();
    final dx = (size.x - _painter.width) / 2;
    final dy = (size.y - _painter.height) / 2;
    _painter.paint(canvas, Offset(dx, dy));
  }
}

/// Draw an emoji directly onto a canvas (for components that already
/// override render and just want the glyph).
void paintEmoji(Canvas canvas, String emoji, Size box) {
  final tp = TextPainter(
    text: TextSpan(text: emoji, style: TextStyle(fontSize: box.width * 0.95)),
    textDirection: TextDirection.ltr,
  )..layout();
  tp.paint(
    canvas,
    Offset((box.width - tp.width) / 2, (box.height - tp.height) / 2),
  );
}
