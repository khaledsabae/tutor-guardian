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

  bool get isDark => brightness == Brightness.dark;

  /// The identity as shipped since the 2026-06 redesign, unchanged.
  static const light = AppPalette(
    brightness: Brightness.light,
    primary: Color(0xFF0D9488), // vivid teal
    primaryDeep: Color(0xFF0F766E),
    accent: Color(0xFFF59E0B), // amber — gamification
    accentDeep: Color(0xFFD97706),
    background: Color(0xFFFAF7F2), // warm cream
    surface: Colors.white,
    surfaceAlt: Color(0xFFF1EDE5), // assistant bubble
    ink: Color(0xFF1E293B),
    inkSoft: Color(0xFF64748B),
    textSecondary: Color(0xFF475569),
    success: Color(0xFF22C55E),
    track: Color(0xFFEBE5DA),
    warningBg: Color(0xFFFFF3CD),
    warningFg: Color(0xFF856404),
    dangerBg: Color(0xFFF8D7DA),
    dangerFg: Color(0xFF721C24),
  );

  /// Not the light palette inverted.
  ///
  /// Teal and amber are lightened, because the shipped values are tuned to sit
  /// on cream and go muddy on a dark ground. The semantic pairs keep their
  /// *meaning* — warning stays yellow, danger stays red — since the safety
  /// banner and the emergency cards are the two places in this app where
  /// colour is load-bearing rather than decorative; only their lightness
  /// flips, so the foreground stays readable.
  static const dark = AppPalette(
    brightness: Brightness.dark,
    primary: Color(0xFF2DD4BF),
    primaryDeep: Color(0xFF14B8A6),
    accent: Color(0xFFFBBF24),
    accentDeep: Color(0xFFF59E0B),
    background: Color(0xFF14181D),
    surface: Color(0xFF1D232B),
    surfaceAlt: Color(0xFF272E38),
    ink: Color(0xFFE9EDF2),
    inkSoft: Color(0xFF9AA6B4),
    textSecondary: Color(0xFFB6C0CC),
    success: Color(0xFF4ADE80),
    track: Color(0xFF313A45),
    warningBg: Color(0xFF3A2F0B),
    warningFg: Color(0xFFFDE68A),
    dangerBg: Color(0xFF3B1418),
    dangerFg: Color(0xFFFCA5A5),
  );

  /// The palette every `Dt.*` / `AppTheme.*` colour getter reads.
  ///
  /// Mutable and global on purpose: hundreds of call sites — and several
  /// non-widget helpers such as `Dt.softShadow` — read colours without a
  /// `BuildContext` to hand. Kept in sync from `MaterialApp.builder`, so it is
  /// always the palette of the frame currently being built.
  static AppPalette current = light;
}
