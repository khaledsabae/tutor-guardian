import 'dart:math';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flame/game.dart';
import 'package:flame/collisions.dart';
import 'package:flutter/material.dart';

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

  void _spawnObstacle() {
    final isGood = _random.nextDouble() > 0.5; // 50% chance for healthy vs bad
    // Good items (apple/water) are floating slightly higher or on ground
    // Bad items (monster/sugar) are on ground
    final height = isGood ? (_random.nextBool() ? 150.0 : 220.0) : 150.0;
    
    add(ObstacleItem(
      isGood: isGood,
      position: Vector2(size.x, size.y - height),
      size: Vector2(40, 40),
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
  final _paint = Paint()..color = Colors.white; 
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
    // Draw Hero (White square with a cape)
    canvas.drawRRect(
      RRect.fromRectAndRadius(size.toRect(), const Radius.circular(8)),
      _paint,
    );
    // Cape
    final capePaint = Paint()..color = const Color(0xFFEF4444);
    canvas.drawRect(const Rect.fromLTWH(-10, 10, 10, 30), capePaint);
  }
}

class ObstacleItem extends PositionComponent with CollisionCallbacks {
  final bool isGood;
  final double speed = 250;

  ObstacleItem({required this.isGood, super.position, super.size}) {
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
    if (isGood) {
      // Draw Apple (Healthy)
      final paint = Paint()..color = const Color(0xFFDC2626); // Apple red
      canvas.drawCircle(Offset(size.x / 2, size.y / 2), size.x / 2, paint);
      final leaf = Paint()..color = const Color(0xFF16A34A);
      canvas.drawOval(Rect.fromLTWH(size.x / 2 - 5, -5, 10, 10), leaf);
    } else {
      // Draw Sugar/Monster (Unhealthy)
      final paint = Paint()..color = const Color(0xFF9333EA); // Purple monster
      canvas.drawRect(size.toRect(), paint);
      // Spikes
      final spikes = Paint()..color = Colors.white;
      canvas.drawCircle(const Offset(10, 10), 4, spikes);
      canvas.drawCircle(Offset(size.x - 10, 10), 4, spikes);
    }
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
