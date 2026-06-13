/// Tree of Deeds Game — P1.4 Improved (شجرة الأخلاق 🌳).
///
/// مستوى 1–10 مع صعوبة متدرجة، حياة، نمو الشجرة، أعمال صالحة/سيئة، ورسومات أفضل.
/// التعليمي: تعلم أن الأعمال الصالحة تبني شخصية جميلة والأعمال السيئة تضر بالبيئة.
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

/// Configuration for Tree of Deeds at a specific level.
class TreeOfDeedsConfig {
  final GameConfig config;
  final double deedSpeed;
  final double goodDeedRatio;
  int lives;
  final int deedsPerWave;
  final double waveInterval;
  final int scorePerDeed;
  final double growthPerDeed;

  TreeOfDeedsConfig({
    required this.config,
    required this.deedSpeed,
    required this.goodDeedRatio,
    required this.lives,
    required this.deedsPerWave,
    required this.waveInterval,
    required this.scorePerDeed,
    required this.growthPerDeed,
  });

  static  level1 = TreeOfDeedsConfig(
    config: GameConfig.defaultConfig,
    deedSpeed: 130,
    goodDeedRatio: 0.7,
    lives: 3,
    deedsPerWave: 1,
    waveInterval: 1.2,
    scorePerDeed: 10,
    growthPerDeed: 0.05,
  );

  factory TreeOfDeedsConfig.forLevel(int level) {
    if (level == 1) return level1;

    final baseConfig = GameConfig.forLevel(level);
    final speedBoost = 1.0 + (level - 1) * 0.08;
    final extraLives = max(0, (level - 1) ~/ 3);
    final extraDeeds = min(1, (level - 1) ~/ 4);
    final fasterWaves = max(0.6, 1.2 - (level - 1) * 0.06);

    return TreeOfDeedsConfig(
      config: GameConfig.forLevel(level),
      deedSpeed: (130 * speedBoost).roundToDouble(),
      goodDeedRatio: max(0.5, 0.7 - (level - 1) * 0.03),
      lives: min(5, 3 + extraLives),
      deedsPerWave: min(2, 1 + ((level - 1) ~/ 4)),
      waveInterval: fasterWaves,
      scorePerDeed: 10 + (level - 1) * 3,
      growthPerDeed: 0.05 + (level - 1) * 0.01,
    );
  }
}

/// Tree of Deeds Game — Improved with levels, lives, tree growth, good/bad deeds.
class TreeOfDeedsGame extends FlameGame with HasCollisionDetection, TapCallbacks {
  late TreeComponent tree;
  late TextComponent scoreText;
  late TextComponent livesText;
  late TextComponent levelText;

  int score = 0;
  int level = 1;
  bool isGameOver = false;
  bool isPaused = false;
  double spawnTimer = 0;
  int lives = 3;

  final TreeOfDeedsConfig gameConfig;
  final Random _random = Random();
  final Function(int, bool, int) onGameComplete;
  bool _mounted = true;

  TreeOfDeedsGame({
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

    // Background with gradient (sunrise)
    add(RectangleComponent(
      size: size,
      paint: Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFFFDE047), Color(0xFFF59E0B), Color(0xFFF59E0B)],
        ).createShader(Rect.fromLTWH(0, 0, size.x, size.y)),
    ));

    // Ground
    add(RectangleComponent(
      position: Vector2(0, size.y - 100),
      size: Vector2(size.x, 100),
      paint: Paint()
        ..shader = const LinearGradient(
          colors: [Color(0xFFD97706), Color(0xFFB45309)],
        ).createShader(Rect.fromLTWH(0, 0, size.x, 100)),
    ));

    // Tree
    tree = TreeComponent()
      ..position = Vector2(size.x / 2 - 50, size.y - 200)
      ..size = Vector2(100, 100);
    add(tree);

    // Score Text
    scoreText = TextComponent(
      text: 'الحسنات: 0',
      position: Vector2(20, 40),
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Color(0xFF422006),
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
          color: Color(0xFFD97706),
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
      _spawnDeed();
    }
  }

  void _spawnDeed() {
    final isGood = _random.nextDouble() < gameConfig.goodDeedRatio;
    final startX = _random.nextDouble() * (size.x - 50);
    final deedSpeed = gameConfig.deedSpeed * gameConfig.config.speedMultiplier * gameConfig.config.difficulty.multiplier;

    add(DeedItem(
      isGood: isGood,
      position: Vector2(startX, -60),
      size: Vector2(48, 48),
      speed: gameConfig.deedSpeed * gameConfig.config.speedMultiplier * gameConfig.config.difficulty.multiplier,
      gameConfig: gameConfig,
    ));
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (isGameOver || isPaused) return;
    // Deeds handle their own taps
  }

  @override
  bool onKeyEvent(KeyEvent event, Set<LogicalKeyboardKey> keysPressed) {
    if (isGameOver || isPaused) return false;
    if (keysPressed.contains(LogicalKeyboardKey.escape)) {
      isPaused = !isPaused;
      if (isPaused) pauseEngine(); else resumeEngine();
      return true;
    }
    return false;
  }

  void loseLife() {
    if (!_mounted) return;
    gameConfig.lives--;
    if (_mounted) {
      livesText.text = '❤️ ${gameConfig.lives}';
    }
    if (gameConfig.lives <= 0) {
      triggerGameOver();
    } else {
      // Screen shake effect
      _screenShake();
    }
  }

  void increaseScore(int points) {
    score += points;
    if (_mounted) {
      scoreText.text = 'الحسنات: $score';
      tree.grow(gameConfig.growthPerDeed);
    }
    checkLevelComplete();
  }

  void _screenShake() {
    score += points;
    if (_mounted) {
      scoreText.text = 'الحسنات: $score';
      tree.grow(gameConfig.growthPerDeed);
    }
    checkLevelComplete();
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

/// Tree Component with growth animation.
class TreeComponent extends PositionComponent with CollisionCallbacks {
  double _growthStage = 0.0;
  double _swayTimer = 0;
  double _swayOffset = 0;

  TreeComponent() {
    add(RectangleHitbox());
  }

  void grow(double amount) {
    _growthStage = min(1.0, _growthStage + amount);
    size = Vector2(100 + 40 * _growthStage, 100 + 40 * _growthStage);
    position.y -= 20 * amount; // Move up as it grows
  }

  @override
  void update(double dt) {
    super.update(dt);
    _swayTimer += dt;
    _swayOffset = sin(_swayTimer * 0.8) * 3;
    position.x = position.x + _swayOffset - tree?.position.x ?? 0; // Gentle sway
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final box = Size(size.x, size.y);
    final center = Offset(size.x / 2, size.y / 2);

    // Tree trunk
    final trunkRect = Rect.fromCenter(
      center: center + Offset(0, box.height * 0.35),
      width: 20 + 10 * _growthStage,
      height: 50 + 30 * _growthStage,
    );
    final trunkPaint = Paint()
      ..shader = const LinearGradient(
        colors: [Color(0xFF8D6E63), Color(0xFF6D4C41)],
      ).createShader(trunkRect);
    canvas.drawRect(trunkRect, trunkPaint);

    // Trunk texture lines
    final barkPaint = Paint()..color = const Color(0xFF5D4037)..strokeWidth = 1;
    for (int i = 0; i < 5; i++) {
      final y = trunkRect.top + (trunkRect.height / 5) * i;
      canvas.drawLine(Offset(trunkRect.left, y), Offset(trunkRect.right, y), Paint()..color = const Color(0xFF795548)..strokeWidth = 1);
    }

    // Tree canopy layers
    final layers = 3 + (_growthStage * 2).floor();
    for (int i = 0; i < layers; i++) {
      final layerProgress = i / max(1, layers - 1);
      final layerY = trunkRect.top - 20 - layerProgress * (80 + 60 * _growthStage);
      final layerWidth = (100 + 60 * _growthStage) * (1.0 - layerProgress * 0.3);
      final layerHeight = 50 + 30 * _growthStage;

      final layerRect = RRect.fromRectAndRadius(
        Rect.fromCenter(
          center: Offset(center.dx + size.x * 0.02, layerY + layerHeight / 2),
          width: layerWidth,
          height: layerHeight,
        ),
        const Radius.circular(25),
      );

      final alpha = 0.7 + 0.3 * (1 - layerProgress);
      final canopyPaint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0xFF4ADE80).withValues(alpha: alpha),
            Color(0xFF22C55E).withValues(alpha: alpha),
          ],
        ).createShader(layerRect.outerRect);
      canvas.drawRRect(layerRect, canopyPaint);

      // Layer highlight
      final highlightPaint = Paint()
        ..color = const Color(0xFF86EFAC).withValues(alpha: 0.4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2;
      canvas.drawRRect(layerRect, highlightPaint);
    }

    // Fruits/flowers based on growth
    if (_growthStage > 0.3) {
      final fruitPaint = Paint()..color = const Color(0xFFEAB308);
      for (int i = 0; i < (_growthStage * 8).floor(); i++) {
        final angle = (i * 2.5 + _swayTimer) % (2 * pi);
        final radius = 30 + 40 * _growthStage;
        final x = center.dx + cos(i * 1.2 + _swayTimer * 0.5) * radius * 0.3;
        final y = trunkRect.top - 20 - sin(i * 1.2) * radius * 0.2;
        canvas.drawCircle(Offset(x, y), 4 + 2 * _growthStage, Paint()..color = const Color(0xFFEAB308));
      }
    }

    // Gentle sway
    _swayTimer += 0.01;
  }
}

/// Deed Item - good deed (catch to grow) or bad deed (tap to destroy).
class DeedItem extends PositionComponent with CollisionCallbacks, TapCallbacks {
  final bool isGood;
  final double speed;
  final TreeOfDeedsConfig gameConfig;
  final String emoji;

  DeedItem({
    required this.isGood,
    required super.position,
    required super.size,
    required this.speed,
    required this.gameConfig,
  }) : emoji = isGood
        ? ['⭐', '🌟', '✨', '💫', '🌈', '💖', '🙏', '🤝', '📚', '🌱'][Random().nextInt(10)]
        : ['☁️', '🌪️', '💨', '😰', '😢', '😡', '👿', '💀', '☠️', '🚫'][Random().nextInt(10)] {
    add(RectangleHitbox());
  }

  @override
  void update(double dt) {
    super.update(dt);
    position.y += speed * dt;
    position.x += sin(position.y / 30) * 1.5;

    if (position.y > (findParent<TreeOfDeedsGame>()?.size.y ?? 1000) + 100) {
      if (!isGood) {
        // Bad deed reached tree
        final game = findParent<TreeOfDeedsGame>();
        game?.loseLife();
      }
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);

    // Glow
    final glowColor = isGood ? const Color(0xFF22C55E) : const Color(0xFFEF4444);
    final glowPaint = Paint()
      ..color = glowColor.withValues(alpha: 0.3)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(size.x / 2, size.y / 2), max(size.x, size.y) / 2 + 10, glowPaint);

    // Main item
    paintEmoji(canvas, emoji, size.toSize());

    // Ring indicator
    final ringPaint = Paint()
      ..color = isGood ? const Color(0xFF22C55E) : const Color(0xFFEF4444)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4;
    canvas.drawCircle(Offset(size.x / 2, size.y / 2), max(size.x, size.y) / 2 + 6, ringPaint);
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (!isGood) {
      // Destroy bad deed
      removeFromParent();
    }
  }

  @override
  void onCollisionStart(Set<Vector2> intersectionPoints, PositionComponent other) {
    super.onCollisionStart(intersectionPoints, other);
    if (other is TreeComponent) {
      final game = findParent<TreeOfDeedsGame>();
      if (game != null && !game.isGameOver && !game.isPaused) {
        if (isGood) {
          game.increaseScore(gameConfig.scorePerDeed);
        } else {
          game.triggerGameOver();
        }
      }
      removeFromParent();
    }
  }
}

/// LevelBanner reused
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
      colors: [Color(0xFFF59E0B), Color(0xFFD97706)],
    ).createShader(Rect.fromLTWH(0, 0, 300, 80));
    canvas.drawRRect(rect, bgPaint);

    final borderPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawRRect(rect, borderPaint);

    final textPaint = TextPaint(style: TextStyle(
      color: const Color(0xFF422006),
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