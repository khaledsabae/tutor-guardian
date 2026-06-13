import 'dart:math';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flame/game.dart';
import 'package:flame/collisions.dart';
import 'package:flutter/material.dart';

import '../emoji_sprite.dart';

class TreeOfDeedsGame extends FlameGame with HasCollisionDetection {
  late TreeComponent tree;
  late TextComponent scoreText;
  int score = 0;
  bool isGameOver = false;
  double spawnTimer = 0;
  final Random _random = Random();
  final Function(int) onGameOver;

  TreeOfDeedsGame({required this.onGameOver});

  @override
  Future<void> onLoad() async {
    camera.viewfinder.anchor = Anchor.topLeft;

    // Background color (Sunrise)
    add(RectangleComponent(
      size: size,
      paint: Paint()..color = const Color(0xFFFDE047), // Yellow
    ));

    // Ground
    add(RectangleComponent(
      position: Vector2(0, size.y - 100),
      size: Vector2(size.x, 100),
      paint: Paint()..color = const Color(0xFFD97706), // Brown dirt
    ));

    // Add Tree
    tree = TreeComponent()
      ..position = Vector2(size.x / 2 - 50, size.y - 200)
      ..size = Vector2(100, 100);
    add(tree);

    // Score Text
    scoreText = TextComponent(
      text: 'الحسنات: 0',
      position: Vector2(size.x - 120, 40),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Color(0xFF422006),
          fontSize: 20,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
    add(scoreText);
  }

  @override
  void update(double dt) {
    if (isGameOver) return;
    super.update(dt);

    spawnTimer += dt;
    if (spawnTimer > 1.0) {
      spawnTimer = 0;
      _spawnDeed();
    }
  }

  void _spawnDeed() {
    final isGood = _random.nextDouble() > 0.3; // 70% chance for good deeds
    final startX = _random.nextDouble() * (size.x - 40);
    
    add(DeedItem(
      isGood: isGood,
      position: Vector2(startX, -50),
      size: Vector2(40, 40),
    ));
  }

  void increaseScore() {
    score += 10;
    scoreText.text = 'الحسنات: $score';
    // Grow the tree slightly
    tree.scale.add(Vector2(0.05, 0.05));
    tree.position.y -= 2.5; // adjust position to keep root on ground
  }

  void triggerGameOver() {
    isGameOver = true;
    onGameOver(score);
  }
}

class TreeComponent extends PositionComponent with CollisionCallbacks {
  TreeComponent() {
    add(RectangleHitbox());
  }

  @override
  void render(Canvas canvas) {
    paintEmoji(canvas, '🌳', size.toSize());
  }
}

class DeedItem extends PositionComponent with CollisionCallbacks, TapCallbacks {
  final bool isGood;
  final double speed = 150;

  DeedItem({required this.isGood, super.position, super.size}) {
    add(RectangleHitbox());
  }

  @override
  void update(double dt) {
    super.update(dt);
    position.y += speed * dt;
    if (position.y > (findParent<TreeOfDeedsGame>()?.size.y ?? 1000)) {
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    // good deed = a falling good-deed token; bad deed = a dark cloud to pop
    paintEmoji(canvas, isGood ? '⭐' : '☁️', size.toSize());
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (!isGood) {
      // Player destroyed the bad deed
      removeFromParent();
    }
  }

  @override
  void onCollisionStart(Set<Vector2> intersectionPoints, PositionComponent other) {
    super.onCollisionStart(intersectionPoints, other);
    if (other is TreeComponent) {
      final game = findParent<TreeOfDeedsGame>();
      if (game != null && !game.isGameOver) {
        if (isGood) {
          game.increaseScore();
        } else {
          game.triggerGameOver();
        }
      }
      removeFromParent();
    }
  }
}
