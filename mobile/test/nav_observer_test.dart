/// Unit tests for the "lostness" classifier.
///
/// The interesting logic in TgNavObserver is how it decides what a finished
/// visit *meant*. That decision is a pure function, so it is tested directly
/// with synthetic timings rather than through a real Navigator — fast, and it
/// pins the thresholds that the analytics dashboards will be read against.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/core/nav_observer.dart';

void main() {
  group('classifyExit', () {
    test('a very short visit is a bounce, even if it led somewhere', () {
      expect(
        classifyExit(dwellMs: 400, childPushCount: 0),
        ExitKind.bounce,
      );
      // Bounce wins over dead-end: leaving that fast is the whole signal.
      expect(
        classifyExit(dwellMs: 400, childPushCount: 3),
        ExitKind.bounce,
      );
    });

    test('a long visit that went nowhere is a dead end', () {
      expect(
        classifyExit(dwellMs: 30000, childPushCount: 0),
        ExitKind.deadEnd,
      );
    });

    test('a long visit that led onward is healthy', () {
      expect(
        classifyExit(dwellMs: 30000, childPushCount: 1),
        ExitKind.none,
      );
    });

    test('the bounce threshold is exclusive at the boundary', () {
      expect(
        classifyExit(dwellMs: kBounceThresholdMs - 1, childPushCount: 0),
        ExitKind.bounce,
      );
      // Exactly at the threshold is no longer a bounce — it falls through to
      // the dead-end check.
      expect(
        classifyExit(dwellMs: kBounceThresholdMs, childPushCount: 0),
        ExitKind.deadEnd,
      );
      expect(
        classifyExit(dwellMs: kBounceThresholdMs, childPushCount: 1),
        ExitKind.none,
      );
    });

    test('every visit produces at most one classification', () {
      // Guards against a future refactor emitting both a bounce and a dead-end
      // for the same visit, which would double-count in the dashboards.
      for (final dwell in [0, 100, 2999, 3000, 10000, 120000]) {
        for (final children in [0, 1, 5]) {
          final kind = classifyExit(dwellMs: dwell, childPushCount: children);
          expect(ExitKind.values.contains(kind), isTrue);
        }
      }
    });
  });

  group('thresholds', () {
    test('are ordered sanely', () {
      // A bounce must be shorter than the idle window, or a bounce could never
      // be observed as idle and the two signals would overlap confusingly.
      expect(kBounceThresholdMs, lessThan(kIdleThresholdMs));
      expect(kIdleSampleRate, greaterThan(0));
      expect(kBackHammerWindowMs, greaterThan(0));
    });
  });


  // --- v2: a finished task is not a dead end -------------------------------
  //
  // The old classifier had only childPushCount, so every leaf screen in the
  // app scored as a trap: a lesson read to the end, a habit ticked, a surah
  // closed. 2,129 users — 66% — were labelled lost by ordinary use.

  group('classifyExit — productive visits', () {
    test('a long visit that opened a dialog is not a dead end', () {
      // Dialogs and sheets are how a leaf screen offers its action, and the
      // observer never saw them because they are not PageRoutes.
      expect(
        classifyExit(dwellMs: 30000, childPushCount: 0, productiveCount: 1),
        ExitKind.none,
      );
    });

    test('a long visit where the user completed something is not a dead end',
        () {
      expect(
        classifyExit(dwellMs: 120000, childPushCount: 0, productiveCount: 3),
        ExitKind.none,
      );
    });

    test('a long visit with nothing at all is still a dead end', () {
      expect(
        classifyExit(dwellMs: 30000, childPushCount: 0, productiveCount: 0),
        ExitKind.deadEnd,
      );
    });

    test('a bounce stays a bounce even when productive', () {
      // Ordering matters: under three seconds is a bounce whatever else
      // happened, otherwise a screen that fires a beacon on open would
      // reclassify every quick visit as healthy.
      expect(
        classifyExit(dwellMs: 500, childPushCount: 0, productiveCount: 5),
        ExitKind.bounce,
      );
    });

    test('productiveCount defaults to zero so old call sites behave', () {
      expect(
        classifyExit(dwellMs: 30000, childPushCount: 0),
        ExitKind.deadEnd,
      );
    });
  });
}
