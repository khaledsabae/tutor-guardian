/// Onboarding storage — single source of truth for "first-launch" state.
///
/// Backed by [SharedPreferences] (plain text on Android, NSUserDefaults
/// on iOS). The package is not encrypted — none of these values are
/// sensitive. For the actual chat session (Bearer token, device id)
/// we keep using [flutter_secure_storage].
library;

import 'package:shared_preferences/shared_preferences.dart';

class OnboardingStorage {
  OnboardingStorage(this._prefs);

  static const _kOnboardingCompleted = 'tg.onboarding.completed';
  static const _kActiveChildId = 'tg.active_child_id';
  static const _kActiveChildName = 'tg.active_child_name';
  static const _kActiveChildAgeGroup = 'tg.active_child_age_group';

  final SharedPreferences _prefs;

  /// Has the user finished the onboarding flow at least once?
  bool get onboardingCompleted =>
      _prefs.getBool(_kOnboardingCompleted) ?? false;

  Future<void> markOnboardingCompleted() async {
    await _prefs.setBool(_kOnboardingCompleted, true);
  }

  Future<void> resetOnboarding() async {
    await _prefs.setBool(_kOnboardingCompleted, false);
  }

  int? get activeChildId => _prefs.getInt(_kActiveChildId);

  String? get activeChildName => _prefs.getString(_kActiveChildName);

  String? get activeChildAgeGroup => _prefs.getString(_kActiveChildAgeGroup);

  Future<void> setActiveChild({
    required int id,
    required String name,
    required String ageGroup,
  }) async {
    await _prefs.setInt(_kActiveChildId, id);
    await _prefs.setString(_kActiveChildName, name);
    await _prefs.setString(_kActiveChildAgeGroup, ageGroup);
  }

  Future<void> clearActiveChild() async {
    await _prefs.remove(_kActiveChildId);
    await _prefs.remove(_kActiveChildName);
    await _prefs.remove(_kActiveChildAgeGroup);
  }

  /// Clear everything — useful for "switch device" debug flows.
  Future<void> clearAll() async {
    await _prefs.remove(_kOnboardingCompleted);
    await clearActiveChild();
  }
}
