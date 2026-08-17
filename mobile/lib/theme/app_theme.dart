import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_palette.dart';
import 'design_tokens.dart';

/// Theme + colour tokens for المربي الذكي.
///
/// Redesigned 2026-06 to a playful, vibrant (Duolingo-style) identity:
/// vivid teal + amber, warm cream background, chunky rounded components,
/// soft colored shadows instead of grey borders. Constant names are kept
/// stable — many screens reference `AppTheme.primary` etc. directly.
class AppTheme {
  // ── Brand palette ──────────────────────────────────────────────────────
  //
  // Getters over [AppPalette.current] — see app_palette.dart for why these
  // stopped being `const`. Names are unchanged; 424 references depend on them.
  static Color get primary => AppPalette.current.primary; // vivid teal
  static Color get primaryDark => AppPalette.current.primaryDeep;
  static Color get accent => AppPalette.current.accent; // amber

  // Surfaces
  static Color get background => AppPalette.current.background;
  static Color get surface => AppPalette.current.surface;
  static Color get surfaceAlt => AppPalette.current.surfaceAlt;

  // Text
  static Color get textPrimary => AppPalette.current.ink;
  static Color get textSecondary => AppPalette.current.textSecondary;
  static Color get textMuted => AppPalette.current.inkSoft;

  // Semantic / safety — these keep their MEANING in both palettes: the safety
  // banner and the emergency cards are where colour is load-bearing, not
  // decorative. Only lightness flips, so warning stays yellow and danger stays
  // red on a dark ground too.
  static Color get success => AppPalette.current.success;
  static Color get warningBg => AppPalette.current.warningBg;
  static Color get warningFg => AppPalette.current.warningFg;
  static Color get dangerBg => AppPalette.current.dangerBg;
  static Color get dangerFg => AppPalette.current.dangerFg;

  /// The light theme. Kept as its own entry point — `main.dart` and a number
  /// of tests call it by name.
  static ThemeData light() => _build(AppPalette.light);

  /// The dark theme, requested in production feedback (#fb_e7402eaa, 15 Aug
  /// 2026) and absent until now: `design_tokens.dart` said "light mode only".
  static ThemeData dark() => _build(AppPalette.dark);

  /// One builder, two palettes. Reading colours from [p] rather than from the
  /// `AppTheme.*` getters matters: this runs while building a `ThemeData` that
  /// may not be the one currently live, so the globals would answer for the
  /// wrong palette.
  static ThemeData _build(AppPalette p) {
    final primary = p.primary;
    final accent = p.accent;
    final surface = p.surface;
    final background = p.background;
    final textPrimary = p.ink;
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
      brightness: p.brightness,
      primary: primary,
      secondary: accent,
      surface: surface,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: p.brightness,
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
          side: BorderSide(color: primary, width: 2),
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
      progressIndicatorTheme: ProgressIndicatorThemeData(
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
          borderSide: BorderSide(color: primary, width: 2),
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
