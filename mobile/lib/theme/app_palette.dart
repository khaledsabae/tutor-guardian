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
    required this.onPrimary,
    required this.primaryDeep,
    required this.accent,
    required this.onAccent,
    required this.accentDeep,
    required this.background,
    required this.surface,
    required this.surfaceAlt,
    required this.ink,
    required this.inkSoft,
    required this.textSecondary,
    required this.success,
    required this.successText,
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

  /// Text/icons placed ON [primary] (filled buttons, selected chips).
  ///
  /// Both button themes used to hard-code `Colors.white`, which is fine on the
  /// light emerald (5.5:1) and unreadable on the luminous dark-mode one
  /// (2.5:1, WCAG AA needs 4.5:1). Pinned ≥ 4.5:1 by dark_mode_test.dart.
  final Color onPrimary;
  final Color primaryDeep;
  final Color accent;

  /// Text/icons placed ON [accent]. White on the gold was 3.2:1 in light and
  /// 1.7:1 in dark; a deep brown ink reads at 5.7:1 and 10.9:1.
  final Color onAccent;
  final Color accentDeep;
  final Color background;
  final Color surface;
  final Color surfaceAlt;
  final Color ink;
  final Color inkSoft;
  final Color textSecondary;
  final Color success;

  /// [success] is a fill/icon colour: as text on white it reads 2.5:1.
  /// Use this one for words (UX_UI_ROADMAP DS7).
  final Color successText;
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
    onPrimary: Colors.white, // 5.5:1
    primaryDeep: Color(0xFF044E46), // Deep Emerald
    accent: Color(0xFFD97706), // Warm Noble Gold
    onAccent: Color(0xFF1F1300), // 5.7:1
    accentDeep: Color(0xFFB45309), // Burnished Gold
    background: Color(0xFFFAF8F5), // Warm Noble Cream
    surface: Colors.white,
    surfaceAlt: Color(0xFFF3EFEA), // Warm Linen surface
    ink: Color(0xFF111827), // Deep Obsidian Ink
    inkSoft: Color(0xFF6B7280),
    textSecondary: Color(0xFF4B5563),
    success: Color(0xFF10B981), // Pure Emerald
    successText: Color(0xFF047857), // 5.5:1 on white
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
    onPrimary: Color(0xFF04211B), // 6.7:1 — white here was 2.5:1
    primaryDeep: Color(0xFF059669),
    accent: Color(0xFFFBBF24), // Radiant Gold
    onAccent: Color(0xFF1F1300), // 10.9:1 — white here was 1.7:1
    accentDeep: Color(0xFFD97706),
    background: Color(0xFF0A1210), // Nocturnal Obsidian-Emerald
    surface: Color(0xFF131F1C), // Deep Emerald Surface
    surfaceAlt: Color(0xFF1C2D29), // Elevated Emerald Card
    ink: Color(0xFFF9FAFB),
    inkSoft: Color(0xFF9CA3AF),
    textSecondary: Color(0xFFD1D5DB),
    success: Color(0xFF34D399),
    successText: Color(0xFF34D399), // 8.8:1 on the dark surface
    track: Color(0xFF20332E),
    warningBg: Color(0xFF3A2B09),
    warningFg: Color(0xFFFDE68A),
    dangerBg: Color(0xFF3B1215),
    dangerFg: Color(0xFFFCA5A5),
    tipGradient: [Color(0xFF3B2E10), Color(0xFF4D3C14)],
    tipInk: Color(0xFFFDE68A),
  );

  /// Blend two palettes — what `AppColors.lerp` hands `AnimatedTheme`, so a
  /// light/dark switch fades these colours instead of snapping them.
  static AppPalette lerp(AppPalette a, AppPalette b, double t) {
    Color c(Color x, Color y) => Color.lerp(x, y, t)!;
    return AppPalette(
      brightness: t < .5 ? a.brightness : b.brightness,
      primary: c(a.primary, b.primary),
      onPrimary: c(a.onPrimary, b.onPrimary),
      primaryDeep: c(a.primaryDeep, b.primaryDeep),
      accent: c(a.accent, b.accent),
      onAccent: c(a.onAccent, b.onAccent),
      accentDeep: c(a.accentDeep, b.accentDeep),
      background: c(a.background, b.background),
      surface: c(a.surface, b.surface),
      surfaceAlt: c(a.surfaceAlt, b.surfaceAlt),
      ink: c(a.ink, b.ink),
      inkSoft: c(a.inkSoft, b.inkSoft),
      textSecondary: c(a.textSecondary, b.textSecondary),
      success: c(a.success, b.success),
      successText: c(a.successText, b.successText),
      track: c(a.track, b.track),
      warningBg: c(a.warningBg, b.warningBg),
      warningFg: c(a.warningFg, b.warningFg),
      dangerBg: c(a.dangerBg, b.dangerBg),
      dangerFg: c(a.dangerFg, b.dangerFg),
      tipGradient: [
        for (var i = 0; i < a.tipGradient.length; i++)
          c(a.tipGradient[i], b.tipGradient[i]),
      ],
      tipInk: c(a.tipInk, b.tipInk),
    );
  }

  /// The palette every `Dt.*` / `AppTheme.*` colour getter reads.
  ///
  /// Mutable and global on purpose: hundreds of call sites — and several
  /// non-widget helpers such as `Dt.softShadow` — read colours without a
  /// `BuildContext` to hand. Kept in sync from `MaterialApp.builder` through
  /// [sync]. New code should read `context.colors` (theme/app_colors.dart)
  /// instead, which also rebuilds with the theme on its own.
  static AppPalette current = light;

  static bool _synced = false;

  /// Pin [current] to [brightness] (UX_UI_ROADMAP DS5).
  ///
  /// A widget that reads `Dt.surface` without depending on `Theme` is not
  /// rebuilt when the user switches light/dark, so it kept painting the old
  /// palette until something else happened to rebuild it — dark cards on a
  /// light screen, or the reverse. When the palette really changes, every
  /// element is marked for one rebuild after the frame, the way hot reload
  /// does it: navigation, scroll positions and text fields keep their state.
  static void sync(Brightness brightness) {
    final next = brightness == Brightness.dark ? dark : light;
    if (identical(next, current)) {
      _synced = true;
      return;
    }
    current = next;
    // The first frame builds everything after this call anyway.
    if (!_synced) {
      _synced = true;
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) => rebuildTree());
  }

  /// Mark every element in the app for one rebuild.
  @visibleForTesting
  static void rebuildTree() {
    void visit(Element element) {
      element.markNeedsBuild();
      element.visitChildren(visit);
    }

    WidgetsBinding.instance.rootElement?.visitChildren(visit);
  }
}
