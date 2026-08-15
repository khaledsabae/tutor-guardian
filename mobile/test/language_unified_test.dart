// One language, not two.
//
// The app used to carry two switches: `appLocaleProvider` for the interface and
// curriculum text, and a separate `content_language` preference for media. They
// could disagree, and they did — a parent on an English phone read English
// lessons and was handed the Arabic podcast, because the media switch defaulted
// to a hard-coded 'ar' and never asked what language they were reading in.
//
// These tests exist so the second switch cannot come back.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/lesson_assets_provider.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('media language follows the app language', () async {
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(overrides: [
      sharedPreferencesProvider.overrideWith((ref) async => prefs),
    ]);
    addTearDown(container.dispose);

    container.read(appLocaleProvider.notifier).setLocale('en');
    expect(container.read(contentLanguageProvider), 'en');

    container.read(appLocaleProvider.notifier).setLocale('ar');
    expect(container.read(contentLanguageProvider), 'ar');
  });

  test('a stored content_language cannot override the app language', () async {
    // Existing installs still carry this key from the old second switch. It
    // must not resurrect the disagreement.
    SharedPreferences.setMockInitialValues({'content_language': 'ar'});
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(overrides: [
      sharedPreferencesProvider.overrideWith((ref) async => prefs),
    ]);
    addTearDown(container.dispose);

    container.read(appLocaleProvider.notifier).setLocale('en');
    expect(container.read(contentLanguageProvider), 'en',
        reason: 'the stale media preference must be ignored, not obeyed');
  });

  test('an unsupported locale falls back to Arabic rather than to itself', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container.read(appLocaleProvider.notifier).setLocale('fr');
    expect(container.read(contentLanguageProvider), 'ar',
        reason: 'French has no media; asking for it would 404 every asset');
  });
}
