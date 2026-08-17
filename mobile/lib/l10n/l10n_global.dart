/// Access to [AppLocalizations] for code that runs outside the widget tree
/// (API-client errors, state notifiers, background services).
///
/// `TutorGuardianApp`'s `builder` keeps [AppL10n.current] in sync with the
/// app locale on every rebuild; before the first frame it falls back to
/// Arabic, the app's default locale.
library;

import 'dart:io' show Platform;
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/widgets.dart';

import 'app_localizations.dart';

abstract final class AppL10n {
  static AppLocalizations current = lookupAppLocalizations(const Locale('ar'));
}

/// The one place that decides which language content is served in.
///
/// There used to be two answers. Curriculum TEXT followed
/// `TgClient.uiLanguage`, which was assigned only when the user picked a
/// language explicitly; media followed the device locale. So a phone set to
/// English whose owner never touched the language switch received English
/// podcasts over Arabic lesson text — reported from production as «بعض الدروس
/// بالانجليزية رغم اني نزلت التطبيق بالعربي», and its mirror image «أغير
/// الاعدادات الى اللغة الانجليزية لكن الدروس باللغة العربية». Two reports in
/// two days pointing opposite ways, because they were two halves of one split.
///
/// [explicit] is the stored choice, or null when the user never made one — in
/// which case the device decides, exactly as `MaterialApp` does with a null
/// `locale`. Resolved against `supportedLocales` rather than a hard-coded
/// ar/en pair, so adding a third language does not silently leave its speakers
/// on Arabic. Anything unsupported falls back to Arabic.
String resolvedContentLanguage(String? explicit) {
  final code = explicit ??
      // Pinned under test for the reason MaterialApp pins it: the host
      // machine's locale must not decide what a widget test asserts.
      (Platform.environment.containsKey('FLUTTER_TEST')
          ? 'ar'
          : PlatformDispatcher.instance.locale.languageCode);
  final supported =
      AppLocalizations.supportedLocales.map((l) => l.languageCode).toSet();
  return supported.contains(code) ? code : 'ar';
}
