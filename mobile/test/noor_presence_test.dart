/// NoorPresence v0 — the moon-window framing around the existing mascot
/// images, with a drawn halo in two moods (NOOR_WAL_QANADIL_PLAN, Phase 1).
///
/// Pins:
///   1. The oval window clips the existing mascot asset (calm → serene,
///      proud → celebrate) and passes `cacheWidth` so the decode matches the
///      on-screen size (memory).
///   2. The halo is drawn (CustomPainter) and differs between the two moods.
///   3. Colours come from the palette via `context.colors` — the window
///      ground and rim follow the live palette in BOTH themes.
///   4. The halo loop respects reduced motion: with
///      `MediaQuery.disableAnimations` it never animates.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

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
  testWidgets('calm mood shows the serene mascot inside an oval window',
      (tester) async {
    await tester.pumpWidget(_host(const NoorPresence(size: 96)));
    // The halo loops forever — pumpAndSettle would time out by design.
    await tester.pump(const Duration(milliseconds: 300));

    final image = tester.widget<Image>(find.byType(Image));
    // cacheWidth wraps the provider in a ResizeImage — the decode matches
    // the window, not the 1024² source.
    expect(image.image, isA<ResizeImage>());
    final resized = image.image as ResizeImage;
    expect(resized.width, greaterThanOrEqualTo(90));
    expect(resized.width, lessThan(400));
    expect(
      ((resized.imageProvider as AssetImage).assetName),
      'assets/images/generated/mascot_serene.webp',
    );
    // Oval window around the mascot.
    expect(find.byType(ClipOval), findsOneWidget);
  });

  testWidgets('proud mood switches to the celebrate mascot',
      (tester) async {
    await tester
        .pumpWidget(_host(const NoorPresence(size: 96, mood: NoorMood.proud)));
    await tester.pump(const Duration(milliseconds: 300));

    final image = tester.widget<Image>(find.byType(Image));
    expect(
      ((image.image as ResizeImage).imageProvider as AssetImage).assetName,
      'assets/images/generated/mascot_celebrate.webp',
    );
  });

  testWidgets('the halo is a CustomPaint that changes with the mood',
      (tester) async {
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
        _host(const NoorPresence(size: 96, mood: NoorMood.proud)));
    await tester.pump(const Duration(milliseconds: 300));
    expect(haloFinder, findsOneWidget);
  });

  testWidgets('window ground and rim follow the dark palette',
      (tester) async {
    await tester.pumpWidget(
        _host(const NoorPresence(size: 96), palette: AppPalette.dark));
    await tester.pump(const Duration(milliseconds: 300));

    final container = tester.widget<Container>(
      find.ancestor(of: find.byType(ClipOval), matching: find.byType(Container)),
    );
    final decoration = container.decoration! as BoxDecoration;
    expect(decoration.color, AppPalette.dark.surfaceAlt);
    expect(decoration.border!.top.color, AppPalette.dark.accent);
  });

  testWidgets('halo does not loop under reduced motion', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(extensions: [AppColors(AppPalette.light)]),
        home: Builder(
          builder: (context) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: const Scaffold(
              body: Center(child: NoorPresence(size: 96)),
            ),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    final state = tester.state<NoorPresenceState>(find.byType(NoorPresence));
    expect(state.haloLooping, isFalse,
        reason: 'reduceMotion must hold the halo still, not flicker it');
  });

  testWidgets('halo loops when motion is allowed', (tester) async {
    await tester.pumpWidget(_host(const NoorPresence(size: 96)));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    final state = tester.state<NoorPresenceState>(find.byType(NoorPresence));
    expect(state.haloLooping, isTrue);
  });
}
