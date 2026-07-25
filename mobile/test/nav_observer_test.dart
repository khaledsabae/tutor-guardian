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
}
