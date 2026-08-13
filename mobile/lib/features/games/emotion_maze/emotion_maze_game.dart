/// Redesigned Emotion Maze educational mini-game.
///
/// The 50 questions moved to `assets/content/games/emotion_maze.ar.json` on
/// 2026-08-13 so they can be translated without touching Dart.
/// [EduGameShell] loads them by [EduGameTheme.id]; this file is now the
/// game's identity and nothing else.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Emotion Maze game.
class EmotionMazeGame extends EduGameShell {
  const EmotionMazeGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'emotion_maze',
            name: 'متاهة المشاعر',
            heroEmoji: '🧠',
            description: 'تعلّم كيف تتعامل مع المشاعر وتحل الأزمات الأسرية بهدوء',
            backgroundColor: Color(0xFF2E1065),
            surfaceColor: Color(0xFF4C1D95),
            accentColor: Color(0xFFA855F7),
            textColor: Colors.white,
          ),
        );
}
