// Design-system guards (UX_UI_ROADMAP.md, UX-0).
//
// Pins the three things the 2026-09 audit found broken and fixed:
//   1. Text on filled buttons meets WCAG AA (4.5:1) in BOTH palettes. The
//      button themes hard-coded Colors.white: 2.5:1 on the dark primary and
//      1.7:1 on the dark gold. The on-colour tokens exist so this cannot
//      silently regress.
//   2. Invalid form fields get a visible outline (error borders exist).
//   3. Raw exception strings never reach a parent — describeFailure maps them.

import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/app_localizations_en.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/widgets/ui/error_retry_view.dart';

double contrast(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05);
}

void main() {
  group('WCAG AA text contrast (≥ 4.5:1)', () {
    for (final p in [AppPalette.light, AppPalette.dark]) {
      final name = p.isDark ? 'dark' : 'light';
      final pairs = <String, List<Color>>{
        'onPrimary on primary': [p.onPrimary, p.primary],
        'onAccent on accent': [p.onAccent, p.accent],
        'ink on background': [p.ink, p.background],
        'ink on surface': [p.ink, p.surface],
        'ink on surfaceAlt': [p.ink, p.surfaceAlt],
        'dangerFg on dangerBg': [p.dangerFg, p.dangerBg],
        'warningFg on warningBg': [p.warningFg, p.warningBg],
        'tipInk on tip': [p.tipInk, p.tipGradient.last],
      };
      pairs.forEach((label, c) {
        test('$name: $label', () {
          expect(contrast(c[0], c[1]), greaterThanOrEqualTo(4.5),
              reason: '$label is ${contrast(c[0], c[1]).toStringAsFixed(2)}:1');
        });
      });
    }
  });

  test('button themes read the on-colour tokens, not Colors.white', () {
    // Asserted on source: building ThemeData needs GoogleFonts assets that
    // tests do not have (see dark_mode_test.dart).
    final src = File('lib/theme/app_theme.dart').readAsStringSync();
    expect(src, contains('foregroundColor: p.onPrimary'));
    expect(src, contains('foregroundColor: p.onAccent'));
    expect(src, isNot(contains('foregroundColor: Colors.white')));
  });

  test('invalid inputs get a visible error outline', () {
    final src = File('lib/theme/app_theme.dart').readAsStringSync();
    expect(src, contains('errorBorder: OutlineInputBorder('));
    expect(src, contains('focusedErrorBorder: OutlineInputBorder('));
  });

  group('describeFailure', () {
    final AppLocalizations l10n = AppLocalizationsEn();

    test('connection failures read as offline', () {
      expect(describeFailure(l10n, const SocketException('Failed host lookup')),
          l10n.errorOfflineBody);
      expect(describeFailure(l10n, TimeoutException('slow')), l10n.errorOfflineBody);
    });

    test('5xx reads as our problem, not the parent\'s', () {
      expect(describeFailure(l10n, const TgApiError(503, 'upstream')),
          l10n.errorServerBody);
    });

    test('a 4xx carries the server-written message through', () {
      expect(describeFailure(l10n, const TgApiError(404, 'Child not found.')),
          'Child not found.');
    });

    test('anything else never leaks its toString()', () {
      final out = describeFailure(l10n, StateError('boom'));
      expect(out, l10n.errorUnknownBody);
      expect(out, isNot(contains('StateError')));
    });
  });
}
