/// The two palettes, and which one is live right now.
///
/// «لدي اقتراح و اتمنى ان تطبقوه ألا و هو الوضع الداكن. فهو اريح للعين» —
/// #fb_e7402eaa, 15 Aug 2026.
///
/// The obstacle was never the colours; it was that `Dt.primary` and friends
/// were `static const Color`, so all ~512 references resolved at compile time
/// and no amount of theming could move them. Rewriting 512 call sites would
/// have been the week of work the plan estimated.
///
/// Instead the *definitions* become getters over a swappable palette, and the
/// call sites keep their exact spelling. Only the 47 sites that used a token
/// inside a `const` constructor had to change, because a getter is not a
/// compile-time constant.
///
/// [current] is set from `MaterialApp.builder` on every rebuild, which is the
/// same trick `AppL10n.current` already uses in this codebase for the same
/// reason: code outside the widget tree needs the resolved value, and the
/// builder is where the resolved value first exists.
library;

import 'package:flutter/material.dart';

@immutable
class AppPalette {
  const AppPalette({
    required this.brightness,
    required this.primary,
    required this.primaryDeep,
    required this.accent,
    required this.accentDeep,
    required this.background,
    required this.surface,
    required this.surfaceAlt,
    required this.ink,
    required this.inkSoft,
    required this.textSecondary,
    required this.success,
    required this.track,
    required this.warningBg,
    required this.warningFg,
    required this.dangerBg,
    required this.dangerFg,
    required this.tipGradient,
    required this.tipInk,
  });

  final Brightness brightness;
  final Color primary;
  final Color primaryDeep;
  final Color accent;
  final Color accentDeep;
  final Color background;
  final Color surface;
  final Color surfaceAlt;
  final Color ink;
  final Color inkSoft;
  final Color textSecondary;
  final Color success;
  final Color track;
  final Color warningBg;
  final Color warningFg;
  final Color dangerBg;
  final Color dangerFg;

  /// The amber "tip" card — the daily tip and the coach tip.
  ///
  /// Both mixed this by hand, identically and separately, outside the tokens.
  /// That is why both stayed fully cream when everything around them went
  /// dark: there was no token to change. One definition now, read by both.
  final List<Color> tipGradient;
  final Color tipInk;

  bool get isDark => brightness == Brightness.dark;

  /// The identity: Modern Islamic Luxury (Royal Emerald & Warm Gold).
  static const light = AppPalette(
    brightness: Brightness.light,
    primary: Color(0xFF0F766E), // Royal Islamic Emerald
    primaryDeep: Color(0xFF044E46), // Deep Emerald
    accent: Color(0xFFD97706), // Warm Noble Gold
    accentDeep: Color(0xFFB45309), // Burnished Gold
    background: Color(0xFFFAF8F5), // Warm Noble Cream
    surface: Colors.white,
    surfaceAlt: Color(0xFFF3EFEA), // Warm Linen surface
    ink: Color(0xFF111827), // Deep Obsidian Ink
    inkSoft: Color(0xFF6B7280),
    textSecondary: Color(0xFF4B5563),
    success: Color(0xFF10B981), // Pure Emerald
    track: Color(0xFFE8E2D7),
    warningBg: Color(0xFFFFF3CD),
    warningFg: Color(0xFF856404),
    dangerBg: Color(0xFFFEF2F2),
    dangerFg: Color(0xFFB91C1C),
    tipGradient: [Color(0xFFFEF3C7), Color(0xFFFDE68A)],
    tipInk: Color(0xFF92400E),
  );

  /// Modern Islamic Luxury — Dark (Deep Obsidian Emerald & Radiant Gold).
  static const dark = AppPalette(
    brightness: Brightness.dark,
    primary: Color(0xFF10B981), // Luminous Emerald
    primaryDeep: Color(0xFF059669),
    accent: Color(0xFFFBBF24), // Radiant Gold
    accentDeep: Color(0xFFD97706),
    background: Color(0xFF0A1210), // Nocturnal Obsidian-Emerald
    surface: Color(0xFF131F1C), // Deep Emerald Surface
    surfaceAlt: Color(0xFF1C2D29), // Elevated Emerald Card
    ink: Color(0xFFF9FAFB),
    inkSoft: Color(0xFF9CA3AF),
    textSecondary: Color(0xFFD1D5DB),
    success: Color(0xFF34D399),
    track: Color(0xFF20332E),
    warningBg: Color(0xFF3A2B09),
    warningFg: Color(0xFFFDE68A),
    dangerBg: Color(0xFF3B1215),
    dangerFg: Color(0xFFFCA5A5),
    tipGradient: [Color(0xFF3B2E10), Color(0xFF4D3C14)],
    tipInk: Color(0xFFFDE68A),
  );

  /// The palette every `Dt.*` / `AppTheme.*` colour getter reads.
  ///
  /// Mutable and global on purpose: hundreds of call sites — and several
  /// non-widget helpers such as `Dt.softShadow` — read colours without a
  /// `BuildContext` to hand. Kept in sync from `MaterialApp.builder`, so it is
  /// always the palette of the frame currently being built.
  static AppPalette current = light;
}
