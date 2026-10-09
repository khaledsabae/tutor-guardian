/// «مستويات الاحتفال» — the one celebration API has two volumes, and both
/// respect the system's reduce-motion setting.
///
/// Pinned here:
///   · milestone (the default, so existing call sites keep their confetti)
///     shows confetti + Lottie stars;
///   · quiet shows the same dialog with neither;
///   · reduce-motion drops the effects even for milestone — the dialog is
///     information, the confetti is decoration;
///   · a badge rides inside the dialog instead of a second silent window.
library;

import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lottie/lottie.dart';

import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/widgets/ui/celebration_overlay.dart';

Future<void> _pump(
  WidgetTester tester, {
  bool disableAnimations = false,
  CelebrationTier tier = CelebrationTier.milestone,
  CelebrationBadge? badge,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context)
            .copyWith(disableAnimations: disableAnimations),
        child: child!,
      ),
      home: Scaffold(
        body: Builder(
          builder: (context) => Center(
            child: TextButton(
              onPressed: () => showCelebration(
                context,
                emoji: '🎉',
                title: 'title',
                message: 'message',
                tier: tier,
                badge: badge,
              ),
              child: const Text('fire'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('fire'));
  // One frame for the route, one for the entrance — the confetti ticker
  // never settles, so no pumpAndSettle. The Lottie asset loads through a
  // future, so give it a couple of frames.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 200));
  await tester.pump(const Duration(milliseconds: 200));
}

void main() {
  testWidgets('milestone (default) keeps confetti and stars', (tester) async {
    await _pump(tester);
    expect(find.text('title'), findsOneWidget);
    expect(find.byType(ConfettiWidget), findsOneWidget);
    expect(find.byType(LottieBuilder), findsOneWidget);
  });

  testWidgets('quiet shows the dialog without confetti or stars',
      (tester) async {
    await _pump(tester, tier: CelebrationTier.quiet);
    expect(find.text('title'), findsOneWidget);
    expect(find.text('message'), findsOneWidget);
    expect(find.byType(ConfettiWidget), findsNothing);
    expect(find.byType(LottieBuilder), findsNothing);
  });

  testWidgets('reduce motion drops the effects, keeps the dialog',
      (tester) async {
    await _pump(tester, disableAnimations: true);
    expect(find.text('title'), findsOneWidget);
    expect(find.byType(ConfettiWidget), findsNothing);
    expect(find.byType(LottieBuilder), findsNothing);
  });

  testWidgets('a badge rides inside the dialog', (tester) async {
    await _pump(
      tester,
      tier: CelebrationTier.quiet,
      badge: const (emoji: '🌱', title: 'أول خطوة'),
    );
    expect(find.text('أول خطوة'), findsOneWidget);
    expect(find.text('🌱'), findsOneWidget);
  });
}
