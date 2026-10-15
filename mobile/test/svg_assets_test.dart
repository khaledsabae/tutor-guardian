/// «ورق مقصوص» — every SVG the app ships is one flutter_svg can draw.
///
/// The art set is hand-written SVG (assets/svg/, rules in STYLE.md). A file
/// flutter_svg cannot parse does not crash anything: the picture just stays
/// empty, or the error builder quietly swaps in a fallback, and the screen
/// ships with a hole in it. So the whole set is pinned here instead:
///
///   1. Every file on disk under assets/svg/{noor,icons,art} is in the bundle
///      (a folder missing from pubspec.yaml is a silent hole, too).
///   2. Every file decodes through flutter_svg's own loader
///      ([SvgAssetLoader] → `vg.loadPicture`) — the exact path [SvgPicture]
///      takes on a device — into a picture the size of its viewBox.
///   3. Every file, pumped as an [SvgPicture.asset], paints without its
///      error builder firing.
///   4. The STYLE.md technical rules hold: only the elements flutter_svg
///      renders faithfully. flutter_svg *skips* what it does not support
///      (`<filter>`, `<mask>`, CSS) with a warning, not an error — a skipped
///      paper shadow would pass 2 and 3 and still look wrong.
///   5. One icon per [BrandIcon] value, named after it — BrandGlyph builds the
///      path from `icon.name`.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/widgets/ui/brand_glyph.dart';

const _folders = [
  'assets/svg/noor',
  'assets/svg/icons',
  'assets/svg/art',
  // The story scenes' paper pieces (tool/story_art.py): 240² props and
  // 360×240 backdrops, the bg_ files.
  'assets/svg/stories',
];

/// What is on disk — the source of truth for "every file".
List<String> _onDisk() {
  final paths = <String>[
    for (final folder in _folders)
      for (final entity in Directory(folder).listSync())
        if (entity is File && entity.path.endsWith('.svg'))
          entity.path.replaceAll(r'\', '/'),
  ]..sort();
  return paths;
}

/// The viewBox each folder is drawn on (STYLE.md). The two wide scenes are
/// the only exceptions, and they are named.
const _viewBoxes = <String, String>{
  'assets/svg/noor': '0 0 240 240',
  'assets/svg/icons': '0 0 48 48',
  'assets/svg/art': '0 0 240 240',
  'assets/svg/stories': '0 0 240 240',
};
const _viewBoxExceptions = <String, String>{
  'assets/svg/art/onboarding_welcome.svg': '0 0 360 240',
  'assets/svg/art/share_bg_celebration.svg': '0 0 360 640',
};

/// The drawing size [path] declares, by folder unless it is an exception.
Size _viewBox(String path) {
  final viewBox =
      _viewBoxExceptions[path] ??
      (path.startsWith('assets/svg/stories/bg_') ? '0 0 360 240' : null) ??
      _viewBoxes[path.substring(0, path.lastIndexOf('/'))]!;
  final parts = viewBox.split(' ').map(double.parse).toList();
  return Size(parts[2], parts[3]);
}

const _allowedElements = {
  'svg',
  'g',
  'path',
  'rect',
  'circle',
  'ellipse',
  'polygon',
  'polyline',
  'line',
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final files = _onDisk();

  test('the art set is on disk at all', () {
    // 7 Noor faces + 17 icons + 20 scenes when this was written; a big drop
    // means a folder went missing, not that the art got leaner.
    expect(files.length, greaterThanOrEqualTo(44), reason: files.join('\n'));
  });

  test('every SVG on disk is in the bundle', () async {
    final manifest = await AssetManifest.loadFromAssetBundle(rootBundle);
    final bundled = manifest.listAssets().toSet();
    final missing = files.where((f) => !bundled.contains(f)).toList();
    expect(
      missing,
      isEmpty,
      reason: 'on disk but not bundled — declare the folder in pubspec.yaml',
    );
  });

  group('every SVG decodes through flutter_svg', () {
    for (final path in files) {
      test(path, () async {
        final info = await vg.loadPicture(SvgAssetLoader(path), null);
        addTearDown(info.picture.dispose);
        expect(info.size, _viewBox(path), reason: path);
      });
    }
  });

  group('every SVG paints as an SvgPicture without its error builder', () {
    for (final path in files) {
      testWidgets(path, (tester) async {
        Object? failure;
        await tester.pumpWidget(
          Directionality(
            textDirection: TextDirection.rtl,
            child: Center(
              child: SvgPicture.asset(
                path,
                width: 96,
                height: 96,
                errorBuilder: (context, error, stack) {
                  failure = error;
                  return const SizedBox(width: 96, height: 96);
                },
              ),
            ),
          ),
        );
        // The parse runs in an isolate — real time, not the test's fake one.
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 300)),
        );
        await tester.pump();
        expect(failure, isNull, reason: '$path: $failure');
        expect(tester.takeException(), isNull);
        // The placeholder is a bare box; a FittedBox exists only once the
        // picture arrived — this is what proves it was drawn, not skipped.
        expect(
          find.descendant(
            of: find.byType(SvgPicture),
            matching: find.byType(FittedBox),
          ),
          findsOneWidget,
          reason: '$path never produced a picture',
        );
        // Given both sides, the picture keeps its own aspect from the height.
        final box = _viewBox(path);
        expect(
          tester.getSize(find.byType(SvgPicture)),
          Size(96 * box.width / box.height, 96),
        );
      });
    }
  });

  group('STYLE.md: only what flutter_svg draws faithfully', () {
    for (final path in files) {
      test(path, () {
        final source = File(path).readAsStringSync();
        final tags = RegExp(
          r'<\s*([A-Za-z][\w:-]*)',
        ).allMatches(source).map((m) => m.group(1)!).toSet();
        final foreign = tags.difference(_allowedElements);
        expect(
          foreign,
          isEmpty,
          reason:
              '$path uses $foreign — flutter_svg skips or mangles it '
              '(STYLE.md lists what is allowed)',
        );
        expect(source, isNot(contains('class=')), reason: '$path: CSS class');
        expect(source, isNot(contains('style=')), reason: '$path: CSS style');
        expect(source, isNot(contains('xlink')), reason: '$path: xlink');
        expect(source, isNot(contains('url(')), reason: '$path: url() paint');
        final root = RegExp(r'<svg\b[^>]*>').firstMatch(source)!.group(0)!;
        expect(root, contains('viewBox='), reason: '$path: root needs viewBox');
        expect(
          RegExp(r'\s(width|height)=').hasMatch(root),
          isFalse,
          reason: '$path: fixed width/height on the root — viewBox only',
        );
        expect(
          source.length,
          lessThanOrEqualTo(12 * 1024),
          reason: '$path is over the 12 KB budget',
        );
      });
    }
  });

  test('one icon file per BrandIcon value, named after it', () {
    final icons = files
        .where((f) => f.startsWith('assets/svg/icons/'))
        .map((f) => f.substring('assets/svg/icons/'.length, f.length - 4))
        .toSet();
    final values = BrandIcon.values.map((i) => i.name).toSet();
    expect(icons.difference(values), isEmpty, reason: 'icon without a value');
    expect(values.difference(icons), isEmpty, reason: 'value without an icon');
  });
}
