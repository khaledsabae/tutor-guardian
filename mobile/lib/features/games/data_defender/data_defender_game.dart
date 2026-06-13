import 'dart:math';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flame/game.dart';
import 'package:flame/collisions.dart';
import 'package:flutter/material.dart';

class DataDefenderGame extends FlameGame with HasCollisionDetection, TapCallbacks {
  late Player player;
  late TextComponent scoreText;
  int score = 0;
  bool isGameOver = false;
  double spawnTimer = 0;
  final Random _random = Random();
  final Function(int) onGameOver;

  DataDefenderGame({required this.onGameOver});

  @override
  Future<void> onLoad() async {
    camera.viewfinder.anchor = Anchor.topLeft;

    // Background color
    add(RectangleComponent(
      size: size,
      paint: Paint()..color = const Color(0xFF1E293B), // Dark slate
    ));

    // Add Player
    player = Player()
      ..position = Vector2(size.x / 2 - 25, size.y - 100)
      ..size = Vector2(50, 50);
    add(player);

    // Score Text
    scoreText = TextComponent(
      text: 'النقاط: 0',
      position: Vector2(size.x - 100, 40),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Colors.white,
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
    // Spawn an item every 0.8 seconds
    if (spawnTimer > 0.8) {
      spawnTimer = 0;
      _spawnItem();
    }
  }

  void _spawnItem() {
    final isGood = _random.nextDouble() > 0.4; // 60% chance for good item
    final startX = _random.nextDouble() * (size.x - 40);
    add(FallingItem(
      isGood: isGood,
      position: Vector2(startX, -50),
      size: Vector2(40, 40),
    ));
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (isGameOver) return;
    // Move player left or right based on tap position
    if (event.localPosition.x < size.x / 2) {
      player.position.x = max(0, player.position.x - 60);
    } else {
      player.position.x = min(size.x - player.size.x, player.position.x + 60);
    }
  }

  void increaseScore() {
    score += 10;
    scoreText.text = 'النقاط: $score';
  }

  void triggerGameOver() {
    isGameOver = true;
    onGameOver(score);
  }
}

class Player extends PositionComponent with CollisionCallbacks {
  final _paint = Paint()..color = const Color(0xFF38BDF8); // Light blue robot

  Player() {
    add(RectangleHitbox());
  }

  @override
  void render(Canvas canvas) {
    // Draw a simple robot shape
    canvas.drawRRect(
      RRect.fromRectAndRadius(size.toRect(), const Radius.circular(8)),
      _paint,
    );
    // Eyes
    final eyePaint = Paint()..color = Colors.white;
    canvas.drawCircle(const Offset(15, 15), 5, eyePaint);
    canvas.drawCircle(Offset(size.x - 15, 15), 5, eyePaint);
  }
}

class FallingItem extends PositionComponent with CollisionCallbacks {
  final bool isGood;
  final double speed = 250;

  FallingItem({required this.isGood, super.position, super.size}) {
    add(RectangleHitbox());
  }

  @override
  void update(double dt) {
    super.update(dt);
    position.y += speed * dt;
    if (position.y > (findParent<DataDefenderGame>()?.size.y ?? 1000)) {
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    if (isGood) {
      // Draw Shield
      final paint = Paint()..color = const Color(0xFF4ADE80); // Green
      canvas.drawCircle(Offset(size.x / 2, size.y / 2), size.x / 2, paint);
    } else {
      // Draw Virus
      final paint = Paint()..color = const Color(0xFFEF4444); // Red
      canvas.drawRect(size.toRect(), paint);
      // X mark
      final xPaint = Paint()
        ..color = Colors.white
        ..strokeWidth = 3;
      canvas.drawLine(const Offset(10, 10), Offset(size.x - 10, size.y - 10), xPaint);
      canvas.drawLine(Offset(size.x - 10, 10), Offset(10, size.y - 10), xPaint);
    }
  }

  @override
  void onCollisionStart(Set<Vector2> intersectionPoints, PositionComponent other) {
    super.onCollisionStart(intersectionPoints, other);
    if (other is Player) {
      final game = findParent<DataDefenderGame>();
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
