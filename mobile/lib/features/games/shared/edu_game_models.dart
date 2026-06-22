/// Base educational game models and shared configuration.
///
/// This is the redesign layer for the four domain-specific mini-games. It
/// replaces the old Flame-based shared utilities with a lighter, purely
/// widget-driven architecture that is easier to make RTL-friendly and
/// responsive.
library;

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Difficulty tier for a level.
enum GameTier {
  easy('سهل', Color(0xFF10B981)),
  normal('عادي', Color(0xFF3B82F6)),
  hard('صعب', Color(0xFFF59E0B)),
  expert('خبير', Color(0xFFEF4444));

  final String label;
  final Color color;
  const GameTier(this.label, this.color);
}

/// Theme for one of the four educational games.
class EduGameTheme {
  final String id;
  final String name;
  final String heroEmoji;
  final String description;
  final Color backgroundColor;
  final Color surfaceColor;
  final Color accentColor;
  final Color textColor;

  const EduGameTheme({
    required this.id,
    required this.name,
    required this.heroEmoji,
    required this.description,
    required this.backgroundColor,
    required this.surfaceColor,
    required this.accentColor,
    required this.textColor,
  });

  /// Brand palette for the unified identity: warm teal + cream + white.
  /// Game shells now use these tokens so the four mini-games feel like
  /// one family instead of four unrelated apps.
  static const unifiedBackground = Color(0xFFFAF7F2);
  static const unifiedSurface = Color(0xFFFFFFFF);
  static const unifiedPrimary = Color(0xFF01696F);
  static const unifiedPrimarySoft = Color(0xFFE6F2F2);
  static const unifiedAccent = Color(0xFFF59E0B);
  static const unifiedText = Color(0xFF1E293B);

  // ── Per-game accent tints (kept only as subtle flavour) ───────────────────
  static const dataDefender = EduGameTheme(
    id: 'data_defender',
    name: 'حارس البيانات',
    heroEmoji: '🛡️',
    description: 'تعلّم كيف تحمي بياناتك من الفيروسات والروابط المشبوهة.',
    backgroundColor: unifiedBackground,
    surfaceColor: unifiedSurface,
    accentColor: Color(0xFF06B6D4),
    textColor: unifiedText,
  );

  static const healthyHero = EduGameTheme(
    id: 'healthy_hero',
    name: 'البطل الصحي',
    heroEmoji: '🩺',
    description: 'اختيارات ذكية للأكل والنوم والصحة اليومية.',
    backgroundColor: unifiedBackground,
    surfaceColor: unifiedSurface,
    accentColor: Color(0xFF22C55E),
    textColor: unifiedText,
  );

  static const emotionMaze = EduGameTheme(
    id: 'emotion_maze',
    name: 'متاهة المشاعر',
    heroEmoji: '🧠',
    description: 'تعلّم كيف تتعامل مع المشاعر وتحل الأزمات الأسرية بهدوء.',
    backgroundColor: unifiedBackground,
    surfaceColor: unifiedSurface,
    accentColor: Color(0xFFA855F7),
    textColor: unifiedText,
  );

  static const treeOfDeeds = EduGameTheme(
    id: 'tree_of_deeds',
    name: 'شجرة الأخلاق',
    heroEmoji: '🌳',
    description: 'قرارات تبني شخصية جميلة وتقربنا من الله.',
    backgroundColor: unifiedBackground,
    surfaceColor: unifiedSurface,
    accentColor: Color(0xFF84CC16),
    textColor: unifiedText,
  );
}

/// One multiple-choice question inside an educational game.
class EduQuestion {
  final String id;
  final String question;
  final String? context;
  final List<EduOption> options;
  final String? emoji;
  final String? category;

  const EduQuestion({
    required this.id,
    required this.question,
    required this.options,
    this.context,
    this.emoji,
    this.category,
  });
}

/// One answer option for an educational question.
class EduOption {
  final String text;
  final bool isCorrect;
  final String rationale;

  const EduOption({
    required this.text,
    required this.isCorrect,
    this.rationale = '',
  });
}

/// Result of a single play session.
class EduGameResult {
  final int level;
  final int score;
  final int correctAnswers;
  final int totalQuestions;
  final bool completed;
  final int stars;

  const EduGameResult({
    required this.level,
    required this.score,
    required this.correctAnswers,
    required this.totalQuestions,
    required this.completed,
    required this.stars,
  });
}

/// Per-level persisted progress.
class GameLevelProgress {
  final int bestScore;
  final int bestStars;
  final bool unlocked;
  final int attempts;

  const GameLevelProgress({
    this.bestScore = 0,
    this.bestStars = 0,
    this.unlocked = true,
    this.attempts = 0,
  });

  Map<String, dynamic> toJson() => {
        'bestScore': bestScore,
        'bestStars': bestStars,
        'unlocked': unlocked,
        'attempts': attempts,
      };

  factory GameLevelProgress.fromJson(Map<String, dynamic> json) =>
      GameLevelProgress(
        bestScore: (json['bestScore'] as num?)?.toInt() ?? 0,
        bestStars: (json['bestStars'] as num?)?.toInt() ?? 0,
        unlocked: json['unlocked'] as bool? ?? true,
        attempts: (json['attempts'] as num?)?.toInt() ?? 0,
      );
}

/// Persisted progress for one of the four games.
class EduGameProgress {
  final String gameId;
  final int totalScore;
  final int gamesPlayed;
  final Map<int, GameLevelProgress> levels;

  const EduGameProgress({
    required this.gameId,
    this.totalScore = 0,
    this.gamesPlayed = 0,
    this.levels = const {},
  });

  int get highestUnlockedLevel {
    int maxLevel = 1;
    for (final entry in levels.entries) {
      if (entry.value.unlocked && entry.key > maxLevel) {
        maxLevel = entry.key;
      }
    }
    // Always allow level 1; next after any completed level is also unlocked.
    for (int i = 1; i <= 10; i++) {
      final p = levels[i];
      if (p != null && (p.unlocked || p.bestStars > 0)) {
        maxLevel = maxLevel < i ? i : maxLevel;
      }
    }
    return maxLevel;
  }

  EduGameProgress recordGame(int level, EduGameResult result) {
    final nextLevels = Map<int, GameLevelProgress>.from(levels);
    final current = nextLevels[level] ?? const GameLevelProgress();
    nextLevels[level] = GameLevelProgress(
      bestScore: result.score > current.bestScore ? result.score : current.bestScore,
      bestStars: result.stars > current.bestStars ? result.stars : current.bestStars,
      unlocked: true,
      attempts: current.attempts + 1,
    );

    // Unlock the next level when completed.
    if (result.completed && level < 10) {
      final next = nextLevels[level + 1] ?? const GameLevelProgress();
      if (!next.unlocked) {
        nextLevels[level + 1] = GameLevelProgress(
          bestScore: next.bestScore,
          bestStars: next.bestStars,
          unlocked: true,
          attempts: next.attempts,
        );
      }
    }

    return EduGameProgress(
      gameId: gameId,
      totalScore: totalScore + result.score,
      gamesPlayed: gamesPlayed + 1,
      levels: nextLevels,
    );
  }

  Map<String, dynamic> toJson() => {
        'gameId': gameId,
        'totalScore': totalScore,
        'gamesPlayed': gamesPlayed,
        'levels': levels.map(
          (k, v) => MapEntry(k.toString(), v.toJson()),
        ),
      };

  factory EduGameProgress.fromJson(Map<String, dynamic> json) {
    final rawLevels = (json['levels'] as Map<String, dynamic>?) ?? {};
    return EduGameProgress(
      gameId: (json['gameId'] as String?) ?? '',
      totalScore: (json['totalScore'] as num?)?.toInt() ?? 0,
      gamesPlayed: (json['gamesPlayed'] as num?)?.toInt() ?? 0,
      levels: rawLevels.map(
        (k, v) => MapEntry(int.parse(k), GameLevelProgress.fromJson(v as Map<String, dynamic>)),
      ),
    );
  }
}

/// Simple, correct JSON persistence for game progress.
class EduGameProgressService {
  EduGameProgressService._();
  static final EduGameProgressService instance = EduGameProgressService._();

  String _key(String gameId) => 'edu_game_progress_$gameId';

  Future<EduGameProgress> load(String gameId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key(gameId));
    if (raw == null || raw.isEmpty) {
      return EduGameProgress(gameId: gameId);
    }
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return EduGameProgress.fromJson(map);
    } catch (_) {
      return EduGameProgress(gameId: gameId);
    }
  }

  Future<void> save(EduGameProgress progress) async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = jsonEncode(progress.toJson());
    await prefs.setString(_key(progress.gameId), encoded);
  }
}
