// ignore_for_file: avoid_print — this is a CLI report; printing is the point.
// Counts surfaces that still hard-code a light colour instead of reading the
// palette — the exact defect that shipped in 1.0.48+93.
//
// Dark mode was verified on an emulator, one screen at a time, and passed.
// What that missed is that "I fixed the tiles I could see" is not the same as
// "no screen hard-codes a light ground". 161 sites across 49 files did.
//
// Run:  dart run tool/audit_light_surfaces.dart
//       dart run tool/audit_light_surfaces.dart --list
//
// Exits non-zero while any remain, so it can gate the flip of
// ThemeModeNotifier's default back to ThemeMode.system.

import 'dart:io';
import 'dart:math';

/// A colour literal in any position. Whether it is a *surface* is decided by
/// what encloses it, not by the property name — `color:` means the ground
/// inside `BoxDecoration`, and the ink inside `TextStyle`.
final _colour = RegExp(
  r'(backgroundColor|color|fillColor|cardColor)\s*:\s*(?:const\s+)?'
  r'(Colors\.white\d*|Color\(0x([0-9A-Fa-f]{8})\))',
);

/// Constructors whose `color:` paints a ground.
final _groundCtor = RegExp(
  r'\b(BoxDecoration|ShapeDecoration|Material|Card|Container|DecoratedBox|'
  r'ColoredBox|Scaffold|AppBar|BottomSheet|Chip|Ink)\s*\(',
);

/// Constructors whose `color:` paints ink or an icon — white here is usually
/// deliberate, sitting on top of a brand colour that is the same in both
/// themes. 31 of these were flagged by an earlier, blunter version of this
/// check and every one turned out to be correct as written.
final _inkCtor = RegExp(
  r'\b(TextStyle|Icon|IconData|IconThemeData|CircleAvatar|shimmer|'
  r'AlwaysStoppedAnimation)\s*\(|'
  r'\b(labelStyle|titleTextStyle|foregroundColor|decorationColor|valueColor|'
  r'iconTheme|indicatorColor|cursorColor)\s*:',
);

double _luminance(String argb) {
  double channel(int v) {
    final c = v / 255.0;
    return c <= 0.03928 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4).toDouble();
  }

  final r = int.parse(argb.substring(2, 4), radix: 16);
  final g = int.parse(argb.substring(4, 6), radix: 16);
  final b = int.parse(argb.substring(6, 8), radix: 16);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/// Walks backwards counting brackets to find the constructor this argument
/// belongs to. Two lines of context is not enough — `Icon(` and
/// `BoxDecoration(` both routinely sit five lines above their `color:`.
String _enclosing(List<String> lines, int index, int fromColumn) {
  var depth = 0;
  for (var i = index; i >= 0 && i > index - 40; i--) {
    final line = lines[i];
    for (var c = (i == index ? fromColumn : line.length) - 1; c >= 0; c--) {
      final ch = line[c];
      if (ch == ')') depth++;
      if (ch == '(') {
        if (depth == 0) {
          final head = line.substring(0, c + 1);
          if (_inkCtor.hasMatch(head)) return 'ink';
          if (_groundCtor.hasMatch(head)) return 'ground';
          return 'other';
        }
        depth--;
      }
    }
  }
  return 'other';
}

void main(List<String> args) {
  final verbose = args.contains('--list');
  final hits = <String, List<String>>{};

  for (final entity in Directory('lib').listSync(recursive: true)) {
    if (entity is! File || !entity.path.endsWith('.dart')) continue;
    if (entity.path.contains('l10n/app_localizations')) continue;
    if (entity.path.contains('theme/app_palette.dart')) continue; // the source

    final lines = entity.readAsLinesSync();
    for (var i = 0; i < lines.length; i++) {
      // A white that is correct in BOTH themes — a play button over a video
      // thumbnail, say — is annotated where it lives, with its reason, so the
      // exception travels with the code instead of living in this file.
      //   color: Colors.white, // audit-ok: <why>
      if (lines[i].contains('audit-ok:')) continue;
      for (final m in _colour.allMatches(lines[i])) {
        final prop = m.group(1)!;
        final token = m.group(2)!;

        double lum;
        if (token.startsWith('Colors.white')) {
          // Colors.white12 / white54 / white70 are already translucent.
          if (token != 'Colors.white') continue;
          final rest = lines[i].substring(m.end);
          final alpha = RegExp(r'^\.withValues\(alpha:\s*([0-9.]+)')
              .firstMatch(rest);
          if (alpha != null &&
              (double.tryParse(alpha.group(1)!) ?? 1) < 0.4) {
            continue;
          }
          lum = 1.0;
        } else {
          final argb = m.group(3)!;
          // A near-transparent overlay tints whatever is under it and reads
          // correctly in both themes.
          if (int.parse(argb.substring(0, 2), radix: 16) < 0x40) continue;
          lum = _luminance(argb);
        }
        if (lum <= 0.55) continue;

        // `backgroundColor`/`fillColor`/`cardColor` are grounds by name.
        // A bare `color:` needs its enclosing constructor to decide.
        final isGround = prop != 'color' ||
            _enclosing(lines, i, m.start) == 'ground';
        if (!isGround) continue;

        hits.putIfAbsent(entity.path, () => []).add(
              '  ${i + 1}: ${lines[i].trim()}',
            );
      }
    }
  }

  final total = hits.values.fold<int>(0, (a, b) => a + b.length);
  if (total == 0) {
    print('✅  no hard-coded light surfaces — ThemeMode.system is safe to '
        'restore as the default');
    exit(0);
  }

  print('❌  $total hard-coded light surface(s) in ${hits.length} file(s)\n');
  final entries = hits.entries.toList()
    ..sort((a, b) => b.value.length.compareTo(a.value.length));
  for (final e in entries) {
    print('${e.value.length.toString().padLeft(4)}  ${e.key}');
    if (verbose) e.value.forEach(print);
  }
  print('\nEach one is a screen that stays light while the rest of the app '
      'goes dark.\nWhite text and overlays sitting ON brand colour are '
      'deliberate — check before\nreplacing, and prefer AppPalette over a '
      'literal either way.');
  exit(1);
}
