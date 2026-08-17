/// Riverpod providers for the onboarding flow + active-child wiring.
///
/// Providers:
///   * sharedPreferencesProvider   (FutureProvider — boot once, cached)
///   * onboardingStorageProvider  (`Provider<OnboardingStorage>`)
///   * onboardingCompletedProvider (`StateProvider<bool>` — initialized
///     from disk on first build)
///   * activeChildProfileProvider (derived — {id, name, ageGroup} or
///     null when the user has not finished onboarding)
///
/// Submitting the form goes through `createChildProvider` (defined in
/// `progress_providers.dart`) — that already calls
/// `OnboardingStorage.setActiveChild` via this provider.
library;

import 'dart:ui';

import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../api/tg_client.dart';
import '../../../l10n/l10n_global.dart';
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
  OnboardingCompletedNotifier(bool Function() read) : super(read());

  Future<void> markCompleted() async {
    state = true;
  }
}

final onboardingCompletedProvider =
    StateNotifierProvider<OnboardingCompletedNotifier, bool>((ref) {
  final storage = ref.watch(onboardingStorageProvider);
  return OnboardingCompletedNotifier(() => storage.onboardingCompleted);
});

/// Which guided-tour version the user has completed (0 = none). Read once at
/// launch by `RootScaffold`; `ref.invalidate` it after `markTourSeen` so the
/// settings replay row takes effect without a restart.
final tourVersionProvider = Provider<int>((ref) {
  return ref.watch(onboardingStorageProvider).tourVersion;
});

/// The active child profile, derived from disk. Returns null when the
/// user hasn't completed onboarding OR has explicitly cleared the
/// child (e.g. in a debug flow).
class ActiveChildProfile {
  final int id;
  final String name;
  final String ageGroup;
  final String? avatarEmoji;
  const ActiveChildProfile({
    required this.id,
    required this.name,
    required this.ageGroup,
    this.avatarEmoji,
  });
}

final activeChildProfileProvider = Provider<ActiveChildProfile?>((ref) {
  final storage = ref.watch(onboardingStorageProvider);
  final id = storage.activeChildId;
  final name = storage.activeChildName;
  final age = storage.activeChildAgeGroup;
  final avatar = storage.activeChildAvatar;
  if (id == null || name == null || age == null) return null;
  return ActiveChildProfile(id: id, name: name, ageGroup: age, avatarEmoji: avatar);
});

class AppLocaleNotifier extends StateNotifier<Locale?> {
  final SharedPreferences? _prefs;
  AppLocaleNotifier(this._prefs) : super(null) {
    _init();
  }

  void _init() {
    if (_prefs != null) {
      // One-time cleanup: media used to have its own switch under
      // `content_language`, and it could disagree with this one. The app now
      // derives media language from the app locale, so the old key is dead
      // state — removed so nothing can read it back into existence.
      _prefs.remove('content_language');
      final code = _prefs.getString('tg.ui_language');
      if (code != null) {
        state = Locale(code);
      }
    }
    // No stored choice does NOT mean Arabic. `state` stays null so MaterialApp
    // follows the device — but `TgClient.uiLanguage` used to stay null too, so
    // curriculum TEXT carried no `?lang=` and came back Arabic while media
    // followed the device and came back English. Both now read the same
    // resolver, so text and audio can no longer disagree.
    TgClient.uiLanguage = resolvedContentLanguage(state?.languageCode);
  }

  Future<void> setLocale(String languageCode) async {
    state = Locale(languageCode);
    // Curriculum reads carry this so lessons arrive in the chosen language;
    // without it the UI switched and the content stayed Arabic.
    TgClient.uiLanguage = languageCode;
    if (_prefs != null) {
      await _prefs.setString('tg.ui_language', languageCode);
    }
  }
}

final appLocaleProvider =
    StateNotifierProvider<AppLocaleNotifier, Locale?>((ref) {
  final prefsAsync = ref.watch(sharedPreferencesProvider);
  final prefs = prefsAsync.maybeWhen(
    data: (p) => p,
    orElse: () => null,
  );
  return AppLocaleNotifier(prefs);
});


/// Light / dark / follow-the-system, persisted.
///
/// «لدي اقتراح و اتمنى ان تطبقوه ألا و هو الوضع الداكن. فهو اريح للعين» —
/// #fb_e7402eaa, 15 Aug 2026. The app had no `darkTheme` and no `ThemeMode`
/// at all; `design_tokens.dart` said "light mode only for now" in a comment.
///
/// Defaults to [ThemeMode.light] — dark is opt-in.
///
/// It shipped defaulting to [ThemeMode.system] in 1.0.48+93, on the reasoning
/// that a parent whose phone is already dark should not have to find a
/// setting. That was right about the intent and wrong about the readiness:
/// 161 surfaces across 49 files still hard-code a light colour, so every
/// dark-phone user was dropped into a half-converted theme — the Qur'an
/// screen, the lesson sections and the assistant bubble all stayed light with
/// light text on them. Nobody who had not asked for dark mode should absorb
/// that.
///
/// Flip this back to [ThemeMode.system] once the audit in
/// `tool/audit_light_surfaces.dart` reports zero.
class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier(this._prefs) : super(ThemeMode.light) {
    final stored = _prefs?.getString(_key);
    if (stored != null) {
      state = ThemeMode.values.firstWhere(
        (m) => m.name == stored,
        orElse: () => ThemeMode.system,
      );
    }
  }

  static const _key = 'tg.theme_mode';
  final SharedPreferences? _prefs;

  Future<void> set(ThemeMode mode) async {
    state = mode;
    await _prefs?.setString(_key, mode.name);
  }
}

final themeModeProvider =
    StateNotifierProvider<ThemeModeNotifier, ThemeMode>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).maybeWhen(
        data: (p) => p,
        orElse: () => null,
      );
  return ThemeModeNotifier(prefs);
});
