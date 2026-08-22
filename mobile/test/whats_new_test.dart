/// The two ways a "what's new" card goes wrong, stated as tests.
///
///  1. It greets a brand-new user with a list of changes they have no "before"
///     for. That is the one this feature most easily gets wrong, because on the
///     first release carrying it every device has no stored build — a user of
///     two months and someone who installed a minute ago are indistinguishable
///     unless something else separates them.
///  2. It comes back. A card that reappears on the next launch is worse than no
///     card, because dismissing it stops meaning anything.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/whats_new/data/whats_new.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

const _noted = 102; // must stay a member of kWhatsNewBuilds

Future<WhatsNewStore> storeWith(Map<String, Object> seed) async {
  SharedPreferences.setMockInitialValues(seed);
  return WhatsNewStore(await SharedPreferences.getInstance());
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('the build under test is actually a noted one', () {
    // Guard the premise: if 102 drops out of the list, every "shows" case
    // below would pass for the wrong reason.
    expect(kWhatsNewBuilds, contains(_noted));
    expect(latestNotedBuild, kWhatsNewBuilds.first);
  });

  group('a fresh install', () {
    test('is not shown the card', () async {
      final s = await storeWith({});
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: false),
        isFalse,
      );
    });

    test('has its build recorded silently, so the next update is its first card',
        () async {
      final s = await storeWith({});
      expect(s.lastSeenBuild, isNull);
      await s.seedForFreshInstall(_noted);
      expect(s.lastSeenBuild, _noted);
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: true),
        isFalse,
        reason: 'seeding must not leave the card armed for this same build',
      );
    });

    test('seeding never overwrites a build the user already dismissed',
        () async {
      final s = await storeWith({WhatsNewStore.kLastSeenBuild: 99});
      await s.seedForFreshInstall(_noted);
      expect(s.lastSeenBuild, 99);
    });
  });

  group('an existing user who just updated', () {
    test('is shown the card', () async {
      final s = await storeWith({});
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: true),
        isTrue,
      );
    });

    test('is not shown it again after dismissing', () async {
      final s = await storeWith({});
      await s.markSeen(_noted);
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: true),
        isFalse,
      );
    });

    test('a dismissal on a newer build suppresses an older one', () async {
      final s = await storeWith({WhatsNewStore.kLastSeenBuild: 200});
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: true),
        isFalse,
      );
    });

    test('a dismissal on an older build does not suppress this one', () async {
      final s = await storeWith({WhatsNewStore.kLastSeenBuild: 99});
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: true),
        isTrue,
      );
    });
  });

  test('a build with no notes shows nothing', () async {
    final s = await storeWith({});
    final unnoted = _noted + 1;
    expect(kWhatsNewBuilds.contains(unnoted), isFalse);
    expect(
      s.shouldShow(currentBuild: unnoted, onboardingCompleted: true),
      isFalse,
    );
  });

  group('the startup seed', () {
    test('silences the card for a device that never onboarded', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      await seedWhatsNewForFreshInstall(prefs, _noted);
      final s = WhatsNewStore(prefs);
      expect(s.lastSeenBuild, _noted);
      // And stays silenced once they finish onboarding on this same build.
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: true),
        isFalse,
      );
    });

    test('leaves an upgrading user alone', () async {
      // This is the regression that the first version of this feature had: the
      // seed sat in the card, which only builds after onboarding is complete —
      // so it could never distinguish the two cases and a fresh install saw
      // the card. Running at startup, an onboarded device is untouched.
      SharedPreferences.setMockInitialValues(
          {OnboardingStorage.keyOnboardingCompleted: true});
      final prefs = await SharedPreferences.getInstance();
      await seedWhatsNewForFreshInstall(prefs, _noted);
      final s = WhatsNewStore(prefs);
      expect(s.lastSeenBuild, isNull, reason: 'the seed must not fire here');
      expect(
        s.shouldShow(currentBuild: _noted, onboardingCompleted: true),
        isTrue,
      );
    });
  });

  test('the onboarding key is the one the app actually writes', () async {
    // This store reads a key owned by another feature. If onboarding renames
    // it, every existing user silently becomes a "fresh install" and the card
    // stops appearing for anyone — a failure with no error and no crash.
    SharedPreferences.setMockInitialValues(
        {OnboardingStorage.keyOnboardingCompleted: true});
    final prefs = await SharedPreferences.getInstance();
    expect(onboardingCompletedFrom(prefs), isTrue);
    expect(OnboardingStorage.keyOnboardingCompleted, 'tg.onboarding.completed');
  });

  test('every bullet is translated in both languages', () async {
    final ar = await AppLocalizations.delegate.load(const Locale('ar'));
    final en = await AppLocalizations.delegate.load(const Locale('en'));
    final arLines = [
      ar.whatsNewTitle, ar.whatsNew102Tafsir, ar.whatsNew102Adhkar,
      ar.whatsNew102Wird, ar.whatsNew102Timing,
    ];
    final enLines = [
      en.whatsNewTitle, en.whatsNew102Tafsir, en.whatsNew102Adhkar,
      en.whatsNew102Wird, en.whatsNew102Timing,
    ];
    for (var i = 0; i < arLines.length; i++) {
      expect(arLines[i].trim(), isNotEmpty);
      expect(enLines[i].trim(), isNotEmpty);
      expect(enLines[i], isNot(arLines[i]), reason: 'line $i not translated');
    }
  });
}
