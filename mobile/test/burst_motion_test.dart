import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:almorabbi/features/missions/praise_header.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/widgets/ui/celebration_overlay.dart';

void main() {
  group('Burst motion across 0ms, 150ms, and 400ms phases', () {
    testWidgets(
      'praise sticker entrance interpolates scale from 0.6 to 1.0',
      (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            locale: const Locale('ar'),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: const Scaffold(
              body: PraiseHeader(
                note: 'أحسنت',
                display: PraiseDisplay.stickerAndText,
              ),
            ),
          ),
        );

        // Frame 0ms: entrance starts at begin (0.6)
        await tester.pump();
        final stickerTransformFinder = find.descendant(
          of: find.byType(TweenAnimationBuilder<double>),
          matching: find.byType(Transform),
        );
        final transform0 = tester.widget<Transform>(stickerTransformFinder);
        // Vector_math 4x4 matrix storage[0] represents the 2D x-axis scale
        final scale0 = transform0.transform.storage[0];
        expect(scale0, closeTo(0.6, 0.05));

        // Frame 150ms: mid-way through 300ms easeOutBack curve
        await tester.pump(const Duration(milliseconds: 150));
        final transform150 = tester.widget<Transform>(stickerTransformFinder);
        final scale150 = transform150.transform.storage[0];
        expect(scale150, greaterThan(scale0));
        expect(scale150, isNot(equals(1.0)));

        // Frame 400ms: duration (300ms) complete, settled at 1.0
        await tester.pump(const Duration(milliseconds: 250));
        final transform400 = tester.widget<Transform>(stickerTransformFinder);
        final scale400 = transform400.transform.storage[0];
        expect(scale400, closeTo(1.0, 0.001));
      },
    );

    testWidgets(
      'celebration entrance interpolates scale and opacity across 0ms, 150ms, 400ms',
      (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            locale: const Locale('ar'),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () {
                    showCelebration(
                      context,
                      title: 'مبروك',
                      message: 'أتممت الدرس',
                      tier: CelebrationTier.quiet,
                    );
                  },
                  child: const Text('Show'),
                ),
              ),
            ),
          ),
        );

        await tester.tap(find.text('Show'));
        // 0ms: dialog transition starts at 0.0
        await tester.pump();

        final scaleTransitions = tester
            .widgetList<ScaleTransition>(find.byType(ScaleTransition))
            .toList();
        final fadeTransitions = tester
            .widgetList<FadeTransition>(find.byType(FadeTransition))
            .toList();

        // The celebration dialog transition is the middle scale and last fade
        final dialogScale0 = scaleTransitions[1];
        final dialogFade0 = fadeTransitions.last;
        expect(dialogScale0.scale.value, closeTo(0.0, 0.05));
        expect(dialogFade0.opacity.value, closeTo(0.0, 0.05));

        // 150ms: actively animating
        await tester.pump(const Duration(milliseconds: 150));
        final dialogScale150 = tester
            .widgetList<ScaleTransition>(find.byType(ScaleTransition))
            .toList()[1];
        final dialogFade150 = tester
            .widgetList<FadeTransition>(find.byType(FadeTransition))
            .toList()
            .last;
        expect(dialogScale150.scale.value, greaterThan(0.0));
        expect(dialogFade150.opacity.value, greaterThan(0.0));
        expect(dialogFade150.opacity.value, lessThan(1.0));

        // 400ms: completed (duration is Dt.base = 350ms)
        await tester.pump(const Duration(milliseconds: 250));
        final dialogScale400 = tester
            .widgetList<ScaleTransition>(find.byType(ScaleTransition))
            .toList()[1];
        final dialogFade400 = tester
            .widgetList<FadeTransition>(find.byType(FadeTransition))
            .toList()
            .last;
        expect(dialogScale400.scale.value, closeTo(1.0, 0.001));
        expect(dialogFade400.opacity.value, closeTo(1.0, 0.001));
      },
    );
  });
}
