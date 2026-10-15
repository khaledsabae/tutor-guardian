/// Wiring for «قناديل الأسبوع» (نور والقناديل, phase 3).
///
/// One request feeds three places on «اليوم»: the lantern string under ①,
/// the «أسابيع مضيئة» chip, and Noor's Friday line. Any failure — offline,
/// an older server's 404, a malformed answer — is null, and each of them
/// then simply is not there: the lanterns never break «اليوم».
library;

import 'dart:ui' show PlatformDispatcher;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/chat_notifier.dart' show tgClientProvider;
import '../../companion/providers/companion_providers.dart'
    show todayStopsProvider;
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/providers/progress_providers.dart';
import '../data/family_week.dart';
import '../data/lantern_seen_store.dart';

/// The titles' language: the app's chosen one, else the device's.
String _lang(Ref ref) {
  final code =
      ref.watch(appLocaleProvider)?.languageCode ??
      PlatformDispatcher.instance.locale.languageCode;
  return code == 'en' ? 'en' : 'ar';
}

/// This week's lanterns, or null (nothing to show).
///
/// Asked again when something on «اليوم» may have lit a lantern: the active
/// child's lesson progress changed, or a stop of «درب اليوم» was reached. The
/// lantern string also asks again when «اليوم» comes back into view and on
/// resume; ticking the plan asks again itself.
final familyWeekProvider = FutureProvider.autoDispose<FamilyWeek?>((ref) async {
  try {
    ref.watch(activeChildProgressProvider.select((v) => v?.valueOrNull));
    ref.watch(todayStopsProvider.select((s) => (s.step, s.ask, s.mission)));
  } catch (_) {
    // The active child is read from preferences that may not be loaded yet
    // at launch. Only the refresh triggers depend on it — the week is the
    // family's — and they are watched all the same, so it asks again once
    // they load.
  }
  final lang = _lang(ref);
  try {
    final json = await ref
        .watch(tgClientProvider)
        .fetchFamilyWeek(DateTime.now().timeZoneOffset.inMinutes, lang: lang);
    return FamilyWeek.fromJson(json);
  } catch (_) {
    return null;
  }
});

/// The device's record of lanterns already shown lit; null until the
/// preferences are read.
final lanternSeenStoreProvider = Provider.autoDispose<LanternSeenStore?>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).valueOrNull;
  return prefs == null ? null : LanternSeenStore(prefs);
});
