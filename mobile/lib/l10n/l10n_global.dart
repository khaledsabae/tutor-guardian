/// Access to [AppLocalizations] for code that runs outside the widget tree
/// (API-client errors, state notifiers, background services).
///
/// `TutorGuardianApp`'s `builder` keeps [AppL10n.current] in sync with the
/// app locale on every rebuild; before the first frame it falls back to
/// Arabic, the app's default locale.
library;

import 'package:flutter/widgets.dart';

import 'app_localizations.dart';

abstract final class AppL10n {
  static AppLocalizations current = lookupAppLocalizations(const Locale('ar'));
}
