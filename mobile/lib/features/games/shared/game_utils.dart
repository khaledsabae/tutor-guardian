/// Shared game utilities — P1.4 improved games.
///
/// Common utilities for all educational games: level management,
/// difficulty scaling, progress tracking, and visual themes.
library;

import 'dart:math';
import 'package:flame/components.dart';
import 'package:flutter/material.dart';

/// Base game configuration shared across all games.
class GameConfig {
  final int level;
  final int maxLevel;
  final Difficulty difficulty;
  final int lives;
  final double speedMultiplier;
  final double spawnRateMultiplier;
  final int scorePerItem;
  final int scoreToWin;

  const GameConfig({
    required this.level,
    required this.maxLevel,
    required this.difficulty,
    required this.lives,
    required this.speedMultiplier,
    required this.spawnRateMultiplier,
    required this.scorePerItem,
    required this.scoreToWin,
  });

  /// Create config for a specific level with progressive difficulty.
  factory GameConfig.forLevel(int level, {int maxLevel = 10}) {
    final difficulty = Difficulty.values[min((level - 1) ~/ 2, Difficulty.values.length - 1)];
    final speedMult = 1.0 + (level - 1) * 0.12;
    final spawnMult = 1.0 + (level - 1) * 0.08;
    final lives = max(1, 3 - (level - 1) ~/ 3);
    final scorePerItem = 10 + (level - 1) * 2;
    final scoreToWin = 100 + (level - 1) * 50;

    return GameConfig(
      level: level,
      maxLevel: maxLevel,
      difficulty: difficulty,
      lives: lives,
      speedMultiplier: speedMult,
      spawnRateMultiplier: spawnMult,
      scorePerItem: scorePerItem,
      scoreToWin: scoreToWin,
    );
  }

  static const defaultConfig = GameConfig(
    level: 1,
    maxLevel: 10,
    difficulty: Difficulty.easy,
    lives: 3,
    speedMultiplier: 1.0,
    spawnRateMultiplier: 1.0,
    scorePerItem: 10,
    scoreToWin: 100,
  );
}

/// Progressive difficulty tiers.
enum Difficulty {
  easy(0.8, 'سهل', Color(0xFF10B981)),
  normal(1.0, 'عادي', Color(0xFF3B82F6)),
  hard(1.25, 'صعب', Color(0xFFF59E0B)),
  expert(1.5, 'خبير', Color(0xFFEF4444));

  const Difficulty(this.multiplier, this.label, this.color);
  final double multiplier;
  final String label;
  final Color color;
}

/// Visual theme for each game.
class GameTheme {
  final Color backgroundColor;
  final Color accentColor;
  final Color textColor;
  final String name;
  final String backgroundAsset; // For future custom backgrounds

  const GameTheme({
    required this.backgroundColor,
    required this.accentColor,
    required this.textColor,
    required this.name,
    this.backgroundAsset = '',
  });

  static const dataDefender = GameTheme(
    backgroundColor: Color(0xFF0F172A),
    accentColor: Color(0xFF06B6D4),
    textColor: Colors.white,
    name: 'حارس البيانات',
  );

  static const healthyHero = GameTheme(
    backgroundColor: Color(0xFF38BDF8),
    accentColor: Color(0xFF22C55E),
    textColor: Colors.white,
    name: 'البطل الصحي',
  );

  static const emotionMaze = GameTheme(
    backgroundColor: Color(0xFF1E1B4B),
    accentColor: Color(0xFFA855F7),
    textColor: Colors.white,
    name: 'متاهة المشاعر',
  );

  static const treeOfDeeds = GameTheme(
    backgroundColor: Color(0xFFF59E0B),
    accentColor: Color(0xFF84CC16),
    textColor: Color(0xFF422006),
    name: 'شجرة الأخلاق',
  );
}

/// Game progress tracking.
class GameProgress {
  final int gameId;
  int highestLevel;
  int totalScore;
  int gamesPlayed;
  DateTime? lastPlayed;
  Map<int, int> levelBestScores; // level -> best score

  GameProgress({
    required this.gameId,
    this.highestLevel = 1,
    this.totalScore = 0,
    this.gamesPlayed = 0,
    this.lastPlayed,
    Map<int, int>? levelBestScores,
  }) : levelBestScores = levelBestScores ?? {};

  void recordGame(int level, int score, bool completed) {
    gamesPlayed++;
    totalScore += score;
    lastPlayed = DateTime.now();

    if (score > (levelBestScores[level] ?? 0)) {
      levelBestScores[level] = score;
    }

    if (completed && level >= highestLevel && highestLevel < 10) {
      highestLevel = min(level + 1, 10);
    }
  }

  Map<String, dynamic> toJson() => {
    'gameId': gameId,
    'highestLevel': highestLevel,
    'totalScore': totalScore,
    'gamesPlayed': gamesPlayed,
    'lastPlayed': lastPlayed?.toIso8601String(),
    'levelBestScores': levelBestScores.map((k, v) => MapEntry(k.toString(), v)),
  };

  factory GameProgress.fromJson(Map<String, dynamic> json) => GameProgress(
    gameId: json['gameId'] as int,
    highestLevel: json['highestLevel'] as int? ?? 1,
    totalScore: json['totalScore'] as int? ?? 0,
    gamesPlayed: json['gamesPlayed'] as int? ?? 0,
    lastPlayed: json['lastPlayed'] != null ? DateTime.parse(json['lastPlayed'] as String) : null,
    levelBestScores: (json['levelBestScores'] as Map<String, dynamic>?)?.map(
      (k, v) => MapEntry(int.parse(k), v as int),
    ) ?? {},
  );
}

/// Emoji sprite sizes for consistent rendering.
class EmojiSizes {
  static const small = Size(32, 32);
  static const medium = Size(48, 48);
  static const large = Size(64, 64);
  static const xlarge = Size(96, 96);

  static Size forLevel(int level) {
    if (level <= 2) return small;
    if (level <= 5) return medium;
    if (level <= 8) return large;
    return xlarge;
  }
}

/// Score popup animation component.
class ScorePopup extends PositionComponent {
  final String text;
  final Color color;
  double _timer = 0;

  ScorePopup({required this.text, required this.color, required super.position}) {
    anchor = Anchor.center;
  }

  @override
  void update(double dt) {
    super.update(dt);
    _timer += dt;
    position.y -= 50 * dt;
    if (_timer > 1.0) removeFromParent();
  }

  @override
  void render(Canvas canvas) {
    super.render(canvas);
    final opacity = max(0.0, 1.0 - (_timer / 1.0));
    final paint = TextPaint(style: TextStyle(
      color: color.withValues(alpha: opacity),
      fontSize: 24,
      fontWeight: FontWeight.bold,
      shadows: [
        Shadow(
          color: Colors.black.withValues(alpha: 0.5 * opacity),
          blurRadius: 4,
          offset: const Offset(0, 2),
        ),
      ],
    ));
    paint.render(canvas, text, Vector2(position.x, position.y));
  }
}

/// Particle explosion for celebrations.
class ParticleExplosion extends Component {
  final Vector2 position;
  final int particleCount;
  final Color color;
  double _timer = 0;
  final List<_Particle> _particles = [];

  ParticleExplosion({required this.position, this.particleCount = 20, this.color = const Color(0xFFFFD700)}) {
    final random = Random();
    for (int i = 0; i < particleCount; i++) {
      final angle = random.nextDouble() * 2 * pi;
      final speed = 200 + random.nextDouble() * 200;
      _particles.add(_Particle(
        position: Vector2.zero(),
        velocity: Vector2(cos(angle), sin(angle)) * speed,
        color: color,
        size: 6 + random.nextDouble() * 4,
      ));
    }
  }

  @override
  void update(double dt) {
    _timer += dt;
    if (_timer > 1.5) {
      removeFromParent();
      return;
    }
    for (final p in _particles) {
      p.position += p.velocity * dt;
      p.velocity.y += 500 * dt; // gravity
      p.opacity = max(0.0, 1.0 - _timer / 1.5);
    }
  }

  @override
  void render(Canvas canvas) {
    for (final p in _particles) {
      if (p.opacity > 0) {
        final paint = Paint()..color = color.withValues(alpha: p.opacity);
        canvas.drawCircle(p.position.toOffset(), p.size, paint);
      }
    }
  }
}

class _Particle {
  Vector2 position;
  final Vector2 velocity;
  final Color color;
  final double size;
  double opacity = 1.0;

  _Particle({required this.position, required this.velocity, required this.color, required this.size});
}

/// Level complete overlay with stars animation.
class LevelCompleteOverlay extends PositionComponent {
  final int level;
  final int score;
  final int starsEarned;
  final VoidCallback onNext;
  final VoidCallback onReplay;
  double _timer = 0;
  int _starsShown = 0;

  LevelCompleteOverlay({
    required super.position,
    required this.level,
    required this.score,
    required this.starsEarned,
    required this.onNext,
    required this.onReplay,
  }) {
    size = Vector2(300, 400);
    anchor = Anchor.center;
  }

  @override
  void update(double dt) {
    super.update(dt);
    _timer += dt;
    _starsShown = min(starsEarned, (_timer / 0.4).floor());
    if (_timer > 1.5 + starsEarned * 0.3) {
      // Auto-continue after showing all stars
    }
  }

  @override
  void render(Canvas canvas) {
    final rect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: position.toOffset(), width: size.x, height: size.y),
      const Radius.circular(24),
    );

    // Background
    final bgPaint = Paint()..color = const Color(0xFF1E293B);
    canvas.drawRRect(rect, bgPaint);

    // Border
    final borderPaint = Paint()
      ..color = const Color(0xFF10B981)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawRRect(rect, borderPaint);

    // Stars
    for (int i = 0; i < _starsShown; i++) {
      final starX = position.x - 60 + i * 60.0;
      final starY = position.y - 60;
      final opacity = min(1.0, max(0.0, (_timer - i * 0.4) * 2.5));
      _drawStar(canvas, Offset(starX, starY), 30, opacity);
    }

    final scoreText = TextPaint(style: const TextStyle(
      color: Colors.white,
      fontSize: 28,
      fontWeight: FontWeight.bold,
    ));
    scoreText.render(canvas, 'النتيجة: $score', Vector2(position.x - 80, position.y + 30));

    // Buttons (shown after stars)
    if (_timer > 1.5 + starsEarned * 0.3) {
      final replayPaint = Paint()..color = const Color(0xFF3B82F6);
      final nextPaint = Paint()..color = const Color(0xFF10B981);

      final replayRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(position.x, position.y + 80), width: 120, height: 48),
        const Radius.circular(12),
      );
      final nextRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(position.x, position.y + 140), width: 120, height: 48),
        const Radius.circular(12),
      );

      canvas.drawRRect(replayRect, replayPaint..style = PaintingStyle.fill);
      canvas.drawRRect(nextRect, nextPaint..style = PaintingStyle.fill);

      final btnText = TextPaint(style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold));
      btnText.render(canvas, 'إعادة', Vector2(position.x - 35, position.y + 72));
      btnText.render(canvas, 'التالي', Vector2(position.x - 28, position.y + 132));
    }
  }

  void _drawStar(Canvas canvas, Offset center, double radius, double opacity) {
    final paint = Paint()
      ..color = const Color(0xFFFFD700).withValues(alpha: opacity)
      ..style = PaintingStyle.fill;
    final path = Path();
    for (int i = 0; i < 5; i++) {
      final angle = -pi / 2 + i * 2 * pi / 5;
      final x = center.dx + radius * cos(angle);
      final y = center.dy + radius * sin(angle);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    path.close();
    canvas.drawPath(path, paint);
  }
}