// Dark mode — requested in production (#fb_e7402eaa, 15 Aug 2026).
//
// The obstacle was never the colours. `Dt.primary` and friends were
// `static const Color`, so all ~512 references resolved at compile time and
// nothing could move them. These tests pin the two properties that made the
// cheap fix possible and would silently undo it:
//
//   1. The tokens are getters over a swappable palette, not constants.
//   2. Both palettes define every colour, so no surface falls back to a light
//      value on a dark ground.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/theme/app_theme.dart';
import 'package:almorabbi/theme/design_tokens.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AppPalette.current = AppPalette.light;
  });

  tearDown(() => AppPalette.current = AppPalette.light);

  group('palette', () {
    test('tokens follow the live palette instead of a compile-time constant',
        () {
      final lightPrimary = Dt.primary;
      final lightSurface = AppTheme.surface;

      AppPalette.current = AppPalette.dark;

      expect(Dt.primary, isNot(lightPrimary),
          reason: 'Dt.primary is still frozen — dark mode cannot work');
      expect(AppTheme.surface, isNot(lightSurface));
      expect(Dt.primary, AppPalette.dark.primary);
    });

    test('gradients rebuild from the live palette too', () {
      final lightColors = Dt.primaryGradient.colors;
      AppPalette.current = AppPalette.dark;
      expect(Dt.primaryGradient.colors, isNot(lightColors));
    });

    test('the dark ground is actually dark and its ink is actually light', () {
      // Guards the direction of the swap: a copy-paste that left the light
      // values in place would still "have a dark theme" and be unreadable.
      expect(AppPalette.dark.background.computeLuminance(), lessThan(0.2));
      expect(AppPalette.dark.surface.computeLuminance(), lessThan(0.2));
      expect(AppPalette.dark.ink.computeLuminance(), greaterThan(0.6));
      expect(AppPalette.light.background.computeLuminance(), greaterThan(0.8));
      expect(AppPalette.light.ink.computeLuminance(), lessThan(0.2));
    });

    test('safety colours keep their meaning in both palettes', () {
      // The safety banner and emergency cards are the two places where colour
      // carries meaning rather than style. Warning must read yellow and danger
      // must read red on a dark ground too — only lightness may flip.
      for (final p in [AppPalette.light, AppPalette.dark]) {
        final warn = HSLColor.fromColor(p.warningFg).hue;
        final danger = HSLColor.fromColor(p.dangerFg).hue;
        expect(warn, inInclusiveRange(35, 65), reason: 'warning stopped being yellow');
        expect(danger < 20 || danger > 340, isTrue,
            reason: 'danger stopped being red');
      }
    });

    test('foreground/background pairs stay legible in dark', () {
      // Not a full WCAG pass, but it catches the failure that matters: a pair
      // where both ends landed on the same side of the lightness scale.
      final pairs = <String, List<Color>>{
        'ink on background': [AppPalette.dark.ink, AppPalette.dark.background],
        'ink on surface': [AppPalette.dark.ink, AppPalette.dark.surface],
        'warning': [AppPalette.dark.warningFg, AppPalette.dark.warningBg],
        'danger': [AppPalette.dark.dangerFg, AppPalette.dark.dangerBg],
      };
      pairs.forEach((name, c) {
        final diff = (c[0].computeLuminance() - c[1].computeLuminance()).abs();
        expect(diff, greaterThan(0.25), reason: '$name has too little contrast');
      });
    });
  });

  group('themes', () {
    // `AppTheme.light()/dark()` cannot be constructed here: `_build` calls
    // GoogleFonts.cairoTextTheme(), Cairo is not bundled as an asset, and the
    // loader fails asynchronously after the assertions have already passed —
    // so the test would report a font problem as a theming problem. No
    // existing test in this repo builds a ThemeData either.
    //
    // What actually needs pinning is that the two palettes are distinct and
    // each one is internally consistent, and that is assertable directly.
    test('the two palettes are distinct on every surface that matters', () {
      const l = AppPalette.light;
      const d = AppPalette.dark;
      for (final pair in <List<Color>>[
        [l.background, d.background],
        [l.surface, d.surface],
        [l.surfaceAlt, d.surfaceAlt],
        [l.ink, d.ink],
        [l.inkSoft, d.inkSoft],
        [l.textSecondary, d.textSecondary],
        [l.track, d.track],
        [l.primary, d.primary],
        [l.accent, d.accent],
      ]) {
        expect(pair[0], isNot(pair[1]),
            reason: 'a surface was copied unchanged into the dark palette');
      }
    });

    test('no colour inside _build reads the global palette', () {
      // `_build(p)` may be constructing a theme that is not the live one, so
      // every colour in it must come from `p`. Three did not — `fillColor`,
      // `linearTrackColor` and a label colour still read `Dt.*` — so
      // `AppTheme.dark()`, built while the light palette was current, baked
      // the LIGHT surface into its input fields. On a dark ground the
      // assistant's behaviour field rendered as a white pill.
      //
      // Asserted against the source rather than the built theme because
      // building a ThemeData needs GoogleFonts, which has no assets here.
      final src = File('lib/theme/app_theme.dart').readAsStringSync();
      final start = src.indexOf('static ThemeData _build(AppPalette p) {');
      expect(start, greaterThan(0), reason: '_build was renamed');
      final body = src.substring(start);
      final leaks = RegExp(
        r'\b(Dt|AppTheme)\.'
        r'(primary|primaryDeep|primaryDark|accent|accentDeep|background|'
        r'surface|surfaceAlt|ink|inkSoft|textPrimary|textSecondary|textMuted|'
        r'success|track|warningBg|warningFg|dangerBg|dangerFg)\b',
      ).allMatches(body).map((m) => m.group(0)).toSet();
      expect(leaks, isEmpty,
          reason: 'these read the live palette instead of the one being '
              'built: ${leaks.join(", ")}');
    });

    test('each palette reports its own brightness', () {
      expect(AppPalette.light.brightness, Brightness.light);
      expect(AppPalette.dark.brightness, Brightness.dark);
      expect(AppPalette.dark.isDark, isTrue);
      expect(AppPalette.light.isDark, isFalse);
    });
  });

  group('themeModeProvider', () {
    test('defaults to light — dark is opt-in until the audit is clean',
        () async {
      // 1.0.48+93 shipped defaulting to ThemeMode.system, which put every
      // dark-phone user into a theme that was only half converted: 161
      // surfaces across 49 files still hard-code a light colour, so the
      // Qur'an screen, the lesson sections and the assistant bubble stayed
      // light with light text on them.
      //
      // When `dart run tool/audit_light_surfaces.dart` exits 0, flip this
      // back to ThemeMode.system and change this expectation with it.
      final prefs = await SharedPreferences.getInstance();
      expect(ThemeModeNotifier(prefs).state, ThemeMode.light);
    });

    test('persists the choice across instances', () async {
      final prefs = await SharedPreferences.getInstance();
      await ThemeModeNotifier(prefs).set(ThemeMode.dark);
      expect(ThemeModeNotifier(prefs).state, ThemeMode.dark);
    });
  });
}
