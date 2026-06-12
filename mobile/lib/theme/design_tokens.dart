import 'package:flutter/material.dart';

/// Design tokens for the playful (Duolingo-style) redesign.
///
/// Everything here is code-only: gradients, radii, shadows and motion
/// constants. No asset files. Light mode only for now.
abstract final class Dt {
  // ── Core palette ───────────────────────────────────────────────────────
  static const Color primary = Color(0xFF0D9488); // vivid teal
  static const Color primaryDeep = Color(0xFF0F766E);
  static const Color accent = Color(0xFFF59E0B); // amber — gamification
  static const Color accentDeep = Color(0xFFD97706);
  static const Color background = Color(0xFFFAF7F2); // warm cream
  static const Color surface = Colors.white;
  static const Color ink = Color(0xFF1E293B);
  static const Color inkSoft = Color(0xFF64748B);
  static const Color success = Color(0xFF22C55E);
  static const Color track = Color(0xFFEBE5DA); // progress bar track

  static const LinearGradient primaryGradient = LinearGradient(
    begin: AlignmentDirectional.topStart,
    end: AlignmentDirectional.bottomEnd,
    colors: [primary, primaryDeep],
  );

  static const LinearGradient accentGradient = LinearGradient(
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
  Color get tint => Color.lerp(base, Colors.white, .9)!;
}

const _domainStyles = <String, DomainStyle>{
  'islamic_parenting':
      DomainStyle(Color(0xFF10B981), Color(0xFF059669), '🕌'),
  'development': DomainStyle(Color(0xFF8B5CF6), Color(0xFF6D28D9), '🌱'),
  'medical': DomainStyle(Color(0xFFFB7185), Color(0xFFE11D48), '🩺'),
  'cyber': DomainStyle(Color(0xFF3B82F6), Color(0xFF1D4ED8), '🛡️'),
};

const _fallbackDomainStyle =
    DomainStyle(Dt.primary, Dt.primaryDeep, '📚');

DomainStyle styleFor(String? domain) =>
    _domainStyles[domain] ?? _fallbackDomainStyle;
