/// BrandGlyph — the drawn icon set (جولة الحرفة, item 1).
///
/// Pinned here:
///   1. Every glyph paints: pumped at two sizes in BOTH palettes without an
///      exception, and its painter actually issues draw calls (golden-lite:
///      a recording canvas that counts — an empty painter must not pass).
///   2. The glyph follows the live palette: light and dark hosts paint
///      different colours.
///   3. Emoji-as-graphics never come back: the files this tour migrated are
///      scanned (comments stripped) and any emoji in code fails the test.
library;

import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
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

/// A [Canvas] that forwards the draw calls the glyph painters use and counts
/// them, so "the painter ran" is provable without golden files.
class _CountingCanvas implements Canvas {
  _CountingCanvas(this._inner);

  final Canvas _inner;
  int draws = 0;

  void _mark() => draws++;

  @override
  void drawPath(ui.Path path, Paint paint) {
    _mark();
    _inner.drawPath(path, paint);
  }

  @override
  void drawCircle(Offset c, double radius, Paint paint) {
    _mark();
    _inner.drawCircle(c, radius, paint);
  }

  @override
  void drawLine(Offset p1, Offset p2, Paint paint) {
    _mark();
    _inner.drawLine(p1, p2, paint);
  }

  @override
  void drawRect(Rect rect, Paint paint) {
    _mark();
    _inner.drawRect(rect, paint);
  }

  @override
  void drawRRect(RRect rrect, Paint paint) {
    _mark();
    _inner.drawRRect(rrect, paint);
  }

  @override
  void drawOval(Rect rect, Paint paint) {
    _mark();
    _inner.drawOval(rect, paint);
  }

  // The transform plumbing the painter uses; not draws, just forwarded.
  @override
  void save() => _inner.save();
  @override
  void restore() => _inner.restore();
  @override
  void translate(double dx, double dy) => _inner.translate(dx, dy);
  @override
  void scale(double sx, [double? sy]) => _inner.scale(sx, sy);

  @override
  dynamic noSuchMethod(Invocation invocation) => throw StateError(
    'BrandGlyph painter used ${invocation.memberName}, '
    'which the counting canvas does not forward',
  );
}

void main() {
  group('every glyph paints', () {
    for (final icon in BrandIcon.values) {
      for (final palette in [AppPalette.light, AppPalette.dark]) {
        final sizeNames = [16.0, 96.0];
        for (final size in sizeNames) {
          testWidgets(
            '${icon.name} @ ${size.toStringAsFixed(0)}px '
            '(${palette.isDark ? 'dark' : 'light'}) paints and records draws',
            (tester) async {
              await tester.pumpWidget(
                _host(BrandGlyph(icon, size: size), palette),
              );

              expect(tester.takeException(), isNull);
              final glyphPaint = find
                  .descendant(
                    of: find.byType(BrandGlyph),
                    matching: find.byType(CustomPaint),
                  )
                  .first;
              expect(glyphPaint, findsOneWidget);
              expect(tester.getSize(glyphPaint), Size(size, size));

              // Golden-lite: re-run the painter against a counting canvas.
              final customPaint = tester.widget<CustomPaint>(glyphPaint);
              final painter = customPaint.painter!;
              final recorder = ui.PictureRecorder();
              final counting = _CountingCanvas(Canvas(recorder));
              painter.paint(counting, Size(size, size));
              expect(
                counting.draws,
                greaterThan(0),
                reason:
                    '${icon.name} recorded no draw calls — an empty '
                    'glyph slipped into the set',
              );
            },
          );
        }
      }
    }
  });

  testWidgets('the default colour follows the live palette', (tester) async {
    final key = UniqueKey();
    await tester.pumpWidget(
      _host(BrandGlyph(key: key, BrandIcon.crescent), AppPalette.light),
    );
    final glyphPaint = find
        .descendant(
          of: find.byType(BrandGlyph),
          matching: find.byType(CustomPaint),
        )
        .first;
    final lightPainter = (tester.widget<CustomPaint>(glyphPaint).painter!);
    await tester.pumpWidget(
      _host(BrandGlyph(key: key, BrandIcon.crescent), AppPalette.dark),
    );
    // MaterialApp animates the theme (AnimatedTheme, ~200ms) — the glyph
    // only sees the dark palette after the lerp.
    await tester.pump(const Duration(milliseconds: 400));

    final darkPainter = tester.widget<CustomPaint>(glyphPaint).painter!;
    expect(
      lightPainter,
      isNot(darkPainter),
      reason: 'palette change must repaint',
    );
    expect(lightPainter.shouldRepaint(darkPainter), isTrue);
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
