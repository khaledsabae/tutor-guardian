// DS8: fonts are bundled, and runtime fetching is off — so every GoogleFonts
// call in lib/ must name a bundled family, and every weight the package can
// resolve for it must be on disk. A family added without its files would
// render the platform fallback everywhere, silently.

import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/theme/bundled_fonts.dart';

/// GoogleFonts method → file-name family, and the weights the package defines.
const _bundled = <String, (String, List<String>)>{
  'cairo': ('Cairo', ['ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black']),
  'cairoTextTheme': ('Cairo', ['Regular']),
  'amiriQuran': ('AmiriQuran', ['Regular']),
  'tajawal': ('Tajawal', ['ExtraLight', 'Light', 'Regular', 'Medium', 'Bold', 'ExtraBold', 'Black']),
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('every GoogleFonts call in lib/ uses a bundled family', () {
    final used = <String>{};
    final call = RegExp(r'GoogleFonts\.(\w+)\(');
    for (final f in Directory('lib').listSync(recursive: true).whereType<File>()) {
      if (!f.path.endsWith('.dart')) continue;
      for (final m in call.allMatches(f.readAsStringSync())) {
        used.add(m.group(1)!);
      }
    }
    expect(used, isNotEmpty);
    expect(used.difference(_bundled.keys.toSet()), isEmpty,
        reason: 'bundle the font under assets/google_fonts/ before using it');
  });

  test('every weight of every bundled family is in the asset bundle', () async {
    final manifest = await AssetManifest.loadFromAssetBundle(rootBundle);
    final assets = manifest.listAssets().toSet();
    for (final (family, weights) in _bundled.values) {
      for (final w in weights) {
        expect(assets, contains('assets/google_fonts/$family-$w.ttf'));
      }
    }
  });

  test('each bundled family ships its OFL licence', () async {
    for (final path in kBundledFontLicences.values) {
      final text = await rootBundle.loadString(path);
      expect(text, contains('SIL Open Font License'));
    }
  });
}
