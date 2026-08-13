/// Smart Habits educational mini-game (formerly "Healthy Hero").
///
/// Reframed to teach daily habits, responsibility, social/emotional and life
/// skills — NO medical/first-aid/clinical content — so the app stays squarely
/// "Islamic education" and does not present undeclared health features.
///
/// The 50 questions moved to `assets/content/games/healthy_hero.ar.json` on
/// 2026-08-13 so they can be translated without touching Dart.
/// [EduGameShell] loads them by [EduGameTheme.id]; this file is now the
/// game's identity and nothing else.
library;

import 'package:flutter/material.dart';

import '../shared/edu_game_models.dart';
import '../shared/edu_game_shell.dart';

/// Entry point for the Smart Habits game.
class HealthyHeroGame extends EduGameShell {
  const HealthyHeroGame({super.key})
      : super(
          theme: const EduGameTheme(
            id: 'healthy_hero',
            name: 'بطل العادات الذكية',
            heroEmoji: '🌟',
            description: 'عادات ومهارات حياتية ذكية لطفلك',
            backgroundColor: Color(0xFF0F3D4A),
            surfaceColor: Color(0xFF164E63),
            accentColor: Color(0xFF22C55E),
            textColor: Colors.white,
          ),
        );
}
