/// What a child's name has to be, wherever the parent types one.
///
/// The server takes 1–80 characters after trimming (`ChildCreateRequest` and
/// `ChildUpdateRequest` in `backend/app/routers/children.py`); the add and
/// edit forms say so before a request does.
///
/// Onboarding asks too — one optional line on the creation wait («الاسم»,
/// phase 2 of docs/NOOR_WAL_QANADIL_PLAN.md) — and is stricter, on top of the
/// same rule: the name fills a title («درب سارة») and the greeting on Today,
/// so it is capped at [onboardingNameMaxLength], and a digits-only answer
/// reads as a mistyped field, not a name.
library;

import '../../../l10n/app_localizations.dart';

/// The add/edit forms' rule. Null when [raw] is acceptable.
String? childNameError(AppLocalizations l10n, String? raw) {
  final name = raw?.trim() ?? '';
  if (name.isEmpty) return l10n.addChildNameRequired;
  if (name.length > 80) return l10n.addChildNameTooLong;
  return null;
}

const onboardingNameMaxLength = 30;

/// ASCII, Arabic-Indic and Persian digits, and the spaces between them.
final _digitsOnly = RegExp(r'^[0-9٠-٩۰-۹\s]+$');

/// The onboarding field's rule: [childNameError], then the stricter checks.
String? onboardingNameError(AppLocalizations l10n, String raw) {
  final base = childNameError(l10n, raw);
  if (base != null) return base;
  final name = raw.trim();
  // Code points, as the server counts (Python's len), not UTF-16 units.
  if (name.runes.length > onboardingNameMaxLength) {
    return l10n.onbNameTooLong;
  }
  if (_digitsOnly.hasMatch(name)) return l10n.onbNameDigitsOnly;
  return null;
}
