/// Fonts ship inside the app (UX_UI_ROADMAP DS8).
///
/// `google_fonts` used to download Cairo, Amiri Quran and Tajawal on first
/// use. An offline first launch therefore rendered Arabic in the platform
/// fallback — different shaping and metrics, so the layout jumped when the
/// real font arrived — and every launch told fonts.gstatic.com the app was
/// open. The exact files the package would have fetched (same sha256) now live
/// in `assets/google_fonts/`, which the package checks before the network.
///
/// Runtime fetching is switched off so a style that is *not* bundled fails
/// loudly in development instead of quietly phoning home in production;
/// `test/bundled_fonts_test.dart` keeps the bundle and the call sites in step.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

/// Families bundled under `assets/google_fonts/`, with their licence file.
const Map<String, String> kBundledFontLicences = {
  'Cairo': 'assets/google_fonts/OFL-cairo.txt',
  'Amiri Quran': 'assets/google_fonts/OFL-amiriquran.txt',
  'Tajawal': 'assets/google_fonts/OFL-tajawal.txt',
};

void configureBundledFonts() {
  GoogleFonts.config.allowRuntimeFetching = false;
  // The SIL Open Font License requires the licence to travel with the fonts;
  // this puts it on the app's licences page next to the packages'.
  LicenseRegistry.addLicense(_fontLicences);
}

Stream<LicenseEntry> _fontLicences() async* {
  for (final entry in kBundledFontLicences.entries) {
    final text = await rootBundle.loadString(entry.value);
    yield LicenseEntryWithLineBreaks(<String>[entry.key], text);
  }
}
