/// NoorFace — the drawn six-state crescent face (جولة الحرفة, item 4).
///
/// Pins:
///   1. Every state paints without exceptions in both palettes — a drawn
///      face must never take a screen down over a bad path.
///   2. The blink/breath cycle runs normally, and rests (never animates)
///      under `MediaQuery.disableAnimations` — the CI journeys run with
///      animations disabled and a looping face would hang them.
///   3. [NoorPresence] adopts the drawn face at small sizes and keeps the
///      illustration art at hero sizes.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/companion/widgets/noor_face.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';

Widget _host(Widget child, {AppPalette? palette, bool? disableAnimations}) {
  final p = palette ?? AppPalette.light;
  return MaterialApp(
    theme: ThemeData(brightness: p.brightness, extensions: [AppColors(p)]),
    home: Scaffold(
      body: Center(
        child: disableAnimations == null
            ? child
            : MediaQuery(
                data: MediaQueryData(disableAnimations: disableAnimations),
                child: child,
              ),
      ),
    ),
  );
}

void main() {
  for (final state in NoorFaceState.values) {
    testWidgets('$state paints in the light palette', (tester) async {
      await tester.pumpWidget(_host(NoorFace(size: 56, state: state)));
      await tester.pump(const Duration(milliseconds: 200));
      expect(tester.takeException(), isNull);
    });

    testWidgets('$state paints in the dark palette', (tester) async {
      await tester.pumpWidget(
        _host(NoorFace(size: 56, state: state), palette: AppPalette.dark),
      );
      await tester.pump(const Duration(milliseconds: 200));
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('the blink/breath cycle runs when motion is allowed', (
    tester,
  ) async {
    await tester.pumpWidget(_host(const NoorFace(size: 56)));
    await tester.pump(const Duration(milliseconds: 100));
    final state = tester.state<NoorFaceWidgetState>(find.byType(NoorFace));
    expect(state.cycling, isTrue);
  });

  testWidgets('the cycle rests under disableAnimations', (tester) async {
    await tester.pumpWidget(
      _host(const NoorFace(size: 56), disableAnimations: true),
    );
    await tester.pump(const Duration(milliseconds: 100));
    final state = tester.state<NoorFaceWidgetState>(find.byType(NoorFace));
    expect(
      state.cycling,
      isFalse,
      reason:
          'a looping face under remove-animations is flicker at 20× — '
          'and it hangs the CI journeys',
    );
  });

  testWidgets('the cycle rests when TickerMode is disabled', (tester) async {
    final enabled = ValueNotifier<bool>(true);
    addTearDown(enabled.dispose);

    await tester.pumpWidget(
      ValueListenableBuilder<bool>(
        valueListenable: enabled,
        builder: (context, value, _) => _host(
          TickerMode(
            enabled: value,
            child: const NoorFace(size: 56),
          ),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    final state = tester.state<NoorFaceWidgetState>(find.byType(NoorFace));
    expect(state.cycling, isTrue);

    // Disable TickerMode (e.g. switching tab in RootScaffold)
    enabled.value = false;
    await tester.pump();
    expect(
      state.cycling,
      isFalse,
      reason: 'a background tab must mute its tickers and save battery',
    );

    // Re-enable TickerMode (switching back to the tab)
    enabled.value = true;
    await tester.pump();
    expect(state.cycling, isTrue);
  });

  testWidgets('the cycle stops when the tab changes in an IndexedStack', (
    tester,
  ) async {
    int tab = 0;
    late StateSetter setTab;

    await tester.pumpWidget(
      StatefulBuilder(
        builder: (context, setState) {
          setTab = setState;
          return _host(
            IndexedStack(
              index: tab,
              children: [
                TickerMode(
                  enabled: tab == 0,
                  child: const NoorFace(size: 56),
                ),
                TickerMode(
                  enabled: tab == 1,
                  child: const SizedBox(),
                ),
              ],
            ),
          );
        },
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    final state = tester.state<NoorFaceWidgetState>(find.byType(NoorFace));
    expect(state.cycling, isTrue);

    // Switch away to tab 1
    setTab(() => tab = 1);
    await tester.pump();
    expect(state.cycling, isFalse, reason: 'hidden tab must stop cycling');

    // Switch back to tab 0
    setTab(() => tab = 0);
    await tester.pump();
    expect(state.cycling, isTrue, reason: 'active tab resumes cycling');
  });

  testWidgets('a semantic label is exposed when given', (tester) async {
    await tester.pumpWidget(
      _host(const NoorFace(size: 56, semanticLabel: 'نور')),
    );
    expect(find.bySemanticsLabel('نور'), findsOneWidget);
  });

  group('NoorPresence adopts the drawn face at small sizes', () {
    testWidgets('44 dp window shows NoorFace, not an asset', (tester) async {
      await tester.pumpWidget(_host(const NoorPresence(size: 44)));
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.byType(NoorFace), findsOneWidget);
      expect(find.byType(Image), findsNothing);
    });

    testWidgets('96 dp hero window keeps the illustration', (tester) async {
      await tester.pumpWidget(_host(const NoorPresence(size: 96)));
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.byType(NoorFace), findsNothing);
      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('proud maps to the happy face', (tester) async {
      await tester.pumpWidget(
        _host(const NoorPresence(size: 44, mood: NoorMood.proud)),
      );
      await tester.pump(const Duration(milliseconds: 200));
      // The happy face cycles too — presence halo and face both breathe.
      expect(find.byType(NoorFace), findsOneWidget);
    });
  });
}
