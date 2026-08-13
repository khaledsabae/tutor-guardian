/// Redesigned Data Defender educational mini-game.
///
/// The 50 questions moved to `assets/content/games/data_defender.ar.json` on
/// 2026-08-13 so they can be translated without touching Dart.
/// [EduGameShell] loads them by [EduGameTheme.id]; this file is now the
/// game's identity and nothing else.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Data Defender game.
class DataDefenderGame extends EduGameShell {
  const DataDefenderGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'data_defender',
            name: 'حارس البيانات',
            heroEmoji: '🛡️',
            description: 'تعلّم أمانك وخصوصيتك العائلية من الفيروسات والاحتيال',
            backgroundColor: Color(0xFF0B1120),
            surfaceColor: Color(0xFF1E293B),
            accentColor: Color(0xFF06B6D4),
            textColor: Colors.white,
          ),
        );
}
