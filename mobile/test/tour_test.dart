/// Invariants for the first-run guided tour.
///
/// The load-bearing one is the first group: the tour is a full-screen veil
/// that swallows taps, so if it ever ran under `flutter test` it would break
/// every widget test that touches the nav bar — starting with
/// `program_widget_test.dart`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/tour/tour_controller.dart';
import 'package:almorabbi/features/tour/tour_step.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

void main() {
  group('test guard', () {
    test('the tour is suppressed under FLUTTER_TEST', () {
      expect(kTourEnabled, isFalse,
          reason: 'a live veil would eat taps in every widget test');
    });
  });

  group('OnboardingStorage.tourVersion', () {
    late OnboardingStorage storage;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      storage = OnboardingStorage(await SharedPreferences.getInstance());
    });

    test('starts at 0 and records the version it was shown at', () async {
      expect(storage.tourVersion, 0);
      await storage.markTourSeen(kTourVersion);
      expect(storage.tourVersion, kTourVersion);
    });

    test('rewinds to 0 so settings can replay it', () async {
      await storage.markTourSeen(kTourVersion);
      await storage.markTourSeen(0);
      expect(storage.tourVersion, 0);
      expect(storage.tourVersion < kTourVersion, isTrue);
    });

    test('is an int, not a bool — a later version can re-trigger', () async {
      await storage.markTourSeen(1);
      expect(storage.tourVersion < 2, isTrue,
          reason: 'bumping kTourVersion must re-arm the tour');
    });
  });

  group('steps', () {
    final tabKeys = List.generate(4, (_) => GlobalKey());
    final focusKey = GlobalKey();
    final steps = buildTourSteps(tabKeys: tabKeys, focusKey: focusKey);

    // Both shipped locales: a key can exist in Arabic and be missing in
    // English, and the tour is the first thing a new user sees.
    final locales = {
      'ar': lookupAppLocalizations(const Locale('ar')),
      'en': lookupAppLocalizations(const Locale('en')),
    };

    test('there are five stops, in nav order then the focus card', () {
      expect(steps.length, 5);
      for (var i = 0; i < 4; i++) {
        expect(steps[i].key, same(tabKeys[i]),
            reason: 'step $i must point at destination $i');
      }
      expect(steps.last.key, same(focusKey));
    });

    test('every target key is distinct', () {
      expect(steps.map((s) => s.key).toSet().length, steps.length);
    });

    test('every caption and title resolves in every locale', () {
      for (final entry in locales.entries) {
        for (var i = 0; i < steps.length; i++) {
          expect(steps[i].caption(entry.value), isNotEmpty,
              reason: 'step $i has no ${entry.key} caption');
          expect(steps[i].title!(entry.value), isNotEmpty,
              reason: 'step $i has no ${entry.key} title');
        }
      }
    });

    test('the action labels resolve in every locale', () {
      for (final l in locales.values) {
        expect(l.tourNext, isNotEmpty);
        expect(l.tourSkip, isNotEmpty);
        expect(l.tourDone, isNotEmpty);
        expect(l.tourReplay, isNotEmpty);
      }
    });
  });

  // The tour never runs under FLUTTER_TEST, so the overlay's geometry is
  // otherwise untested. This exercises the one thing it depends on: that a
  // GlobalKey on a KeyedSubtree wrapping a NavigationDestination measures that
  // destination's own slot, and that RTL mirroring comes for free from the
  // framework's layout rather than from index arithmetic we'd have to write.
  group('destination measurement', () {
    Future<List<Rect>> layOut(WidgetTester tester, TextDirection dir) async {
      final keys = List.generate(4, (_) => GlobalKey());
      await tester.pumpWidget(MaterialApp(
        home: Directionality(
          textDirection: dir,
          child: Scaffold(
            bottomNavigationBar: NavigationBar(
              selectedIndex: 0,
              destinations: [
                for (var i = 0; i < 4; i++)
                  KeyedSubtree(
                    key: keys[i],
                    child: NavigationDestination(
                      icon: const Icon(Icons.home),
                      label: 'tab$i',
                    ),
                  ),
              ],
            ),
          ),
        ),
      ));
      await tester.pumpAndSettle();
      return keys.map((k) {
        final box = k.currentContext!.findRenderObject() as RenderBox;
        return box.localToGlobal(Offset.zero) & box.size;
      }).toList();
    }

    testWidgets('each key measures one whole, distinct destination',
        (tester) async {
      final rects = await layOut(tester, TextDirection.ltr);
      expect(rects.toSet().length, 4, reason: 'rects must not overlap');
      final width = tester.view.physicalSize.width / tester.view.devicePixelRatio;
      for (final r in rects) {
        expect(r.width, closeTo(width / 4, 0.5));
        expect(r.height, greaterThan(0));
      }
    });

    testWidgets('RTL mirrors the destinations without any index flipping',
        (tester) async {
      final rtl = await layOut(tester, TextDirection.rtl);
      final ltr = await layOut(tester, TextDirection.ltr);
      // Destination 0 is on the right in RTL and on the left in LTR — read
      // straight off localToGlobal, with no direction-aware maths anywhere.
      expect(rtl.first.center.dx, greaterThan(rtl.last.center.dx));
      expect(ltr.first.center.dx, lessThan(ltr.last.center.dx));
      // ...and it is a true mirror, not merely reversed.
      for (var i = 0; i < 4; i++) {
        expect(rtl[i].center.dx, closeTo(ltr[3 - i].center.dx, 0.5));
      }
    });
  });

  group('TourController', () {
    test('walks every step, then reports the end exactly once', () {
      final c = TourController();
      expect(c.state.active, isFalse);

      c.start(5);
      expect(c.state.active, isTrue);
      expect(c.state.index, 0);
      expect(c.state.isLast, isFalse);

      for (var i = 0; i < 4; i++) {
        expect(c.next(), isFalse, reason: 'step $i is not the end');
        expect(c.state.index, i + 1);
      }

      expect(c.state.isLast, isTrue);
      expect(c.next(), isTrue, reason: 'the fifth "next" completes the tour');
      expect(c.state.active, isFalse);
      // Idempotent: a stray tap after the last one must not re-report.
      expect(c.next(), isFalse);
    });

    test('stop() ends the tour wherever it is', () {
      final c = TourController()..start(5);
      c.next();
      c.stop();
      expect(c.state.active, isFalse);
      expect(c.next(), isFalse);
    });

    test('start() ignores an empty step list', () {
      final c = TourController()..start(0);
      expect(c.state.active, isFalse);
    });
  });
}
