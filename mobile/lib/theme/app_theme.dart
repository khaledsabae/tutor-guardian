import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'design_tokens.dart';

/// Theme + colour tokens for المربي الذكي.
///
/// Redesigned 2026-06 to a playful, vibrant (Duolingo-style) identity:
/// vivid teal + amber, warm cream background, chunky rounded components,
/// soft colored shadows instead of grey borders. Constant names are kept
/// stable — many screens reference `AppTheme.primary` etc. directly.
class AppTheme {
  // ── Brand palette ──────────────────────────────────────────────────────
  static const Color primary = Dt.primary; // vivid teal
  static const Color primaryDark = Dt.primaryDeep;
  static const Color accent = Dt.accent; // amber — gamification accent

  // Surfaces
  static const Color background = Dt.background; // warm cream
  static const Color surface = Dt.surface;
  static const Color surfaceAlt = Color(0xFFF1EDE5); // assistant bubble

  // Text
  static const Color textPrimary = Dt.ink;
  static const Color textSecondary = Color(0xFF475569);
  static const Color textMuted = Dt.inkSoft;

  // Semantic / safety — must stay semantically yellow/red: the safety
  // banner and emergency cards depend on these meanings.
  static const Color success = Dt.success;
  static const Color warningBg = Color(0xFFFFF3CD);
  static const Color warningFg = Color(0xFF856404);
  static const Color dangerBg = Color(0xFFF8D7DA);
  static const Color dangerFg = Color(0xFF721C24);

  /// Build the Material 3 light theme with Arabic-friendly typography.
  static ThemeData light() {
    // Cairo is a modern, well-hinted Arabic-Latin pair that ships via
    // google_fonts; falls back gracefully when offline.
    final base = GoogleFonts.cairoTextTheme().apply(
      bodyColor: textPrimary,
      displayColor: textPrimary,
    );
    // Heavier headings give the playful "chunky" feel without new fonts.
    final textTheme = base.copyWith(
      headlineMedium:
          base.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
      headlineSmall:
          base.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
      titleLarge: base.titleLarge?.copyWith(fontWeight: FontWeight.w800),
      titleMedium: base.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      labelLarge: base.labelLarge?.copyWith(fontWeight: FontWeight.w700),
    );

    final colorScheme = ColorScheme.fromSeed(
      seedColor: primary,
      brightness: Brightness.light,
      primary: primary,
      secondary: accent,
      surface: surface,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: background,
      textTheme: textTheme,
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          // Y-axis slide is RTL-safe (no horizontal direction to mirror).
          TargetPlatform.android: _FadeSlideUpTransitionsBuilder(),
          TargetPlatform.iOS: _FadeSlideUpTransitionsBuilder(),
        },
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: background,
        foregroundColor: textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: GoogleFonts.cairo(
          fontSize: 22,
          fontWeight: FontWeight.w800,
          color: textPrimary,
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: surface,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Dt.rCard),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          elevation: 0,
          minimumSize: const Size(0, 54),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(Dt.rButton),
          ),
          textStyle:
              GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.w800),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          minimumSize: const Size(0, 54),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(Dt.rButton),
          ),
          textStyle:
              GoogleFonts.cairo(fontSize: 16, fontWeight: FontWeight.w800),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          minimumSize: const Size(0, 50),
          side: const BorderSide(color: primary, width: 2),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(Dt.rButton),
          ),
          textStyle: GoogleFonts.cairo(fontWeight: FontWeight.w700),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: surface,
        height: 72,
        indicatorColor: primary.withValues(alpha: .14),
        surfaceTintColor: Colors.transparent,
        labelTextStyle: WidgetStatePropertyAll(
          GoogleFonts.cairo(fontSize: 12, fontWeight: FontWeight.w700),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: primary,
        linearTrackColor: Dt.track,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: textPrimary,
        contentTextStyle:
            GoogleFonts.cairo(color: Colors.white, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFFF1EDE5),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Dt.rButton),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Dt.rButton),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Dt.rButton),
          borderSide: const BorderSide(color: primary, width: 2),
        ),
      ),
    );
  }
}

/// Fade + slight upward slide for every pushed route. Y-axis only so the
/// motion reads identically in RTL and LTR.
class _FadeSlideUpTransitionsBuilder extends PageTransitionsBuilder {
  const _FadeSlideUpTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    final curved =
        CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
    return FadeTransition(
      opacity: curved,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0, .04),
          end: Offset.zero,
        ).animate(curved),
        child: child,
      ),
    );
  }
}
