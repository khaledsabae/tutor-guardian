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

/// Colour in a background/surface position — not text, not border, not shadow.
final _surface = RegExp(
  r'(backgroundColor|color|fillColor|cardColor|surfaceTintColor)\s*:\s*'
  r'(?:const\s+)?(Colors\.white\d*|Color\(0x([0-9A-Fa-f]{8})\))',
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

void main(List<String> args) {
  final verbose = args.contains('--list');
  final hits = <String, List<String>>{};

  for (final entity in Directory('lib').listSync(recursive: true)) {
    if (entity is! File || !entity.path.endsWith('.dart')) continue;
    if (entity.path.contains('l10n/app_localizations')) continue;
    if (entity.path.contains('theme/app_palette.dart')) continue; // the source

    final lines = entity.readAsLinesSync();
    for (var i = 0; i < lines.length; i++) {
      for (final m in _surface.allMatches(lines[i])) {
        final token = m.group(2)!;
        double lum;
        if (token.startsWith('Colors.white')) {
          lum = 1.0;
        } else {
          final argb = m.group(3)!;
          // A near-transparent overlay tints whatever is under it and is fine
          // in both themes.
          if (int.parse(argb.substring(0, 2), radix: 16) < 0x40) continue;
          lum = _luminance(argb);
        }
        if (lum > 0.55) {
          hits.putIfAbsent(entity.path, () => []).add(
                '  ${i + 1}: ${lines[i].trim()}',
              );
        }
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
