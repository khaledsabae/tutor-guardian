/// NoorFace — the six-state «نور» face, «ورق مقصوص» SVG since 2026-10-14
/// (drawn in code before, جولة الحرفة item 4).
///
/// Pins:
///   1. Every state paints without exceptions in both palettes, and shows
///      its own SVG (night → the sleepy face).
///   2. The blink/breath cycle runs normally, and rests (never animates)
///      under `MediaQuery.disableAnimations` or a disabled TickerMode — the
///      CI journeys run with animations disabled and a looping face would
///      hang them; a background tab must not burn battery.
///   3. The blink is noor_calm shown over the open-eyed faces (awake, happy)
///      for ~140 ms per cycle — and never while resting.
///   4. The breath is a ~2% scale, nothing more.
///   5. [NoorPresence] shows the SVG face at every size — no raster left.
library;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
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

/// The asset each mounted [SvgPicture] under [of] draws, with the opacity of
/// the [Opacity] directly above it (1 when there is none).
Map<String, double> _pictures(WidgetTester tester, Finder of) {
  final result = <String, double>{};
  for (final element in find
      .descendant(of: of, matching: find.byType(SvgPicture))
      .evaluate()) {
    final svg = element.widget as SvgPicture;
    final asset = (svg.bytesLoader as SvgAssetLoader).assetName;
    var opacity = 1.0;
    element.visitAncestorElements((ancestor) {
      if (ancestor.widget is Opacity) {
        opacity = (ancestor.widget as Opacity).opacity;
        return false;
      }
      return ancestor.widget is! NoorFace;
    });
    result[asset] = opacity;
  }
  return result;
}

double _scale(WidgetTester tester) {
  final transform = tester.widget<Transform>(
    find
        .descendant(of: find.byType(NoorFace), matching: find.byType(Transform))
        .first,
  );
  return transform.transform.getMaxScaleOnAxis();
}

void main() {
  test('each state names its own SVG; night is the sleepy face', () {
    expect({for (final s in NoorFaceState.values) s: noorFaceAsset(s)}, {
      NoorFaceState.calm: 'assets/svg/noor/noor_calm.svg',
      NoorFaceState.awake: 'assets/svg/noor/noor_awake.svg',
      NoorFaceState.happy: 'assets/svg/noor/noor_happy.svg',
      NoorFaceState.thinking: 'assets/svg/noor/noor_thinking.svg',
      NoorFaceState.night: 'assets/svg/noor/noor_sleepy.svg',
      NoorFaceState.tender: 'assets/svg/noor/noor_tender.svg',
    });
  });

  for (final state in NoorFaceState.values) {
    testWidgets('$state paints in the light palette', (tester) async {
      await tester.pumpWidget(_host(NoorFace(size: 56, state: state)));
      await tester.pump(const Duration(milliseconds: 200));
      expect(tester.takeException(), isNull);
      // Its own face is the one showing (the closed-eye frame, if mounted
      // for blinking, waits at opacity 0).
      expect(_pictures(tester, find.byType(NoorFace))[noorFaceAsset(state)], 1);
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

  group('the blink: noor_calm over an open-eyed face', () {
    for (final state in [NoorFaceState.awake, NoorFaceState.happy]) {
      testWidgets('$state blinks at the top of the cycle, then opens', (
        tester,
      ) async {
        await tester.pumpWidget(_host(NoorFace(size: 56, state: state)));
        // The loop starts at 0: the first 140 ms are the blink.
        await tester.pump(const Duration(milliseconds: 60));
        final face = tester.state<NoorFaceWidgetState>(find.byType(NoorFace));
        expect(face.blinking, isTrue);
        expect(_pictures(tester, find.byType(NoorFace)), {
          noorFaceAsset(state): 0,
          'assets/svg/noor/noor_calm.svg': 1,
        });

        await tester.pump(const Duration(milliseconds: 200));
        expect(face.blinking, isFalse);
        expect(_pictures(tester, find.byType(NoorFace)), {
          noorFaceAsset(state): 1,
          'assets/svg/noor/noor_calm.svg': 0,
        });

        // …and again on the next pass.
        await tester.pump(const Duration(milliseconds: 3800));
        expect(face.blinking, isTrue);
      });

      testWidgets('$state never rests mid-blink under disableAnimations', (
        tester,
      ) async {
        await tester.pumpWidget(
          _host(NoorFace(size: 56, state: state), disableAnimations: true),
        );
        for (var i = 0; i < 5; i++) {
          await tester.pump(const Duration(milliseconds: 900));
          final face = tester.state<NoorFaceWidgetState>(
            find.byType(NoorFace),
          );
          expect(face.blinking, isFalse);
          expect(_pictures(tester, find.byType(NoorFace))[noorFaceAsset(state)],
              1);
        }
      });
    }

    for (final state in [
      NoorFaceState.calm,
      NoorFaceState.thinking,
      NoorFaceState.night,
      NoorFaceState.tender,
    ]) {
      testWidgets('$state has no blink frame at all', (tester) async {
        await tester.pumpWidget(_host(NoorFace(size: 56, state: state)));
        await tester.pump(const Duration(milliseconds: 60));
        expect(_pictures(tester, find.byType(NoorFace)), {
          noorFaceAsset(state): 1,
        });
      });
    }
  });

  testWidgets('the breath is a ~2% scale, resting still when reduced', (
    tester,
  ) async {
    await tester.pumpWidget(_host(const NoorFace(size: 56)));
    var low = double.infinity, high = 0.0;
    for (var t = 0; t < 4000; t += 100) {
      await tester.pump(const Duration(milliseconds: 100));
      final scale = _scale(tester);
      low = scale < low ? scale : low;
      high = scale > high ? scale : high;
    }
    expect(low, closeTo(1.0, .003));
    expect(high, closeTo(1.02, .003));

    await tester.pumpWidget(
      _host(const NoorFace(size: 56), disableAnimations: true),
    );
    await tester.pump();
    final rest = _scale(tester);
    await tester.pump(const Duration(seconds: 1));
    expect(_scale(tester), rest, reason: 'reduced motion: no breathing');
  });

  group('NoorPresence shows the SVG face at every size', () {
    testWidgets('44 dp window shows NoorFace, not an asset', (tester) async {
      await tester.pumpWidget(_host(const NoorPresence(size: 44)));
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.byType(NoorFace), findsOneWidget);
      expect(find.byType(Image), findsNothing);
    });

    testWidgets('a 96 dp hero window is the SVG face too — no raster', (
      tester,
    ) async {
      await tester.pumpWidget(_host(const NoorPresence(size: 96)));
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.byType(NoorFace), findsOneWidget);
      expect(find.byType(Image), findsNothing);
    });

    testWidgets('the face state passes through to the window', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(const NoorPresence(size: 56, face: NoorFaceState.night)),
      );
      await tester.pump(const Duration(milliseconds: 200));
      expect(
        tester.widget<NoorFace>(find.byType(NoorFace)).state,
        NoorFaceState.night,
      );
    });

    testWidgets('proud maps to the happy face', (tester) async {
      await tester.pumpWidget(
        _host(const NoorPresence(size: 44, mood: NoorMood.proud)),
      );
      await tester.pump(const Duration(milliseconds: 200));
      // The happy face cycles too — presence halo and face both breathe.
      expect(find.byType(NoorFace), findsOneWidget);
      expect(
        tester.widget<NoorFace>(find.byType(NoorFace)).state,
        NoorFaceState.happy,
      );
    });
  });
}
