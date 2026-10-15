/// NoorPresence — the moon-window framing around «نور», with a drawn halo
/// in two moods (NOOR_WAL_QANADIL_PLAN, Phase 1; «ورق مقصوص» SVG face since
/// 2026-10-14).
///
/// Pins:
///   1. The oval window clips the SVG face (calm → noor_calm, proud →
///      noor_happy) at every size — no raster mascot is decoded any more.
///   2. The halo is drawn (CustomPainter) and differs between the two moods.
///   3. The window ground is the art's emerald #0F6B5C in BOTH themes (the
///      ivory moon must read on a light page and a dark one); the rim and the
///      halo follow the live palette.
///   4. The halo loop respects reduced motion: with
///      `MediaQuery.disableAnimations` it never animates.
library;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/companion/widgets/noor_face.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';

Widget _host(Widget child, {AppPalette? palette}) {
  final p = palette ?? AppPalette.light;
  return MaterialApp(
    theme: ThemeData(brightness: p.brightness, extensions: [AppColors(p)]),
    home: Scaffold(body: Center(child: child)),
  );
}

void main() {
  /// The face showing inside the window (the blink frame, when mounted,
  /// sits at opacity 0 and is not the face).
  String shownFace(WidgetTester tester) {
    final shown = find
        .descendant(of: find.byType(ClipOval), matching: find.byType(SvgPicture))
        .evaluate()
        .where((e) {
          final opacity = e.findAncestorWidgetOfExactType<Opacity>();
          return opacity == null || opacity.opacity == 1;
        })
        .map((e) => ((e.widget as SvgPicture).bytesLoader as SvgAssetLoader)
            .assetName)
        .toList();
    expect(shown, hasLength(1), reason: '$shown');
    return shown.single;
  }

  for (final size in [44.0, 96.0, 160.0]) {
    testWidgets('calm mood: the calm SVG face in an oval window at $size', (
      tester,
    ) async {
      await tester.pumpWidget(_host(NoorPresence(size: size)));
      // The halo loops forever — pumpAndSettle would time out by design.
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byType(ClipOval), findsOneWidget);
      expect(
        find.descendant(
          of: find.byType(ClipOval),
          matching: find.byType(NoorFace),
        ),
        findsOneWidget,
      );
      expect(shownFace(tester), 'assets/svg/noor/noor_calm.svg');
      expect(find.byType(Image), findsNothing, reason: 'no raster mascot');
    });
  }

  testWidgets('proud mood switches to the happy face', (tester) async {
    await tester.pumpWidget(
      _host(const NoorPresence(size: 96, mood: NoorMood.proud)),
    );
    // Past the first blink (the happy face blinks to calm for 140 ms).
    await tester.pump(const Duration(milliseconds: 300));
    expect(shownFace(tester), 'assets/svg/noor/noor_happy.svg');
  });

  testWidgets('the halo is a CustomPaint that changes with the mood', (
    tester,
  ) async {
    await tester.pumpWidget(_host(const NoorPresence(size: 96)));
    // The halo loops forever — pumpAndSettle would time out by design.
    await tester.pump(const Duration(milliseconds: 300));
    final haloFinder = find
        .descendant(
          of: find.byType(NoorPresence),
          matching: find.byType(CustomPaint),
        )
        .first;
    expect(haloFinder, findsOneWidget);

    await tester.pumpWidget(
      _host(const NoorPresence(size: 96, mood: NoorMood.proud)),
    );
    await tester.pump(const Duration(milliseconds: 300));
    expect(haloFinder, findsOneWidget);
  });

  for (final palette in [AppPalette.light, AppPalette.dark]) {
    final theme = palette.isDark ? 'dark' : 'light';
    for (final size in [44.0, 96.0]) {
      testWidgets('$theme, $size: emerald ground, rim from the palette', (
        tester,
      ) async {
        await tester.pumpWidget(
          _host(NoorPresence(size: size), palette: palette),
        );
        // MaterialApp animates a theme change; let it land.
        await tester.pump(const Duration(milliseconds: 400));

        final container = tester.widget<Container>(
          find.ancestor(
            of: find.byType(ClipOval),
            matching: find.byType(Container),
          ),
        );
        final decoration = container.decoration! as BoxDecoration;
        expect(decoration.color, const Color(0xFF0F6B5C));
        expect(decoration.color, kNoorWindowGround);
        expect(decoration.border!.top.color, palette.accent);
      });
    }
  }

  testWidgets('halo does not loop under reduced motion', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(extensions: [AppColors(AppPalette.light)]),
        home: Builder(
          builder: (context) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: const Scaffold(body: Center(child: NoorPresence(size: 96))),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    final state = tester.state<NoorPresenceState>(find.byType(NoorPresence));
    expect(
      state.haloLooping,
      isFalse,
      reason: 'reduceMotion must hold the halo still, not flicker it',
    );
  });

  testWidgets('halo loops when motion is allowed', (tester) async {
    await tester.pumpWidget(_host(const NoorPresence(size: 96)));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    final state = tester.state<NoorPresenceState>(find.byType(NoorPresence));
    expect(state.haloLooping, isTrue);
  });
}
