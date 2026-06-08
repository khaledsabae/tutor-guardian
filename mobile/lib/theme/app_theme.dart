import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Theme + colour tokens for المربي الذكي.
///
/// Palette is derived from the existing web frontend (`frontend/index.html`,
/// `frontend/manifest.json`): a teal primary, neutral greys, safety colours
/// (yellow for "review with a specialist", red for emergency).
class AppTheme {
  // ── Brand palette (tuned to the existing web client) ──────────────────────
  static const Color primary = Color(0xFF1A5F7A); // deep teal
  static const Color primaryDark = Color(0xFF0E3F52);
  static const Color accent = Color(0xFF01696F); // manifest.json theme_color

  // Surfaces
  static const Color background = Color(0xFFF7F6F2); // manifest.json bg
  static const Color surface = Colors.white;
  static const Color surfaceAlt = Color(0xFFF1F3F5); // assistant bubble

  // Text
  static const Color textPrimary = Color(0xFF1A1A1A);
  static const Color textSecondary = Color(0xFF555555);
  static const Color textMuted = Color(0xFF8A8A8A);

  // Semantic / safety
  static const Color success = Color(0xFF28A745);
  static const Color warningBg = Color(0xFFFFF3CD);
  static const Color warningFg = Color(0xFF856404);
  static const Color dangerBg = Color(0xFFF8D7DA);
  static const Color dangerFg = Color(0xFF721C24);

  /// Build the Material 3 light theme with Arabic-friendly typography.
  static ThemeData light() {
    // Cairo is a modern, well-hinted Arabic-Latin pair that ships via
    // google_fonts; falls back gracefully when offline.
    final textTheme = GoogleFonts.cairoTextTheme().apply(
      bodyColor: textPrimary,
      displayColor: textPrimary,
    );

    final colorScheme = ColorScheme.fromSeed(
      seedColor: primary,
      brightness: Brightness.light,
      primary: primary,
      surface: surface,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: background,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: primary,
        foregroundColor: Colors.white,
        centerTitle: true,
        titleTextStyle: GoogleFonts.cairo(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: GoogleFonts.cairo(fontWeight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 12,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFD0D5DD)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFD0D5DD)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: primary, width: 1.5),
        ),
      ),
    );
  }
}
