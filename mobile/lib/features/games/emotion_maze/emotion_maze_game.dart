/// Emotion Maze Game — P1.4 Improved (متاهة المشاعر 🧠).
///
/// مستوى 1–10 مع صعوبة متدرجة، حياة، آلية اختيار إيجابي/سلبي، ورسومات أفضل.
/// التعليمي: تعلم تنظيم المشاعر واختيار الردود الإيجابية.
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

/// Configuration for Emotion Maze at a specific level.
class EmotionMazeConfig {
  final GameConfig config;
  final double doorSpeed;
  final double goodDoorRatio;
  int lives;
  final int doorsPerWave;
  final double waveInterval;
  final int scorePerDoor;

  EmotionMazeConfig({
    required this.config,
    required this.doorSpeed,
    required this.goodDoorRatio,
    required this.lives,
    required this.doorsPerWave,
    required this.waveInterval,
    required this.scorePerDoor,
  });

  static  level1 = EmotionMazeConfig(
    config: GameConfig.defaultConfig,
    doorSpeed: 80,
    goodDoorRatio: 0.5,
    lives: 3,
    doorsPerWave: 2,
    waveInterval: 3.0,
    scorePerDoor: 1,
  );

  factory EmotionMazeConfig.forLevel(int level) {
    if (level == 1) return level1;

    final baseConfig = GameConfig.forLevel(level);
    final speedBoost = 1.0 + (level - 1) * 0.1;
    final extraLives = max(1, (level - 1) ~/ 3);
    final extraDoors = min(1, (level - 1) ~/ 4);
    final fasterWaves = max(1.5, 3.0 - (level - 1) * 0.15);

    return EmotionMazeConfig(
      config: GameConfig.forLevel(level),
      doorSpeed: (80 * speedBoost).roundToDouble(),
      goodDoorRatio: max(0.4, 0.5 - (level - 1) * 0.02),
      lives: min(5, 3 + extraLives),
      doorsPerWave: min(3, 2 + extraDoors),
      waveInterval: fasterWaves,
      scorePerDoor: 1 + (level - 1),
    );
  }
}

/// Emotion Maze Game — Improved with levels, lives, emotional learning feedback.
class EmotionMazeGame extends FlameGame with HasCollisionDetection, TapCallbacks {
  late TextComponent scoreText;
  late TextComponent livesText;
  late TextComponent levelText;
  late TextComponent hintText;

  int score = 0;
  int level = 1;
  bool isGameOver = false;
  bool isPaused = false;
  double waveTimer = 0;
  int lives = 3;

  final EmotionMazeConfig gameConfig;
  final Random _random = Random();
  final Function(int, bool, int) onGameComplete;
  bool _mounted = true;

  EmotionMazeGame({
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

    // Background with gradient
    add(RectangleComponent(
      size: size,
      paint: Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1E1B4B), Color(0xFF312E81), Color(0xFF1E1B4B)],
        ).createShader(Rect.fromLTWH(0, 0, size.x, size.y)),
    ));

    // Score Text
    scoreText = TextComponent(
      text: 'الأبواب المفتوحة: 0',
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
      text: '❤️ $lives',
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
          color: Color(0xFFA855F7),
          fontSize: 18,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
    add(levelText);

    // Hint text showing current emotion pair
    hintText = TextComponent(
      text: '😌 هدوء  vs  😡 غضب',
      position: Vector2(size.x / 2, 80),
      anchor: Anchor.center,
      textRenderer: TextPaint(
        style: const TextStyle(
          color: Color(0xFFA855F7),
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
    add(hintText);

    _showLevelBanner();
    _spawnWave();
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

    waveTimer += dt;
    if (waveTimer > gameConfig.waveInterval) {
      waveTimer = 0;
      _spawnWave();
    }
  }

  void _spawnWave() {
    for (int i = 0; i < gameConfig.doorsPerWave; i++) {
      final isLeftGood = _random.nextBool();
      final xPositions = [size.x * 0.25, size.x * 0.75];

      for (int j = 0; j < gameConfig.doorsPerWave; j++) {
        final isGood = (j == 0) ? isLeftGood : !isLeftGood;
        final xPos = xPositions[j];

        add(ChoiceDoor(
          isGood: isGood,
          position: Vector2(xPos - 50, -120),
          size: Vector2(100, 120),
          speed: gameConfig.doorSpeed,
          gameConfig: gameConfig,
        ));
      }
    }
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (isGameOver || isPaused) return;
    // Doors handle their own taps
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
    lives--;
    if (_mounted) livesText.text = '❤️ $lives';
    if (lives <= 0) {
      triggerGameOver();
    } else {
      // Clear current doors
      children.whereType<ChoiceDoor>().forEach((d) => d.removeFromParent());
      Future.delayed(const Duration(seconds: 1), () {
        if (_mounted && !isGameOver) _spawnWave();
      });
    }
  }

  void increaseScore(int points) {
    score += points;
    if (_mounted) scoreText.text = 'الأبواب المفتوحة: $score';
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
      colors: [Color(0xFFA855F7), Color(0xFF9333EA)],
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

/// Choice Door with emotional visualization.
class ChoiceDoor extends PositionComponent with CollisionCallbacks, TapCallbacks {
  final bool isGood;
  final double speed;
  final EmotionMazeConfig gameConfig;
  double _scale = 1.0;
  double _pulseTimer = 0;
  bool _tapped = false;

  ChoiceDoor({
    required this.isGood,
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
    if (isGameOver || _tapped) return;

    _pulseTimer += dt;
    _scale = 1.0 + 0.05 * sin(_pulseTimer * 3);

    position.y += speed * dt;

    if (position.y > (findParent<EmotionMazeGame>()?.size.y ?? 1000) + 150) {
      if (!_tapped && isGood) {
        // Missed a good door
        final game = findParent<EmotionMazeGame>();
        game?.loseLife();
      }
      removeFromParent();
    }
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final box = Size(size.x * _scale, size.y * _scale);
    final center = Offset(size.x / 2, size.y / 2);

    // Door frame
    final doorRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: center, width: box.width * 0.85, height: box.height * 0.85),
      const Radius.circular(16),
    );

    // Door color based on emotion
    final doorPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: isGood
            ? [Color(0xFF10B981).withValues(alpha: 0.9), Color(0xFF059669)]
            : [Color(0xFFEF4444).withValues(alpha: 0.9), Color(0xFFDC2626)],
      ).createShader(doorRect.outerRect);
    canvas.drawRRect(doorRect, doorPaint);

    // Border
    final borderPaint = Paint()
      ..color = isGood ? Color(0xFF10B981) : Color(0xFFEF4444)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawRRect(doorRect, borderPaint);

    // Inner glow
    final glowPaint = Paint()
      ..color = (isGood ? Color(0xFF10B981) : Color(0xFFEF4444)).withValues(alpha: 0.2)
      ..style = PaintingStyle.fill;
    canvas.drawRRect(doorRect.deflate(4), glowPaint);

    // Emoji
    paintEmoji(canvas, isGood ? '😌' : '😡', box);
  }

  @override
  void onTapDown(TapDownEvent event) {
    if (isGameOver || _tapped) return;
    _tapped = true;

    final game = findParent<EmotionMazeGame>();
    if (game == null || game.isGameOver || game.isPaused) return;

    if (isGood) {
      game.increaseScore(gameConfig.scorePerDoor);
      // Remove all doors in this wave
      parent?.children.whereType<ChoiceDoor>().forEach((door) => door.removeFromParent());
      // Schedule next wave faster
      game.waveTimer = gameConfig.waveInterval * 0.5;
    } else {
      game.loseLife();
      // Remove all doors
      parent?.children.whereType<ChoiceDoor>().forEach((door) => door.removeFromParent());
    }
  }
}