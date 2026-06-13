/// Data Defender Game — P1.4 Improved (أمان رقمي).
///
/// مستوى 1–10 مع صعوبة متدرجة، حياة مركّبة، ورسومات أفضل.
/// التعليمي: تعلم حماية البيانات الشخصية من الفيروسات والروابط المشبوهة.
library;

import 'dart:math';
import 'package:flame/components.dart';
import 'package:flame/events.dart';
import 'package:flame/game.dart';
import 'package:flame/collisions.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../shared/game_utils.dart';
import '../emoji_sprite.dart';

/// Configuration for Data Defender at a specific level.
class DataDefenderConfig {
  final GameConfig config;
  final double playerSpeed;
  final double itemBaseSpeed;
  final double goodItemRatio;
  int lives;
  final int virusDamage;
  final int shieldDuration;

  DataDefenderConfig({
    required this.config,
    required this.playerSpeed,
    required this.itemBaseSpeed,
    required this.goodItemRatio,
    required this.lives,
    required this.virusDamage,
    required this.shieldDuration,
  });

  static final level1 = DataDefenderConfig(
    config: GameConfig.defaultConfig,
    playerSpeed: 60,
    itemBaseSpeed: 200,
    goodItemRatio: 0.6,
    lives: 3,
    virusDamage: 1,
    shieldDuration: 5,
  );

  factory DataDefenderConfig.forLevel(int level) {
    final baseConfig = GameConfig.forLevel(level);
    if (level == 1) return level1;

    // Progressive upgrades
    final extraLives = max(0, (level - 1) ~/ 3);
    final speedBoost = 1.0 + (level - 1) * 0.1;
    final shieldUnlocked = level >= 3;
    final doubleShield = level >= 6;
    final timeoutShield = level >= 8;

    return DataDefenderConfig(
      config: GameConfig.forLevel(level),
      playerSpeed: (60 * speedBoost).roundToDouble(),
      itemBaseSpeed: (200 * speedBoost).roundToDouble(),
      goodItemRatio: max(0.35, 0.6 - (level - 1) * 0.03),
      lives: min(5, 3 + extraLives),
      virusDamage: level >= 5 ? 2 : 1,
      shieldDuration: level >= 8 ? 8 : (shieldUnlocked ? 5 : 0),
    );
  }
}

/// Data Defender Game — Improved with levels, lives, power-ups, and shield mechanic.
class DataDefenderGame extends FlameGame with HasCollisionDetection, TapCallbacks {
  late Player player;
  late TextComponent scoreText;
  late TextComponent livesText;
  late TextComponent levelText;
  late TextComponent shieldText;

  int score = 0;
  int level = 1;
  bool isGameOver = false;
  bool isPaused = false;
  double spawnTimer = 0;
  double shieldTimer = 0;
  int shieldsAvailable = 0;
  bool shieldActive = false;

  final DataDefenderConfig gameConfig;
  final Random _random = Random();
  final Function(int, bool, int) onGameComplete;
  bool _mounted = true;

  DataDefenderGame({
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

    // Background with gradient
    add(RectangleComponent(
      size: size,
      paint: Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0F172A), Color(0xFF1E293B), Color(0xFF0F172A)],
        ).createShader(Rect.fromLTWH(0, 0, size.x, size.y)),
    ));

    // Grid pattern background
    _addGridPattern();

    // Player
    player = Player(gameConfig: gameConfig)
      ..position = Vector2(size.x / 2 - 30, size.y - 120)
      ..size = Vector2(64, 64);
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
      position: Vector2(size.x - 120, 40),
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
          color: Color(0xFF06B6D4),
          fontSize: 18,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
    add(levelText);

    // Shield indicator
    shieldText = TextComponent(
      text: '🛡️ درع: 0',
      position: Vector2(size.x - 100, 80),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Color(0xFF06B6D4),
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
    add(shieldText);

    // Level indicator banner briefly
    _showLevelBanner();
  }

  void _addGridPattern() {
    add(GridPatternComponent(size: size));
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

    if (shieldActive) {
      shieldTimer -= dt;
      if (shieldTimer <= 0) {
        shieldActive = false;
        _updateShieldUI();
      }
    }

    spawnTimer += dt;
    final spawnInterval = 0.8 / gameConfig.config.spawnRateMultiplier;
    if (spawnTimer > spawnInterval) {
      spawnTimer = 0;
      _spawnItem();
    }
  }

  void _spawnItem() {
    final isGood = _random.nextDouble() < gameConfig.goodItemRatio;
    final startX = _random.nextDouble() * (size.x - 50);
    final itemSpeed = gameConfig.itemBaseSpeed * gameConfig.config.speedMultiplier * gameConfig.config.difficulty.multiplier;
    final spawnInterval = 0.8 / gameConfig.config.spawnRateMultiplier;

    add(FallingItem(
      isGood: isGood,
      position: Vector2(startX, -60),
      size: Vector2(50, 50),
      speed: itemSpeed,
      gameConfig: gameConfig,
    ));
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (isGameOver || isPaused) return;
    if (event.localPosition.x < size.x / 2) {
      player.moveLeft(gameConfig.playerSpeed);
    } else {
      player.moveRight(gameConfig.playerSpeed, size.x);
    }
  }

  @override
  bool onKeyEvent(KeyEvent event, Set<LogicalKeyboardKey> keysPressed) {
    if (isGameOver || isPaused) return false;
    if (keysPressed.contains(LogicalKeyboardKey.arrowLeft)) {
      player.moveLeft(gameConfig.playerSpeed);
    }
    if (keysPressed.contains(LogicalKeyboardKey.arrowRight)) {
      player.moveRight(gameConfig.playerSpeed, size.x);
    }
    if (keysPressed.contains(LogicalKeyboardKey.space)) {
      _activateShield();
    }
    if (keysPressed.contains(LogicalKeyboardKey.escape)) {
      _togglePause();
    }
    return true;
  }

  void _togglePause() {
    isPaused = !isPaused;
    if (isPaused) {
      pauseEngine();
    } else {
      resumeEngine();
    }
  }

  void _activateShield() {
    if (shieldActive || shieldsAvailable <= 0) return;
    shieldActive = true;
    shieldsAvailable--;
    shieldTimer = gameConfig.shieldDuration.toDouble();
    _updateShieldUI();
    player.activateShield();
    Future.delayed(Duration(seconds: gameConfig.shieldDuration), () {
      if (_mounted) player.deactivateShield();
    });
  }

  void _updateShieldUI() {
    if (!_mounted) return;
    shieldText.text = shieldActive
        ? '🛡️ درع: ${shieldTimer.ceil()}ث'
        : '🛡️ درع: $shieldsAvailable';
  }

  void addLife() {
    if (!_mounted) return;
    gameConfig.lives++;
    livesText.text = '❤️ ${gameConfig.lives}';
  }

  void loseLife() {
    if (shieldActive) return;
    if (!_mounted) return;
    gameConfig.lives--;
    livesText.text = '❤️ ${gameConfig.lives}';
    if (gameConfig.lives <= 0) {
      triggerGameOver();
    } else {
      player.flashInvincible();
    }
  }

  void increaseScore(int points) {
    score += points;
    if (_mounted) scoreText.text = 'النقاط: $score';
  }

  void addShield() {
    shieldsAvailable++;
    _updateShieldUI();
  }

  void triggerGameOver() {
    isGameOver = true;
    pauseEngine();
    onGameComplete(score, false, level);
  }

  void levelComplete() {
    isGameOver = true;
    pauseEngine();
    onGameComplete(score, true, level);
  }

  void checkLevelComplete() {
    if (score >= gameConfig.config.scoreToWin && !isGameOver) {
      levelComplete();
    }
  }

  @override
  void onRemove() {
    _mounted = false;
    super.onRemove();
  }
}

/// Grid pattern background for cyber theme.
class GridPatternComponent extends PositionComponent {
  GridPatternComponent({required super.size});

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final spacing = 40.0;
    final paint = Paint()
      ..color = const Color(0xFF06B6D4).withValues(alpha: 0.02)
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;

    for (double x = 0; x <= size.x; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.y), paint);
    }
    for (double y = 0; y <= size.y; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.x, y), paint);
    }
  }
}

/// Level banner that appears at level start.
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
      colors: [Color(0xFF06B6D4), Color(0xFF0891B2)],
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

/// Player with shield, movement animation, and visual effects.
class Player extends PositionComponent with CollisionCallbacks {
  final DataDefenderConfig gameConfig;
  bool _shieldActive = false;
  double _flashTimer = 0;

  Player({required this.gameConfig}) {
    add(RectangleHitbox());
  }

  void moveLeft(double speed) {
    position.x = max(30.0, position.x - speed);
  }

  void moveRight(double speed, double screenWidth) {
    position.x = min(screenWidth - 90.0, position.x + speed);
  }

  void activateShield() {
    _shieldActive = true;
  }

  void deactivateShield() {
    _shieldActive = false;
  }

  void flashInvincible() {
    _flashTimer = 0.5;
  }

  @override
  void update(double dt) {
    super.update(dt);
    if (_flashTimer > 0) {
      _flashTimer -= dt;
    }
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final box = Size(size.x, size.y);
    final center = Offset(size.x / 2, size.y / 2);
    final radius = min(size.x, size.y) / 2 - 4;

    if (_shieldActive) {
      final shieldPaint = Paint()
        ..shader = const LinearGradient(
          colors: [Color(0xFF06B6D4), Color(0xFF80D0C7)],
        ).createShader(Rect.fromCircle(center: center, radius: radius + 15))
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4;
      canvas.drawCircle(center, radius + 15, shieldPaint);

      final glowPaint = Paint()
        ..color = const Color(0xFF06B6D4).withValues(alpha: 0.3)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(center, radius + 10, glowPaint);
    }

    final bodyRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: center, width: size.x - 8, height: size.y - 8),
      const Radius.circular(16),
    );
    final bodyPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          const Color(0xFF1E293B).withValues(alpha: 0.9),
          const Color(0xFF334155).withValues(alpha: 0.7),
        ],
      ).createShader(bodyRect.outerRect);
    canvas.drawRRect(bodyRect, bodyPaint);

    final borderPaint = Paint()
      ..color = const Color(0xFF06B6D4).withValues(alpha: 0.8)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawRRect(bodyRect, borderPaint);

    final eyePaint = Paint()..color = const Color(0xFF06B6D4);
    canvas.drawCircle(Offset(center.dx - 15, center.dy - 8), 6, eyePaint);
    canvas.drawCircle(Offset(center.dx + 15, center.dy - 8), 6, eyePaint);
    canvas.drawCircle(Offset(center.dx - 15, center.dy - 8), 2, Paint()..color = Colors.white);
    canvas.drawCircle(Offset(center.dx + 15, center.dy - 8), 2, Paint()..color = Colors.white);

    final antennaPaint = Paint()
      ..color = const Color(0xFF06B6D4)
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(center.dx, center.dy - radius),
      Offset(center.dx, center.dy - radius - 20),
      antennaPaint,
    );
    canvas.drawCircle(Offset(center.dx, center.dy - radius - 20), 4, Paint()..color = const Color(0xFF06B6D4));
  }
}

/// Falling item with type (good/bad) and visual variety.
class FallingItem extends PositionComponent with CollisionCallbacks {
  final bool isGood;
  final double speed;
  final DataDefenderConfig gameConfig;
  final String emoji;
  double _rotation = 0;

  static const _goodEmojis = ['🔒', '🛡️', '🔐', '✅', '💾', '🔑'];
  static const _badEmojis = ['🦠', '👾', '⚠️', '☠️', '💣', '🔴'];

  FallingItem({
    required this.isGood,
    required super.position,
    required super.size,
    required this.speed,
    required this.gameConfig,
  }) : emoji = isGood
        ? _goodEmojis[Random().nextInt(_goodEmojis.length)]
        : _badEmojis[Random().nextInt(_badEmojis.length)] {
    add(RectangleHitbox());
  }

  @override
  void update(double dt) {
    super.update(dt);
    position.y += speed * dt;
    _rotation += dt * 2;

    if (position.y > (findParent<DataDefenderGame>()?.size.y ?? 1000) + 100) {
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final box = Size(size.x, size.y);
    canvas.save();
    canvas.translate(size.x / 2, size.y / 2);
    canvas.rotate(_rotation);
    paintEmoji(canvas, emoji, box);
    canvas.restore();

    final ringPaint = Paint()
      ..color = isGood ? const Color(0xFF10B981) : const Color(0xFFEF4444)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawCircle(Offset(size.x / 2, size.y / 2), max(size.x, size.y) / 2 + 4, ringPaint);
  }

  @override
  void onCollisionStart(Set<Vector2> intersectionPoints, PositionComponent other) {
    super.onCollisionStart(intersectionPoints, other);
    if (other is Player) {
      final game = findParent<DataDefenderGame>();
      if (game != null && !game.isGameOver && !game.isPaused) {
        if (isGood) {
          game.increaseScore(gameConfig.config.scorePerItem);
          if (Random().nextDouble() < 0.15) {
            game.addShield();
          }
          if (Random().nextDouble() < 0.05) {
            game.addLife();
          }
        } else {
          game.loseLife();
        }
      }
      removeFromParent();
    }
  }
}