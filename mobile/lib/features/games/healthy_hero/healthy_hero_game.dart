/// Healthy Hero Game — P1.4 Improved (رحلة البطل الصحي 🩺).
///
/// مستوى 1–10 مع صعوبة متدرجة، حياة، أطعمة صحية/غير صحية، قفز، ورسومات أفضل.
/// التعليمي: تعلم عادات الأكل الصحي والنوم المبكر.
library;

import 'dart:math';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flame/game.dart';
import 'package:flame/collisions.dart';
import 'package:flutter/material.dart';

import '../shared/game_utils.dart';
import '../emoji_sprite.dart';

/// Configuration for Healthy Hero at a specific level.
class HealthyHeroConfig {
  final GameConfig config;
  final double jumpForce;
  final double gravity;
  final double obstacleSpeed;
  final double goodObstacleRatio;
  final int lives;
  final int obstaclesPerWave;
  final double waveInterval;
  final int scorePerItem;
  final double groundHeight;

  const HealthyHeroConfig({
    required this.config,
    required this.jumpForce,
    required this.gravity,
    required this.obstacleSpeed,
    required this.goodObstacleRatio,
    required this.lives,
    required this.obstaclesPerWave,
    required this.waveInterval,
    required this.scorePerItem,
    required this.groundHeight,
  });

  static const level1 = HealthyHeroConfig(
    config: GameConfig.defaultConfig,
    jumpForce: -650,
    gravity: 1500,
    obstacleSpeed: 250,
    goodObstacleRatio: 0.55,
    lives: 3,
    obstaclesPerWave: 1,
    waveInterval: 1.5,
    scorePerItem: 10,
    groundHeight: 100,
  );

  factory HealthyHeroConfig.forLevel(int level) {
    if (level == 1) return level1;

    final baseConfig = GameConfig.forLevel(level);
    final speedBoost = 1.0 + (level - 1) * 0.08;
    final extraLives = max(0, (level - 1) ~/ 3);
    final extraObstacles = min(1, (level - 1) ~/ 4);
    final fasterWaves = max(0.8, 1.5 - (level - 1) * 0.08);

    return HealthyHeroConfig(
      config: GameConfig.forLevel(level),
      jumpForce: (-650 * speedBoost).roundToDouble(),
      gravity: (1500 * speedBoost).roundToDouble(),
      obstacleSpeed: (250 * speedBoost).roundToDouble(),
      goodObstacleRatio: max(0.45, 0.55 - (level - 1) * 0.02),
      lives: min(5, 3 + max(0, (level - 1) ~/ 3)),
      obstaclesPerWave: min(2, 1 + ((level - 1) ~/ 4)),
      waveInterval: fasterWaves,
      scorePerItem: 10 + (level - 1) * 2,
      groundHeight: 100,
    );
  }
}

/// Healthy Hero Game — Improved with levels, lives, jump physics, healthy vs junk food.
class HealthyHeroGame extends FlameGame with HasCollisionDetection, TapCallbacks {
  late HeroPlayer player;
  late TextComponent scoreText;
  late TextComponent livesText;
  late TextComponent levelText;

  int score = 0;
  int level = 1;
  bool isGameOver = false;
  bool isPaused = false;
  double spawnTimer = 0;
  int lives = 3;

  final HealthyHeroConfig gameConfig;
  final Random _random = Random();
  final Function(int, bool, int) onGameComplete;
  bool _mounted = true;

  HealthyHeroGame({
    required this.gameConfig,
    required this.onGameComplete,
  });

  @override
  Future<void> onLoad() async {
    camera.viewfinder.anchor = Anchor.topLeft;
    await _setupGame();
  }

  Future<void> _setupGame() async {
    camera.viewfinder.anchor = Anchor.topLeft;
    lives = gameConfig.lives;

    // Background with gradient (sunny day)
    add(RectangleComponent(
      size: size,
      paint: Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF38BDF8), Color(0xFF06B6D4), Color(0xFF0EA5E9)],
        ).createShader(Rect.fromLTWH(0, 0, size.x, size.y)),
    ));

    // Ground
    add(RectangleComponent(
      position: Vector2(0, size.y - gameConfig.groundHeight),
      size: Vector2(size.x, gameConfig.groundHeight),
      paint: Paint()
        ..shader = const LinearGradient(
          colors: [Color(0xFF22C55E), Color(0xFF16A34A)],
        ).createShader(Rect.fromLTWH(0, 0, size.x, gameConfig.groundHeight)),
    ));

    // Player
    player = HeroPlayer(gameConfig: gameConfig)
      ..position = Vector2(50, size.y - gameConfig.groundHeight - 80)
      ..size = Vector2(60, 60);
    add(player);

    // Score Text
    scoreText = TextComponent(
      text: 'النقاط: 0',
      position: Vector2(20, 40),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Colors.white,
          fontSize: 22,
          fontWeight: FontWeight.bold,
          shadows: [Shadow(color: Colors.black87, blurRadius: 4, offset: Offset(0, 2))],
        ),
      ),
    );
    add(scoreText);

    // Lives Text
    livesText = TextComponent(
      text: '❤️ ${gameConfig.lives}',
      position: Vector2(size.x - 100, 40),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Colors.redAccent,
          fontSize: 22,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
    add(livesText);

    // Level Text
    levelText = TextComponent(
      text: 'المستوى ${gameConfig.config.level}',
      position: Vector2(size.x / 2 - 50, 40),
      anchor: Anchor.center,
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Color(0xFF22C55E),
          fontSize: 18,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
    add(levelText);

    _showLevelBanner();
  }

  void _showLevelBanner() {
    final banner = LevelBanner(
      text: 'المستوى ${gameConfig.config.level}',
      position: Vector2(size.x / 2, size.y / 2),
    );
    add(banner);
    Future.delayed(const Duration(seconds: 2), () => banner.removeFromParent());
  }

  @override
  void update(double dt) {
    if (isGameOver || isPaused) return;
    super.update(dt);

    spawnTimer += dt;
    final spawnInterval = gameConfig.waveInterval / gameConfig.config.spawnRateMultiplier;
    if (spawnTimer > spawnInterval) {
      spawnTimer = 0;
      _spawnWave();
    }
  }

  void _spawnWave() {
    final obstacleSpeed = gameConfig.obstacleSpeed * gameConfig.config.speedMultiplier * gameConfig.config.difficulty.multiplier;

    for (int i = 0; i < gameConfig.obstaclesPerWave; i++) {
      final isGood = _random.nextDouble() < gameConfig.goodObstacleRatio;
      final goodFoods = ['🍎', '🥦', '🥕', '💧', '🍌', '🥛', '🥑', '🌰'];
      final badFoods = ['🍬', '🍭', '🍔', '🥤', '🍟', '🍩', '🍫', '😈'];

      final emoji = isGood
          ? ['🍎', '🥦', '🥕', '💧', '🍌', '🥛', '🥑', '🌰'][_random.nextInt(8)]
          : ['🍬', '🍭', '🍔', '🥤', '🍟', '🍩', '🍫', '😈'][_random.nextInt(8)];

      final height = isGood ? (_random.nextBool() ? 150.0 : 230.0) : 130.0;

      add(ObstacleItem(
        isGood: isGood,
        emoji: emoji,
        position: Vector2(size.x + (_random.nextDouble() * 200), size.y - height),
        size: Vector2(48, 48),
        speed: gameConfig.obstacleSpeed * gameConfig.config.speedMultiplier * gameConfig.config.difficulty.multiplier,
        gameConfig: gameConfig,
      ));
    }
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (isGameOver || isPaused) return;
    player.jump();
  }

  @override
  bool onKeyEvent(KeyEvent event, Set<LogicalKeyboardKey> keysPressed) {
    if (isGameOver || isPaused) return false;
    if (keysPressed.contains(LogicalKeyboardKey.space) || keysPressed.contains(LogicalKeyboardKey.arrowUp)) {
      player.jump();
    }
    if (keysPressed.contains(LogicalKeyboardKey.escape)) {
      isPaused = !isPaused;
      if (isPaused) pauseEngine(); else resumeEngine();
    }
    return true;
  }

  void loseLife() {
    if (!_mounted) return;
    gameConfig.lives--;
    if (_mounted) {
      findComponent<livesText>()?.text = '❤️ ${gameConfig.lives}';
    }
    if (gameConfig.lives <= 0) {
      triggerGameOver();
    } else {
      player.flashInvincible();
    }
  }

  void increaseScore(int points) {
    score += points;
    if (_mounted) {
      findComponent<scoreText>()?.text = 'النقاط: $score';
    }
  }

  void triggerGameOver() {
    isGameOver = true;
    pauseEngine();
    onGameComplete(score, false, level);
  }

  void checkLevelComplete() {
    if (score >= gameConfig.config.scoreToWin && !isGameOver) {
      levelComplete();
    }
  }

  void levelComplete() {
    isGameOver = true;
    pauseEngine();
    onGameComplete(score, true, level);
  }

  @override
  void onRemove() {
    _mounted = false;
    super.onRemove();
  }
}

/// Hero Player with jump physics and visual effects.
class HeroPlayer extends PositionComponent with CollisionCallbacks {
  final HealthyHeroConfig gameConfig;
  double yVelocity = 0;
  double gravity = 1500;
  double jumpForce = -650;
  bool isJumping = false;
  bool _flashTimer = false;
  double _flashTimerValue = 0;

  HeroPlayer({required this.gameConfig}) {
    gravity = gameConfig.gravity.toDouble();
    jumpForce = gameConfig.jumpForce.toDouble();
    add(RectangleHitbox());
  }

  @override
  void onLoad() {
    super.onLoad();
    gravity = gameConfig.gravity.toDouble();
    jumpForce = gameConfig.jumpForce.toDouble();
  }

  void jump() {
    if (!isJumping && !findParent<HealthyHeroGame>()!.isGameOver) {
      isJumping = true;
      yVelocity = gameConfig.jumpForce;
    }
  }

  @override
  void update(double dt) {
    super.update(dt);

    yVelocity += gravity * dt;
    position.y += yVelocity * dt;

    final groundY = (findParent<HealthyHeroGame>()?.size.y ?? 1000) - (findParent<HealthyHeroGame>()?.gameConfig.groundHeight ?? 100) - size.y;
    if (position.y >= groundY) {
      position.y = groundY;
      yVelocity = 0;
      isJumping = false;
    }

    if (_flashTimer) {
      _flashTimerValue += dt;
      if (_flashTimerValue > 0.5) {
        _flashTimer = false;
        _flashTimerValue = 0;
      }
    }
  }

  void flashInvincible() {
    _flashTimer = true;
    _flashTimerValue = 0;
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final box = Size(size.x, size.y);
    final center = Offset(size.x / 2, size.y / 2);
    final radius = min(size.x, size.y) / 2 - 4;

    // Hero body with cape
    final bodyRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: center, width: size.x - 6, height: size.y - 6),
      const Radius.circular(16),
    );

    // Flash effect
    final bodyPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: _flashTimer
            ? [Color(0xFFFEF08A), Color(0xFFFDE047)]
            : [Color(0xFF166534), Color(0xFF15803D)],
      ).createShader(bodyRect.outerRect);
    canvas.drawRRect(bodyRect, bodyPaint);

    // Cape
    final capePaint = Paint()..color = const Color(0xFF22C55E).withValues(alpha: 0.8);
    final capePath = Path();
    capePath.moveTo(center.dx - radius, center.dy - radius);
    capePath.lineTo(center.dx - radius - 15, center.dy);
    capePath.lineTo(center.dx - radius, center.dy + radius / 2);
    capePath.close();
    canvas.drawPath(capePath, capePaint);

    // Face
    final facePaint = Paint()..color = const Color(0xFFFDBA74);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: center, width: box.width * 0.6, height: box.height * 0.5),
        const Radius.circular(12),
      ),
      facePaint,
    );

    // Eyes
    final eyePaint = Paint()..color = const Color(0xFF1F2937);
    canvas.drawCircle(Offset(center.dx - 12, center.dy - 8), 5, eyePaint);
    canvas.drawCircle(Offset(center.dx + 12, center.dy - 8), 5, eyePaint);
    canvas.drawCircle(Offset(center.dx - 12, center.dy - 8), 2, Paint()..color = Colors.white);
    canvas.drawCircle(Offset(center.dx + 12, center.dy - 8), 2, Paint()..color = Colors.white);

    // Smile
    final smilePaint = Paint()..color = const Color(0xFF1F2937)..strokeWidth = 2..style = PaintingStyle.stroke;
    final smilePath = Path();
    smilePath.moveTo(center.dx - 10, center.dy + 8);
    smilePath.quadraticBezierTo(center.dx, center.dy + 14, center.dx + 10, center.dy + 8);
    canvas.drawPath(smilePath, smilePaint);
  }
}

/// Obstacle Item - healthy food (jump to collect) or junk food (jump to avoid).
class ObstacleItem extends PositionComponent with CollisionCallbacks {
  final bool isGood;
  final String emoji;
  final double speed;
  final HealthyHeroConfig gameConfig;

  ObstacleItem({
    required this.isGood,
    required this.emoji,
    required super.position,
    required super.size,
    required this.speed,
    required this.gameConfig,
  }) {
    add(RectangleHitbox());
  }

  @override
  void update(double dt) {
    super.update(dt);
    position.x -= speed * dt;

    if (position.x < -100) {
      if (isGood) {
        // Missed good food
        final game = findParent<HealthyHeroGame>();
        if (game != null && !game.isGameOver) {
          // Small penalty for missing healthy food
        }
      }
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final box = size.toSize();

    // Glow effect
    final glowColor = isGood ? const Color(0xFF22C55E) : const Color(0xFFEF4444);
    final glowPaint = Paint()
      ..color = glowColor.withValues(alpha: 0.3)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(size.x / 2, size.y / 2), max(size.x, size.y) / 2 + 8, glowPaint);

    // Main item
    paintEmoji(canvas, emoji, box);

    // Type indicator
    final ringPaint = Paint()
      ..color = isGood ? const Color(0xFF22C55E) : const Color(0xFFEF4444)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawCircle(Offset(size.x / 2, size.y / 2), max(size.x, size.y) / 2 + 4, ringPaint);
  }

  @override
  void onCollisionStart(Set<Vector2> intersectionPoints, PositionComponent other) {
    super.onCollisionStart(intersectionPoints, other);
    if (other is HeroPlayer) {
      final game = findParent<HealthyHeroGame>();
      if (game != null && !game.isGameOver && !game.isPaused) {
        if (isGood) {
          game.increaseScore(gameConfig.scorePerItem);
        } else {
          game.loseLife();
        }
      }
      removeFromParent();
    }
  }
}

/// LevelBanner reused from shared
class LevelBanner extends PositionComponent {
  final String text;
  double _timer = 0;
  double _yOffset = -100;

  LevelBanner({required this.text, required super.position}) {
    anchor = Anchor.center;
    size = Vector2(300, 80);
    priority = 100;
  }

  @override
  void update(double dt) {
    super.update(dt);
    _timer += dt;
    if (_timer < 0.5) {
      _yOffset = -100 + 200 * _timer;
    } else if (_timer < 2.5) {
      _yOffset = 0;
    } else if (_timer < 3.0) {
      _yOffset = -100 * (_timer - 2.5);
    } else {
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    final rect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(position.x, position.y + _yOffset), width: 300, height: 80),
      const Radius.circular(20),
    );

    final bgPaint = Paint()..shader = const LinearGradient(
      colors: [Color(0xFF22C55E), Color(0xFF16A34A)],
    ).createShader(Rect.fromLTWH(0, 0, 300, 80));
    canvas.drawRRect(rect, bgPaint);

    final borderPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawRRect(rect, borderPaint);

    final textPaint = TextPaint(style: TextStyle(
      color: Colors.white,
      fontSize: 26,
      fontWeight: FontWeight.bold,
      shadows: [Shadow(color: Colors.black87, blurRadius: 4, offset: Offset(0, 2))],
    ));
    textPaint.render(canvas, text, Vector2(-100, _yOffset - 12));
  }
}

// Helper to find components
extension Finding on FlameGame {
  TextComponent? findComponent(String name) {
    for (final c in children) {
      if (c is TextComponent && c.text.startsWith(name.split(' ')[0])) return c;
    }
    return null;
  }
}