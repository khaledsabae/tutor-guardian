/// Riverpod providers for the onboarding flow + active-child wiring.
///
/// Providers:
///   * sharedPreferencesProvider   (FutureProvider — boot once, cached)
///   * onboardingStorageProvider  (Provider<OnboardingStorage>)
///   * onboardingCompletedProvider (StateProvider<bool> — initialized
///     from disk on first build)
///   * activeChildProfileProvider (derived — {id, name, ageGroup} or
///     null when the user has not finished onboarding)
///
/// Submitting the form goes through `createChildProvider` (defined in
/// `progress_providers.dart`) — that already calls
/// `OnboardingStorage.setActiveChild` via this provider.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/onboarding_storage.dart';

/// Async-loaded once at app start. All other providers wait on this
/// via `ref.watch`.
final sharedPreferencesProvider = FutureProvider<SharedPreferences>((ref) {
  return SharedPreferences.getInstance();
});

final onboardingStorageProvider = Provider<OnboardingStorage>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).requireValue;
  return OnboardingStorage(prefs);
});

/// "Has the user completed onboarding at least once?" Boot value is
/// derived from disk; flipped to `true` only when the form succeeds.
class OnboardingCompletedNotifier extends StateNotifier<bool> {
  OnboardingCompletedNotifier(this._read) : super(_read());
  final bool Function() _read;

  Future<void> markCompleted() async {
    state = true;
  }
}

final onboardingCompletedProvider =
    StateNotifierProvider<OnboardingCompletedNotifier, bool>((ref) {
  final storage = ref.watch(onboardingStorageProvider);
  return OnboardingCompletedNotifier(() => storage.onboardingCompleted);
});

/// The active child profile, derived from disk. Returns null when the
/// user hasn't completed onboarding OR has explicitly cleared the
/// child (e.g. in a debug flow).
class ActiveChildProfile {
  final int id;
  final String name;
  final String ageGroup;
  const ActiveChildProfile({
    required this.id,
    required this.name,
    required this.ageGroup,
  });
}

final activeChildProfileProvider = Provider<ActiveChildProfile?>((ref) {
  final storage = ref.watch(onboardingStorageProvider);
  final id = storage.activeChildId;
  final name = storage.activeChildName;
  final age = storage.activeChildAgeGroup;
  if (id == null || name == null || age == null) return null;
  return ActiveChildProfile(id: id, name: name, ageGroup: age);
});
