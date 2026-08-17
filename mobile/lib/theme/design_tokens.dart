import 'package:flutter/material.dart';

import 'app_palette.dart';

/// Design tokens for the playful (Duolingo-style) redesign.
///
/// Everything here is code-only: gradients, radii, shadows and motion
/// constants. No asset files. Colours come from [AppPalette.current].
abstract final class Dt {
  // ── Core palette ───────────────────────────────────────────────────────
  //
  // Getters, not constants. These were `static const Color`, which meant every
  // one of ~512 references resolved at compile time — the single reason dark
  // mode was estimated at a week. The spelling at each call site is unchanged;
  // only the definitions moved behind [AppPalette.current].
  static Color get primary => AppPalette.current.primary;
  static Color get primaryDeep => AppPalette.current.primaryDeep;
  static Color get accent => AppPalette.current.accent;
  static Color get accentDeep => AppPalette.current.accentDeep;
  static Color get background => AppPalette.current.background;
  static Color get surface => AppPalette.current.surface;
  static Color get ink => AppPalette.current.ink;
  static Color get inkSoft => AppPalette.current.inkSoft;
  static Color get success => AppPalette.current.success;
  static Color get track => AppPalette.current.track;

  static LinearGradient get primaryGradient => LinearGradient(
        begin: AlignmentDirectional.topStart,
        end: AlignmentDirectional.bottomEnd,
        colors: [primary, primaryDeep],
      );

  static LinearGradient get accentGradient => LinearGradient(
        begin: AlignmentDirectional.topStart,
        end: AlignmentDirectional.bottomEnd,
        colors: [accent, accentDeep],
      );

  // ── Radii ──────────────────────────────────────────────────────────────
  static const double rCard = 24;
  static const double rButton = 18;
  static const double rChip = 999; // pill
  static const double rSheet = 28;

  // ── Shadows ────────────────────────────────────────────────────────────
  /// Soft colored shadow — replaces grey borders on cards.
  static List<BoxShadow> softShadow(Color color, {double alpha = .25}) => [
        BoxShadow(
          color: color.withValues(alpha: alpha),
          blurRadius: 16,
          offset: const Offset(0, 6),
        ),
      ];

  /// Neutral shadow for white cards on the cream background.
  static List<BoxShadow> get cardShadow => [
        BoxShadow(
          color: const Color(0xFF8B7E66).withValues(alpha: .12),
          blurRadius: 14,
          offset: const Offset(0, 4),
        ),
      ];

  // ── Motion ─────────────────────────────────────────────────────────────
  static const Duration fast = Duration(milliseconds: 200);
  static const Duration base = Duration(milliseconds: 350);
  static const Duration slow = Duration(milliseconds: 600);
  static const Duration stagger = Duration(milliseconds: 60);

  // ── Spacing ──────────────────────────────────────────────────────────────
  static const double pad = 16;

  /// Items beyond this index appear without an entrance animation —
  /// they're off-screen anyway and animating them wastes frames.
  static const int maxStaggeredItems = 10;
}

/// Per-domain visual identity: gradient pair + emoji mascot.
class DomainStyle {
  final Color base;
  final Color dark;
  final String emoji;

  const DomainStyle(this.base, this.dark, this.emoji);

  LinearGradient get gradient => LinearGradient(
        begin: AlignmentDirectional.topStart,
        end: AlignmentDirectional.bottomEnd,
        colors: [base, dark],
      );

  /// Very light tint of the domain color for section backgrounds.
  Color get tint => Color.lerp(base, AppPalette.current.surface, .9)!;
}

const _domainStyles = <String, DomainStyle>{
  'islamic_parenting':
      DomainStyle(Color(0xFF10B981), Color(0xFF059669), '🕌'),
  'aqeedah':
      DomainStyle(Color(0xFF01696F), Color(0xFF014F55), '☪️'),
  'development': DomainStyle(Color(0xFF8B5CF6), Color(0xFF6D28D9), '🌱'),
  'medical': DomainStyle(Color(0xFFFBBF24), Color(0xFFD97706), '🧩'),
  'cyber': DomainStyle(Color(0xFF3B82F6), Color(0xFF1D4ED8), '🛡️'),
};

// Not const: it reads brand colours, which now follow the live palette.
DomainStyle get _fallbackDomainStyle =>
    DomainStyle(Dt.primary, Dt.primaryDeep, '📚');

DomainStyle styleFor(String? domain) =>
    _domainStyles[domain] ?? _fallbackDomainStyle;
