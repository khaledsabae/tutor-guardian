import 'dart:math';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flame/game.dart';
import 'package:flame/collisions.dart';
import 'package:flutter/material.dart';

import '../emoji_sprite.dart';

class HealthyHeroGame extends FlameGame with HasCollisionDetection, TapCallbacks {
  late HeroPlayer player;
  late TextComponent scoreText;
  int score = 0;
  bool isGameOver = false;
  double spawnTimer = 0;
  final Random _random = Random();
  final Function(int) onGameOver;

  HealthyHeroGame({required this.onGameOver});

  @override
  Future<void> onLoad() async {
    camera.viewfinder.anchor = Anchor.topLeft;

    // Background color (Sunny day)
    add(RectangleComponent(
      size: size,
      paint: Paint()..color = const Color(0xFF38BDF8), // Sky blue
    ));
    
    // Ground
    add(RectangleComponent(
      position: Vector2(0, size.y - 100),
      size: Vector2(size.x, 100),
      paint: Paint()..color = const Color(0xFF4ADE80), // Green grass
    ));

    // Add Player
    player = HeroPlayer()
      ..position = Vector2(50, size.y - 150)
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
    if (spawnTimer > 1.2) {
      spawnTimer = 0;
      _spawnObstacle();
    }
  }

  // Healthy foods to collect vs unhealthy things to jump over.
  static const _good = ['🍎', '🥦', '🥕', '💧', '🍌', '🥛'];
  static const _bad = ['🍬', '🍭', '🍔', '🥤', '😈'];

  void _spawnObstacle() {
    final isGood = _random.nextDouble() > 0.45;
    final height = isGood ? (_random.nextBool() ? 150.0 : 230.0) : 150.0;
    add(ObstacleItem(
      isGood: isGood,
      emoji: (isGood ? _good : _bad)[_random.nextInt(isGood ? _good.length : _bad.length)],
      position: Vector2(size.x, size.y - height),
      size: Vector2(44, 44),
    ));
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (isGameOver) return;
    player.jump();
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

class HeroPlayer extends PositionComponent with CollisionCallbacks {
  double yVelocity = 0;
  final double gravity = 1500;
  final double jumpForce = -650;
  bool isJumping = false;

  HeroPlayer() {
    add(RectangleHitbox());
  }

  @override
  void update(double dt) {
    super.update(dt);
    
    // Apply gravity
    yVelocity += gravity * dt;
    position.y += yVelocity * dt;

    // Floor collision
    final groundY = (findParent<HealthyHeroGame>()?.size.y ?? 1000) - 150;
    if (position.y >= groundY) {
      position.y = groundY;
      yVelocity = 0;
      isJumping = false;
    }
  }

  void jump() {
    if (!isJumping) {
      isJumping = true;
      yVelocity = jumpForce;
    }
  }

  @override
  void render(Canvas canvas) {
    paintEmoji(canvas, '🦸', size.toSize());
  }
}

class ObstacleItem extends PositionComponent with CollisionCallbacks {
  final bool isGood;
  final String emoji;
  final double speed = 250;

  ObstacleItem({
    required this.isGood,
    required this.emoji,
    super.position,
    super.size,
  }) {
    add(RectangleHitbox());
  }

  @override
  void update(double dt) {
    super.update(dt);
    position.x -= speed * dt;
    if (position.x < -100) {
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    paintEmoji(canvas, emoji, size.toSize());
  }

  @override
  void onCollisionStart(Set<Vector2> intersectionPoints, PositionComponent other) {
    super.onCollisionStart(intersectionPoints, other);
    if (other is HeroPlayer) {
      final game = findParent<HealthyHeroGame>();
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
