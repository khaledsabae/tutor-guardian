/// The palette as a [ThemeExtension] (UX_UI_ROADMAP DS5).
///
/// `context.colors` is the way new and migrated widgets read colours. It goes
/// through `Theme.of`, so the widget depends on the theme and rebuilds when it
/// changes, and `AnimatedTheme` fades between palettes through [lerp] instead
/// of snapping. The `Dt.*` / `AppTheme.*` getters stay as a compatibility
/// shim over `AppPalette.current` for the ~500 existing call sites.
library;

import 'package:flutter/material.dart';

import 'app_palette.dart';

@immutable
class AppColors extends ThemeExtension<AppColors> {
  const AppColors(this.palette);

  final AppPalette palette;

  @override
  AppColors copyWith({AppPalette? palette}) => AppColors(palette ?? this.palette);

  @override
  AppColors lerp(covariant ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    return AppColors(AppPalette.lerp(palette, other.palette, t));
  }
}

extension AppColorsContext on BuildContext {
  /// The live palette for this part of the tree.
  AppPalette get colors =>
      Theme.of(this).extension<AppColors>()?.palette ?? AppPalette.current;

  /// The violet used for reflection and coin copy, as text on the surface.
  /// The deep violet is 7:1 on the light surface and 2.4:1 on the dark one,
  /// so dark mode takes the light lavender (9:1) instead.
  Color get violetText =>
      colors.isDark ? const Color(0xFFC4B5FD) : const Color(0xFF6D28D9);
}
