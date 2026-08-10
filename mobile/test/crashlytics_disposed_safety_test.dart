// Regression test for the Crashlytics crash caused by stale/disposed state.
//
// A `Future.delayed` inside each star could call `_controller.repeat()` after
// the controller was disposed, when the screen was popped before the star's
// stagger elapsed. It had to be fixed twice, because the bedtime routine and
// the story bookshelf each carried a byte-identical copy of the class.
//
// The original version of this test re-implemented the star in the test file,
// since neither screen could be mounted without audio and l10n mocks. Now that
// the widget lives in lib/widgets/ui/night_sky.dart it can be mounted directly,
// so this exercises the code that actually ships.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/widgets/ui/night_sky.dart';

void main() {
  group('TwinklingStars dispose safety', () {
    testWidgets('disposing before the staggered start fires does not throw',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: TwinklingStars(count: 12)),
      ));

      // Pop while every star is still waiting out its delay (up to 3s).
      await tester.pump(const Duration(milliseconds: 10));
      await tester.pumpWidget(const SizedBox.shrink());

      // Let the delayed callbacks fire after dispose — none may throw.
      await tester.pump(const Duration(seconds: 4));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
    });

    testWidgets('stars keep animating when the screen stays mounted',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: TwinklingStars(count: 8)),
      ));
      await tester.pump(const Duration(seconds: 4));

      expect(tester.takeException(), isNull);
      // Scoped to the widget: MaterialApp contributes its own FadeTransitions
      // for route animations.
      expect(
        find.descendant(
          of: find.byType(TwinklingStars),
          matching: find.byType(FadeTransition),
        ),
        findsNWidgets(8),
      );

      // Unmount cleanly so the test does not leak tickers.
      await tester.pumpWidget(const SizedBox.shrink());
    });
  });

  group('FloatingFireflies', () {
    testWidgets('mounts and disposes without leaking a ticker', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: FloatingFireflies(count: 6)),
      ));
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
    });
  });
}
