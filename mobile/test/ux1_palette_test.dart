// DS5: the palette as a ThemeExtension, and a light/dark switch that reaches
// every widget — including the ones that read Dt.* without depending on Theme.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/theme/app_theme.dart';
import 'package:almorabbi/theme/design_tokens.dart';

/// Paints Dt.surface and never asks for the theme: exactly the kind of widget
/// that used to keep the old palette after a switch.
class _LegacySwatch extends StatelessWidget {
  const _LegacySwatch();

  @override
  Widget build(BuildContext context) =>
      ColoredBox(key: const Key('legacy'), color: Dt.surface, child: const SizedBox(width: 10, height: 10));
}

class _ContextSwatch extends StatelessWidget {
  const _ContextSwatch();

  @override
  Widget build(BuildContext context) =>
      ColoredBox(key: const Key('ctx'), color: context.colors.surface, child: const SizedBox(width: 10, height: 10));
}

Color _colorOf(WidgetTester t, String key) =>
    t.widget<ColoredBox>(find.byKey(Key(key))).color;

Widget _app(ValueNotifier<ThemeMode> mode) => ValueListenableBuilder<ThemeMode>(
      valueListenable: mode,
      builder: (_, m, _) => MaterialApp(
        theme: AppTheme.light(),
        darkTheme: AppTheme.dark(),
        themeMode: m,
        // The same call main.dart's builder makes.
        builder: (context, child) {
          AppPalette.sync(Theme.of(context).brightness);
          return child!;
        },
        home: const Column(children: [_LegacySwatch(), _ContextSwatch()]),
      ),
    );

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 6; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
}

void main() {
  setUp(() => AppPalette.current = AppPalette.light);

  testWidgets('switching to dark repaints a widget with no Theme dependency',
      (t) async {
    final mode = ValueNotifier(ThemeMode.light);
    await t.pumpWidget(_app(mode));
    expect(_colorOf(t, 'legacy'), AppPalette.light.surface);

    mode.value = ThemeMode.dark;
    await _settle(t);
    expect(_colorOf(t, 'legacy'), AppPalette.dark.surface);
    expect(_colorOf(t, 'ctx'), AppPalette.dark.surface);

    mode.value = ThemeMode.light;
    await _settle(t);
    expect(_colorOf(t, 'legacy'), AppPalette.light.surface);
    expect(_colorOf(t, 'ctx'), AppPalette.light.surface);
  });

  testWidgets('context.colors follows the theme it is under', (t) async {
    late AppPalette seen;
    Widget probe(ThemeData theme) => MaterialApp(
          theme: theme,
          home: Builder(builder: (c) {
            seen = c.colors;
            return const SizedBox();
          }),
        );
    await t.pumpWidget(probe(AppTheme.dark()));
    expect(seen.isDark, isTrue);
    expect(seen.surface, AppPalette.dark.surface);
    await t.pumpWidget(probe(AppTheme.light()));
    await t.pump(const Duration(milliseconds: 400));
    expect(seen.isDark, isFalse);
  });

  test('AppColors.lerp blends every colour between the two palettes', () {
    const a = AppColors(AppPalette.light);
    const b = AppColors(AppPalette.dark);
    expect(a.lerp(b, 0).palette.surface, AppPalette.light.surface);
    expect(a.lerp(b, 1).palette.surface, AppPalette.dark.surface);
    final mid = a.lerp(b, .5).palette;
    expect(mid.surface, Color.lerp(AppPalette.light.surface, AppPalette.dark.surface, .5));
    expect(mid.tipGradient, hasLength(AppPalette.light.tipGradient.length));
  });

  _violetContrast();

  test('both themes carry the palette extension', () {
    expect(AppTheme.light().extension<AppColors>()!.palette, same(AppPalette.light));
    expect(AppTheme.dark().extension<AppColors>()!.palette, same(AppPalette.dark));
  });
}

double _contrast(Color a, Color b) {
  final la = a.computeLuminance(), lb = b.computeLuminance();
  final hi = la > lb ? la : lb, lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}


// Words that used to be hard-coded violet on the surface (lesson reflections,
// coin rows) read in both modes.
void _violetContrast() {
  testWidgets('violet copy reads on the surface in both themes', (t) async {
    for (final theme in [AppTheme.light(), AppTheme.dark()]) {
      late Color text, surface;
      await t.pumpWidget(MaterialApp(
        theme: theme,
        home: Builder(builder: (c) {
          text = c.violetText;
          surface = c.colors.surface;
          return const SizedBox();
        }),
      ));
      expect(_contrast(text, surface), greaterThanOrEqualTo(4.5),
          reason: 'violet text on ${theme.brightness} surface');
    }
  });
}
