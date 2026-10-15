/// BrandGlyph — the brand icon set (جولة الحرفة, item 1; «ورق مقصوص» SVG
/// since 2026-10-14).
///
/// Pinned here:
///   1. Every glyph draws: its own SVG (`assets/svg/icons/<name>.svg`),
///      pumped at two sizes in BOTH palettes, arrives as a picture (not the
///      placeholder, not the error box) at exactly the asked size.
///   2. The icons are never tinted — a ColorFilter would flatten the paper
///      layers — whatever `color:` a call site still passes.
///   3. `color:` now means only "quiet": a muted role (outline,
///      textSecondary, disabled…) or a colour under 60% alpha draws the icon
///      at 45%; anything else draws it in its own colours. The quiet-time
///      lantern still reads lit vs. out through it.
///   4. Emoji-as-graphics never come back: the files this tour migrated are
///      scanned (comments stripped) and any emoji in code fails the test.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/widgets/ui/brand_glyph.dart';

Widget _host(Widget child, AppPalette palette) {
  return MaterialApp(
    theme: ThemeData(
      brightness: palette.brightness,
      extensions: [AppColors(palette)],
    ),
    home: Scaffold(body: Center(child: child)),
  );
}

/// Pumps real time until every SvgPicture has its picture (a FittedBox is
/// built only then) — the parse runs in an isolate, outside fake time.
Future<void> _untilDrawn(WidgetTester tester) async {
  for (var i = 0; i < 100; i++) {
    final pictures = find.byType(SvgPicture).evaluate().length;
    final drawn = find
        .descendant(
          of: find.byType(SvgPicture),
          matching: find.byType(FittedBox),
        )
        .evaluate()
        .length;
    if (pictures > 0 && drawn == pictures) return;
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pump();
  }
  fail('the glyph never produced a picture');
}

/// The opacity BrandGlyph applies to its picture (1 when it adds none).
double _opacityOf(WidgetTester tester, Finder glyph) {
  final opacities = tester.widgetList<Opacity>(
    find.descendant(of: glyph, matching: find.byType(Opacity)),
  );
  return opacities.isEmpty ? 1 : opacities.single.opacity;
}

void main() {
  group('every glyph draws its own SVG', () {
    for (final icon in BrandIcon.values) {
      for (final palette in [AppPalette.light, AppPalette.dark]) {
        for (final size in const [16.0, 96.0]) {
          testWidgets(
            '${icon.name} @ ${size.toStringAsFixed(0)}px '
            '(${palette.isDark ? 'dark' : 'light'})',
            (tester) async {
              await tester.pumpWidget(
                _host(BrandGlyph(icon, size: size), palette),
              );
              await _untilDrawn(tester);

              expect(tester.takeException(), isNull);
              final svg = tester.widget<SvgPicture>(find.byType(SvgPicture));
              expect(
                (svg.bytesLoader as SvgAssetLoader).assetName,
                'assets/svg/icons/${icon.name}.svg',
              );
              expect(BrandGlyph.assetFor(icon), 'assets/svg/icons/${icon.name}.svg');
              expect(tester.getSize(find.byType(BrandGlyph)), Size(size, size));
              expect(tester.getSize(find.byType(SvgPicture)), Size(size, size));
            },
          );
        }
      }
    }
  });

  group('colour no longer tints; it only says "quiet"', () {
    testWidgets('no colour filter, whatever colour is passed', (tester) async {
      for (final color in [null, Colors.red, Colors.white, Colors.black]) {
        await tester.pumpWidget(
          _host(BrandGlyph(BrandIcon.star, color: color), AppPalette.light),
        );
        final svg = tester.widget<SvgPicture>(find.byType(SvgPicture));
        expect(svg.colorFilter, isNull, reason: 'tinted by $color');
        expect(
          find.descendant(
            of: find.byType(BrandGlyph),
            matching: find.byType(ColorFiltered),
          ),
          findsNothing,
        );
      }
    });

    for (final palette in [AppPalette.light, AppPalette.dark]) {
      final theme = palette.isDark ? 'dark' : 'light';
      testWidgets('muted roles draw at 45%, vivid ones in full ($theme)', (
        tester,
      ) async {
        late BuildContext context;
        await tester.pumpWidget(
          _host(
            Builder(
              builder: (c) {
                context = c;
                return const SizedBox();
              },
            ),
            palette,
          ),
        );
        // MaterialApp animates the theme in; read the settled one.
        await tester.pump(const Duration(milliseconds: 400));
        final scheme = Theme.of(context).colorScheme;
        final quiet = <String, Color>{
          'outline': scheme.outline,
          'outlineVariant': scheme.outlineVariant,
          'disabled': Theme.of(context).disabledColor,
          'textSecondary': palette.textSecondary,
          'inkSoft': palette.inkSoft,
          'translucent primary': palette.primary.withValues(alpha: .4),
        };
        final vivid = <String, Color?>{
          'none': null,
          'primary': palette.primary,
          'accent': palette.accent,
          'accentDeep': palette.accentDeep,
          'onPrimary': palette.onPrimary,
          'tertiary': scheme.tertiary,
          'success': palette.success,
          'dangerFg': palette.dangerFg,
        };
        // Read off the live context before it is replaced by the pumps below.
        for (final MapEntry(key: name, value: color) in quiet.entries) {
          expect(BrandGlyph.isMuted(context, color), isTrue, reason: name);
        }
        for (final MapEntry(key: name, value: color) in vivid.entries) {
          expect(BrandGlyph.isMuted(context, color), isFalse, reason: name);
        }
        for (final MapEntry(key: name, value: color) in quiet.entries) {
          await tester.pumpWidget(
            _host(BrandGlyph(BrandIcon.lantern, color: color), palette),
          );
          expect(
            _opacityOf(tester, find.byType(BrandGlyph)),
            BrandGlyph.mutedOpacity,
            reason: name,
          );
        }
        for (final MapEntry(key: name, value: color) in vivid.entries) {
          await tester.pumpWidget(
            _host(BrandGlyph(BrandIcon.lantern, color: color), palette),
          );
          expect(_opacityOf(tester, find.byType(BrandGlyph)), 1, reason: name);
        }
      });
    }

    testWidgets('the quiet-time lantern still reads lit vs. out', (
      tester,
    ) async {
      // quiet_time_bar.dart: lit = colorScheme.tertiary, out = outline.
      Widget lantern({required bool out}) => Builder(
        builder: (context) {
          final scheme = Theme.of(context).colorScheme;
          return BrandGlyph(
            BrandIcon.lantern,
            size: 20,
            color: out ? scheme.outline : scheme.tertiary,
          );
        },
      );
      await tester.pumpWidget(_host(lantern(out: false), AppPalette.light));
      final lit = _opacityOf(tester, find.byType(BrandGlyph));
      await tester.pumpWidget(_host(lantern(out: true), AppPalette.light));
      final out = _opacityOf(tester, find.byType(BrandGlyph));
      expect(lit, 1);
      expect(out, lessThan(lit));
    });
  });

  testWidgets('a semantic label is exposed when given', (tester) async {
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(
      _host(
        const BrandGlyph(BrandIcon.gift, semanticLabel: 'هدية'),
        AppPalette.light,
      ),
    );
    expect(find.bySemanticsLabel('هدية'), findsOneWidget);
    handle.dispose();
  });

  testWidgets('GlyphHero tiles the glyph at the asked size', (tester) async {
    await tester.pumpWidget(
      _host(const GlyphHero(BrandIcon.lantern, size: 48), AppPalette.dark),
    );
    expect(tester.takeException(), isNull);
    expect(tester.getSize(find.byType(GlyphHero)), const Size(48, 48));
  });

  test('no emoji-as-graphics has returned to the guarded files', () {
    final failures = <String>[];
    for (final path in guardedFiles) {
      final file = File(path);
      expect(
        file.existsSync(),
        isTrue,
        reason:
            '$path is listed in guardedFiles but does not exist — '
            'update the list when files move',
      );
      final code = stripComments(file.readAsStringSync());
      final hit = _emoji.firstMatch(code);
      if (hit != null) {
        final line = code.substring(0, hit.start).split('\n').length;
        failures.add(
          '$path:$line — an emoji is back in code '
          '(جولة الحرفة: draw a BrandGlyph instead)',
        );
      }
    }
    expect(failures, isEmpty, reason: failures.join('\n'));
  });
}

// ── The no-emoji guard ────────────────────────────────────────────────────

/// The files this tour owns for emoji-as-graphics. Extend the list when a
/// new surface migrates — the test then guards it for free.
const guardedFiles = <String>[
  'lib/widgets/ui/brand_glyph.dart',
  'lib/features/onboarding/screens/onboarding_screen.dart',
  'lib/features/program/screens/quiz_screen.dart',
  'lib/features/program/widgets/next_step_sheet.dart',
  'lib/features/missions/pending_missions_screen.dart',
  'lib/features/home/widgets/home_stats_row.dart',
  'lib/features/home/widgets/today_focus_card.dart',
  'lib/widgets/ui/celebration_overlay.dart',
  'lib/widgets/ui/stat_chip.dart',
  'lib/widgets/ui/empty_state.dart',
  'lib/screens/home_screen.dart',
  'lib/features/home/widgets/today_section.dart',
  'lib/features/home/widgets/today_ask_block.dart',
  'lib/features/home/widgets/today_child_block.dart',
  'lib/features/home/widgets/daily_gift_moment.dart',
  'lib/features/missions/child_mission_screen.dart',
  'lib/features/missions/praise_header.dart',
  'lib/features/companion/widgets/noor_face.dart',
  'lib/features/companion/widgets/noor_presence.dart',
  'lib/features/home/widgets/home_app_bar.dart',
  'lib/features/home/greeting.dart',
  'lib/features/program/widgets/active_child_chip.dart',
  'lib/features/program/screens/lesson_screen.dart',
  'lib/features/hub/data/hub_catalog.dart',
  'lib/features/hub/widgets/hub_group_card.dart',
  'lib/features/routine/widgets/child_mode_shell.dart',
  'lib/features/routine/screens/habit_child_mode_screen.dart',
  'lib/features/routine/widgets/quiet_time_bar.dart',
];

/// The emoji this tour replaced. Detected generically (any emoji range), but
/// listed so a failure names the regression, not a codepoint.
const bannedEmoji = <String>[
  // 🌍 💡 🎁 🚀 🎯 🌟 🪙 🔥 📚 🏅 — the tour's brief.
  '🌍', '💡', '🎁', '🚀', '🎯', '🌟', '🪙', '🔥', '📚', '🏅',
  // Others replaced along the way in the same files.
  '🌙', '🛤️', '💬', '📡', '❓', '🏆', '🏁', '💪',
];

final _emoji = RegExp(
  '[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]',
  unicode: true,
);

/// Strips // and /* */ comments, keeping string literals intact (an emoji in
/// a comment documents history; one in code is a regression).
String stripComments(String source) {
  final out = StringBuffer();
  var inLine = false, inBlock = false;
  var quote = ''; // '', "'", '"'
  var escape = false;
  for (var i = 0; i < source.length; i++) {
    final c = source[i];
    final next = i + 1 < source.length ? source[i + 1] : '';
    if (inLine) {
      if (c == '\n') {
        inLine = false;
        out.write(c);
      }
      continue;
    }
    if (inBlock) {
      if (c == '*' && next == '/') {
        inBlock = false;
        i++;
      }
      continue;
    }
    if (quote.isNotEmpty) {
      out.write(c);
      if (escape) {
        escape = false;
      } else if (c == r'\') {
        escape = true;
      } else if (c == quote) {
        quote = '';
      }
      continue;
    }
    if (c == "'" || c == '"') {
      quote = c;
      out.write(c);
      continue;
    }
    if (c == '/' && next == '/') {
      inLine = true;
      continue;
    }
    if (c == '/' && next == '*') {
      inBlock = true;
      i++;
      continue;
    }
    out.write(c);
  }
  return out.toString();
}
