import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flame/game.dart';
import 'package:flame/collisions.dart';
import 'package:flutter/material.dart';

import '../emoji_sprite.dart';
import 'dart:math';

class EmotionMazeGame extends FlameGame with HasCollisionDetection {
  late TextComponent scoreText;
  int score = 0;
  bool isGameOver = false;
  double spawnTimer = 0;
  final Random _random = Random();
  final Function(int) onGameOver;

  EmotionMazeGame({required this.onGameOver});

  @override
  Future<void> onLoad() async {
    camera.viewfinder.anchor = Anchor.topLeft;

    // Background color (Dark room)
    add(RectangleComponent(
      size: size,
      paint: Paint()..color = const Color(0xFF1E293B),
    ));

    // Score Text
    scoreText = TextComponent(
      text: 'الأبواب المفتوحة: 0',
      position: Vector2(20, 40),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Colors.white,
          fontSize: 20,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
    add(scoreText);

    _spawnDoors();
  }

  void _spawnDoors() {
    // Left door vs Right door (one is good, one is bad)
    final isLeftGood = _random.nextBool();
    
    // Left Door
    add(ChoiceDoor(
      isGood: isLeftGood,
      position: Vector2(size.x / 4 - 40, -100),
      size: Vector2(80, 100),
    ));

    // Right Door
    add(ChoiceDoor(
      isGood: !isLeftGood,
      position: Vector2(size.x * 0.75 - 40, -100),
      size: Vector2(80, 100),
    ));
  }

  @override
  void update(double dt) {
    if (isGameOver) return;
    super.update(dt);

    spawnTimer += dt;
    if (spawnTimer > 3.0) { // New doors every 3 seconds
      spawnTimer = 0;
      _spawnDoors();
    }
  }

  void increaseScore() {
    score += 1;
    scoreText.text = 'الأبواب المفتوحة: $score';
  }

  void triggerGameOver() {
    isGameOver = true;
    onGameOver(score);
  }
}

class ChoiceDoor extends PositionComponent with CollisionCallbacks, TapCallbacks {
  final bool isGood;
  final double speed = 100;

  ChoiceDoor({required this.isGood, super.position, super.size});

  @override
  void update(double dt) {
    super.update(dt);
    position.y += speed * dt;
    // Remove if it goes off screen
    if (position.y > (findParent<EmotionMazeGame>()?.size.y ?? 1000)) {
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    // good choice = calm/breathe (😌), bad choice = anger/scream (😡)
    final box = Size(size.x, size.y);
    final bg = Paint()
      ..color = (isGood ? const Color(0xFF10B981) : const Color(0xFFEF4444))
          .withValues(alpha: 0.18);
    canvas.drawRRect(
      RRect.fromRectAndRadius(size.toRect(), const Radius.circular(14)),
      bg,
    );
    paintEmoji(canvas, isGood ? '😌' : '😡', box);
  }

  @override
  void onTapDown(TapDownEvent event) {
    final game = findParent<EmotionMazeGame>();
    if (game == null || game.isGameOver) return;

    if (isGood) {
      game.increaseScore();
      // Remove both doors visually by finding siblings
      parent?.children.whereType<ChoiceDoor>().forEach((door) => door.removeFromParent());
      game.spawnTimer = 2.0; // Speed up next spawn slightly
    } else {
      game.triggerGameOver();
    }
  }
}
