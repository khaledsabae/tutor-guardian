/// Redesigned Tree of Deeds educational mini-game.
///
/// The 50 questions moved to `assets/content/games/tree_of_deeds.ar.json` on
/// 2026-08-13 so they can be translated without touching Dart.
/// [EduGameShell] loads them by [EduGameTheme.id]; this file is now the
/// game's identity and nothing else.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Tree of Deeds game.
class TreeOfDeedsGame extends EduGameShell {
  const TreeOfDeedsGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'tree_of_deeds',
            name: 'شجرة الأخلاق',
            heroEmoji: '🌳',
            description: 'قرارات تبني شخصية جميلة وتقربنا من الله',
            backgroundColor: Color(0xFF422006),
            surfaceColor: Color(0xFF713F12),
            accentColor: Color(0xFF84CC16),
            textColor: Colors.white,
          ),
        );
}
